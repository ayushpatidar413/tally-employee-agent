"""Safe conversation-context helpers for the Tally dynamic data agent.

SQLite is the durable source of truth. Redis is a best-effort recent-turn cache;
Pinecone is a best-effort semantic index of conversational context, never a source
of business facts. Business values must always be recalculated from the currently
selected uploaded dataset.
"""
from memory.config import MEMORY_ENABLED
from memory.redis_short_term import replace_turns, append_turn
from memory.pinecone_long_term import recall, remember

MAX_RECENT_TURNS = 16
MAX_CONTEXT_CHARS = 1500


def _norm(turn):
    """Normalize SQLite/API/Redis message shapes to {role, message}."""
    if not isinstance(turn, dict):
        return None
    role = str(turn.get("role", "")).strip().lower()
    message = turn.get("message", turn.get("content", ""))
    if role not in {"user", "assistant", "system"}:
        return None
    message = str(message or "").strip()
    if not message:
        return None
    return {"role": role, "message": message[:MAX_CONTEXT_CHARS]}


def hydrate_recent(conversation_id, sqlite_history):
    """Return newest SQLite turns and refresh Redis from them (never trust stale cache)."""
    turns = [_norm(turn) for turn in (sqlite_history or [])]
    turns = [turn for turn in turns if turn]
    turns = turns[-MAX_RECENT_TURNS:]
    if not MEMORY_ENABLED or not conversation_id:
        return turns
    try:
        replace_turns(str(conversation_id), turns)
    except Exception as exc:
        # Memory infrastructure must not prevent an otherwise valid query.
        print("[MEMORY] Redis hydration skipped:", type(exc).__name__)
    return turns


def retrieve_relevant(conversation_id, query, dataset_id=None, top_k=3):
    """Recall only scoped, high-relevance conversational hints.

    When dataset_id is unknown, do not retrieve semantic memories: recent SQLite
    history is safer than mixing memories from different uploaded datasets.
    """
    if not MEMORY_ENABLED or not conversation_id or not str(query or "").strip():
        return []
    if dataset_id is None:
        return []
    try:
        return recall(
            str(conversation_id), str(query), top_k=top_k, dataset_id=dataset_id
        )
    except Exception as exc:
        print("[MEMORY] Relevant-memory retrieval skipped:", type(exc).__name__)
        return []


def remember_turn(conversation_id, role, message, dataset_id=None):
    """Best-effort write to Redis and Pinecone; SQLite should be written by caller first."""
    message = str(message or "").strip()
    role = str(role or "").strip().lower()
    if not MEMORY_ENABLED or not conversation_id or role not in {"user", "assistant", "system"} or not message:
        return
    try:
        append_turn(str(conversation_id), role, message)
    except Exception as exc:
        print("[MEMORY] Redis write skipped:", type(exc).__name__)
    try:
        remember(str(conversation_id), role, message, dataset_id=dataset_id)
    except Exception as exc:
        print("[MEMORY] Pinecone write skipped:", type(exc).__name__)


def format_memory_context(turns):
    """Format retrieved turns as context hints, not as factual business data."""
    formatted = []
    for turn in (turns or []):
        item = _norm(turn)
        if not item:
            continue
        score = turn.get("score") if isinstance(turn, dict) else None
        score_text = f" (relevance={float(score):.2f})" if isinstance(score, (int, float)) else ""
        formatted.append(f'{item["role"].upper()}{score_text}: {item["message"]}')
    return "\n".join(formatted)
