import json
from memory.config import REDIS_URL, REDIS_TTL_SECONDS, REDIS_MAX_TURNS
_client = None
def _client_for_use():
    global _client
    if _client is None:
        import redis
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    return _client
def ping():
    try: return bool(_client_for_use().ping())
    except Exception: return False
def _key(cid): return f"tally-agent:conversation:{str(cid)}:turns"
def append_turn(cid, role, message):
    if not cid or not str(message).strip(): return False
    try:
        c = _client_for_use(); k = _key(cid)
        c.rpush(k, json.dumps({"role":str(role), "message":str(message)}, ensure_ascii=False))
        c.ltrim(k, -REDIS_MAX_TURNS, -1); c.expire(k, REDIS_TTL_SECONDS)
        return True
    except Exception: return False
def get_turns(cid):
    if not cid: return []
    try:
        out=[]
        for raw in _client_for_use().lrange(_key(cid),0,-1):
            try:
                x=json.loads(raw)
                if isinstance(x,dict) and x.get("role") and x.get("message"):
                    out.append({"role":str(x["role"]), "message":str(x["message"])})
            except Exception: pass
        return out
    except Exception: return []
def replace_turns(cid, turns):
    if not cid: return False
    try:
        c=_client_for_use(); k=_key(cid); c.delete(k)
        for t in (turns or [])[-REDIS_MAX_TURNS:]:
            if isinstance(t,dict): append_turn(cid,t.get("role",""),t.get("message",""))
        if turns: c.expire(k,REDIS_TTL_SECONDS)
        return True
    except Exception: return False
