from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
s = p.read_text(encoding="utf-8")

start = s.find("def _deduplicate_filters(")

if start == -1:
    raise RuntimeError("_deduplicate_filters() not found")

end = s.find("\ndef ", start + 1)
if end == -1:
    end = len(s)

print("========== _deduplicate_filters() ==========")
print(s[start:end])
print("=============================================")
