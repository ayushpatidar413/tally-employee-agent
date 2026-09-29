from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
s = p.read_text(encoding="utf-8")

start = s.find("def _extract_date_filters(")
end = s.find("\ndef ", start + 1)

section = s[start:end]

dmy_start = section.find("# DD-MM-YYYY")
invoice_start = section.find("# INVOICE DETAIL QUERY", dmy_start)

print("========== CURRENT DMY BLOCK ==========")
print(section[dmy_start:invoice_start])
print("=======================================")
