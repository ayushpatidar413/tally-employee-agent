"""Grounding = everything that can be decided by CODE before the LLM is asked anything.
 - DatasetCard : columns, roles, categorical values, date coverage
 - periods     : FY / quarter / month / ranges / relative months  ->  exact dates
 - entities    : dataset values found in the question (exact + typo-tolerant)  -> exact column + value
"""
import calendar
import difflib
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

import pandas as pd

from .schema import Period

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
MRX = "|".join(sorted(MONTHS, key=len, reverse=True))


# ------------------------------------------------------------------ normalisation
def norm(s) -> str:
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _sing(tok):
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") else tok


def tokens(s):
    return [_sing(t) for t in norm(s).split()]


# ------------------------------------------------------------------ dataset card
@dataclass
class DatasetCard:
    columns: List[str]
    date_col: Optional[str]
    date_min: Optional[date]
    date_max: Optional[date]
    values: dict = field(default_factory=dict)     # column -> {norm: raw}
    numeric: List[str] = field(default_factory=list)
    rows: int = 0

    @staticmethod
    def build(df, max_card=300):
        dcol = next((c for c in df.columns if "date" in str(c).lower()), None)
        dmin = dmax = None
        if dcol is not None:
            d = pd.to_datetime(df[dcol], errors="coerce")
            if d.notna().any():
                dmin, dmax = d.min().date(), d.max().date()
        vals, nums = {}, []
        for c in df.columns:
            if c == dcol:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                nums.append(c)
                continue
            u = df[c].dropna().astype(str).str.strip().unique()
            if len(u) and sum(bool(re.search(r"\d", x)) for x in u) / len(u) > 0.5:
                continue      # ids / GSTIN / month strings: not entities
            if 0 < len(u) <= max_card:
                vals[c] = {norm(v): v for v in u if norm(v)}
        return DatasetCard(list(map(str, df.columns)), dcol, dmin, dmax, vals, nums, len(df))

    def describe(self, per_col=40):
        lines = [f"rows={self.rows}; date column={self.date_col}; data covers {self.date_min} to {self.date_max}"]
        for c, v in self.values.items():
            raw = sorted(v.values())
            lines.append(f"- {c} ({len(raw)} values): " + ", ".join(raw[:per_col]) + (" ..." if len(raw) > per_col else ""))
        lines.append("- numeric columns: " + ", ".join(self.numeric))
        return "\n".join(lines)


# ------------------------------------------------------------------ periods
def _fy(y0):
    return date(y0, 4, 1), date(y0 + 1, 3, 31)


def _month_end(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def _full_year(y2):
    y2 = int(y2)
    return y2 if y2 > 99 else 2000 + y2


def _fy_label(y0):
    return f"FY{y0}-{str(y0 + 1)[-2:]}"


def resolve_periods(text, data_max: Optional[date] = None):
    """-> (list[Period], flags).  Never guesses silently: bare 'Q2' is flagged as an assumption."""
    s = str(text).replace("\u2013", "-").replace("\u2014", "-")
    found = []  # (start, end, Period)

    def add(m, lo, hi, label):
        found.append((m.start(), m.end(), Period(lo.isoformat(), hi.isoformat(), label)))

    flags = {"entire_dataset": bool(re.search(r"\bentire\s+data\s*set\b|\bwhole\s+data\b|\ball\s+time\b|\bfull\s+data\s*set\b", s, re.I)),
             "assumptions": []}
    for m in re.finditer(r"\bQ([1-4])\s*(?:of\s*)?FY\s*(20\d{2})\s*[-/]\s*(\d{2,4})\b", s, re.I):
        y0 = int(m.group(2)); q = int(m.group(1))
        sm = 4 + 3 * (q - 1); sy = y0 + (1 if sm > 12 else 0); sm = sm - 12 if sm > 12 else sm
        em = sm + 2; ey = sy + (1 if em > 12 else 0); em = em - 12 if em > 12 else em
        add(m, date(sy, sm, 1), _month_end(ey, em), f"Q{q} {_fy_label(y0)}")
    for m in re.finditer(r"\b(?:FY|(?:financial|fiscal)\s+year)\s*(20\d{2})\s*[-/]\s*(\d{2,4})\b", s, re.I):
        y0 = int(m.group(1)); lo, hi = _fy(y0); add(m, lo, hi, _fy_label(y0))
    for m in re.finditer(r"\bFY\s*(\d{2})\s*[-/]\s*(\d{2})\b", s, re.I):
        y0 = _full_year(m.group(1)); lo, hi = _fy(y0); add(m, lo, hi, _fy_label(y0))
    for m in re.finditer(r"\bFY\s*(\d{2})\b(?![\d-])", s, re.I):
        y0 = _full_year(m.group(1)) - 1; lo, hi = _fy(y0); add(m, lo, hi, _fy_label(y0))
    for m in re.finditer(rf"\b({MRX})\w*\.?\s+(\d{{1,2}}),?\s+(20\d{{2}}),?\s*(?:to|-|through|and)\s*({MRX})\w*\.?\s+(\d{{1,2}}),?\s+(20\d{{2}})", s, re.I):
        lo = date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
        hi = date(int(m.group(6)), MONTHS[m.group(4).lower()], int(m.group(5)))
        add(m, lo, hi, f"{lo.isoformat()}..{hi.isoformat()}")
    for m in re.finditer(r"\b(20\d{2}-\d{2}-\d{2})\s*(?:to|-|through)\s*(20\d{2}-\d{2}-\d{2})\b", s):
        add(m, date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2)), f"{m.group(1)}..{m.group(2)}")
    for m in re.finditer(rf"\b({MRX})[a-z]*\.?\s*-\s*({MRX})[a-z]*\.?,?\s+(20\d{{2}})\b", s, re.I):
        a, b, y = MONTHS[m.group(1).lower()], MONTHS[m.group(2).lower()], int(m.group(3))
        if a <= b:
            add(m, date(y, a, 1), _month_end(y, b), f"{calendar.month_abbr[a]} {y} - {calendar.month_abbr[b]} {y}")
    for m in re.finditer(rf"\b({MRX})[a-z]*\.?,?\s+(20\d{{2}})\b", s, re.I):
        mo, y = MONTHS[m.group(1).lower()], int(m.group(2))
        add(m, date(y, mo, 1), _month_end(y, mo), f"{calendar.month_name[mo]} {y}")
    if data_max:
        for m in re.finditer(r"\b(?:last|latest|this)\s+month\b|\bpichh?le\s+mahine\b|\bis\s+mahine\b", s, re.I):
            add(m, date(data_max.year, data_max.month, 1), _month_end(data_max.year, data_max.month),
                f"{calendar.month_name[data_max.month]} {data_max.year}")
            flags["assumptions"].append(f"'{m.group(0)}' = latest month in the data ({calendar.month_name[data_max.month]} {data_max.year})")
    # drop spans swallowed by a longer span, then exact duplicates of the same dates
    found.sort(key=lambda t: -(t[1] - t[0]))
    kept = []
    for st, en, p in found:
        if any(st >= k[0] and en <= k[1] for k in kept):
            continue
        kept.append((st, en, p))
    kept.sort(key=lambda t: t[0])
    out, seen = [], set()
    for _, _, p in kept:
        key = (p.start, p.end)
        if key not in seen:
            seen.add(key); out.append(p)
    if not out and re.search(r"\bQ[1-4]\b", s):
        flags["assumptions"].append("bare quarter without a financial year: ask or state the assumption")
        flags["bare_quarter"] = True
    return out, flags


# ------------------------------------------------------------------ entities
@dataclass
class Entity:
    column: str
    value: str
    span: str
    exact: bool
    score: float = 1.0


def link_entities(card: DatasetCard, question: str, fuzzy=0.88):
    """Find dataset values mentioned in the question. -> (entities, unknown_quoted)"""
    qt = tokens(question)
    found, covered = [], [False] * len(qt)
    cands = []   # (n_tokens, column, raw, vtoks)
    for col, vals in card.values.items():
        for nv, raw in vals.items():
            vt = [_sing(t) for t in nv.split()]
            if vt:
                cands.append((len(vt), col, raw, vt))
    cands.sort(key=lambda c: -c[0])   # longest first so 'Smart Watch' beats 'Watch'
    for n, col, raw, vt in cands:
        for i in range(len(qt) - n + 1):
            if qt[i:i + n] == vt and not all(covered[i:i + n]):
                found.append(Entity(col, raw, " ".join(qt[i:i + n]), True))
                for j in range(i, i + n):
                    covered[j] = True
    # typo tolerance on what is still uncovered (min 5 chars to avoid noise)
    for n, col, raw, vt in cands:
        target = " ".join(vt)
        if len(target) < 5:
            continue
        for i in range(len(qt) - n + 1):
            if any(covered[i:i + n]):
                continue
            w = " ".join(qt[i:i + n])
            r = difflib.SequenceMatcher(None, w, target).ratio()
            if r >= fuzzy and w != target:
                found.append(Entity(col, raw, w, False, round(r, 2)))
                for j in range(i, i + n):
                    covered[j] = True
    known = {norm(e.value) for e in found}
    unknown = []
    for q in re.findall(r"['\"\u2018\u201c]([^'\"\u2019\u201d]{2,40})['\"\u2019\u201d]", question):
        nq = norm(q)
        if not nq or len(nq.split()) > 4 or re.match(r"(what|which|who|how|total|show|give)\b", nq):
            continue
        if nq in known or any(nq == norm(e.value) or _sing(nq) == _sing(norm(e.value)) for e in found):
            continue
        if not any(nq in vals or _sing(nq) in {_sing(x) for x in vals} for vals in card.values.values()):
            unknown.append(q)
    return found, unknown


# ------------------------------------------------------------------ one call used by the pipeline
@dataclass
class Grounded:
    question: str
    periods: List[Period]
    entities: List[Entity]
    unknown: List[str]
    flags: dict
    n_questions: int


def ground(question: str, card: DatasetCard) -> Grounded:
    periods, flags = resolve_periods(question, card.date_max)
    ents, unknown = link_entities(card, question)
    nq = max(question.count("?"), 1)
    if re.search(r"\b(?:and\s+also|aur\s+bhi|also,)\b|,\s*and\s+(?:what|which|who|when)\b", question, re.I):
        nq = max(nq, 2)
    return Grounded(question, periods, ents, unknown, flags, nq)
