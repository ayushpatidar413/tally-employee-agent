
import re
from functools import lru_cache

from spellchecker import SpellChecker
from rapidfuzz import process, fuzz


@lru_cache(maxsize=1)
def get_spellchecker():
    return SpellChecker(language="en")


BUSINESS_WORDS = {
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
    "partyname", "party", "client", "vendor", "stock",
    "gst", "cgst", "sgst", "igst", "turnover", "billing",
    "profit", "margin", "taxable", "unit", "order",
}


def correct_query_typos(question: str, extra_words=None) -> str:
    """
    Correct common query typos using business vocabulary,
    uploaded schema terms, and fuzzy matching.

    Numbers and punctuation are preserved.
    """
    if not isinstance(question, str) or not question.strip():
        return question

    spell = get_spellchecker()

    protected = set()
    schema_words = set()

    for item in extra_words or []:
        if not isinstance(item, str):
            continue

        protected.add(item.lower())

        for token in re.findall(r"[A-Za-z]+", item):
            token = token.lower()
            protected.add(token)
            schema_words.add(token)

    # Business vocabulary gets priority over arbitrary dictionary words.
    candidates = sorted(BUSINESS_WORDS | schema_words)

    def replace_word(match):
        word = match.group(0)
        lower_word = word.lower()

        # Preserve short words and known schema terms.
        if len(word) < 4 or lower_word in protected:
            return word

        # Preserve known business words exactly.
        if lower_word in BUSINESS_WORDS or lower_word in schema_words:
            return word

        # Correct against business/schema vocabulary first.
        matches = process.extract(
            lower_word,
            candidates,
            scorer=fuzz.ratio,
            limit=3,
        )

        if matches:
            best_word, best_score, _ = matches[0]

            # More conservative for short words, more tolerant
            # for longer misspellings.
            threshold = 80 if len(lower_word) < 7 else 78

            if best_score >= threshold:
                correction = best_word
                if word.isupper():
                    return correction.upper()
                if word[0].isupper():
                    return correction.capitalize()
                return correction

        # Fall back to the English spellchecker only when it offers
        # a plausible correction. Do not blindly pick arbitrary words.
        correction = spell.correction(lower_word)

        if not correction or correction == lower_word:
            return word

        candidates_from_spell = spell.candidates(lower_word) or set()
        if correction not in candidates_from_spell:
            return word

        # Avoid a large, uncertain spelling change.
        if abs(len(correction) - len(lower_word)) > 2:
            return word

        if word.isupper():
            return correction.upper()
        if word[0].isupper():
            return correction.capitalize()

        return correction

    return re.sub(r"[A-Za-z]+", replace_word, question)
