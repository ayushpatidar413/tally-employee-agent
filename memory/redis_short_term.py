"""Redis layer for the Tally agent.  (SQLite stays the source of truth.)

Redis ka kaam yahan:
  1. recent turns cache         -> get_turns / append_turn / replace_turns
  2. last structured state      -> set_state / get_state     (period, filters, top rows of previous answer)
  3. pending clarification      -> set_pending / peek_pending / clear_pending
  4. LLM response cache         -> cache_get / cache_set      (prompt caching, restart-safe)

Har Redis failure LOG hoti hai (pehle silent thi) aur 30 sec ke liye circuit-breaker
lag jata hai, taaki Redis band ho to har request 2 sec na ruke.
"""
import json
import time

from memory.config import REDIS_URL, REDIS_TTL_SECONDS, REDIS_MAX_TURNS

PENDING_TTL = 900            # clarification 15 min tak valid
_BREAKER_SEC = 30
_L1_MAX = 300

_client = None
_last_warn = 0.0
_down_until = 0.0
_L1: dict = {}               # in-process fallback for LLM cache


def _client_for_use():
    global _client
    if _client is None:
        import redis
        _client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _client


def _available():
    return time.time() >= _down_until


def _fail(where, exc):
    global _down_until, _last_warn
    _down_until = time.time() + _BREAKER_SEC
    if time.time() - _last_warn > _BREAKER_SEC:
        _last_warn = time.time()
        print(f"[REDIS] {where} failed -> Redis skipped for {_BREAKER_SEC}s: {type(exc).__name__}: {exc}")


def _run(where, fn, default=None):
    if not _available():
        return default
    try:
        return fn(_client_for_use())
    except Exception as exc:
        _fail(where, exc)
        return default


def _key(cid, kind="turns"):
    return f"tally-agent:conversation:{str(cid)}:{kind}"


def _loads(raw):
    if not raw:
        return None
    try:
        val = json.loads(raw)
    except Exception:
        return None
    return val if isinstance(val, dict) else None


# ------------------------------------------------------------------ health
def ping():
    return bool(_run("ping", lambda c: c.ping(), False))


def status():
    target = str(REDIS_URL).split("@")[-1]
    try:
        c = _client_for_use()
        c.ping()
        return {"ok": True, "target": target, "keys": c.dbsize(),
                "ttl_seconds": REDIS_TTL_SECONDS, "max_turns": REDIS_MAX_TURNS}
    except Exception as exc:
        return {"ok": False, "target": target, "error": f"{type(exc).__name__}: {exc}",
                "hint": "Redis server chal raha hai? Docker: docker run -d --name redis -p 6379:6379 redis:7"}


# ------------------------------------------------------------ recent turns
def append_turn(cid, role, message):
    if not cid or not str(message).strip():
        return False
    payload = json.dumps({"role": str(role), "message": str(message)}, ensure_ascii=False)

    def op(c):
        k = _key(cid)
        p = c.pipeline()
        p.rpush(k, payload)
        p.ltrim(k, -REDIS_MAX_TURNS, -1)
        p.expire(k, REDIS_TTL_SECONDS)
        p.execute()
        return True

    return bool(_run("append_turn", op, False))


def get_turns(cid):
    if not cid:
        return []
    raws = _run("get_turns", lambda c: c.lrange(_key(cid), 0, -1), []) or []
    out = []
    for raw in raws:
        try:
            x = json.loads(raw)
        except Exception:
            continue
        if isinstance(x, dict) and x.get("role") and x.get("message"):
            out.append({"role": str(x["role"]), "message": str(x["message"])})
    return out


def replace_turns(cid, turns):
    """Atomic (MULTI/EXEC): delete + rpush ek hi transaction me."""
    if not cid:
        return False
    items = [
        json.dumps({"role": str(t["role"]), "message": str(t["message"])}, ensure_ascii=False)
        for t in (turns or [])[-REDIS_MAX_TURNS:]
        if isinstance(t, dict) and t.get("role") and t.get("message")
    ]

    def op(c):
        k = _key(cid)
        p = c.pipeline(transaction=True)
        p.delete(k)
        if items:
            p.rpush(k, *items)
            p.expire(k, REDIS_TTL_SECONDS)
        p.execute()
        return True

    return bool(_run("replace_turns", op, False))


# ------------------------------------------------------- last structured state
def set_state(cid, state):
    if not cid or not isinstance(state, dict):
        return False
    data = json.dumps(state, ensure_ascii=False, default=str)
    return bool(_run("set_state", lambda c: c.setex(_key(cid, "state"), REDIS_TTL_SECONDS, data), False))


def get_state(cid):
    if not cid:
        return None
    return _loads(_run("get_state", lambda c: c.get(_key(cid, "state")), None))


# ------------------------------------------------------ pending clarification
def set_pending(cid, data):
    if not cid or not isinstance(data, dict):
        return False
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return bool(_run("set_pending", lambda c: c.setex(_key(cid, "pending"), PENDING_TTL, payload), False))


def peek_pending(cid):
    if not cid:
        return None
    return _loads(_run("peek_pending", lambda c: c.get(_key(cid, "pending")), None))


def clear_pending(cid):
    if not cid:
        return False
    return bool(_run("clear_pending", lambda c: c.delete(_key(cid, "pending")), False))


# ----------------------------------------------------------------- LLM cache
def _l1_put(key, value, ttl):
    if len(_L1) >= _L1_MAX:
        _L1.clear()
    _L1[key] = (time.time() + ttl, value)


def cache_get(key):
    hit = _L1.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    raw = _run("cache_get", lambda c: c.get(f"tally-agent:llm:{key}"), None)
    if raw is None:
        return None
    try:
        val = json.loads(raw)
    except Exception:
        return None
    _l1_put(key, val, 60)
    return val


def cache_set(key, value, ttl=600):
    _l1_put(key, value, ttl)
    try:
        data = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return False
    return bool(_run("cache_set", lambda c: c.setex(f"tally-agent:llm:{key}", ttl, data), False))