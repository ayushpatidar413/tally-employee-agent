"""Validator = the safety net between the LLM and the executor.
Structure checks  +  COVERAGE checks (the plan must contain everything the user said).
Every issue is a plain sentence that is fed back to the LLM for repair."""
import difflib
import re
from datetime import date

from . import metrics as M
from .grounding import DatasetCard, Grounded, norm
from .schema import Plan

DERIVED_GROUPS = {"month", "quarter", "fy"}


def _closest(value, choices):
    m = difflib.get_close_matches(norm(value), list(choices), n=1, cutoff=0.6)
    return m[0] if m else None


def validate(plan: Plan, card: DatasetCard, g: Grounded, df=None):
    issues = []
    if plan.clarify:
        return issues
    if not plan.parts:
        return ["The plan has no parts. Produce at least one part."]
    avail = M.available(df) if df is not None else {}
    covered_vals, covered_periods, covered_metrics = set(), set(), set()
    for i, p in enumerate(plan.parts, 1):
        tag = f"part {p.id}"
        if p.ask not in ("total", "rank", "compare"):
            issues.append(f"{tag}: ask must be total, rank or compare (got '{p.ask}').")
        if not p.metrics:
            issues.append(f"{tag}: no metric given.")
        for m in p.metrics:
            if m not in M.METRICS:
                issues.append(f"{tag}: unknown metric '{m}'. Allowed: {', '.join(M.METRICS)}.")
            elif avail and not avail.get(m, True):
                issues.append(f"{tag}: metric '{m}' needs columns that this dataset does not have.")
            covered_metrics.add(m)
        for f in p.filters:
            if f.column not in card.columns:
                issues.append(f"{tag}: filter column '{f.column}' does not exist. Columns: {', '.join(card.columns)}.")
                continue
            vals = card.values.get(f.column)
            if f.op in ("==", "!=", "in") and vals is not None:
                for v in (f.value if isinstance(f.value, list) else [f.value]):
                    if norm(v) not in vals:
                        near = _closest(v, vals)
                        issues.append(f"{tag}: value '{v}' is not in column {f.column}" + (f" (closest: '{vals[near]}')." if near else "."))
                    else:
                        covered_vals.add((f.column, norm(v)))
        if p.ask == "rank" and not p.group_by:
            issues.append(f"{tag}: a ranking needs group_by.")
        if p.group_by and p.group_by.lower() not in DERIVED_GROUPS and p.group_by not in card.columns:
            issues.append(f"{tag}: group_by '{p.group_by}' is not a column (or Month/Quarter/FY).")
        if p.ask == "compare" and len(p.periods) != 2:
            issues.append(f"{tag}: compare needs exactly 2 periods.")
        for per in ([p.period] if p.period else []) + list(p.periods):
            try:
                a, b = date.fromisoformat(per.start), date.fromisoformat(per.end)
                if a > b:
                    issues.append(f"{tag}: period start is after end.")
                covered_periods.add((per.start, per.end))
            except ValueError:
                issues.append(f"{tag}: period dates must be YYYY-MM-DD.")
        if p.depends_on:
            ref = p.depends_on.get("part")
            if not isinstance(ref, int) or ref >= p.id or ref < 1:
                issues.append(f"{tag}: depends_on must point to an EARLIER part.")
    # ---------------- coverage: nothing the user said may be dropped
    for e in g.entities:
        if e.exact and (e.column, norm(e.value)) not in covered_vals and not _is_group_target(e, plan):
            issues.append(f"The question mentions {e.column} = '{e.value}' but no filter uses it. Add the filter (or explain in assumptions).")
        if not e.exact:
            issues.append(f"The question has '{e.span}', which looks like a typo of {e.column} = '{e.value}'. Use the exact value in a filter, or ask to clarify.")
    for u in g.unknown:
        issues.append(f"'{u}' was named in the question but exists in no column. Do NOT drop it: set clarify to say it is not in the data.")
    if g.periods and not g.flags.get("entire_dataset"):
        for per in g.periods:
            if (per.start, per.end) not in covered_periods:
                issues.append(f"The question states the period {per.label} ({per.start}..{per.end}) but no part uses it.")
    ment = M.mentioned(g.question)
    miss = [m for m in ment if m not in covered_metrics and not _implied(m, covered_metrics)]
    if miss:
        issues.append(f"The question asks for {', '.join(miss)} but no part computes it.")
    if g.n_questions > 1 and len(plan.parts) < 2:
        issues.append("The message contains more than one question but the plan has one part. Answer every question (one part each).")
    return issues


def _implied(m, covered):
    spec = M.METRICS.get(m, {})
    return any(M.METRICS.get(c, {}).get("kind") == "ratio" and m in (M.METRICS[c]["num"], M.METRICS[c]["den"]) for c in covered)


def _is_group_target(e, plan):
    """'which state ...' style: the column name itself is not a value, so values never get here;
    a value that is the group_by column of every part is not filterable."""
    return all((p.group_by or "") == e.column for p in plan.parts) and bool(plan.parts)
