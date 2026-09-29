from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
s = p.read_text(encoding="utf-8")

marker = """    # ============================================================
    # 2. INVOICE NUMBER"""

block = r'''    # ============================================================
    # NATURAL PAYMENT PHRASE
    #
    # Examples:
    #   paid by UPI
    #   paid by Cash
    #   paid by Card
    # ============================================================

    paid_by_match = re.search(
        r"\bpaid\s+by\s+(?P<value>[A-Za-z][A-Za-z0-9 _-]*?)"
        r"(?=\s+(?:for|with|where|having|and|or)\s+|[,;]|$)",
        question,
        flags=re.IGNORECASE,
    )

    if paid_by_match:
        payment_value = paid_by_match.group("value").strip()

        payment_column = _resolve_column(
            "payment mode",
            dataset,
            schema,
            rows,
        )

        if not payment_column:
            payment_column = _resolve_column(
                "payment method",
                dataset,
                schema,
                rows,
            )

        if payment_column and _to_number(payment_value) is None:
            filters.append(
                {
                    "column": payment_column,
                    "operator": "=",
                    "value": payment_value,
                    "type": "categorical",
                }
            )

'''

if marker not in s:
    raise SystemExit("INSERTION MARKER NOT FOUND")

s = s.replace(marker, block + marker, 1)
p.write_text(s, encoding="utf-8")

print("PAID BY FILTER ADDED")
