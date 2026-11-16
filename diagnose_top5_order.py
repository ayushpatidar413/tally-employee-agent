from pathlib import Path

p = Path("services/semantic_query_service.py")
s = p.read_text(encoding="utf-8")

top5 = s.index("# CONTEXTUAL_TOP5_MONTHLY_DECLINE_V1")
decline = s.index("# DETERMINISTIC ALL-PRODUCT MONTHLY SALES DECLINE")

print("Top5 handler line:", s[:top5].count("\n") + 1)
print("Generic decline handler line:", s[:decline].count("\n") + 1)
print("Top5 before generic:", top5 < decline)

print("\n--- Generic handler return statements ---")
block = s[decline:top5]
for i, line in enumerate(block.splitlines(), 1):
    if "return " in line or "decline_query" in line:
        print(f"{i}: {line.strip()}")
