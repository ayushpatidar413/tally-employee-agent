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

old = '''    # YYYY-MM-DD
    ymd_match = re.search(
        r"\\b(20\\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\\d|3[01])\\b",
        question_norm,
    )'''

new = '''    # YYYY-MM-DD
    ymd_match = re.search(
        r"\\b(20\\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\\d|3[01])\\b",
        question,
    )'''

if old not in section:
    raise RuntimeError("YYYY-MM-DD block not found")

section = section.replace(old, new, 1)

old = '''    # YYYY-MM
    if not numeric_date_filters_added:
        ym_match = re.search(
            r"\\b(20\\d{2})-(0?[1-9]|1[0-2])\\b",
            question_norm,
        )'''

new = '''    # YYYY-MM
    if not numeric_date_filters_added:
        ym_match = re.search(
            r"\\b(20\\d{2})-(0?[1-9]|1[0-2])\\b",
            question,
        )'''

if old not in section:
    raise RuntimeError("YYYY-MM block not found")

section = section.replace(old, new, 1)

old = '''    # MM-YYYY
    if not numeric_date_filters_added:
        my_match = re.search(
            r"\\b(0?[1-9]|1[0-2])-(20\\d{2})\\b",
            question_norm,
        )'''

new = '''    # MM-YYYY
    if not numeric_date_filters_added:
        my_match = re.search(
            r"\\b(0?[1-9]|1[0-2])-(20\\d{2})\\b",
            question,
        )'''

if old not in section:
    raise RuntimeError("MM-YYYY block not found")

section = section.replace(old, new, 1)

old = '''    # DD-MM-YYYY
    if not numeric_date_filters_added:
        dmy_match = re.search(
            r"\\b(0?[1-9]|[12]\\d|3[01])-(0?[1-9]|1[0-2])-(20\\d{2})\\b",
            question_norm,
        )'''

new = '''    # DD-MM-YYYY
    if not numeric_date_filters_added:
        dmy_match = re.search(
            r"\\b(0?[1-9]|[12]\\d|3[01])-(0?[1-9]|1[0-2])-(20\\d{2})\\b",
            question,
        )'''

if old not in section:
    raise RuntimeError("DD-MM-YYYY block not found")

section = section.replace(old, new, 1)

s = s[:start] + section + s[end:]

p.write_text(s, encoding="utf-8")

print("NUMERIC DATE PARSER FIXED")
