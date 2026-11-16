"""
memory/last_result.py
Structured snapshot of the LAST answer of a conversation (question, answer, top result rows,
scope notes). Lets follow-ups like "inme se top 3", "us customer ka profit", "pehle wale ka"
resolve against real names/numbers instead of a truncated chat text.
Stored in Redis when available, otherwise in a small in-process dict (TTL 2 hours).
"""
import json
import time

_LOCAL = {}
_TTL = 7200


def _key(cid):
    return f"tally-agent:conversation:{cid}:last_result"


def save(cid, question, answer, result):
    if not cid:
        return False
    result = result if isinstance(result, dict) else {}
    rows = result.get("table") or result.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    snap = {
        "question": str(question or "")[:400],
        "answer": str(answer or "")[:900],
        "rows": [r for r in rows[:10] if isinstance(r, dict)],
        "row_count": len(rows),
        "scope": [str(x)[:160] for x in (result.get("scope_notes") or [])[:4]],
        "ts": time.time(),
    }
    try:
        text = json.dumps(snap, ensure_ascii=False, default=str)
    except Exception:
        return False
    _LOCAL[str(cid)] = (time.time(), text)
    try:
        from memory.redis_short_term import _client_for_use
        c = _client_for_use()
        c.set(_key(cid), text, ex=_TTL)
    except Exception:
        pass
    return True


def load(cid):
    if not cid:
        return None
    text = None
    try:
        from memory.redis_short_term import _client_for_use
        text = _client_for_use().get(_key(cid))
    except Exception:
        text = None
    if not text:
        hit = _LOCAL.get(str(cid))
        if hit and time.time() - hit[0] < _TTL:
            text = hit[1]
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def format_snapshot(snap):
    if not snap:
        return ""
    lines = ["LAST RESULT (structured data of the previous answer). Resolve 'inme se / us / uska / "
             "pehla / top wala / same' against these exact names and numbers:",
             f"Question: {snap.get('question', '')}",
             f"Answer: {snap.get('answer', '')}"]
    rows = snap.get("rows") or []
    if rows:
        lines.append(f"Result rows (first {len(rows)} of {snap.get('row_count')}):")
        for r in rows:
            lines.append("  " + json.dumps(r, ensure_ascii=False, default=str)[:260])
    if snap.get("scope"):
        lines.append("Scope: " + "; ".join(snap["scope"]))
    return "\n".join(lines)[:3200]
