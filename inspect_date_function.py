from pathlib import Path

p = Path(r".\graph\dynamic_nodes.py")
s = p.read_text(encoding="utf-8")

start = s.find("def _extract_date_filters(")
if start == -1:
    raise RuntimeError("_extract_date_filters() not found")

# Find the next top-level function after _extract_date_filters
rest = s[start + 1:]
next_func = rest.find("\ndef ")
if next_func == -1:
    end = len(s)
else:
    end = start + 1 + next_func

function_text = s[start:end]

print("========== _extract_date_filters() ==========")
print(function_text)
print("==============================================")
