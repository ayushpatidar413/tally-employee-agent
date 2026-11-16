"""Clean runner.  Usage:
   python ask.py "Show sales month-wise"
   python ask.py -f queries_850.txt            (batch -> results.csv, results.txt)
"""
import sys, os, io, re, warnings, contextlib
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def agent():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from graph.dynamic_workflow import dynamic_agent
    return dynamic_agent


def ask(a, q):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        r = a.invoke({"question": q})
    return str(r.get("answer") or "").strip(), r


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return
    a = agent()
    if args[0] == "-f":
        import csv
        csv.field_size_limit(2**31 - 1)
        qs = []
        for line in open(args[1], encoding="utf-8"):
            m = re.match(r"^\s*(\d+)\.\s+(.*\S)", line)
            qs.append((m.group(1), m.group(2)) if m else (str(len(qs) + 1), line.strip()))
        qs = [x for x in qs if x[1]]
        done = set()
        if os.path.exists("results.csv"):
            done = {r[0] for r in csv.reader(open("results.csv", encoding="utf-8-sig")) if r}
        with open("results.csv", "a", newline="", encoding="utf-8-sig") as fc, open("results.txt", "a", encoding="utf-8") as ft:
            w = csv.writer(fc)
            for n, q in qs:
                if n in done:
                    continue
                try:
                    ans, _ = ask(a, q)
                except Exception as e:
                    ans = "ERROR: " + repr(e)
                w.writerow([n, q, ans[:30000]]); fc.flush()
                ft.write("=" * 70 + "\n%s. %s\n%s\n" % (n, q, ans)); ft.flush()
                print("%s. %s -> %s" % (n, q[:60], ans.splitlines()[0][:60] if ans else "(empty)"))
        print("\nSaved: results.csv and results.txt (full answers)")
    else:
        q = " ".join(args)
        ans, r = ask(a, q)
        print("\nQ:", q, "\n" + "-" * 60 + "\n" + ans)
        if os.environ.get("ASK_DEBUG"):
            d_ = r.get("dataset") or {}
            print("\n[debug] dataset:", d_.get("id"), d_.get("name") or d_.get("dataset_name"), "| plan:", {k: (r.get("query_plan") or {}).get(k) for k in ("operation", "reason")})
        ch = (r.get("result") or {}).get("chart_spec")
        if ch:
            print("\n[chart: %s | x=%s | series=%s]" % (ch.get("type"), ch.get("x"), ch.get("series")))


main()