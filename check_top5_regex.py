from pathlib import Path
from datetime import datetime
import shutil
import py_compile

path = Path("services/semantic_query_service.py")
source = path.read_text(encoding="utf-8")

start_marker = "# CONTEXTUAL_TOP5_MONTHLY_DECLINE_V1"
end_marker = "# DETERMINISTIC ALL-PRODUCT MONTHLY SALES DECLINE"

start = source.find(start_marker)
end = source.find(end_marker, start)

if start < 0 or end < 0:
    raise RuntimeError("Top5 handler markers not found. No changes made.")

block = source[start:end]

# Only inspect the two regex groups that identify the prior Top 5 query.
old_patterns = [
    r'r"\\btop\\s*5\\b"',
    r'r"\\b(?:product|products|item|items)\\b"',
]

for pattern in old_patterns:
    print(f"{pattern}: {block.count(pattern)} occurrence(s)")

# Correct doubled backslashes in this handler's regex source.
fixed_block = block.replace(r"\\", r"\\"[0:1])

if fixed_block == block:
    print("No doubled backslashes found in this handler.")
else:
    backup = path.with_name(
        path.name + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
    )
    shutil.copy2(path, backup)
    path.write_text(source[:start] + fixed_block + source[end:], encoding="utf-8")

    try:
        py_compile.compile(str(path), doraise=True)
    except Exception:
        shutil.copy2(backup, path)
        print("Compile failed; original file restored.")
        raise

    print("Regex escaping corrected; compile passed.")
    print("Backup:", backup)
