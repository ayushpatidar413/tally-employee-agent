"""Guards for the dynamic agent: relevance check + report-shaped rows."""
import re
import difflib

try:
    from graph.dynamic_nodes import load_dataset_rows
except Exception:
    load_dataset_rows = None

NO_DATA_REASON = "The question does not match any column or value in the uploaded dataset."


def _tokens(text):
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text))
    return re.findall(r"[a-z0-9]+", text.lower())


def _norm(token):
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


_NEUTRAL_RAW = (
    "show display give tell list get find fetch see view report reports details detail data information info "
    "what which who whom whose where when why how much many is are was were be been am the a an of in on at for to by and or with from "
    "all any some each every please pls kindly me my our us we you your it its this that these those there their them they he she "
    "has have had do does did can could will would should may might also only just not no yes than then so if as about into out up down over under "
    "between during after before since till until within across against per wise vs versus "
    "total overall complete full whole entire "
    "month months monthly year years yearly annual quarter quarters quarterly week weeks weekly day days daily date today yesterday tomorrow "
    "last past previous prev current next latest recent first second third "
    "top bottom highest lowest best worst biggest smallest largest maximum minimum max min average avg mean sum count number numbers "
    "trend trends growth compare comparison rank ranking "
    "january february march april june july august september october november december jan feb mar apr jun jul aug sep sept oct nov dec fy ytd "
    "kya kitna kitni kis kisko kise kitne kaun kaise kab kahan hai hain hua hui hue ho tha thi ka ki ke ko me mein se par pe aur ya "
    "dikhao dikha batao bata do de dena sabse zyada kam jyada wala wali wale kul saal mahina mahine din "
    "sell bought buy most least change absolute difference increase decrease q1 q2 q3 q4 h1 h2 "
    "above below higher lower greater less more fewer calculate calc compute generate generated received receive make made median mode but newest oldest earliest correlation correlated summary summaries overview rolling moving cumulative running unique distinct different percent percentage share ratio chart graph plot pie bar line visual download export csv excel pdf name names contain contains containing except excluding including without like gap come comes came"
)

_BUSINESS_RAW = (
    "sales sale selling sold revenue turnover billing business profit margin gst cgst sgst igst tax taxable discount "
    "quantity qty price rate cost amount value invoice bill customer client party product item category brand state city region "
    "payment paid pending due balance purchase supplier vendor stock inventory expense income loss unit order gross net retail wholesale "
    "employee employees attendance present absent leave department staff worker checkin checkout working hours shift payroll "
    "bikri munafa nafa grahak maal kharidi udhar udhaar kimat daam karmchari upasthiti"
)




NEUTRAL = {_norm(w) for w in _NEUTRAL_RAW.split()}
BUSINESS = {_norm(w) for w in _BUSINESS_RAW.split()}

_VOCAB_CACHE = {}


def build_vocab(schema, rows):
    sv = set()
    for col in schema or []:
        if isinstance(col, dict):
            names = [col.get("source_column"), col.get("canonical_column")]
        else:
            names = [col]
        for name in names:
            if name:
                sv.update(_norm(t) for t in _tokens(name))
    vv = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        for value in row.values():
            if isinstance(value, str) and len(value) <= 80:
                vv.update(_norm(t) for t in _tokens(value))
    return sv, vv


def check_relevance(question, sv, vv):
    content = []
    for t in (_norm(t) for t in _tokens(question)):
        if len(t) < 2 or t.isdigit() or t in NEUTRAL:
            continue
        content.append(t)
    if not content:
        return True, [], []
    known = sv | vv | BUSINESS
    pool = None
    matched, unmatched = [], []
    for t in content:
        if t in known:
            matched.append(t)
            continue
        if len(t) >= 4:
            if pool is None:
                pool = list(known)
            if _near_match(t, known):
                matched.append(t)
                continue
        unmatched.append(t)
    ok = bool(matched) and not unmatched
    return ok, matched, unmatched


def _get_vocab(state):
    dataset_id = state.get("dataset_id")
    if dataset_id in _VOCAB_CACHE:
        return _VOCAB_CACHE[dataset_id]
    rows = state.get("rows") or []
    if not rows and load_dataset_rows is not None and dataset_id is not None:
        rows = load_dataset_rows(int(dataset_id)) or []
    vocab = build_vocab(state.get("schema"), rows)
    _VOCAB_CACHE[dataset_id] = vocab
    return vocab


def relevance_guard(node_function):
    """
    Dynamic relevance guard.

    The vocabulary check is advisory only. It must not reject a
    question merely because it contains an unfamiliar word,
    spelling mistake, product name, customer name, or Hinglish.

    The downstream planner and query engine determine whether
    the question can be answered from the selected dataset.
    """
    def wrapper(state):
        state = dict(state or {})

        question = (
            state.get("original_question")
            or state.get("raw_question")
            or state.get("question")
            or ""
        )
        question = str(question)

        # Preserve the original user input.
        state.setdefault("original_question", question)
        state.setdefault("raw_question", question)

        # Run the existing vocabulary check for diagnostics only.
        try:
            sv, vv = _get_vocab(state)

            if sv or vv:
                ok, matched, unmatched = check_relevance(
                    question, sv, vv
                )
            else:
                ok, matched, unmatched = True, [], []

            print(
                f"[GUARD-DYNAMIC] advisory_relevant={ok} "
                f"matched={matched} unmatched={unmatched} "
                f"question={question!r}"
            )

        except Exception as exc:
            print(
                "[GUARD-DYNAMIC] Advisory check failed; "
                f"continuing to planner: {exc}"
            )

        # Never reject a question based only on a fixed vocabulary.
        # The downstream workflow must decide whether data supports it.
        return node_function(state)

    return wrapper
def _add_report_rows(state):
    result = (state or {}).get("result")
    if not isinstance(result, dict):
        return state
    if result.get("rows") or result.get("table"):
        return state
    frows = result.get("filtered_rows")
    value = result.get("value")
    if not isinstance(frows, list) or not frows:
        return state
    if not all(isinstance(r, dict) for r in frows[:5]):
        return state
    if not isinstance(value, (int, float)):
        return state

    keys = list(frows[0].keys())
    date_col = next((k for k in keys if re.search(r"date", str(k), re.I)), None)
    if not date_col:
        return state

    metric_col = None
    for k in keys:
        if k == date_col:
            continue
        total, seen, ok = 0.0, 0, True
        for r in frows:
            v = r.get(k)
            if v is None or v == "":
                continue
            try:
                total += float(v)
                seen += 1
            except (TypeError, ValueError):
                ok = False
                break
        if ok and seen and abs(total - float(value)) <= max(0.01, abs(float(value)) * 1e-6):
            metric_col = k
            break
    if not metric_col:
        return state

    party_col = next((k for k in keys if re.search(r"party.?name|customer", str(k), re.I)), None)
    inv_col = next((k for k in keys if re.search(r"invoice.?no|invoice.?number", str(k), re.I)), None)

    groups = {}
    for r in frows:
        month = str(r.get(date_col) or "")[:7]
        if not month:
            continue
        g = groups.setdefault(month, {"sum": 0.0, "recs": 0, "inv": set(), "who": set()})
        try:
            g["sum"] += float(r.get(metric_col) or 0)
        except (TypeError, ValueError):
            pass
        g["recs"] += 1
        if inv_col and r.get(inv_col):
            g["inv"].add(r.get(inv_col))
        if party_col and r.get(party_col):
            g["who"].add(str(r.get(party_col)))
    if not groups:
        return state

    rows = []
    for month in sorted(groups):
        g = groups[month]
        row = {"Month": month}
        if party_col:
            row["Customers"] = ", ".join(sorted(g["who"]))
        row["Records"] = len(g["inv"]) if inv_col else g["recs"]
        row[str(metric_col)] = round(g["sum"], 2)
        rows.append(row)

    return {**state, "result": {**result, "rows": rows}}


def report_shape(node_function):
    """Runs AFTER the chart node. Adds month-wise rows for filtered engine results."""
    def wrapper(state):
        out = node_function(state)
        try:
            return _add_report_rows_v3(out)
        except Exception as exc:
            print("[REPORT-SHAPE] skipped:", exc)
            return out
    return wrapper

def answer_passthrough(node_function):
    """Preserve blocked answers and synchronize final aggregate metadata."""
    def wrapper(state):
        if (state.get("query_plan") or {}).get("reason") == NO_DATA_REASON:
            return state

        out = node_function(state)

        if not isinstance(out, dict):
            return out

        result = out.get("result") or state.get("result") or {}
        plan = out.get("query_plan") or state.get("query_plan") or {}

        if not isinstance(result, dict):
            result = {}
        if not isinstance(plan, dict):
            plan = {}

        # Prefer the actual executed result over potentially stale planner metadata.
        column = (
            result.get("aggregate_column")
            or plan.get("aggregate_column")
            or out.get("aggregate_column")
            or state.get("aggregate_column")
        )

        function = (
            result.get("aggregate_function")
            or plan.get("aggregate_function")
            or out.get("aggregate_function")
            or state.get("aggregate_function")
        )

        updated_result = dict(result)

        if column:
            updated_result["aggregate_column"] = column
        if function:
            updated_result["aggregate_function"] = function

        return {
            **out,
            "result": updated_result,
            "aggregate_column": column,
            "aggregate_function": function,
        }

    return wrapper

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _near_match(token, known):
    near = [w for w in known if w[:1] == token[:1] and abs(len(w) - len(token)) <= 2]
    return bool(near) and bool(difflib.get_close_matches(token, near, n=1, cutoff=0.8))


def _add_report_rows_v2(state):
    result = (state or {}).get("result")
    if not isinstance(result, dict):
        return state
    if result.get("rows") or result.get("table"):
        return state
    value = result.get("value")
    if not isinstance(value, (int, float)):
        return state

    text = str(result.get("engine_answer") or state.get("answer") or "")
    m = re.search(r"Customers matched:\s*(.+)", text)
    rows = state.get("rows") or []
    if not m or not rows or not isinstance(rows[0], dict):
        print("[REPORT-SHAPE] skipped: no matched customers or no rows")
        return state

    names = {n.strip().lower() for n in m.group(1).split(",") if n.strip()}
    keys = list(rows[0].keys())
    party_col = next((k for k in keys if re.search(r"party.?name|customer", str(k), re.I)), None)
    date_col = next((k for k in keys if re.search(r"date", str(k), re.I)), None)
    if not party_col or not date_col:
        print("[REPORT-SHAPE] skipped: party/date column not found in", keys)
        return state

    sub = [r for r in rows if str(r.get(party_col) or "").strip().lower() in names]
    expected = result.get("filtered_rows")
    if not sub or (isinstance(expected, int) and len(sub) != expected):
        print("[REPORT-SHAPE] skipped: matched rows", len(sub), "expected", expected)
        return state

    def close(total):
        return abs(total - float(value)) <= max(0.05, abs(float(value)) * 1e-6)

    metric_name, getter, sums = _prefer_gst(text, keys, sub, close)
    for k in keys:
        if k in (date_col, party_col):
            continue
        total, seen, ok = 0.0, 0, True
        for r in sub:
            v = r.get(k)
            if v is None or v == "":
                continue
            f = _num(v)
            if f is None:
                ok = False
                break
            total += f
            seen += 1
        if ok and seen:
            sums[k] = round(total, 2)
            if metric_name is None and close(total):
                metric_name, getter = k, (lambda r, k=k: _num(r.get(k)) or 0.0)
    if metric_name is None:
        tax = [k for k in keys
               if re.match(r"(cgst|sgst|igst)", str(k), re.I)
               and not re.search(r"rate|%|percent", str(k), re.I)]
        if tax:
            total = sum(_num(r.get(k)) or 0.0 for r in sub for k in tax)
            if close(total):
                metric_name = "GST"
                getter = (lambda r, tax=tax: sum(_num(r.get(k)) or 0.0 for k in tax))
    if metric_name is None:
        print("[REPORT-SHAPE] skipped: no column matches value", value, "| column sums:", sums)
        return state

    inv_col = next((k for k in keys if re.search(r"invoice.?no|invoice.?number", str(k), re.I)), None)
    groups = {}
    for r in sub:
        month = str(r.get(date_col) or "")[:7]
        if not month:
            continue
        g = groups.setdefault(month, {"sum": 0.0, "recs": 0, "inv": set(), "who": set()})
        g["sum"] += getter(r)
        g["recs"] += 1
        if inv_col and r.get(inv_col):
            g["inv"].add(r.get(inv_col))
        g["who"].add(str(r.get(party_col)))
    if not groups:
        return state

    out = []
    for month in sorted(groups):
        g = groups[month]
        out.append({
            "Month": month,
            "Customers": ", ".join(sorted(g["who"])),
            "Records": len(g["inv"]) if inv_col else g["recs"],
            metric_name: round(g["sum"], 2),
        })
    print("[REPORT-SHAPE] built", len(out), "monthly rows | metric:", metric_name)
    return {**state, "result": {**result, "rows": out}}

def _prefer_gst(text, keys, sub, close):
    """If the engine answer is about GST, report CGST+SGST+IGST together as 'GST'."""
    label = re.match(r"\s*(?:total\s+)?([A-Za-z ]+?)\s*:", text or "")
    name = label.group(1).strip().lower() if label else ""
    if name not in ("gst", "tax", "total gst"):
        return None, None, {}
    tax = [k for k in keys
           if re.match(r"(cgst|sgst|igst)", str(k), re.I)
           and not re.search(r"rate|%|percent", str(k), re.I)]
    if not tax:
        return None, None, {}
    total = sum(_num(r.get(k)) or 0.0 for r in sub for k in tax)
    if close(total):
        return "GST", (lambda r, tax=tax: sum(_num(r.get(k)) or 0.0 for k in tax)), {}
    return None, None, {}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}")


def _numv(v):
    try:
        return float(str(v).replace(",", "").replace("\u20b9", "").strip())
    except (TypeError, ValueError):
        return None


def _add_report_rows_v3(state):
    """Data-driven report rows: no column names or metric names hard-coded."""
    import itertools

    result = (state or {}).get("result")
    if not isinstance(result, dict):
        return state
    if result.get("rows") or result.get("table"):
        return state
    value = result.get("value")
    if not isinstance(value, (int, float)):
        return state

    text = str(result.get("engine_answer") or state.get("answer") or "")
    m = re.search(r"Customers matched:\s*(.+)", text)
    rows = state.get("rows") or []
    if not m or not rows or not isinstance(rows[0], dict):
        print("[REPORT-SHAPE] skipped: no matched names or no rows")
        return state

    names = {n.strip().lower() for n in m.group(1).split(",") if n.strip()}
    keys = list(rows[0].keys())

    # party column = the column that actually holds the matched names
    party_col, best = None, 0
    for k in keys:
        hits = sum(1 for r in rows if str(r.get(k) or "").strip().lower() in names)
        if hits > best:
            party_col, best = k, hits
    if not party_col:
        print("[REPORT-SHAPE] skipped: no column holds the matched names")
        return state

    sub = [r for r in rows if str(r.get(party_col) or "").strip().lower() in names]
    expected = result.get("filtered_rows")
    if isinstance(expected, int) and len(sub) != expected:
        print("[REPORT-SHAPE] skipped: matched rows", len(sub), "expected", expected)
        return state

    # date column = first column where (almost) every value looks like YYYY-MM...
    date_col = None
    for k in keys:
        if k == party_col:
            continue
        hits = sum(1 for r in sub if _ISO_DATE.match(str(r.get(k) or "")))
        if hits >= 0.9 * len(sub):
            date_col = k
            break

    numeric = {}
    for k in keys:
        if k in (party_col, date_col):
            continue
        total, seen, ok = 0.0, 0, True
        for r in sub:
            v = r.get(k)
            if v is None or v == "":
                continue
            f = _numv(v)
            if f is None:
                ok = False
                break
            total += f
            seen += 1
        if ok and seen:
            numeric[k] = total

    def close(total):
        return abs(total - float(value)) <= max(0.05, abs(float(value)) * 1e-6)

    label = re.match(r"\s*(?:total\s+)?([A-Za-z ]+?)\s*:", text)
    words = [w for w in re.findall(r"[a-z]+", (label.group(1) if label else "").lower())
             if w not in ("total", "sum", "average", "avg", "count", "of", "the")]
    cand = [k for k in numeric if any(w in str(k).lower() for w in words)]

    metric_cols = None
    for pool in (cand[:8], list(numeric)[:10]):
        for size in (1, 2, 3):
            for combo in itertools.combinations(pool, size):
                if close(sum(numeric[k] for k in combo)):
                    metric_cols = combo
                    break
            if metric_cols:
                break
        if metric_cols:
            break
    if not metric_cols:
        print("[REPORT-SHAPE] skipped: no column(s) add up to", value, "| sums:",
              {k: round(v, 2) for k, v in numeric.items()})
        return state

    if words:
        metric_name = words[0].upper() if len(words[0]) <= 4 else words[0].title()
    else:
        metric_name = str(metric_cols[0])

    def amount(r):
        return sum(_numv(r.get(k)) or 0.0 for k in metric_cols)

    inv_col = next((k for k in keys if re.search(r"invoice.?(no|number)", str(k), re.I)), None)
    groups = {}
    for r in sub:
        key = str(r.get(date_col))[:7] if date_col else str(r.get(party_col))
        if not key or key == "None":
            continue
        g = groups.setdefault(key, {"sum": 0.0, "recs": 0, "inv": set(), "who": set()})
        g["sum"] += amount(r)
        g["recs"] += 1
        if inv_col and r.get(inv_col):
            g["inv"].add(r.get(inv_col))
        g["who"].add(str(r.get(party_col)))
    if not groups:
        return state

    out = []
    for key in sorted(groups):
        g = groups[key]
        records = len(g["inv"]) if inv_col else g["recs"]
        if date_col:
            out.append({"Month": key, "Customers": ", ".join(sorted(g["who"])),
                        "Records": records, metric_name: round(g["sum"], 2)})
        else:
            out.append({"Customer": key, "Records": records, metric_name: round(g["sum"], 2)})
    print("[REPORT-SHAPE] built", len(out), "rows | metric:", metric_name,
          "| from columns:", list(metric_cols), "| date:", date_col, "| party:", party_col)
    return {**state, "result": {**result, "rows": out}}
