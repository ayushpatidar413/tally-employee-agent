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

# Find the next section after DMY.
dmy_end = section.find("    # ========================================================", dmy_start + 1)
if dmy_end == -1:
    raise RuntimeError("End of DMY section not found")

dmy_block = section[dmy_start:dmy_end]

# Remove the DMY block from its current position.
section_without_dmy = section[:dmy_start] + section[dmy_end:]

# Find MM-YYYY block.
my_start = section_without_dmy.find("    # MM-YYYY")
if my_start == -1:
    raise RuntimeError("MM-YYYY section not found")

# Insert DMY immediately before MM-YYYY.
section = (
    section_without_dmy[:my_start]
    + dmy_block
    + section_without_dmy[my_start:]
)

s = s[:start] + section + s[end:]

p.write_text(s, encoding="utf-8")

print("DATE FORMAT ORDER FIXED")
