"""
followup_resolver.py  -  follow-up / short-reply / change-comparison helpers
for services/semantic_query_service.py

Fixes three problems seen in the Vyapar AI chat:
  1. "yes" / "give" / "haan" after a clarification question lost the original
     request   -> resolve_short_reply()
  2. "Which products increased in August 2026?" asked a needless clarification
     and the old decline-logic ignored the named month
                -> product_change_result()   (pure pandas, no LLM)
  3. LLM wrote wrong amounts ("Rs 2.8 Lakh" for Rs 2,797.75) and used Share %
     as if it were growth
                -> multi_period_compare_answer() + guard_answer()
"""
from __future__ import annotations

import contextvars
import difflib
import re
from datetime import datetime

import pandas as pd

# ----------------------------------------------------------------- helpers
USER_TEXT = contextvars.ContextVar("user_text", default="")   # original user message (for reply language)

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH_RE = (r"(january|february|march|april|may|june|july|august|september|october|"
             r"november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)")


def inr(v):
    """Indian grouping, always full number (never Lakh / Crore words)."""
    s = f"{abs(float(v)):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = head + "," + tail
    return f"{'-' if v < 0 else ''}\u20b9{whole}.{frac}"


def _indian_int(n):
    s = f"{abs(int(round(n)))}"
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    return ("-" if n < 0 else "") + s


def fmt_metric(name, v):
    """Money gets the rupee sign; quantities / counts do not; '%' metrics get a % sign."""
    n = str(name or "").lower()
    v = float(v)
    _is_invoice_count = bool(re.search(r"\b(?:invoices|bills|transactions)\b", n)) or (
        bool(re.search(r"\binvoice\b", n)) and not re.search(r"value|total|amount|gst|ticket|avg|average", n))
    if _is_invoice_count or any(k in n for k in ("qty", "quantity", "units", "count", "nunique", "number of", "orders", "pieces")):
        return _indian_int(v) if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"
    if "%" in n or "margin" in n or "percent" in n:
        return f"{v:.2f}%"
    return inr(v)


def _alnum(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _find_col(df, names):
    wanted = {re.sub(r"[^a-z0-9]", "", n.lower()) for n in names}
    for c in df.columns:
        if re.sub(r"[^a-z0-9]", "", str(c).lower()) in wanted:
            return c
    return None


# ------------------------------------------------- 1. short reply resolver
AFFIRM = {
    "yes", "yess", "yes please", "ys", "yep", "yup", "yeah", "y", "ok", "okk", "okay", "k", "sure",
    "please", "pls", "plz", "go ahead", "do it", "correct", "right", "exactly", "that one",
    "give", "giv", "give me", "show", "show me", "tell me", "please give", "please show",
    "haan", "han", "ha", "haa", "hanji", "haan ji", "ji", "ji haan", "bilkul", "sahi", "theek hai",
    "thik hai", "thik", "batao", "bata do", "bta do", "btao", "dikhao", "dikha do", "dikhado",
    "kar do", "kr do", "krdo", "kardo", "de do", "do", "chalo", "haan batao", "haan dikhao",
}
NEGATE = {"no", "nope", "nahi", "nahin", "na", "no thanks", "nahi chahiye", "cancel", "leave it"}
_ACKS = ("got it", "okay", "ok", "sure", "noted", "understood", "alright", "theek hai", "samajh gaya")
_ASK_START = re.compile(
    r"^\s*(do you|would you|should i|shall i|did you|are you looking|is it|could you|can you|"
    r"please (?:specify|clarify|tell)|kya aap|kya main|kya tum|aap kya|batayein|please confirm)", re.I)


def _is_short_reply(q):
    n = _alnum(q)
    if not n:
        return False
    if n in AFFIRM or n in NEGATE:
        return True
    if len(n.split()) <= 3:  # typo tolerance: "yess", "hann", "bataoo"
        return bool(difflib.get_close_matches(n, list(AFFIRM | NEGATE), n=1, cutoff=0.82))
    return False


def _is_negative(q):
    n = _alnum(q)
    return n in NEGATE or bool(difflib.get_close_matches(n, list(NEGATE), n=1, cutoff=0.9))


def _turns(history):
    out = []
    for m in (history or [])[-14:]:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role", "")).lower()
        text = str(m.get("message") or m.get("content") or "").strip()
        if role in ("user", "assistant") and text:
            out.append((role, text))
    return out


def _looks_like_question_or_offer(text):
    t = text.strip()
    return t.endswith("?") or bool(_ASK_START.match(t)) or "specify" in t.lower()


def _is_ack(text):
    return _alnum(text) in {_alnum(a) for a in _ACKS} or _alnum(text).rstrip(" !") in {_alnum(a) for a in _ACKS}


def resolve_short_reply(question, history):
    """
    Returns a standalone question when `question` is a bare confirmation
    (yes / haan / give / dikhao ...) of an earlier clarification, else None.
    Works even when the assistant wrote 'Got it!' in between.
    """
    if not _is_short_reply(question) or _is_negative(question):
        return None
    turns = _turns(history)
    cur = _alnum(question)
    # drop the current message if the API already put it into history
    if turns and turns[-1][0] == "user" and _alnum(turns[-1][1]) == cur:
        turns = turns[:-1]

    # last substantive user request = last user turn that is not itself a short reply
    idx = None
    for i in range(len(turns) - 1, -1, -1):
        role, text = turns[i]
        if role == "user" and not _is_short_reply(text):
            idx = i
            break
    if idx is None:
        return None
    request = turns[idx][1]

    # the assistant clarification / offer that followed that request (skip 'Got it!' acks)
    offer = ""
    for role, text in turns[idx + 1:]:
        if role == "assistant" and not _is_ack(text) and _looks_like_question_or_offer(text):
            offer = text
    if not offer:
        # user said "give"/"show" and there was no explicit question: just redo the request
        return request
    return (f"{request}\n"
            f"The assistant asked: \"{offer[:400]}\"\n"
            f"The user answered YES. Treat that interpretation as confirmed, answer the original "
            f"request now, and do NOT ask any further clarification.")


# ------------------------------- 2. deterministic product increase / decrease
_INC = re.compile(r"\b(increas\w*|grew|grow\w*|gain\w*|rise\w*|rose|risen|improv\w*|went up|go(?:ing)? up|"
                  r"(?:went|go|goes|going|gone|are|is|come|came)\s+up|higher|greater|badh\w*|bad[ha]\w*|zyada hu\w*|jyada hu\w*|vri?ddhi|vruddhi|barh\w*|izaf\w*|ijaf\w*|tarakk?i)\b", re.I)
_DEC = re.compile(r"\b(decreas\w*|declin\w*|drop\w*|fall\w*|fell|(?:went|go|goes|going|gone|are|is|come|came)\s+down|lower|reduc\w*|ghat\w*|kam hu\w*|kam ho\w*|kami|gir\w*)\b", re.I)
_PROD = re.compile(r"\b(products?|prodct\w*|prduct\w*|items?|itm\w*|maal)\b", re.I)
_WHICH = re.compile(r"\b(which|what|any|all|every|kaun|kaunse|konse|kon se|kis|list|show|batao|dikhao)\b", re.I)


def _months_in(text):
    """[(year|None, month)] in order of appearance."""
    out = []
    for m in re.finditer(_MONTH_RE + r"(?:\s*,?\s*(20\d{2}))?\b", str(text or ""), re.I):
        mon = MONTHS[m.group(1).lower()]
        yr = int(m.group(2)) if m.group(2) else None
        # "may" is also an English verb: only accept bare 'may' next to a year or sales words
        if m.group(1).lower() == "may" and yr is None and not re.search(
                r"\b(in|of|for|during|vs|versus|with|and|to|from|compare|comparing|between)\s+may\b"
                r"|\bmay\s+(sales|ka|ki|me|mein)\b"
                r"|\bmay\s+(?:and|vs\.?|versus|to|with)\s+" + _MONTH_RE + r"\b",
                str(text), re.I):
            continue
        out.append((yr, mon))
    return out


def product_change_result(df, dataset_id, question, state_fn):
    """
    'Which products increased / decreased in <Month Year>?'  (+ Hinglish / typos)
    Compares that month with the previous month (or with an explicitly named
    second month). Without any month: latest vs previous month in the data.
    Returns a state dict (same shape as _state) or None if not this kind of query.
    """
    q = str(question or "")

    # Do not let this month-to-month product handler intercept richer analyses.
    # Quarterly / FY / QoQ questions, margin questions, and multi-metric
    # comparisons must continue to the semantic planner or dedicated handlers.
    if re.search(
        r"\b(?:q[1-4]|first\s+quarter|second\s+quarter|third\s+quarter|"
        r"fourth\s+quarter|quarterly|quarters?|fiscal\s+year|fy\s*20\d{2}|qoq)\b",
        q,
        re.I,
    ):
        return None
    if re.search(r"\b(?:margin|profit\s+margin|gross\s+margin|net\s+margin)\b", q, re.I):
        return None
    # If both sales and profit are requested, this helper's single-metric
    # selection (which prefers Profit) would silently drop the sales metric.
    if re.search(r"\b(?:sales?|revenue|turnover)\b", q, re.I) and re.search(
        r"\b(?:profits?|munafa)\b", q, re.I
    ):
        return None

    if not _PROD.search(q):
        return None
    if re.search(r"\b(broken down|break ?down|by product|per product|product[\s-]?wise|productwise|wise|each product|for each)\b", q, re.I):
        return None
    try:
        if find_entities(q, df):      # a named customer / product -> planner, not the global product list
            return None
    except Exception:
        pass
    inc, dec = bool(_INC.search(q)), bool(_DEC.search(q))
    if not inc and not dec:
        return None
    direction = "both" if (inc and dec) else ("up" if inc else "down")

    pcol = _find_col(df, ["Product", "Product Name", "Item", "Item Name", "ItemName"])
    dcol = _find_col(df, ["Date", "Invoice Date", "Transaction Date", "Bill Date"])
    if pcol is None or dcol is None:
        return None
    ql = q.lower()
    if re.search(r"\bprofit\b|\bmunafa\b", ql):
        metric_names, metric_label = ["Profit"], "profit"
    elif re.search(r"\bqty\b|\bquantity\b|\bunits?\b", ql):
        metric_names, metric_label = ["Qty", "Quantity"], "quantity"
    elif re.search(r"taxable", ql):
        metric_names, metric_label = ["TaxableAmount"], "taxable sales"
    else:
        metric_names, metric_label = ["GrossAmount", "Sales", "Revenue", "Sales Amount"], "sales"
    mcol = _find_col(df, metric_names)
    if mcol is None:
        return None

    w = df[[pcol, dcol, mcol]].copy()
    w["_d"] = pd.to_datetime(w[dcol], errors="coerce")
    w["_v"] = pd.to_numeric(w[mcol], errors="coerce")
    w["_p"] = w[pcol].astype("string").str.strip()
    w = w.dropna(subset=["_d", "_v", "_p"])
    w = w[w["_p"] != ""]
    if w.empty:
        return None
    w["_m"] = w["_d"].dt.to_period("M")
    avail = sorted(w["_m"].unique())
    if len(avail) < 2:
        return None

    def resolve(yr, mon):
        cands = [m for m in avail if m.month == mon and (yr is None or m.year == yr)]
        return cands[-1] if cands else None

    named = _months_in(q)
    cur = prev = None
    if named:
        cur = resolve(*named[0])
        if cur is None:
            lbl = f"{datetime(2000, named[0][1], 1):%B}" + (f" {named[0][0]}" if named[0][0] else "")
            return state_fn(dataset_id, f"Information is not available in the uploaded file: no sales found for {lbl}.",
                            table=[], rows=[], filtered_rows=0)
        if len(named) >= 2:
            other = resolve(*named[1])
            if other is not None and other != cur:
                prev, cur = (other, cur) if other < cur else (cur, other)
        if prev is None:
            earlier = [m for m in avail if m < cur]
            if not earlier:
                return state_fn(dataset_id, f"There is no month before {cur.strftime('%B %Y')} in the data to compare with.",
                                table=[], rows=[], filtered_rows=0)
            prev = earlier[-1]
    else:
        cur, prev = avail[-1], avail[-2]

    g = (w[w["_m"].isin([prev, cur])].groupby(["_p", "_m"], observed=True)["_v"].sum().unstack(fill_value=0))
    recs = []
    for prod, row in g.iterrows():
        a, b = round(float(row.get(prev, 0)), 2), round(float(row.get(cur, 0)), 2)
        diff = round(b - a, 2)
        if diff == 0:
            continue
        if direction == "up" and diff < 0 or direction == "down" and diff > 0:
            continue
        recs.append({"Product": str(prod), f"{prev.strftime('%b %Y')}": a, f"{cur.strftime('%b %Y')}": b,
                     "Change": diff, "Change %": round(diff / abs(a) * 100, 2) if a else None})
    by_pct = bool(re.search(r"percent|percentage|%|pratishat", ql))
    recs.sort(key=lambda r: abs(r["Change %"]) if (by_pct and r["Change %"] is not None) else abs(r["Change"]),
              reverse=True)
    want_top = None
    if re.search(r"\b(largest|biggest|highest|greatest|maximum|max|most|top|sabse|sab se)\b", ql):
        mt = re.search(r"\btop\s+(\d+)\b", ql)
        want_top = int(mt.group(1)) if mt else 1

    pl, cl = prev.strftime("%B %Y"), cur.strftime("%B %Y")
    word = {"up": "higher", "down": "lower", "both": "different"}[direction]
    fm = lambda x: fmt_metric(metric_label, x)
    if want_top:
        recs = recs[:want_top]
    if not recs:
        ans = f"No product had {word} {metric_label} in {cl} compared with {pl}."
    elif want_top:
        verb = {"up": "increase", "down": "decline", "both": "change"}[direction]
        parts = []
        for r in recs:
            pct = f", {abs(r['Change %']):.2f}%" if r["Change %"] is not None else ""
            parts.append(f"{r['Product']}: {fm(abs(r['Change']))}{pct} "
                         f"({fm(r[prev.strftime('%b %Y')])} in {pl} to {fm(r[cur.strftime('%b %Y')])} in {cl})")
        head = f"Largest {verb} in {metric_label}" if len(recs) == 1 else f"Top {len(recs)} {verb}s in {metric_label}"
        ans = head + ": " + "; ".join(parts) + "."
    else:
        top = recs[:3]
        tops = "; ".join(f"{r['Product']} ({'+' if r['Change'] > 0 else '-'}{fm(abs(r['Change']))})" for r in top)
        ans = (f"{len(recs)} {'product had' if len(recs) == 1 else 'products had'} {word} {metric_label} in {cl} than in {pl}. "
               f"Biggest changes: {tops}. Compared {cl} with {pl}"
               + ("" if named and len(named) >= 2 else " (previous month, assumed)") + ".")
    chart = None
    if len(recs) > 1:
        chart = {"type": "bar", "x": "Product", "series": ["Change"], "interactive": True,
                 "data": recs[:15], "title": f"Product change: {pl} to {cl}"}
    return state_fn(dataset_id, ans, table=recs, rows=recs, filtered_rows=int(len(w)),
                    scope_notes=[f"Metric: {mcol}", f"Compared {cl} with {pl}",
                                 "Calculated from product-wise monthly totals."],
                    **({"chart_spec": chart} if chart else {}))


# ----------------------------- 3. multi-period compare + answer grounding
def multi_period_compare_answer(question, records):
    """
    'Compare May and June' (no year) or 'May 2025 vs June 2025 and May 2026 vs June 2026'
    over records that have a `period` column like 2025-05. Pure arithmetic.
    Returns text or None.
    """
    q = str(question or "")
    if not re.search(r"\b(compare|comparison|compared|versus|vs\.?|difference|tulna)\b", q, re.I):
        return None
    if not isinstance(records, list) or len(records) < 3 or not all(isinstance(r, dict) for r in records):
        return None
    pk = next((k for k in records[0] if str(k).lower() == "period"), None)
    if pk is None:
        return None
    mentions = _months_in(q)
    mons = []
    for _, m in mentions:
        if m not in mons:
            mons.append(m)
    if len(mons) != 2:
        return None
    by = {}
    for r in records:
        m = re.fullmatch(r"(\d{4})-(\d{2})", str(r.get(pk, "")).strip())
        if m:
            k2 = (int(m.group(1)), int(m.group(2)))
            if k2 in by:      # several rows for one period (extra grouping): never pick one of them
                return None
            by[k2] = r
    metrics = [k for k, v in records[0].items()
               if k != pk and isinstance(v, (int, float)) and not isinstance(v, bool)
               and str(k).lower() != "share %" and not str(k).lower().endswith("change %")]
    if not metrics:
        return None
    years = sorted({y for (y, _m) in by})
    lines = []
    for y in years:
        a, b = by.get((y, mons[0])), by.get((y, mons[1]))
        if not a or not b:
            continue
        for mt in metrics:
            x, z = float(a[mt]), float(b[mt])
            d = round(z - x, 2)
            la, lb = datetime(y, mons[0], 1).strftime("%B %Y"), datetime(y, mons[1], 1).strftime("%B %Y")
            s = f"{mt}: {fmt_metric(mt, x)} in {la} and {fmt_metric(mt, z)} in {lb}. "
            if d == 0:
                s += "No change."
            else:
                s += f"It {'increased' if d > 0 else 'decreased'} by {fmt_metric(mt, abs(d))}"
                if x:
                    s += f" ({abs(d / abs(x) * 100):.2f}%)"
                s += "."
            lines.append(s)
    return "\n".join(lines) if lines else None


_AMT = re.compile(r"\u20b9\s*([\d,]+(?:\.\d+)?)")


def _nums(obj, acc):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        acc.add(round(float(obj), 2))
    elif isinstance(obj, dict):
        for v in obj.values():
            _nums(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _nums(v, acc)


def guard_answer(text, records, totals):
    """
    Returns the LLM text if every rupee amount in it exists in the computed
    result (or is a simple difference of two result numbers) and it does not use
    Lakh/Crore words; otherwise None so the caller can use a deterministic text.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if re.search(r"\b(lakh|lakhs|lac|crore|crores|cr)\b", text, re.I):
        return None
    allowed = set()
    _nums(records, allowed)
    _nums(totals, allowed)
    if isinstance(records, list):
        for key in {k for r in records if isinstance(r, dict) for k in r}:
            col = sorted((float(r[key]) for r in records if isinstance(r, dict)
                          and isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)), reverse=True)
            run = 0.0
            for v_ in col[:12]:
                run += v_
                allowed.add(round(run, 2))
            run = 0.0
            for v_ in sorted(col)[:12]:
                run += v_
                allowed.add(round(run, 2))
    vals = sorted(allowed)
    diffs = set()
    if len(vals) <= 60:  # pairwise differences / sums of the computed numbers are legitimate
        for i, a in enumerate(vals):
            for b in vals[i + 1:]:
                diffs.add(round(b - a, 2))
                diffs.add(round(a + b, 2))
    for m in _AMT.finditer(text):
        n = round(float(m.group(1).replace(",", "")), 2)
        if not any(abs(n - v) <= 0.011 for v in allowed | diffs):
            return None
    return text



# ------------------------------------------------ 4. smalltalk without LLM
_GREET = re.compile(r"^\s*(hi+|hii+|hello+|hey+|hola|namaste|namaskar|good\s+(morning|afternoon|evening)|"
                    r"hi there|hello there)\s*[!.?]*\s*$", re.I)
_THANKS = re.compile(r"^\s*(thanks?|thank\s*you|thx|ty|shukriya|dhanyavad|dhanyawad|great|nice|awesome|"
                     r"perfect|thanks a lot|ok\s*thanks?|okay\s*thanks?)\s*[!.]*\s*$", re.I)


def smalltalk_reply(q):
    if _GREET.match(str(q or "")):
        return ("Hello! Ask me anything about your uploaded data, for example: "
                "'total sales in August 2026', 'top 5 customers', or 'which products increased last month'.")
    if _THANKS.match(str(q or "")):
        return "You're welcome! Ask me anything else about your data."
    return None


# --------------------------------------------- 5. does this message need context?
_CTX_WORDS = re.compile(
    r"\b(us|uska|uski|uske|usne|usko|usme|usse|iska|iski|iske|isme|isse|inka|inki|inke|inme|inmein|inse|"
    r"unka|unki|unke|unme|unmein|unse|ye|yeh|yahi|wo|woh|wahi|isi|usi|same|this|that|those|these|them|it|its|"
    r"above|previous|earlier|pichhle|pichle|pichhla|upar|uper|ab|aur|also|then|other|baaki|bakiyon|"
    r"compare|instead|rather|only|sirf)\b", re.I)


def needs_context(q):
    """True when a message looks like a follow-up (pronoun / ellipsis / very short)."""
    text = str(q or "").strip()
    if not text:
        return False
    if len(text.split()) <= 4:
        return True
    return bool(_CTX_WORDS.search(text))



# --------------------------------------------- 5A. answer-aware reference resolver
_PAYMENT_MODES = (
    "Credit Card", "Debit Card", "UPI", "Cash", "Bank Transfer",
    "Net Banking", "Cheque", "Wallet", "Card", "NEFT", "RTGS", "IMPS",
)

def _history_without_current(question, history):
    turns = _turns(history)
    current = _alnum(question)
    if turns and turns[-1][0] == "user" and _alnum(turns[-1][1]) == current:
        turns = turns[:-1]
    return turns


def _last_answer_value(turns, pattern, flags=re.I):
    """Return a capture from the newest assistant answer matching a safe pattern."""
    for role, message in reversed(turns):
        if role != "assistant":
            continue
        match = re.search(pattern, message, flags)
        if match:
            value = (match.group(1) or "").strip(" \t\r\n`*_.,;:!?()[]{}")
            if value:
                return value
    return None


def _previous_period(turns):
    """Find the newest explicit period from user requests; never infer a date."""
    patterns = (
        r"\bCY\s*20\d{2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:to|through|[-?])\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
        r"\bFY\s*20\d{2}\s*[-/]\s*(?:20)?\d{2}\b",
        r"\bcalendar\s+year\s+20\d{2}(?:\s*\([^)]{0,70}\))?",
        r"\b(?:Q[1-4]\s*(?:of\s*)?(?:FY\s*)?20\d{2}\s*[-/]\s*(?:20)?\d{2}|(?:first|second|third|fourth)\s+quarter\s+FY\s*20\d{2}\s*[-/]\s*(?:20)?\d{2})\b",
    )
    for role, message in reversed(turns):
        if role != "user":
            continue
        for pattern in patterns:
            m = re.search(pattern, message, re.I)
            if m:
                return re.sub(r"\s+", " ", m.group(0)).strip()
    return None


def resolve_answer_references(question, history):
    """
    Resolve only explicit conversational references against prior assistant answers.
    This is intentionally conservative: it does not calculate, alter metrics, or
    replace filters unless the new message contains a matching reference phrase.
    """
    q = str(question or "").strip()
    if not q:
        return q
    turns = _history_without_current(q, history)
    if not turns:
        return q

    original = q

    # "this/that top payment mode" -> the mode named in the previous answer.
    mode_ref = re.search(
        r"\b(?:this|that|same|top|highest|selected)"
        r"(?:\s+(?:top|highest|selected|same))*\s+(?:payment\s+)?mode\b",
        q, re.I,
    )
    if mode_ref:
        for role, message in reversed(turns):
            if role != "assistant":
                continue
            # Prefer the mode explicitly named as the winner in the answer's
            # opening sentence; do not pick the first mode from a later table.
            winner = re.search(
                r"^\s*([A-Za-z][A-Za-z ]{1,35}?)\s+"
                r"(?:has|had|recorded|generated|showed)\s+"
                r"(?:the\s+)?(?:highest|lowest|largest|smallest)\b",
                message,
                re.I,
            )
            found = winner.group(1).strip() if winner else None
            if not found:
                # Fallback only when the assistant answer contains one mode.
                present = [
                    mode for mode in _PAYMENT_MODES
                    if re.search(rf"(?<![A-Za-z]){re.escape(mode)}(?![A-Za-z])", message, re.I)
                ]

                # "Card" is already part of "Credit Card" / "Debit Card".
                if "Credit Card" in present or "Debit Card" in present:
                    present = [mode for mode in present if mode != "Card"]

                if len(present) == 1:
                    found = present[0]
            if found:
                q = q[:mode_ref.start()] + f"payment mode {found}" + q[mode_ref.end():]
                break

    # "this/that top B2B dealer/customer/party" -> name explicitly stated in answer.
    party_ref = re.search(
        r"\b(?:this|that|same|top|highest|leading)\s+(?:top\s+)?"
        r"(?:B2B\s+)?(?:dealer|customer|party)\b",
        q, re.I,
    )
    if party_ref:
        party_patterns = (
            r"\b(?:top|highest|leading|best)\s+(?:B2B\s+)?(?:dealer|customer|party)"
            r"[^.\n]{0,100}?\b(?:was|is|:)\s*([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}?)"
            r"(?=\s+(?:with|for|at|by|having|whose|and)\b|[.,;\n]|$)",
            r"\b([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3})"
            r"\s+(?:was|is)\s+(?:the\s+)?(?:top|highest|leading)\s+(?:B2B\s+)?(?:dealer|customer|party)\b",
        )
        party = None
        for pat in party_patterns:
            party = _last_answer_value(turns, pat)
            if party:
                break
        if party:
            q = q[:party_ref.start()] + f"B2B dealer {party}" + q[party_ref.end():]

    # "that specific lowest sales month / that month" -> month named by prior answer.
    month_ref = re.search(
        r"\b(?:that|this|same|specific|lowest|highest)\s+"
        r"(?:(?:specific|lowest|highest)\s+){0,2}(?:sales\s+)?month\b",
        q, re.I,
    )
    if month_ref:
        month = _last_answer_value(
            turns,
            r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+20\d{2})\b",
        )
        if month:
            q = q[:month_ref.start()] + month + q[month_ref.end():]

    # Resolve "that exact same watch model/product/item"
    product_ref = re.search(
        r"\b(?:that|this|same|its)\s+"
        r"(?:(?:exact|same)\s+)*"
        r"(?:watch\s+model|product|item|model)\b",
        q,
        re.I,
    )

    if product_ref:
        product_patterns = (
            # "Top SKU: Ladies Watch" / "The top product is Ladies Watch"
            r"\b(?:top\s+sku|sku|product|item)\b[^.\n]{0,60}?"
            r"(?:is|was|:)\s*[`*_]*([A-Z][A-Za-z0-9&'/ -]+?)"
            r"(?=\s*(?:[.,;\n]|$))",

            # "Analog Leather Watch had the lowest profit margin"
            r"\b([A-Z][A-Za-z0-9&'./-]+"
            r"(?:\s+[A-Z][A-Za-z0-9&'./-]+){1,5})"
            r"\s+(?:had|has|recorded|generated|showed)\b",

            # "Product: Analog Leather Watch"
            r"\b(?:product|item|model)\b[^.\n]{0,100}?"
            r"(?:was|is|:)\s*"
            r"[`*_]*([A-Z][A-Za-z0-9&'./-]+"
            r"(?:\s+[A-Z][A-Za-z0-9&'./-]+){0,5})",
            # Markdown table row with or without a rank column.
            r"\|\s*(?:\d+\s*\|\s*)?"
            r"([A-Z][A-Za-z0-9&'./-]+"
            r"(?:\s+[A-Z][A-Za-z0-9&'./-]+){1,5})"
            r"\s*\|\s*\d+(?:\.\d+)?\s*%",
        )

        product = None

        # Resolve product only from the latest assistant answer.
        # Never fall back to an unrelated older answer.
        latest_assistant = next(
            (
                message for role, message in reversed(turns)
                if role == "assistant"
            ),
            "",
        )

        for pattern in product_patterns:
            match = re.search(pattern, latest_assistant, re.I)
            if match:
                product = (match.group(1) or "").strip(
                    " \t\r\n`*_.,;:!?()[]{}"
                )
                if product:
                    break

        if product:
            q = (
                q[:product_ref.start()]
                + product
                + q[product_ref.end():]
            )

    # Preserve an explicitly referenced "that period"; also carry a prior FY
    # into a direct continuation about the same selected dealer/customer.
    period = _previous_period(turns)
    
    # Do not carry a stale FY period into a product follow-up
    # when the referenced product came from an all-dataset query.
    previous_user_query = next(
        (
            message
            for role, message in reversed(turns)
            if role == "user"
        ),
        "",
    )

    _previous_query_is_dataset_wide = bool(
        re.search(
            r"\b(?:entire|whole|across\s+the\s+entire|"
            r"across\s+the\s+whole)\s+dataset\b",
            previous_user_query,
            re.I,
        )
    )

    if product_ref and _previous_query_is_dataset_wide:
        period = None

    if period and not re.search(
        r"\b(?:FY\s*20\d{2}\s*[-/]\s*(?:20)?\d{2}|"
        r"calendar\s+year\s+20\d{2}|"
        r"CY\s*20\d{2}|"
        r"Q[1-4]\s*(?:of\s*)?(?:FY\s*)?20\d{2}\s*[-/]\s*(?:20)?\d{2}|"
        r"January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\b",
        q,
        re.I,
    ):
        if re.search(r"\bthat\s+period\b", q, re.I):
            q = re.sub(
                r"\bthat\s+period\b",
                f"the same period ({period})",
                q,
                count=1,
                flags=re.I,
            )
        elif (
            (party_ref or mode_ref or product_ref or month_ref)
            and re.search(
                r"\b(?:category|product|sales|revenue|billing|"
                r"transaction|invoice|payment|mode|profit|quantity|"
                r"average|total|count|amount)\b",
                q,
                re.I,
            )
        ):
            q = q.rstrip(" .?!") + f" within {period}."
            

    if q != original:
        print("[FOLLOWUP-REF] resolved answer references:", repr(original), "->", repr(q))
    return q

# --------------------------------------------- 6. entity matching against real values
_STOP = set("""the a an of for in on at to by is are was were what which who whom how much many total sales sale
profit profits quantity qty gst tax margin discount discounts amount revenue show give tell me my our and or with
from compare vs versus month months year years day days week weeks monthly yearly daily per top bottom best worst
highest lowest most least all any every each customer customers party parties product products item items category
categories invoice invoices kitna kitni kitne ka ki ke ko me mein se hai hain tha thi kya kaun konsa kaunsa batao
dikhao aur ya sabse zyada jyada kam uska uski uske iska iski iske inka wo woh yeh ye ab pichhle last previous
latest this that same data report list wise number numbers average avg mean sum count name names value values
increase increased decrease decreased drop dropped growth grew down up higher lower between before after""".split())


def find_entities(question, df, max_hits=6):
    """
    Match words in the question to real cell values (typo tolerant), e.g.
    'leathr walet' -> Product = 'Leather Wallet'. Returns [(column, value, user_text)].
    """
    tokens = re.findall(r"[a-z0-9]+", str(question or "").lower())
    grams = []
    for n in (1, 2, 3, 4):
        for i in range(len(tokens) - n + 1):
            g = tokens[i:i + n]
            if g[0] in _STOP or g[-1] in _STOP:
                continue
            if all(t in MONTHS or t.isdigit() for t in g):
                continue
            joined = "".join(g)
            if len(joined) >= 4:
                grams.append((" ".join(g), joined))
    grams = grams[:30]
    if not grams:
        return []

    hits = {}
    for col in df.columns:
        sr = df[col]
        if pd.api.types.is_numeric_dtype(sr) or pd.api.types.is_datetime64_any_dtype(sr):
            continue
        vals = sr.dropna().astype(str).str.strip().unique()
        if not (2 <= len(vals) <= 3000):
            continue
        nmap = {}
        for v in vals:
            k = re.sub(r"[^a-z0-9]", "", v.lower())
            if len(k) >= 3:
                nmap.setdefault(k, v)
        if not nmap:
            continue
        keys = list(nmap)
        fuzzy_ok = len(keys) <= 600
        for raw, g in grams:
            m = g if g in nmap else None
            if m is None and fuzzy_ok:
                cm = difflib.get_close_matches(g, keys, n=1, cutoff=0.84)
                m = cm[0] if cm else None
            if m is None:
                continue
            key = (col, nmap[m])
            if key not in hits or len(raw) > len(hits[key]):
                hits[key] = raw
    # drop matches whose text is contained in a longer matched text of the same column
    items = sorted(hits.items(), key=lambda kv: -len(kv[1]))
    out, seen = [], set()
    for (col, val), raw in items:
        if any(raw in r and raw != r for c, _, r in out):
            continue
        out.append((col, val, raw))
        seen.add((col, val))
        if len(out) >= max_hits:
            break
    return out


def entity_hint(question, df):
    hits = find_entities(question, df)
    return "; ".join(f"{c} = '{v}' (user wrote '{r}')" for c, v, r in hits)



# ------------------------------------- 7. "<metric> for <entity> [in <month>]" without the LLM
_Q_QTY = re.compile(r"\b(qty|quantity|units?|pieces|pcs)\b", re.I)
_Q_PROFIT = re.compile(r"\b(profit|profits|munafa|kamai)\b", re.I)
_Q_SALES = re.compile(r"\b(sales?|revenue|turnover|billing|bikri|biki|bika|sold)\b", re.I)
_BLOCK_WORDS = re.compile(
    r"\b(top|bottom|highest|lowest|best|worst|rank\w*|wise|by|each|per|which|who|whom|average|avg|mean|"
    r"count|how many|list|trend|growth|increase\w*|decrease\w*|declin\w*|drop\w*|margin|percentage|percent|"
    r"share|ratio|rate|than|except|excluding|without|hero|star|all|every)\b", re.I)
_RELATIVE = re.compile(r"\b(last|previous|this|current|latest|pichh?le|pichh?la|is|iss|isi|agle)\s+(month|mahine|mahina|year|saal|week)\b", re.I)
_CMP = re.compile(r"\b(compare\w*|vs\.?|versus|difference|tulna)\b", re.I)


def entity_metric_result(df, dataset_id, question, state_fn):
    """
    'profit of Power Bank in July 2026', 'total sles of leathr walet', 'Pooja Sharma ka sales may me',
    'compare may and june sales for power bank'. One entity (typo tolerant), one metric, 0-2 months.
    Anything more complex returns None and goes to the planner.
    """
    q = str(question or "")
    if _RELATIVE.search(q):
        return None
    named = _months_in(q)
    uniq_months = []
    for y_, m_ in named:
        if (y_, m_) not in uniq_months:
            uniq_months.append((y_, m_))
    if _BLOCK_WORDS.search(q):
        return None
    is_range = (len(uniq_months) == 2 and not _CMP.search(q) and
                bool(re.search(r"\b(period|between|from|range|till|until|through|upto|up to)\b|\s[-\u2013\u2014]\s", q, re.I)))
    if _CMP.search(q) and len(uniq_months) != 2:
        return None
    if len(uniq_months) > 2:
        return None

    if _Q_QTY.search(q):
        names, label = ["Qty", "Quantity", "Units"], "Quantity"
    elif _Q_PROFIT.search(q):
        names, label = ["Profit", "Net Profit", "Gross Profit"], "Profit"
    elif _Q_SALES.search(q):
        names, label = ["GrossAmount", "SalesAmount", "Sales", "Revenue", "Sales Amount"], "Sales"
    else:
        return None
    mcol = _find_col(df, names)
    dcol = _find_col(df, ["Date", "Invoice Date", "Transaction Date", "Bill Date"])
    if mcol is None or not pd.api.types.is_numeric_dtype(df[mcol]):
        return None

    hits = find_entities(q, df)
    if not hits:
        return None
    by_col = {}
    for col, val, _raw in hits:
        by_col.setdefault(col, set()).add(val)
    if any(len(v) > 1 for v in by_col.values()):
        return None          # two products / two parties in one question -> planner

    mask = pd.Series(True, index=df.index)
    for col, vals in by_col.items():
        v = next(iter(vals))
        mask &= df[col].astype("string").str.strip().str.lower() == v.strip().lower()
    scope = ", ".join(f"{c} = {next(iter(v))}" for c, v in by_col.items())
    sub = df[mask]

    dates = pd.to_datetime(df[dcol], errors="coerce") if dcol is not None else None
    periods = []
    range_label = ""
    if is_range and dates is not None:
        avail_r = sorted(dates.dropna().dt.to_period("M").unique())
        ends = []
        for y_, m_ in uniq_months:
            c_ = [p_ for p_ in avail_r if p_.month == m_ and (y_ is None or p_.year == y_)]
            ends.append(c_[-1] if c_ else pd.Period(year=(y_ or avail_r[-1].year), month=m_, freq="M"))
        lo_p, hi_p = sorted(ends)
        dts = dates.loc[sub.index]
        sub = sub[(dts >= lo_p.start_time) & (dts <= hi_p.end_time)]
        range_label = f"{lo_p.strftime('%b %Y')} - {hi_p.strftime('%b %Y')}"
        uniq_months = []
    if uniq_months:
        if dates is None:
            return None
        avail = sorted(dates.dropna().dt.to_period("M").unique())
        for y_, m_ in uniq_months:
            cands = [p for p in avail if p.month == m_ and (y_ is None or p.year == y_)]
            if not cands:
                lbl = datetime(2000, m_, 1).strftime("%B") + (f" {y_}" if y_ else "")
                return state_fn(dataset_id, f"No data found for {lbl} in the uploaded file.",
                                table=[], rows=[], filtered_rows=0)
            periods.append(cands[-1])
        periods.sort()
    else:
        ym = re.search(r"\b(20\d{2})\b", q)
        if ym and dates is not None and not range_label:
            sub = sub[dates.loc[sub.index].dt.year == int(ym.group(1))]

    fm = lambda x: fmt_metric(label, x)
    rows_out, lines = [], []
    if periods:
        vals = []
        for per in periods:
            part = sub[dates.loc[sub.index].dt.to_period("M") == per]
            val = round(float(pd.to_numeric(part[mcol], errors="coerce").sum()), 2)
            vals.append((per, val, len(part)))
            rows_out.append({"Period": per.strftime("%B %Y"), label: val})
        if all(n == 0 for _, _, n in vals):
            return state_fn(dataset_id, f"No rows found for {scope} in "
                            + " and ".join(p_.strftime("%B %Y") for p_ in periods) + ".",
                            table=[], rows=[], filtered_rows=0)
        if len(vals) == 1:
            ans = f"{label} for {scope} in {vals[0][0].strftime('%B %Y')}: {fm(vals[0][1])}."
        else:
            (p1, v1, _), (p2, v2, _) = vals
            d = round(v2 - v1, 2)
            ans = (f"{label} for {scope}: {fm(v1)} in {p1.strftime('%B %Y')} and {fm(v2)} in {p2.strftime('%B %Y')}. ")
            if d == 0:
                ans += "No change."
            else:
                ans += f"It {'increased' if d > 0 else 'decreased'} by {fm(abs(d))}"
                ans += f" ({abs(d / abs(v1) * 100):.2f}%)." if v1 else "."
    else:
        if sub.empty:
            return state_fn(dataset_id, f"No rows found for {scope}.", table=[], rows=[], filtered_rows=0)
        total = round(float(pd.to_numeric(sub[mcol], errors="coerce").sum()), 2)
        span = f" ({range_label})" if range_label else ""
        if dates is not None and not range_label:
            d_ = dates.loc[sub.index].dropna()
            if len(d_):
                span = f" ({d_.min():%b %Y} - {d_.max():%b %Y})"
        ans = f"{label} for {scope}: {fm(total)}{span}."
        rows_out.append({label: total})
    return state_fn(dataset_id, ans, table=rows_out, rows=rows_out, filtered_rows=int(len(sub)),
                    scope_notes=[f"Metric: {mcol}", f"Filter: {scope}",
                                 "Entity names were matched to the closest value in your data."])


def near_entities(question, df, max_cols=2, per_col=3):
    """Closest real values for words in the question (used when an exact value does not exist)."""
    tokens = re.findall(r"[a-z0-9]+", str(question or "").lower())
    grams = []
    for n in (1, 2, 3):
        for i in range(len(tokens) - n + 1):
            g = tokens[i:i + n]
            if g[0] in _STOP or g[-1] in _STOP or all(t in MONTHS or t.isdigit() for t in g):
                continue
            joined = "".join(g)
            if len(joined) >= 5:
                grams.append(joined)
    if not grams:
        return ""
    found = []
    for col in df.columns:
        sr = df[col]
        if pd.api.types.is_numeric_dtype(sr) or pd.api.types.is_datetime64_any_dtype(sr):
            continue
        vals = sr.dropna().astype(str).str.strip().unique()
        if not (2 <= len(vals) <= 600):
            continue
        nmap = {re.sub(r"[^a-z0-9]", "", v.lower()): v for v in vals}
        picks = []
        for g in grams:
            for m in difflib.get_close_matches(g, list(nmap), n=per_col, cutoff=0.6):
                if nmap[m] not in picks:
                    picks.append(nmap[m])
        if picks:
            found.append(f"{col}: " + ", ".join(f"'{x}'" for x in picks[:per_col]))
        if len(found) >= max_cols:
            break
    return "; ".join(found)



# ------------------------------------------- 8. readable deterministic summary of a result
def summarize_result(p, records, totals, span):
    p = p or {}
    records = records or []
    totals = totals or {}

    def lab(v):
        m = re.fullmatch(r"(\d{4})-(\d{2})", str(v))
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%b %Y") if m else str(v)

    lines = []
    if not records:
        if totals:
            lines.append(", ".join(f"{k}: {fmt_metric(k, v)}" for k, v in totals.items()))
        if span:
            lines.append(f"Period: {span}")
        return "\n".join(lines) or "No rows matched."
    first = records[0]
    num = [k for k, v in first.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    dims = [k for k in first if k not in num]
    mkeys = [k for k in num if str(k).lower() != "share %" and not str(k).lower().endswith("change %")]
    if len(records) == 1 and not dims:
        lines.append(", ".join(f"{k}: {fmt_metric(k, first[k])}" for k in mkeys))
    else:
        by = " and ".join(dims) if dims else "result"
        lines.append(f"{len(records)} rows grouped by {by}. First rows:")
        for r in records[:6]:
            label = " / ".join(lab(r[d]) for d in dims) or "-"
            vals = ", ".join(f"{k} {fmt_metric(k, r[k])}" for k in mkeys[:3] if isinstance(r.get(k), (int, float)))
            if "Share %" in r and isinstance(r.get("Share %"), (int, float)):
                vals += f" ({r['Share %']:.2f}% share)"
            lines.append(f"- {label}: {vals}")
        if len(records) > 6:
            lines.append(f"... and {len(records) - 6} more rows (full table below).")
    if totals:
        lines.append("Totals: " + ", ".join(f"{k}: {fmt_metric(k, v)}" for k, v in totals.items()))
    if span:
        lines.append(f"Period: {span}")
    return "\n".join(lines)