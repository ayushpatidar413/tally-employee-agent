"""Typed query plan (plain dataclasses: no extra dependency)."""
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional

ASKS = {"total", "rank", "compare"}


@dataclass
class Filter:
    column: str
    op: str = "=="            # == != in > >= < <=
    value: Any = None


@dataclass
class Period:
    start: str                # YYYY-MM-DD inclusive
    end: str                  # YYYY-MM-DD inclusive
    label: str = ""


@dataclass
class Part:
    id: int = 1
    ask: str = "total"        # total | rank | compare
    metrics: List[str] = field(default_factory=list)       # names from metrics.METRICS
    filters: List[Filter] = field(default_factory=list)
    period: Optional[Period] = None
    periods: List[Period] = field(default_factory=list)    # compare only (2 periods)
    group_by: Optional[str] = None                          # column | Month | Quarter | FY
    order: str = "desc"
    limit: Optional[int] = None
    depends_on: Optional[dict] = None                       # {"part": 1, "column": "PartyName"}


@dataclass
class Plan:
    parts: List[Part] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    clarify: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def plan_from_dict(d: dict) -> Plan:
    """Tolerant parser: unknown keys ignored, wrong shapes raise ValueError."""
    if not isinstance(d, dict):
        raise ValueError("plan must be a JSON object")
    parts = []
    for i, p in enumerate(d.get("parts") or [], 1):
        if not isinstance(p, dict):
            raise ValueError("each part must be an object")
        def per(x):
            return Period(str(x["start"]), str(x["end"]), str(x.get("label", ""))) if isinstance(x, dict) and x.get("start") and x.get("end") else None
        parts.append(Part(
            id=int(p.get("id") or i), ask=str(p.get("ask") or "total").lower(),
            metrics=[str(m).lower() for m in (p.get("metrics") or [])],
            filters=[Filter(str(f.get("column")), str(f.get("op") or "==").lower(), f.get("value")) for f in (p.get("filters") or []) if isinstance(f, dict)],
            period=per(p.get("period")), periods=[x for x in (per(q) for q in (p.get("periods") or [])) if x],
            group_by=(str(p["group_by"]) if p.get("group_by") else None),
            order=str(p.get("order") or "desc").lower(),
            limit=(int(p["limit"]) if p.get("limit") not in (None, "") else None),
            depends_on=p.get("depends_on") if isinstance(p.get("depends_on"), dict) else None))
    return Plan(parts=parts, assumptions=[str(a) for a in (d.get("assumptions") or [])],
                clarify=(str(d["clarify"]) if d.get("clarify") else None))
