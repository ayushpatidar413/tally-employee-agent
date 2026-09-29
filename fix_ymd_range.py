from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
lines = p.read_text(encoding="utf-8").splitlines()

for i, line in enumerate(lines):
    if line.strip() == "if ymd_match:":
        lines[i] = "    if ymd_match and not ymd_is_range:"
        lines.insert(i, "")
        lines.insert(i, "    ymd_is_range = bool(")
        lines.insert(i + 1, "        re.search(")
        lines.insert(i + 2, '            r"\\b(?:from|between)\\s+"')
        lines.insert(i + 3, '            r"(?:\\d{4}-\\d{1,2}-\\d{1,2}|\\d{1,2}-\\d{1,2}-\\d{4})"')
        lines.insert(i + 4, '            r"\\s+(?:to|and)\\s+"')
        lines.insert(i + 5, '            r"(?:\\d{4}-\\d{1,2}-\\d{1,2}|\\d{1,2}-\\d{1,2}-\\d{4})\\b",')
        lines.insert(i + 6, "            question,")
        lines.insert(i + 7, "            flags=re.IGNORECASE,")
        lines.insert(i + 8, "        )")
        lines.insert(i + 9, "    )")
        break
else:
    raise SystemExit("TARGET IF STATEMENT NOT FOUND")

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("YMD RANGE FIXED")
