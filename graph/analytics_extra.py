"""analytics_extra v3 - deterministic handlers that run BEFORE the LLM planner / older pipeline.
Everything is derived from the loaded dataframe (columns + real values). Returns None when a question
is not recognised, so the older pipeline keeps working unchanged."""
import re
import pandas as pd

RS = "\u20b9"
MN = ["january","february","march","april","may","june","july","august","september","october","november","december"]
MRX = "|".join(MN)
STOP = set("the a an of for in on at to by and or with from between during is are was were what which who whom how much many "
           "show give me my our us list find tell get did do does we i you it this that these those total overall all each every any "
           "latest previous last recent prior first month months year years quarter quarters day days daily monthly yearly annual "
           "wise sales sale revenue turnover billing business amount value profit gst tax discount quantity qty units customer customers "
           "party parties product products category categories state states payment mode modes invoice invoices highest lowest top bottom "
           "best worst most least higher lower than compare comparison growth change trend rank ranking above below under over sold sell "
           "comes come coming contribute contributes contribution percent percentage share average correlated correlation summary rolling cumulative running".split())

METRICS = [
    ("count", r"invoice[\s-]*counts?|number of invoices|count of invoices|invoices? count|total invoices", ["__invcount__"], "Invoice Count"),
    ("margin", r"profit[\s-]*margin|\bmargins?\b", ["__derived__"], "Profit Margin %"),
    ("invoice_total", r"invoice\s*(?:value|amount|total)", ["InvoiceTotal", "Invoice Total", "Invoice Value"], "Invoice Value"),
    ("profit", r"\bprofit", ["Profit"], "Profit"),
    ("gst", r"\bgst\b|\btax\b", ["TotalGST", "Total GST", "GST"], "GST"),
    ("discount", r"discount", ["DiscountAmt", "Discount Amount", "Discount"], "Discount"),
    ("qty", r"quantit|\bqty\b|\bunits\b", ["Qty", "Quantity"], "Quantity"),
    ("sales", r"\bsales?\b|revenue|turnover|billing|business|\bsell\b|\bselling\b|\bsold\b", ["GrossAmount", "Gross Amount", "Sales Amount", "SalesAmount"], "Sales"),
]
CATS = [("PartyName", ["PartyName", "Party Name", "Customer Name"]), ("Product", ["Product", "Item Name"]),
        ("Category", ["Category"]), ("PartyState", ["PartyState", "State"]),
        ("PaymentMode", ["PaymentMode", "Payment Mode"]), ("PartyType", ["PartyType", "Party Type"])]
DIMS = [
    ("party type", r"party[\s-]*types?|customer[\s-]*types?", ["PartyType", "Party Type"]),
    ("customer", r"\bcustomers?\b|\bparty\b|\bparties\b|\bclients?\b|\bwho\b|\bbuyers?\b", ["PartyName", "Party Name", "Customer Name"]),
    ("product", r"\bproducts?\b|\bitems?\b", ["Product", "Item Name"]),
    ("category", r"\bcategor(?:y|ies)\b", ["Category"]),
    ("state", r"\bstates?\b", ["PartyState", "State"]),
    ("payment mode", r"payment[\s-]*modes?|payment[\s-]*methods?", ["PaymentMode", "Payment Mode"]),
]
NA_WORDS = {
    "purchase": (r"\bpurchas\w*", ["purchase"]),
    "supplier": (r"\bsuppliers?\b|\bvendors?\b", ["supplier", "vendor"]),
    "stock": (r"\bstock\b|\binventory\b", ["stock", "inventory"]),
    "outstanding": (r"\boutstanding\b|\boverdue\b|\breceivables?\b|\bunpaid\b", ["outstanding", "balance", "overdue"]),
    "employee": (r"\bemployees?\b|\battendance\b", ["employee", "attendance"]),
    "student": (r"\bstudents?\b|\bmarks\b|\bcgpa\b", ["student", "marks", "cgpa"]),
}
UP = r"highest|most|best|top|maximum|largest|biggest|higher|greatest"
DOWN = r"lowest|least|worst|bottom|minimum|smallest|lower|fewest"


def _n(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _col(cols, cands):
    idx = {_n(c): c for c in cols}
    for c in cands:
        if _n(c) in idx:
            return idx[_n(c)]
    return None


def _fmt(key, v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    if key in ("qty", "count"):
        return "{:,.0f}".format(v)
    if key == "pct":
        return "{:+,.2f}%".format(v)
    if key in ("margin", "share"):
        return "{:,.2f}%".format(v)
    return RS + "{:,.2f}".format(v)


def _table(title, head, rows):
    out = [title, "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def _out(txt, **extra):
    res = {"operation": "engine", "engine_answer": txt}
    res.update(extra)
    return {"answer": txt, "result": res}


def _na(msg):
    return {"answer": "DATA_NOT_AVAILABLE: " + msg,
            "result": {"operation": "engine", "status": "DATA_NOT_AVAILABLE", "engine_answer": "DATA_NOT_AVAILABLE: " + msg}}


def _metric(q):
    t = re.sub(r"(?:quantity|qty|units)\s+sold", "quantity", q)
    if re.search(r"quantit|\bqty\b|\bunits\b", t):
        t = re.sub(r"\bsold\b|\bselling\b|\bsell\b", " ", t)
    found = []
    for key, rx, cands, label in METRICS:
        m = re.search(rx, t)
        if m:
            found.append((m.start(), key, cands, label))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    found.sort()
    return found


def _money(q):
    """threshold: returns (op, number) or None. op in {'>','<'}"""
    m = re.search(r"\b(above|over|greater than|more than|exceed\w*|higher than|below|under|less than|lower than)\s+(?:rs\.?\s*|inr\s*|\u20b9\s*)?(\d[\d,]*(?:\.\d+)?)\s*(k|lakhs?|lacs?|crores?|cr|million|m)?\b", q)
    if not m:
        return None
    v = float(m.group(2).replace(",", ""))
    mult = {"k": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7, "million": 1e6, "m": 1e6}.get(m.group(3) or "", 1)
    up = m.group(1) in ("above", "over", "greater than", "more than", "higher than") or m.group(1).startswith("exceed")
    return (">" if up else "<"), v * mult


def _dates(q, default_year=None):
    """explicit dates found in text -> list of (pos, Timestamp). Handles dd-mm-yyyy, dd/mm/yyyy, yyyy-mm-dd, '15 august 2026', 'august 15, 2026', '1 august' (+year later)."""
    q = q.lower()
    found = []
    for m in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d\d)\b", q):
        try:
            found.append((m.start(), pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
        except ValueError:
            pass
    for m in re.finditer(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b", q):
        try:
            found.append((m.start(), pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))))
        except ValueError:
            pass
    yr = re.findall(r"\b(20\d\d)\b", q)
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(%s)(?:,?\s+(20\d\d))?\b" % MRX, q):
        y = m.group(3) or (yr[-1] if yr else default_year)
        if y:
            found.append((m.start(), pd.Timestamp(int(y), MN.index(m.group(2)) + 1, int(m.group(1)))))
    for m in re.finditer(r"\b(%s)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)\b" % MRX, q):
        found.append((m.start(), pd.Timestamp(int(m.group(3)), MN.index(m.group(1)) + 1, int(m.group(2)))))

    # English ordinal day words: third August 2026, August fifteenth 2026
    day_words = {
        "first": 1, "second": 2, "third": 3, "fourth": 4,
        "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
        "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12,
        "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
        "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
        "nineteenth": 19, "twentieth": 20, "twenty-first": 21,
        "twenty-second": 22, "twenty-third": 23, "twenty-fourth": 24,
        "twenty-fifth": 25, "twenty-sixth": 26, "twenty-seventh": 27,
        "twenty-eighth": 28, "twenty-ninth": 29, "thirtieth": 30,
        "thirty-first": 31,
        "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8,
        "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19,
        "eight": 8, "nine": 9,
        "twenty one": 21, "twenty two": 22, "twenty three": 23,
        "twenty four": 24, "twenty five": 25, "twenty six": 26,
        "twenty seven": 27, "twenty eight": 28, "twenty nine": 29,
        "thirty one": 31,
    }

    word_pattern = "|".join(
        re.escape(word) for word in sorted(day_words, key=len, reverse=True)
    )

    # Day word before month, with year required or inferred from query.
    for m in re.finditer(
        r"\b(" + word_pattern + r")\s+(" + MRX + r")(?:,?\s+(20\d{2}))?\b",
        q,
    ):
        y = m.group(3) or (yr[-1] if yr else default_year)
        if y:
            try:
                found.append((
                    m.start(),
                    pd.Timestamp(int(y), MN.index(m.group(2)) + 1, day_words[m.group(1)])
                ))
            except ValueError:
                pass

    # Month before day word: August fifteenth 2026 / August third, 2026
    for m in re.finditer(
        r"\b(" + MRX + r")\s+(" + word_pattern + r"),?\s+(20\d{2})\b",
        q,
    ):
        try:
            found.append((
                m.start(),
                pd.Timestamp(
                    int(m.group(3)),
                    MN.index(m.group(1)) + 1,
                    day_words[m.group(2)],
                ),
            ))
        except ValueError:
            pass

    found.sort()
    return found


def _scope(q, d, dc):
    """returns (df, notes, error_msg)"""
    notes = []
    if not dc:
        return d, notes, None
    ds = _dates(q)
    if len(ds) >= 2 and re.search(r"between|from|\bto\b|\band\b|till|until", q):
        a, b = ds[0][1], ds[1][1]
        if a > b:
            a, b = b, a
        d = d[(d[dc] >= a) & (d[dc] <= b + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]
        notes.append("Date range: %s to %s" % (a.date(), b.date()))
    elif len(ds) == 1:
        d = d[d[dc].dt.normalize() == ds[0][1]]
        notes.append("Date: %s" % ds[0][1].date())
    else:
        q_scope = q.lower()

        # Numeric month-year: 08-2026, 08/2026, 2026-08
        # Do not match a month-year fragment inside a full date.
        numeric_month_year = re.search(
            r"(?<![\d./-])(?:"
            r"(0?[1-9]|1[0-2])[-/.](20\d{2})|"
            r"(20\d{2})[-/.](0?[1-9]|1[0-2])"
            r")(?![\d./-])",
            q_scope,
        )

        yr = re.search(r"\b(20\d\d)\b", q_scope)
        mo = re.search(r"\b(%s)\b" % MRX, q_scope)
        qq = re.search(r"\bq([1-4])\b", q_scope)
        lab = []

        if numeric_month_year:
            if numeric_month_year.group(1):
                numeric_month = int(numeric_month_year.group(1))
                numeric_year = int(numeric_month_year.group(2))
            else:
                numeric_year = int(numeric_month_year.group(3))
                numeric_month = int(numeric_month_year.group(4))

            d = d[
                (d[dc].dt.month == numeric_month)
                & (d[dc].dt.year == numeric_year)
            ]

            lab.extend([MN[numeric_month - 1].title(), str(numeric_year)])
            yr = None
            mo = None
            qq = None
        if mo:
            d = d[d[dc].dt.month == MN.index(mo.group(1)) + 1]; lab.append(mo.group(1).title())
        if qq:
            d = d[d[dc].dt.quarter == int(qq.group(1))]; lab.append("Q" + qq.group(1))
        if yr:
            d = d[d[dc].dt.year == int(yr.group(1))]; lab.append(yr.group(1))
        if lab:
            notes.append("Scope: " + " ".join(lab))
            if (mo or qq) and not yr:
                yrs = sorted(set(d[dc].dt.year.dropna().astype(int)))
                if len(yrs) > 1:
                    notes.append("Combined across years %s (add a year for one)" % ", ".join(map(str, yrs)))
        fst = re.search(r"\b(first|earliest|oldest|initial|starting|opening)\s+(?:(\d+)\s+)?(?:available\s+)?(month|year|quarter|day)s?\b", q)
        if fst and not re.search(r"\bfirst\s+\d+\s+(invoices?|transactions?|records?|rows?)", q):
            fr_ = {"month": "M", "year": "Y", "quarter": "Q", "day": "D"}[fst.group(3)]
            n_ = int(fst.group(2)) if fst.group(2) else 1
            ps = d[dc].dt.strftime("%Y-%m-%d") if fr_ == "D" else d[dc].dt.to_period(fr_).astype(str)
            uq = sorted(ps.dropna().unique())
            sel_ = uq[:n_]
            d = d[ps.isin(sel_)]
            notes.append("First %d %s%s: %s" % (n_, fst.group(3), "s" if n_ > 1 else "", ", ".join(sel_)))
        rel = re.search(r"\b(latest|previous|prior)\s+(?:available\s+)?(month|year|quarter)\b", q) if not (mo or qq or yr) else None
        if rel and not re.search(r"\b(latest|previous|prior|last)\s+\d+\b", q):
            fr = {"month": "M", "year": "Y", "quarter": "Q"}[rel.group(2)]
            full = d[dc].dt.to_period(fr)
            u = sorted(full.dropna().unique())
            if u:
                sel = u[-1] if rel.group(1) == "latest" else (u[-2] if len(u) > 1 else None)
                if sel is None:
                    return d, notes, "no previous %s in data" % rel.group(2)
                d = d[full == sel]
                notes.append("%s %s: %s" % (rel.group(1).title(), rel.group(2), sel))
    if d.empty:
        return d, notes, "no rows for the requested date range"
    return d, notes, None


def _entities(q, d, cols):
    """returns (df, notes, unknown_phrase). exact full-value match first, then name tokens, else unknown 'for X'."""
    notes = []
    qq = re.sub(r"'s\b", "", q)
    applied = False
    for cname, cands in CATS:
        c = _col(cols, cands)
        if not c:
            continue
        vals = sorted({str(v) for v in d[c].dropna().unique()}, key=len, reverse=True)
        hits, rest = [], qq
        for v in vals:
            rx = r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(v.lower())
            if len(v) >= 3 and re.search(rx, rest):
                hits.append(v)
                rest = re.sub(rx, " ", rest)
        if hits:
            d = d[d[c].astype(str).isin(hits)]
            notes.append("%s: %s" % (c, ", ".join(hits))); applied = True
    pc = _col(cols, ["PartyName", "Party Name", "Customer Name"])
    if pc and not any(n.startswith(pc + ":") for n in notes):
        toks = set()
        for name in d[pc].dropna().unique():
            toks.update(w for w in re.findall(r"[a-z]+", str(name).lower()) if len(w) >= 3)
        words = [w for w in re.findall(r"[a-z]+", qq) if w in toks and w not in STOP]
        if words:
            low = d[pc].astype(str).str.lower()
            allm = low.apply(lambda s: all(w in s.split() for w in words))
            mask = allm if allm.any() else low.apply(lambda s: any(w in s.split() for w in words))
            if mask.any():
                d = d[mask]; applied = True
                names = sorted(d[pc].astype(str).unique())
                notes.append("Customers matched: " + ", ".join(names[:8]) + (" ..." if len(names) > 8 else ""))
    unknown = None
    if not applied:
        m = re.search(r"\b(?:for|of|from|to)\s+([a-z][a-z .&'-]{2,40}?)(?:\s+(?:in|during|on|from|between|by|and)\b|$|\?|\.|,)", qq)
        if m:
            entity_phrase = m.group(1)
            # Remove natural-language date expressions before checking unknown entities.
            date_matches = _dates(qq)
            if date_matches:
                entity_phrase = re.sub(
                    r"\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
                    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
                    r"eighteenth|nineteenth|twentieth|thirtieth|"
                    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
                    r"twenty(?:\s+(?:one|two|three|four|five|six|seven|eight|nine))?|"
                    r"thirty(?:\s+one)?|\d{1,4})\b",
                    " ",
                    entity_phrase,
                    flags=re.I,
                )
            words = [w for w in re.findall(r"[a-z]+", entity_phrase) if w not in STOP and w not in MN]
            if words and not re.search(r"\b(20\d\d|q[1-4])\b", m.group(1)):
                unknown = " ".join(words)
    return d, notes, unknown


def _agg_of(q):
    if re.search(r"\bmedian\b", q):
        return "median"
    if re.search(r"average|\bavg\b|\bmean\b", q):
        return "mean"
    return "sum"


def _aggregate(s, agg):
    return float(getattr(s, agg)())


def _scalar_val(d, col, agg):
    if col == "__invcount__":
        return float(d["__inv__"].nunique())
    if col == "__margin__":
        g = d["__gross__"].sum()
        return float(d["__profit__"].sum() / g * 100) if g else float("nan")
    return _aggregate(d[col], agg)


def _period_series(d, dc, per):
    if per == "D":
        return d[dc].dt.strftime("%Y-%m-%d")
    return d[dc].dt.to_period(per).astype(str)


def _group(d, keys, mets):
    """mets: list of (key,col,label). returns DataFrame indexed by group with one column per metric label."""
    g = d.groupby(keys)
    def one(col):
        if col == "__margin__":
            return (g["__profit__"].sum() / g["__gross__"].sum().where(g["__gross__"].sum() != 0)) * 100
        if col == "__invcount__":
            return g["__inv__"].nunique()
        return g[col].sum()
    out = pd.DataFrame({lab: one(col) for _k, col, lab in mets})
    return out


def _span(d, dc):
    """Human-readable period actually covered by the (already filtered) rows, e.g. 'Apr 2025 - Jun 2025'."""
    if not dc or d is None or d.empty:
        return None
    a, b = d[dc].min(), d[dc].max()
    if pd.isna(a) or pd.isna(b):
        return None
    fa, fb = a.strftime("%b %Y"), b.strftime("%b %Y")
    return fa if fa == fb else "%s - %s" % (fa, fb)


def _find_dim(q, cols):
    best = None
    for name, rx, cands in DIMS:
        m = re.search(rx, q)
        if m and (best is None or m.start() < best[0] or (m.start() == best[0] and len(m.group(0)) > best[3])):
            best = (m.start(), name, _col(cols, cands), len(m.group(0)))
    return best


def handle(question, df, skip_entity=False):
    q = str(question or "").lower().strip()
    q = q.replace("\u2019", "'")
    if not q or df is None or df.empty:
        return None
    cols = list(df.columns)

    for name, (rx, hints) in NA_WORDS.items():
        if re.search(rx, q) and not any(h in _n(c) for c in cols for h in hints):
            return _na("'%s' is not present in this dataset's columns" % name)

    dc = _col(cols, ["Date", "Bill Date", "Invoice Date"])
    d = df.copy()
    if dc:
        d[dc] = pd.to_datetime(d[dc], errors="coerce")

    metl = _metric(q)
    if not metl and re.search(r"\bbought the (?:most|least)\b|\bwho bought\b|\bbiggest buyer\b", q):
        metl = [(0, 'sales', METRICS[-1][2], 'Sales')]
    unit_words = re.search(r"\b(month|quarter|year|day)\b", q)
    dim = _find_dim(q, cols)
    pc = _col(cols, ["PartyName", "Party Name", "Customer Name"])
    ic = _col(cols, ["InvoiceNo", "Invoice No", "Invoice Number"])

    # ---------- counts / lists ----------
    if re.search(r"how many|number of|count (?:of )?(?:all )?(?:invoices|customers|products|categories)", q) and (not metl or re.search(r"transactions?", q)):
        dcount, en2, unk2 = (d, [], None) if skip_entity else _entities(q, d, cols)
        if unk2:
            return _na("'%s' not found in this dataset" % unk2.title())
        dsc, sn2, err2 = _scope(q, dcount, dc)
        if err2:
            return _na(err2)
        extra = "".join("\n- " + n_ for n_ in en2 + sn2)
        if dim and dim[2] and not re.search(r"\binvoices?\b|transactions?", q):
            v = dsc[dim[2]].nunique()
            return _out("Number of %s: {:,}".format(v) % (dim[1] + ("s" if not dim[1].endswith("s") else "")) + extra, value=int(v))
        if re.search(r"\binvoices?\b", q) and ic:
            v = dsc[ic].nunique()
            return _out("Number of invoices: {:,}".format(v) + extra, value=int(v))
        if re.search(r"transactions?", q):
            return _out("Number of sales transactions (rows): {:,}".format(len(dsc)) + extra, value=int(len(dsc)))
        return None
    ls = re.match(r"^(?:show|list)\s+(?:all|unique|distinct)\s+(customers?|products?|categories|states|parties|payment modes?)\W*$", q)
    if ls and dim and dim[2]:
        vals = sorted(d[dim[2]].dropna().astype(str).unique())
        txt = "%d unique %s: %s" % (len(vals), dim[1], ", ".join(vals))
        return _out(txt)
    if not metl and not re.search(r"\binvoices?\b|\btransactions?\b", q):
        return None

    # ---------- resolve metric columns ----------
    mets = []
    missing = []
    for _p, key, cands, label in metl:
        if key == "margin":
            pcol_, gcol_ = _col(cols, ["Profit"]), _col(cols, ["GrossAmount", "Gross Amount", "Sales Amount"])
            if pcol_ and gcol_:
                d["__profit__"] = pd.to_numeric(d[pcol_], errors="coerce")
                d["__gross__"] = pd.to_numeric(d[gcol_], errors="coerce")
                mets.append(("margin", "__margin__", label))
            else:
                missing.append(label)
            continue
        if key == "count":
            if ic:
                d["__inv__"] = d[ic]
                mets.append(("count", "__invcount__", label))
            else:
                missing.append(label)
            continue
        c = _col(cols, cands)
        if c:
            d[c] = pd.to_numeric(d[c], errors="coerce")
            mets.append((key, c, label))
        else:
            missing.append(label)
    if metl and not mets:
        return _na("no column for %s" % ", ".join(missing))
    notes = []
    if missing:
        notes.append("Not available in this dataset (not calculated): " + ", ".join(missing))

    if re.search(r"pareto|80/20|anomal|unusual|outlier", q):
        return None
    has_margin = any(m[1] == "__margin__" for m in mets)
    has_invcount = any(m[1] == "__invcount__" for m in mets)
    if (has_margin and re.search(r"compar|growth|change|invoice|trend|correlat|rolling|cumulative", q)) or \
            (has_invcount and re.search(r"compar|growth|change|trend|correlat|rolling|cumulative|percent|share|contribution", q)):
        return None

    # ---------- entity filters ----------
    if not skip_entity:
        d, en, unknown = _entities(q, d, cols)
        notes += en
        if unknown:
            return _na("'%s' not found in this dataset" % unknown.title())

    # ---------- explicit comparisons between two named periods ----------
    yrs = list(dict.fromkeys(re.findall(r"\b(20\d\d)\b", q)))
    mons = list(dict.fromkeys(re.findall(r"\b(%s)\b" % MRX, q)))
    qs = list(dict.fromkeys(re.findall(r"\bq([1-4])\b", q)))
    cue = re.search(r"\bcompar|\bchange\b|growth|difference|\bhigher\b|\blower\b|\bvs\b|versus|increase|decrease", q)
    nd = _dates(q)
    if dc and cue and mets and not nd and ((len(yrs) >= 2 and not mons and not qs) or len(mons) >= 2 or len(qs) >= 2 or (len(mons) == 1 and len(yrs) >= 2)):
        plist = []
        if len(yrs) >= 2 and not mons and not qs:
            plist = [(y, d[d[dc].dt.year == int(y)]) for y in yrs[:2]]
        elif len(mons) == 1 and len(yrs) >= 2:
            mi = MN.index(mons[0]) + 1
            plist = [("%s %s" % (mons[0].title(), y), d[(d[dc].dt.month == mi) & (d[dc].dt.year == int(y))]) for y in yrs[:2]]
        elif len(mons) >= 2:
            y = yrs[0] if yrs else None
            if not y:
                cand = sorted({yy for yy in d[dc].dt.year.dropna().astype(int)}, reverse=True)
                for yy in cand:
                    if all(((d[dc].dt.year == yy) & (d[dc].dt.month == MN.index(m_) + 1)).any() for m_ in mons[:2]):
                        y = str(yy); break
            for m_ in mons[:2]:
                sub = d[d[dc].dt.month == MN.index(m_) + 1]
                if y:
                    sub = sub[sub[dc].dt.year == int(y)]
                plist.append((m_.title() + (" " + y if y else ""), sub))
        elif len(qs) >= 2:
            y = yrs[0] if yrs else None
            if not y:
                y = str(int(d[dc].dt.year.max()))
            for qn in qs[:2]:
                plist.append(("Q%s %s" % (qn, y), d[(d[dc].dt.quarter == int(qn)) & (d[dc].dt.year == int(y))]))
        if len(plist) == 2:
            empty = [n_ for n_, s_ in plist if s_.empty]
            if empty:
                return _na("no data for %s in this dataset (data covers %s to %s)" % (", ".join(empty), d[dc].min().date(), d[dc].max().date()))
            if dim and dim[2] and mets[0][1] not in ("__margin__", "__invcount__"):
                k_, c_, l_ = mets[0]
                ga = plist[0][1].groupby(plist[0][1][dim[2]].astype(str))[c_].sum()
                gb = plist[1][1].groupby(plist[1][1][dim[2]].astype(str))[c_].sum()
                tt = pd.DataFrame({"a": ga, "b": gb}).fillna(0)
                tt["diff"] = tt["b"] - tt["a"]
                tt["pct"] = tt["diff"] / tt["a"].where(tt["a"] != 0) * 100
                tt = tt.sort_values("b", ascending=False)
                rows_ = [[i, _fmt(k_, r_["a"]), _fmt(k_, r_["b"]), ("+" if r_["diff"] >= 0 else "-") + _fmt(k_, abs(r_["diff"])), _fmt("pct", r_["pct"])] for i, r_ in tt.iterrows()]
                txt = _table("%s by %s: %s vs %s" % (l_, dim[1], plist[0][0], plist[1][0]), [dim[1].title(), plist[0][0], plist[1][0], "Abs change", "% change"], rows_)
                txt += "".join("\n- " + n_ for n_ in notes)
                return _out(txt, table=[{dim[2]: i, plist[0][0]: float(r_["a"]), plist[1][0]: float(r_["b"])} for i, r_ in tt.iterrows()])
            rows_, recs = [], []
            winner = None
            for k_, c_, l_ in mets:
                a_, b_ = float(plist[0][1][c_].sum()), float(plist[1][1][c_].sum())
                diff = b_ - a_
                pct = diff / a_ * 100 if a_ else float("nan")
                rows_.append([l_, _fmt(k_, a_), _fmt(k_, b_), ("+" if diff >= 0 else "-") + _fmt(k_, abs(diff)), _fmt("pct", pct)])
                recs.append({"metric": l_, plist[0][0]: a_, plist[1][0]: b_, "abs_change": diff, "pct_change": None if pd.isna(pct) else pct})
                if winner is None:
                    winner = plist[1][0] if b_ > a_ else plist[0][0]
            txt = _table("Comparison: %s vs %s" % (plist[0][0], plist[1][0]), ["Metric", plist[0][0], plist[1][0], "Abs change", "% change"], rows_)
            txt += "\n\n- Higher %s: %s" % (mets[0][2].lower(), winner)
            txt += "".join("\n- " + n_ for n_ in notes)
            return _out(txt, table=recs, chart_spec={"type": "bar", "x": "metric", "series": [plist[0][0], plist[1][0]], "interactive": True, "data": recs})

    # ---------- latest vs previous period change ----------
    chg = re.search(r"(change|increase\w*|decrease\w*|difference|growth|drop|rise|up|down|compar\w*)", q) and \
        re.search(r"\b(last|previous|prior)\s+(month|year|quarter)\b|\blatest\s+(month|year|quarter)\b.*\b(previous|prior|last)|\b(previous|prior|last)\b.*\blatest\b", q)
    if dc and mets and chg and not re.search(r"\b(last|latest|previous)\s+\d+\b", q):
        um = re.search(r"\b(month|year|quarter)\b", q)
        unit = um.group(1) if um else "month"
        fr = {"month": "M", "year": "Y", "quarter": "Q"}[unit]
        per_all = d[dc].dt.to_period(fr)
        u = sorted(per_all.dropna().unique())
        if len(u) >= 2:
            pa, pb = u[-2], u[-1]
            rows_, recs = [], []
            for k_, c_, l_ in mets:
                a_, b_ = float(d[per_all == pa][c_].sum()), float(d[per_all == pb][c_].sum())
                diff = b_ - a_
                pct = diff / a_ * 100 if a_ else float("nan")
                rows_.append([l_, _fmt(k_, a_), _fmt(k_, b_), ("+" if diff >= 0 else "-") + _fmt(k_, abs(diff)), _fmt("pct", pct)])
                recs.append({"metric": l_, str(pa): a_, str(pb): b_, "abs_change": diff, "pct_change": None if pd.isna(pct) else pct})
            txt = _table("Latest %s %s vs previous %s %s" % (unit, pb, unit, pa), ["Metric", str(pa), str(pb), "Abs change", "% change"], rows_)
            txt += "".join("\n- " + n_ for n_ in notes)
            return _out(txt, table=recs)

    # ---------- growth over periods ----------
    gro = re.search(r"growth|grew|month[\s-]*over[\s-]*month|year[\s-]*over[\s-]*year|quarter[\s-]*over[\s-]*quarter|percentage change in (?:monthly|yearly|quarterly|annual)|\bmom\b|\byoy\b", q)
    if dc and mets and gro:
        if re.search(r"year|yearly|annual|yoy", q) and not re.search(r"month", q):
            fr = "Y"
        elif re.search(r"quarter", q):
            fr = "Q"
        else:
            fr = "M"
        sub_full = d
        key_, col_, lab_ = mets[0]
        ser = sub_full.groupby(_period_series(sub_full, dc, fr))[col_].sum().sort_index()
        pct = ser.pct_change() * 100
        scope_y = re.search(r"\b(20\d\d)\b", q)
        if scope_y:
            keep = [i for i in ser.index if str(i).startswith(scope_y.group(1))]
            ser, pct = ser.loc[keep], pct.loc[keep]
        rows_ = [[i, _fmt(key_, ser[i]), _fmt("pct", pct[i]) if not pd.isna(pct[i]) else "-"] for i in ser.index]
        title = "%s growth by %s" % (lab_, {"M": "month", "Y": "year", "Q": "quarter"}[fr])
        pick = pct.dropna()
        lines = []
        if len(pick):
            lines.append("Highest growth: %s (%s)" % (pick.idxmax(), _fmt("pct", pick.max())))
            lines.append("Lowest growth: %s (%s)" % (pick.idxmin(), _fmt("pct", pick.min())))
        if re.search(r"which|highest|lowest|best|worst|most|least", q) and len(pick):
            want_low = re.search(r"\b(%s)\b" % DOWN, q) and not re.search(r"\b(%s)\b" % UP, q)
            i = pick.idxmin() if want_low else pick.idxmax()
            txt = "%s %s growth: %s (%s; value %s)" % ("Lowest" if want_low else "Highest", lab_, i, _fmt("pct", pick[i]), _fmt(key_, ser[i]))
            txt += "\n\n" + _table(title, [fr == "Y" and "Year" or "Period", lab_, "Growth %"], rows_)
        else:
            txt = _table(title, ["Period", lab_, "Growth %"], rows_) + "\n\n" + "\n".join("- " + l for l in lines)
        txt += "".join("\n- " + n_ for n_ in notes)
        recs = [{"period": i, lab_: float(ser[i]), "growth_pct": None if pd.isna(pct[i]) else float(pct[i])} for i in ser.index]
        return _out(txt, table=recs, chart_spec={"type": "line", "x": "period", "series": [lab_, "growth_pct"], "interactive": True, "data": recs})

    # ---------- invoice / transaction detail rows ----------
    inv = re.search(r"\binvoices?\b|\btransactions?\b", q) and not any(m[0] == "count" for m in mets) and not re.search(r"how many|count|unique|distinct|duplicate|missing|\b(average|avg|mean|median|total|sum|maximum|minimum)\b", q)
    th = _money(q)
    if inv and not (dim and dim[1] != "customer") and not re.search(r"\b(monthly|yearly|month[\s-]*wise|year[\s-]*wise|quarterly|daily)\b", q):
        sc, sn, err = _scope(q, d, dc)
        if err:
            return _na(err)
        d2 = sc
        notes += sn
        mcol = mets[0][1] if mets else _col(cols, ["InvoiceTotal", "Invoice Total"])
        mlab = mets[0][2] if mets else "Invoice Value"
        if th and mcol:
            d2 = d2[d2[mcol] > th[1]] if th[0] == ">" else d2[d2[mcol] < th[1]]
            notes.append("%s %s %s" % (mlab, th[0], "{:,.2f}".format(th[1])))
        tn = re.search(r"\b(top|bottom|first|last|latest|recent|oldest)\s+(\d+)\b", q)
        which = re.search(r"\b(%s|%s)\b" % (UP, DOWN), q)
        n = int(tn.group(2)) if tn else (1 if re.search(r"\bwhich invoice|\bwhat is the (?:highest|lowest)", q) else 20)
        if tn and tn.group(1) in ("top", "bottom") or (which and not tn and mcol):
            asc = bool(tn and tn.group(1) == "bottom") or bool(re.search(r"\b(%s)\b" % DOWN, q) and not tn)
            d2 = d2.sort_values(mcol, ascending=asc)
        elif tn and tn.group(1) in ("first", "oldest"):
            d2 = d2.sort_values(dc, ascending=True)
        elif th and mcol:
            d2 = d2.sort_values(mcol, ascending=False)
        else:
            d2 = d2.sort_values(dc, ascending=False) if dc else d2
        total_rows = len(d2)
        show = [c for c in [ic, dc, pc, _col(cols, ["Product"])] if c]
        for _k, c_, _l in mets:
            if c_ not in show:
                show.append(c_)
        for c_ in ([_col(cols, ["Qty"]), _col(cols, ["GrossAmount"]), _col(cols, ["InvoiceTotal"])] if not mets else []):
            if c_ and c_ not in show:
                show.append(c_)
        t = d2.head(n)[show].copy()
        if dc in t:
            t[dc] = pd.to_datetime(t[dc]).dt.strftime("%Y-%m-%d")
        for c_ in t.columns:
            if pd.api.types.is_float_dtype(t[c_]):
                t[c_] = t[c_].map(lambda v: "{:,.2f}".format(v) if pd.notna(v) else "-")
        txt = _table("%d matching invoices (showing %d)" % (total_rows, len(t)), list(t.columns), t.astype(str).values.tolist())
        txt += "".join("\n- " + n_ for n_ in notes)
        return _out(txt, filtered_rows=int(total_rows), table=t.to_dict("records"))

    if not mets:
        return None

    # ---------- scope (dates etc.) ----------
    d, sn, err = _scope(q, d, dc)
    if err:
        return _na(err + " (data covers %s to %s)" % (pd.to_datetime(df[dc], errors="coerce").min().date() if dc else "?", pd.to_datetime(df[dc], errors="coerce").max().date() if dc else "?"))
    notes += sn
    latest_n = re.search(r"\b(latest|last|previous|recent)\s+(\d+)\s+(month|quarter|year)s?\b", q)
    per = next((f for f, rx in [("D", r"day[\s-]*wise|daily|by day|each day|every day|per day"),
                                ("M", r"month[\s-]*wise|monthly|by month|each month|every month|per month|\bmonths\b"),
                                ("Q", r"quarter[\s-]*wise|quarterly|by quarter|each quarter|\bquarters\b"),
                                ("Y", r"year[\s-]*wise|yearly|annual|annually|by year|each year|\byears\b")] if re.search(rx, q)), None)
    rank_up = bool(re.search(r"\b(%s)\b" % UP, q))
    rank_dn = bool(re.search(r"\b(%s)\b" % DOWN, q))
    sell_rank = re.search(r"\b(best|top)[\s-]*selling\b|\b(worst|least)[\s-]*selling\b|bought the most|bought the least", q)
    if sell_rank:
        rank_up = bool(re.search(r"best|top|most", sell_rank.group(0)))
        rank_dn = not rank_up
    if sell_rank and re.search(r"bought", q) and not dim:
        dim = (0, "customer", pc, 8)
    dim_rank = bool(dim and dim[2] and (re.search(r"\b(top|bottom|best|worst|highest|lowest|most|least)\b|wise|\bby\b|\beach\b|\bper\b|\bacross\b|ranking|\brank\b", q)
                                         or re.search(r"\b(customer|product|category|state|party|payment mode)s?\s+(?:sales|revenue|profit|gst|discount|quantity)", q)))
    explicit_per = re.search(r"month[\s-]*wise|monthly|quarter[\s-]*wise|quarterly|year[\s-]*wise|yearly|annual|day[\s-]*wise|daily|\b(?:by|each|every|per)\s+(?:month|quarter|year|day)", q)
    if dim_rank and per and not explicit_per:
        per = None   # "top 3 customers ... in the last/first 3 months": months only scope the rows
    if per is None and unit_words and (rank_up or rank_dn) and not dim and not latest_n:
        if re.search(r"\b(month|quarter|year|day)\b", q):
            per = {"month": "M", "quarter": "Q", "year": "Y", "day": "D"}[unit_words.group(1)]
    if latest_n:
        fr = {"month": "M", "quarter": "Q", "year": "Y"}[latest_n.group(3)]
        n = int(latest_n.group(2))
        p = d[dc].dt.to_period(fr)
        u = sorted(p.dropna().unique())
        sel = u[-n:] if latest_n.group(1) != "previous" else u[-2 * n:-n]
        d = d[p.isin(sel)]
        if not dim_rank:
            per = per or fr
        notes.append("Periods: " + ", ".join(map(str, sel)))
    topn = re.search(r"\b(top|bottom|best|worst)\s+(\d+)\b", q)
    th = _money(q)
    avg_cond = re.search(r"\b(above|below)\s+(?:the\s+)?average\b", q)
    avg_pairs = [(m_.group(1), m_.group(2)) for m_ in re.finditer(r"\b(sales?|revenue|profit|gst|discount|quantity|qty|margin)\b(?:(?!\b(?:sales?|revenue|profit|gst|discount|quantity|qty|margin)\b)[^,.])*?\b(above|below)\s+(?:the\s+)?average", q)]
    corr = re.search(r"correlat|relationship between|\brelation\b", q)
    summ = re.search(r"\b(sales|profit|business|performance|overall)\s+summary\b|\bsummary of (sales|profit|business)\b", q)
    roll = re.search(r"rolling\s+(\d+)[\s-]*(month|quarter|year)|cumulative|running total", q)
    share = re.search(r"percent(?:age)? of|contribution|\bshare\b|comes from|proportion", q)


    # ---------- summary ----------
    if summ:
        def cs(*c):
            return _col(cols, list(c))
        sc_, pc_, qc_, gc_, dcnt = cs("GrossAmount"), cs("Profit"), cs("Qty"), cs("TotalGST"), cs("DiscountAmt")
        rws = []
        if sc_: rws.append(["Total sales", _fmt("s", pd.to_numeric(d[sc_], errors="coerce").sum())])
        if pc_: rws.append(["Total profit", _fmt("s", pd.to_numeric(d[pc_], errors="coerce").sum())])
        if sc_ and pc_ and pd.to_numeric(d[sc_], errors="coerce").sum():
            rws.append(["Profit margin", _fmt("margin", pd.to_numeric(d[pc_], errors="coerce").sum() / pd.to_numeric(d[sc_], errors="coerce").sum() * 100)])
        if qc_: rws.append(["Total quantity", _fmt("qty", pd.to_numeric(d[qc_], errors="coerce").sum())])
        if gc_: rws.append(["Total GST", _fmt("s", pd.to_numeric(d[gc_], errors="coerce").sum())])
        if dcnt: rws.append(["Total discount", _fmt("s", pd.to_numeric(d[dcnt], errors="coerce").sum())])
        if ic: rws.append(["Invoices", "{:,}".format(d[ic].nunique())])
        if pc: rws.append(["Customers", "{:,}".format(d[pc].nunique())])
        if sc_:
            for nm_, cands_ in (("Top customer", ["PartyName"]), ("Top product", ["Product"]), ("Top category", ["Category"]), ("Top state", ["PartyState"])):
                c0 = _col(cols, cands_)
                if c0:
                    g0 = pd.to_numeric(d[sc_], errors="coerce").groupby(d[c0].astype(str)).sum()
                    rws.append([nm_, "%s (%s)" % (g0.idxmax(), _fmt("s", g0.max()))])
            if dc:
                gm = pd.to_numeric(d[sc_], errors="coerce").groupby(d[dc].dt.to_period("M").astype(str)).sum()
                rws.append(["Best month", "%s (%s)" % (gm.idxmax(), _fmt("s", gm.max()))])
                rws.append(["Weakest month", "%s (%s)" % (gm.idxmin(), _fmt("s", gm.min()))])
                rws.append(["Data covers", "%s to %s" % (d[dc].min().date(), d[dc].max().date())])
        txt = _table("Summary (%d rows)" % len(d), ["Metric", "Value"], rws) + "".join("\n- " + n_ for n_ in notes)
        return _out(txt, filtered_rows=int(len(d)))

    # ---------- correlation ----------
    if corr and len(mets) >= 2 and all(m[1] not in ("__margin__", "__invcount__") for m in mets[:2]):
        a_, b_ = mets[0], mets[1]
        r_ = d[a_[1]].corr(d[b_[1]])
        strength = "very strong" if abs(r_) >= 0.9 else "strong" if abs(r_) >= 0.7 else "moderate" if abs(r_) >= 0.4 else "weak" if abs(r_) >= 0.2 else "negligible"
        txt = "Correlation between %s and %s (row level, %d rows): %.4f (%s %s relationship)" % (a_[2], b_[2], len(d), r_, strength, "positive" if r_ >= 0 else "negative")
        return _out(txt, value=float(r_))

    # ---------- rolling / cumulative ----------
    if roll and dc and mets and mets[0][1] not in ("__margin__", "__invcount__"):
        mfr = {"month": "M", "quarter": "Q", "year": "Y"}.get(roll.group(2) if roll.group(1) else "month", "M")
        ser = d.groupby(_period_series(d, dc, mfr))[mets[0][1]].sum().sort_index()
        k_, l_ = mets[0][0], mets[0][2]
        if roll.group(1):
            n_ = int(roll.group(1))
            rv = ser.rolling(n_).sum()
            rows_ = [[i, _fmt(k_, ser[i]), _fmt(k_, rv[i]) if not pd.isna(rv[i]) else "-"] for i in ser.index]
            txt = _table("Rolling %d-%s %s" % (n_, roll.group(2), l_.lower()), ["Period", l_, "Rolling %d" % n_], rows_)
        else:
            cv = ser.cumsum()
            rows_ = [[i, _fmt(k_, ser[i]), _fmt(k_, cv[i])] for i in ser.index]
            txt = _table("Cumulative %s" % l_.lower(), ["Period", l_, "Cumulative"], rows_)
        return _out(txt + "".join("\n- " + n_ for n_ in notes))

    # ---------- above / below average (per dimension) ----------
    if avg_pairs and dim and dim[2]:
        specs = []
        for w_, dirn in avg_pairs:
            m0 = _metric(w_)
            if m0:
                c0 = _col(cols, m0[0][2])
                if c0:
                    d[c0] = pd.to_numeric(d[c0], errors="coerce")
                    specs.append((m0[0][1], c0, m0[0][3], dirn))
        if specs:
            keys = [(k_, c_, l_) for k_, c_, l_, _d in specs]
            tab = _group(d, d[dim[2]].astype(str), keys)
            conds = []
            avgs = {l_: tab[l_].mean() for _k, _c, l_, _d in specs}  # averages over ALL groups, before any filtering
            for k_, c_, l_, dirn in specs:
                av = avgs[l_]
                tab = tab[tab[l_] > av] if dirn == "above" else tab[tab[l_] < av]
                conds.append("%s %s average (%s)" % (l_, dirn, _fmt(k_, av)))
            tab = tab.sort_values(specs[0][2], ascending=False)
            rows_ = [[i + 1, n_] + [_fmt(k_, tab.loc[n_, l_]) for k_, _c, l_ in keys] for i, n_ in enumerate(tab.index)]
            txt = _table("%d %s with %s" % (len(tab), dim[1], " and ".join(conds)), ["#", dim[1].title()] + [l_ for _k, _c, l_ in keys], rows_)
            return _out(txt + "".join("\n- " + n_ for n_ in notes), table=[{dim[2]: n_} for n_ in tab.index])
    if avg_pairs:
        return None

    # ---------- share / contribution ----------
    if share and mets[0][1] not in ("__margin__", "__invcount__") and ((dim and dim[2]) or per):
        if per and dc and not (dim and dim[2]):
            keyser, nm_ = _period_series(d, dc, per), "Period"
        else:
            keyser, nm_ = d[dim[2]].astype(str), dim[1].title()
        ser = d.groupby(keyser)[mets[0][1]].sum()
        tot = ser.sum()
        ser = ser.sort_values(ascending=False) if nm_ != "Period" else ser.sort_index()
        rows_ = [[i, _fmt(mets[0][0], v), _fmt("share", v / tot * 100 if tot else float("nan"))] for i, v in ser.items()]
        txt = _table("%s share by %s" % (mets[0][2], nm_.lower()), [nm_, mets[0][2], "Share %"], rows_)
        txt += "\n\n- Total %s: %s" % (mets[0][2].lower(), _fmt(mets[0][0], tot))
        return _out(txt + "".join("\n- " + n_ for n_ in notes))

    # highest and lowest side by side
    if re.search(r"\bcompar\w*\b.*\b(highest|best)\b.*\b(and|vs|versus)\b.*\b(lowest|worst)\b", q) and (dim or per or unit_words):
        if dim and dim[2]:
            s = d.groupby(d[dim[2]].astype(str))[mets[0][1]].sum()
            lab = dim[1].title()
        else:
            fr = per or {"month": "M", "quarter": "Q", "year": "Y", "day": "D"}.get(unit_words.group(1) if unit_words else "month", "M")
            s = d.groupby(_period_series(d, dc, fr))[mets[0][1]].sum(); lab = "Period"
        hi, lo = s.idxmax(), s.idxmin()
        txt = _table("Highest vs lowest %s by %s" % (lab.lower(), mets[0][2]), ["", lab, mets[0][2]],
                     [["Highest", hi, _fmt(mets[0][0], s[hi])], ["Lowest", lo, _fmt(mets[0][0], s[lo])]])
        txt += "\n\n- Difference: " + _fmt(mets[0][0], s[hi] - s[lo])
        return _out(txt)

    # ---------- grouped tables (dimension or period) ----------
    wise = re.search(r"wise|\bby\b|\beach\b|\bevery\b|\bper\b|\bacross\b|ranking|\brank\b|\bcompar", q) or \
        (dim and not any(n_.split(":")[0] in ("PartyName", "Category", "Product", "PartyState", "PaymentMode", "PartyType", "Customers matched") for n_ in notes)
         and re.search(r"\b(customer|product|category|state|party|payment mode|party type)s?\s+(?:sales|revenue|profit|gst|discount|quantity|qty)\b", q))
    if per and dc:
        keys = _period_series(d, dc, per)
        tab = _group(d, keys, mets)
        if th:
            tab = tab[tab[mets[0][2]] > th[1]] if th[0] == ">" else tab[tab[mets[0][2]] < th[1]]
            notes.append("%s %s %s" % (mets[0][2], th[0], "{:,.2f}".format(th[1])))
        label = {"D": "day", "M": "month", "Q": "quarter", "Y": "year"}[per]
        if th:
            tab = tab.sort_index()
            title = "%d %ss with %s %s %s" % (len(tab), label, mets[0][2], "above" if th[0] == ">" else "below", "{:,.2f}".format(th[1]))
        elif topn or rank_up or rank_dn:
            asc = bool(topn and topn.group(1) in ("bottom", "worst")) or (rank_dn and not rank_up and not topn)
            asc = asc or bool(re.search(r"\b(worst|lowest|least|minimum|lower)\b", q) and not topn)
            n = int(topn.group(2)) if topn else 1
            tab = tab.sort_values(mets[0][2], ascending=asc).head(n)
            title = "%s %d %s by %s" % ("Bottom" if asc else "Top", len(tab), label if len(tab) == 1 else label + "s", mets[0][2])
        else:
            tab = tab.sort_index()
            title = "%s by %s" % (" & ".join(m[2] for m in mets), label)
        rows_ = [[i] + [_fmt(k_, tab.loc[i, l_]) for k_, _c, l_ in mets] for i in tab.index]
        txt = _table(title, ["Period"] + [m[2] for m in mets], rows_) + "".join("\n- " + n_ for n_ in notes)
        recs = [dict({"period": i}, **{l_: float(tab.loc[i, l_]) for _k, _c, l_ in mets}) for i in tab.index]
        res = _out(txt, table=recs, filtered_rows=int(len(d)))
        if re.search(r"chart|plot|visuali|graph|trend", q) or len(tab) > 3:
            res["result"]["chart_spec"] = {"type": "line", "x": "period", "series": [m[2] for m in mets], "interactive": True, "data": recs}
        return res

    if dim and dim[2] and (wise or topn or rank_up or rank_dn or th):
        tab = _group(d, d[dim[2]].astype(str), mets)
        first = mets[0][2]
        if th:
            tab = tab[tab[first] > th[1]] if th[0] == ">" else tab[tab[first] < th[1]]
            notes.append("%s %s %s" % (first, th[0], "{:,.2f}".format(th[1])))
            title = "%d %s with %s %s %s" % (len(tab), dim[1], first, "above" if th[0] == ">" else "below", "{:,.2f}".format(th[1]))
            tab = tab.sort_values(first, ascending=th[0] == "<")
        elif topn or rank_up or rank_dn:
            asc = bool(topn and topn.group(1) in ("bottom", "worst")) or (rank_dn and not rank_up and not topn)
            if topn:
                n = int(topn.group(2))
            elif re.match(r"^(which|who|what)\b", q) or sell_rank or re.search(r"\bmy\b|\bhas the\b|\bis the\b", q):
                n = 1
            else:
                n = 5
            tab = tab.sort_values(first, ascending=asc).head(n)
            title = "%s %d %s by %s" % ("Bottom" if asc else "Top", len(tab), dim[1], first)
        else:
            tab = tab.sort_values(first, ascending=False)
            title = "%s by %s (%d)" % (" & ".join(m[2] for m in mets), dim[1], len(tab))
        shown = tab if len(tab) <= 200 else tab.head(200)
        span = _span(d, dc)
        rows_ = [[k + 1, i] + [_fmt(k_, shown.loc[i, l_]) for k_, _c, l_ in mets] for k, i in enumerate(shown.index)]
        txt = _table(title, ["#", dim[1].title()] + [m[2] for m in mets], rows_) + "".join("\n- " + n_ for n_ in notes)
        if span:
            txt += "\n- Period covered: " + span
        recs = [dict({dim[2]: i}, **{l_: float(shown.loc[i, l_]) for _k, _c, l_ in mets}, **({"Period": span} if span else {})) for i in shown.index]
        return _out(txt, table=recs, filtered_rows=int(len(d)), period_label=span, scope_notes=list(notes))

    # ---------- scalar (only when scope/entity/multi-metric/median/synonym asks for it) ----------
    agg = _agg_of(q)
    syn = re.search(r"\bturnover\b|\bsell\b|\bsold\b|\bselling\b", q) and not re.search(r"quantity|qty|units", q)
    maxmin = re.search(r"\b(maximum|highest|largest|biggest|max)\b", q), re.search(r"\b(minimum|lowest|smallest|min)\b", q)
    if maxmin[0] and not maxmin[1]:
        agg = "max"
    elif maxmin[1] and not maxmin[0]:
        agg = "min"
    if notes or len(mets) >= 2 or agg == "median" or syn or mets[0][0] in ("invoice_total", "margin", "count"):
        word = {"sum": "Total", "mean": "Average", "median": "Median", "max": "Maximum", "min": "Minimum"}[agg]
        if len(mets) == 1:
            k_, c_, l_ = mets[0]
            v = _scalar_val(d, c_, agg)
            txt = "%s %s: %s  (%d rows)" % (word, l_.lower(), _fmt(k_, v), len(d)) + "".join("\n- " + n_ for n_ in notes)
            return _out(txt, value=v, filtered_rows=int(len(d)))
        rows_ = [[l_, _fmt(k_, _scalar_val(d, c_, agg))] for k_, c_, l_ in mets]
        txt = _table("%s (%d rows)" % (word, len(d)), ["Metric", "Value"], rows_) + "".join("\n- " + n_ for n_ in notes)
        return _out(txt, filtered_rows=int(len(d)))
    return None


_ALT_CACHE = {}


def _all_dataset_ids(current_id=None):
    import graph.dynamic_nodes as dn
    for name in dir(dn):
        low = name.lower()
        if "dataset" in low and any(k in low for k in ("list", "all", "fetch")) and callable(getattr(dn, name)):
            try:
                res = getattr(dn, name)()
            except Exception:
                continue
            if isinstance(res, (list, tuple)):
                ids = [int(r["id"]) for r in res if isinstance(r, dict) and r.get("id") is not None]
                if ids:
                    return ids
    if current_id is not None:
        return list(range(max(1, int(current_id) - 15), int(current_id) + 16))
    return []


def _frame(did):
    from graph.dynamic_nodes import load_dataset_rows
    rows = load_dataset_rows(int(did))
    rows = [(r.get("row_data") or r.get("data") or r) if isinstance(r, dict) else r for r in rows]
    return pd.DataFrame(rows)


def _alt_frame(q, current_id):
    met = _metric(q)
    if not met:
        return None
    key = (tuple(m[1] for m in met), current_id)
    if key in _ALT_CACHE:
        return _ALT_CACHE[key]
    best, best_score = None, -1
    for did in _all_dataset_ids(current_id):
        if did == current_id:
            continue
        try:
            f = _frame(did)
        except Exception:
            continue
        if f is None or f.empty:
            continue
        score = sum(1 for m in met if _col(list(f.columns), m[2]))
        if score == len(met) and (best is None or score > best_score or (score == best_score and len(f) > len(best))):
            best, best_score = f, score
    _ALT_CACHE[key] = best
    return best


def _defer_to_engine(question):
    """Invoice-count questions that also ask for another metric are left to the older dynamic query engine
    (this was added in the user's own version of the module and is kept as-is)."""
    has_invoice_count = bool(re.search(
        r"\b(?:invoice\s+count|number\s+of\s+invoices|count\s+of\s+invoices)\b", question or "", re.IGNORECASE))
    has_other_metric = bool(re.search(
        r"\b(?:sales|revenue|profit|discount|gst|quantity|qty)\b", question or "", re.IGNORECASE))
    needs_engine = bool(re.search(r"compar|growth|change|trend|rolling|cumulative|correlat|percent|share|contribution", question or "", re.IGNORECASE))
    return has_invoice_count and has_other_metric and needs_engine


def run(state):
    q = state.get("original_question") or state.get("question") or ""
    if _defer_to_engine(q):
        return None
    ds = state.get("dataset") or {}
    did = state.get("dataset_id") or ds.get("id")
    rows = state.get("rows") or []
    if not rows and did is not None:
        from graph.dynamic_nodes import load_dataset_rows
        rows = load_dataset_rows(int(did))
    rows = [(r.get("row_data") or r.get("data") or r) if isinstance(r, dict) else r for r in rows]
    frame = pd.DataFrame(rows)
    qlow = str(q).lower()
    met = _metric(qlow)
    if met and not frame.empty and any(not _col(list(frame.columns), m[2]) for m in met):
        alt = _alt_frame(qlow, int(did) if did is not None else None)
        if alt is not None:
            return handle(q, alt)
    return handle(q, frame)


def wrap_planner(fn):
    def inner(state):
        try:
            out = run(state)
        except Exception as exc:
            print("[EXTRA PLANNER-SKIP ERROR]", type(exc).__name__, exc)
            out = None
        if out is None:
            return fn(state)
        plan = {"status": "OK", "operation": "engine", "filters": [],
                "reason": "Deterministic analytics_extra (LLM skipped)"}
        return {**state, "query_plan": plan, "result": out["result"], "error": None}
    return inner


def wrap_extra(fn):
    def inner(state):
        r = state.get("result")
        if isinstance(r, dict) and r.get("engine_answer"):
            return state
        try:
            out = run(state)
        except Exception as exc:
            print("[EXTRA ERROR]", type(exc).__name__, exc)
            out = None
        if out is None:
            return fn(state)
        return {**state, "result": out["result"], "error": None}
    return inner