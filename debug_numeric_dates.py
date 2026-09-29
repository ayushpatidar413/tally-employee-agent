import re
from graph.dynamic_nodes import _normalize_text

qs = [
    "Show invoices for 2026-08",
    "Show invoices for 08-2026",
    "Show invoices for 15-08-2026",
    "Show invoices for 2026-08-15",
]

for q in qs:
    n = _normalize_text(q)

    print("\nQUESTION :", repr(q))
    print("NORMALIZED:", repr(n))

    ymd = re.search(
        r"\b(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])\b",
        n,
    )

    ym = re.search(
        r"\b(20\d{2})-(0?[1-9]|1[0-2])\b",
        n,
    )

    my = re.search(
        r"\b(0?[1-9]|1[0-2])-(20\d{2})\b",
        n,
    )

    dmy = re.search(
        r"\b(0?[1-9]|[12]\d|3[01])-(0?[1-9]|1[0-2])-(20\d{2})\b",
        n,
    )

    print("YYYY-MM-DD:", ymd.groups() if ymd else None)
    print("YYYY-MM    :", ym.groups() if ym else None)
    print("MM-YYYY    :", my.groups() if my else None)
    print("DD-MM-YYYY :", dmy.groups() if dmy else None)
