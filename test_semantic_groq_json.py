import os
from dotenv import load_dotenv

load_dotenv()

from services.semantic_query_service import _llm

if not os.getenv("GROQ_API_KEY"):
    raise SystemExit("GROQ_API_KEY missing")

result = _llm(
    "You are a JSON-only assistant. Return a valid JSON object with the requested key.",
    'Return JSON containing exactly this key and value: {"status": "GROQ_JSON_OK"}',
    True,
)

print("JSON RESULT:", result)
print("RESULT TYPE:", type(result).__name__)
