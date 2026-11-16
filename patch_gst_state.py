from pathlib import Path
from datetime import datetime
import shutil

p = Path("graph/analytics_extra.py")
s = p.read_text(encoding="utf-8")

backup = p.with_name(
    p.name + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
)
shutil.copy2(p, backup)
print("BACKUP:", backup)

# A. Let the filtered GST ratio handler process ratio questions first.
old = '''        and bool(re.search(r"\\b(compare|versus|vs|total|collected|gst)\\b", q))
    )
    if gst_compare:
'''

new = '''        and bool(re.search(r"\\b(compare|versus|vs|total|collected|gst)\\b", q))
        and not bool(re.search(
            r"\\bratio\\b|\\bpercentage\\b|\\bpercent\\b|\\bshare\\b", q
        ))
    )
    if gst_compare:
'''

if old not in s:
    raise RuntimeError("Existing gst_compare condition not found; no GST priority change made")

s = s.replace(old, new, 1)
print("FIXED: GST ratio queries bypass the unfiltered GST comparison handler")

# B. Resolve state names from the full dataset, not from already-filtered rows.
old_state = '''            states = sorted(
                work[state_col].dropna().astype(str).str.strip().unique(),
                key=len,
                reverse=True
            )'''

new_state = '''            states = sorted(
                df[state_col].dropna().astype(str).str.strip().unique(),
                key=len,
                reverse=True
            )'''

count = s.count(old_state)
if count < 2:
    raise RuntimeError(
        "Expected two state-filter blocks, found %d; no state changes applied" % count
    )

s = s.replace(old_state, new_state, 2)
print("FIXED: state names resolved against the full dataset")

# C. If the query explicitly names a state but it cannot be resolved,
# do not silently return results for all states.
old_gst_state = '''            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]

        if work.empty:
'''

new_gst_state = '''            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]
            elif re.search(
                r"\\b(andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|"
                r"goa|gujarat|haryana|himachal pradesh|jharkhand|karnataka|"
                r"kerala|madhya pradesh|maharashtra|manipur|meghalaya|mizoram|"
                r"nagaland|odisha|punjab|rajasthan|sikkim|tamil nadu|telangana|"
                r"tripura|uttar pradesh|uttarakhand|west bengal)\\b", q, re.I
            ):
                work = work.iloc[0:0]

        if work.empty:
'''

if old_gst_state not in s:
    raise RuntimeError("GST state-filter ending not found")

s = s.replace(old_gst_state, new_gst_state, 1)

old_month_state = '''            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]

        work[date_col] = _to_dt(work[date_col])
'''

new_month_state = '''            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]
            elif re.search(
                r"\\b(andhra pradesh|arunachal pradesh|assam|bihar|chhattisgarh|"
                r"goa|gujarat|haryana|himachal pradesh|jharkhand|karnataka|"
                r"kerala|madhya pradesh|maharashtra|manipur|meghalaya|mizoram|"
                r"nagaland|odisha|punjab|rajasthan|sikkim|tamil nadu|telangana|"
                r"tripura|uttar pradesh|uttarakhand|west bengal)\\b", q, re.I
            ):
                work = work.iloc[0:0]

        work[date_col] = _to_dt(work[date_col])
'''

if old_month_state not in s:
    raise RuntimeError("Monthly IGST state-filter ending not found")

s = s.replace(old_month_state, new_month_state, 1)

p.write_text(s, encoding="utf-8")
print("UPDATED:", p)
