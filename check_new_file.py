import sys
from graph.dynamic_nodes import detect_dynamic_intent, select_dynamic_dataset, load_dataset_rows
from graph import guards

if len(sys.argv) < 2:
    s = {"question": "show data"}
    s = {**s, **(detect_dynamic_intent(s) or {})}
    s = {**s, **(select_dynamic_dataset(s) or {})}
    print("Available datasets (id | name):")
    for d in s.get("datasets") or []:
        ds = d.get("dataset", {})
        print(" ", ds.get("id"), "|", ds.get("original_filename"))
    print("Run again with:  python check_new_file.py <dataset_id>")
    sys.exit()

dataset_id = int(sys.argv[1])
rows = load_dataset_rows(dataset_id)
if not rows:
    print("No rows found for dataset", dataset_id)
    sys.exit()

cols = list(rows[0].keys())
sv, vv = guards.build_vocab(cols, rows)
print("dataset", dataset_id, "| rows:", len(rows), "| columns:", len(cols))
print("columns:", cols)

questions = [f"Show {c}" for c in cols]
num_cols = [c for c in cols if isinstance(rows[0].get(c), (int, float))]
text_cols = [c for c in cols if isinstance(rows[0].get(c), str)]
for c in num_cols[:5]:
    questions.append(f"Show total {c}")
    questions.append(f"Show {c} month wise")
    if text_cols:
        sample = str(rows[0].get(text_cols[0]))
        questions.append(f"{sample} {c}")

bad = []
for q in questions:
    ok, m, u = guards.check_relevance(q, sv, vv)
    if not ok:
        bad.append((q, u))
print("\nOWN-DATA QUESTIONS:", len(questions), "| wrongly rejected:", len(bad))
for q, u in bad:
    print("  WRONGLY REJECTED:", q, "| unmatched:", u)

print("\nOFF-TOPIC QUESTIONS (all should be REJECTED):")
for q in ["weather report", "weather today", "who won the cricket match", "recipe for pasta",
          "football score", "what is the capital of France", "show school details"]:
    ok, m, u = guards.check_relevance(q, sv, vv)
    print(("  WRONGLY PASSED:" if ok else "  rejected      :"), q, "| unmatched:", u)