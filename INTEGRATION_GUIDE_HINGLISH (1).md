# Tally Agent Redis + Pinecone memory pack

## Current status
This ZIP contains memory modules, **not an automatic patch to api.py**. Keep `MEMORY_ENABLED=false` until API integration and tests are complete.

## Copy
Extract the ZIP into:
`C:\Users\91930\Desktop\project\tally-employee-agent`
It should create the `memory` folder in the project root.

## Non-secret .env settings
Add/verify these lines in the existing `.env`:
```
MEMORY_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_TTL_SECONDS=86400
REDIS_MAX_TURNS=16
PINECONE_INDEX_NAME=tally-agent-memory
PINECONE_NAMESPACE=tally-agent-memory
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```
Keep your existing `PINECONE_API_KEY` secret in `.env`; never print/share it.

## Import check
With venv activated from project root:
```
python -c "from memory.conversation_context import hydrate_recent, retrieve_relevant, remember_turn; print('Memory modules import OK')"
```

## Important
The existing SQLite DB remains the durable history. Before enabling memory, API integration must load SQLite history, hydrate Redis, retrieve Pinecone snippets, use those snippets only to resolve conversational references, and save each user/assistant turn once. Numerical sales/profit results must still be calculated from the uploaded dataset. This pack does not yet make those API changes.
