"""Redis + Pinecone health check.

CLI (project root se, venv active):
    python -m memory.health            # config + Redis + Pinecone stats
    python -m memory.health --roundtrip   # + Pinecone me test vector likh/padh/delete

API: GET /memory-status?roundtrip=false
"""
import hashlib
import json
import sys
import time

from memory import config as cfg


def redis_status():
    from memory import redis_short_term as rst
    out = rst.status()
    if out.get("ok"):
        try:
            c = rst._client_for_use()
            c.setex("tally-agent:healthcheck", 30, "ok")
            out["roundtrip"] = c.get("tally-agent:healthcheck") == "ok"
        except Exception as exc:
            out["roundtrip"] = False
            out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _ns_count(v):
    if isinstance(v, dict):
        return v.get("vector_count")
    return getattr(v, "vector_count", None)


def pinecone_status(roundtrip=False):
    out = {"enabled": bool(cfg.MEMORY_ENABLED), "api_key_present": bool(cfg.PINECONE_API_KEY),
           "index": cfg.PINECONE_INDEX_NAME, "namespace": cfg.PINECONE_NAMESPACE,
           "embedding_model": cfg.LOCAL_EMBEDDING_MODEL}
    if not cfg.PINECONE_API_KEY:
        out.update(ok=False, error="PINECONE_API_KEY missing")
        return out
    try:
        from pinecone import Pinecone
        from memory import pinecone_long_term as pl

        pc = Pinecone(api_key=cfg.PINECONE_API_KEY)
        desc = pc.describe_index(cfg.PINECONE_INDEX_NAME)
        index = pc.Index(cfg.PINECONE_INDEX_NAME)
        stats = index.describe_index_stats()
        namespaces = getattr(stats, "namespaces", None) or {}
        model_dim = pl._embedder().get_sentence_embedding_dimension()
        index_dim = getattr(desc, "dimension", None)
        out.update(
            index_dimension=index_dim, model_dimension=model_dim, metric=getattr(desc, "metric", None),
            total_vectors=getattr(stats, "total_vector_count", None),
            namespace_vectors={k: _ns_count(v) for k, v in dict(namespaces).items()},
            dimension_match=(index_dim == model_dim),
        )
        out["ok"] = bool(out["dimension_match"])
        if not out["dimension_match"]:
            out["error"] = (f"Index dimension {index_dim} != embedding model dimension {model_dim}. "
                            "Upserts silently fail; naya index banao ya model badlo.")
        if roundtrip and out["ok"]:
            cid, msg = f"healthcheck-{int(time.time())}", "health check: which product has highest sales"
            wrote = pl.remember(cid, "user", msg, dataset_id="hc")
            vid = hashlib.sha256(f"{cid}|hc|user|{msg}".encode("utf-8")).hexdigest()
            got = []
            for _ in range(6):                      # Pinecone eventually consistent hai
                time.sleep(2)
                got = pl.recall(cid, "highest sales product", top_k=1, dataset_id="hc")
                if got:
                    break
            try:
                index.delete(ids=[vid], namespace=cfg.PINECONE_NAMESPACE)
            except Exception:
                pass
            out["roundtrip"] = {"written": wrote, "recalled": bool(got),
                                "score": got[0]["score"] if got else None}
            out["ok"] = bool(wrote and got)
    except Exception as exc:
        out.update(ok=False, error=f"{type(exc).__name__}: {exc}")
    return out


if __name__ == "__main__":
    rt = "--roundtrip" in sys.argv
    print(json.dumps({"redis": redis_status(), "pinecone": pinecone_status(roundtrip=rt)}, indent=2, default=str))
