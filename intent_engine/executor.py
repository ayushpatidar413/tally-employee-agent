"""Executor = deterministic pandas. The only place numbers are produced."""
import calendar
from dataclasses import dataclass, field
from typing import Any, List

import pandas as pd

from . import metrics as M
from .grounding import norm
from .schema import Part, Plan


def inr(v):
    n = round(float(v), 2)
    s = f"{abs(n):.2f}"
    ip, fp = s.split(".")
    if len(ip) > 3:
        head, tail = ip[:-3], ip[-3:]
        head = ",".join([head[max(i - 2, 0):i] for i in range(len(head), 0, -2)][::-1])
        ip = head + "," + tail
    return ("-" if n < 0 else "") + "\u20b9" + ip + "." + fp


def num(v):
    return f"{round(float(v)):,}"


@dataclass
class PartResult:
    part_id: int
    rows: List[dict] = field(default_factory=list)
    text: str = ""
    scope: str = ""
    matched: int = 0
    keys: List[Any] = field(default_factory=list)     # ranked group keys (for depends_on)


def _fmt(metric, v):
    m = M.METRICS[metric]
    if v is None or pd.isna(v):
        return "n/a"
    if m.get("pct"):
        return f"{v:.2f}%"
    return inr(v) if m["money"] else num(v)


def _value(df, metric):
    """scalar for one metric over df"""
    m = M.METRICS[metric]
    if m["kind"] == "sum":
        c = M.find_col(df, m["cols"])
        return float(pd.to_numeric(df[c], errors="coerce").fillna(0).sum())
    if m["kind"] == "nunique":
        c = M.find_col(df, m["cols"])
        return float(df[c].nunique())
    n, d = _value(df, m["num"]), _value(df, m["den"])
    return None if not d else n / d * m.get("mult", 1)


def _apply_filters(df, filters, dcol, period):
    w = df
    for f in filters:
        col = next((c for c in df.columns if str(c) == f.column), None)
        if col is None:
            raise ValueError(f"unknown column {f.column}")
        s = w[col]
        if f.op in ("==", "!=", "in"):
            want = {norm(x) for x in (f.value if isinstance(f.value, list) else [f.value])}
            hit = s.astype(str).map(norm).isin(want)
            w = w[hit] if f.op != "!=" else w[~hit]
        else:
            x = pd.to_numeric(s, errors="coerce")
            w = w[{">": x > float(f.value), ">=": x >= float(f.value), "<": x < float(f.value), "<=": x <= float(f.value)}[f.op]]
    if period is not None:
        d = pd.to_datetime(w[dcol], errors="coerce")
        w = w[(d >= pd.Timestamp(period.start)) & (d < pd.Timestamp(period.end) + pd.Timedelta(days=1))]
    return w


def _group_key(df, dcol, group_by):
    g = group_by.lower()
    d = pd.to_datetime(df[dcol], errors="coerce")
    if g == "month":
        return d.dt.to_period("M")
    if g in ("quarter", "fy"):
        fy0 = d.dt.year - (d.dt.month < 4).astype(int)
        if g == "fy":
            return "FY" + fy0.astype(str) + "-" + (fy0 + 1).astype(str).str[-2:]
        q = ((d.dt.month - 4) % 12) // 3 + 1
        return "Q" + q.astype(str) + " FY" + fy0.astype(str) + "-" + (fy0 + 1).astype(str).str[-2:]
    return df[group_by].astype(str).str.strip()


def _nice(k):
    return f"{calendar.month_name[k.month]} {k.year}" if isinstance(k, pd.Period) else str(k)


def run_part(df, dcol, part: Part, prior: dict) -> PartResult:
    filters = list(part.filters)
    if part.depends_on:
        ref = prior.get(part.depends_on["part"])
        if ref is None or not ref.keys:
            return PartResult(part.id, text=f"Part {part.id} depends on part {part.depends_on['part']}, which found nothing.")
        from .schema import Filter
        filters.append(Filter(part.depends_on["column"], "==", ref.keys[0]))
    scope_bits = [f"{f.column} {f.op} {f.value}" for f in filters] + ([part.period.label or f"{part.period.start}..{part.period.end}"] if part.period else [])
    scope = "; ".join(scope_bits) or "entire dataset"
    res = PartResult(part.id, scope=scope)

    if part.ask == "compare":
        vals = []
        for per in part.periods:
            w = _apply_filters(df, filters, dcol, per)
            vals.append((per.label or f"{per.start}..{per.end}", _value(w, part.metrics[0])))
        (l1, v1), (l2, v2) = vals
        res.rows = [{"Period": l1, "Value": round(v1 or 0, 2)}, {"Period": l2, "Value": round(v2 or 0, 2)}]
        chg = f"{l2} is {abs((v2 - v1) / v1 * 100):.2f}% {'higher' if v2 > v1 else 'lower'} than {l1}" if v1 else f"change % not defined because {l1} is zero"
        res.text = f"{M.METRICS[part.metrics[0]]['label'].capitalize()}: {l1} = {_fmt(part.metrics[0], v1)}; {l2} = {_fmt(part.metrics[0], v2)}. {chg}."
        res.scope = "; ".join([f"{f.column} {f.op} {f.value}" for f in filters] + [l1, l2])
        return res

    w = _apply_filters(df, filters, dcol, part.period)
    res.matched = len(w)
    m0 = part.metrics[0]
    if part.ask == "total" or not part.group_by:
        row = {M.METRICS[m]["label"].title(): (round(_value(w, m), 2) if _value(w, m) is not None else None) for m in part.metrics}
        res.rows = [row]
        res.text = "; ".join(f"{M.METRICS[m]['label'].capitalize()}: {_fmt(m, _value(w, m))}" for m in part.metrics) + ("" if len(w) else " (no matching rows)")
        return res

    if w.empty:
        res.text = "No rows matched this scope, so nothing can be ranked."
        return res
    key = _group_key(w, dcol, part.group_by)
    out = []
    for k, sub in w.groupby(key, sort=False):
        out.append((k, {m: _value(sub, m) for m in part.metrics}))
    out = [o for o in out if o[1][m0] is not None]
    asc = part.order == "asc"
    out.sort(key=lambda o: o[1][m0], reverse=not asc)
    n = part.limit or 1
    top = out[:n]
    if n == 1:
        ties = [o for o in out if o[1][m0] == out[0][1][m0]][:5]
        top = ties if len(ties) > 1 else top
    res.keys = [k if not isinstance(k, pd.Period) else k for k, _ in top]
    gl = part.group_by.title() if part.group_by.lower() in ("month", "quarter", "fy") else part.group_by
    res.rows = [dict({"Rank": i, gl: _nice(k)}, **{M.METRICS[m]["label"].title(): round(v[m], 2) for m in part.metrics}) for i, (k, v) in enumerate(top, 1)]
    word = "Lowest" if asc else "Highest"
    if len(top) == 1:
        res.text = f"{word} {M.METRICS[m0]['label']} by {gl.lower()}: {_nice(top[0][0])} with {_fmt(m0, top[0][1][m0])}"
    elif n == 1:
        res.text = f"{word} {M.METRICS[m0]['label']} by {gl.lower()} is shared ({_fmt(m0, top[0][1][m0])} each): " + ", ".join(_nice(k) for k, _ in top)
    else:
        res.text = f"{'Bottom' if asc else 'Top'} {len(top)} by {M.METRICS[m0]['label']} ({gl.lower()}): " + "; ".join(f"{i}. {_nice(k)} ({_fmt(m0, v[m0])})" for i, (k, v) in enumerate(top, 1))
    return res


def execute(df, dcol, plan: Plan):
    results, prior = [], {}
    for part in plan.parts:
        r = run_part(df, dcol, part, prior)
        prior[part.id] = r
        results.append(r)
    return results


def compose(results: List[PartResult], plan: Plan) -> str:
    if len(results) == 1:
        r = results[0]
        return f"{r.text}. Scope: {r.scope}." if not r.text.endswith(".") else f"{r.text} Scope: {r.scope}."
    lines = [f"{i}. {r.text.rstrip('.')}." for i, r in enumerate(results, 1)]
    scopes = []
    for r in results:
        if r.scope not in scopes:
            scopes.append(r.scope)
    lines.append("Scope: " + " | ".join(scopes) + ".")
    if plan.assumptions:
        lines.append("Assumptions: " + "; ".join(plan.assumptions) + ".")
    return "\n".join(lines)
