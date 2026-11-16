from pathlib import Path
from datetime import datetime
import shutil

src = Path("run_query_tests.py")
dst = Path("run_failed_query_tests.py")

if not src.exists():
    raise SystemExit("ERROR: run_query_tests.py project root mein nahi mili.")

if dst.exists():
    backup = dst.with_name(
        f"{dst.stem}.{datetime.now():%Y%m%d_%H%M%S}.bak{dst.suffix}"
    )
    shutil.copy2(dst, backup)
    print(f"Backup: {backup}")

s = src.read_text(encoding="utf-8")

start = s.index("CHATS = [")
end = s.index("\nSUSPECT =", start)

failed_chats = '''CHATS = [
    # Invalid/ambiguous product: should not silently switch to another product
    ["total sles of leathr walet", "uska profit?", "same for may", "kitni qty biki?"],
    ["leathr walet kitni qty biki", "uska profit", "same for may"],

    # Follow-ups after product/month query
    ["power bank sales in july 2026", "aur august?", "compare dono"],
    ["powr bnk sale july 2026", "aur august", "compare dono"],

    # Follow-ups after an engine failure in previous runs
    ["top 5 customers by sales", "inme se kiska margin sabse accha hai",
     "us customer ka profit", "uska product wise batao"],

    # Data/schema routing checks
    ["gst kitna laga total", "cgst sgst alag alag", "pichhle mahine ka"],
    ["discount percentage product wise", "sabse jyada discount kispe"],
    ["employee ki salary kitni hai"],

    # Month/entity follow-up checks
    ["konse prodct ki sale gir rhi hai", "sabse zyada kitna gira",
     "uska pichhle mahine ka sales"],
    ["shalini sharma ka profit", "uska sales bhi",
     "us customer ne kaun sa product jyada kharida"],
]'''

s = s[:start] + failed_chats + s[end:]
dst.write_text(s, encoding="utf-8")
print(f"Created: {dst}")
