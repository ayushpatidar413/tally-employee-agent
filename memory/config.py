import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
except Exception:
    pass
MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "true").strip().lower() in {"1","true","yes","on"}
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", "86400"))
REDIS_MAX_TURNS = int(os.getenv("REDIS_MAX_TURNS", "16"))
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "tally-agent-memory").strip()
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "tally-agent-memory").strip()
LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
