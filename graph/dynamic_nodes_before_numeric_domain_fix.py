from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from services.dynamic_query_service import (
    get_all_dataset_context,
    load_dataset_rows,
)


# ============================================================
# STATE
# ============================================================

class DynamicAgentState(TypedDict, total=False):
    question: str

    dataset_id: Optional[int]
    dataset_type: Optional[str]

    intent: Optional[str]

    datasets: List[Dict[str, Any]]
    dataset: Dict[str, Any]
    schema: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]

    requested_columns: List[str]
    unavailable_columns: List[str]

    lookup_column: Optional[str]
    lookup_value: Optional[str]

    filters: List[Dict[str, Any]]

    group_by: Optional[str]
    aggregate_function: Optional[str]
    aggregate_column: Optional[str]

    owner_column: Optional[str]

    sort_column: Optional[str]
    sort_direction: Optional[str]

    result: Dict[str, Any]
    answer: str
    error: Optional[str]
    export_requested: bool
    export_format: Optional[str]
    export_filename: Optional[str]


# ============================================================
# TEXT HELPERS
# ============================================================

def _normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)

    return text


def _normalize_column(value: Any) -> str:
    text = _normalize_text(value)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _tokens(value: Any) -> set[str]:
    normalized = _normalize_column(value)

    if not normalized:
        return set()

    return set(normalized.split())


def _singular(word: str) -> str:
    word = word.lower().strip()

    # Common irregular/special plural forms
    special_plurals = {
        "names": "name",
        "addresses": "address",
        "classes": "class",
        "statuses": "status",
        "statuses": "status",
        "companies": "company",
        "categories": "category",
        "cities": "city",
        "countries": "country",
        "employees": "employee",
        "students": "student",
        "customers": "customer",
        "products": "product",
        "quantities": "quantity",
        "departments": "department",
        "designations": "designation",
        "salaries": "salary",
        "ages": "age",
        "scores": "score",
        "marks": "mark",
        "prices": "price",
        "amounts": "amount",
        "dates": "date",
        "phones": "phone",
        "numbers": "number",
        "emails": "email",
    }

    if word in special_plurals:
        return special_plurals[word]

    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"

    if word.endswith("ses") and len(word) > 4:
        return word[:-2]

    if word.endswith("xes") and len(word) > 4:
        return word[:-2]

    if word.endswith("zes") and len(word) > 4:
        return word[:-2]

    if word.endswith("ches") and len(word) > 5:
        return word[:-2]

    if word.endswith("shes") and len(word) > 5:
        return word[:-2]

    if word.endswith("s") and len(word) > 2:
        return word[:-1]

    return word


# ============================================================
# FALLBACK SYNONYMS
# ============================================================
#
# These are only fallbacks.
#
# The primary system uses the actual uploaded schema, so new
# columns can work without adding them here.
# ============================================================

COLUMN_SYNONYMS = {
    "name": {
        "name",
        "customer name",
        "party name",
        "party",
        "client",
        "client name",
        "customer",
        "buyer",
        "buyer name",
        "supplier name",
        "vendor name",
    },
    "customer": {
        "customer",
        "customer name",
        "party",
        "party name",
        "client",
        "client name",
        "buyer",
        "buyer name",
    },
    "supplier": {
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "party",
        "party name",
    },
    "product": {
        "product",
        "product name",
        "item",
        "item name",
        "goods",
        "stock item",
        "description",
    },
    "amount": {
        "amount",
        "total",
        "total amount",
        "value",
        "price",
        "sales amount",
        "purchase amount",
        "net amount",
        "grand total",
    },
    "quantity": {
        "quantity",
        "qty",
        "units",
        "unit",
    },
    "date": {
        "date",
        "transaction date",
        "bill date",
        "invoice date",
        "sale date",
        "purchase date",
        "payment date",
    },
    "invoice": {
        "invoice",
        "invoice number",
        "invoice no",
        "invoice id",
        "bill number",
        "bill no",
        "bill id",
    },
    "city": {
        "city",
        "town",
        "location",
    },
    "state": {
        "state",
        "province",
    },
    "payment": {
        "payment",
        "payment mode",
        "payment method",
        "mode",
        "method",
    },
    "employee": {
        "employee",
        "employee name",
        "staff",
        "staff name",
    },
    "employee_id": {
        "employee id",
        "emp id",
        "employee number",
        "emp number",
    },
    "salary": {
        "salary",
        "monthly salary",
        "pay",
        "wage",
        "income",
    },
}


# ============================================================
# DATASET / SCHEMA HELPERS
# ============================================================

def _dataset_columns(
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]] | None = None,
) -> List[str]:
    """
    Return clean source column names for a dataset.

    Handles:
    - ["Product", "Price"]
    - [{"name": "Product", "dtype": "str"}, ...]
    - schema source_column values
    - actual row keys

    Never returns schema dictionaries converted to strings.
    """

    columns: List[str] = []

    # ==========================================================
    # DATASET COLUMNS
    # ==========================================================

    raw_columns = dataset.get("columns")

    if isinstance(raw_columns, list):
        for column in raw_columns:
            if isinstance(column, str):
                value = column.strip()

                if value:
                    columns.append(value)

            elif isinstance(column, dict):
                # Common metadata format:
                # {"name": "Product", "dtype": "str", ...}
                name = (
                    column.get("name")
                    or column.get("column")
                    or column.get("source_column")
                )

                if name:
                    columns.append(str(name).strip())

    elif isinstance(raw_columns, str):
        # Support comma-separated metadata.
        for part in raw_columns.split(","):
            value = part.strip()

            if value:
                columns.append(value)

    # ==========================================================
    # SCHEMA COLUMNS
    # ==========================================================

    for item in schema:
        if not isinstance(item, dict):
            continue

        source_column = item.get("source_column")

        if source_column:
            columns.append(
                str(source_column).strip()
            )

        # Some schema formats may use "name".
        elif item.get("name"):
            columns.append(
                str(item["name"]).strip()
            )

    # ==========================================================
    # ACTUAL ROW COLUMNS
    # ==========================================================

    if rows:
        for row in rows:
            if not isinstance(row, dict):
                continue

            for key in row.keys():
                if key is None:
                    continue

                value = str(key).strip()

                if value:
                    columns.append(value)

    # ==========================================================
    # REMOVE DUPLICATES WHILE PRESERVING ORDER
    # ==========================================================

    result: List[str] = []
    seen = set()

    for column in columns:
        normalized = _normalize_column(column)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(column)

    return result


def _schema_entry(
    column: str,
    schema: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    normalized = _normalize_column(column)

    for item in schema:
        source = item.get("source_column")

        if source and _normalize_column(source) == normalized:
            return item

    return None


def _canonical_name(
    column: str,
    schema: List[Dict[str, Any]],
) -> str:
    item = _schema_entry(column, schema)

    if item:
        canonical = item.get("canonical_column")

        if canonical:
            return str(canonical)

    return ""


def _column_score(
    requested: str,
    actual: str,
    schema: List[Dict[str, Any]],
) -> float:
    requested_norm = _normalize_column(requested)
    actual_norm = _normalize_column(actual)

    if not requested_norm or not actual_norm:
        return 0.0

    # --------------------------------------------------------
    # Exact match
    # --------------------------------------------------------

    if requested_norm == actual_norm:
        return 100.0

    requested_tokens = _tokens(requested_norm)
    actual_tokens = _tokens(actual_norm)

    if not requested_tokens or not actual_tokens:
        return 0.0

    # --------------------------------------------------------
    # Singular/plural normalization
    # --------------------------------------------------------

    requested_singular_tokens = {
        _singular(token)
        for token in requested_tokens
    }

    actual_singular_tokens = {
        _singular(token)
        for token in actual_tokens
    }

    # --------------------------------------------------------
    # IMPORTANT SAFETY CHECK
    #
    # If the request contains multiple meaningful words and
    # the actual column does not contain the important words,
    # do NOT allow fuzzy matching to invent a column.
    #
    # Example:
    #
    # "student email addresses"
    #
    # must NOT match:
    # "Student ID"
    #
    # because "email" is not present in Student ID.
    # --------------------------------------------------------

    stop_words = {
        "the",
        "a",
        "an",
        "all",
        "give",
        "show",
        "get",
        "find",
        "list",
        "display",
        "student",
        "students",
        "employee",
        "employees",
        "customer",
        "customers",
        "record",
        "records",
        "data",
        "information",
        "details",
        "detail",
    }

    meaningful_requested_tokens = {
        _singular(token)
        for token in requested_tokens
        if token not in stop_words
    }

    meaningful_actual_tokens = {
        _singular(token)
        for token in actual_tokens
        if token not in stop_words
    }

    # If there are meaningful requested words, at least one of
    # them must meaningfully match the actual column.
    #
    # This prevents:
    #   email addresses -> Student ID
    #   phone number    -> Student ID
    #   salary          -> Employee Name
    #
    if meaningful_requested_tokens:
        meaningful_overlap = (
            meaningful_requested_tokens
            .intersection(
                meaningful_actual_tokens
            )
        )

        if not meaningful_overlap:
            # Before rejecting completely, check canonical
            # schema and synonyms below.
            canonical_for_actual = _canonical_name(
                actual,
                schema,
            )

            canonical_tokens = set()

            if canonical_for_actual:
                canonical_tokens = {
                    _singular(token)
                    for token in _tokens(
                        _normalize_column(
                            canonical_for_actual
                        )
                    )
                }

            canonical_overlap = (
                meaningful_requested_tokens
                .intersection(canonical_tokens)
            )

            if not canonical_overlap:
                # No meaningful relationship at all.
                #
                # Do not fuzzy-match unrelated columns.
                return 0.0

    score = 0.0

    # --------------------------------------------------------
    # Phrase matching
    # --------------------------------------------------------

    if requested_norm in actual_norm:
        score += 55.0

    if actual_norm in requested_norm:
        score += 45.0

    # --------------------------------------------------------
    # Normal token overlap
    # --------------------------------------------------------

    overlap = requested_tokens.intersection(
        actual_tokens
    )

    if overlap:
        score += len(overlap) * 20.0

    # --------------------------------------------------------
    # Singular/plural token overlap
    # --------------------------------------------------------

    singular_overlap = (
        requested_singular_tokens.intersection(
            actual_singular_tokens
        )
    )

    if singular_overlap:
        score += len(singular_overlap) * 30.0

    # --------------------------------------------------------
    # Strong match when all meaningful requested words
    # match the actual column.
    # --------------------------------------------------------

    if meaningful_requested_tokens and (
        meaningful_requested_tokens
        <= actual_singular_tokens
    ):
        score += 50.0

    # --------------------------------------------------------
    # Canonical schema matching
    # --------------------------------------------------------

    canonical = _canonical_name(
        actual,
        schema,
    )

    if canonical:
        canonical_norm = _normalize_column(
            canonical
        )

        canonical_tokens = _tokens(
            canonical_norm
        )

        canonical_singular_tokens = {
            _singular(token)
            for token in canonical_tokens
        }

        canonical_overlap = (
            requested_tokens.intersection(
                canonical_tokens
            )
        )

        if canonical_overlap:
            score += (
                len(canonical_overlap) * 35.0
            )

        canonical_singular_overlap = (
            requested_singular_tokens.intersection(
                canonical_singular_tokens
            )
        )

        if canonical_singular_overlap:
            score += (
                len(canonical_singular_overlap)
                * 35.0
            )

        if requested_norm == canonical_norm:
            score += 80.0

    # --------------------------------------------------------
    # Generic synonym fallback
    # --------------------------------------------------------

    for canonical_key, synonyms in COLUMN_SYNONYMS.items():

        normalized_synonyms = {
            _normalize_column(value)
            for value in synonyms
        }

        singular_synonyms = {
            " ".join(
                _singular(token)
                for token in _tokens(value)
            )
            for value in normalized_synonyms
        }

        canonical_key_norm = _normalize_column(
            canonical_key
        )

        canonical_key_singular = " ".join(
            _singular(token)
            for token in _tokens(
                canonical_key_norm
            )
        )

        requested_singular = " ".join(
            _singular(token)
            for token in requested_tokens
        )

        actual_singular = " ".join(
            _singular(token)
            for token in actual_tokens
        )

        if requested_norm == canonical_key_norm:
            if actual_norm in normalized_synonyms:
                score += 90.0

        if requested_singular == canonical_key_singular:
            if actual_singular in singular_synonyms:
                score += 90.0

        if requested_norm in normalized_synonyms:
            if actual_singular == canonical_key_singular:
                score += 80.0

    return score


def _resolve_column(
    requested: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]] | None = None,
) -> Optional[str]:
    if not requested:
        return None

    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    requested_norm = _normalize_column(
        requested
    )

    if not requested_norm:
        return None

    # --------------------------------------------------------
    # Exact source column
    # --------------------------------------------------------

    for column in columns:
        if (
            _normalize_column(column)
            == requested_norm
        ):
            return column

    # --------------------------------------------------------
    # Singular/plural exact source column
    #
    # student names -> Student Name
    # products -> Product
    # customers -> Customer
    # --------------------------------------------------------

    requested_singular = " ".join(
        _singular(token)
        for token in _tokens(requested_norm)
    )

    for column in columns:
        actual_norm = _normalize_column(column)

        actual_singular = " ".join(
            _singular(token)
            for token in _tokens(actual_norm)
        )

        if (
            requested_singular
            and requested_singular
            == actual_singular
        ):
            return column

    # --------------------------------------------------------
    # Exact canonical column
    # --------------------------------------------------------

    for item in schema:
        canonical = item.get(
            "canonical_column"
        )

        if (
            canonical
            and _normalize_column(canonical)
            == requested_norm
        ):
            source = item.get(
                "source_column"
            )

            if source:
                return source

    # --------------------------------------------------------
    # Singular/plural canonical match
    # --------------------------------------------------------

    for item in schema:
        canonical = item.get(
            "canonical_column"
        )

        source = item.get(
            "source_column"
        )

        if not canonical or not source:
            continue

        canonical_singular = " ".join(
            _singular(token)
            for token in _tokens(
                canonical
            )
        )

        if (
            requested_singular
            and requested_singular
            == canonical_singular
        ):
            return source

    # --------------------------------------------------------
    # Scored matching
    # --------------------------------------------------------

    best_column = None
    best_score = 0.0

    for column in columns:
        score = _column_score(
            requested,
            column,
            schema,
        )

        if score > best_score:
            best_score = score
            best_column = column

    if best_score >= 35:
        return best_column

    return None


def _find_date_column(
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[str]:
    # Prefer schema-detected date columns.
    for item in schema:
        data_type = _normalize_text(item.get("data_type"))
        canonical = _normalize_text(item.get("canonical_column"))

        if data_type == "date" or "date" in canonical:
            source = item.get("source_column")

            if source:
                return source

    # Fallback: inspect column names.
    columns = _dataset_columns(dataset, schema, rows)

    for column in columns:
        normalized = _normalize_column(column)

        if any(
            token in normalized
            for token in (
                "date",
                "bill date",
                "invoice date",
                "transaction date",
                "payment date",
            )
        ):
            return column

    return None


# ============================================================
# VALUE HELPERS
# ============================================================

def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    text = (
        text.replace(",", "")
        .replace("â‚¹", "")
        .replace("$", "")
        .replace("â‚¬", "")
        .replace("Â£", "")
        .replace("Ã¢â€šÂ¹", "")
    )

    text = re.sub(r"[^\d.\-]", "", text)

    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    if not text:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)

        return parsed
    except ValueError:
        return None


def _format_number(value: Any) -> Any:
    if isinstance(value, float):
        if value.is_integer():
            return int(value)

        return round(value, 2)

    return value


def _clean_result_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        str(key): value
        for key, value in row.items()
        if not str(key).startswith("_")
    }


# ============================================================
# QUERY VALUE MATCHING
# ============================================================

def _values_equal(left: Any, right: Any) -> bool:
    left_number = _to_number(left)
    right_number = _to_number(right)

    if left_number is not None and right_number is not None:
        return abs(left_number - right_number) < 0.000001

    return _normalize_text(left) == _normalize_text(right)


def _contains_value(value: Any, search: str) -> bool:
    return _normalize_text(search) in _normalize_text(value)


# ============================================================
# QUERY PARSING
# ============================================================

def _extract_requested_columns(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> tuple[List[str], List[str]]:
    """
    Extract explicitly requested columns.

    Returns:
        requested_columns
        unavailable_columns

    Important behavior:
    - "show student names" -> Student Name
    - "show student names and marks" -> Student Name, Marks
    - "show all student names" -> Student Name
    - "show all sales" -> all columns
    - "show all sales data" -> all columns
    - "show all student data" -> all columns
    - unknown fields are reported as unavailable
    """

    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    question_norm = _normalize_text(question)

    requested: List[str] = []
    unavailable: List[str] = []

    # ========================================================
    # REMOVE EXPORT INSTRUCTIONS
    # ========================================================

    cleaned_question = re.sub(
        r"\b(?:and\s+)?(?:download|export|save)\b"
        r".*?"
        r"(?:\b(?:as|to|in)\s+)?"
        r"\b(?:csv|xlsx|excel|spreadsheet|pdf|report|file)\b",
        " ",
        question_norm,
        flags=re.IGNORECASE,
    )

    cleaned_question = re.sub(
        r"\b(?:download|export|save)\b.*$",
        " ",
        cleaned_question,
        flags=re.IGNORECASE,
    )

    # ========================================================
    # HELPERS
    # ========================================================

    def is_existing_value(candidate: str) -> bool:
        candidate_norm = _normalize_text(candidate)

        if not candidate_norm:
            return False

        for row in rows:
            for value in row.values():
                if value is None:
                    continue

                value_norm = _normalize_text(
                    str(value)
                )

                if (
                    value_norm
                    and value_norm == candidate_norm
                ):
                    return True

        return False

    def add_unavailable(candidate: str) -> None:
        candidate = candidate.strip()

        if not candidate:
            return

        candidate = re.sub(
            r"\s+",
            " ",
            candidate,
        ).strip()

        candidate = re.sub(
            r"\b(?:show|display|list|give|get|fetch|"
            r"return|only|just|me|the|all)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )

        candidate = re.sub(
            r"\s+",
            " ",
            candidate,
        ).strip()

        if not candidate:
            return

        if candidate.lower() in {
            "all",
            "everything",
            "entire",
            "full",
            "complete",
            "whole",
            "data",
            "records",
            "record",
            "details",
            "detail",
            "information",
            "rows",
            "columns",
            "fields",
        }:
            return

        if candidate not in unavailable:
            unavailable.append(candidate)

    def process_candidate(candidate: str) -> None:
        if not candidate:
            return

        candidate = candidate.strip()

        if not candidate:
            return

        # Remove filter tails.
        candidate = re.split(
            r"\s+(?:where|for|of)\s+",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        # Remove projection words.
        candidate = re.sub(
            r"\b(?:show|display|list|give|get|fetch|"
            r"return|only|just|me|the|all)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )

        candidate = re.sub(
            r"\s+",
            " ",
            candidate,
        ).strip()

        if not candidate:
            return

        if candidate.lower() in {
            "all",
            "everything",
            "entire",
            "full",
            "complete",
            "whole",
            "data",
            "records",
            "record",
            "details",
            "detail",
            "information",
            "rows",
            "columns",
            "fields",
        }:
            return

        # Never treat an actual cell value as a column.
        if is_existing_value(candidate):
            return

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            if resolved not in requested:
                requested.append(resolved)
        else:
            add_unavailable(candidate)

    # ========================================================
    # PROJECTION PATTERNS
    # ========================================================

    projection_patterns = [
        r"\b(?:show|display|list|give|get|fetch|return)"
        r"\s+(?:me\s+)?(.+?)(?:\s+where\s+|\s+for\s+|\s+of\s+|$)",

        r"\b(?:only|just)\s+(.+?)(?:\s+where\s+|\s+for\s+|\s+of\s+|$)",

        r"\b(?:columns?|fields?)\s*[:=]?\s*(.+)$",

        r"\b(?:with|having)\s+(?:only\s+)?(.+)$",
    ]

    expanded_candidates: List[str] = []

    for pattern in projection_patterns:
        matches = re.findall(
            pattern,
            cleaned_question,
            flags=re.IGNORECASE,
        )

        for match in matches:
            if isinstance(match, tuple):
                candidate = match[0]
            else:
                candidate = match

            if not candidate:
                continue

            parts = re.split(
                r"\s*(?:,|\band\b|&)\s*",
                candidate,
                flags=re.IGNORECASE,
            )

            for part in parts:
                part = part.strip()

                if part:
                    expanded_candidates.append(part)

    # ========================================================
    # PROCESS PROJECTION CANDIDATES
    # ========================================================

    for candidate in expanded_candidates:
        process_candidate(candidate)

    # ========================================================
    # STRONG PROJECTION PATTERNS
    # ========================================================

    strong_projection_patterns = [
        r"\b(?:student|students|employee|employees|customer|customers)"
        r"\s+(?:names?|ids?|email(?:s| addresses?)?|"
        r"phones?|numbers?|ages?|marks?|scores?|"
        r"departments?|designations?|salaries?|"
        r"addresses?|cities?|states?|countries?|"
        r"products?|categories?|quantities?|prices?|"
        r"amounts?|dates?)\b"
    ]

    for pattern in strong_projection_patterns:
        matches = re.findall(
            pattern,
            cleaned_question,
            flags=re.IGNORECASE,
        )

        for match in matches:
            if match:
                process_candidate(match)

    # ========================================================
    # EXPLICIT SOURCE COLUMN NAMES
    # ========================================================

    for column in columns:
        column_norm = _normalize_column(column)

        if not column_norm:
            continue

        if re.search(
            rf"\b{re.escape(column_norm)}\b",
            cleaned_question,
            flags=re.IGNORECASE,
        ):
            process_candidate(column)

    # ========================================================
    # ALL-DATA REQUEST
    #
    # These mean "return the complete dataset":
    #
    #   show all sales
    #   show all sales data
    #   show all students
    #   show all student data
    #   show all employees
    #   show all employee records
    #
    # These remain projection requests:
    #
    #   show all student names
    #   give all student names and marks
    # ========================================================

    all_data_request = False

    # --------------------------------------------------------
    # Generic all-data phrase
    # --------------------------------------------------------

    if re.search(
        r"\b(?:all|everything|entire|full|complete|whole)"
        r"\s+"
        r"(?:data|records?|details?|information|rows?|columns?|fields?)"
        r"\s*$",
        cleaned_question,
        flags=re.IGNORECASE,
    ):
        all_data_request = True

    # --------------------------------------------------------
    # "all <domain>"
    # --------------------------------------------------------

    elif re.search(
        r"\b(?:all|everything|entire|full|complete|whole)"
        r"\s+"
        r"(?:student|students|employee|employees|customer|customers|"
        r"sales|sale|products?|inventory|orders?|transactions?)"
        r"\s*$",
        cleaned_question,
        flags=re.IGNORECASE,
    ):
        all_data_request = True

    # --------------------------------------------------------
    # "all <domain> data/details/records"
    # --------------------------------------------------------

    elif re.search(
        r"\b(?:all|everything|entire|full|complete|whole)"
        r"\s+"
        r"(?:student|students|employee|employees|customer|customers|"
        r"sales|sale|products?|inventory|orders?|transactions?)"
        r"\s+"
        r"(?:data|records?|details?|information|rows?|columns?|fields?)"
        r"\s*$",
        cleaned_question,
        flags=re.IGNORECASE,
    ):
        all_data_request = True

    if all_data_request:
        requested = []
        unavailable = []

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    requested = list(
        dict.fromkeys(requested)
    )

    unavailable = list(
        dict.fromkeys(unavailable)
    )

    return requested, unavailable
def _extract_numeric_filters(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Extract numeric filters dynamically from the uploaded dataset.

    Examples:
        marks greater than 80
        age above 20
        salary below 50000
        quantity >= 10
        price between 100 and 500
    """

    filters: List[Dict[str, Any]] = []

    question_norm = _normalize_text(question)

    # ========================================================
    # EXPLICIT COMPARISON
    # ========================================================

    comparison_pattern = re.compile(
        r"(?P<column>[A-Za-z][A-Za-z0-9 _-]{0,50}?)"
        r"\s*"
        r"(?P<operator>"
        r">=|<=|>|<|="
        r"|greater\s+than"
        r"|more\s+than"
        r"|above"
        r"|over"
        r"|less\s+than"
        r"|lower\s+than"
        r"|below"
        r"|under"
        r"|at\s+least"
        r"|at\s+most"
        r")"
        r"\s*"
        r"(?P<value>-?\d+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    operator_map = {
        ">": ">",
        ">=": ">=",
        "<": "<",
        "<=": "<=",
        "=": "=",
        "greater than": ">",
        "more than": ">",
        "above": ">",
        "over": ">",
        "less than": "<",
        "lower than": "<",
        "below": "<",
        "under": "<",
        "at least": ">=",
        "at most": "<=",
    }

    for match in comparison_pattern.finditer(question_norm):
        raw_column = match.group("column").strip()
        raw_operator = match.group("operator").strip().lower()
        raw_value = match.group("value").strip()

        column = _resolve_column(
            raw_column,
            dataset,
            schema,
            rows,
        )

        if not column:
            continue

        numeric_value = _to_number(raw_value)

        if numeric_value is None:
            continue

        operator = operator_map.get(raw_operator)

        if not operator:
            continue

        filters.append(
            {
                "column": column,
                "operator": operator,
                "value": numeric_value,
                "type": "numeric",
            }
        )

    # ========================================================
    # BETWEEN
    # ========================================================

    between_pattern = re.compile(
        r"(?P<column>[A-Za-z][A-Za-z0-9 _-]{0,50}?)"
        r"\s+between\s+"
        r"(?P<low>-?\d+(?:\.\d+)?)"
        r"\s+(?:and|to)\s+"
        r"(?P<high>-?\d+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    for match in between_pattern.finditer(question_norm):
        raw_column = match.group("column").strip()

        column = _resolve_column(
            raw_column,
            dataset,
            schema,
            rows,
        )

        if not column:
            continue

        low = _to_number(match.group("low"))
        high = _to_number(match.group("high"))

        if low is None or high is None:
            continue

        filters.append(
            {
                "column": column,
                "operator": ">=",
                "value": low,
                "type": "numeric",
            }
        )

        filters.append(
            {
                "column": column,
                "operator": "<=",
                "value": high,
                "type": "numeric",
            }
        )

    # ========================================================
    # SIMPLE COLUMN = NUMBER
    # ========================================================

    equals_pattern = re.compile(
        r"(?P<column>[A-Za-z][A-Za-z0-9 _-]{0,50}?)"
        r"\s*=\s*"
        r"(?P<value>-?\d+(?:\.\d+)?)",
        flags=re.IGNORECASE,
    )

    for match in equals_pattern.finditer(question_norm):
        raw_column = match.group("column").strip()

        column = _resolve_column(
            raw_column,
            dataset,
            schema,
            rows,
        )

        if not column:
            continue

        numeric_value = _to_number(
            match.group("value")
        )

        if numeric_value is None:
            continue

        filters.append(
            {
                "column": column,
                "operator": "=",
                "value": numeric_value,
                "type": "numeric",
            }
        )

    return filters


def _extract_categorical_filters(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    filters: List[Dict[str, Any]] = []

    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # "customer = ABC Traders"
    # "city is Indore"
    # "payment mode is Cash"
    # --------------------------------------------------------

    explicit_pattern = re.compile(
        r"(?P<column>[A-Za-z][A-Za-z0-9 _-]{0,50}?)"
        r"\s+(?:is|equals?|=)\s+"
        r"(?P<value>[^,;]+?)"
        r"(?=\s+(?:and|or|where|with|having)\s+|[,;]|$)",
        flags=re.IGNORECASE,
    )

    for match in explicit_pattern.finditer(question):
        raw_column = match.group("column").strip()
        raw_value = match.group("value").strip()

        column = _resolve_column(
            raw_column,
            dataset,
            schema,
            rows,
        )

        if not column:
            continue

        if _to_number(raw_value) is not None:
            continue

        filters.append(
            {
                "column": column,
                "operator": "=",
                "value": raw_value,
                "type": "categorical",
            }
        )

    # --------------------------------------------------------
    # Dynamic matching against actual dataset values
    #
    # Examples:
    #
    # "records for ABC Traders"
    # "show abc"
    # "give details abc"
    # "show laptop"
    #
    # The value is discovered from the uploaded dataset.
    # No customer/product names are hardcoded.
    # --------------------------------------------------------

    columns = _dataset_columns(dataset, schema, rows)

    existing_filter_columns = {
        item.get("column")
        for item in filters
    }

    question_tokens = set(_tokens(question_norm))

    # Words that normally describe the operation rather than
    # being a dataset value.
    ignored_query_words = {
        "show",
        "display",
        "list",
        "give",
        "get",
        "fetch",
        "return",
        "only",
        "just",
        "details",
        "detail",
        "detials",
        "data",
        "record",
        "records",
        "transaction",
        "transactions",
        "invoice",
        "invoices",
        "information",
        "all",
        "every",
        "entire",
        "full",
        "complete",
        "whole",
        "for",
        "of",
        "with",
        "where",
        "having",
        "from",
        "the",
        "and",
        "or",
        "please",
        "me",
        "can",
        "you",
        "want",
        "need",
    }

    # --------------------------------------------------------
    # Build unique values from every column.
    # --------------------------------------------------------

    for column in columns:

        if column in existing_filter_columns:
            continue

        unique_values: List[str] = []
        seen = set()

        for row in rows:
            value = row.get(column)

            if value is None:
                continue

            value_text = str(value).strip()

            if not value_text:
                continue

            normalized = _normalize_text(value_text)

            if normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(value_text)

        # Longest first.
        # This makes "ABC Traders" win over "ABC"
        # when both actually exist in the dataset.
        unique_values.sort(
            key=lambda item: len(_normalize_text(item)),
            reverse=True,
        )

        for value in unique_values[:1000]:

            normalized_value = _normalize_text(value)

            if len(normalized_value) < 2:
                continue

            # Never treat numbers as categorical filters.
            if _to_number(value) is not None:
                continue

            # Never treat the column name itself as a value.
            if normalized_value == _normalize_column(column):
                continue

            value_tokens = set(_tokens(normalized_value))

            if not value_tokens:
                continue

            # ------------------------------------------------
            # Exact full-value match
            # ------------------------------------------------

            if normalized_value in question_norm:
                filters.append(
                    {
                        "column": column,
                        "operator": "=",
                        "value": value,
                        "type": "categorical",
                    }
                )

                break

            # ------------------------------------------------
            # Partial value matching
            #
            # Example:
            #
            # Dataset:
            #     ABC Traders
            #
            # Question:
            #     give only details abc
            #
            # "abc" is a meaningful token from the actual
            # dataset value, so resolve it to ABC Traders.
            # ------------------------------------------------

            meaningful_value_tokens = {
                token
                for token in value_tokens
                if len(token) >= 2
                and token not in ignored_query_words
            }

            if not meaningful_value_tokens:
                continue

            meaningful_question_tokens = {
                token
                for token in question_tokens
                if token not in ignored_query_words
                and len(token) >= 2
            }

            if not meaningful_question_tokens:
                continue

            # Tokens from the dataset value that appear in
            # the user's question.
            matched_tokens = (
                meaningful_value_tokens
                & meaningful_question_tokens
            )

            if not matched_tokens:
                continue

            # ------------------------------------------------
            # Strong partial matching
            #
            # For multi-word values:
            #     ABC Traders
            #
            # Query:
            #     abc
            #
            # One meaningful token is enough when that token
            # uniquely identifies a dataset value.
            # ------------------------------------------------

            if len(meaningful_value_tokens) > 1:

                # Count how many actual dataset values contain
                # the same matched token.
                token_matches = []

                for other_value in unique_values[:1000]:
                    other_normalized = _normalize_text(other_value)
                    other_tokens = {
                        token
                        for token in _tokens(other_normalized)
                        if len(token) >= 2
                        and token not in ignored_query_words
                    }

                    if matched_tokens & other_tokens:
                        token_matches.append(other_value)

                # If the token identifies one actual value,
                # safely use that value.
                if len(token_matches) == 1:
                    filters.append(
                        {
                            "column": column,
                            "operator": "=",
                            "value": value,
                            "type": "categorical",
                        }
                    )

                    break

                # If multiple dataset values contain the token,
                # require all meaningful value tokens.
                if matched_tokens == meaningful_value_tokens:
                    filters.append(
                        {
                            "column": column,
                            "operator": "=",
                            "value": value,
                            "type": "categorical",
                        }
                    )

                    break

            else:
                # Single-token dataset value.
                #
                # Example:
                # Product = Laptop
                # Query = "show laptop"
                if meaningful_value_tokens <= meaningful_question_tokens:
                    filters.append(
                        {
                            "column": column,
                            "operator": "=",
                            "value": value,
                            "type": "categorical",
                        }
                    )

                    break

    # --------------------------------------------------------
    # "product contains laptop"
    # "description containing laptop"
    # --------------------------------------------------------

    contains_pattern = re.compile(
        r"(?P<column>[A-Za-z][A-Za-z0-9 _-]{0,50}?)"
        r"\s+(?:contains?|containing|includes?)\s+"
        r"(?P<value>[^,;]+?)"
        r"(?=\s+(?:and|or|where|with|having)\s+|[,;]|$)",
        flags=re.IGNORECASE,
    )

    for match in contains_pattern.finditer(question):
        raw_column = match.group("column").strip()
        raw_value = match.group("value").strip()

        column = _resolve_column(
            raw_column,
            dataset,
            schema,
            rows,
        )

        if not column:
            continue

        filters.append(
            {
                "column": column,
                "operator": "contains",
                "value": raw_value,
                "type": "categorical",
            }
        )

    return _deduplicate_filters(filters)


def _extract_date_filters(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    filters: List[Dict[str, Any]] = []

    date_column = _find_date_column(
        dataset,
        schema,
        rows,
    )

    if not date_column:
        return filters

    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # Year
    # --------------------------------------------------------

    year_match = re.search(
        r"\b(?:in|for|during|year)\s*(20\d{2})\b",
        question_norm,
    )

    if not year_match:
        year_match = re.search(
            r"\b(20\d{2})\b",
            question_norm,
        )

    if year_match:
        year = int(year_match.group(1))

        filters.append(
            {
                "column": date_column,
                "operator": "year",
                "value": year,
                "type": "date",
            }
        )

    # --------------------------------------------------------
    # Month names
    # --------------------------------------------------------

    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    month_number = None

    for month_name, number in month_names.items():
        if re.search(rf"\b{month_name}\b", question_norm):
            month_number = number
            break

    if month_number:
        filters.append(
            {
                "column": date_column,
                "operator": "month",
                "value": month_number,
                "type": "date",
            }
        )

    # --------------------------------------------------------
    # Exact date
    # --------------------------------------------------------

    exact_date_match = re.search(
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
        question_norm,
    )

    if exact_date_match:
        parsed = _parse_date(exact_date_match.group(1))

        if parsed:
            filters.append(
                {
                    "column": date_column,
                    "operator": "date",
                    "value": parsed.strftime("%Y-%m-%d"),
                    "type": "date",
                }
            )

    return _deduplicate_filters(filters)


def _deduplicate_filters(
    filters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result = []
    seen = set()

    for item in filters:
        key = (
            item.get("column"),
            item.get("operator"),
            str(item.get("value")),
            item.get("type"),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def _extract_group_by(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[str]:
    question_norm = _normalize_text(question)

    patterns = [
        r"\bgroup(?:ed)?\s+by\s+(.+?)(?:\s+and\s+|\s+where\s+|\s+for\s+|$)",
        r"\bby\s+(.+?)(?:\s+and\s+|\s+where\s+|\s+for\s+|$)",
        r"\bper\s+(.+?)(?:\s+and\s+|\s+where\s+|\s+for\s+|$)",
        r"\beach\s+(.+?)(?:\s+and\s+|\s+where\s+|\s+for\s+|$)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            question_norm,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(1).strip()

        candidate = re.sub(
            r"\b(?:count|sum|total|average|avg|mean|max|maximum|min|minimum)\b",
            " ",
            candidate,
        ).strip()

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return resolved

    return None


def _extract_aggregate(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    question_norm = _normalize_text(question)

    function = None

    if re.search(r"\b(?:average|avg|mean)\b", question_norm):
        function = "average"
    elif re.search(r"\b(?:sum|total)\b", question_norm):
        function = "sum"
    elif re.search(r"\b(?:maximum|max|highest)\b", question_norm):
        function = "max"
    elif re.search(r"\b(?:minimum|min|lowest)\b", question_norm):
        function = "min"
    elif re.search(r"\b(?:count|how many|number of)\b", question_norm):
        function = "count"
    elif re.search(r"\bhow much\b", question_norm):
        function = "sum"

    if not function:
        return None, None

    # --------------------------------------------------------
    # Try explicit aggregate column:
    #
    # "total amount"
    # "sum of amount"
    # "average quantity"
    # "highest salary"
    # --------------------------------------------------------

    patterns = [
        r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest)"
        r"\s+(?:of\s+)?(.+?)(?:\s+by\s+|\s+per\s+|\s+where\s+|$)",

        r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest)"
        r"\s+(.+?)(?:\s+by\s+|\s+per\s+|\s+where\s+|$)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            question_norm,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(1).strip()

        candidate = re.sub(
            r"\b(?:the|amount|value|records?|data)\b",
            " ",
            candidate,
        ).strip()

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return function, resolved

    # If no aggregate column was explicitly named, use the
    # dataset's numeric column where appropriate.
    if function != "count":
        numeric_columns = []

        for item in schema:
            data_type = _normalize_text(item.get("data_type"))

            if data_type in {"numeric", "number", "integer", "float"}:
                source = item.get("source_column")

                if source:
                    numeric_columns.append(source)

        if not numeric_columns:
            for column in _dataset_columns(
                dataset,
                schema,
                rows,
            ):
                values = [
                    _to_number(row.get(column))
                    for row in rows[:100]
                ]

                if values and sum(
                    value is not None
                    for value in values
                ) >= max(1, len(values) // 2):
                    numeric_columns.append(column)

        if len(numeric_columns) == 1:
            return function, numeric_columns[0]

        # Prefer amount-like columns.
        for column in numeric_columns:
            normalized = _normalize_column(column)

            if any(
                word in normalized
                for word in (
                    "amount",
                    "total",
                    "salary",
                    "price",
                    "value",
                    "revenue",
                )
            ):
                return function, column

    return function, None


def _detect_intent(
    question: str,
    requested_columns: List[str],
    filters: List[Dict[str, Any]],
    group_by: Optional[str],
    aggregate_function: Optional[str],
) -> str:
    text = _normalize_text(question)

    if group_by and aggregate_function:
        return "group_aggregate"

    if aggregate_function:
        return "aggregate"

    if filters:
        if requested_columns:
            return "filtered_projection"

        return "filter"

    if requested_columns:
        return "projection"

    if re.search(
        r"\b(?:which|who|what)\b",
        text,
    ):
        return "lookup"

    if re.search(
        r"\b(?:how many|count|number of)\b",
        text,
    ):
        return "count"

    return "search"


# ============================================================
# FILTER APPLICATION
# ============================================================

def _apply_single_filter(
    rows: List[Dict[str, Any]],
    filter_item: Dict[str, Any],
) -> List[Dict[str, Any]]:
    column = filter_item.get("column")
    operator = filter_item.get("operator")
    expected = filter_item.get("value")

    if not column:
        return rows

    result = []

    for row in rows:
        actual = row.get(column)

        if operator == "=":
            if _values_equal(actual, expected):
                result.append(row)

        elif operator == "contains":
            if _contains_value(actual, expected):
                result.append(row)

        elif operator in {">", "<", ">=", "<="}:
            actual_number = _to_number(actual)
            expected_number = _to_number(expected)

            if (
                actual_number is None
                or expected_number is None
            ):
                continue

            matched = False

            if operator == ">":
                matched = actual_number > expected_number

            elif operator == "<":
                matched = actual_number < expected_number

            elif operator == ">=":
                matched = actual_number >= expected_number

            elif operator == "<=":
                matched = actual_number <= expected_number

            if matched:
                result.append(row)

        elif operator == "year":
            parsed = _parse_date(actual)

            if parsed and parsed.year == int(expected):
                result.append(row)

        elif operator == "month":
            parsed = _parse_date(actual)

            if parsed and parsed.month == int(expected):
                result.append(row)

        elif operator == "date":
            parsed = _parse_date(actual)

            expected_date = _parse_date(expected)

            if (
                parsed
                and expected_date
                and parsed.date() == expected_date.date()
            ):
                result.append(row)

    return result


def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    result = rows

    for filter_item in filters:
        result = _apply_single_filter(
            result,
            filter_item,
        )

    return result


# ============================================================
# PROJECTION
# ============================================================

def _project_rows(
    rows: List[Dict[str, Any]],
    columns: List[str],
) -> List[Dict[str, Any]]:
    if not columns:
        return [
            _clean_result_row(row)
            for row in rows
        ]

    result = []

    for row in rows:
        projected = {}

        for column in columns:
            if column in row:
                projected[column] = row[column]

        result.append(projected)

    return result


# ============================================================
# AGGREGATION
# ============================================================

def _aggregate_rows(
    rows: List[Dict[str, Any]],
    function: str,
    column: Optional[str],
) -> Dict[str, Any]:
    if function == "count":
        return {
            "operation": "count",
            "count": len(rows),
        }

    if not column:
        return {
            "operation": function,
            "value": None,
            "error": "No numeric column could be identified.",
        }

    numeric_rows = []

    for row in rows:
        number = _to_number(row.get(column))

        if number is not None:
            numeric_rows.append(
                {
                    "row": row,
                    "value": number,
                }
            )

    if not numeric_rows:
        return {
            "operation": function,
            "column": column,
            "value": None,
            "error": f"No numeric values found in '{column}'.",
        }

    numeric_values = [
        item["value"]
        for item in numeric_rows
    ]

    if function == "sum":
        value = sum(numeric_values)

    elif function == "average":
        value = sum(numeric_values) / len(numeric_values)

    elif function == "max":
        value = max(numeric_values)

    elif function == "min":
        value = min(numeric_values)

    else:
        value = None

    result = {
        "operation": function,
        "column": column,
        "value": _format_number(value),
        "values_count": len(numeric_values),
    }

    # --------------------------------------------------------
    # For MIN/MAX, retain the source records that contain
    # the calculated value.
    # --------------------------------------------------------

    if function in {"min", "max"}:
        matching_rows = [
            item["row"]
            for item in numeric_rows
            if item["value"] == value
        ]

        result["rows"] = matching_rows

    return result


def _group_aggregate(
    rows: List[Dict[str, Any]],
    group_column: str,
    function: str,
    aggregate_column: Optional[str],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        value = row.get(group_column)

        key = (
            str(value).strip()
            if value is not None
            else "(blank)"
        )

        groups.setdefault(key, []).append(row)

    result = []

    for group_value, group_rows in groups.items():
        if function == "count":
            result.append(
                {
                    group_column: group_value,
                    "count": len(group_rows),
                }
            )
            continue

        aggregate = _aggregate_rows(
            group_rows,
            function,
            aggregate_column,
        )

        result.append(
            {
                group_column: group_value,
                function: aggregate.get("value"),
            }
        )

    # Highest result first for numeric aggregation.
    result.sort(
        key=lambda item: (
            _to_number(
                item.get(function)
            )
            if function != "count"
            else _to_number(item.get("count"))
        ) or 0,
        reverse=True,
    )

    return result


# ============================================================
# DATASET SCORING
# ============================================================

def _score_dataset(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
) -> float:
    """
    Score a dataset against the user's question.

    Selection priority:

    1. Explicit/exact filename match
    2. Exact source-column match
    3. Exact canonical-column match
    4. Actual row-value match
    5. General column/schema token match
    6. Dataset type match
    7. Filename token match

    Exact source-column matches intentionally receive a very
    strong score. This prevents a query such as:

        "What is the average Price?"

    from selecting a dataset containing only "Total Amount"
    when another dataset contains an actual "Price" column.
    """

    score = 0.0

    question_text = _normalize_text(question)
    question_tokens = _tokens(question)

    columns = _dataset_columns(
        dataset,
        schema,
        None,
    )

    # ==========================================================
    # IGNORED QUERY WORDS
    # ==========================================================

    ignored_query_words = {
        "show",
        "get",
        "give",
        "display",
        "find",
        "search",
        "download",
        "export",
        "save",
        "data",
        "records",
        "record",
        "details",
        "detail",
        "information",
        "info",
        "file",
        "csv",
        "xlsx",
        "excel",
        "spreadsheet",
        "pdf",
        "report",
        "all",
        "as",
        "the",
        "for",
        "where",
        "with",
        "of",
        "and",
        "or",
        "to",
        "from",
        "is",
        "are",
        "was",
        "were",
        "what",
        "which",
        "who",
        "how",
        "many",
        "much",
        "average",
        "avg",
        "mean",
        "sum",
        "total",
        "maximum",
        "max",
        "highest",
        "minimum",
        "min",
        "lowest",
        "greater",
        "less",
        "than",
        "equal",
        "equals",
        "over",
        "under",
        "between",
    }

    meaningful_tokens = {
        token
        for token in question_tokens
        if token not in ignored_query_words
        and len(token) >= 2
    }

    # ==========================================================
    # 1. FILENAME MATCH
    # ==========================================================

    filename = _normalize_text(
        dataset.get("original_filename")
    )

    if filename:
        filename_without_extension = re.sub(
            r"\.(csv|xlsx|xls)$",
            "",
            filename,
            flags=re.IGNORECASE,
        )

        filename_tokens = _tokens(
            filename_without_extension
        )

        filename_overlap = question_tokens.intersection(
            filename_tokens
        )

        score += len(filename_overlap) * 6

        if filename_without_extension in question_text:
            score += 40

    # ==========================================================
    # 2. EXACT SOURCE COLUMN MATCH
    # ==========================================================

    exact_source_columns = []

    for column in columns:
        column_text = _normalize_text(column)

        if not column_text:
            continue

        # Exact phrase match.
        if re.search(
            rf"\b{re.escape(column_text)}\b",
            question_text,
        ):
            exact_source_columns.append(column)

            # Very strong signal.
            score += 40

    # ==========================================================
    # 3. EXACT CANONICAL COLUMN MATCH
    # ==========================================================

    for column in columns:
        canonical = _canonical_name(
            column,
            schema,
        )

        if not canonical:
            continue

        canonical_text = _normalize_text(
            canonical
        )

        if not canonical_text:
            continue

        if re.search(
            rf"\b{re.escape(canonical_text)}\b",
            question_text,
        ):
            score += 20

    # ==========================================================
    # 4. GENERAL COLUMN / SCHEMA TOKEN MATCH
    # ==========================================================

    for column in columns:
        column_text = _normalize_text(column)
        column_tokens = _tokens(column)

        if not column_text:
            continue

        overlap = question_tokens.intersection(
            column_tokens
        )

        score += len(overlap) * 5

        canonical = _canonical_name(
            column,
            schema,
        )

        if canonical:
            canonical_tokens = _tokens(
                canonical
            )

            canonical_overlap = (
                question_tokens.intersection(
                    canonical_tokens
                )
            )

            score += len(canonical_overlap) * 8

    # ==========================================================
    # 5. ACTUAL ROW-VALUE MATCH
    # ==========================================================

    try:
        dataset_id = dataset.get("id")

        if dataset_id is not None:
            candidate_rows = load_dataset_rows(
                int(dataset_id)
            )

            if candidate_rows:
                rows_to_scan = candidate_rows[:5000]

                matched_values = set()

                for row in rows_to_scan:
                    if not isinstance(row, dict):
                        continue

                    if isinstance(
                        row.get("row_data"),
                        dict,
                    ):
                        row_data = row["row_data"]

                    elif isinstance(
                        row.get("data"),
                        dict,
                    ):
                        row_data = row["data"]

                    else:
                        row_data = {
                            key: value
                            for key, value in row.items()
                            if key not in {
                                "id",
                                "dataset_id",
                                "row_number",
                                "created_at",
                                "row_data_json",
                            }
                        }

                    for value in row_data.values():
                        if value is None:
                            continue

                        value_text = _normalize_text(
                            str(value)
                        )

                        if not value_text:
                            continue

                        matched_values.add(
                            value_text
                        )

                        value_tokens = _tokens(
                            value_text
                        )

                        overlap = (
                            meaningful_tokens.intersection(
                                value_tokens
                            )
                        )

                        # Actual data-value match.
                        score += (
                            len(overlap) * 12
                        )

                        # Exact value/phrase match.
                        if (
                            value_text in question_text
                            and len(value_text) >= 2
                        ):
                            score += 30

                actual_value_tokens = set()

                for value in matched_values:
                    actual_value_tokens.update(
                        _tokens(value)
                    )

                actual_matches = (
                    meaningful_tokens.intersection(
                        actual_value_tokens
                    )
                )

                score += len(actual_matches) * 20

    except Exception:
        # Dataset selection must never crash the agent.
        pass

    # ==========================================================
    # 6. DATASET TYPE MATCH
    # ==========================================================

    dataset_type = _normalize_text(
        dataset.get("data_type")
    )

    if dataset_type:
        if dataset_type in question_tokens:
            score += 10

    # ==========================================================
    # 7. DATASET HAS DATA
    # ==========================================================

    try:
        row_count = int(
            dataset.get("row_count", 0)
        )

        if row_count > 0:
            score += 1

    except Exception:
        pass

    return score

# ============================================================
# EXPORT DETECTION
# ============================================================

def _detect_export_request(
    question: str,
) -> tuple[bool, Optional[str]]:
    """
    Detect whether the user wants the result downloaded/exported.

    Supported:
        CSV
        XLSX / Excel
        PDF

    Default download format:
        XLSX
    """

    text = _normalize_text(question)

    export_words = [
        "download",
        "export",
        "save",
        "downloadable",
        "file",
        "report",
    ]

    requested = any(
        word in text
        for word in export_words
    )

    if not requested:
        return False, None

    if re.search(
        r"\b(?:csv|comma separated)\b",
        text,
    ):
        return True, "csv"

    if re.search(
        r"\b(?:xlsx|excel|spreadsheet)\b",
        text,
    ):
        return True, "xlsx"

    if re.search(
        r"\b(?:pdf|report)\b",
        text,
    ):
        return True, "pdf"

    # Natural "download" without specifying format.
    return True, "xlsx"
# ============================================================
# NODE 1 - INTENT DETECTION
# ============================================================

def detect_dynamic_intent(
    state: DynamicAgentState,
) -> DynamicAgentState:
    question = state.get("question", "").strip()

    export_requested, export_format = _detect_export_request(
        question
    )

    text = _normalize_text(question)

    if (
        re.search(
            r"\b(?:group|grouped|per|each)\b",
            text,
        )
        and re.search(
            r"\b(?:sum|total|average|avg|mean|max|maximum|min|minimum|count|how many)\b",
            text,
        )
    ):
        intent = "group_aggregate"

    elif re.search(
        r"\b(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|how much)\b",
        text,
    ):
        intent = "aggregate"

    elif re.search(
        r"(?:>=|<=|>|<|greater than|more than|above|over|less than|below|under|at least|at most)",
        text,
    ):
        intent = "filter"

    elif re.search(
        r"\b(?:show|display|list|give|get|fetch|return|only|just)\b",
        text,
    ):
        intent = "projection"

    elif re.search(
        r"\b(?:how many|count|number of)\b",
        text,
    ):
        intent = "count"

    elif re.search(
        r"\b(?:which|who|what)\b",
        text,
    ):
        intent = "lookup"

    else:
        intent = "search"

    return {
        **state,
        "intent": intent,
        "export_requested": export_requested,
        "export_format": export_format,
    }


# ============================================================
# NODE 2 - DATASET SELECTION
# ============================================================

def select_dynamic_dataset(
    state: DynamicAgentState,
) -> DynamicAgentState:
    question = state.get("question", "").strip()
    requested_dataset_id = state.get("dataset_id")

    datasets = get_all_dataset_context()

    if not datasets:
        return {
            **state,
            "datasets": [],
            "error": "Information is not available in the uploaded data.",
        }

    # --------------------------------------------------------
    # Explicit dataset selection.
    # --------------------------------------------------------

    if requested_dataset_id is not None:
        for item in datasets:
            dataset = item.get("dataset", {})

            try:
                dataset_id = int(
                    dataset.get("id", -1)
                )
                requested_id = int(
                    requested_dataset_id
                )
            except (TypeError, ValueError):
                continue

            if dataset_id == requested_id:
                return {
                    **state,
                    "datasets": datasets,
                    "dataset": dataset,
                    "schema": item.get("schema", []),
                    "dataset_type": dataset.get("data_type"),
                    "dataset_id": dataset.get("id"),
                }

        return {
            **state,
            "datasets": datasets,
            "dataset": {},
            "schema": [],
            "dataset_type": None,
            "dataset_id": None,
            "error": "Information is not available in the uploaded data.",
        }

    # --------------------------------------------------------
    # Automatic dataset selection.
    # --------------------------------------------------------

    scored = []

    for item in datasets:
        dataset = item.get("dataset", {})
        schema = item.get("schema", [])

        score = _score_dataset(
            question,
            dataset,
            schema,
        )

        try:
            dataset_id = int(
                dataset.get("id", 0)
            )
        except (TypeError, ValueError):
            dataset_id = 0

        scored.append(
            (
                score,
                dataset_id,
                item,
            )
        )

    if not scored:
        return {
            **state,
            "datasets": datasets,
            "dataset": {},
            "schema": [],
            "dataset_type": None,
            "dataset_id": None,
            "error": "Information is not available in the uploaded data.",
        }

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    best_score, best_id, best_item = scored[0]

    if best_score <= 0:
        return {
            **state,
            "datasets": datasets,
            "dataset": {},
            "schema": [],
            "dataset_type": None,
            "dataset_id": None,
            "error": "Information is not available in the uploaded data.",
        }

    dataset = best_item.get(
        "dataset",
        {},
    )
    schema = best_item.get(
        "schema",
        [],
    )

    return {
        **state,
        "datasets": datasets,
        "dataset": dataset,
        "schema": schema,
        "dataset_type": dataset.get("data_type"),
        "dataset_id": dataset.get("id"),
    }


# ============================================================
# NODE 3 - LOAD DATA
# ============================================================

def load_dynamic_data(
    state: DynamicAgentState,
) -> DynamicAgentState:
    dataset_id = state.get("dataset_id")

    if dataset_id is None:
        return {
            **state,
            "error": "No dataset was selected.",
        }

    rows = load_dataset_rows(
        int(dataset_id)
    )

    cleaned_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        if isinstance(
            row.get("row_data"),
            dict,
        ):
            cleaned_rows.append(
                row["row_data"]
            )

        elif isinstance(
            row.get("data"),
            dict,
        ):
            cleaned_rows.append(
                row["data"]
            )

        else:
            cleaned_rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if key not in {
                        "id",
                        "dataset_id",
                        "row_number",
                        "created_at",
                        "row_data_json",
                    }
                }
            )

    return {
        **state,
        "rows": cleaned_rows,
    }


# ============================================================
# NODE 4 - EXECUTE QUERY
# ============================================================

def execute_dynamic_query(
    state: DynamicAgentState,
) -> DynamicAgentState:
    question = state.get(
        "question",
        "",
    )
    dataset = state.get(
        "dataset",
        {},
    )
    schema = state.get(
        "schema",
        [],
    )
    rows = state.get(
        "rows",
        [],
    )

    if not rows:
        return {
            **state,
            "result": {
                "rows": [],
                "count": 0,
                "message": "Dataset contains no rows.",
            },
            "filters": [],
            "requested_columns": [],
            "unavailable_columns": [],
        }

    # --------------------------------------------------------
    # Parse requested columns.
    # --------------------------------------------------------

    requested_columns, unavailable_columns = (
        _extract_requested_columns(
            question,
            dataset,
            schema,
            rows,
        )
    )

    # --------------------------------------------------------
    # Parse filters.
    # --------------------------------------------------------

    numeric_filters = _extract_numeric_filters(
        question,
        dataset,
        schema,
        rows,
    )

    categorical_filters = _extract_categorical_filters(
        question,
        dataset,
        schema,
        rows,
    )

    date_filters = _extract_date_filters(
        question,
        dataset,
        schema,
        rows,
    )

    filters = _deduplicate_filters(
        numeric_filters
        + categorical_filters
        + date_filters
    )

    # --------------------------------------------------------
    # Parse grouping and aggregation.
    # --------------------------------------------------------

    group_by = _extract_group_by(
        question,
        dataset,
        schema,
        rows,
    )

    aggregate_function, aggregate_column = (
        _extract_aggregate(
            question,
            dataset,
            schema,
            rows,
        )
    )

    intent = _detect_intent(
        question,
        requested_columns,
        filters,
        group_by,
        aggregate_function,
    )

    # --------------------------------------------------------
    # Apply filters.
    # --------------------------------------------------------

    filtered_rows = _apply_filters(
        rows,
        filters,
    )

    # --------------------------------------------------------
    # Group + aggregate.
    # --------------------------------------------------------

    if group_by and aggregate_function:
        grouped = _group_aggregate(
            filtered_rows,
            group_by,
            aggregate_function,
            aggregate_column,
        )

        result = {
            "operation": "group_aggregate",
            "group_by": group_by,
            "aggregate_function": aggregate_function,
            "aggregate_column": aggregate_column,
            "rows": grouped,
            "count": len(grouped),
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
        }

        return {
            **state,
            "intent": "group_aggregate",
            "requested_columns": requested_columns,
            "unavailable_columns": unavailable_columns,
            "filters": filters,
            "group_by": group_by,
            "aggregate_function": aggregate_function,
            "aggregate_column": aggregate_column,
            "result": result,
        }

    # --------------------------------------------------------
    # Aggregate.
    # --------------------------------------------------------

    if aggregate_function:
        aggregate = _aggregate_rows(
            filtered_rows,
            aggregate_function,
            aggregate_column,
        )

        result = {
            **aggregate,
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
        }

        return {
            **state,
            "intent": "aggregate",
            "requested_columns": requested_columns,
            "unavailable_columns": unavailable_columns,
            "filters": filters,
            "aggregate_function": aggregate_function,
            "aggregate_column": aggregate_column,
            "result": result,
        }

    # --------------------------------------------------------
    # Count.
    # --------------------------------------------------------

    if re.search(
        r"\b(?:how many|count|number of)\b",
        _normalize_text(question),
    ):
        result = {
            "operation": "count",
            "count": len(filtered_rows),
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
            "rows": [],
        }

        return {
            **state,
            "intent": "count",
            "requested_columns": requested_columns,
            "unavailable_columns": unavailable_columns,
            "filters": filters,
            "result": result,
        }

    # --------------------------------------------------------
    # Requested columns that do not exist.
    #
    # IMPORTANT:
    # Never return all rows for an unavailable-only request.
    # --------------------------------------------------------

    if (
        unavailable_columns
        and not requested_columns
    ):
        result = {
            "operation": "unavailable_columns",
            "rows": [],
            "count": 0,
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
            "columns": _dataset_columns(
                dataset,
                schema,
                rows,
            ),
        }

        return {
            **state,
            "intent": intent,
            "requested_columns": requested_columns,
            "unavailable_columns": unavailable_columns,
            "filters": filters,
            "result": result,
        }

    # --------------------------------------------------------
    # Projection / normal search.
    # --------------------------------------------------------

    projected_rows = _project_rows(
        filtered_rows,
        requested_columns,
    )

    result = {
        "operation": (
            "filtered_projection"
            if filters
            else "projection"
            if requested_columns
            else "search"
        ),
        "rows": projected_rows,
        "count": len(projected_rows),
        "source_rows": len(rows),
        "filtered_rows": len(filtered_rows),
        "columns": (
            requested_columns
            if requested_columns
            else _dataset_columns(
                dataset,
                schema,
                rows,
            )
        ),
    }

    return {
        **state,
        "intent": intent,
        "requested_columns": requested_columns,
        "unavailable_columns": unavailable_columns,
        "filters": filters,
        "result": result,
    }


# ============================================================
# ANSWER HELPERS
# ============================================================

def _describe_filter(
    filter_item: Dict[str, Any],
) -> str:
    column = filter_item.get(
        "column"
    )
    operator = filter_item.get(
        "operator"
    )
    value = filter_item.get(
        "value"
    )

    labels = {
        "=": "equals",
        "contains": "contains",
        ">": "greater than",
        "<": "less than",
        ">=": "at least",
        "<=": "at most",
        "year": "year",
        "month": "month",
        "date": "date",
    }

    label = labels.get(
        operator,
        str(operator),
    )

    return (
        f"{column} {label} {value}"
    )


def _format_table(
    rows: List[Dict[str, Any]],
    max_rows: int = 20,
) -> str:
    if not rows:
        return ""

    display_rows = rows[:max_rows]

    columns: List[str] = []

    for row in display_rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)

    if not columns:
        return ""

    header = " | ".join(columns)

    separator = " | ".join(
        "---"
        for _ in columns
    )

    lines = [
        header,
        separator,
    ]

    for row in display_rows:
        values = []

        for column in columns:
            value = row.get(
                column,
                "",
            )

            if value is None:
                value = ""

            values.append(
                str(value)
            )

        lines.append(
            " | ".join(values)
        )

    if len(rows) > max_rows:
        lines.append(
            f"... and {len(rows) - max_rows} more rows"
        )

    return "\n".join(lines)


# ============================================================
# NODE 5 - ANSWER GENERATION
# ============================================================

def generate_dynamic_answer(
    state: DynamicAgentState,
) -> DynamicAgentState:
    question = state.get(
        "question",
        "",
    )

    result = state.get(
        "result",
        {},
    )

    dataset = state.get(
        "dataset",
        {},
    )

    if state.get("error"):
        return {
            **state,
            "answer": state["error"],
        }

    dataset_name = (
        dataset.get("original_filename")
        or dataset.get("filename")
        or "dataset"
    )

    export_requested = state.get(
        "export_requested",
        False,
    )

    export_format = state.get(
        "export_format"
    )

    filters = state.get(
        "filters",
        [],
    )

    unavailable_columns = state.get(
        "unavailable_columns",
        [],
    )

    result_rows = result.get(
        "rows",
        [],
    )

    # --------------------------------------------------------
    # Unavailable columns.
    #
    # This must happen before the normal zero-row handling.
    # --------------------------------------------------------

    if (
        result.get("operation")
        == "unavailable_columns"
    ):
        unavailable_text = ", ".join(
            unavailable_columns
        )

        answer = (
            f"The requested column"
            f"{'' if len(unavailable_columns) == 1 else 's'} "
            f"'{unavailable_text}' "
            f"{'is' if len(unavailable_columns) == 1 else 'are'} "
            f"not available in "
            f"'{dataset_name}'."
        )

        available_columns = result.get(
            "columns",
            [],
        )

        if available_columns:
            answer += (
                "\n\nAvailable columns:\n"
                + "\n".join(
                    f"- {column}"
                    for column in available_columns
                )
            )

        return {
            **state,
            "answer": answer,
        }

    # --------------------------------------------------------
    # No matching records.
    # --------------------------------------------------------

    if (
        result.get("operation")
        in {
            "filter",
            "filtered_projection",
            "search",
            "projection",
        }
        and not result_rows
    ):
        filter_text = ""

        if filters:
            filter_text = (
                "\n\nApplied filters:\n"
                + "\n".join(
                    f"- {_describe_filter(item)}"
                    for item in filters
                )
            )

        answer = (
            f"No matching records were found in "
            f"'{dataset_name}'."
            f"{filter_text}"
        )

        if unavailable_columns:
            answer += (
                "\n\nUnavailable columns: "
                + ", ".join(
                    unavailable_columns
                )
            )

        return {
            **state,
            "answer": answer,
        }

    # --------------------------------------------------------
    # Count.
    # --------------------------------------------------------

    if result.get("operation") == "count":
        count = result.get(
            "count",
            0,
        )

        answer = (
            f"Found {count} record"
            f"{'' if count == 1 else 's'}"
            f" in '{dataset_name}'."
        )

        if filters:
            answer += (
                "\n\nFilters:\n"
                + "\n".join(
                    f"- {_describe_filter(item)}"
                    for item in filters
                )
            )

        return {
            **state,
            "answer": answer,
        }

    # --------------------------------------------------------
    # Aggregate.
    # --------------------------------------------------------

    if result.get("operation") in {
        "sum",
        "average",
        "max",
        "min",
    }:
        function = result.get(
            "operation"
        )

        column = result.get(
            "column"
        )

        value = result.get(
            "value"
        )

        if function in {
            "sum",
            "average",
        }:
            labels = {
                "sum": "Total",
                "average": "Average",
            }

            answer = (
                f"{labels.get(function, function.title())} "
                f"of '{column}' is **{value}**."
            )

        elif function in {
            "max",
            "min",
        }:
            matching_rows = result.get(
                "rows",
                [],
            )

            if matching_rows:
                label = (
                    "highest"
                    if function == "max"
                    else "lowest"
                )

                answer = (
                    f"The record with the {label} "
                    f"'{column}' is **{value}**."
                )

                answer += "\n\n"

                answer += _format_table(
                    matching_rows,
                    max_rows=20,
                )

            else:
                label = (
                    "Maximum"
                    if function == "max"
                    else "Minimum"
                )

                answer = (
                    f"{label} of '{column}' "
                    f"is **{value}**."
                )

        else:
            answer = (
                f"{function.title()} of '{column}' "
                f"is **{value}**."
            )

        if filters:
            answer += (
                "\n\nFilters:\n"
                + "\n".join(
                    f"- {_describe_filter(item)}"
                    for item in filters
                )
            )

        return {
            **state,
            "answer": answer,
        }

    # --------------------------------------------------------
    # Group + aggregate.
    # --------------------------------------------------------

    if result.get(
        "operation"
    ) == "group_aggregate":
        group_by = result.get(
            "group_by"
        )

        function = result.get(
            "aggregate_function"
        )

        aggregate_column = result.get(
            "aggregate_column"
        )

        answer = (
            f"Grouped by **{group_by}**"
        )

        if aggregate_column:
            answer += (
                f" with {function} of "
                f"**{aggregate_column}**."
            )
        else:
            answer += (
                f" with {function}."
            )

        answer += "\n\n"

        answer += _format_table(
            result_rows,
            max_rows=50,
        )

        return {
            **state,
            "answer": answer,
        }

    # --------------------------------------------------------
    # Normal rows.
    # --------------------------------------------------------

    count = result.get(
        "count",
        len(result_rows),
    )

    operation = result.get(
        "operation",
        "search",
    )

    if operation == "projection":
        prefix = (
            f"Showing {count} record"
            f"{'' if count == 1 else 's'} "
            f"from '{dataset_name}'."
        )
    else:
        prefix = (
            f"Found {count} matching record"
            f"{'' if count == 1 else 's'} "
            f"in '{dataset_name}'."
        )

    answer = prefix

    if filters:
        answer += (
            "\n\nFilters:\n"
            + "\n".join(
                f"- {_describe_filter(item)}"
                for item in filters
            )
        )

    if unavailable_columns:
        answer += (
            "\n\nUnavailable columns: "
            + ", ".join(
                unavailable_columns
            )
        )

    if export_requested and result_rows:
        format_label = (
            export_format.upper()
            if export_format
            else "XLSX"
        )

        answer += (
            f"\n\nReady to download "
            f"{len(result_rows)} records "
            f"as {format_label}."
        )

    if result_rows:
        answer += "\n\n"

        answer += _format_table(
            result_rows,
            max_rows=20,
        )

    return {
        **state,
        "answer": answer,
        "result": result,
        "error": None,
    }
