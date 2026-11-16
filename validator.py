"""Planner = the ONLY place an LLM is used for understanding.
 - grounded facts are injected (exact dates, exact column/value pairs) so the LLM never has to guess them
 - dynamic few-shot: the most similar solved questions from golden.json are shown as examples
 - repair loop: validator issues are sent back, max N times
`llm` is any callable (system: str, user: str) -> str   (plug Gemini/Groq/OpenAI in one line)"""
import json
import re
from typing import Callable, List, Optional

from . import metrics as M
from .grounding import DatasetCard, Grounded, norm
from .schema import Plan, plan_from_dict

SYSTEM = """You are a professional business-data query planner. You convert ANY question about an uploaded table
(typos, Hinglish, fragments, two questions in one) into a JSON PLAN. You never calculate numbers.

PLAN SCHEMA (return JSON only):
{"parts":[{"id":1,"ask":"total|rank|compare","metrics":["sales"],
  "filters":[{"column":"PartyType","op":"==","value":"B2B Dealer"}],
  "period":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD","label":"Q1 FY2025-26"} | null,
  "periods":[ ...two periods, compare only... ],
  "group_by":"<column>|Month|Quarter|FY|null","order":"desc|asc","limit":1,
  "depends_on":{"part":1,"column":"PartyName"} | null}],
 "assumptions":["..."], "clarify": null | "one short question or a statement that something is not in the data"}

RULES
1. GROUNDED FACTS are exact. Use the given columns, values and dates verbatim. Never invent a value, column or date.
2. A value named after within/in/for/of/among (a state, category, party type, payment mode, product) is a FILTER on its own column.
   group_by is the thing the user wants ranked/listed ("which state", "top 2 products", "who").
3. Every metric, entity and period the user mentioned must appear in the plan. Never drop one.
4. Two or more questions in one message -> one part per question, in order. A later part that uses the winner of an earlier part
   ("their", "uska", "that dealer") gets depends_on {"part": <earlier id>, "column": <the earlier part's group_by>}.
5. A stated period applies to every part unless a part states its own. 'entire dataset' means no period.
6. ask=total for a single number, rank for 'which/who/top N/highest/lowest', compare for two periods of one metric.
7. If something asked is not in the data, set clarify to say so instead of substituting something else.
Metrics: """ + ", ".join(f"{k} ({v['label']})" for k, v in M.METRICS.items()) + "."


def _facts(g: Grounded) -> str:
    lines = []
    for p in g.periods:
        lines.append(f"- period: '{p.label}' = {p.start} .. {p.end} (inclusive)")
    for e in g.entities:
        lines.append(f"- entity: column {e.column} = '{e.value}'" + ("" if e.exact else f"  (user typed '{e.span}', probable typo)"))
    for u in g.unknown:
        lines.append(f"- NOT IN DATA: '{u}' (do not substitute; use clarify)")
    for a in g.flags.get("assumptions", []):
        lines.append(f"- note: {a}")
    if g.flags.get("entire_dataset"):
        lines.append("- the user asked for the ENTIRE dataset: do not apply a period")
    lines.append(f"- number of questions detected: {g.n_questions}")
    return "\n".join(lines) or "- (none)"


def _jacc(a, b):
    a, b = set(norm(a).split()), set(norm(b).split())
    return len(a & b) / (len(a | b) or 1)


def pick_examples(question, golden: Optional[List[dict]], k=4):
    if not golden:
        return ""
    ranked = sorted(golden, key=lambda x: -_jacc(question, x["question"]))[:k]
    return "\n".join(f"Q: {x['question']}\nPLAN: {json.dumps(x['plan'], ensure_ascii=False)}" for x in ranked)


def build_user_prompt(question, card: DatasetCard, g: Grounded, golden=None) -> str:
    ex = pick_examples(question, golden)
    return (f"DATASET\n{card.describe()}\n\nGROUNDED FACTS\n{_facts(g)}\n\n"
            + (f"SIMILAR SOLVED QUESTIONS\n{ex}\n\n" if ex else "") + f"QUESTION\n{question}\n\nPLAN JSON:")


def build_repair_prompt(base_prompt, bad_plan_json, issues) -> str:
    return (base_prompt + "\n\nYOUR PREVIOUS PLAN\n" + bad_plan_json + "\n\nPROBLEMS FOUND BY THE VALIDATOR (fix all, return the full corrected plan JSON only)\n"
            + "\n".join(f"- {i}" for i in issues))


def parse_json(text: str) -> dict:
    t = re.sub(r"^```(?:json)?|```$", "", str(text).strip(), flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ValueError("no JSON object in LLM output")
    return json.loads(t[i:j + 1])


def make_plan(llm: Callable[[str, str], str], question, card, g, validate_fn, golden=None, max_repairs=2):
    """-> (plan | None, issues, attempts)"""
    base = build_user_prompt(question, card, g, golden)
    prompt, attempts, issues, plan = base, 0, [], None
    for _ in range(max_repairs + 1):
        attempts += 1
        raw = llm(SYSTEM, prompt)
        try:
            plan = plan_from_dict(raw if isinstance(raw, dict) else parse_json(raw))   # your _llm(..., as_json=True) already returns a dict
        except Exception as exc:
            issues = [f"Output was not a valid plan JSON ({type(exc).__name__}: {str(exc)[:120]})."]
            prompt = build_repair_prompt(base, str(raw)[:1500], issues)
            plan = None
            continue
        issues = validate_fn(plan)
        if not issues:
            return plan, [], attempts
        prompt = build_repair_prompt(base, json.dumps(plan.to_dict(), ensure_ascii=False), issues)
    return plan, issues, attempts
