import re
import difflib
from functools import lru_cache

# These libraries improve fuzzy matching when installed, but spelling support
# must not crash the query service if an optional package is absent.
try:
    from spellchecker import SpellChecker
except Exception:
    SpellChecker = None

try:
    from rapidfuzz import process, fuzz
except Exception:
    process = None
    fuzz = None


def _ratio(a, b):
    if fuzz is not None:
        return float(fuzz.ratio(a, b))
    return 100.0 * difflib.SequenceMatcher(None, a, b).ratio()


def _best_match(word, candidates):
    if not candidates:
        return None, 0.0
    if process is not None and fuzz is not None:
        found = process.extract(word, candidates, scorer=fuzz.ratio, limit=2)
        if not found:
            return None, 0.0
        # Prefer a strong unique winner; avoid rewriting a word when two schema
        # terms are almost equally plausible.
        if len(found) > 1 and float(found[0][1]) - float(found[1][1]) < 4:
            return found[0][0], float(found[0][1])
        return found[0][0], float(found[0][1])
    ranked = sorted(((c, _ratio(word, c)) for c in candidates), key=lambda x: x[1], reverse=True)
    if not ranked:
        return None, 0.0
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 4:
        return ranked[0]
    return ranked[0]


def _one_transposition_apart(a, b):
    """True when two strings differ only by one adjacent character swap."""
    if len(a) != len(b):
        return False
    diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return (
        len(diffs) == 2
        and diffs[1] == diffs[0] + 1
        and a[diffs[0]] == b[diffs[1]]
        and a[diffs[1]] == b[diffs[0]]
    )


@lru_cache(maxsize=1)
def get_spellchecker():
    return SpellChecker(language="en") if SpellChecker is not None else None


BUSINESS_WORDS = {
    "party", "parties", "partyname", "monthwise", "monthlies",
    "igst", "sgst", "cgst", "tax", "gst",

    "customer", "customers", "sales", "sale",
    "profit", "profits", "average", "total",
    "invoice", "invoices", "quantity", "product",
    "products", "payment", "payments", "amount",
    "revenue", "expense", "expenses", "employee",
    "employees", "attendance", "category", "monthly",
    "yearly", "weekly", "daily", "supplier",
    "suppliers", "purchase", "purchases", "gst",
    "discount", "balance", "count", "maximum",
    "minimum", "highest", "lowest", "show",
    "find", "list", "report", "summary", "details",
    "date", "month", "year", "day", "week",
    "present", "absent", "leave", "department",
    "tax", "taxes", "value", "price", "cost",
    "paid", "pending", "status", "name", "top",
    "bottom", "increase", "decrease", "compare",
    "between", "latest", "previous", "current",
    "first", "last", "number", "numbered",
    "highest", "lowest", "growth", "trend",
    
}


HINGLISH_WORDS = {
    "konse", "kaunse", "kaun", "kis", "kiska", "kiski", "kiske",
    "ka", "ki", "ke", "mein", "me", "hai", "hain", "tha", "thi",
    "the", "batao", "btao", "dikhao", "kitna", "kitni", "kitne",
    "gir", "rhi", "rahi", "raha", "rh", "ab", "aur", "uska",
    "uski", "uske", "iska", "iski", "iske", "same", "pichhle",
    "mahine", "mahina", "zyada", "jyada", "sabse", "kisne",
    "biki", "bika", "bikri", "munafa", "kitne", "customer",
}

# FOLLOWUP_RESOLVER_V5: valid English / Hinglish words that must never be "corrected"
HINGLISH_WORDS |= {
    "increased", "decreased", "increasing", "decreasing", "increases", "decreases", "growing", "falling",
    "dropped", "declined", "improved", "inme", "inmein", "unme", "unmein", "unka", "unki", "unke", "unko",
    "wahi", "yahi", "baaki", "kharida", "kharidi", "kharide", "bika", "biki", "giri", "gire", "gira",
    "badhe", "badha", "badhi", "ghate", "ghata", "ghati", "pichla", "pichle", "agla", "agle", "dono",
    "sabse", "accha", "achha", "margin", "percentage", "percent", "month", "months", "monthwise",
}


def _split_joined_word(word, vocabulary):
    """Split joined words only when the vocabulary supports a full split."""
    token = word.lower()
    if not token or token in vocabulary:
        return word

    # Dynamic programming: prefer a complete segmentation into known words.
    n = len(token)
    best = [None] * (n + 1)
    best[0] = []

    for i in range(n):
        if best[i] is None:
            continue
        for term in vocabulary:
            if len(term) >= 2 and token.startswith(term, i):
                j = i + len(term)
                candidate = best[i] + [term]
                if best[j] is None or len(candidate) < len(best[j]):
                    best[j] = candidate

    parts = best[n]
    if not parts or len(parts) < 2:
        return word

    # Avoid splitting a token into too many tiny fragments.
    if any(len(part) < 2 for part in parts):
        return word
    return " ".join(parts)


def correct_query_typos(question: str, extra_words=None) -> str:
    """Correct query typos using business terms and actual dataset vocabulary."""
    if not isinstance(question, str) or not question.strip():
        return question

    spell = get_spellchecker()
    phrases = []
    vocabulary = set(BUSINESS_WORDS) | set(HINGLISH_WORDS)
    protected = set(HINGLISH_WORDS)

    for item in extra_words or []:
        if not isinstance(item, str) or not item.strip():
            continue
        phrase = item.strip()
        phrases.append(phrase)
        tokens = re.findall(r"[A-Za-z]+", phrase.lower())
        vocabulary.update(tokens)
        protected.update(tokens)
        joined = "".join(tokens)
        if len(joined) >= 5:
            # Keep joined variants available for matching/splitting.
            vocabulary.add(joined)

    candidates = sorted(vocabulary)

    def restore_case(original, corrected):
        if original.isupper():
            return corrected.upper()
        if original[:1].isupper():
            return corrected[:1].upper() + corrected[1:]
        return corrected

    def replace_word(match):
        word = match.group(0)
        lower = word.lower()

        if len(lower) < 4 or lower in protected or lower in BUSINESS_WORDS or lower in HINGLISH_WORDS:
            return word
        # FOLLOWUP_RESOLVER_V5: a correctly spelled English word is left alone (needs pyspellchecker)
        if spell is not None and lower.isalpha() and spell.known([lower]):
            return word
        if lower in vocabulary:
            return word

        # First, split concatenated schema/business terms.
        split = _split_joined_word(lower, vocabulary)
        if " " in split:
            return restore_case(word, split)

        # Fuzzy match to full entity names, including joined names.
        if phrases and len(lower) >= 6:
            joined_matches = []
            for phrase in phrases:
                normalized = "".join(re.findall(r"[A-Za-z]+", phrase.lower()))
                if len(normalized) >= 5:
                    score = _ratio(lower, normalized)
                    joined_matches.append((score, phrase))
            if joined_matches:
                score, phrase = max(joined_matches, key=lambda x: x[0])
                if score >= (92 if len(lower) < 9 else 90):
                    return restore_case(word, phrase)

        candidate, score = _best_match(lower, candidates)
        if candidate:
            threshold = 88 if len(lower) < 7 else 80
            # Adjacent-key transpositions such as "toatl" -> "total" are
            # common and are not scored well by ordinary character similarity.
            transposition = _one_transposition_apart(lower, candidate.lower())
            if score >= threshold or transposition:
                return restore_case(word, candidate)

        # FOLLOWUP_RESOLVER_V6: English dictionary fallback removed - it rewrote real names
        # (Shalini Sharma -> Sharing Dharma). Domain words are handled by the dataset vocabulary.
        return word

    corrected = re.sub(r"[A-Za-z]+", replace_word, question)

    # Correct whole multi-word entity phrases (e.g. "leathr walet").
    # Accept only a strong match against an actual dataset value.
    for phrase in sorted(phrases, key=len, reverse=True):
        tokens = re.findall(r"[A-Za-z]+", phrase)
        if len(tokens) < 2:
            continue
        pattern = r"\b" + r"[\s_-]+".join(
            re.escape(token) for token in tokens
        ) + r"\b"
        if re.search(pattern, corrected, re.IGNORECASE):
            continue

        # Do not replace the whole question; only fix an entity-shaped phrase.
        entity_pattern = re.compile(
            r"\b([A-Za-z]{3,}(?:[\s_-]+[A-Za-z]{3,}){1,3})\b"
        )
        def replace_entity(m):
            raw = m.group(1)
            compact = "".join(re.findall(r"[A-Za-z]+", raw.lower()))
            target = "".join(tokens).lower()
            if len(compact) < 6:
                return raw
            score = _ratio(compact, target)
            if score >= 90:
                return restore_case(raw, phrase)
            return raw
        corrected = entity_pattern.sub(replace_entity, corrected)

    return corrected
