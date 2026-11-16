from pathlib import Path
import re

p = Path("services/semantic_query_service.py")
s = p.read_text(encoding="utf-8")

checks = {
    "contextualize function": r"def _contextualize\(",
    "all-products decline block": r"DETERMINISTIC ALL-PRODUCT MONTHLY SALES DECLINE",
    "decline query condition": r"decline_query\s*=",
    "history parser": r"def _history_turns\(",
    "monthly comparison handler": r"def _latest_two_month_sales_followup_result\(",
}

print("=== SOURCE CHECK ===")
for name, pattern in checks.items():
    matches = list(re.finditer(pattern, s, re.I))
    print(f"{name}: {len(matches)} match(es)")
    for m in matches:
        print(f"  line {s.count(chr(10), 0, m.start()) + 1}")

print("\n=== DECLINE HANDLER ===")
marker = "DETERMINISTIC ALL-PRODUCT MONTHLY SALES DECLINE"
if marker in s:
    start = s.index(marker)
    print(s[start:start + 1800])
else:
    print("Marker not found; no changes made.")
