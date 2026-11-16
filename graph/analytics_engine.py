import re
import pandas as pd

RS = "\u20b9"

METRICS = [
    ("invoice_count", r"invoice[\s-]*count|number of invoices|count of invoices|invoices? count",
     ["InvoiceNo", "Invoice No", "Invoice Number"], "Invoice Count"),
    ("margin", r"profit[\s-]*margin|margin", None, "Profit Margin %"),
    ("profit", r"\bprofit", ["Profit"], "Profit"),
    ("sales", r"\bsales?\b|\brevenue|\bturnover|\bbilling", ["GrossAmount", "Gross Amount", "Sales Amount", "SalesAmount"], "Sales"),
    ("gst", r"\bgst\b|\btax\b", ["TotalGST", "Total GST", "GST"], "GST"),
    ("discount", r"discount", ["DiscountAmt", "Discount Amount", "Discount"], "Discount"),
    ("quantity", r"quantity|\bqty\b|\bunits\b", ["Qty", "Quantity"], "Quantity"),
    ("purchase", r"\bpurchases?\b", ["PurchaseAmount", "Purchase Amount", "Purchase"], "Purchase"),
]
LABEL = {m[0]: m[3] for m in METRICS}

DIMS = [
    ("customer", r"\bcustomers?\b|\bpart(?:y|ies)\b|\bclients?\b", ["PartyName", "Party Name", "Customer Name"]),
    ("product", r"\bproducts?\b|\bitems?\b", ["Product", "Item Name", "Item"]),
    ("category", r"\bcategor(?:y|ies)\b", ["Category"]),
    ("state", r"\bstates?\b", ["PartyState", "State"]),
    ("payment", r"payment[\s-]*modes?", ["PaymentMode", "Payment Mode"]),
]

PERIODS = [
    ("M", r"month[\s-]*wise|monthly|by month|each month|every month|per month|month[\s-]*over[\s-]*month"),
    ("Y", r"year[\s-]*wise|yearly|annual|by year|year[\s-]*over[\s-]*year"),
    ("Q", r"quarter[\s-]*wise|quarterly|by quarter|quarter[\s-]*over[\s-]*quarter"),
]


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_col(columns, candidates):
    index = {_norm(c): c for c in columns}
    for cand in candidates or []:
        if _norm(cand) in index:
            return index[_norm(cand)]
    return None


def _detect_metrics(q):
    text = q
    found = []
    for key, rx, _cands, _label in METRICS:
        for m in re.finditer(rx, text):
            found.append((m.start(), key))
            text = text[:m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    found.sort()
    keys = []
    for _pos, key in found:
        if key not in keys:
            keys.append(key)
    return keys, [p for p, _ in sorted(found)]


def _fmt(key, v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if key in ("invoice_count", "quantity"):
        return "{:,.0f}".format(v)
    if key in ("margin", "pct"):
        return "{:,.2f}%".format(v)
    return RS + "{:,.2f}".format(v)


def _table_text(title, headers, rows):
    out = [title, "", "| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def _calc(df, keys, cols, by_series=None):
    need = list(keys)
    if "margin" in keys:
        for k in ("profit", "sales"):
            if k not in need:
                need.append(k)
    base = [k for k in need if k != "margin"]
    work = pd.DataFrame({
        k: (df[cols[k]] if k == "invoice_count" else pd.to_numeric(df[cols[k]], errors="coerce"))
        for k in base
    })
    aggmap = {k: ("nunique" if k == "invoice_count" else "sum") for k in base}
    if by_series is None:
        res = work.agg(aggmap).to_frame().T
    else:
        names = []
        for i, s in enumerate(by_series):
            work["__by%d" % i] = s.values
            names.append("__by%d" % i)
        res = work.groupby(names).agg(aggmap)
        res.index = res.index.map(lambda t: t if isinstance(t, tuple) else (t,))
    if "margin" in keys:
        res["margin"] = (res["profit"] / res["sales"].where(res["sales"] != 0)) * 100
    return res


def _period_filter(q, df, dcol):
    m = re.search(r"\b(latest|last|previous|prior|recent)\s+(?:available\s+)?(?:(\d+)\s+)?(month|year|quarter)s?\b", q)
    if not m:
        return df, None
    word, n, unit = m.group(1), m.group(2), m.group(3)
    freq = {"month": "M", "year": "Y", "quarter": "Q"}[unit]
    per = df[dcol].dt.to_period(freq)
    uniq = sorted(per.dropna().unique())
    if not uniq:
        return df, None
    if n:
        sel = uniq[-int(n):]
    elif word in ("previous", "prior"):
        sel = uniq[-2:-1] if len(uniq) > 1 else []
    else:
        sel = uniq[-1:]
    label = "%s %s%s: %s" % (word, (n + " ") if n else "", unit, ", ".join(map(str, sel)))
    return df[per.isin(sel)], label


def _chart(q, kind_default, x, series_names, records):
    if not re.search(r"chart|visuali[sz]e|plot|graph|trend", q):
        return None
    kind = kind_default
    if re.search(r"\bpie\b", q):
        kind = "pie"
    elif re.search(r"donut", q):
        kind = "donut"
    elif re.search(r"\bline\b|trend", q):
        kind = "line"
    elif re.search(r"\barea\b", q):
        kind = "area"
    elif re.search(r"scatter", q):
        kind = "scatter"
    return {"type": kind, "x": x, "series": series_names, "interactive": True, "data": records}


def _run(state):
    q = str(state.get("original_question") or state.get("question") or "").lower()
    if not q.strip():
        return None
    dataset = state.get("dataset") or {}
    rows = state.get("rows") or []
    if not rows:
        from graph.dynamic_nodes import load_dataset_rows
        rows = load_dataset_rows(int(state.get("dataset_id") or dataset.get("id")))
    rows = [(r.get("row_data") or r.get("data") or r) if isinstance(r, dict) else r for r in rows]
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    cols_all = list(df.columns)

    keys, positions = _detect_metrics(q)
    avg_conds = []
    for m in re.finditer(r"\b(sales?|revenue|profit|gst|discount|quantity|qty)\s+(above|below|higher than|lower than|greater than|less than|more than)\s+(?:the\s+)?average", q):
        k = _detect_metrics(m.group(1))[0]
        if k:
            avg_conds.append((k[0], m.group(2) in ("above", "higher than", "greater than", "more than")))

    entity = None
    best = None
    for name, rx, cands in DIMS:
        m = re.search(rx, q)
        if m and (best is None or m.start() < best):
            best, entity = m.start(), (name, cands)
    period_freq = None
    for freq, rx in PERIODS:
        if re.search(rx, q):
            period_freq = freq
            break

    is_compare = bool(re.search(r"\bcompare\b", q)) and bool(re.search(r"(latest|current).*(previous|prior|last)", q))
    is_growth = bool(re.search(r"growth|month[\s-]*over[\s-]*month|year[\s-]*over[\s-]*year|quarter[\s-]*over[\s-]*quarter", q)) and period_freq
    topn = re.search(r"\b(top|bottom|best|worst)\s+(\d+)\b", q)
    wants_chart = bool(re.search(r"chart|visuali[sz]e|plot|graph", q))

    handles = (
        is_compare
        or is_growth
        or bool(avg_conds and entity)
        or (bool(keys) and (entity or period_freq) and (len(keys) >= 2 or wants_chart or topn))
    )
    if not handles or (not keys and not avg_conds):
        return None

    dcol = _find_col(cols_all, ["Date", "Bill Date", "Invoice Date", "Transaction Date"])
    if dcol:
        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")

    cols, missing = {}, []
    for k in keys:
        if k == "margin":
            continue
        spec = next(m for m in METRICS if m[0] == k)
        c = _find_col(cols_all, spec[2])
        if c:
            cols[k] = c
        else:
            missing.append(k)
    keys = [k for k in keys if k not in missing]
    if "margin" in keys and not ("profit" in cols or _find_col(cols_all, ["Profit"])):
        keys.remove("margin")
        missing.append("margin")
    for k in ("profit", "sales"):
        if "margin" in keys and k not in cols:
            cols[k] = _find_col(cols_all, next(m for m in METRICS if m[0] == k)[2])
    notes = []
    if missing:
        notes.append("Not available in this dataset (not calculated): " + ", ".join(LABEL[k] for k in missing))
    if not keys:
        return {"answer": "DATA_NOT_AVAILABLE: " + ", ".join(LABEL[k] for k in missing),
                "result": {"operation": "engine", "status": "DATA_NOT_AVAILABLE"}}

    for f in (state.get("query_plan") or {}).get("filters") or []:
        if isinstance(f, dict) and f.get("type") == "categorical" and f.get("column") in df.columns:
            vals = f.get("value")
            vals = vals if isinstance(vals, (list, tuple, set)) else [vals]
            lowered = {str(v).strip().lower() for v in vals}
            df = df[df[f["column"]].astype(str).str.strip().str.lower().isin(lowered)]
            notes.append("Filter: %s in %s" % (f["column"], sorted(lowered)))

    ent_col = _find_col(cols_all, entity[1]) if entity else None
    if entity and not ent_col and not (is_compare or is_growth):
        return {"answer": "DATA_NOT_AVAILABLE: no %s column in this dataset" % entity[0],
                "result": {"operation": "engine", "status": "DATA_NOT_AVAILABLE"}}
    if (is_compare or is_growth or period_freq) and not dcol:
        return {"answer": "DATA_NOT_AVAILABLE: no date column in this dataset",
                "result": {"operation": "engine", "status": "DATA_NOT_AVAILABLE"}}

    result = {"operation": "engine", "source_rows": int(len(rows))}
    chart = None

    # ---------------- COMPARE latest vs previous ----------------
    if is_compare:
        unit = "month"
        mm = re.search(r"(month|year|quarter)", q)
        if mm:
            unit = mm.group(1)
        freq = {"month": "M", "year": "Y", "quarter": "Q"}[unit]
        per = df[dcol].dt.to_period(freq)
        uniq = sorted(per.dropna().unique())
        if len(uniq) < 2:
            return {"answer": "DATA_NOT_AVAILABLE: fewer than two %s periods in data" % unit,
                    "result": {"operation": "engine", "status": "DATA_NOT_AVAILABLE"}}
        prev_p, last_p = uniq[-2], uniq[-1]
        a = _calc(df[per == prev_p], keys, cols).iloc[0]
        b = _calc(df[per == last_p], keys, cols).iloc[0]
        trows, recs = [], []
        for k in keys:
            diff = b[k] - a[k]
            pct = (diff / a[k] * 100) if a[k] else float("nan")
            trows.append([LABEL[k], _fmt(k, a[k]), _fmt(k, b[k]),
                          _fmt(k, diff) if k != "margin" else "{:,.2f} pts".format(diff), _fmt("pct", pct)])
            recs.append({"metric": LABEL[k], str(prev_p): float(a[k]), str(last_p): float(b[k]),
                         "abs_change": float(diff), "pct_change": None if pd.isna(pct) else float(pct)})
        text = _table_text("Comparison: latest %s %s vs previous %s %s" % (unit, last_p, unit, prev_p),
                           ["Metric", str(prev_p), str(last_p), "Abs change", "% change"], trows)
        result["table"] = recs
        chart = _chart(q, "bar", "metric", [str(prev_p), str(last_p)], recs)

    # ---------------- GROWTH over periods ----------------
    elif is_growth:
        freq = period_freq
        full = df.copy()
        per_full = full[dcol].dt.to_period(freq)
        tab = _calc(full, keys, cols, [per_full.astype(str)])
        tab.index = [t[0] for t in tab.index]
        tab = tab.sort_index()
        growth_keys = [k for k in keys if k != "margin"]
        for k in growth_keys:
            tab[k + "_pct"] = tab[k].pct_change() * 100
        scoped, label = _period_filter(q, df, dcol)
        if label:
            allowed = set(scoped[dcol].dt.to_period(freq).astype(str))
            tab = tab[tab.index.isin(allowed)]
            notes.append("Period scope: " + label)
        headers = ["Period"]
        for k in keys:
            headers.append(LABEL[k])
            if k in growth_keys:
                headers.append(LABEL[k] + " growth %")
        trows, recs = [], []
        for idx, r in tab.iterrows():
            line, rec = [idx], {"period": idx}
            for k in keys:
                line.append(_fmt(k, r[k]))
                rec[k] = float(r[k])
                if k in growth_keys:
                    line.append(_fmt("pct", r[k + "_pct"]))
                    rec[k + "_growth_pct"] = None if pd.isna(r[k + "_pct"]) else float(r[k + "_pct"])
            trows.append(line)
            recs.append(rec)
        first = growth_keys[0] if growth_keys else None
        if first:
            g = tab[first + "_pct"].dropna()
            if len(g):
                notes.append("Highest %s growth: %s (%s)" % (LABEL[first], g.idxmax(), _fmt("pct", g.max())))
                notes.append("Lowest %s growth: %s (%s)" % (LABEL[first], g.idxmin(), _fmt("pct", g.min())))
        text = _table_text("Growth by period (growth is vs the immediately preceding period in the data)", headers, trows)
        result["table"] = recs
        chart = _chart(q, "line", "period", [LABEL[k] for k in keys], recs) if wants_chart or "trend" in q else None

    # ---------------- ENTITY: top/bottom/average-condition/group ----------------
    elif entity:
        sub, label = _period_filter(q, df, dcol) if dcol else (df, None)
        if label:
            notes.append("Period scope: " + label)
        need_keys = list(keys)
        for k, _above in avg_conds:
            if k not in need_keys:
                need_keys.append(k)
            if k not in cols:
                spec = next(m for m in METRICS if m[0] == k)
                cols[k] = _find_col(cols_all, spec[2])
        if any(cols.get(k) is None for k in need_keys if k != "margin"):
            return None
        tab = _calc(sub, need_keys, cols, [sub[ent_col].astype(str)])
        tab.index = [t[0] for t in tab.index]
        if avg_conds:
            for k, above in avg_conds:
                avg = tab[k].mean()
                tab = tab[tab[k] > avg] if above else tab[tab[k] < avg]
                notes.append("Average customer %s = %s; kept %s" % (LABEL[k], _fmt(k, avg), "above" if above else "below"))
        rank_key = keys[0] if keys else avg_conds[0][0]
        for k in keys:
            pass
        mby = re.search(r"\bby\s+", q)
        if mby:
            after = [(p, k) for p, k in zip(positions, _detect_metrics(q)[0]) if p >= mby.start()]
            cand = [k for _p, k in sorted(after)]
            if cand and cand[0] in keys:
                rank_key = cand[0]
        asc = bool(topn and topn.group(1) in ("bottom", "worst")) or bool(re.search(r"\b(lowest|least)\b", q))
        tab = tab.sort_values(rank_key, ascending=asc)
        total = len(tab)
        limit = int(topn.group(2)) if topn else 20
        tab = tab.head(limit)
        show = need_keys
        trows = [[i + 1, idx] + [_fmt(k, r[k]) for k in show] for i, (idx, r) in enumerate(tab.iterrows())]
        recs = [dict({"rank": i + 1, ent_col: idx}, **{k: float(r[k]) for k in show}) for i, (idx, r) in enumerate(tab.iterrows())]
        title = "%s %s by %s" % ("Bottom" if asc else "Top", len(tab), LABEL[rank_key]) if topn else \
            "%s-wise result (%d of %d rows shown)" % (ent_col, len(tab), total)
        if avg_conds:
            title = "%d %s match the condition (showing %d)" % (total, ent_col, len(tab))
        text = _table_text(title, ["#", ent_col] + [LABEL[k] for k in show], trows)
        result["table"] = recs
        chart = _chart(q, "bar", ent_col, [LABEL[k] for k in show], recs)

    # ---------------- PERIOD grouping ----------------
    else:
        sub, label = _period_filter(q, df, dcol)
        if label:
            notes.append("Period scope: " + label)
        tab = _calc(sub, keys, cols, [sub[dcol].dt.to_period(period_freq).astype(str)])
        tab.index = [t[0] for t in tab.index]
        tab = tab.sort_index()
        trows = [[idx] + [_fmt(k, r[k]) for k in keys] for idx, r in tab.iterrows()]
        recs = [dict({"period": idx}, **{k: float(r[k]) for k in keys}) for idx, r in tab.iterrows()]
        text = _table_text("Result by period", ["Period"] + [LABEL[k] for k in keys], trows)
        result["table"] = recs
        chart = _chart(q, "line", "period", [LABEL[k] for k in keys], recs)

    if notes:
        text += "\n\n" + "\n".join("- " + n for n in notes)
    if chart:
        result["chart_spec"] = chart
    result["engine_answer"] = text
    result["notes"] = notes
    result["filtered_rows"] = int(len(df))
    return {"answer": text, "result": result}


def engine_done(state):
    r = state.get("result")
    return isinstance(r, dict) and bool(r.get("engine_answer"))


def wrap_execute(fn):
    def inner(state):
        plan = state.get("query_plan") or {}

        universal_operation = str(
            plan.get("operation") or ""
        ).strip().lower()

        universal_plan_ready = (
            isinstance(plan, dict)
            and str(plan.get("status") or "").upper() == "OK"
            and universal_operation in {
                "aggregate",
                "group_aggregate",
                "count",
                "ranking",
            }
        )

        if universal_plan_ready:
            return fn(state)

        try:
            out = _run(state)
        except Exception as exc:
            print("[ENGINE ERROR]", type(exc).__name__, exc)
            out = None

        if out is None:
            return fn(state)

        res = out["result"]

        if "engine_answer" not in res:
            res["engine_answer"] = out["answer"]

        return {
            **state,
            "result": res,
            "error": None,
        }

    return inner


def wrap_chart(fn):
    def inner(state):
        return fn(state)
    return inner


def wrap_answer(fn):
    def inner(state):
        if engine_done(state):
            return {**state, "answer": state["result"]["engine_answer"]}
        return fn(state)
    return inner
