"""Confidence score for /ask-business responses.

Ye "answer sahi hone ki probability" nahi hai (LLM ka self-reported confidence unreliable hota hai).
Numbers hamesha pandas se compute hote hain; uncertainty sirf *interpretation* me hoti hai:
kaunsa engine chala, sawal rewrite hua ya nahi, naam fuzzy-match hua ya nahi, rows mile ya nahi.
Isliye score in signals se deterministic nikalta hai aur 'reasons' me wajah dikhti hai.
"""
import re

_FUZZY = re.compile(r"'[^']+'\s*->\s*'[^']+'")


def _norm(s):
    return re.sub(r"[^\w]+", " ", str(s or "").casefold()).strip()


def score_confidence(*, engine, question, standalone, answer, result):
    result = result or {}
    reasons = []
    eng = str(engine or "")

    if result.get("needs_clarification"):
        return {"score": None, "level": "needs_input",
                "reasons": ["Assistant is waiting for your clarification"]}
    if eng == "semantic-unavailable":
        return {"score": 0, "level": "low", "reasons": ["AI engine was unavailable"]}

    if eng.startswith("semantic-deterministic") or eng == "semantic-smalltalk":
        score = 96
        reasons.append("Calculated by fixed rules directly on the uploaded rows")
    elif eng == "semantic":
        if result.get("tier") == "code":
            score = 72
            reasons.append("Answered by AI-written pandas code (sandboxed)")
        else:
            score = 88
            reasons.append("AI built the query plan; numbers computed by pandas")
    elif eng.startswith("legacy"):
        score = 62
        reasons.append("Legacy engine used (less consistent on follow-ups)")
    else:
        score = 75

    if standalone and _norm(standalone) != _norm(question):
        score -= 6
        reasons.append("Your message was rewritten using chat context")

    fuzzy = [n for n in (result.get("scope_notes") or []) if isinstance(n, str) and _FUZZY.search(n)]
    if fuzzy:
        score -= min(14, 7 * len(fuzzy))
        reasons.append("Names auto-matched: " + "; ".join(fuzzy[:2]))

    if "not available" in str(answer or "").casefold():
        score = max(score - 25, 40)
        reasons.append("Requested data/rows were not found in the file")

    fr = result.get("filtered_rows")
    if isinstance(fr, int) and 0 < fr < 3:
        score -= 4
        reasons.append("Very few rows matched")

    score = max(5, min(99, int(score)))
    level = "high" if score >= 85 else "medium" if score >= 65 else "low"
    return {"score": score, "level": level, "reasons": reasons}
