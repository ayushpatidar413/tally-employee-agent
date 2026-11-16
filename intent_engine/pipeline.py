"""Single entry point.  status: ok | clarify | needs_review
 ok           -> answer is deterministic and every user-stated filter/period/metric/part was verified present
 clarify      -> the LLM (or the grounding step) says something asked is not in the data / is ambiguous
 needs_review -> the plan could not be made valid after repairs: DO NOT guess; fall back to the legacy chain or ask the user"""
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from . import executor, planner
from .grounding import DatasetCard, ground
from .validator import validate


@dataclass
class IntentResult:
    status: str
    answer: str = ""
    rows: List[dict] = field(default_factory=list)
    plan: Optional[dict] = None
    issues: List[str] = field(default_factory=list)
    attempts: int = 0
    scope: List[str] = field(default_factory=list)
    ms: int = 0


_CARDS = {}


def _card(df):
    k = (id(df), len(df))
    if k not in _CARDS:
        _CARDS.clear()
        _CARDS[k] = DatasetCard.build(df)
    return _CARDS[k]


def run(question: str, df, llm: Callable[[str, str], str], golden=None, max_repairs=2, log_path: Optional[str] = None) -> IntentResult:
    t0 = time.perf_counter()
    card = _card(df)
    g = ground(question, card)
    plan, issues, attempts = planner.make_plan(llm, question, card, g, lambda p: validate(p, card, g, df), golden, max_repairs)
    if plan is None or (issues and not plan.clarify):
        res = IntentResult("needs_review", plan=plan.to_dict() if plan else None, issues=issues, attempts=attempts)
    elif plan.clarify:
        res = IntentResult("clarify", answer=plan.clarify, plan=plan.to_dict(), attempts=attempts)
    else:
        parts = executor.execute(df, card.date_col, plan)
        res = IntentResult("ok", answer=executor.compose(parts, plan), rows=[r for p in parts for r in p.rows],
                           plan=plan.to_dict(), attempts=attempts, scope=[p.scope for p in parts])
    res.ms = int((time.perf_counter() - t0) * 1000)
    if log_path:        # every query + plan + status: this file becomes your next golden set
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"q": question, "status": res.status, "attempts": attempts, "issues": issues, "plan": res.plan}, ensure_ascii=False) + "\n")
        except Exception:
            pass
    return res
