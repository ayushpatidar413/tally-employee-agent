from pathlib import Path
from datetime import datetime
import py_compile

p = Path("api.py")
s = p.read_text(encoding="utf-8")

start_marker = "        # Repair common mojibake variants of the rupee symbol."
end_marker = "            result[\"answer\"] = answer_text"

start = s.find(start_marker)
if start < 0:
    raise SystemExit("ERROR: Start marker not found. No changes made.")

end = s.find(end_marker, start)
if end < 0:
    raise SystemExit("ERROR: End marker not found. No changes made.")

end += len(end_marker)

backup = p.with_name(
    p.name + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
)
backup.write_text(s, encoding="utf-8")

replacement = r'''        # Repair common rupee-symbol mojibake variants.
        answer_text = result.get("answer")
        if isinstance(answer_text, str):
            answer_text = answer_text.replace("\u00e2\u0082\u00b9", "\u20b9")
            answer_text = answer_text.replace("\u00e2\u201a\u00b9", "\u20b9")
            answer_text = answer_text.replace("\u00e2\u00b9", "\u20b9")
            answer_text = answer_text.replace(
                "leading retail customerby month",
                "leading retail customer by month",
            )
            result["answer"] = answer_text'''

s = s[:start] + replacement + s[end:]
p.write_text(s, encoding="utf-8")
py_compile.compile(str(p), doraise=True)

print("SUCCESS: Clean replacement block installed.")
print("Backup:", backup)
print("Python syntax: OK")
