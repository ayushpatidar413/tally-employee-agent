"""Deterministic "remaining days / due date / overdue / expiry" answers.

LLM ko aaj ki date nahi pata hoti aur wo date-math me galti karta hai, isliye ye poora hisaab
Python me hota hai. "As of" date = server clock (IST).

Do tarah ke sawal:
  1. Calendar:  "is month ke kitne din bache", "financial year me remaining days"
  2. Data:      "overdue invoices", "ABC Traders ki due date me kitne din bache", "next 7 days me due"
                -> due/expiry date column, ya invoice date + credit days se.
Agar file me due/expiry/credit-days nahi hai to "not available" batata hai (guess nahi karta).
"""
import calendar
import json
import re
import warnings
from datetime import date, datetime

import pandas as pd

try:
    from zoneinfo import ZoneInfo
    _IST = ZoneInfo("Asia/Kolkata")
except Exception:            # Windows par: pip install tzdata
    _IST = None

_STRONG = re.compile(
    r"\b(overdue|past\s+due|payment\s+due|due\s+(?:in|date|on|within)|expir\w*|deadline|"
    r"days?\s+(?:left|remaining)|din\s+(?:bache|bacha|bachi|baaki|baki))\b", re.I)
_WEAK = re.compile(r"\b(remaining|remain|bache|bacha|bachi|baaki|baki)\b", re.I)
_DAYS = re.compile(r"\b(days?|din|dino|dinon)\b", re.I)
_DATA_WORDS = re.compile(r"\b(invoice|invoices|bill|party|customer|payment|order|due|overdue|expir\w*|credit)\b", re.I)

_DUE_KEYS = ("duedate", "dueon", "paymentdue", "expir", "validtill", "validupto",
             "validity", "deadline", "maturity", "enddate")
_CREDIT_KEYS = ("creditdays", "creditperiod", "paymentterms", "paymentdays", "termsdays")
_DATE_EXACT = ("invoicedate", "billdate", "date", "transactiondate", "invoicedt")


def today_ist():
    return datetime.now(_IST).date() if _IST else date.today()


def _norm_col(c):
    return re.sub(r"[^a-z0-9]", "", str(c).lower())


def _is_due_name(n):
    return n == "due" or any(k in n for k in _DUE_KEYS)


def is_remaining_days_query(q):
    q = str(q or "")
    if _STRONG.search(q):
        return True
    return bool(_WEAK.search(q) and _DAYS.search(q))


def columns_have_due_info(columns):
    """_route() ke liye: dataset ke column names me due/credit info hai?"""
    if isinstance(columns, str):
        try:
            columns = json.loads(columns)
        except Exception:
            columns = [c.strip() for c in columns.split(",")]
    names = []
    for c in columns or []:
        names.append(str(c.get("name") or c.get("column") or "") if isinstance(c, dict) else str(c))
    norm = [_norm_col(n) for n in names]
    has_due = any(_is_due_name(n) for n in norm)
    has_credit = any(any(k in n for k in _CREDIT_KEYS) for n in norm) and any(n in _DATE_EXACT for n in norm)
    return has_due or has_credit


def _parse(s):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = pd.to_datetime(s, errors="coerce")
        b = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return b if b.notna().sum() > a.notna().sum() else a


def _find_due_series(df):
    for c in df.columns:
        if _is_due_name(_norm_col(c)):
            s = _parse(df[c])
            if len(s) and s.notna().mean() >= 0.6:
                return f"{c} column", s
    credit = next((c for c in df.columns if any(k in _norm_col(c) for k in _CREDIT_KEYS)), None)
    inv = next((c for c in df.columns if _norm_col(c) in _DATE_EXACT), None)
    if credit and inv:
        s = _parse(df[inv]) + pd.to_timedelta(pd.to_numeric(df[credit], errors="coerce"), unit="D")
        if len(s) and s.notna().mean() >= 0.6:
            return f"{inv} + {credit} (credit days)", s
    return None


def _calendar_part(q, today):
    ql = q.lower()
    if re.search(r"\b(financial\s+year|fiscal|fy)\b", ql):
        end = date(today.year + 1, 3, 31) if today.month >= 4 else date(today.year, 3, 31)
        label = "financial year"
    elif re.search(r"\b(quarter|quarterly)\b", ql):
        m = ((today.month - 1) // 3 + 1) * 3
        end = date(today.year, m, calendar.monthrange(today.year, m)[1])
        label = "calendar quarter"
    elif re.search(r"\b(month|mahine|mahina)\b", ql):
        end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        label = "current month"
    elif re.search(r"\b(year|saal|sal|varsh)\b", ql):
        end = date(today.year, 12, 31)
        label = "calendar year"
    else:
        return None
    return label, end, (end - today).days


def _dd(n):
    n = abs(int(n))
    return f"{n} day{'s' if n != 1 else ''}"


def _py(v):
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return str(v)[:10]
    return v


def _entity_filter(df, q):
    ql = " " + re.sub(r"[^\w]+", " ", q.lower()) + " "
    best = None
    for c in df.columns:
        s = df[c]
        if c == "_due" or pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            continue
        vals = s.dropna().astype(str).str.strip().unique()
        if len(vals) > 2000:
            continue
        for v in vals:
            nv = re.sub(r"[^\w]+", " ", v.lower()).strip()
            if len(nv) >= 4 and f" {nv} " in ql and (best is None or len(nv) > best[2]):
                best = (c, v, len(nv))
    return best


def _pick(work, *keys):
    for c in work.columns:
        if c in ("_due", "_days"):
            continue
        n = _norm_col(c)
        if any(k in n for k in keys):
            return c
    return None


def remaining_days_answer(df, question, today=None):
    """-> dict(answer, rows, scope_notes, period_label) ya None (sawal is type ka nahi)."""
    q = str(question or "")
    if not is_remaining_days_query(q):
        return None
    today = today or today_ist()
    today_txt = f"{today:%d %b %Y}"
    found = _find_due_series(df)
    cal = _calendar_part(q, today)

    if cal and (found is None or not _DATA_WORDS.search(q)):
        label, end, left = cal
        return {
            "answer": (f"Today is {today_txt} (IST). The {label} ends on {end:%d %b %Y}, so "
                       f"{_dd(left)} remain (excluding today)."),
            "rows": [{"As of": str(today), "Period": label, "Ends on": str(end), "Days Remaining": left}],
            "scope_notes": ["Calendar calculation using the server date (IST); no uploaded data used."],
            "period_label": f"{today_txt} - {end:%d %b %Y}",
        }

    if found is None:
        cols = ", ".join(map(str, list(df.columns)[:30]))
        return {
            "answer": ("Information is not available in the uploaded file. Remaining days needs a due-date / "
                       "expiry-date column (or invoice date + credit days), and this dataset has none. "
                       f"Available columns: {cols}"),
            "rows": [],
            "scope_notes": ["No due/expiry/credit-days column found."],
            "period_label": None,
        }

    label, due = found
    work = df.loc[due.notna()].copy()
    work["_due"] = due.loc[work.index]
    scope = [f"Due date source: {label}", f"As of {today_txt} (server clock, IST)",
             "All rows with a due date are counted; paid/settled status is not considered."]

    ent = _entity_filter(work, q)
    if ent:
        work = work[work[ent[0]].astype(str).str.strip() == ent[1]]
        scope.append(f"{ent[0]} = {ent[1]}")
    if work.empty:
        return {"answer": "Information is not available in the uploaded file (no matching rows with a due date).",
                "rows": [], "scope_notes": scope, "period_label": None}

    work["_days"] = (work["_due"].dt.normalize() - pd.Timestamp(today)).dt.days.astype(int)

    m = re.search(r"(?:within|next|agle|aage)\s+(\d{1,3})\s*(?:days?|din)", q, re.I)
    if re.search(r"\b(overdue|past\s+due)\b", q, re.I):
        work = work[work["_days"] < 0]
        scope.append("Only overdue rows")
    elif m:
        n = int(m.group(1))
        work = work[(work["_days"] >= 0) & (work["_days"] <= n)]
        scope.append(f"Due within the next {n} days")
    if work.empty:
        return {"answer": "No rows match that due-date condition.", "rows": [],
                "scope_notes": scope, "period_label": today_txt}

    id_cols = []
    for c in (_pick(work, "invoiceno", "invoicenumber", "billno"),
              _pick(work, "partyname", "customer"),
              _pick(work, "product", "item")):
        if c and c not in id_cols:
            id_cols.append(c)

    rows = []
    for _, r in work.sort_values("_days").head(50).iterrows():
        d = int(r["_days"])
        rec = {c: _py(r[c]) for c in id_cols}
        rec["Due Date"] = r["_due"].strftime("%Y-%m-%d")
        rec["Days Remaining"] = d
        rec["Status"] = "Overdue" if d < 0 else ("Due today" if d == 0 else "Upcoming")
        rows.append(rec)

    n = len(work)
    over = int((work["_days"] < 0).sum())
    zero = int((work["_days"] == 0).sum())
    up = n - over - zero
    if n == 1:
        d = int(work["_days"].iloc[0])
        dd = work["_due"].iloc[0]
        name = str(_py(work[id_cols[0]].iloc[0])) if id_cols else "The item"
        if d < 0:
            ans = f"{name} was due on {dd:%d %b %Y} and is overdue by {_dd(d)} (as of {today_txt})."
        elif d == 0:
            ans = f"{name} is due today ({dd:%d %b %Y})."
        else:
            ans = f"{name} is due on {dd:%d %b %Y}: {_dd(d)} remaining (as of {today_txt})."
    else:
        ans = f"{n} rows with a due date (as of {today_txt}): {over} overdue, {zero} due today, {up} upcoming."
        nxt = work[work["_days"] >= 0].sort_values("_days").head(1)
        if len(nxt):
            ans += f" Nearest upcoming due date: {nxt['_due'].iloc[0]:%d %b %Y} ({_dd(nxt['_days'].iloc[0])} remaining)."
        if over:
            ans += f" Most overdue: {_dd(work['_days'].min())} past due."
        if n > 50:
            ans += " Showing the 50 most urgent rows."
    return {"answer": ans, "rows": rows, "scope_notes": scope, "period_label": today_txt}
