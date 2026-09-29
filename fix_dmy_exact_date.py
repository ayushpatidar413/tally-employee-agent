from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
s = p.read_text(encoding="utf-8")

start = s.find("def _extract_date_filters(")
if start == -1:
    raise RuntimeError("_extract_date_filters() not found")

end = s.find("\ndef ", start + 1)
if end == -1:
    end = len(s)

section = s[start:end]

dmy_start = section.find("    # DD-MM-YYYY")
if dmy_start == -1:
    raise RuntimeError("DD-MM-YYYY section not found")

# The DMY section ends immediately before the invoice-detail section.
dmy_end = section.find("    # ========================================================\n    # INVOICE DETAIL QUERY", dmy_start)

if dmy_end == -1:
    raise RuntimeError("End of DD-MM-YYYY section not found")

new_dmy = '''    # DD-MM-YYYY
    if not numeric_date_filters_added:
        dmy_match = re.search(
            r"\\b(0?[1-9]|[12]\\d|3[01])-(0?[1-9]|1[0-2])-(20\\d{2})\\b",
            question,
        )

        if dmy_match:
            day = int(dmy_match.group(1))
            month = int(dmy_match.group(2))
            year = int(dmy_match.group(3))

            filters.extend([
                {
                    "column": date_column,
                    "operator": "year",
                    "value": year,
                    "type": "date",
                },
                {
                    "column": date_column,
                    "operator": "month",
                    "value": month,
                    "type": "date",
                },
                {
                    "column": date_column,
                    "operator": "date",
                    "value": f"{year:04d}-{month:02d}-{day:02d}",
                    "type": "date",
                },
            ])

            numeric_date_filters_added = True

'''

section = section[:dmy_start] + new_dmy + section[dmy_end:]

s = s[:start] + section + s[end:]

p.write_text(s, encoding="utf-8")

print("DMY EXACT DATE FIXED")
