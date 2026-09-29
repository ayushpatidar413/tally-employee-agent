from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from services.dynamic_query_service import (
    get_all_dataset_context,
    load_dataset_rows,
    load_dataset_column_values,
    check_dataset_has_matching_dates,
    run_sql_aggregate,
    run_sql_distinct_count,
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
        "buyer",
        "buyer name",
        "supplier name",
        "vendor name",
    },
    "customer": {
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

    Priority:
    1. Dataset column metadata
    2. Schema source columns
    3. Actual row keys as a fallback

    Important:
    - Do NOT scan rows when dataset metadata already contains
      column names.
    - This keeps column resolution fast for large datasets.
    """

    columns: List[str] = []

    # ==========================================================
    # 1. DATASET COLUMN METADATA
    # ==========================================================

    raw_columns = dataset.get("columns")

    if isinstance(raw_columns, list):
        for column in raw_columns:
            if isinstance(column, str):
                value = column.strip()

                if value:
                    columns.append(value)

            elif isinstance(column, dict):
                name = (
                    column.get("name")
                    or column.get("column")
                    or column.get("source_column")
                )

                if name:
                    value = str(name).strip()

                    if value:
                        columns.append(value)

    elif isinstance(raw_columns, str):
        for part in raw_columns.split(","):
            value = part.strip()

            if value:
                columns.append(value)

    # ==========================================================
    # 2. SCHEMA COLUMNS
    #
    # Schema lookup is cheap compared with scanning thousands
    # of data rows, so always allow schema columns to supplement
    # dataset metadata.
    # ==========================================================

    for item in schema or []:
        if not isinstance(item, dict):
            continue

        source_column = item.get("source_column")

        if source_column:
            value = str(source_column).strip()

            if value:
                columns.append(value)

        elif item.get("name"):
            value = str(item["name"]).strip()

            if value:
                columns.append(value)

    # ==========================================================
    # 3. FAST PATH
    #
    # If dataset metadata or schema already gave us columns,
    # do NOT scan all rows.
    #
    # Example:
    #   dataset 22 has 26 columns
    #   rows = 8,325
    #
    # We already know the columns, so scanning 8,325 rows is
    # unnecessary.
    # ==========================================================

    if columns:
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

    # ==========================================================
    # 4. FALLBACK TO ACTUAL ROW KEYS
    #
    # This preserves support for datasets where metadata/schema
    # does not contain column information.
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
    # 5. REMOVE DUPLICATES
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

    # --------------------------------------------------------
    # IMPORTANT MULTI-WORD SAFETY CHECK
    #
    # A multi-word request must not be reduced to only one
    # matching word when that changes the meaning.
    #
    # Examples:
    #
    #   "GST rate"   -> must NOT match "GST"
    #   "party type" -> must NOT match "Party Name"
    #   "payment mode" -> must NOT match "Payment"
    #
    # But valid singular/plural requests such as:
    #
    #   "student names" -> "Student Name"
    #   "customers"     -> "Customer"
    #
    # remain supported.
    # --------------------------------------------------------

    if meaningful_requested_tokens:
        meaningful_overlap = (
            meaningful_requested_tokens.intersection(
                meaningful_actual_tokens
            )
        )

        # For multi-word requests, require every meaningful
        # requested concept to be represented.
        if len(meaningful_requested_tokens) > 1:

            all_meaningful_words_match = (
                meaningful_requested_tokens
                <= meaningful_actual_tokens
            )

            if not all_meaningful_words_match:

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

                canonical_match = (
                    meaningful_requested_tokens
                    <= canonical_tokens
                )

                if not canonical_match:
                    return 0.0

        elif not meaningful_overlap:
            # Single meaningful-word requests may still use
            # canonical/synonym matching.
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
    # Common business synonyms
    #
    # These are semantic aliases used by users.
    # They are resolved against the ACTUAL uploaded columns.
    #
    # Examples:
    #   customer -> Party Name
    #   customer name -> Party Name
    #   party -> Party Name
    #   party name -> Party Name
    #   client -> Party Name
    #   buyer -> Party Name
    # --------------------------------------------------------

    synonym_groups = [
        {
            "customer",
            "customer name",
            "party",
            "party name",
            "client",
            "client name",
            "buyer",
            "buyer name",
        },
        {
            "state",
            "states",
            "party state",
            "party states",
            "state name",
            "party state name",
        },
        {
            "product",
            "product name",
            "item",
            "item name",
        },
        {
            "salesperson",
            "sales person",
            "sales executive",
            "sales representative",
            "representative",
        },
        {
            "warehouse",
            "warehouse name",
            "location",
            "store",
            "branch",
        },
        {
            "payment mode",
            "payment method",
            "mode of payment",
            "payment type",
        },
        {
            "invoice",
            "invoice no",
            "invoice number",
            "bill number",
            "bill no",
        },
    ]

    requested_synonym_group = None

    for group in synonym_groups:
        if requested_norm in {
            _normalize_column(item)
            for item in group
        }:
            requested_synonym_group = group
            break

    if requested_synonym_group:
        normalized_group = {
            _normalize_column(item)
            for item in requested_synonym_group
        }

        for column in columns:
            column_text = str(column)

            # Direct synonym match
            column_norm = _normalize_column(
                column_text
            )

            if column_norm in normalized_group:
                return column

            # Support CamelCase uploaded columns.
            #
            # Examples:
            #   PartyName   -> Party Name
            #   CustomerName -> Customer Name
            #   ProductName -> Product Name
            #   InvoiceNo   -> Invoice No
            spaced_column = re.sub(
                r"(?<=[a-z])(?=[A-Z])",
                " ",
                column_text,
            )

            spaced_column_norm = _normalize_column(
                spaced_column
            )

            if spaced_column_norm in normalized_group:
                return column

            # Semantic business synonym matching.
            #
            # Example:
            #   requested = customer
            #   actual    = PartyName
            #
            # Both belong to the same synonym group.
            if (
                spaced_column_norm == "party name"
                and "customer" in normalized_group
            ):
                return column

            if (
                spaced_column_norm == "customer name"
                and "customer" in normalized_group
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
    # --------------------------------------------------------
    # 1. Prefer schema-detected date columns.
    # --------------------------------------------------------

    for item in schema:
        data_type = _normalize_text(
            item.get("data_type")
        )

        canonical = _normalize_text(
            item.get("canonical_column")
        )

        if (
            data_type == "date"
            or "date" in canonical
        ):
            source = item.get("source_column")

            if source:
                return source

    # --------------------------------------------------------
    # 2. Fallback: inspect column names.
    # --------------------------------------------------------

    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

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

    # --------------------------------------------------------
    # 3. Detect month-period columns.
    #
    # Examples:
    #   Month = 2025-01
    #   Month = 2025-08
    #   Billing Month = 2026-09
    #
    # These are intentionally allowed to remain text in the
    # schema because they represent periods rather than full
    # dates.
    # --------------------------------------------------------

    month_column_candidates = []

    for column in columns:
        normalized = _normalize_text(column)

        if (
            normalized == "month"
            or "month" in normalized
        ):
            month_column_candidates.append(column)

    for column in month_column_candidates:
        values = []

        for row in rows[:100]:
            value = row.get(column)

            if value is None:
                continue

            text = str(value).strip()

            if text:
                values.append(text)

        if not values:
            continue

        valid_month_values = 0

        for value in values:
            if re.fullmatch(
                r"\d{4}-\d{2}",
                value,
            ):
                try:
                    datetime.strptime(
                        value,
                        "%Y-%m",
                    )
                    valid_month_values += 1
                except ValueError:
                    continue

        if valid_month_values > 0:
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
        .replace("?", "")
        .replace("$", "")
        .replace("?", "")
        .replace("?", "")
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

    # --------------------------------------------------------
    # FAST PATH
    #
    # Most uploaded business data uses ISO-style dates:
    #
    #   2025-04-01
    #   2025-04-01 00:00:00
    #   2025-04-01T00:00:00
    #   2025-04-01T00:00:00Z
    #
    # datetime.fromisoformat() is much faster than repeatedly
    # calling datetime.strptime() with multiple formats.
    # --------------------------------------------------------

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        if parsed.tzinfo:
            parsed = parsed.replace(
                tzinfo=None
            )

        return parsed

    except ValueError:
        pass

    # --------------------------------------------------------
    # FAST COMMON DATE FORMATS
    # --------------------------------------------------------

    text_length = len(text)

    # YYYY/MM/DD
    if (
        text_length == 10
        and text[4] == "/"
        and text[7] == "/"
    ):
        try:
            return datetime(
                int(text[0:4]),
                int(text[5:7]),
                int(text[8:10]),
            )
        except ValueError:
            return None

    # DD-MM-YYYY
    if (
        text_length == 10
        and text[2] == "-"
        and text[5] == "-"
    ):
        try:
            return datetime(
                int(text[6:10]),
                int(text[3:5]),
                int(text[0:2]),
            )
        except ValueError:
            return None

    # DD/MM/YYYY
    if (
        text_length == 10
        and text[2] == "/"
        and text[5] == "/"
    ):
        try:
            return datetime(
                int(text[6:10]),
                int(text[3:5]),
                int(text[0:2]),
            )
        except ValueError:
            return None

    # YYYY-MM
    if (
        text_length == 7
        and text[4] == "-"
    ):
        try:
            return datetime(
                int(text[0:4]),
                int(text[5:7]),
                1,
            )
        except ValueError:
            return None

    # MM-YYYY
    if (
        text_length == 7
        and text[2] == "-"
    ):
        try:
            return datetime(
                int(text[3:7]),
                int(text[0:2]),
                1,
            )
        except ValueError:
            return None

    # --------------------------------------------------------
    # NAMED-MONTH FORMATS
    #
    # Keep strptime only for formats such as:
    #
    #   01-Apr-2025
    #   01-April-2025
    # --------------------------------------------------------

    if "-" in text:
        try:
            return datetime.strptime(
                text,
                "%d-%b-%Y",
            )
        except ValueError:
            pass

        try:
            return datetime.strptime(
                text,
                "%d-%B-%Y",
            )
        except ValueError:
            pass

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

    This function is intentionally column-first for performance.

    Important behavior preserved:
    - Dynamic source-column detection.
    - Business aliases such as customer -> PartyName.
    - Invoice detail lookup.
    - Explicit projection handling.
    - Student/employee strong projection patterns.
    - Unavailable-column detection.
    - "all sales" / "all students" full-data requests.
    - Numeric row requests such as "100 sales rows".
    """

    # ========================================================
    # DATASET COLUMNS
    # ========================================================

    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    question_norm = _normalize_text(question)

    # ========================================================
    # REMOVE NUMERIC ROW COUNT FROM COLUMN EXTRACTION
    #
    # Example:
    #   Give me 100 sales rows
    #
    # "100 sales" must not become an unavailable column.
    # ========================================================

    column_question = re.sub(
        r"\b\d[\d,]*\s+"
        r"(?:sales?|rows?|records?|transactions?|invoices?|"
        r"purchases?|expenses?|payments?|orders?)\b",
        " ",
        question_norm,
        flags=re.IGNORECASE,
    )

    column_question = re.sub(
        r"\s+",
        " ",
        column_question,
    ).strip()

    # ========================================================
    # FAST NORMALIZED COLUMN LOOKUP
    # ========================================================

    normalized_columns = {}

    for column in columns:
        normalized = _normalize_column(column)

        if normalized:
            normalized_columns[
                normalized
            ] = column

    # ========================================================
    # LAZY VALUE LOOKUP
    #
    # The old implementation scanned every cell for every
    # candidate. That is extremely expensive for large
    # transaction datasets.
    #
    # We now build the value index only if it is actually
    # needed.
    # ========================================================

    value_index = None

    def build_value_index():
        nonlocal value_index

        if value_index is not None:
            return value_index

        value_index = set()

        for row in rows:
            if not isinstance(row, dict):
                continue

            for value in row.values():
                if value is None:
                    continue

                value_norm = _normalize_text(
                    str(value)
                )

                if value_norm:
                    value_index.add(value_norm)

        return value_index

    def is_existing_value(candidate: str) -> bool:
        candidate_norm = _normalize_text(candidate)

        if not candidate_norm:
            return False

        return candidate_norm in build_value_index()

    # ========================================================
    # INVOICE DETAIL QUERY
    # ========================================================

    invoice_detail_match = re.search(
        r"\bINV[-\s]?\d+\b",
        question,
        flags=re.IGNORECASE,
    )

    invoice_detail_query = bool(
        invoice_detail_match
        and re.search(
            r"\b(?:invoice|inv)\b",
            question,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:show|find|get|give|fetch|display|"
            r"details?|information|lookup|look\s+up)\b",
            question,
            flags=re.IGNORECASE,
        )
    )

    if invoice_detail_query:
        return columns, []

    # ========================================================
    # REMOVE EXPORT LANGUAGE
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
    # REQUESTED / UNAVAILABLE
    # ========================================================

    requested: List[str] = []
    unavailable: List[str] = []

    def add_unavailable(candidate: str) -> None:
        candidate = str(candidate).strip()

        if not candidate:
            return

        candidate_norm = _normalize_text(candidate)

        if not candidate_norm:
            return

        if candidate_norm not in {
            _normalize_text(item)
            for item in unavailable
        }:
            unavailable.append(candidate)

    # ========================================================
    # PROCESS ONE CANDIDATE
    # ========================================================

    def process_candidate(candidate: str) -> None:
        if candidate is None:
            return

        candidate = str(candidate).strip()

        if not candidate:
            return

        candidate_norm = _normalize_text(candidate)

        if not candidate_norm:
            return

        # ----------------------------------------------------
        # DOMAIN WORDS
        # ----------------------------------------------------

        domain_words = {
            "sale",
            "sales",
            "student",
            "students",
            "employee",
            "employees",
            "inventory",
            "order",
            "orders",
            "transaction",
            "transactions",
            "invoice",
            "invoices",
            "purchase",
            "purchases",
        }

        # ----------------------------------------------------
        # SALES AS EXPLICIT PROJECTION
        #
        # Example:
        #   Show sales, GST and discount for ABC Traders
        #
        # Here "sales" represents the amount column.
        # ----------------------------------------------------

        if candidate_norm in {
            "sale",
            "sales",
        }:
            explicit_projection_request = bool(
                re.search(
                    r",|\band\b|&",
                    cleaned_question,
                    flags=re.IGNORECASE,
                )
            )

            if explicit_projection_request:
                resolved_sales = _resolve_column(
                    "amount",
                    dataset,
                    schema,
                    rows,
                )

                if resolved_sales:
                    if resolved_sales not in requested:
                        requested.append(
                            resolved_sales
                        )

            return

        if candidate_norm in domain_words:
            return

        # ----------------------------------------------------
        # BUSINESS ALIASES
        #
        # customer / party -> Party Name
        # product / item   -> Product
        # ----------------------------------------------------

        business_aliases = {
            "customer": [
                "party name",
                "customer name",
                "party",
            ],
            "customers": [
                "party name",
                "customer name",
                "party",
            ],
            "party": [
                "party name",
                "party",
            ],
            "parties": [
                "party name",
                "party",
            ],
            "product": [
                "product",
                "item",
                "item name",
            ],
            "products": [
                "product",
                "item",
                "item name",
            ],
            "item": [
                "product",
                "item",
                "item name",
            ],
            "items": [
                "product",
                "item",
                "item name",
            ],
        }

        if candidate_norm in business_aliases:
            for alias in business_aliases[
                candidate_norm
            ]:
                resolved_alias = _resolve_column(
                    alias,
                    dataset,
                    schema,
                    rows,
                )

                if resolved_alias:
                    if resolved_alias not in requested:
                        requested.append(
                            resolved_alias
                        )

                    return

        # ----------------------------------------------------
        # IMPORTANT PERFORMANCE CHANGE
        #
        # Resolve against the actual dataset columns BEFORE
        # scanning cell values.
        #
        # For:
        #   Show GST for April 2025
        #
        # GST/TotalGST is resolved here without scanning rows.
        # ----------------------------------------------------

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            if resolved not in requested:
                requested.append(resolved)

            return

        # ----------------------------------------------------
        # FAST SKIP FOR QUERY / METRIC PHRASES
        #
        # Do not scan every dataset cell for phrases such as:
        #   total sales
        #   total profit
        #   average sales
        #   sales for August 2026
        #
        # These are query language, not actual row values.
        #
        # Real values such as:
        #   ABC Traders
        #   Shalini Sharma
        #   Ladies Watch
        #
        # are still allowed to use the value index.
        # ----------------------------------------------------

        candidate_tokens = [
            _normalize_text(token)
            for token in re.findall(
                r"[A-Za-z0-9]+",
                candidate_norm,
            )
        ]

        candidate_tokens = [
            token
            for token in candidate_tokens
            if token
        ]

        query_only_tokens = {
            "total",
            "sum",
            "average",
            "avg",
            "mean",
            "maximum",
            "max",
            "minimum",
            "min",
            "highest",
            "lowest",
            "sales",
            "sale",
            "revenue",
            "turnover",
            "billing",
            "profit",
            "gst",
            "cgst",
            "sgst",
            "igst",
            "discount",
            "tax",
            "taxable",
            "amount",
            "value",
            "invoice",
            "invoices",
            "payment",
            "payments",
            "summary",
            "wise",
            "show",
            "give",
            "list",
            "display",
            "return",
            "fetch",
        }

        month_tokens = {
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            "jan",
            "feb",
            "mar",
            "apr",
            "jun",
            "jul",
            "aug",
            "sep",
            "sept",
            "oct",
            "nov",
            "dec",
        }

        if candidate_tokens:
            candidate_is_query_phrase = all(
                token in query_only_tokens
                or token in month_tokens
                or (
                    token.isdigit()
                    and len(token) == 4
                )
                for token in candidate_tokens
            )

            if candidate_is_query_phrase:
                return
            
        # ----------------------------------------------------
        # GROUP-BY QUERY PHRASES
        #
        # Examples:
        #   sales by state
        #   sales by payment mode
        #   sales by GST rate
        #   sales by inter-state status
        #
        # These are query instructions, not unavailable
        # columns. Grouping is handled separately by
        # _extract_group_by().
        # ----------------------------------------------------

        if re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b"
            r".*\bby\b",
            candidate_norm,
            flags=re.IGNORECASE,
        ):
            return
        # ----------------------------------------------------
        # ONLY NOW CHECK ACTUAL CELL VALUES
        #
        # This is still required for real row values such as:
        #   ABC Traders
        #   Shalini Sharma
        #   Ladies Watch
        # ----------------------------------------------------

        if is_existing_value(candidate):
            return

        add_unavailable(candidate)

    # ========================================================
    # PROJECTION PATTERNS
    # ========================================================

    projection_patterns = [
        r"\b(?:with|having)\s+(?:only\s+)?(.+)$",

        r"\b(?:show|display|list|give|get|fetch|return)"
        r"\s+(?:me\s+)?(.+?)(?:\s+where\s+|\s+for\s+|\s+of\s+|$)",

        r"\b(?:only|just)\s+(.+?)(?:\s+where\s+|\s+for\s+|\s+of\s+|$)",

        r"\b(?:columns?|fields?)\s*[:=]?\s*(.+)$",
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
                    expanded_candidates.append(
                        part
                    )

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
    # DYNAMIC SOURCE COLUMN DETECTION
    # ========================================================

    question_tokens = {
        _normalize_text(token)
        for token in re.findall(
            r"[A-Za-z0-9]+",
            cleaned_question,
        )
    }

    dynamic_ignored_tokens = {
        "show",
        "display",
        "list",
        "give",
        "get",
        "fetch",
        "return",
        "find",
        "only",
        "just",
        "me",
        "the",
        "all",
        "data",
        "records",
        "record",
        "details",
        "detail",
        "information",
        "info",
        "for",
        "from",
        "where",
        "with",
        "having",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "by",
        "as",
        "is",
        "are",
        "was",
        "were",
        "wise",
        "summary",
        "summaries",
        "total",
        "sum",
        "average",
        "avg",
        "mean",
        "maximum",
        "max",
        "minimum",
        "min",
        "highest",
        "lowest",
        "greater",
        "less",
        "than",
        "equal",
        "equals",
        "between",
        "over",
        "under",
        "month",
        "monthly",
        "year",
        "yearly",
        "day",
        "daily",
        "date",
        "dates",
        "sales",
        "sale",
        "purchase",
        "purchases",
        "invoice",
        "invoices",
        "transaction",
        "transactions",
        "order",
        "orders",
        "student",
        "students",
        "employee",
        "employees",
    }

    dynamic_question_tokens = {
        token
        for token in question_tokens
        if token
        and token not in dynamic_ignored_tokens
        and not (
            token.isdigit()
            and len(token) == 4
        )
    }

    normalized_question_tokens = {
        _singular(token)
        for token in dynamic_question_tokens
    }

    for column in columns:
        column_norm = _normalize_column(column)

        if not column_norm:
            continue

        column_tokens = [
            _normalize_text(token)
            for token in re.findall(
                r"[A-Za-z0-9]+",
                column_norm,
            )
        ]

        column_tokens = [
            token
            for token in column_tokens
            if token
        ]

        if not column_tokens:
            continue

        normalized_column_tokens = {
            _singular(token)
            for token in column_tokens
        }

        overlap = (
            normalized_column_tokens
            .intersection(
                normalized_question_tokens
            )
        )

        # Single-word columns.
        if len(column_tokens) == 1 and overlap:
            process_candidate(column)
            continue

        # Multi-word columns.
        if len(column_tokens) > 1:
            matched_tokens = len(overlap)

            if matched_tokens == len(
                normalized_column_tokens
            ):
                process_candidate(column)

    # ========================================================
    # ALL-DATA REQUEST
    # ========================================================

    all_data_request = False

    if re.search(
        r"\b(?:all|everything|entire|full|complete|whole)"
        r"\s+"
        r"(?:data|records?|details?|information|rows?|columns?|fields?)"
        r"\s*$",
        cleaned_question,
        flags=re.IGNORECASE,
    ):
        all_data_request = True

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
    """
    Extract categorical filters from the user's question.

    Performance rules:
    1. Explicit filters such as:
       - where PaymentMode is UPI
       - customer = ABC Traders
       - city is Indore
       are resolved directly.

    2. Invoice numbers and employee IDs are handled directly.

    3. Dynamic matching against actual dataset values is performed
       only when the question contains a meaningful free-form value.
       Pure metric/date queries skip the expensive dataset scan.

    This preserves dynamic behavior without scanning thousands of
    rows for queries such as:
        Show GST for April 2025
        Show profit for April 2025
        Show total sales
    """

    filters: List[Dict[str, Any]] = []

    question_norm = _normalize_text(question)

    # ============================================================
    # 1. EXPLICIT CATEGORICAL FILTERS
    #
    # Examples:
    #   customer = ABC Traders
    #   city is Indore
    #   payment mode is Cash
    #   where PaymentMode is UPI
    # ============================================================

    explicit_pattern = re.compile(
        r"(?:\bwhere\b|\bwith\b|\bhaving\b|\band\b|\bor\b)"
        r"\s+"
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

    # ============================================================
    # 2. INVOICE NUMBER
    #
    # Examples:
    #   show invoice INV101
    #   details of invoice INV103
    # ============================================================

    invoice_match = re.search(
        r"\bINV[-\s]?\d+\b",
        question,
        flags=re.IGNORECASE,
    )

    if invoice_match:
        invoice_value = invoice_match.group(0).upper()

        invoice_value = re.sub(
            r"[-\s]+",
            "",
            invoice_value,
        )

        invoice_column = _resolve_column(
            "invoice no",
            dataset,
            schema,
            rows,
        )

        if not invoice_column:
            invoice_column = _resolve_column(
                "invoice number",
                dataset,
                schema,
                rows,
            )

        if invoice_column:
            filters.append(
                {
                    "column": invoice_column,
                    "operator": "=",
                    "value": invoice_value,
                    "type": "categorical",
                }
            )

    # ============================================================
    # 3. EMPLOYEE ID
    #
    # Examples:
    #   attendance for EMP001
    #   details for employee EMP001
    # ============================================================

    employee_id_match = re.search(
        r"\bEMP\d+\b",
        question,
        flags=re.IGNORECASE,
    )

    if employee_id_match:
        employee_id = employee_id_match.group(0).upper()

        employee_id_column = _resolve_column(
            "employee id",
            dataset,
            schema,
            rows,
        )

        if employee_id_column:
            filters.append(
                {
                    "column": employee_id_column,
                    "operator": "=",
                    "value": employee_id,
                    "type": "categorical",
                }
            )

    # ============================================================
    # 4. CONTAINS FILTER
    #
    # Examples:
    #   product contains laptop
    #   description containing laptop
    # ============================================================

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

    # ============================================================
    # 5. IF AN EXPLICIT FILTER ALREADY EXISTS, DO NOT PERFORM
    #    EXPENSIVE FREE-FORM VALUE DISCOVERY UNNECESSARILY.
    #
    # Example:
    #   Show GST where PaymentMode is UPI
    #
    # UPI has already been extracted above.
    # ============================================================

    existing_filter_columns = {
        item.get("column")
        for item in filters
        if item.get("column")
    }

    # ============================================================
    # 6. DETERMINE WHETHER FREE-FORM VALUE DISCOVERY IS NEEDED
    # ============================================================

    dynamic_value_question = question_norm

    filter_clause_match = re.search(
        r"\b(?:where|with|having)\b(.+)$",
        question_norm,
        flags=re.IGNORECASE,
    )

    if filter_clause_match:
        dynamic_value_question = (
            filter_clause_match.group(1).strip()
        )

    dynamic_value_question_tokens = set(
        _tokens(dynamic_value_question)
    )

    # ============================================================
    # 7. IGNORE NORMAL QUERY WORDS
    # ============================================================

    ignored_query_words = {
        "show",
        "display",
        "list",
        "give",
        "get",
        "fetch",
        "return",
        "export",
        "only",
        "just",
        "details",
        "detail",
        "detials",
        "data",
        "record",
        "records",
        "row",
        "rows",
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
        "total",
        "sum",
        "average",
        "avg",
        "maximum",
        "max",
        "minimum",
        "min",
        "highest",
        "lowest",
        "top",
        "bottom",
        "sales",
        "sale",
        "revenue",
        "turnover",
        "billing",
        "profit",

        "customer",
        "customers",
        "party",
        "parties",
        "product",
        "products",
        "item",
        "items",
        "category",
        "categories",
        "supplier",
        "suppliers",
        "vendor",
        "vendors",

        "gst",
        "cgst",
        "sgst",
        "igst",
        "discount",
        "quantity",
        "qty",
        "amount",
        "value",
        "tax",
        "taxable",
        "invoicevalue",
        "monthly",
        "month",
        "year",
        "yearly",
        "daily",
        "day",
        "date",
        # Month names are handled by the date-filter parser.
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",

        # Short month names.
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }

    meaningful_question_tokens = {
        token
        for token in dynamic_value_question_tokens
        if len(token) >= 2
        and token not in ignored_query_words
        and not token.isdigit()
    }

    # ============================================================
    # 8. FAST EXIT
    #
    # This is the important performance optimization.
    #
    # For:
    #   Show GST for April 2025
    #
    # meaningful_question_tokens will contain no useful
    # categorical value, so we do NOT scan 8,325 rows.
    # ============================================================

    if not meaningful_question_tokens:
        return _deduplicate_filters(filters)

    # ============================================================
    # 9. GET DATASET COLUMNS ONLY WHEN DYNAMIC MATCHING IS NEEDED
    # ============================================================

    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    # ============================================================
    # 10. DYNAMIC MATCHING AGAINST ACTUAL DATASET VALUES
    #
    # This preserves:
    #   Show sales for Shalini Sharma
    #   Show sales for Ladies Watch
    #   Show ABC
    #   Show laptop
    #
    # No values are hardcoded.
    # ============================================================

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

        # Longest values first.
        unique_values.sort(
            key=lambda item: len(
                _normalize_text(item)
            ),
            reverse=True,
        )

        # Keep existing safety limit.
        unique_values = unique_values[:1000]

        for value in unique_values:

            normalized_value = _normalize_text(value)

            if len(normalized_value) < 2:
                continue

            # Never treat numbers as categorical values.
            if _to_number(value) is not None:
                continue

            # Never treat dates as categorical values.
            if _parse_date(value) is not None:
                continue

            # Never treat the column name as its own value.
            if (
                normalized_value
                == _normalize_column(column)
            ):
                continue

            value_tokens = set(
                _tokens(normalized_value)
            )

            if not value_tokens:
                continue

            meaningful_value_tokens = {
                token
                for token in value_tokens
                if len(token) >= 2
                and token not in ignored_query_words
            }

            if not meaningful_value_tokens:
                continue

            # ====================================================
            # EXACT VALUE MATCH
            # ====================================================

            if normalized_value in dynamic_value_question:
                filters.append(
                    {
                        "column": column,
                        "operator": "=",
                        "value": value,
                        "type": "categorical",
                    }
                )
                break

            # ====================================================
            # PARTIAL TOKEN MATCH
            # ====================================================

            matched_tokens = (
                meaningful_value_tokens
                & meaningful_question_tokens
            )

            if not matched_tokens:
                continue

            # ----------------------------------------------------
            # MULTI-WORD DATASET VALUE
            #
            # Example:
            #   Dataset: ABC Traders
            #   Query:   show abc
            # ----------------------------------------------------

            if len(meaningful_value_tokens) > 1:

                # We only need to perform the expensive
                # uniqueness check when a token actually
                # matched the question.
                token_matches = []

                for other_value in unique_values:
                    other_normalized = _normalize_text(
                        other_value
                    )

                    other_tokens = {
                        token
                        for token in _tokens(
                            other_normalized
                        )
                        if len(token) >= 2
                        and token not in ignored_query_words
                    }

                    if matched_tokens & other_tokens:
                        token_matches.append(
                            other_value
                        )

                        if len(token_matches) > 1:
                            break

                # If the token uniquely identifies this
                # dataset value, use it.
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

                # If multiple values contain the token,
                # require all meaningful tokens.
                if (
                    len(token_matches) > 1
                    and matched_tokens
                    == meaningful_value_tokens
                ):
                    filters.append(
                        {
                            "column": column,
                            "operator": "=",
                            "value": value,
                            "type": "categorical",
                        }
                    )
                    break

            # ----------------------------------------------------
            # SINGLE-WORD DATASET VALUE
            #
            # Example:
            #   Product = Laptop
            #   Query = show laptop
            # ----------------------------------------------------

            else:

                if (
                    meaningful_value_tokens
                    <= meaningful_question_tokens
                ):
                    filters.append(
                        {
                            "column": column,
                            "operator": "=",
                            "value": value,
                            "type": "categorical",
                        }
                    )
                    break

    return _deduplicate_filters(filters)

# ============================================================
# DATE-TO-DATE COMPARISON DETECTION
# ============================================================

def _extract_date_comparison(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detect explicit comparison between two dates.

    Examples:
        Compare sales between 2026-09-10 and 2026-09-13
        Compare sales from 2026-09-10 to 2026-09-13
        Sales on 2026-09-10 vs 2026-09-13

    Returns:
        {
            "column": <real date column>,
            "date_1": "2026-09-10",
            "date_2": "2026-09-13",
        }

    Returns None when the question is not a date-to-date
    comparison query.
    """

    date_column = _find_date_column(
        dataset,
        schema,
        rows,
    )

    if not date_column:
        return None

    question_norm = question
    
    # "from DATE to DATE" is also used for normal date-range
    # filtering. Treat it as a comparison only when the question
    # explicitly contains comparison language.
    comparison_intent = bool(
        re.search(
            r"\b(?:compare|comparison|versus|vs|difference|change|increase|increased|decrease|decreased)\b",
            _normalize_text(question),
        )
    )

    # --------------------------------------------------------
    # Standard comparison:
    #
    # between DATE and DATE
    # from DATE to DATE
    # --------------------------------------------------------

    match = None

    if comparison_intent:
        match = re.search(
            r"\b(?:between|from)\s+"
            r"(\d{4}-\d{1,2}-\d{1,2})\s+"
            r"(?:and|to)\s+"
            r"(\d{4}-\d{1,2}-\d{1,2})\b",
            question_norm,
        )

    # --------------------------------------------------------
    # VS / versus comparison:
    #
    # DATE vs DATE
    # DATE versus DATE
    # --------------------------------------------------------

    if not match:
        match = re.search(
            r"\b"
            r"(\d{4}-\d{1,2}-\d{1,2})"
            r"\s+(?:vs|versus)\s+"
            r"(\d{4}-\d{1,2}-\d{1,2})"
            r"\b",
            question_norm,
        )

    if not match:
        return None

    date_1 = _parse_date(
        match.group(1)
    )

    date_2 = _parse_date(
        match.group(2)
    )

    if not date_1 or not date_2:
        return None

    return {
        "column": date_column,
        "date_1": date_1.strftime("%Y-%m-%d"),
        "date_2": date_2.strftime("%Y-%m-%d"),
    }
# ============================================================
# PERIOD-TO-PERIOD COMPARISON DETECTION
# ============================================================

def _extract_period_comparison(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Detect comparison between two months or two years.

    Examples:
        Compare September 2026 with August 2026
        Compare September sales with August sales
        Compare 2026 sales with 2025 sales
        Show month over month sales growth
        How much did sales increase this month compared to last month?

    Returns:
        {
            "column": "Bill Date",
            "period_type": "month",
            "period_1": "2026-09",
            "period_2": "2026-08",
        }

    or None when no period comparison is detected.
    """

    date_column = _find_date_column(
        dataset,
        schema,
        rows,
    )

    if not date_column:
        return None

    question_norm = _normalize_text(question)

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

    # --------------------------------------------------------
    # Explicit month-to-month comparison
    #
    # Examples:
    #   Compare September 2026 with August 2026
    #   Compare September sales with August sales
    # --------------------------------------------------------

    month_matches = re.findall(
        r"\b("
        r"january|february|march|april|may|june|"
        r"july|august|september|october|november|december"
        r")"
        r"(?:\s+(20\d{2}))?\b",
        question_norm,
    )

    if len(month_matches) >= 2:
        first_month_name, first_year = month_matches[0]
        second_month_name, second_year = month_matches[1]

        first_month = month_names[first_month_name]
        second_month = month_names[second_month_name]

        # If years are explicitly provided, use them.
        if first_year:
            year_1 = int(first_year)
        else:
            year_1 = None

        if second_year:
            year_2 = int(second_year)
        else:
            year_2 = None

        # If one or both years are omitted, infer them from
        # available dataset dates.
        available_dates = []

        for row in rows:
            parsed_date = _parse_date(
                row.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if available_dates:
            latest_date = max(available_dates)

            if year_1 is None:
                year_1 = latest_date.year

            if year_2 is None:
                year_2 = latest_date.year

        if year_1 is not None and year_2 is not None:
            return {
                "column": date_column,
                "period_type": "month",
                "period_1": f"{year_1:04d}-{first_month:02d}",
                "period_2": f"{year_2:04d}-{second_month:02d}",
            }

    # --------------------------------------------------------
    # Explicit year-to-year comparison
    #
    # Examples:
    #   Compare 2026 sales with 2025 sales
    #   Compare 2026 with 2025
    # --------------------------------------------------------

    year_matches = re.findall(
        r"\b(20\d{2})\b",
        question_norm,
    )

    unique_years = []

    for year_text in year_matches:
        year = int(year_text)

        if year not in unique_years:
            unique_years.append(year)

    if len(unique_years) >= 2:
        return {
            "column": date_column,
            "period_type": "year",
            "period_1": str(unique_years[0]),
            "period_2": str(unique_years[1]),
        }

    # --------------------------------------------------------
    # Month-over-month comparison
    #
    # Examples:
    #   Show month over month sales growth
    #   How much did sales increase this month compared to
    #   last month?
    # --------------------------------------------------------

    mom_query = bool(
        re.search(
            r"\bmonth[\s-]+over[\s-]+month\b",
            question_norm,
        )
        or re.search(
            r"\bthis\s+month\b.*\blast\s+month\b",
            question_norm,
        )
        or re.search(
            r"\b(?:this|current)\s+month\b.*"
            r"\b(?:compared|versus|vs|against)\b.*"
            r"\blast\s+month\b",
            question_norm,
        )
    )

    if mom_query:
        available_dates = []

        for row in rows:
            parsed_date = _parse_date(
                row.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if not available_dates:
            return None

        latest_date = max(available_dates)

        current_year = latest_date.year
        current_month = latest_date.month

        if current_month == 1:
            previous_year = current_year - 1
            previous_month = 12
        else:
            previous_year = current_year
            previous_month = current_month - 1

        return {
            "column": date_column,
            "period_type": "month",
            "period_1": (
                f"{current_year:04d}-{current_month:02d}"
            ),
            "period_2": (
                f"{previous_year:04d}-{previous_month:02d}"
            ),
        }

    return None

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

    # ========================================================
    # INVOICE DETAIL QUERY
    #
    # Examples:
    #   show invoice INV102
    #   find invoice INV103
    #   give me details for invoice INV104
    #
    # An invoice lookup should return the complete invoice
    # record rather than only the Invoice No column.
    # ========================================================
    
    

    # --------------------------------------------------------
    # Year
    # --------------------------------------------------------

    # --------------------------------------------------------
    # Year
    # --------------------------------------------------------
    #
    # Do not add a year filter when an exact YYYY-MM-DD
    # date is present. The exact-date filter below should
    # handle that query.
    # --------------------------------------------------------
    
    exact_date_present = bool(
        re.search(
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
            question,
        )
    )

    year_match = None

    if not exact_date_present:
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
    # Date range
    #
    # Examples:
    #   from 2026-08-01 to 2026-08-05
    #   between 2026-08-01 and 2026-08-05
    #
    # Use start/end filters for a date range.
    # --------------------------------------------------------

    date_range_match = re.search(
        r"\b(?:from|between)\s+"
        r"(\d{4}-\d{1,2}-\d{1,2})"
        r"\s+(?:to|and)\s+"
        r"(\d{4}-\d{1,2}-\d{1,2})\b",
        question,
    )

    if date_range_match:
        start_date = _parse_date(
            date_range_match.group(1)
        )
        end_date = _parse_date(
            date_range_match.group(2)
        )

        if start_date and end_date:
            filters.append(
                {
                    "column": date_column,
                    "operator": ">=",
                    "value": start_date.strftime(
                        "%Y-%m-%d"
                    ),
                    "type": "date",
                }
            )

            filters.append(
                {
                    "column": date_column,
                    "operator": "<=",
                    "value": end_date.strftime(
                        "%Y-%m-%d"
                    ),
                    "type": "date",
                }
            )

    # --------------------------------------------------------
    # Exact date
    # --------------------------------------------------------

    exact_date_match = re.search(
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
        question,
    )

    if exact_date_match and not date_range_match:
        parsed = _parse_date(
            exact_date_match.group(1)
        )

        if parsed:
            filters.append(
                {
                    "column": date_column,
                    "operator": "date",
                    "value": parsed.strftime(
                        "%Y-%m-%d"
                    ),
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
# ============================================================
# TEMPORAL GROUPING DETECTION
# ============================================================

def _extract_time_grouping(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """
    Detect day/month/year/quarter based grouping requests.

    Examples:
        Show sales day wise
        Show sales by day
        Show sales month wise
        Show sales by month
        Show sales year wise
        Show sales by year
        Show annual sales trend
        Show quarterly sales trend
        Show sales trend

    Returns:
        {
            "column": <real date/month source column>,
            "period": "day" | "month" | "year" | "quarter"
        }

    Returns None when the question is not a temporal grouping query.
    """

    question_norm = _normalize_text(question)

    date_column = _find_date_column(
        dataset,
        schema,
        rows,
    )

    if not date_column:
        return None

    # --------------------------------------------------------
    # DAY
    # --------------------------------------------------------

    if re.search(
        r"\b(?:day|daily|date)\s*(?:wise|wise)?\b",
        question_norm,
    ):
        return {
            "column": date_column,
            "period": "day",
        }

    # --------------------------------------------------------
    # MONTH
    # --------------------------------------------------------

    if re.search(
        r"\b(?:month|monthly)\s*(?:wise|wise)?\b",
        question_norm,
    ):
        return {
            "column": date_column,
            "period": "month",
        }

    # --------------------------------------------------------
    # QUARTER
    # --------------------------------------------------------

    if re.search(
        r"\b(?:quarter|quarterly)\s*(?:wise|wise)?\b",
        question_norm,
    ):
        return {
            "column": date_column,
            "period": "quarter",
        }

    # --------------------------------------------------------
    # YEAR
    # --------------------------------------------------------

    if re.search(
        r"\b(?:year|yearly|annual)\s*(?:wise|wise)?\b",
        question_norm,
    ):
        return {
            "column": date_column,
            "period": "year",
        }

    # --------------------------------------------------------
    # TREND
    #
    # "Show sales trend" automatically uses monthly grouping
    # unless the user explicitly requested another period.
    # --------------------------------------------------------

    if re.search(
        r"\btrend\b",
        question_norm,
    ):
        return {
            "column": date_column,
            "period": "month",
        }

    return None

def _extract_group_by(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> Optional[str]:
    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # RANKING BY GROUP
    #
    # Examples:
    #   Which customer has highest sales?
    #   Which customer has most sales?
    #   Which product has highest sales?
    # --------------------------------------------------------

    if (
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst)\b",
            question_norm,
        )
    ):
        for candidate in (
            "customer",
            "customers",
            "party",
            "parties",
            "product",
            "products",
            "item",
            "items",
        ):
            if re.search(
                rf"\b{re.escape(candidate)}\b",
                question_norm,
            ):
                resolved = _resolve_column(
                    candidate,
                    dataset,
                    schema,
                    rows,
                )

                if resolved:
                    return resolved

    # --------------------------------------------------------
    # ATTENDANCE STATUS SUMMARY
    # --------------------------------------------------------

    if (
        _normalize_text(
            dataset.get("data_type")
        ) == "attendance"
        and re.search(
            r"\battendance\b",
            question_norm,
        )
        and re.search(
            r"\bstatus\b",
            question_norm,
        )
        and re.search(
            r"\b(?:summary|count|breakdown|distribution)\b",
            question_norm,
        )
    ):
        resolved_status_column = _resolve_column(
            "attendance status",
            dataset,
            schema,
            rows,
        )

        if resolved_status_column:
            return resolved_status_column

    # --------------------------------------------------------
    # DIRECT "BY <COLUMN>" RESOLUTION
    #
    # Examples:
    #   GST by customer
    #   GST by customer name
    #   GST by party
    #   GST by sales person
    #   GST by sales executive
    #   GST by payment method
    #   GST by warehouse
    #
    # Important:
    # Resolve the complete phrase through _resolve_column()
    # BEFORE removing words such as "sales".
    # --------------------------------------------------------

    direct_by_patterns = [
        r"\bby\s+(.+?)(?=\s+(?:where|with|having|for|and|or)\b|$)",
        r"\bgroup(?:ed)?\s+by\s+(.+?)(?=\s+(?:where|with|having|for|and|or)\b|$)",
        r"\bper\s+(.+?)(?=\s+(?:where|with|having|for|and|or)\b|$)",
        r"\beach\s+(.+?)(?=\s+(?:where|with|having|for|and|or)\b|$)",
    ]

    for pattern in direct_by_patterns:
        match = re.search(
            pattern,
            question_norm,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(1).strip()

        if not candidate:
            continue

        # ----------------------------------------------------
        # SPECIAL CASE: GST RATE
        #
        # "by GST rate" must resolve to the GST rate column,
        # even when the dataset also contains a GST amount
        # column.
        # ----------------------------------------------------

        candidate_normalized = _normalize_text(candidate)
        
        # ----------------------------------------------------
        # SPECIAL CASE: INTER-STATE STATUS
        #
        # "by inter-state status" should resolve to the
        # actual InterState source column.
        # ----------------------------------------------------

        if re.search(
            r"\binter\s*[-_]?\s*state(?:\s+status)?\b",
            candidate_normalized,
        ):
            for inter_state_column in (
                "InterState",
                "Inter State",
                "Inter-State",
                "Inter_State",
            ):
                inter_state_match = _resolve_column(
                    inter_state_column,
                    dataset,
                    schema,
                    rows,
                )

                if inter_state_match:
                    return inter_state_match

        if re.search(
            r"\bgst\s+rate\b",
            candidate_normalized,
        ):
            for rate_column in (
                "GST Rate %",
                "GST Rate",
                "GST_Rate",
                "GSTRate",
            ):
                rate_match = _resolve_column(
                    rate_column,
                    dataset,
                    schema,
                    rows,
                )

                if rate_match:
                    return rate_match

        # First try the COMPLETE candidate.
        #
        # This is important for:
        #   sales person
        #   sales executive
        #   customer name
        #   payment method
        #   warehouse name
        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )


        # First try the COMPLETE candidate.
        #
        # This is important for:
        #   sales person
        #   sales executive
        #   customer name
        #   payment method
        #   warehouse name
        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return resolved

        # ----------------------------------------------------
        # If the candidate contains aggregation/filler words,
        # remove them and try again.
        # ----------------------------------------------------

        cleaned_candidate = re.sub(
            r"\b(?:count|sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|sales|sale|bottom)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )

        cleaned_candidate = re.sub(
            r"\b(?:the|amount|value|records?|data)\b",
            " ",
            cleaned_candidate,
            flags=re.IGNORECASE,
        )

        cleaned_candidate = re.sub(
            r"\s+",
            " ",
            cleaned_candidate,
        ).strip()

        if not cleaned_candidate:
            continue

        resolved = _resolve_column(
            cleaned_candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return resolved

    # --------------------------------------------------------
    # "COLUMN WISE" RESOLUTION
    #
    # Examples:
    #   party wise
    #   customer wise
    #   product wise
    #   sales person wise
    # --------------------------------------------------------

    wise_match = re.search(
        r"\b(.+?)\s+wise\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if wise_match:
        candidate = wise_match.group(1).strip()

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return resolved

        cleaned_candidate = re.sub(
            r"\b(?:count|sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|sales|sale)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )

        cleaned_candidate = re.sub(
            r"\b(?:the|amount|value|records?|data)\b",
            " ",
            cleaned_candidate,
            flags=re.IGNORECASE,
        )

        cleaned_candidate = re.sub(
            r"\s+",
            " ",
            cleaned_candidate,
        ).strip()

        if cleaned_candidate:
            resolved = _resolve_column(
                cleaned_candidate,
                dataset,
                schema,
                rows,
            )

            if resolved:
                return resolved

        # --------------------------------------------------------
    # MONTHLY / YEARLY / QUARTERLY TREND
    #
    # Examples:
    #   Show monthly sales trend
    #   Show yearly sales trend
    #   Show annual sales trend
    #   Show quarterly sales trend
    #
    # If the question explicitly asks for a trend and the
    # dataset contains a matching time column, use that column
    # as the grouping column.
    # --------------------------------------------------------

    trend_time_candidates = []

    if re.search(
        r"\b(?:monthly|month\s+wise|month-wise)\b",
        question_norm,
    ):
        trend_time_candidates = [
            "Month",
            "month",
            "Billing Month",
            "Sales Month",
        ]

    elif re.search(
        r"\b(?:yearly|year\s+wise|year-wise|annual)\b",
        question_norm,
    ):
        trend_time_candidates = [
            "Year",
            "year",
            "Financial Year",
            "FY",
        ]

    elif re.search(
        r"\b(?:quarterly|quarter\s+wise|quarter-wise)\b",
        question_norm,
    ):
        trend_time_candidates = [
            "Quarter",
            "quarter",
            "Financial Quarter",
        ]

    if trend_time_candidates:
        for candidate in trend_time_candidates:
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
    """
    Detect aggregation function and the actual source column.

    Important:
    - Works with mapped columns such as Total Amount -> amount.
    - Works with completely unmapped columns such as GST, Discount.
    - Always returns the REAL source column name.
    - Does not require every column to have a canonical mapping.
    """

    question_norm = _normalize_text(question)
    
    columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    # ==========================================================
    # 1. DETECT AGGREGATION FUNCTION
    # ==========================================================

    function: Optional[str] = None
    
    # ----------------------------------------------------------
    # TREND QUERIES
    #
    # A sales/purchase/expense/payment trend normally means
    # summing the relevant monetary metric over the time
    # dimension when no explicit aggregation is provided.
    # ----------------------------------------------------------

    is_trend_query = bool(
        re.search(
            r"\b(?:monthly|month\s+wise|month-wise|"
            r"yearly|year\s+wise|year-wise|annual|"
            r"quarterly|quarter\s+wise|quarter-wise|trend)\b",
            question_norm,
        )
    )
    
    if is_trend_query:
        function = "sum"


    # ----------------------------------------------------------
    # COUNT must be checked before SUM.
    #
    # "total invoices" / "total customers" / "total products"
    # means COUNT, not SUM.
    # ----------------------------------------------------------

    if re.search(
        r"\b(?:count|how many|number of)\b",
        question_norm,
    ):
        function = "count"
    # ==========================================================
    # DISTINCT / UNIQUE VALUE COLUMN DETECTION
    # ==========================================================
    is_distinct_query = bool(
        re.search(
            r"\b(?:unique|distinct)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if is_distinct_query:
        distinct_column = None

        # ----------------------------------------------------------
        # DISTINCT / UNIQUE ENTITY -> ACTUAL SOURCE COLUMN
        # ----------------------------------------------------------
        #
        # Use the existing generic resolver. This keeps the logic
        # independent from the actual uploaded schema.
        #
        # invoices  -> InvoiceNo
        # customers -> PartyName
        # products  -> Product
        # GSTIN     -> GSTIN
        # ----------------------------------------------------------

        distinct_candidate = None

        if re.search(
            r"\b(?:invoice|invoices)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "invoice"

        elif re.search(
            r"\b(?:customer|customers|party|parties|client|buyer)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "customer"

        elif re.search(
            r"\b(?:product|products|item|items)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "product"

        elif re.search(
            r"\bgstin\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "GSTIN"

        elif re.search(
            r"\b(?:payment\s+mode|payment\s+modes|payment\s+method)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "PaymentMode"

        elif re.search(
            r"\b(?:category|categories)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "Category"

        elif re.search(
            r"\b(?:state|states|party\s+state)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            distinct_candidate = "PartyState"

        if distinct_candidate:
            distinct_column = _resolve_column(
                distinct_candidate,
                dataset,
                schema,
                rows,
            )

        # ----------------------------------------------------------
        # FALLBACK: exact uploaded column name
        # ----------------------------------------------------------
        if not distinct_column:
            for column in columns:
                if not column:
                    continue

                column_text = str(column)
                column_norm = _normalize_column(column_text)

                if not column_norm:
                    continue

                if column_norm == _normalize_column(
                    question_norm
                ):
                    distinct_column = column_text
                    break

        if distinct_column:
          return "count", distinct_column
    # InvoiceNo is an identifier, not a numeric measure.
    # "total InvoiceNo" means count of InvoiceNo values.
    if re.search(
        r"\btotal\s+(?:invoice\s*no|invoiceno|invoice\s+number)\b",
        question_norm,
        flags=re.IGNORECASE,
    ):
        function = "count"

        invoice_column = None

        # Resolve InvoiceNo directly from the available schema.
        for schema_item in schema:
            if not isinstance(schema_item, dict):
                continue

            source_column = (
                schema_item.get("source_column")
                or schema_item.get("column")
                or schema_item.get("name")
            )

            if not source_column:
                continue

            normalized_source = _normalize_text(
                str(source_column)
            )

            if normalized_source in {
                "invoiceno",
                "invoice no",
                "invoice number",
            }:
                invoice_column = str(source_column)
                break

        # Fallback to actual row keys.
        if not invoice_column and rows:
            for source_column in rows[0].keys():
                normalized_source = _normalize_text(
                    str(source_column)
                )

                if normalized_source in {
                    "invoiceno",
                    "invoice no",
                    "invoice number",
                }:
                    invoice_column = str(source_column)
                    break

        if invoice_column:
            aggregate_column = invoice_column

    elif re.search(
        r"\btotal\s+(?:invoices?|customers?|products?|"
        r"salespersons?|employees?|transactions?|records?|"
        r"rows?|entries?)\b",
        question_norm,
    ):
        function = "count"

    elif re.search(
        r"\b(?:average|avg|mean)\b",
        question_norm,
    ):
        function = "average"

    elif re.search(
        r"\b(?:sum|total)\b",
        question_norm,
    ):
        function = "sum"

    elif re.search(
        r"\b(?:maximum|max|highest)\b",
        question_norm,
    ):
        # "Which customer/product has the highest profit?"
        # means:
        #   SUM(Profit) per customer/product
        #   then select the highest group.
        #
        # It must NOT calculate MAX(Profit) from a
        # single invoice row.
        if (
            re.search(
                r"\b(?:profit|gst|totalgst|total\s+gst)\b",
                question_norm,
            )
            and re.search(
                r"\b(?:customer|customers|party|parties|product|products|item|items)\b",
                question_norm,
            )
        ):
            function = "sum"
        else:
            function = "max"

    elif re.search(
        r"\b(?:minimum|min|lowest)\b",
        question_norm,
    ):
        # "Which customer/product has the lowest profit?"
        # means:
        #   SUM(Profit) per customer/product
        #   then select the lowest group.
        if (
            re.search(
                r"\b(?:profit|gst|totalgst|total\s+gst)\b",
                question_norm,
            )
            and re.search(
                r"\b(?:customer|customers|party|parties|product|products|item|items)\b",
                question_norm,
            )
        ):
            function = "sum"
        else:
            function = "min"

    # ==========================================================
    # 2. ATTENDANCE STATUS SUMMARY
    # ==========================================================

    if (
        not function
        and _normalize_text(dataset.get("data_type")) == "attendance"
        and re.search(r"\battendance\b", question_norm)
        and re.search(r"\bstatus\b", question_norm)
        and re.search(r"\b(?:summary|breakdown|distribution)\b", question_norm)
    ):
        function = "count"

    # ==========================================================
    # 3. "HOW MUCH" = SUM
    # ==========================================================

    if (
        not function
        and re.search(r"\bhow much\b", question_norm)
    ):
        function = "sum"

    # ==========================================================
    # 4. GET ALL REAL SOURCE COLUMNS
    # ==========================================================

    dataset_columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )
    

    # ==========================================================
    # 5. FIND NUMERIC COLUMNS
    #
    # IMPORTANT:
    # Do NOT stop after finding schema numeric columns.
    #
    # We also inspect actual row values.
    #
    # This allows:
    #
    # GST
    # Discount
    # Tax
    # Freight
    # Shipping Charges
    # Commission
    #
    # etc. to work without hardcoding them.
    # ==========================================================

    numeric_columns: List[str] = []

    # ----------------------------------------------------------
    # 5A. Numeric information from schema
    # ----------------------------------------------------------

    for item in schema:
        source = item.get("source_column")
        data_type = _normalize_text(
            item.get("data_type")
        )

        if (
            source
            and source in dataset_columns
            and data_type in {
                "numeric",
                "number",
                "integer",
                "float",
                "decimal",
            }
        ):
            numeric_columns.append(source)

    # ----------------------------------------------------------
    # 5B. Numeric information from ACTUAL DATA
    #
    # Always inspect rows even if schema already contains
    # numeric columns.
    # ----------------------------------------------------------

    sample_rows = rows[:100]

    for column in dataset_columns:

        if column in numeric_columns:
            continue

        values = []

        for row in sample_rows:
            value = _to_number(
                row.get(column)
            )

            if value is not None:
                values.append(value)

        if not values:
            continue

        # If most available values are numeric,
        # treat this as a numeric source column.
        non_empty_count = sum(
            1
            for row in sample_rows
            if row.get(column) not in (None, "")
        )

        if non_empty_count == 0:
            continue

        numeric_ratio = (
            len(values) / non_empty_count
        )

        if numeric_ratio >= 0.5:
            numeric_columns.append(column)

        # Remove duplicates while preserving source-column names.
    numeric_columns = list(
        dict.fromkeys(numeric_columns)
    )
    
    # ==========================================================
    # EXACT EXPLICIT NUMERIC SOURCE-COLUMN MATCH
    #
    # Handles direct aggregate queries such as:
    #
    #   Show total GST_Rate
    #   Show total DiscountPct
    #   Show total InvoiceTotal
    #   Show total UnitPrice
    #
    # IMPORTANT:
    # This must happen before semantic business aliases such
    # as "GST", "Total GST", etc.
    #
    # Therefore an exact uploaded column name always wins
    # when the user explicitly names that column.
    # ==========================================================

    explicit_aggregate_column_match = bool(
        function
        and re.search(
            r"\b(?:total|sum|average|avg|mean|max|maximum|min|minimum)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if (
        explicit_aggregate_column_match
        and numeric_columns
    ):
        question_compact = re.sub(
            r"\s+",
            "",
            question_norm,
        )

        for column in numeric_columns:
            column_text = _normalize_text(column)

            if not column_text:
                continue

            column_compact = re.sub(
                r"\s+",
                "",
                column_text,
            )

            # Exact source-column match.
            if re.search(
                rf"\b{re.escape(column_text)}\b",
                question_norm,
                flags=re.IGNORECASE,
            ):
                return function, column

            # Space-insensitive exact match.
            #
            # Example:
            # GST_Rate -> gstrate
            # Invoice Total -> invoicetotal
            if (
                column_compact
                and column_compact in question_compact
            ):
                return function, column
    
    # ==========================================================
    # RANKING SALES METRIC PREFERENCE
    #
    # For questions such as:
    #
    #   Which customer has the highest sales?
    #   Which customer has the lowest sales?
    #   Which product has the highest sales?
    #   Which product has the lowest sales?
    #
    # "highest"/"lowest" sets function to max/min earlier,
    # so the normal sales fallback is skipped.
    #
    # Therefore resolve the sales-value column explicitly here.
    #
    # IMPORTANT:
    # This only handles generic sales/revenue ranking.
    # Explicit metrics such as Profit, GST, Taxable Value,
    # Quantity, etc. continue through their existing logic.
    # ==========================================================

    ranking_sales_query = bool(
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
    )

    if ranking_sales_query and numeric_columns:

        ranking_sales_columns = [
            "Invoice Value",
            "InvoiceTotal",
            "Invoice Total",
            "Total Amount",
            "TotalAmount",
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
            "Revenue",
            "Turnover",
            "Taxable Value",
            "TaxableAmount",
        ]

        for preferred in ranking_sales_columns:

            preferred_norm = _normalize_text(
                preferred
            )

            for column in numeric_columns:

                column_norm = _normalize_text(
                    column
                )

                if column_norm == preferred_norm:
                    return function or "sum", column

    # ==========================================================
    # TREND SALES METRIC PREFERENCE
    #
    # For a generic sales trend such as:
    #
    #   Show monthly sales trend
    #   Show yearly sales trend
    #
    # prefer the customer-facing invoice/sales value when
    # the question does not explicitly name another metric.
    #
    # Priority:
    #   Invoice Value
    #   Invoice Total
    #   Total Amount
    #   Sales Amount
    #   Amount
    #
    # Explicit metrics such as GST, Profit, or Taxable Value
    # are still handled by the normal column matching logic.
    # ==========================================================

    if is_trend_query:
        trend_metric_candidates = [
            "Invoice Value",
            "Invoice Total",
            "Total Amount",
            "Sales Amount",
            "Sale Amount",
            "Amount",
        ]

        for candidate in trend_metric_candidates:
            resolved_trend_metric = _resolve_column(
                candidate,
                dataset,
                schema,
                rows,
            )

            if resolved_trend_metric:
                # Only use the default trend metric when the
                # user did not explicitly request another
                # numeric metric.
                explicit_metric_requested = any(
                    re.search(
                        rf"\b{re.escape(_normalize_text(column))}\b",
                        question_norm,
                    )
                    for column in numeric_columns
                    if _normalize_text(column)
                    and _normalize_text(column)
                    not in {
                        "invoices",
                    }
                )

                if not explicit_metric_requested:
                    return function or "sum", resolved_trend_metric

                break

    # ==========================================================
    # 6. DETECT "-WISE"
    # ==========================================================

    has_wise = bool(
    re.search(
        r"\bwise\b",
        question_norm,
      )
    )

    # ==========================================================
    # 7. FOR "-WISE" QUESTIONS
    #
    # Example:
    #
    # salesperson-wise GST
    #
    # -> SUM GST
    #
    # warehouse-wise Discount
    #
    # -> SUM Discount
    # ==========================================================

    if has_wise and numeric_columns:

        # ------------------------------------------------------
        # 7A. Exact source-column match
        # ------------------------------------------------------

        for column in numeric_columns:

            column_text = _normalize_text(
                column
            )

            if not column_text:
                continue

            if re.search(
                rf"\b{re.escape(column_text)}\b",
                question_norm,
            ):
                if not function:
                    function = "sum"

                return function, column

        # ------------------------------------------------------
        # 7B. Token-based source-column match
        #
        # Handles:
        #
        # Total Amount
        # GST
        # Discount
        # Shipping Charges
        # etc.
        # ------------------------------------------------------

        question_tokens = set(
            _tokens(question_norm)
        )

        for column in numeric_columns:

            column_text = _normalize_text(
                column
            )

            column_tokens = set(
                _tokens(column_text)
            )

            if not column_tokens:
                continue

            if column_tokens.issubset(
                question_tokens
            ):
                if not function:
                    function = "sum"

                return function, column
    # ==========================================================
    # 8. "COLUMN BY GROUP" QUESTIONS
    #
    # IMPORTANT:
    # For group queries, the column after "by" is the
    # GROUPING column, not automatically the amount column.
    #
    # Examples:
    #
    #   sales by HSN
    #       -> GROUP BY HSN
    #       -> SUM Invoice Value
    #
    #   sales by Party Type
    #       -> GROUP BY Party Type
    #       -> SUM Invoice Value
    #
    #   taxable amount by GST rate
    #       -> GROUP BY GST Rate
    #       -> SUM Taxable Value
    #
    #   invoice value by GST rate
    #       -> GROUP BY GST Rate
    #       -> SUM Invoice Value
    # ==========================================================

    if (
        not function
        and numeric_columns
        and re.search(r"\bby\b", question_norm)
    ):

        # ------------------------------------------------------
        # Resolve the grouping column first.
        # ------------------------------------------------------

        group_column = _extract_group_by(
            question,
            dataset,
            schema,
            rows,
        )

        # ------------------------------------------------------
        # If a grouping column exists, DO NOT return it as
        # the aggregate column.
        #
        # Instead, continue to the sales/measure logic below.
        # ------------------------------------------------------

        if group_column:
            group_column_norm = _normalize_text(
                group_column
            )

            # --------------------------------------------------
            # Check whether the user explicitly mentioned a
            # numeric measure in the question.
            #
            # Example:
            # taxable amount by GST rate
            # invoice value by GST rate
            # profit by category
            # --------------------------------------------------

            # --------------------------------------------------
            # Explicit business measure aliases.
            #
            # User wording does not always match the uploaded
            # column name exactly.
            #
            # Example:
            #   taxable amount -> Taxable Value
            #   invoice value  -> Invoice Value
            #   gross amount   -> Gross Amount
            # --------------------------------------------------

            explicit_measure_aliases = {
                "taxable amount": (
                    "Taxable Value",
                    "TaxableAmount",
                ),
                "taxable value": (
                    "Taxable Value",
                    "TaxableAmount",
                ),
                "invoice value": (
                    "Invoice Value",
                    "InvoiceTotal",
                ),
                "invoice amount": (
                    "Invoice Value",
                    "InvoiceTotal",
                ),
                "gross amount": (
                    "Gross Amount",
                    "GrossAmount",
                ),
                "discount amount": (
                    "Discount Amt",
                    "DiscountAmt",
                ),
                "discount": (
                    "Discount Amt",
                    "DiscountAmt",
                ),
                "profit": (
                    "Profit",
                ),
                "total gst": (
                    "Total GST",
                    "TotalGST",
                    "GST",
                ),
                "gst amount": (
                    "GST",
                    "Total GST",
                    "TotalGST",
                ),
                "gst": (
                    "GST",
                ),
                "cgst": (
                    "CGST",
                ),
                "sgst": (
                    "SGST",
                ),
                "igst": (
                    "IGST",
                ),
                "quantity": (
                    "Qty Sold",
                    "Qty",
                    "Quantity",
                ),
                "qty": (
                    "Qty Sold",
                    "Qty",
                    "Quantity",
                ),
            }

            # Longest phrase first so:
            # "taxable amount" is checked before "amount".
            explicit_aliases = sorted(
                explicit_measure_aliases.items(),
                key=lambda item: len(item[0]),
                reverse=True,
            )

            for alias, possible_columns in explicit_aliases:

                if not re.search(
                    rf"\b{re.escape(alias)}\b",
                    question_norm,
                ):
                    continue

                for possible_column in possible_columns:

                    possible_norm = _normalize_text(
                        possible_column
                    )

                    for column in numeric_columns:

                        column_norm = _normalize_text(
                            column
                        )

                        # Never use the grouping column itself.
                        if (
                            group_column_norm
                            and column_norm
                            == group_column_norm
                        ):
                            continue

                        if (
                            column_norm
                            == possible_norm
                        ):
                            return "sum", column

            # --------------------------------------------------
            # Exact uploaded-column match.
            # --------------------------------------------------

            for column in numeric_columns:

                column_text = _normalize_text(
                    column
                )

                if not column_text:
                    continue

                # Never use the grouping column itself.
                if (
                    group_column_norm
                    and column_text
                    == group_column_norm
                ):
                    continue

                if re.search(
                    rf"\b{re.escape(column_text)}\b",
                    question_norm,
                ):
                    return "sum", column

                # Space-insensitive comparison.
                question_compact = re.sub(
                    r"\s+",
                    "",
                    question_norm,
                )

                column_compact = re.sub(
                    r"\s+",
                    "",
                    column_text,
                )

                if (
                    column_compact
                    and column_compact
                    in question_compact
                ):
                    return "sum", column

            # --------------------------------------------------
            # No explicit numeric measure was mentioned.
            #
            # If this is a sales/revenue query, select the
            # normal monetary sales column.
            # --------------------------------------------------

            sales_words = {
                "sale",
                "sales",
                "revenue",
                "billing",
                "turnover",
            }

            question_tokens = set(
                _tokens(question_norm)
            )

            if question_tokens.intersection(
                sales_words
            ):

                preferred_sales_columns = [
                    "Invoice Value",
                    "InvoiceTotal",
                    "Total Amount",
                    "TotalAmount",
                    "Gross Amount",
                    "GrossAmount",
                    "Sales Amount",
                    "SalesAmount",
                    "Amount",
                    "Revenue",
                    "Turnover",
                    "Taxable Value",
                    "TaxableAmount",
                ]

                for preferred in preferred_sales_columns:

                    preferred_norm = _normalize_text(
                        preferred
                    )

                    for column in numeric_columns:

                        column_norm = _normalize_text(
                            column
                        )

                        if (
                            column_norm
                            == preferred_norm
                        ):
                            if (
                                column_norm
                                != group_column_norm
                            ):
                                return "sum", column

                # --------------------------------------------------
                # Generic monetary fallback.
                # --------------------------------------------------

                for column in numeric_columns:

                    column_norm = _normalize_text(
                        column
                    )

                    if (
                        column_norm
                        == group_column_norm
                    ):
                        continue

                    if any(
                        word in column_norm
                        for word in (
                            "invoice value",
                            "invoice amount",
                            "total amount",
                            "gross amount",
                            "sales amount",
                            "revenue",
                            "turnover",
                            "amount",
                            "value",
                        )
                    ):
                        return "sum", column

        # ------------------------------------------------------
        # No grouping column was resolved.
        #
        # Preserve the existing behavior for generic
        # "COLUMN by GROUP" queries.
        # ------------------------------------------------------
        else:

            for column in numeric_columns:

                column_text = _normalize_text(
                    column
                )

                if not column_text:
                    continue

                if re.search(
                    rf"\b{re.escape(column_text)}\b",
                    question_norm,
                ):
                    return "sum", column

            question_tokens = set(
                _tokens(question_norm)
            )

            for column in numeric_columns:

                column_text = _normalize_text(
                    column
                )

                column_tokens = set(
                    _tokens(column_text)
                )

                if not column_tokens:
                    continue

                if column_tokens.issubset(
                    question_tokens
                ):
                    return "sum", column  
    
    # ==========================================================
    # EXPLICIT BUSINESS METRIC WITHOUT AGGREGATION WORD
    #
    # Examples:
    #   Show profit
    #   Show profit for April 2025
    #   Show  for April 2025
    #   Show discount for May 2025
    #
    # The user explicitly named a numeric business metric,
    # so the default operation is SUM unless another
    # aggregation function was already detected.
    # ==========================================================

    explicit_metric_aliases = {
        "profit": (
            "Profit",
        ),
        "total gst": (
            "Total GST",
            "TotalGST",
            "GST",
        ),
        "gst amount": (
            "GST",
            "Total GST",
            "TotalGST",
        ),
        "gst": (
            "Total GST",
            "TotalGST",
            "GST",
        ),
        "cgst": (
            "CGST",
        ),
        "sgst": (
            "SGST",
        ),
        "igst": (
            "IGST",
        ),
        "discount amount": (
            "Discount Amt",
            "DiscountAmt",
        ),
        "discount": (
            "Discount Amt",
            "DiscountAmt",
        ),
        "taxable amount": (
            "Taxable Value",
            "TaxableAmount",
        ),
        "taxable value": (
            "Taxable Value",
            "TaxableAmount",
        ),
        "quantity": (
            "Qty Sold",
            "Qty",
            "Quantity",
        ),
        "qty": (
            "Qty Sold",
            "Qty",
            "Quantity",
        ),
    }

    explicit_metric_aliases_sorted = sorted(
        explicit_metric_aliases.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for alias, possible_columns in explicit_metric_aliases_sorted:

        if not re.search(
            rf"\b{re.escape(alias)}\b",
            question_norm,
        ):
            continue

        for possible_column in possible_columns:

            possible_norm = _normalize_text(
                possible_column
            )

            for column in numeric_columns:

                column_norm = _normalize_text(
                    column
                )

                if column_norm == possible_norm:
                    return (
                        function or "sum",
                        column,
                    )

    # ==========================================================
    # 8A. EXPLICIT NUMERIC COLUMN MATCH
    #
    # Resolve an explicitly mentioned numeric source column
    # before applying the generic Sales/Revenue fallback.
    #
    # Examples:
    #   total GST -> GST
    #   total discount -> Discount
    #   average GST -> GST
    #   total sales -> Total Amount (handled by fallback)
    # ==========================================================
    
    if function and numeric_columns:

        aggregation_words = {
            "sum",
            "total",
            "average",
            "avg",
            "mean",
            "maximum",
            "max",
            "highest",
            "minimum",
            "min",
            "lowest",
        }

        question_without_aggregation = question_norm

        for word in aggregation_words:
            question_without_aggregation = re.sub(
                rf"\b{re.escape(word)}\b",
                " ",
                question_without_aggregation,
            )

        question_without_aggregation = re.sub(
            r"\b(?:of|the|data|records?)\b",
            " ",
            question_without_aggregation,
        )

        question_without_aggregation = re.sub(
            r"\s+",
            " ",
            question_without_aggregation,
        ).strip()

        for column in numeric_columns:

            column_text = _normalize_text(column)

            if not column_text:
                continue

            if (
                re.search(
                    rf"\b{re.escape(column_text)}\b",
                    question_without_aggregation,
                )
                or column_text.replace(" ", "")
                in question_without_aggregation.replace(" ", "")
            ):
                return function, column
    sales_words = {
        "sale",
        "sales",
        "revenue",
        "billing",
        "turnover",
    }

    question_tokens = set(
        _tokens(question_norm)
    )

    has_sales_term = bool(
        question_tokens.intersection(
            sales_words
        )
    )

    if has_sales_term and numeric_columns:

        if not function:
            function = "sum"

        # ------------------------------------------------------
        # SALES METRIC PRIORITY
        #
        # Generic sales/revenue questions should use the actual
        # invoice/sales value, NOT UnitPrice.
        #
        # Example:
        #   Show total sales
        #   Show total sales by customer
        #   Show sales by product
        #
        # Preferred:
        #   InvoiceTotal
        #   Invoice Value
        #   Total Amount
        #   GrossAmount
        #   Sales Amount
        #
        # UnitPrice is intentionally NOT included here because
        # unit price is not total sales.
        # ------------------------------------------------------

        preferred_sales_columns = [
            "Invoice Value",
            "InvoiceTotal",
            "Invoice Total",
            "Total Amount",
            "TotalAmount",
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Revenue",
            "Turnover",
            "Amount",
            "Taxable Value",
            "TaxableAmount",
        ]

        for preferred in preferred_sales_columns:

            preferred_norm = _normalize_text(
                preferred
            )

            for column in numeric_columns:

                column_norm = _normalize_text(
                    column
                )

                if column_norm == preferred_norm:
                    return function, column

        # ------------------------------------------------------
        # Generic monetary fallback
        #
        # Do NOT use UnitPrice as a generic sales metric.
        # ------------------------------------------------------

        fallback_words = (
            "invoice",
            "amount",
            "revenue",
            "turnover",
            "sales",
            "total",
            "value",
        )

        for column in numeric_columns:

            normalized = _normalize_text(
                column
            )

            if any(
                word in normalized
                for word in fallback_words
            ):
                return function, column

        if len(numeric_columns) == 1:
            return function, numeric_columns[0]
    # ==========================================================
    # INVOICE VALUE / INVOICE AMOUNT SPECIAL CASE
    #
    # Examples:
    #   What is the average invoice value?
    #   What is the average invoice amount?
    #   What is the total invoice value?
    #   What is the highest invoice value?
    #
    # "invoice" by itself means InvoiceNo, but
    # "invoice value" means the monetary invoice value.
    # ==========================================================

    if (
        function
        and numeric_columns
        and re.search(
            r"\binvoice\s+(?:value|amount|total)\b",
            question_norm,
        )
    ):

        invoice_value_candidates = [
            "Invoice Value",
            "InvoiceTotal",
            "Invoice Total",
            "Total Amount",
            "TotalAmount",
        ]

        for preferred in invoice_value_candidates:

            preferred_norm = _normalize_text(
                preferred
            )

            for column in numeric_columns:

                column_norm = _normalize_text(
                    column
                )

                if column_norm == preferred_norm:
                    return function, column
    # ==========================================================
    # 9. EXPLICIT AGGREGATION
    #
    # Examples:
    #
    # total GST
    # average discount
    # maximum GST
    # minimum discount
    # ==========================================================

    if function:

        patterns = [
            r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|bottom)"
            r"\s+(?:of\s+)?(.+?)(?:\s+by\s+|\s+per\s+|\s+wise\b|\s+where\s+|$)",

            r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|bottom)"
            r"\s+(.+?)(?:\s+by\s+|\s+per\s+|\s+wise\b|\s+where\s+|$)",
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

            candidate = re.sub(
                r"\b(?:party|customer|product|item)\s+wise\b",
                " ",
                candidate,
            ).strip()

            if not candidate:
                continue

            # --------------------------------------------------
            # First resolve against REAL SOURCE COLUMNS
            # --------------------------------------------------

            for column in dataset_columns:

                column_text = _normalize_text(
                    column
                )

                if (
                    candidate == column_text
                    or candidate.replace(" ", "")
                    == column_text.replace(" ", "")
                ):
                    return function, column

            # --------------------------------------------------
            # Then use existing resolver
            # --------------------------------------------------

            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                rows,
            )

            if resolved:

                # IMPORTANT:
                # Ensure resolver result is converted back
                # to a real source column.
                for column in dataset_columns:

                    if (
                        _normalize_text(column)
                        == _normalize_text(resolved)
                    ):
                        return function, column

                return function, resolved
        # ==========================================================
    # 10. DYNAMIC CATEGORICAL COUNT
    #
    # Examples:
    #
    # count payment mode
    # count product
    # count customers
    # count invoices
    #
    # Also supports:
    #
    # count payment mode by salesperson
    # count product by warehouse
    #
    # IMPORTANT:
    # This does NOT require the column to be numeric.
    # It resolves against the REAL source columns.
    # ==========================================================

    if function == "count":

        # ------------------------------------------------------
        # 10A. Extract the column requested after COUNT
        # ------------------------------------------------------

        count_patterns = [
            r"\b(?:count|how many|number of|total)\b"
            r"\s+(?:of\s+)?(.+?)"
            r"(?:\s+by\s+|\s+per\s+|\s+wise\b|\s+where\s+|$)",

            r"\b(?:count|how many|number of|total)\b"
            r"\s+(.+?)$",
        ]

        for pattern in count_patterns:

            match = re.search(
                pattern,
                question_norm,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            candidate = match.group(1).strip()

            candidate = re.sub(
                r"\b(?:the|records?|data)\b",
                " ",
                candidate,
            ).strip()

            if not candidate:
                continue
            
                        # --------------------------------------------------
            # BUSINESS ENTITY ALIASES
            #
            # User-facing business terms do not always match
            # the actual source-column name.
            #
            # Example:
            #   customers -> Party Name
            #   invoices  -> Invoice No
            #   products  -> Product
            # --------------------------------------------------

            candidate_normalized = _normalize_text(
                candidate
            )

            business_count_aliases = {
                "customer": [
                    "Party Name",
                    "Customer",
                    "Customer Name",
                ],
                "customers": [
                    "Party Name",
                    "Customer",
                    "Customer Name",
                ],
                "party": [
                    "Party Name",
                ],
                "parties": [
                    "Party Name",
                ],
                "invoice": [
                    "Invoice No",
                    "Invoice Number",
                    "Bill No",
                    "Bill Number",
                ],
                "invoices": [
                    "Invoice No",
                    "Invoice Number",
                    "Bill No",
                    "Bill Number",
                ],
                "product": [
                    "Product",
                    "Product Name",
                    "Item",
                    "Item Name",
                ],
                "products": [
                    "Product",
                    "Product Name",
                    "Item",
                    "Item Name",
                ],
                "supplier": [
                    "Supplier",
                    "Supplier Name",
                ],
                "suppliers": [
                    "Supplier",
                    "Supplier Name",
                ],
            }

            alias_columns = business_count_aliases.get(
                candidate_normalized,
                [],
            )

            for alias_column in alias_columns:
                for column in dataset_columns:
                    if (
                        _normalize_text(column)
                        == _normalize_text(alias_column)
                    ):
                        return "count", column
            # --------------------------------------------------
            # Resolve directly against REAL source columns
            # --------------------------------------------------

            for column in dataset_columns:

                column_text = _normalize_text(
                    column
                )

                if not column_text:
                    continue

                if (
                    candidate == column_text
                    or candidate.replace(" ", "")
                    == column_text.replace(" ", "")
                ):
                    return "count", column

            # --------------------------------------------------
            # Token-based source-column matching
            #
            # Handles:
            #
            # payment mode
            # invoice no
            # total amount
            # customer name
            # etc.
            # --------------------------------------------------

            candidate_tokens = set(
                _tokens(candidate)
            )

            if candidate_tokens:

                for column in dataset_columns:

                    column_text = _normalize_text(
                        column
                    )

                    column_tokens = set(
                        _tokens(column_text)
                    )

                    if not column_tokens:
                        continue

                    if column_tokens.issubset(
                        candidate_tokens
                    ):
                        return "count", column

            # --------------------------------------------------
            # Existing resolver fallback
            # --------------------------------------------------

            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                rows,
            )

            if resolved:

                for column in dataset_columns:

                    if (
                        _normalize_text(column)
                        == _normalize_text(resolved)
                    ):
                        return "count", column

                return "count", resolved

    # ==========================================================
    # 10. GENERIC NUMERIC FALLBACK
    # ==========================================================

    if function and function != "count":

        if len(numeric_columns) == 1:
            return function, numeric_columns[0]

        for column in numeric_columns:

            normalized = _normalize_text(
                column
            )

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

    # ==========================================================
    # 11. NOTHING FOUND
    # ==========================================================

    return function, None
    # ========================================================
    # SPECIAL BUSINESS TERMS
    # Vyapar-style questions often use:
    #
    #   sales
    #   sale
    #   revenue
    #   billing
    #   turnover
    #
    # instead of the actual numeric column name:
    #
    #   Total Amount
    #   Amount
    #   Sales Amount
    #
    # Therefore "total sales", "highest sale", etc.
    # should resolve to the appropriate numeric amount column.
    # ========================================================

    sales_words = {
        "sale",
        "sales",
        "revenue",
        "billing",
        "turnover",
    }

    question_tokens = set(
        _tokens(question_norm)
    )

    has_sales_term = bool(
        question_tokens.intersection(
            sales_words
        )
    )

    if has_sales_term:
        numeric_columns = []

        # ----------------------------------------------------
        # Get numeric columns from schema
        # ----------------------------------------------------

        for item in schema:
            data_type = _normalize_text(
                item.get("data_type")
            )

            if data_type in {
                "numeric",
                "number",
                "integer",
                "float",
            }:
                source = item.get(
                    "source_column"
                )

                if source:
                    numeric_columns.append(
                        source
                    )

        # ----------------------------------------------------
        # Detect numeric columns from actual rows
        # ----------------------------------------------------

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

                valid_values = sum(
                    value is not None
                    for value in values
                )

                if (
                    valid_values
                    >= max(
                        1,
                        len(values) // 2,
                    )
                ):
                    numeric_columns.append(
                        column
                    )

        # ----------------------------------------------------
        # Prefer amount/sales/revenue/value columns
        # ----------------------------------------------------

        preferred_words = (
            "amount",
            "sales amount",
            "sale amount",
            "total",
            "revenue",
            "turnover",
            "price",
            "value",
        )

        for column in numeric_columns:
            normalized = _normalize_column(
                column
            )

            if any(
                word in normalized
                for word in preferred_words
            ):
                return function, column

        # If there is exactly one numeric column,
        # use it as the sales value.
        if len(numeric_columns) == 1:
            return function, numeric_columns[0]

    # ========================================================
    # EXPLICIT AGGREGATE COLUMN
    # ========================================================
    #
    # Examples:
    #   total amount
    #   sum of amount
    #   average quantity
    #   highest salary
    # ========================================================

    patterns = [
        r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|bottom)"
        r"\s+(?:of\s+)?(.+?)(?:\s+by\s+|\s+per\s+|\s+wise\b|\s+where\s+|$)",

        r"(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|bottom)"
        r"\s+(.+?)(?:\s+by\s+|\s+per\s+|\s+wise\b|\s+where\s+|$)",
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

        # Do not attempt to resolve grouping words
        # as aggregate columns.
        candidate = re.sub(
            r"\b(?:party|customer|product|item)\s+wise\b",
            " ",
            candidate,
        ).strip()

        if not candidate:
            continue

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
            rows,
        )

        if resolved:
            return function, resolved

    # ========================================================
    # GENERIC NUMERIC COLUMN FALLBACK
    # ========================================================

    if function != "count":
        numeric_columns = []

        for item in schema:
            data_type = _normalize_text(
                item.get("data_type")
            )

            if data_type in {
                "numeric",
                "number",
                "integer",
                "float",
            }:
                source = item.get(
                    "source_column"
                )

                if source:
                    numeric_columns.append(
                        source
                    )

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
                ) >= max(
                    1,
                    len(values) // 2,
                ):
                    numeric_columns.append(
                        column
                    )

        if len(numeric_columns) == 1:
            return function, numeric_columns[0]

        # Prefer amount-like columns.
        for column in numeric_columns:
            normalized = _normalize_column(
                column
            )

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
def _extract_multi_aggregate(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Detect multiple explicit aggregate metrics in one question.

    Example:
        Show total sales, total GST and total discount
        for ABC Traders in September 2026

    Returns:
        [
            {"function": "sum", "column": "Total Amount"},
            {"function": "sum", "column": "GST"},
            {"function": "sum", "column": "Discount"},
        ]

    This is intentionally separate from _extract_aggregate(),
    which continues to support the existing single-metric flow.
    """

    question_norm = _normalize_text(question)

    if not re.search(
        r"\b(?:total|sum|average|avg|mean|maximum|max|minimum|min)\b",
        question_norm,
    ):
        return []

    dataset_columns = _dataset_columns(
        dataset,
        schema,
        rows,
    )

    if not dataset_columns:
        return []

    numeric_columns = []

    for item in schema:
        source = item.get("source_column")
        data_type = _normalize_text(
            item.get("data_type")
        )

        if (
            source
            and source in dataset_columns
            and data_type in {
                "numeric",
                "number",
                "integer",
                "float",
                "decimal",
            }
        ):
            numeric_columns.append(source)

    # Also inspect actual row values so unmapped numeric
    # columns such as GST and Discount are supported.
    for column in dataset_columns:

        if column in numeric_columns:
            continue

        values = []

        for row in rows[:100]:
            value = _to_number(
                row.get(column)
            )

            if value is not None:
                values.append(value)

        if not values:
            continue

        non_empty_count = sum(
            1
            for row in rows[:100]
            if row.get(column) not in (None, "")
        )

        if non_empty_count == 0:
            continue

        numeric_ratio = (
            len(values) / non_empty_count
        )

        if numeric_ratio >= 0.5:
            numeric_columns.append(column)

    numeric_columns = list(
        dict.fromkeys(numeric_columns)
    )

    if not numeric_columns:
        return []

    results = []

    # ----------------------------------------------------------
    # Resolve explicit metric names.
    # ----------------------------------------------------------

    for column in numeric_columns:

        column_norm = _normalize_text(
            column
        )

        if not column_norm:
            continue

        matched = False

        # Exact source-column match.
        if re.search(
            rf"\b{re.escape(column_norm)}\b",
            question_norm,
        ):
            matched = True

        # Token-based match for multi-word columns.
        if not matched:
            column_tokens = set(
                _tokens(column_norm)
            )

            question_tokens = set(
                _tokens(question_norm)
            )

            if (
                column_tokens
                and column_tokens.issubset(
                    question_tokens
                )
            ):
                matched = True

        if not matched:
            continue

                # Determine the requested aggregation.
        #
        # Important:
        # We must detect the aggregation belonging to THIS
        # metric, not any aggregation word appearing nearby.
        #
        # Example:
        #   average GST and total discount
        #
        # GST      -> average
        # Discount -> sum
        # ------------------------------------------------------

        function = "sum"

        column_pattern = re.escape(
            column_norm
        )

        # ------------------------------------------------------
        # Look for an aggregation phrase immediately associated
        # with this column.
        # ------------------------------------------------------

        aggregation_matches = re.findall(
            rf"\b("
            rf"average|avg|mean|"
            rf"maximum|max|highest|"
            rf"minimum|min|lowest|"
            rf"sum|total"
            rf")\b"
            rf"\s+(?:of\s+)?"
            rf"(?:the\s+)?"
            rf"{column_pattern}"
            rf"\b",
            question_norm,
        )

        if not aggregation_matches:
            continue

        for aggregation_word in aggregation_matches:

            function = "sum"

            if aggregation_word in {
                "average",
                "avg",
                "mean",
            }:
                function = "average"

            elif aggregation_word in {
                "maximum",
                "max",
                "highest",
            }:
                function = "max"

            elif aggregation_word in {
                "minimum",
                "min",
                "lowest",
            }:
                function = "min"

            elif aggregation_word in {
                "sum",
                "total",
            }:
                function = "sum"

            results.append(
                {
                    "function": function,
                    "column": column,
                }
            )

    # ----------------------------------------------------------
    # Resolve "sales" as the sales/amount column.
    #
    # "sales" is often a business-domain word rather than
    # a literal source-column name.
    # ----------------------------------------------------------

    if re.search(
        r"\b(?:total|sum)\s+sales?\b",
        question_norm,
    ):

        sales_column = _resolve_column(
            "sales",
            dataset,
            schema,
            rows,
        )

        if not sales_column:
            sales_column = _resolve_column(
                "amount",
                dataset,
                schema,
                rows,
            )

        if (
            sales_column
            and sales_column in numeric_columns
            and not any(
                item["column"] == sales_column
                for item in results
            )
        ):
            results.insert(
                0,
                {
                    "function": "sum",
                    "column": sales_column,
                },
            )

    # Preserve source-column order and remove duplicates.
    unique_results = []
    seen = set()

    for item in results:

        key = (
            item["function"],
            item["column"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(item)

    # Multi-aggregate means at least two metrics.
    if len(unique_results) < 2:
        return []

    return unique_results

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
            # ------------------------------------------------
            # Date-aware comparison
            #
            # Date range filters such as:
            #   Date >= 2026-08-01
            #   Date <= 2026-08-05
            #
            # must compare parsed dates instead of numbers.
            # ------------------------------------------------

            actual_date = _parse_date(actual)
            expected_date = _parse_date(expected)

            if actual_date and expected_date:
                matched = False

                if operator == ">":
                    matched = actual_date > expected_date

                elif operator == "<":
                    matched = actual_date < expected_date

                elif operator == ">=":
                    matched = actual_date >= expected_date

                elif operator == "<=":
                    matched = actual_date <= expected_date

                if matched:
                    result.append(row)

                continue

            # ------------------------------------------------
            # Numeric comparison fallback
            # ------------------------------------------------

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
    """
    Apply multiple filters while avoiding repeated date parsing.

    Date filters such as:
        year = 2025
        month = 4

    are combined into a single row scan when they refer
    to the same date column.
    """

    if not filters or not rows:
        return rows

    date_filters = []
    other_filters = []

    for filter_item in filters:
        operator = filter_item.get("operator")

        if operator in {"year", "month", "date"}:
            date_filters.append(filter_item)
        else:
            other_filters.append(filter_item)

    result = rows

    # ---------------------------------------------------------
    # Optimize date filters
    # ---------------------------------------------------------
    if date_filters:
        date_column = date_filters[0].get("column")

        if date_column and all(
            item.get("column") == date_column
            for item in date_filters
        ):
            optimized_result = []

            parsed_expectations = {}

            for filter_item in date_filters:
                operator = filter_item.get("operator")
                expected = filter_item.get("value")

                if operator == "year":
                    parsed_expectations["year"] = int(expected)

                elif operator == "month":
                    parsed_expectations["month"] = int(expected)

                elif operator == "date":
                    parsed_expectations["date"] = _parse_date(
                        expected
                    )

            expected_year = parsed_expectations.get("year")
            expected_month = parsed_expectations.get("month")
            expected_date = parsed_expectations.get("date")

            for row in result:
                actual = row.get(date_column)

                parsed = _parse_date(actual)

                if not parsed:
                    continue

                if (
                    expected_year is not None
                    and parsed.year != expected_year
                ):
                    continue

                if (
                    expected_month is not None
                    and parsed.month != expected_month
                ):
                    continue

                if (
                    expected_date is not None
                    and parsed.date() != expected_date.date()
                ):
                    continue

                optimized_result.append(row)

            result = optimized_result

        else:
            # Preserve existing behavior for unusual
            # combinations involving different date columns.
            for filter_item in date_filters:
                result = _apply_single_filter(
                    result,
                    filter_item,
                )

    # ---------------------------------------------------------
    # Apply remaining filters normally
    # ---------------------------------------------------------
    for filter_item in other_filters:
        result = _apply_single_filter(
            result,
            filter_item,
        )

    return result

def _is_employee_level_query(
    question: str,
    dataset: Dict[str, Any],
) -> bool:
    """
    Detect employee-level questions on an attendance dataset.

    Examples:
        show all employees
        show employee names and department

    These should return one row per employee rather than
    one row per attendance day.
    """

    if _normalize_text(
        dataset.get("data_type")
    ) != "attendance":
        return False

    text = _normalize_text(question)

    employee_words = re.search(
        r"\b(?:employee|employees|staff|worker|workers)\b",
        text,
    )

    attendance_words = re.search(
        r"\b(?:attendance|present|absent|leave|check in|check out|working hours)\b",
        text,
    )

    return bool(
        employee_words
        and not attendance_words
    )


def _deduplicate_employee_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convert attendance rows into one row per employee.

    Employee identity is based on Employee ID.
    """

    unique_rows = []
    seen_employee_ids = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        employee_id = str(
            row.get("Employee ID", "")
        ).strip()

        if not employee_id:
            continue

        if employee_id in seen_employee_ids:
            continue

        seen_employee_ids.add(employee_id)
        unique_rows.append(row)

    return unique_rows
def _is_employee_level_query(
    question: str,
    dataset: Dict[str, Any],
) -> bool:
    """
    Detect employee-level questions on an attendance dataset.

    Employee-level queries should return one row per employee,
    not one row per attendance day.
    """

    if _normalize_text(
        dataset.get("data_type")
    ) != "attendance":
        return False

    text = _normalize_text(question)

    has_employee_word = re.search(
        r"\b(?:employee|employees|staff|worker|workers)\b",
        text,
    )

    has_attendance_word = re.search(
        r"\b(?:attendance|present|absent|leave|check in|check out|working hours)\b",
        text,
    )

    return bool(
        has_employee_word
        and not has_attendance_word
    )


def _deduplicate_employee_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Return one attendance row per unique Employee ID.
    """

    unique_rows = []
    seen_employee_ids = set()

    for row in rows:
        if not isinstance(row, dict):
            continue

        employee_id = str(
            row.get("Employee ID", "")
        ).strip()

        if not employee_id:
            continue

        if employee_id in seen_employee_ids:
            continue

        seen_employee_ids.add(employee_id)
        unique_rows.append(row)

    return unique_rows
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

        # ----------------------------------------------------
        # COUNT without a column:
        #
        # Count rows.
        # ----------------------------------------------------

        if not column:
            return {
                "operation": "count",
                "count": len(rows),
            }

        # ----------------------------------------------------
        # COUNT with a column:
        #
        # Count occurrences of each distinct value.
        #
        # Example:
        #
        # Payment Mode:
        # UPI
        # Cash
        # UPI
        # Bank
        #
        # becomes:
        #
        # UPI  -> 2
        # Cash -> 1
        # Bank -> 1
        # ----------------------------------------------------

        value_counts: Dict[str, int] = {}

        for row in rows:

            value = row.get(column)

            if value in (None, ""):
                key = "(blank)"
            else:
                key = str(value).strip()

                if not key:
                    key = "(blank)"

            value_counts[key] = (
                value_counts.get(key, 0) + 1
            )

        frequency_rows = [
            {
                column: value,
                "count": count,
            }
            for value, count in value_counts.items()
        ]

        frequency_rows.sort(
            key=lambda item: item["count"],
            reverse=True,
        )

        return {
            "operation": "count",
            "column": column,
            "rows": frequency_rows,
            "count": len(rows),
            "values_count": len(frequency_rows),
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
    time_period: Optional[str] = None,
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        value = row.get(group_column)

        # ----------------------------------------------------
        # Temporal grouping
        #
        # day   -> 2026-09-10
        # month -> 2026-09
        # year  -> 2026
        #
        # If time_period is None, preserve the existing
        # normal grouping behavior.
        # ----------------------------------------------------

        if time_period:
            parsed_date = _parse_date(value)

            if parsed_date:
                if time_period == "day":
                    key = parsed_date.strftime("%Y-%m-%d")

                elif time_period == "month":
                    key = parsed_date.strftime("%Y-%m")

                elif time_period == "year":
                    key = parsed_date.strftime("%Y")

                elif time_period == "quarter":
                    quarter = (
                        (parsed_date.month - 1) // 3
                    ) + 1

                    key = (
                        f"{parsed_date.year}-Q{quarter}"
                    )

                else:
                    key = str(value).strip()

            else:
                key = "(blank)"

        else:
            key = (
                str(value).strip()
                if value is not None
                else "(blank)"
            )

        groups.setdefault(
            key,
            [],
        ).append(row)

    result = []

    # --------------------------------------------------------
    # Create a human-friendly aggregate column name.
    #
    # Example:
    #   sum + Total Amount
    #       -> Total Sales
    #
    #   max + Total Amount
    #       -> Maximum Total Amount
    #
    #   average + Quantity
    #       -> Average Quantity
    # --------------------------------------------------------

    if function == "count":
        result_column = "Count"

    elif aggregate_column:
        if function == "sum":
            normalized_aggregate = _normalize_column(
                aggregate_column
            )

            if any(
                word in normalized_aggregate
                for word in (
                    "amount",
                    "sales",
                    "sale",
                    "revenue",
                    "turnover",
                )
            ):
                result_column = "Total Sales"
            else:
                result_column = (
                    f"Total {aggregate_column}"
                )

        elif function == "average":
            result_column = (
                f"Average {aggregate_column}"
            )

        elif function == "max":
            result_column = (
                f"Maximum {aggregate_column}"
            )

        elif function == "min":
            result_column = (
                f"Minimum {aggregate_column}"
            )

        else:
            result_column = (
                f"{function.title()} {aggregate_column}"
            )

    else:
        result_column = function.title()

    # --------------------------------------------------------
    # Calculate aggregate for each group.
    # --------------------------------------------------------

    for group_value, group_rows in groups.items():

        if function == "count":

            # ------------------------------------------------
            # COUNT without a target column:
            #
            # Count rows in each group.
            # ------------------------------------------------

            if not aggregate_column:

                result.append(
                    {
                        group_column: group_value,
                        result_column: len(group_rows),
                    }
                )

                continue

            # ------------------------------------------------
            # COUNT with a target column:
            #
            # Example:
            #
            # count payment mode by salesperson
            #
            # Group:
            #   Salesperson
            #
            # Count:
            #   Payment Mode
            #
            # Produce one row for every combination.
            # ------------------------------------------------

            value_counts: Dict[str, int] = {}

            for row in group_rows:

                value = row.get(
                    aggregate_column
                )

                if value in (None, ""):
                    value_key = "(blank)"
                else:
                    value_key = str(
                        value
                    ).strip()

                    if not value_key:
                        value_key = "(blank)"

                value_counts[value_key] = (
                    value_counts.get(
                        value_key,
                        0,
                    )
                    + 1
                )

            for value_key, count in value_counts.items():

                result.append(
                    {
                        group_column: group_value,
                        aggregate_column: value_key,
                        "Count": count,
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
                result_column: aggregate.get(
                    "value"
                ),
            }
        )

    # --------------------------------------------------------
    # Sorting
    #
    # Normal grouped queries:
    #   Highest aggregate first.
    #
    # Temporal trend queries:
    #   Chronological order.
    # --------------------------------------------------------

    if time_period:
        if time_period == "day":
            result.sort(
                key=lambda item: str(
                    item.get(group_column, "")
                )
            )

        elif time_period == "month":
            result.sort(
                key=lambda item: str(
                    item.get(group_column, "")
                )
            )

        elif time_period == "year":
            result.sort(
                key=lambda item: str(
                    item.get(group_column, "")
                )
            )

        elif time_period == "quarter":
            result.sort(
                key=lambda item: str(
                    item.get(group_column, "")
                )
            )

        else:
            result.sort(
                key=lambda item: str(
                    item.get(group_column, "")
                )
            )

    else:
        # Normal grouped aggregation:
        # highest result first.
        result.sort(
            key=lambda item: (
                _to_number(
                    item.get(result_column)
                )
                if function != "count"
                else _to_number(
                    item.get("count")
                )
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
    # SEMANTIC GROUP-BY COLUMN MATCH
    # ==========================================================
    #
    # Reuse the same dynamic column resolver used by the
    # query engine.
    #
    # This allows dataset selection to understand:
    #
    #   payment method  -> Payment Mode
    #   payment type    -> Payment Mode
    #   location        -> Warehouse
    #   branch          -> Warehouse
    #   store           -> Warehouse
    #
    # without hardcoding every possible user phrase here.
    #
    # IMPORTANT:
    # Actual source columns still take precedence because
    # _extract_group_by() resolves the real source column.
    # ==========================================================

    try:
        semantic_group_column = _extract_group_by(
            question,
            dataset,
            schema,
            [],
        )

        if semantic_group_column:
            normalized_group_column = _normalize_column(
                semantic_group_column
            )

            normalized_source_columns = {
                _normalize_column(column)
                for column in columns
                if _normalize_column(column)
            }

            if (
                normalized_group_column
                in normalized_source_columns
            ):
                # Strong bonus because the dataset actually
                # contains the requested grouping concept.
                score += 250

    except Exception:
        # Dataset selection must never fail because of
        # semantic group-column detection.
        pass

    
    # ==========================================================
    # DOMAIN / DATASET SEMANTIC MATCH
    # ==========================================================
    #
    # Important:
    # A word such as "sales" can appear as a CELL VALUE in
    # an unrelated dataset, for example:
    #
    #     Department = Sales
    #
    # That must not cause an HR/attendance dataset to beat an
    # actual sales dataset containing columns such as:
    #
    #     Party Name
    #     Invoice No
    #     Total Amount
    #     Bill Date
    #     Product
    #
    # We therefore score the dataset's schema/domain before
    # actual row-value matches are considered.
    # ==========================================================

    normalized_columns = {
        _normalize_text(column)
        for column in columns
        if _normalize_text(column)
    }

    question_domain_words = {
        token
        for token in question_tokens
        if token in {
            "sale",
            "sales",
            "invoice",
            "invoices",
            "billing",
            "bill",
            "revenue",
            "purchase",
            "purchases",
            "party",
            "parties",
            "product",
            "products",
            "stock",
            "inventory",
            "order",
            "orders",
            "transaction",
            "transactions",
        }
    }

    # ==========================================================
    # ATTENDANCE / HR DOMAIN MATCH
    # ==========================================================

    attendance_question_words = {
        token
        for token in question_tokens
        if token in {
            "employee",
            "employees",
            "attendance",
            "attendances",
            "present",
            "absent",
            "leave",
            "leaves",
            "half",
            "weekly",
            "off",
            "check",
            "working",
            "hours",
            "department",
            "designation",
        }
    }

    sales_schema_columns = {
        "party name",
        "party",
        "customer name",
        "invoice no",
        "invoice number",
        "invoice",
        "bill no",
        "bill number",
        "bill date",
        "total amount",
        "amount",
        "sales amount",
        "sale amount",
        "product",
        "item",
        "item name",
    }

    hr_schema_columns = {
        "employee id",
        "employee name",
        "department",
        "designation",
        "employment type",
        "joining date",
        "attendance status",
        "check in",
        "check out",
        "working hours",
        "leave type",
    }

    sales_schema_overlap = (
        normalized_columns.intersection(
            sales_schema_columns
        )
    )

    hr_schema_overlap = (
        normalized_columns.intersection(
            hr_schema_columns
        )
    )

    if question_domain_words and sales_schema_overlap:
        score += 100 + (
            len(sales_schema_overlap) * 15
        )

    if attendance_question_words and hr_schema_overlap:
        score += 100 + (
            len(hr_schema_overlap) * 15
        )

    # ==========================================================
    # QUERY DOMAIN VS DATASET TYPE
    # ==========================================================
    dataset_type = _normalize_text(
        dataset.get("data_type")
    )

    if dataset_type:
        normalized_dataset_type = _singular(dataset_type)
        normalized_question_tokens = {
            _singular(token)
            for token in question_tokens
        }

        if (
            dataset_type in question_tokens
            or normalized_dataset_type
            in normalized_question_tokens
        ):
            score += 300

    ignored_query_words = {
        "show",
        "get",
        "give",
        "display",
        "find",
        "search",
        "download",
        "save",
        "data",
        "records",
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

        # ------------------------------------------------------
        # Generic business/domain words in a filename should
        # NOT influence dataset selection by themselves.
        #
        # Example:
        #   "Show sales by product"
        #
        # should not prefer:
        #   test_period_sales.csv
        #
        # merely because the filename contains "sales".
        #
        # Explicit filename references still receive the
        # stronger exact filename bonus below.
        # ------------------------------------------------------

        generic_filename_tokens = {
            "sale",
            "sales",
            "purchase",
            "purchases",
            "invoice",
            "invoices",
            "billing",
            "bill",
            "product",
            "products",
            "customer",
            "customers",
            "supplier",
            "suppliers",
            "employee",
            "employees",
            "attendance",
            "expense",
            "expenses",
            "payment",
            "payments",
            "inventory",
            "stock",
            "data",
            "dataset",
            "report",
        }

        filename_specific_tokens = {
            token
            for token in filename_tokens
            if _singular(token)
            not in {
                _singular(value)
                for value in generic_filename_tokens
            }
        }

        filename_overlap = question_tokens.intersection(
            filename_specific_tokens
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

        column_tokens = _tokens(column)

        # ------------------------------------------------------
        # Exact phrase match
        # ------------------------------------------------------

        if re.search(
            rf"\b{re.escape(column_text)}\b",
            question_text,
        ):
            exact_source_columns.append(column)
            score += 40
            continue

        # ------------------------------------------------------
        # Generic singular/plural token match
        #
        # Example:
        #   "invoices" -> "invoice"
        #   "products" -> "product"
        #   "customers" -> "customer"
        #
        # This does NOT require adding every possible column
        # name to Python.
        # ------------------------------------------------------

        normalized_column_tokens = {
            _singular(token)
            for token in column_tokens
        }

        normalized_question_tokens = {
            _singular(token)
            for token in question_tokens
        }

        if normalized_column_tokens:
            token_overlap = (
                normalized_column_tokens
                .intersection(
                    normalized_question_tokens
                )
            )

            # Only treat a single-token column as an exact
            # requested-column match when that token is present.
            if len(column_tokens) == 1 and token_overlap:
                exact_source_columns.append(column)
                score += 40

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
    #
    # Detect free-form values from the ACTUAL DATASET.
    #
    # Examples:
    #   Shalini Sharma
    #   Ladies Watch
    #   UPI
    #   Delhi
    #
    # Important:
    # Keep the COLUMN associated with the value.
    #
    # This allows dataset selection to distinguish:
    #
    #   PartyState = Delhi
    #   State      = Delhi
    #
    # and also lets detailed transaction datasets receive
    # preference when a business value exists in them.
    # ==========================================================

    month_tokens = {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }

    metric_tokens = {
        "gst",
        "cgst",
        "sgst",
        "igst",
        "tax",
        "taxable",
        "amount",
        "value",
        "profit",
        "discount",
        "quantity",
        "qty",
        "sales",
        "sale",
        "revenue",
        "turnover",
        "billing",
        "invoice",
        "invoices",
        "total",
        "average",
        "avg",
        "mean",
        "maximum",
        "max",
        "minimum",
        "min",
        "highest",
        "lowest",
        "top",
        "bottom",
    }

    row_match_tokens = {
        token
        for token in meaningful_tokens
        if token not in question_domain_words
        and token not in month_tokens
        and token not in metric_tokens
        and not (
            token.isdigit()
            and len(token) == 4
        )
    }

    # Only perform the expensive row scan when the question
    # contains a possible free-form categorical value.
    if row_match_tokens:

        try:
            dataset_id = dataset.get("id")

            if dataset_id is not None:
                candidate_rows = load_dataset_rows(
                    int(dataset_id)
                )

                if candidate_rows:
                    rows_to_scan = candidate_rows[:5000]

                    # --------------------------------------------------
                    # Collect UNIQUE VALUES BY COLUMN
                    #
                    # Previously all values were placed into one set.
                    # That made:
                    #
                    #     Delhi
                    #
                    # lose its originating column.
                    #
                    # We now preserve:
                    #
                    #     {
                    #         "PartyState": {"Delhi", ...},
                    #         "Product": {...},
                    #         "PartyName": {...}
                    #     }
                    # --------------------------------------------------

                    column_values = {}

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

                        for column, value in row_data.items():

                            if value is None:
                                continue

                            value_text = _normalize_text(
                                str(value)
                            )

                            if not value_text:
                                continue

                            column_values.setdefault(
                                column,
                                set(),
                            ).add(
                                value_text
                            )

                    # --------------------------------------------------
                    # SCORE ACTUAL VALUES WITH THEIR COLUMNS
                    # --------------------------------------------------

                    exact_value_matches = []
                    token_value_matches = []

                    actual_value_tokens = set()

                    for column, matched_values in column_values.items():

                        normalized_column = _normalize_text(
                            str(column)
                        )

                        column_tokens = set(
                            _tokens(normalized_column)
                        )

                        # ------------------------------------------------
                        # CANONICAL COLUMN NAME
                        #
                        # Example:
                        #   PartyState -> state
                        #   InvoiceNo  -> invoice_no
                        #   PartyName  -> customer
                        #
                        # This lets free-form values use the schema's
                        # canonical meaning instead of depending on the
                        # raw source-column name.
                        # ------------------------------------------------

                        canonical_column = _canonical_name(
                            column,
                            schema,
                        )

                        normalized_canonical_column = _normalize_text(
                            canonical_column or ""
                        )

                        canonical_column_tokens = set(
                            _tokens(normalized_canonical_column)
                        )

                        for value_text in matched_values:

                            value_tokens = _tokens(
                                value_text
                            )

                            if not value_tokens:
                                continue

                            actual_value_tokens.update(
                                value_tokens
                            )

                            overlap = (
                                row_match_tokens.intersection(
                                    value_tokens
                                )
                            )

                            if overlap:

                                token_value_matches.append(
                                    {
                                        "column": column,
                                        "value": value_text,
                                        "overlap": overlap,
                                    }
                                )

                                # Stronger than the old generic
                                # token-only score.
                                score += (
                                    len(overlap) * 12
                                )

                            # ------------------------------------------------
                            # EXACT VALUE / PHRASE MATCH
                            # ------------------------------------------------

                            if (
                                len(value_text) >= 2
                                and re.search(
                                    rf"\b{re.escape(value_text)}\b",
                                    question_text,
                                )
                            ):

                                exact_value_matches.append(
                                    {
                                        "column": column,
                                        "value": value_text,
                                    }
                                )

                                # Exact actual dataset value.
                                score += 30

                                # ------------------------------------------------
                                # COLUMN-AWARE EXACT MATCH
                                #
                                # Example:
                                #
                                #   "show sales by state Delhi"
                                #
                                # Dataset 22:
                                #   PartyState = Delhi
                                #
                                # Dataset 25:
                                #   State = Delhi
                                #
                                # Both can match Delhi, but the detailed
                                # transaction dataset gets an additional
                                # preference below.
                                # ------------------------------------------------

                                normalized_question_tokens = set(
                                    _tokens(question_text)
                                )

                                source_column_match = bool(
                                    normalized_column
                                    in normalized_question_tokens
                                )

                                canonical_column_match = bool(
                                    canonical_column_tokens
                                    .intersection(
                                        normalized_question_tokens
                                    )
                                )

                                if source_column_match:
                                    score += 15

                                if canonical_column_match:
                                    score += 15

                    # --------------------------------------------------
                    # ADDITIONAL UNIQUE-TOKEN MATCH
                    # --------------------------------------------------

                    actual_matches = (
                        row_match_tokens.intersection(
                            actual_value_tokens
                        )
                    )

                    score += min(
                        len(actual_matches) * 20,
                        100,
                    )

                    # --------------------------------------------------
                    # DETAILED TRANSACTION DATASET PREFERENCE
                    #
                    # If the user's free-form value actually exists
                    # inside a detailed transaction dataset, prefer
                    # that dataset over derived summary/ledger data.
                    #
                    # This is generic and dataset-independent.
                    #
                    # Examples:
                    #
                    #   Delhi
                    #   UPI
                    #   Watches
                    #   Ladies Watch
                    #   Pooja Sharma
                    # --------------------------------------------------

                    if exact_value_matches:
                        try:
                            if _is_detailed_transaction_dataset(
                                dataset,
                                schema,
                            ):
                                score += 350

                        except Exception:
                            pass

        except Exception:
            # Dataset selection must never crash the agent.
            pass
    
    # Explicit dataset-domain words should strongly influence
    # dataset selection.
    #
    # Example:
    #
    #   "Show sales for September 2026"
    #
    # must prefer:
    #
    #   data_type = sales
    #
    # over:
    #
    #   data_type = attendance
    #
    # even if the attendance dataset contains:
    #
    #   Department = Sales
    #
    # as a row value.
    # ==========================================================

    dataset_type = _normalize_text(
        dataset.get("data_type")
    )

    if dataset_type:
        normalized_dataset_type = _singular(
            dataset_type
        )

        normalized_question_tokens = {
            _singular(token)
            for token in question_tokens
        }

        if (
            dataset_type in question_tokens
            or normalized_dataset_type
            in normalized_question_tokens
        ):
            score += 300 
    
    # ==========================================================
    # DETAILED METRIC DATASET PREFERENCE
    # ==========================================================
    #
    # For metric-only questions such as:
    #
    #   Show total quantity sold
    #   What is the average unit price?
    #   What is the total gross amount?
    #
    # prefer a sufficiently large detailed transaction dataset
    # when it actually contains the requested metric column.
    #
    # This prevents small summary/test datasets from winning
    # merely because they contain generic words such as:
    #
    #   Price
    #   Taxable Value
    #   Total
    #
    # The rule is generic and does not depend on a dataset ID.
    # ==========================================================

    metric_query_terms = {
        "quantity",
        "qty",
        "unit price",
        "unitprice",
        "gross amount",
        "grossamount",
        "discount",
        "discount amount",
        "taxable amount",
        "gst",
        "cgst",
        "sgst",
        "igst",
        "profit",
        "cost",
        "invoice value",
        "invoice total",
    }

    normalized_metric_columns = {
        _normalize_column(column)
        for column in columns
        if _normalize_column(column)
    }

    requested_metric_matches = []

    for metric_term in metric_query_terms:
        normalized_metric_term = _normalize_column(
            metric_term
        )

        if not normalized_metric_term:
            continue

        if normalized_metric_term in normalized_metric_columns:
            if (
                re.search(
                    rf"\b{re.escape(metric_term)}\b",
                    question_text,
                )
            ):
                requested_metric_matches.append(
                    normalized_metric_term
                )

    if requested_metric_matches:

        try:
            row_count = int(
                dataset.get("row_count", 0) or 0
            )
        except (TypeError, ValueError):
            row_count = 0

        if (
            _singular(dataset_type)
            in {
                "sale",
                "purchase",
                "expense",
                "payment",
                "inventory",
            }
            and row_count >= 100
        ):
            score += 500

            # Prefer substantial transaction datasets,
            # but keep this bonus capped.
            score += min(
                row_count / 20,
                150,
            )
    
    # ==========================================================
    # GENERIC SALES TOTAL DATASET PREFERENCE
    # ==========================================================
    #
    # For a generic query such as:
    #
    #     "Show total sales"
    #
    # there is no customer/product/category/month/etc. to
    # identify a specific dataset.
    #
    # Prefer a real transaction-level sales dataset over
    # tiny test/manual/summary datasets.
    #
    # This rule intentionally applies ONLY to generic sales
    # queries so existing specific dataset-selection behavior
    # remains unchanged.
    # ==========================================================

    generic_sales_query = bool(
        re.search(
            r"\b(?:sales?|revenue|turnover|billing)\b",
            question_text,
        )
        and not re.search(
            r"\b(?:by|per|each|product|products|customer|customers|"
            r"party|parties|category|categories|payment|"
            r"month|monthly|day|daily|date|year|yearly|"
            r"highest|lowest|top|bottom|profit)\b",
            question_text,
        )
    )

    if (
        generic_sales_query
        and _singular(dataset_type) == "sale"
    ):
        normalized_sales_columns = {
            _normalize_column(column)
            for column in columns
            if _normalize_column(column)
        }

        strong_transaction_columns = {
            "invoice no",
            "invoice number",
            "invoice total",
            "invoicetotal",
            "invoice value",
            "date",
            "bill date",
            "party name",
            "customer name",
            "product",
            "qty",
            "quantity",
            "taxable amount",
            "taxableamount",
            "profit",
            "payment mode",
        }

        transaction_matches = (
            normalized_sales_columns.intersection(
                strong_transaction_columns
            )
        )

        if len(transaction_matches) >= 3:
            score += 400

            try:
                row_count = int(
                    dataset.get("row_count", 0)
                )

                # Prefer substantial transaction datasets.
                # Cap the bonus so very large datasets do not
                # overwhelm all other matching logic.
                score += min(
                    row_count / 10,
                    200,
                )

            except Exception:
                pass

    # ==========================================================
    # DISTINCT-VALUE QUERY DATASET PREFERENCE
    # ==========================================================
    #
    # For queries such as:
    #
    #     Show all Month values
    #     Show all Product values
    #     Show all InvoiceNo values
    #     Show all GSTIN values
    #
    # multiple datasets may contain the same requested column.
    #
    # Prefer a sufficiently large detailed transaction dataset
    # over a small summary/aggregate dataset.
    #
    # This is intentionally generic. It does NOT depend on:
    #
    #     Month
    #     Product
    #     InvoiceNo
    #     GSTIN
    #
    # or any specific dataset ID.
    # ==========================================================

    distinct_value_query = bool(
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide)\b"
            r".*?\b(?:all|every|unique|distinct)\b"
            r".*?\bvalues?\b",
            question_text,
            flags=re.IGNORECASE,
        )
        or
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide)\b"
            r".*?\b(?:unique|distinct)\b",
            question_text,
            flags=re.IGNORECASE,
        )
        or
        re.search(
            r"\bhow\s+many\b"
            r".*?\b(?:unique|distinct)\b",
            question_text,
            flags=re.IGNORECASE,
        )
    )

    if (
        distinct_value_query
        and exact_source_columns
        and _singular(dataset_type)
        in {
            "sale",
            "purchase",
            "expense",
            "payment",
            "inventory",
        }
    ):
        try:
            row_count = int(
                dataset.get("row_count", 0) or 0
            )
        except (TypeError, ValueError):
            row_count = 0

        # A detailed transaction dataset must have a
        # substantial number of records. Small datasets
        # are allowed to remain summary/test datasets.
        if row_count >= 100:
            score += 500

            # Prefer larger detailed datasets while keeping
            # the bonus capped.
            score += min(
                row_count / 20,
                150,
            )
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

    # ==========================================================
    # 1. EXPLICIT GROUP + AGGREGATION
    # ==========================================================

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

    # ==========================================================
    # 2. COLUMN-BY-GROUP QUESTIONS
    #
    # Examples:
    #   GST by salesperson
    #   Discount by warehouse
    #   Commission by product
    #   Transport Charges by city
    #
    # These are aggregation queries even though the user did
    # not explicitly say "sum" or "total".
    #
    # The actual columns are resolved later dynamically.
    # ==========================================================

    elif (
        re.search(
            r"\bby\b",
            text,
        )
        and not re.search(
            r"\b(?:sum|total|average|avg|mean|max|maximum|min|minimum|count|how many)\b",
            text,
        )
    ):
        intent = "group_aggregate"

    # ==========================================================
    # 3. EXPLICIT AGGREGATION
    # ==========================================================

    elif re.search(
        r"\b(?:sum|total|average|avg|mean|max|maximum|min|minimum|highest|lowest|how much)\b",
        text,
    ):
        intent = "aggregate"

    # ==========================================================
    # 4. FILTER
    # ==========================================================

    elif re.search(
        r"(?:>=|<=|>|<|greater than|more than|above|over|less than|below|under|at least|at most)",
        text,
    ):
        intent = "filter"

    # ==========================================================
    # 5. PROJECTION
    # ==========================================================

    elif re.search(
        r"\b(?:show|display|list|give|get|fetch|return|only|just)\b",
        text,
    ):
        intent = "projection"

    # ==========================================================
    # 6. COUNT
    # ==========================================================

    elif re.search(
        r"\b(?:how many|count|number of)\b",
        text,
    ):
        intent = "count"

    # ==========================================================
    # 7. LOOKUP
    # ==========================================================

    elif re.search(
        r"\b(?:which|who|what)\b",
        text,
    ):
        intent = "lookup"

    # ==========================================================
    # 8. DEFAULT SEARCH
    # ==========================================================

    else:
        intent = "search"

    return {
        **state,
        "intent": intent,
        "export_requested": export_requested,
        "export_format": export_format,
    }

def _is_detailed_transaction_dataset(
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
) -> bool:
    """
    Detect whether a dataset looks like a real detailed
    business transaction dataset rather than a small
    summary/test dataset.
    """

    data_type = _singular(
        dataset.get("data_type")
    )

    if data_type not in {
        "sale",
        "purchase",
        "expense",
        "payment",
        "inventory",
    }:
        return False

    try:
        row_count = int(
            dataset.get("row_count", 0) or 0
        )
    except (TypeError, ValueError):
        row_count = 0

    # A detailed transaction dataset should contain
    # a meaningful number of transaction rows.
    if row_count < 100:
        return False

    columns = []

    for item in schema or []:

        if not isinstance(item, dict):
            continue

        source = item.get(
            "source_column"
        )

        canonical = item.get(
            "canonical_column"
        )

        if source:
            columns.append(
                str(source)
            )

        if canonical:
            columns.append(
                str(canonical)
            )

    normalized_columns = {
        _normalize_text(column)
        for column in columns
        if column
    }

    transaction_columns = {
        "invoice no",
        "invoice number",
        "invoice",
        "invoice total",
        "invoice value",
        "date",
        "bill date",
        "transaction date",
        "party name",
        "customer name",
        "customer",
        "product",
        "product name",
        "qty",
        "quantity",
        "taxable amount",
        "taxableamount",
        "gst",
        "cgst",
        "sgst",
        "igst",
        "profit",
        "payment mode",
    }

    matches = normalized_columns.intersection(
        transaction_columns
    )

    return len(matches) >= 3
# ============================================================
# NODE 2 - DATASET SELECTION
# ============================================================

def select_dynamic_dataset(
    state: DynamicAgentState,
) -> DynamicAgentState:
    question = state.get("question", "").strip()
    requested_dataset_id = state.get("dataset_id")

    datasets = get_all_dataset_context()
    
    # --------------------------------------------------------
    # Identify detailed business transaction datasets.
    #
    # These are preferred over tiny test/sample/summary
    # datasets when a date-specific business query is made.
    # --------------------------------------------------------

    detailed_transaction_datasets = []

    for item in datasets:
        dataset = item.get("dataset", {})
        schema = item.get("schema", [])

        if _is_detailed_transaction_dataset(
            dataset,
            schema,
        ):
            detailed_transaction_datasets.append(
                item
            )

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
    # Cache whether each dataset contains at least one row
    # matching the requested date filters.
    #
    # This prevents the same detailed dataset from being
    # scanned and parsed again later in the date-safety block.
    date_eligibility_cache = {}


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

        # ----------------------------------------------------
        # Date-aware dataset eligibility
        #
        # If the question contains a date/month/year/range
        # filter, a dataset must contain at least one row
        # matching that requested period.
        #
        # This prevents a dataset with a higher general score
        # from being selected when it cannot answer the
        # requested period.
        # ----------------------------------------------------

        date_filters = _extract_date_filters(
            question,
            dataset,
            schema,
            [],
        )

        if date_filters:
            date_eligibility_cache[dataset_id] = False

            # Resolve the date column from schema/metadata first.
            date_column = _find_date_column(
                dataset,
                schema,
                [],
            )

            # Preserve fallback support for Month-only datasets.
            if not date_column:
                try:
                    fallback_rows = load_dataset_rows(
                        dataset_id
                    )
                except Exception:
                    fallback_rows = []

                if fallback_rows:
                    date_column = _find_date_column(
                        dataset,
                        schema,
                        fallback_rows,
                    )

            if date_column:

                period_exists = False

                try:
                    period_exists = check_dataset_has_matching_dates(
                        dataset_id,
                        date_column,
                        date_filters,
                    )

                except Exception:
                    period_exists = False

                date_eligibility_cache[dataset_id] = (
                    period_exists
                )

                if not period_exists:
                    continue
                    if row_matches:
                        period_exists = True
                        break

                date_eligibility_cache[dataset_id] = (
                    period_exists
                )

                if not period_exists:
                    continue
        #
        # If the user explicitly asks for:
        #     "... by <column>"
        #
        # the candidate dataset must actually contain that
        # requested grouping column.
        #
        # Example:
        #     "invoice value by GST rate"
        #
        # Party-wise Ledger has:
        #     GST
        #
        # but does NOT have:
        #     GST Rate / GST Rate %
        #
        # Therefore Party-wise Ledger must be rejected.
        # --------------------------------------------------------

        group_match = re.search(
            r"\bby\s+(.+?)(?=\s+(?:where|with|having|for|and|or)\b|$)",
            _normalize_text(question),
        )

        if group_match:
            requested_group = group_match.group(1).strip()

            candidate_rows = []

            try:
                candidate_rows = load_dataset_rows(
                    dataset_id
                )
            except Exception:
                candidate_rows = []

            # ----------------------------------------------------
            # TOP-N RANKING SPECIAL CASE
            #
            # Examples:
            #   Show the top 3 products by sales
            #   Show the top 3 customers by sales
            #
            # In these queries:
            #
            #   "products/customers" = GROUP BY dimension
            #   "sales"              = ranking metric
            #
            # The normal "by <column>" logic would incorrectly
            # interpret "sales" as the grouping column.
            # ----------------------------------------------------

            ranking_group_column = None

            top_n_ranking_match = re.search(
                r"\b(?:top|bottom)\s+\d+\s+"
                r"(customers?|products?|items?|parties?|"
                r"categories?|suppliers?|vendors?)"
                r"\s+by\s+",
                _normalize_text(question),
                flags=re.IGNORECASE,
            )

            if top_n_ranking_match:
                ranking_entity = (
                    top_n_ranking_match.group(1)
                    .strip()
                )

                ranking_group_column = _resolve_column(
                    ranking_entity,
                    dataset,
                    schema,
                    candidate_rows,
                )

            # ----------------------------------------------------
            # If this is a Top-N ranking query and the entity
            # column exists, use that entity as the grouping
            # column instead of trying to resolve "sales".
            # ----------------------------------------------------

            if ranking_group_column:
                actual_group_column = ranking_group_column

            else:
                actual_group_column = _resolve_column(
                    requested_group,
                    dataset,
                    schema,
                    candidate_rows,
                )

                # Reuse the full semantic group-by resolver when
                # direct column resolution cannot understand the
                # user's phrase.
                #
                # Example:
                #   "inter state status" -> InterState
                #   "payment method"     -> PaymentMode
                #   "GST rate"           -> GST_Rate
                #
                # This keeps dataset selection consistent with
                # the actual query execution logic.
                if not actual_group_column:
                    actual_group_column = _extract_group_by(
                        question,
                        dataset,
                        schema,
                        candidate_rows,
                    )

            if not actual_group_column:
                # --------------------------------------------------------
                # AMBIGUOUS "BY <VALUE>" QUERY
                #
                # Examples:
                #   Show sales by Delhi
                #   Show sales by Gujarat
                #   Show sales by Karnataka
                #
                # Here the word after "by" is a DATA VALUE, not a
                # grouping column. The actual column will be discovered
                # later by the row-value matching logic.
                #
                # Also support:
                #
                #   Show sales by state Delhi
                #
                # where:
                #   "state"  = grouping/filter column
                #   "Delhi"  = actual value
                #
                # Do not reject the dataset simply because the complete
                # "by ..." phrase cannot be resolved as a column.
                # --------------------------------------------------------

                requested_group_tokens = [
                    token
                    for token in _tokens(requested_group)
                    if token
                ]

                prefix_group_column = None

                # Try progressively shorter prefixes.
                #
                # Example:
                #   "state delhi"
                #
                # tries:
                #   "state delhi"
                #   "state"
                #
                # and therefore resolves "state".
                for prefix_length in range(
                    len(requested_group_tokens),
                    0,
                    -1,
                ):
                    candidate_group_text = " ".join(
                        requested_group_tokens[:prefix_length]
                    )

                    prefix_group_column = _resolve_column(
                        candidate_group_text,
                        dataset,
                        schema,
                        candidate_rows,
                    )

                    if prefix_group_column:
                        actual_group_column = prefix_group_column
                        break

            # --------------------------------------------------------
            # If even the prefix cannot be resolved, keep the
            # dataset as a candidate.
            #
            # Row-value matching will decide whether the value
            # actually exists in this dataset.
            # --------------------------------------------------------
                    
            # ----------------------------------------------------
            # DETAILED GROUP-BY DATASET PREFERENCE
            #
            # When the user explicitly asks for a grouped business
            # metric such as:
            #
            #   Show total sales by state
            #   Show sales by customer
            #   Show sales by product
            #   Show sales by category
            #
            # prefer a large detailed transaction dataset when it
            # actually contains the requested grouping column.
            #
            # This prevents derived summary/ledger datasets from
            # winning merely because they contain a matching
            # "State", "Customer", etc. column.
            #
            # This is dataset-independent.
            # ----------------------------------------------------

            try:
                group_dataset_row_count = int(
                    dataset.get("row_count", 0) or 0
                )
            except (TypeError, ValueError):
                group_dataset_row_count = 0

            if (
                group_dataset_row_count >= 100
                and _is_detailed_transaction_dataset(
                    dataset,
                    schema,
                )
            ):
                score += 350

        # --------------------------------------------------------
        # DETAILED DATASET PREFERENCE
        #
        # When the user asks for detailed business information
        # such as products, customers, parties, categories,
        # HSN, invoices, suppliers, vendors, or payment modes,
        # prefer a sufficiently large transactional dataset
        # over tiny test/manual datasets that happen to match.
        #
        # This is generic and does not depend on any dataset ID.
        # --------------------------------------------------------

        normalized_question = _normalize_text(
            question
        )

        detailed_query_terms = {
            "product",
            "products",
            "customer",
            "customers",
            "party",
            "parties",
            "category",
            "categories",
            "hsn",
            "invoice",
            "invoices",
            "supplier",
            "suppliers",
            "vendor",
            "vendors",
            "payment mode",
            "payment modes",
        }

        asks_for_detail = any(
            re.search(
                rf"\b{re.escape(term)}\b",
                normalized_question,
            )
            for term in detailed_query_terms
        )

        if asks_for_detail:
            try:
                row_count = int(
                    dataset.get("row_count", 0) or 0
                )
            except (TypeError, ValueError):
                row_count = 0

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                    "inventory",
                }
                and row_count >= 100
            ):
                score += 150
        # --------------------------------------------------------
        # TIME-SERIES / TREND DATASET PREFERENCE
        #
        # Prefer datasets specifically containing monthly/time
        # series information when the question asks for a trend.
        #
        # This is generic and does not depend on dataset IDs.
        # --------------------------------------------------------

        trend_terms = {
            "monthly",
            "month wise",
            "month-wise",
            "monthly trend",
            "trend",
            "yearly",
            "year wise",
            "year-wise",
            "annual",
            "annual trend",
            "quarterly",
            "quarter wise",
            "quarter-wise",
        }

        asks_for_trend = any(
            re.search(
                rf"\b{re.escape(term)}\b",
                normalized_question,
            )
            for term in trend_terms
        )

        if asks_for_trend:
            candidate_columns = []

            for schema_item in schema:
                source_column = schema_item.get(
                    "source_column"
                )

                if source_column:
                    candidate_columns.append(
                        _normalize_text(source_column)
                    )

            has_time_column = any(
                (
                    "month" in column
                    or "date" in column
                    or "year" in column
                    or "quarter" in column
                )
                for column in candidate_columns
            )

            try:
                row_count = int(
                    dataset.get("row_count", 0) or 0
                )
            except (TypeError, ValueError):
                row_count = 0

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                }
                and has_time_column
                and row_count >= 3
            ):
                score += 200
        
        # --------------------------------------------------------
        # SUMMARY / TREND DATASET PREFERENCE
        #
        # Prefer an existing monthly summary dataset only when
        # the requested trend can actually be answered from
        # monthly summary data.
        #
        # IMPORTANT:
        # Daily trend queries must NOT receive this bonus because
        # a monthly summary cannot provide true daily data.
        #
        # Examples:
        #   Show daily sales trend
        #       -> prefer detailed transaction dataset
        #
        #   Show monthly sales trend
        #       -> monthly summary dataset is preferred
        #
        #   Show quarterly sales trend
        #       -> monthly summary can be grouped into quarters
        #
        #   Show yearly sales trend
        #       -> monthly summary can be grouped into years
        # --------------------------------------------------------

        trend_terms = {
            "monthly",
            "month wise",
            "month-wise",
            "monthly trend",
            "trend",
            "yearly",
            "year wise",
            "year-wise",
            "annual",
            "annual trend",
            "quarterly",
            "quarter wise",
            "quarter-wise",
        }

        asks_for_trend = any(
            re.search(
                rf"\b{re.escape(term)}\b",
                normalized_question,
            )
            for term in trend_terms
        )

        # Daily requests require actual date-level/detail data.
        asks_for_daily_trend = bool(
            re.search(
                r"\b(?:daily|day|day\s+wise|day-wise|"
                r"by\s+day|date\s+wise|date-wise)\b",
                normalized_question,
            )
        )

        # Monthly/yearly/quarterly trends can use a monthly
        # summary dataset because those periods can be derived
        # from monthly data.
        asks_for_summary_trend = bool(
            re.search(
                r"\b(?:monthly|month\s+wise|month-wise|"
                r"monthly\s+trend|yearly|year\s+wise|"
                r"year-wise|annual|annual\s+trend|"
                r"quarterly|quarter\s+wise|quarter-wise)\b",
                normalized_question,
            )
        )

        if (
            asks_for_trend
            and asks_for_summary_trend
            and not asks_for_daily_trend
        ):
            candidate_columns = [
                _normalize_text(
                    schema_item.get(
                        "source_column",
                        "",
                    )
                )
                for schema_item in schema
            ]

            candidate_columns = [
                column
                for column in candidate_columns
                if column
            ]

            has_month_column = any(
                column == "month"
                or "month" in column
                for column in candidate_columns
            )

            summary_metric_columns = {
                "invoices",
                "taxable value",
                "gst",
                "invoice value",
                "profit",
            }

            summary_metric_matches = sum(
                1
                for metric in summary_metric_columns
                if metric in candidate_columns
            )

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                }
                and has_month_column
                and summary_metric_matches >= 2
            ):
                score += 1000

        # --------------------------------------------------------
        # MONTHLY RANKING DATASET PREFERENCE
        #
        # Questions such as:
        #   Which month had the highest sales?
        #   Which month had the lowest sales?
        #
        # require month-level historical data.
        #
        # Prefer a monthly summary dataset when it contains:
        #   - Month
        #   - a sales-value metric
        #
        # This prevents tiny/manual datasets from being selected
        # merely because they contain recent sales rows.
        #
        # IMPORTANT:
        # This applies only to highest/lowest month questions.
        # --------------------------------------------------------

        monthly_ranking_query = bool(
            re.search(
                r"\b(?:highest|maximum|most|lowest|minimum|least|bottom)\b",
                normalized_question,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover)\b",
                normalized_question,
            )
            and re.search(
                r"\bmonth\b",
                normalized_question,
            )
        )

        if monthly_ranking_query:

            candidate_columns = [
                _normalize_text(
                    schema_item.get(
                        "source_column",
                        "",
                    )
                )
                for schema_item in schema
            ]

            candidate_columns = [
                column
                for column in candidate_columns
                if column
            ]

            has_month_column = any(
                column == "month"
                or "month" in column
                for column in candidate_columns
            )

            monthly_sales_metrics = {
                "invoice value",
                "invoice total",
                "total amount",
                "sales amount",
                "sale amount",
                "amount",
                "taxable value",
            }

            monthly_metric_matches = sum(
                1
                for metric in monthly_sales_metrics
                if metric in candidate_columns
            )

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                }
                and has_month_column
                and monthly_metric_matches >= 1
            ):
                score += 1000
                
                # ========================================================
        # DETAILED METRIC DATASET PREFERENCE
        #
        # For metric-only questions such as:
        #   Show total quantity sold
        #   What is the average unit price?
        #   What is the total gross amount?
        #
        # Prefer a sufficiently large detailed transaction
        # dataset when the requested metric actually exists.
        #
        # This is dataset-ID independent.
        # ========================================================

        metric_query = bool(
            re.search(
                r"\b(?:quantity|qty|unit\s*price|gross\s*amount|"
                r"discount|taxable\s*amount|gst|cgst|sgst|igst|"
                r"profit|cost|invoice\s*(?:value|total|amount))\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
        )

        if metric_query:
            try:
                row_count = int(
                    dataset.get("row_count", 0) or 0
                )
            except (TypeError, ValueError):
                row_count = 0

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                    "inventory",
                }
                and row_count >= 100
            ):
                candidate_rows = []

                try:
                    candidate_rows = load_dataset_rows(
                        dataset_id
                    )
                except Exception:
                    candidate_rows = []

                metric_resolved = False

                metric_phrases = [
                    "quantity",
                    "qty",
                    "unit price",
                    "gross amount",
                    "discount",
                    "taxable amount",
                    "gst",
                    "cgst",
                    "sgst",
                    "igst",
                    "profit",
                    "cost",
                    "invoice value",
                    "invoice total",
                    "invoice amount",
                ]

                for metric_phrase in metric_phrases:
                    if not re.search(
                        rf"\b{re.escape(metric_phrase)}\b",
                        normalized_question,
                        flags=re.IGNORECASE,
                    ):
                        continue

                    resolved_metric_column = _resolve_column(
                        metric_phrase,
                        dataset,
                        schema,
                        candidate_rows,
                    )

                    if resolved_metric_column:
                        metric_resolved = True
                        break

                if metric_resolved:
                    score += 500
                    score += min(
                        row_count / 20,
                        150,
                    )



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

    # --------------------------------------------------------
    # DATE-SPECIFIC DETAILED DATASET SAFETY
    #
    # Prefer a real detailed transaction dataset when the
    # requested date/period exists there.
    #
    # Do not silently fall back to a tiny test/sample dataset
    # when the requested period does not exist in detailed data.
    # --------------------------------------------------------

    if detailed_transaction_datasets:

        date_query_detected = bool(
            re.search(
                r"\b(?:for|in|during)\b.*?"
                r"\b(?:\d{4}|january|february|march|april|may|"
                r"june|july|august|september|october|november|"
                r"december)\b",
                _normalize_text(question),
                flags=re.IGNORECASE,
            )
        )

        if date_query_detected:

            eligible_detailed_items = []

            for detailed_item in detailed_transaction_datasets:

                detailed_dataset = detailed_item.get(
                    "dataset",
                    {},
                )

                try:
                    detailed_id = int(
                        detailed_dataset.get(
                            "id",
                            -1,
                        )
                    )
                except (TypeError, ValueError):
                    continue

                # Reuse the result from the date scan that
                # already happened during normal dataset
                # selection.
                detailed_period_exists = (
                    date_eligibility_cache.get(
                        detailed_id,
                        False,
                    )
                )

                if detailed_period_exists:
                    eligible_detailed_items.append(
                        detailed_item
                    )

            # ------------------------------------------------
            # CASE 1:
            # A detailed dataset contains the requested
            # period.
            #
            # Therefore do NOT select a tiny test dataset.
            # Select the highest-scoring eligible detailed
            # dataset instead.
            # ------------------------------------------------

            if eligible_detailed_items:

                eligible_ids = {
                    int(
                        item.get(
                            "dataset",
                            {},
                        ).get(
                            "id",
                            -1,
                        )
                    )
                    for item in eligible_detailed_items
                }

                eligible_scored = [
                    item
                    for item in scored
                    if int(item[1]) in eligible_ids
                ]

                if eligible_scored:

                    eligible_scored.sort(
                        key=lambda item: (
                            item[0],
                            item[1],
                        ),
                        reverse=True,
                    )

                    best_score, best_id, best_item = (
                        eligible_scored[0]
                    )

            # ------------------------------------------------
            # CASE 2:
            # No detailed dataset contains the requested
            # period.
            #
            # If normal scoring selected a tiny/test dataset,
            # reject it instead of returning incorrect data.
            # ------------------------------------------------

            else:

                selected_dataset = best_item.get(
                    "dataset",
                    {},
                )

                selected_schema = best_item.get(
                    "schema",
                    [],
                )

                selected_is_detailed = (
                    _is_detailed_transaction_dataset(
                        selected_dataset,
                        selected_schema,
                    )
                )

                if not selected_is_detailed:

                    return {
                        **state,
                        "datasets": datasets,
                        "dataset": {},
                        "schema": [],
                        "dataset_type": None,
                        "dataset_id": None,
                        "error": (
                            "No data is available for the "
                            "requested period in the detailed "
                            "business transaction data."
                        ),
                    }

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
# SQL FAST-PATH ELIGIBILITY
# ============================================================

def _is_simple_sql_aggregate_query(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Determine whether a query can safely use the SQL aggregate
    fast path without loading every dataset row into Python.

    Returns:
        (eligible, aggregate_function, source_column)
    """

    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # Must contain a simple aggregate request.
    # --------------------------------------------------------

    if re.search(
        r"\b(?:by|per|each|wise)\b",
        question_norm,
    ):
        return False, None, None

    # --------------------------------------------------------
    # Do not optimize row/detail/export queries.
    #
    # "invoice" by itself is NOT a detail query.
    #
    # Examples that remain eligible:
    #   average invoice value
    #   maximum invoice total
    #   total invoice amount
    #
    # Examples that must stay on the row-based path:
    #   show invoice rows
    #   list invoices
    #   export invoices
    # --------------------------------------------------------

    if re.search(
        r"\b(?:export|list|display|fetch|return)\b",
        question_norm,
    ):
        return False, None, None

    if re.search(
        r"\b(?:row|rows|record|records|transaction|transactions|"
        r"invoices?)\b",
        question_norm,
    ):
        if not re.search(
            r"\b(?:total|average|avg|mean|maximum|max|highest|"
            r"minimum|min|lowest|sum|how\s+much)\b",
            question_norm,
        ):
            return False, None, None

    # --------------------------------------------------------
    # No date/month/year filters in the first SQL fast path.
    # --------------------------------------------------------

    if re.search(
        r"\b(?:for|in|during|from|between)\b.*?"
        r"\b(?:20\d{2}|january|february|march|april|may|june|"
        r"july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
        question_norm,
    ):
        return False, None, None

    # --------------------------------------------------------
    # Only use schema-confirmed numeric source columns.
    # --------------------------------------------------------

    numeric_columns = []

    for item in schema or []:
        if not isinstance(item, dict):
            continue

        source = item.get("source_column")
        data_type = _normalize_text(
            item.get("data_type")
        )

        if (
            source
            and data_type in {
                "numeric",
                "number",
                "integer",
                "float",
                "decimal",
            }
        ):
            numeric_columns.append(
                str(source)
            )

    if not numeric_columns:
        return False, None, None
    
    # --------------------------------------------------------
    # Grouped customer/product ranking must use the
    # row-based grouped aggregation path, not scalar SQL MAX/MIN.
    #
    # Examples:
    #   Which customer has the highest sales?
    #   Which customer has the lowest sales?
    #   Which product has the highest sales?
    #   Which product has the lowest sales?
    # --------------------------------------------------------

    grouped_sales_ranking = bool(
        re.search(
            r"\b(?:highest|maximum|most|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|product|products|item|items)\b",
            question_norm,
        )
    )

    if grouped_sales_ranking:
        return False, None, None
    
    # --------------------------------------------------------
    # Grouped customer/product profit ranking must also use
    # the row-based grouped aggregation path.
    #
    # Examples:
    #   Which customer has the highest profit?
    #   Which customer has the lowest profit?
    #   Which product has the highest profit?
    #   Which product has the lowest profit?
    # --------------------------------------------------------

    grouped_profit_ranking = bool(
        re.search(
            r"\b(?:highest|maximum|most|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\bprofit\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|party|parties|"
            r"product|products|item|items)\b",
            question_norm,
        )
    )

    grouped_gst_ranking = bool(
        re.search(
            r"\b(?:highest|maximum|most|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:gst|totalgst|total gst)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|party|parties|"
            r"product|products|item|items)\b",
            question_norm,
        )
    )

    if grouped_profit_ranking or grouped_gst_ranking:
        return False, None, None


    # --------------------------------------------------------
    # Detect aggregate function.
    # --------------------------------------------------------

    if re.search(
        r"\b(?:average|avg|mean)\b",
        question_norm,
    ):
        function = "average"

    elif re.search(
        r"\b(?:maximum|max|highest)\b",
        question_norm,
    ):
        function = "max"

    elif re.search(
        r"\b(?:minimum|min|lowest)\b",
        question_norm,
    ):
        function = "min"

    elif re.search(
        r"\b(?:sum|total|how\s+much)\b",
        question_norm,
    ):
        function = "sum"

    else:
        return False, None, None

    # --------------------------------------------------------
    # Resolve explicit business metrics.
    # --------------------------------------------------------

    metric_aliases = {
        "profit": (
            "Profit",
        ),
        "total gst": (
            "TotalGST",
            "Total GST",
            "GST",
        ),
        "gst amount": (
            "TotalGST",
            "Total GST",
            "GST",
        ),
        "gst": (
            "TotalGST",
            "Total GST",
            "GST",
        ),
        "cgst": (
            "CGST",
        ),
        "sgst": (
            "SGST",
        ),
        "igst": (
            "IGST",
        ),
        "discount amount": (
            "DiscountAmt",
            "Discount Amt",
        ),
        "discount": (
            "DiscountAmt",
            "Discount Amt",
        ),
        "taxable amount": (
            "TaxableAmount",
            "Taxable Value",
        ),
        "taxable value": (
            "TaxableAmount",
            "Taxable Value",
        ),
        "quantity": (
            "Qty",
            "Quantity",
        ),
        "qty": (
            "Qty",
            "Quantity",
        ),
    }

    aliases = sorted(
        metric_aliases.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    
    # --------------------------------------------------------
    # EXACT SOURCE-COLUMN MATCH MUST WIN
    #
    # Example:
    #   Show total GST_Rate
    #
    # Must resolve to:
    #   GST_Rate
    #
    # before semantic aliases such as:
    #   GST -> TotalGST
    #
    # This keeps uploaded-column names authoritative.
    # --------------------------------------------------------

    question_compact = re.sub(
        r"\s+",
        "",
        question_norm,
    )

    for source_column in numeric_columns:
        source_text = _normalize_text(
            str(source_column)
        )

        if not source_text:
            continue

        # Exact normalized source-column match.
        if re.search(
            rf"\b{re.escape(source_text)}\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            return True, function, source_column

        # Space-insensitive exact source-column match.
        #
        # Examples:
        #   GST_Rate -> gstrate
        #   InvoiceTotal -> invoicetotal
        #   DiscountAmt -> discountamt
        source_compact = re.sub(
            r"\s+",
            "",
            source_text,
        )

        if (
            source_compact
            and source_compact in question_compact
        ):
            return True, function, source_column

    for alias, possible_columns in aliases:
        if not re.search(
            rf"\b{re.escape(alias)}\b",
            question_norm,
        ):
            continue

        for possible_column in possible_columns:
            possible_norm = _normalize_text(
                possible_column
            )

            for source_column in numeric_columns:
                if (
                    _normalize_text(source_column)
                    == possible_norm
                ):
                    return (
                        True,
                        function,
                        source_column,
                    )

    # --------------------------------------------------------
    # Generic sales / invoice value.
    #
    # "Show total sales"
    # "Show average invoice value"
    # "Show maximum invoice total"
    # --------------------------------------------------------

    sales_candidates = [
        "InvoiceTotal",
        "Invoice Total",
        "Invoice Value",
        "Total Amount",
        "TotalAmount",
        "Sales Amount",
        "SalesAmount",
        "GrossAmount",
        "Gross Amount",
        "Amount",
        "Revenue",
        "Turnover",
    ]

    for candidate in sales_candidates:
        candidate_norm = _normalize_text(candidate)

        for source_column in numeric_columns:
            if (
                _normalize_text(source_column)
                == candidate_norm
            ):
                if re.search(
                    r"\b(?:sales?|revenue|turnover|billing|"
                    r"invoice\s+(?:value|amount|total))\b",
                    question_norm,
                ):
                    return (
                        True,
                        function,
                        source_column,
                    )

    return False, None, None
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
            "error": state.get(
                "error",
                "No dataset was selected.",
            ),
        }

    # ========================================================
    # SQL FAST PATH
    #
    # Simple aggregate queries do not need all dataset rows.
    #
    # Example:
    #   Show total sales
    #   Show total profit
    #   Show total GST
    #   Show average invoice value
    #
    # The eligibility helper only allows safe, unfiltered
    # aggregate queries with schema-confirmed numeric columns.
    # ========================================================

    dataset = state.get("dataset") or {}
    schema = state.get("schema") or []
    question = state.get("question", "")
    
    # ========================================================
    # GENERIC DISTINCT / UNIQUE SQL FAST PATH
    #
    # Examples:
    #   How many unique invoices are there?
    #   How many distinct customers are there?
    #   Show unique products
    #   Show distinct GSTIN values
    #
    # Reuse the existing generic database function:
    # count_distinct_dataset_column()
    #
    # Do NOT hardcode InvoiceNo / PartyName here.
    # ========================================================

    distinct_query = bool(
        re.search(
            r"\b(?:unique|distinct)\b",
            _normalize_text(question),
            flags=re.IGNORECASE,
        )
    )

    if distinct_query:
        try:
            distinct_function, distinct_column = (
                _extract_aggregate(
                    question,
                    dataset,
                    schema,
                    [],
                )
            )

            # If _extract_aggregate resolved a column,
            # use it directly.
            if distinct_column:
                distinct_value = run_sql_distinct_count(
                    dataset_id=int(dataset_id),
                    column_name=distinct_column,
                )

                return {
                    **state,
                    "rows": [],
                    "aggregate_function": "distinct_count",
                    "aggregate_column": distinct_column,
                    "result": {
                        "operation": "distinct_count",
                        "aggregate_function": "distinct_count",
                        "aggregate_column": distinct_column,
                        "value": distinct_value,
                        "distinct_count": distinct_value,
                        "source_rows": int(
                            dataset.get("row_count", 0) or 0
                        ),
                        "filtered_rows": int(
                            dataset.get("row_count", 0) or 0
                        ),
                        "sql_fast_path": True,
                        "sql_distinct_fast_path": True,
                    },
                }

        except Exception as e:
            print(
                "\n[DISTINCT FAST PATH ERROR]",
                type(e).__name__,
                str(e),
            )
            # Safely continue to the existing SQL/row path.
            pass
    try:
        (
            sql_fast_path,
            sql_function,
            sql_column,
        ) = _is_simple_sql_aggregate_query(
            question=question,
            dataset=dataset,
            schema=schema,
        )
    except Exception:
        sql_fast_path = False
        sql_function = None
        sql_column = None

    if (
        sql_fast_path
        and sql_function
        and sql_column
    ):
        try:
            aggregate_value = run_sql_aggregate(
                dataset_id=int(dataset_id),
                column_name=sql_column,
                function=sql_function,
            )

            invoice_count = run_sql_distinct_count(
                dataset_id=int(dataset_id),
                column_name="InvoiceNo",
            )

            customer_count = run_sql_distinct_count(
                dataset_id=int(dataset_id),
                column_name="PartyName",
            )

            return {
                **state,
                "rows": [],
                "aggregate_function": sql_function,
                "aggregate_column": sql_column,
                "result": {
                    "operation": "aggregate",
                    "aggregate_function": sql_function,
                    "aggregate_column": sql_column,
                    "value": aggregate_value,
                    "source_rows": int(
                        dataset.get("row_count", 0) or 0
                    ),
                    "filtered_rows": int(
                        dataset.get("row_count", 0) or 0
                    ),
                    "invoice_count": invoice_count,
                    "customer_count": customer_count,
                    "sql_fast_path": True,
                },
            }

        except Exception:
            # If SQL fast path fails for any reason,
            # safely fall back to the existing row-based path.
            pass

    # ========================================================
    # EXISTING ROW-BASED PATH
    #
    # Keep this unchanged for:
    # - grouped queries
    # - filtered queries
    # - date queries
    # - raw rows
    # - exports
    # - detailed reports
    # - Top-N queries
    # ========================================================

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

def _extract_top_n(
    question: str,
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Detect explicit Top-N / Bottom-N / Highest-N / Lowest-N
    ranking queries.

    Supported examples:

        Show the top 10 invoices
        Show the bottom 5 products

        Show the 10 highest-value invoices
        Show the 5 lowest-profit invoices

        Which 10 customers have the highest sales?
        Which 10 products have the highest sales?
        Which 5 invoices have the highest invoice value?

    Returns:
        (top_n, direction, ranking_type)
    """

    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # 1. "top N" / "bottom N"
    # --------------------------------------------------------

    match = re.search(
        r"\b(top|bottom)\s+(\d+)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if match:
        ranking_word = match.group(1).lower()

        return (
            int(match.group(2)),
            "asc" if ranking_word == "bottom" else "desc",
            ranking_word,
        )

    # --------------------------------------------------------
    # 2. "N highest ..." / "N lowest ..."
    #
    # Examples:
    #   10 highest-value invoices
    #   5 highest-profit invoices
    #   10 lowest-value invoices
    # --------------------------------------------------------

    match = re.search(
        r"\b(\d+)\s+(highest|lowest)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if match:
        top_n = int(match.group(1))
        ranking_word = match.group(2).lower()

        return (
            top_n,
            "desc" if ranking_word == "highest" else "asc",
            ranking_word,
        )

    # --------------------------------------------------------
    # 3. "Which N customers/products have the highest sales?"
    #
    # Examples:
    #   Which 10 customers have the highest sales?
    #   Which 10 products have the highest sales?
    #   Which 5 invoices have the highest invoice value?
    #   Which 3 customers have the lowest profit?
    #
    # The number comes BEFORE the entity name.
    # --------------------------------------------------------

    match = re.search(
        r"\b(?:which|what)\s+(\d+)\s+"
        r"(?:customers?|products?|items?|invoices?|"
        r"transactions?|records?|parties?|categories?|"
        r"suppliers?|vendors?)\b"
        r".*?\b(highest|lowest|most|least)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if match:
        top_n = int(match.group(1))
        ranking_word = match.group(2).lower()

        if ranking_word in (
            "lowest",
            "least",
        ):
            direction = "asc"
        else:
            direction = "desc"

        return (
            top_n,
            direction,
            ranking_word,
        )

    # --------------------------------------------------------
    # 4. More general "N ... highest/lowest" pattern
    #
    # This catches variations such as:
    #
    #   10 customers with highest sales
    #   5 products with lowest profit
    #
    # without changing the normal single-ranking queries.
    # --------------------------------------------------------

    match = re.search(
        r"\b(\d+)\s+"
        r"(?:customers?|products?|items?|invoices?|"
        r"transactions?|records?|parties?|categories?|"
        r"suppliers?|vendors?)\b"
        r".*?\b(highest|lowest|most|least)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if match:
        top_n = int(match.group(1))
        ranking_word = match.group(2).lower()

        direction = (
            "asc"
            if ranking_word in (
                "lowest",
                "least",
            )
            else "desc"
        )

        return (
            top_n,
            direction,
            ranking_word,
        )

    return (
        None,
        None,
        None,
    )

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
    question_norm = _normalize_text(question)
    # ========================================================
    # SQL FAST-PATH RESULT
    #
    # Simple aggregate queries may already have their result
    # calculated directly by SQLite in load_dynamic_data().
    #
    # In that case rows is intentionally empty.
    # Do not treat that as an empty dataset.
    # ========================================================

    existing_result = state.get("result") or {}

    if (
        isinstance(existing_result, dict)
        and existing_result.get("sql_fast_path") is True
        and existing_result.get("operation") in {
            "aggregate",
            "distinct_count",
        }
    ):
        return {
            **state,
            "result": existing_result,
            "intent": (
                "count"
                if existing_result.get("operation") == "distinct_count"
                else "aggregate"
            ),
            "error": None,
        }
        

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
    
    # --------------------------------------------------------
    # DISTINCT / UNIQUE VALUE QUERY
    #
    # These queries must not be interpreted as ordinary
    # categorical-filter queries.
    #
    # Examples:
    #   Show distinct InvoiceNo values
    #   Show unique InvoiceNo values
    #   Show distinct products
    #   Show unique GSTIN values
    # --------------------------------------------------------

    # --------------------------------------------------------
    # DISTINCT / UNIQUE VALUE QUERY
    # --------------------------------------------------------

    distinct_values_requested = bool(
        re.search(
            r"\b(?:unique|distinct)\b",
            _normalize_text(question),
            flags=re.IGNORECASE,
        )
    )

    if distinct_values_requested:
        numeric_filters = []
        categorical_filters = []
        date_filters = []
    else:
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

    time_grouping = _extract_time_grouping(
        question,
        dataset,
        schema,
        rows,
    )

    group_by = _extract_group_by(
        question,
        dataset,
        schema,
        rows,
    )

    # Temporal grouping takes priority over normal grouping.
    #
    # Examples:
    #   Show sales day wise
    #   Show sales month wise
    #   Show sales year wise
    #   Show sales trend
    #
    # Keep the REAL source date column in group_by.
    if time_grouping:
        group_by = time_grouping["column"]

    aggregate_function, aggregate_column = (
        _extract_aggregate(
            question,
            dataset,
            schema,
            rows,
        )
    )
   # --------------------------------------------------------
    # InvoiceNo identifier protection
    #
    # Prevent "No" inside "InvoiceNo" from becoming:
    # InterState = No
    #
    # Applies to:
    #   Show total InvoiceNo
    #   Show all InvoiceNo values
    # --------------------------------------------------------

    invoice_identifier_requested = bool(
        (
            aggregate_column
            and _normalize_text(str(aggregate_column)) in {
                "invoiceno",
                "invoice no",
                "invoice number",
            }
        )
        or any(
            _normalize_text(str(column)) in {
                "invoiceno",
                "invoice no",
                "invoice number",
            }
            for column in (requested_columns or [])
        )
    )

    invoice_number_query = bool(
        invoice_identifier_requested
        and (
            re.search(
                r"\btotal\s+(?:invoice\s*no|invoiceno|invoice\s+number)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b(?:show|give|list|display|return|fetch|provide)\b"
                r".*?\b(?:all|every)\b"
                r".*?\b(?:invoice\s*no|invoiceno|invoice\s+number)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )
    )

    if invoice_number_query:
        filters = [
            item
            for item in filters
            if _normalize_text(str(item.get("column", "")))
            not in {
                "interstate",
            }
            or _normalize_text(str(item.get("value", ""))) != "no"
        ]
    # --------------------------------------------------------
    # DISTINCT VALUE QUERY
    #
    # Examples:
    #   Show all PaymentMode values
    #   Show all Product values
    #   Show all GSTIN values
    #
    # Reuse the existing COUNT-with-column mechanism so the
    # result contains each distinct value and its frequency.
    # --------------------------------------------------------

    distinct_values_requested = bool(
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide)\b"
            r".*?\b(?:all|every|unique|distinct)\b"
            r".*?\bvalues?\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        or
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide)\b"
            r".*?\b(?:unique|distinct)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if distinct_values_requested and requested_columns:
        if len(requested_columns) == 1:
            aggregate_function = "count"
            aggregate_column = requested_columns[0]

            # DISTINCT-VALUE queries should count each value
            # directly and must not become date/grouped queries.
            #
            # Examples:
            #   Show all Month values
            #   Show all GSTIN values
            #   Show all PaymentMode values
            #
            # "Month" must mean distinct Month values, not:
            #   GROUP BY Date
            #
            # This is generic and does not depend on any
            # particular column name or dataset.
            group_by_column = None
            group_by = None
            date_group_by = None
            time_group_by = None
    # --------------------------------------------------------
    # Ranking questions.
    #
    # "Which customer has highest sales?"
    # means:
    #   GROUP BY customer
    #   SUM sales
    #   ORDER BY total sales DESC
    #
    # Ordinary "highest sale" queries are not changed because
    # they do not have a group_by column.
    # --------------------------------------------------------

    question_norm = _normalize_text(
        question
    )
    
    top_n, top_direction, top_ranking_type = _extract_top_n(
         question
    )
    # --------------------------------------------------------
    # RAW ROW REQUEST
    #
    # Examples:
    #   Show all sales records
    #   Show all sales rows
    #   Give me all sales records
    #   List all invoices
    #
    # These requests must return the underlying rows instead
    # of being interpreted as a sales aggregation.
    # --------------------------------------------------------

    raw_rows_requested = bool(
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide|export)\b"
            r".*?\b(?:all|every)\b"
            r".*?\b(?:rows?|records?|transactions?|invoices?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        or
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide|export)\b"
            r".*?\b(?:rows?|records?|transactions?|invoices?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    # --------------------------------------------------------
    # REQUESTED RAW ROW COUNT
    #
    # Examples:
    #   Give me 100 sales rows
    #   Show 500 sales records
    #   Give me 8305 sales rows
    #   List 200 invoices
    #
    # The number is a row limit, not a column name.
    # --------------------------------------------------------

    requested_row_count = None

    row_count_match = re.search(
        r"\b(\d[\d,]*)\s+"
        r"(?:sales?|rows?|records?|transactions?|invoices?|"
        r"purchases?|expenses?|payments?|orders?)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if raw_rows_requested and row_count_match:
        try:
            requested_row_count = int(
                row_count_match.group(1).replace(",", "")
            )
        except (TypeError, ValueError):
            requested_row_count = None

        if requested_row_count is not None:
            requested_row_count = max(
                requested_row_count,
                0,
            )

    if raw_rows_requested:
        aggregate_function = None
        aggregate_column = None
        group_by = None
        time_grouping = None

    ranking_group_query = bool(
        group_by
        and re.search(
            r"\b(?:highest|maximum|most|top)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
    )

    lowest_ranking_group_query = bool(
        group_by
        and re.search(
            r"\b(?:lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst)\b",
            question_norm,
        )
    )

    if ranking_group_query or lowest_ranking_group_query:
        aggregate_function = "sum"

        # Customer/product sales ranking must aggregate
        # the invoice value, not the individual invoice maximum.
        ranking_sales_columns = [
            "Invoice Value",
            "InvoiceTotal",
            "Invoice Total",
            "Total Amount",
            "TotalAmount",
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
            "Revenue",
            "Turnover",
            "Taxable Value",
            "TaxableAmount",
        ]

        for preferred in ranking_sales_columns:
            preferred_norm = _normalize_text(preferred)

            for column in schema or []:
                if not isinstance(column, dict):
                    continue

                source_column = column.get("source_column")
                data_type = _normalize_text(
                    column.get("data_type")
                )

                if not source_column:
                    continue

                if data_type not in {
                    "numeric",
                    "number",
                    "integer",
                    "float",
                    "decimal",
                }:
                    continue

                if _normalize_text(source_column) == preferred_norm:
                    aggregate_column = str(source_column)
                    break

            if aggregate_column:
                break
    # --------------------------------------------------------
    # Attendance summary default.
    #
    # "attendance status summary" means:
    #   GROUP BY Attendance Status
    #   COUNT rows in each status
    # --------------------------------------------------------

        if (
            group_by
            and aggregate_function is None
            and "summary" in question.lower()
            and (
                 dataset.get("data_type") == "attendance"
                 or dataset.get("dataset_type") == "attendance"
                )
        ):
            aggregate_function = "count"
            aggregate_column = None

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
    # Resolve the sales value column for grouped ranking.
    #
    # Example:
    #   Which customer has the highest sales?
    #   Which product has the lowest sales?
    #
    # These queries must SUM InvoiceTotal by the group.
    # --------------------------------------------------------

    if (
        (ranking_group_query or lowest_ranking_group_query)
        and group_by
        and not aggregate_column
    ):
        ranking_sales_columns = [
            "InvoiceTotal",
            "Invoice Total",
            "Invoice Value",
            "Total Amount",
            "TotalAmount",
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
            "Revenue",
            "Turnover",
            "Taxable Amount",
            "TaxableAmount",
        ]

        available_columns = set()

        for row in filtered_rows:
            if isinstance(row, dict):
                available_columns.update(
                    str(key)
                    for key in row.keys()
                    if key is not None
                )

        for preferred in ranking_sales_columns:
            preferred_norm = _normalize_text(preferred)

            for column in available_columns:
                if _normalize_text(column) == preferred_norm:
                    aggregate_column = column
                    break

            if aggregate_column:
                break

    # --------------------------------------------------------
    # APPLY REQUESTED RAW ROW LIMIT
    #
    # Examples:
    #   Give me all sales rows
    #       -> keep all matching rows
    #
    #   Give me 100 sales rows
    #       -> keep first 100 matching rows
    #
    #   Give me 8305 sales rows
    #       -> keep first 8305 matching rows
    #
    #   Give me 10000 sales rows
    #       -> keep all available matching rows
    #
    # This applies ONLY to raw-row requests.
    # Normal aggregate/group-by queries are unchanged.
    # --------------------------------------------------------

    if raw_rows_requested and requested_row_count is not None:
        filtered_rows = filtered_rows[
            :requested_row_count
        ]
    # --------------------------------------------------------
    # Explicit Top-N row ranking.
    #
    # Examples:
    #   Show the 10 highest-value invoices
    #   Show the 10 lowest-value invoices
    #   Show the 5 highest-profit invoices
    #
    # This is different from grouped ranking:
    #
    #   "Which customer has highest sales?"
    #       -> GROUP BY customer
    #
    #   "Show the 10 highest-value invoices"
    #       -> SORT individual rows
    # --------------------------------------------------------


    # --------------------------------------------------------
    # Date-to-date comparison.
    #
    # Examples:
    #   Compare sales between 2026-09-10 and 2026-09-13
    #   Compare sales from 2026-09-10 to 2026-09-13
    #   Compare sales 2026-09-10 vs 2026-09-13
    #
    # This is handled before normal grouping so the two
    # individual dates can be calculated independently.
    # --------------------------------------------------------

    date_comparison = _extract_date_comparison(
        question,
        dataset,
        schema,
        rows,
    )
    
        # --------------------------------------------------------
    # Execute date-to-date comparison.
    # --------------------------------------------------------

    if date_comparison:
        comparison_column = date_comparison["column"]
        comparison_date_1 = date_comparison["date_1"]
        comparison_date_2 = date_comparison["date_2"]

        date_1_rows = []
        date_2_rows = []

        for row in rows:
            parsed_date = _parse_date(
                row.get(comparison_column)
            )

            if not parsed_date:
                continue

            row_date = parsed_date.strftime(
                "%Y-%m-%d"
            )

            if row_date == comparison_date_1:
                date_1_rows.append(row)

            if row_date == comparison_date_2:
                date_2_rows.append(row)

        # ----------------------------------------------------
        # Resolve the numeric sales/amount column.
        # ----------------------------------------------------

        comparison_column_value = _resolve_column(
            "sales",
            dataset,
            schema,
            filtered_rows,
        )

        if not comparison_column_value:
            comparison_column_value = _resolve_column(
                "amount",
                dataset,
                schema,
                filtered_rows,
            )

        # ----------------------------------------------------
        # Calculate totals.
        # ----------------------------------------------------

        def _comparison_total(
            comparison_rows,
        ):
            total = 0.0

            for comparison_row in comparison_rows:
                value = comparison_row.get(
                    comparison_column_value
                )

                if value is None:
                    continue

                try:
                    if isinstance(value, str):
                        cleaned = re.sub(
                            r"[?,\s]",
                            "",
                            value,
                        )
                    else:
                        cleaned = value

                    total += float(cleaned)

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            return total

        date_1_total = _comparison_total(
            date_1_rows
        )

        date_2_total = _comparison_total(
            date_2_rows
        )

        difference = (
            date_2_total - date_1_total
        )

        if date_1_total != 0:
            percentage_change = (
                difference
                / date_1_total
            ) * 100
        else:
            percentage_change = None

        result = {
            "operation": "date_comparison",
            "comparison_column": comparison_column,
            "date_1": comparison_date_1,
            "date_2": comparison_date_2,
            "value_1": date_1_total,
            "value_2": date_2_total,
            "difference": difference,
            "percentage_change": percentage_change,
            "rows": [
                {
                    "Date": comparison_date_1,
                    "Sales": date_1_total,
                },
                {
                    "Date": comparison_date_2,
                    "Sales": date_2_total,
                },
            ],
            "count": 2,
            "source_rows": len(rows),
            "filtered_rows": len(date_1_rows) + len(date_2_rows),
        }

        return {
            **state,
            "intent": "date_comparison",
            "requested_columns": [],
            "unavailable_columns": [],
            "filters": filters,
            "group_by": None,
            "aggregate_function": "sum",
            "aggregate_column": comparison_column_value,
            "result": result,
        }
        # --------------------------------------------------------
    # Period-to-period comparison.
    #
    # Examples:
    #   Compare September 2026 with August 2026
    #   Compare September sales with August sales
    #   Compare 2026 sales with 2025 sales
    #   Show month over month sales growth
    # --------------------------------------------------------

    period_comparison = _extract_period_comparison(
        question,
        dataset,
        schema,
        rows,
    )

    if period_comparison:
        comparison_column = period_comparison["column"]
        period_type = period_comparison["period_type"]
        period_1 = period_comparison["period_1"]
        period_2 = period_comparison["period_2"]

        period_1_rows = []
        period_2_rows = []

        for row in rows:
            parsed_date = _parse_date(
                row.get(comparison_column)
            )

            if not parsed_date:
                continue

            if period_type == "month":
                row_period = parsed_date.strftime(
                    "%Y-%m"
                )
            else:
                row_period = parsed_date.strftime(
                    "%Y"
                )

            if row_period == period_1:
                period_1_rows.append(row)

            if row_period == period_2:
                period_2_rows.append(row)

        # ----------------------------------------------------
        # Resolve numeric sales/amount column.
        # ----------------------------------------------------

        comparison_column_value = _resolve_column(
            "sales",
            dataset,
            schema,
            rows,
        )

        if not comparison_column_value:
            comparison_column_value = _resolve_column(
                "amount",
                dataset,
                schema,
                rows,
            )

        def _period_total(comparison_rows):
            total = 0.0

            for comparison_row in comparison_rows:
                value = comparison_row.get(
                    comparison_column_value
                )

                if value is None:
                    continue

                try:
                    if isinstance(value, str):
                        cleaned = re.sub(
                            r"[?,\s]",
                            "",
                            value,
                        )
                    else:
                        cleaned = value

                    total += float(cleaned)

                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            return total

        period_1_total = _period_total(
            period_1_rows
        )

        period_2_total = _period_total(
            period_2_rows
        )

        # ----------------------------------------------------
        # Do not treat a completely missing period as ?0.
        # ----------------------------------------------------

        period_1_has_data = bool(
            period_1_rows
        )

        period_2_has_data = bool(
            period_2_rows
        )

        difference = None
        percentage_change = None

        if (
            period_1_has_data
            and period_2_has_data
        ):
            # period_1 = starting/older period
            # period_2 = comparison/newer period
            #
            # Example:
            # August  = 15,000
            # September = 30,000
            #
            # Change = 30,000 - 15,000
            #        = +15,000
            difference = (
                period_2_total
                - period_1_total
            )

            # Percentage change is calculated relative
            # to the starting period.
            if period_1_total != 0:
                percentage_change = (
                    difference
                    / period_1_total
                ) * 100

        result = {
            "operation": "period_comparison",
            "comparison_column": comparison_column,
            "period_type": period_type,
            "period_1": period_1,
            "period_2": period_2,
            "value_1": (
                period_1_total
                if period_1_has_data
                else None
            ),
            "value_2": (
                period_2_total
                if period_2_has_data
                else None
            ),
            "difference": difference,
            "percentage_change": percentage_change,
            "period_1_has_data": period_1_has_data,
            "period_2_has_data": period_2_has_data,
            "rows": [
                {
                    "Period": period_1,
                    "Sales": (
                        period_1_total
                        if period_1_has_data
                        else None
                    ),
                },
                {
                    "Period": period_2,
                    "Sales": (
                        period_2_total
                        if period_2_has_data
                        else None
                    ),
                },
            ],
            "count": 2,
            "source_rows": len(rows),
            "filtered_rows": (
                len(period_1_rows)
                + len(period_2_rows)
            ),
        }

        return {
            **state,
            "intent": "period_comparison",
            "requested_columns": [],
            "unavailable_columns": [],
            "filters": [],
            "group_by": None,
            "aggregate_function": "sum",
            "aggregate_column": comparison_column_value,
            "result": result,
        }

    # --------------------------------------------------------
    # Employee-level query on attendance data.
    #
    # Keep daily attendance rows for attendance queries,
    # but return one row per employee for employee queries.
    # --------------------------------------------------------

    employee_level_query = _is_employee_level_query(
        question,
        dataset,
    )

    if employee_level_query:
        filtered_rows = _deduplicate_employee_rows(
            filtered_rows
        )
    # --------------------------------------------------------
    # EMPLOYEE ATTENDANCE SUMMARY
    #
    # Example:
    #   show attendance for EMP001
    #
    # After Employee ID filtering, summarize the attendance
    # statuses instead of returning 31 raw daily rows.
    # --------------------------------------------------------

    employee_attendance_summary = (
        _normalize_text(
            dataset.get("data_type")
        ) == "attendance"
        and bool(
            re.search(
                r"\bEMP\d+\b",
                question,
                flags=re.IGNORECASE,
            )
        )
        and bool(
            re.search(
                r"\battendance\b",
                _normalize_text(question),
            )
        )
    )

    if employee_attendance_summary:
        attendance_column = _resolve_column(
            "attendance status",
            dataset,
            schema,
            filtered_rows,
        )

        if attendance_column:
            grouped = _group_aggregate(
                filtered_rows,
                attendance_column,
                "count",
                None,
            )

            result = {
                "operation": "employee_attendance_summary",
                "group_by": attendance_column,
                "aggregate_function": "count",
                "aggregate_column": None,
                "rows": grouped,
                "count": len(grouped),
                "source_rows": len(rows),
                "filtered_rows": len(filtered_rows),
            }

            return {
                **state,
                "intent": "group_aggregate",
                "requested_columns": [],
                "unavailable_columns": [],
                "filters": filters,
                "group_by": attendance_column,
                "aggregate_function": "count",
                "aggregate_column": None,
                "result": result,
            }

    # --------------------------------------------------------
    # Complete report request.
    #
    # Examples:
    #   Complete sales report
    #   Full sales report
    #   Detailed sales report
    #   Show complete sales report
    #
    # These are row-level report requests.
    # Do NOT convert them into SUM().
    # --------------------------------------------------------

    question_norm = _normalize_text(
        question
    )

    complete_report_query = bool(
        re.search(
            r"\b(?:complete|full|detailed|all)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and re.search(
            r"\breport\b",
            question_norm,
        )
    )

    if complete_report_query:
        requested_columns = _dataset_columns(
            dataset,
            schema,
            filtered_rows,
        )

        result = {
            "operation": "rows",
            "rows": filtered_rows,
            "count": len(filtered_rows),
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
        }

        return {
            **state,
            "intent": "rows",
            "requested_columns": requested_columns,
            "unavailable_columns": [],
            "filters": filters,
            "result": result,
        }
    
    # --------------------------------------------------------
    # CUSTOMER / PRODUCT SALES RANKING
    # --------------------------------------------------------
    #
    # Examples:
    #   Which customer has the highest sales?
    #   Which customer has the lowest sales?
    #   Which product has the highest sales?
    #   Which product has the lowest sales?
    #
    # These must aggregate sales BY customer/product first.
    # They must NOT use MAX/MIN on individual InvoiceTotal
    # rows.
    # --------------------------------------------------------

    customer_product_sales_ranking = bool(
        re.search(
            r"\b(?:highest|maximum|most|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|product|products|item|items)\b",
            question_norm,
        )
        and not top_n
    )

    if customer_product_sales_ranking:

        if re.search(
            r"\b(?:customer|customers)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "customer",
                dataset,
                schema,
                filtered_rows,
            )

            if not group_by:
                group_by = _resolve_column(
                    "party name",
                    dataset,
                    schema,
                    filtered_rows,
                )

        elif re.search(
            r"\b(?:product|products|item|items)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "product",
                dataset,
                schema,
                filtered_rows,
            )

        aggregate_function = "sum"

        # Prefer the actual transaction value column.
        # The sales dataset uses InvoiceTotal.
        aggregate_column = None

        preferred_sales_columns = [
            "InvoiceTotal",
            "Invoice Total",
            "Invoice Value",
            "Total Amount",
            "TotalAmount",
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
            "Revenue",
            "Turnover",
            "Taxable Amount",
            "TaxableAmount",
        ]

        available_columns = set()

        for row in filtered_rows:
            if isinstance(row, dict):
                available_columns.update(
                    str(key)
                    for key in row.keys()
                    if key is not None
                )

        for preferred in preferred_sales_columns:
            preferred_norm = _normalize_text(preferred)

            for column in available_columns:
                if _normalize_text(column) == preferred_norm:
                    aggregate_column = column
                    break

            if aggregate_column:
                break
        
    # --------------------------------------------------------
    # TOP-N INDIVIDUAL ROW RANKING
    # --------------------------------------------------------
    #
    # This must run before normal aggregation.
    #
    # Example:
    #   Show the 10 highest-value invoices
    #
    # Result:
    #   ORDER BY InvoiceTotal DESC
    #   LIMIT 10
    #
    # It must NOT become:
    #   MAX(InvoiceNo)
    #
    # because "invoice" identifies the row/entity,
    # while "value" identifies the metric.
    # --------------------------------------------------------

    top_n_row_query = bool(
        top_n
        and not group_by
        and re.search(
            r"\b(?:invoice|invoices|transaction|transactions|record|records)\b",
            question_norm,
        )
    )

    if top_n_row_query:

        ranking_column = None

        # ----------------------------------------------------
        # Highest/lowest profit
        # ----------------------------------------------------

        if re.search(
            r"\bprofit\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "profit",
                dataset,
                schema,
                filtered_rows,
            )

        # ----------------------------------------------------
        # Unit price
        # ----------------------------------------------------

        elif re.search(
            r"\b(?:unit\s+price|price)\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "unit price",
                dataset,
                schema,
                filtered_rows,
            )

            if not ranking_column:
                ranking_column = _resolve_column(
                    "price",
                    dataset,
                    schema,
                    filtered_rows,
                )

        # ----------------------------------------------------
        # Invoice value / sales value
        #
        # "highest-value invoices"
        # "lowest-value invoices"
        # "top 10 invoices by sales"
        # ----------------------------------------------------

        else:

            for candidate in (
                "invoice total",
                "invoice value",
                "sales",
                "revenue",
                "billing",
                "turnover",
                "total amount",
                "amount",
            ):
                ranking_column = _resolve_column(
                    candidate,
                    dataset,
                    schema,
                    filtered_rows,
                )

                if ranking_column:
                    break

        # ----------------------------------------------------
        # If a ranking column was found, sort the INDIVIDUAL
        # rows and limit the result.
        # ----------------------------------------------------

        if ranking_column:

            ranked_rows = []

            for row in filtered_rows:

                value = row.get(
                    ranking_column
                )

                numeric_value = _to_number(
                    value
                )

                if numeric_value is None:
                    continue

                ranked_rows.append(
                    (
                        numeric_value,
                        row,
                    )
                )

            ranked_rows.sort(
                key=lambda item: item[0],
                reverse=(
                    top_direction != "asc"
                ),
            )

            selected_rows = [
                row
                for _, row in ranked_rows[
                    :top_n
                ]
            ]

            result = {
                "operation": "top_n_rows",
                "ranking_column": ranking_column,
                "ranking_direction": top_direction,
                "top_n": top_n,
                "rows": selected_rows,
                "count": len(selected_rows),
                "source_rows": len(rows),
                "filtered_rows": len(filtered_rows),
            }

            return {
                **state,
                "intent": "rows",
                "requested_columns": requested_columns,
                "unavailable_columns": unavailable_columns,
                "filters": filters,
                "result": result,
                "aggregate_function": None,
                "aggregate_column": ranking_column,
            }

    # --------------------------------------------------------
    # Group + aggregate.
    # --------------------------------------------------------

    if group_by and aggregate_function:
        grouped = _group_aggregate(
            filtered_rows,
            group_by,
            aggregate_function,
            aggregate_column,
            time_period=(
                time_grouping.get("period")
                if time_grouping
                else None
            ),
        )

        # --------------------------------------------------------
        # Lowest ranking query.
        #
        # _group_aggregate() normally sorts numeric results
        # from highest to lowest.
        #
        # For:
        #   Which day had the lowest sales?
        #
        # we need the smallest grouped sales value first.
        # --------------------------------------------------------

        if lowest_ranking_group_query or top_direction == "asc":
            def _group_numeric_value(row):
                if not isinstance(row, dict):
                    return 0.0

                for key, value in row.items():
                    if key == group_by:
                        continue

                    try:
                        if value is None:
                            continue

                        return float(
                            str(value)
                            .replace(",", "")
                            .replace("₹", "")
                            .replace("$", "")
                            .strip()
                        )
                    except (TypeError, ValueError):
                        continue

                return 0.0

            grouped.sort(
                key=_group_numeric_value
            )

        # ----------------------------------------------------
        # SINGLE GROUPED RANKING
        #
        # Examples:
        #   Which product has the highest profit?
        #   Which product has the lowest profit?
        #
        # _group_aggregate() already sorts descending.
        # For lowest-profit queries we explicitly sort
        # ascending first.
        # ----------------------------------------------------

        profit_ranking_group_query = bool(
            re.search(
                r"\b(?:highest|maximum|most|lowest|minimum|least)\b",
                question_norm,
            )
            and re.search(
                r"\bprofit\b",
                question_norm,
            )
        )

        if profit_ranking_group_query:

            if re.search(
                r"\b(?:lowest|minimum|least)\b",
                question_norm,
            ):
                grouped.sort(
                    key=lambda row: float(
                        row.get("Total Profit", 0) or 0
                    )
                )
            else:
                grouped.sort(
                    key=lambda row: float(
                        row.get("Total Profit", 0) or 0
                    ),
                    reverse=True,
                )

            # Keep only one row for:
            #   Which customer has the highest profit?
            #   Which product has the lowest profit?
            #
            # Do NOT reduce explicit Top-N / Bottom-N queries.
            if not top_n:
                grouped = grouped[:1]

        # ----------------------------------------------------
        # Explicit Top-N grouped ranking.
        #
        # Examples:
        #   Show the top 3 customers by sales
        #   Show the top 3 products by sales
        #
        # _group_aggregate() already calculates the grouped
        # sales values. Here we only limit the ranked groups.
        # ----------------------------------------------------

        if top_n:

            if top_direction == "asc":

                grouped = grouped[
                    :top_n
                ]

            else:

                grouped = grouped[
                    :top_n
                ]

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
    # Explicit column requests take priority over inferred
    # aggregation.
    #
    # Example:
    #   give me a sales report with customer, product and amount
    #
    # requested_columns:
    #   Party Name, Product, Total Amount
    #
    # This is a row-level report, not a SUM query.
    # --------------------------------------------------------

    explicit_projection = len(
         requested_columns
    ) >= 2

    if explicit_projection:
        aggregate_function = None
        aggregate_column = None
    
        # --------------------------------------------------------
    # Multi-metric aggregate.
    #
    # Example:
    #   Show total sales, total GST and total discount
    #   for ABC Traders in September 2026
    #
    # This must run before explicit_projection because the
    # query intentionally requests multiple aggregated metrics,
    # not multiple row-level columns.
    # --------------------------------------------------------

    multi_aggregates = _extract_multi_aggregate(
        question,
        dataset,
        schema,
        filtered_rows,
    )

    if multi_aggregates:

        aggregate_rows = {}
        aggregate_results = []

        for item in multi_aggregates:

            function = item["function"]
            column = item["column"]

            values = []

            for row in filtered_rows:

                value = row.get(column)

                if value is None:
                    continue

                numeric_value = _to_number(
                    value
                )

                if numeric_value is not None:
                    values.append(
                        numeric_value
                    )

            if function == "sum":
                metric_value = sum(values)

            elif function == "average":
                metric_value = (
                    sum(values) / len(values)
                    if values
                    else 0.0
                )

            elif function == "max":
                metric_value = (
                    max(values)
                    if values
                    else 0.0
                )

            elif function == "min":
                metric_value = (
                    min(values)
                    if values
                    else 0.0
                )

            else:
                continue

            # Keep the latest value for backward compatibility.
            aggregate_rows[column] = metric_value

            # Keep every requested aggregation separately.
            aggregate_results.append(
                {
                    "function": function,
                    "column": column,
                    "value": metric_value,
                }
            )

        if aggregate_rows:

         result = {
            "operation": "multi_aggregate",
            "aggregates": aggregate_rows,
            "aggregate_metrics": multi_aggregates,
            "aggregate_results": aggregate_results,
            "rows": [
                aggregate_rows
            ],
            "count": 1,
            "source_rows": len(rows),
            "filtered_rows": len(filtered_rows),
        }

        return {
                **state,
                "intent": "aggregate",
                "requested_columns": [
                    item["column"]
                    for item in multi_aggregates
                ],
                "unavailable_columns": unavailable_columns,
                "filters": filters,
                "aggregate_function": "multi",
                "aggregate_column": None,
                "result": result,
            }

    # --------------------------------------------------------
    # --------------------------------------------------------
    # Employee-level attendance projection.
    #
    # Generic employee queries should not expose the
    # first attendance day for each employee.
    #
    # Example:
    #   show all employees
    #
    # Return employee identity fields only.
    # --------------------------------------------------------

    if employee_level_query and not requested_columns:
        employee_columns = []

        for column_name in [
            "Employee ID",
            "Employee Name",
            "Department",
        ]:
            resolved_column = _resolve_column(
                column_name,
                dataset,
                schema,
                filtered_rows,
            )

            if resolved_column:
                employee_columns.append(
                    resolved_column
                )

        if employee_columns:
            projected_rows = [
                {
                    column: row.get(column)
                    for column in employee_columns
                }
                for row in filtered_rows
            ]

            result = {
                "operation": "projection",
                "rows": projected_rows,
                "count": len(projected_rows),
                "source_rows": len(rows),
                "filtered_rows": len(filtered_rows),
            }

            return {
                **state,
                "intent": "projection",
                "requested_columns": employee_columns,
                "unavailable_columns": [],
                "filters": filters,
                "result": result,
            }

        # Aggregate.
    # --------------------------------------------------------

    aggregate = {}

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

        # --------------------------------------------------------
        # Preserve rows generated by categorical COUNT.
        # --------------------------------------------------------

    if aggregate_function:

        if (
            aggregate_function == "count"
            and aggregate.get("column")
        ):
            result["rows"] = aggregate.get(
                "rows",
                [],
            )

        elif aggregate_function in (
            "max",
            "min",
        ):
            result["rows"] = []

        else:
            result["rows"] = filtered_rows

    else:
        # No aggregate was detected.
        # Return a safe empty result instead of
        # referencing an uninitialized variable.
        result = {
            "operation": "rows",
            "rows": filtered_rows,
            "count": len(filtered_rows),
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
    # ----------------------------------------------------
    # SQL fast-path aggregate results
    # ----------------------------------------------------
    # SQL aggregate queries intentionally do not load
    # individual rows into Python. The aggregate value is
    # already available in result["value"].
    #
    # Do not treat result_rows=[] as an empty dataset.
    # The existing aggregate formatting below can handle
    # this result normally.
    # ----------------------------------------------------

    sql_fast_path = bool(
        result.get("sql_fast_path")
        and result.get("operation") == "aggregate"
    )
    # --------------------------------------------------------
    # Date-to-date comparison answer.
    # --------------------------------------------------------

    if result.get("operation") == "date_comparison":
        date_1 = result.get("date_1")
        date_2 = result.get("date_2")
        value_1 = result.get("value_1", 0)
        value_2 = result.get("value_2", 0)
        difference = result.get("difference", 0)
        percentage_change = result.get(
            "percentage_change"
        )

        try:
            value_1_text = f"\u20b9{float(value_1):,.2f}"
        except (TypeError, ValueError):
            value_1_text = str(value_1)

        try:
            value_2_text = f"\u20b9{float(value_2):,.2f}"
        except (TypeError, ValueError):
            value_2_text = str(value_2)

        try:
            difference_text = f"\u20b9{abs(float(difference)):,.2f}"
        except (TypeError, ValueError):
            difference_text = str(abs(difference))

        if percentage_change is not None:
            try:
                percentage_text = (
                    f"{abs(float(percentage_change)):.2f}%"
                )
            except (TypeError, ValueError):
                percentage_text = str(
                    abs(percentage_change)
                )
        else:
            percentage_text = "N/A"

        if difference > 0:
            change_word = "increased"
        elif difference < 0:
            change_word = "decreased"
        else:
            change_word = "remained unchanged"

        if difference == 0:
            change_sentence = (
                "Sales remained unchanged between "
                f"{date_1} and {date_2}."
            )
        else:
            change_sentence = (
                f"Sales {change_word} by "
                f"{difference_text} "
                f"({percentage_text}) from "
                f"{period_1} to {period_2}."
            )

        answer = (
            "Sales comparison:\n\n"
            f"- {date_1}: {value_1_text}\n"
            f"- {date_2}: {value_2_text}\n\n"
            f"{change_sentence}"
        )

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }
        
    # --------------------------------------------------------
    # Period-to-period comparison answer.
    # --------------------------------------------------------

    if result.get("operation") == "period_comparison":
        period_1 = result.get("period_1")
        period_2 = result.get("period_2")

        value_1 = result.get("value_1")
        value_2 = result.get("value_2")

        difference = result.get(
            "difference"
        )

        percentage_change = result.get(
            "percentage_change"
        )

        period_1_has_data = result.get(
            "period_1_has_data",
            False,
        )

        period_2_has_data = result.get(
            "period_2_has_data",
            False,
        )

        # ----------------------------------------------------
        # Missing period handling.
        # ----------------------------------------------------

        if (
            not period_1_has_data
            or not period_2_has_data
        ):
            missing_periods = []

            if not period_1_has_data:
                missing_periods.append(
                    str(period_1)
                )

            if not period_2_has_data:
                missing_periods.append(
                    str(period_2)
                )

            missing_text = ", ".join(
                missing_periods
            )

            answer = (
                "Sales period comparison:\n\n"
                f"- {period_1}: "
                + (
                    f"\u20b9{float(value_1):,.2f}"
                    if value_1 is not None
                    else "No data"
                )
                + "\n"
                f"- {period_2}: "
                + (
                    f"\u20b9{float(value_2):,.2f}"
                    if value_2 is not None
                    else "No data"
                )
                + "\n\n"
                f"No comparison was calculated because "
                f"there is no data for: {missing_text}."
            )

            return {
                **state,
                "answer": answer,
                "result": result,
                "error": None,
            }

        # ----------------------------------------------------
        # Format values.
        # ----------------------------------------------------

        value_1_text = (
            f"\u20b9{float(value_1):,.2f}"
        )

        value_2_text = (
            f"\u20b9{float(value_2):,.2f}"
        )

        difference_text = (
            f"\u20b9{abs(float(difference)):,.2f}"
        )

        if percentage_change is not None:
            percentage_text = (
                f"{abs(float(percentage_change)):.2f}%"
            )
        else:
            percentage_text = "N/A"

        # ----------------------------------------------------
        # Determine change direction.
        #
        # period_1 is the newer/current period.
        # period_2 is the comparison period.
        # ----------------------------------------------------

        if difference > 0:
            change_word = "increased"
        elif difference < 0:
            change_word = "decreased"
        else:
            change_word = "remained unchanged"

        if difference == 0:
            change_sentence = (
                "Sales remained unchanged between "
                f"{period_1} and {period_2}."
            )
        else:
            change_sentence = (
                f"Sales {change_word} by "
                f"{difference_text} "
                f"({percentage_text}) from "
                f"{period_2} to {period_1}."
            )

        answer = (
            "Sales period comparison:\n\n"
            f"- {period_1}: {value_1_text}\n"
            f"- {period_2}: {value_2_text}\n\n"
            f"{change_sentence}"
        )

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }
        # --------------------------------------------------------
    # Multi-metric aggregate answer.
    #
    # Example:
    # Show total sales, total GST and total discount
    # for ABC Traders in September 2026
    # --------------------------------------------------------

    if result.get("operation") == "multi_aggregate":
        
        multi_aggregates = result.get(
            "aggregate_metrics",
            [],
        )
        aggregates = result.get(
            "aggregates",
            {},
        )

        filtered_count = result.get(
            "filtered_rows",
            0,
        )

        answer_lines = [
            "Sales Summary",
            "",
        ]

        # ----------------------------------------------------
        # Format known business metrics.
        # ----------------------------------------------------

        metric_labels = {
            "Total Amount": "Total Sales",
            "Sales": "Total Sales",
            "GST": "Total GST",
            "Discount": "Total Discount",
        }

        aggregate_results = result.get(
            "aggregate_results",
            [],
        )

        for item in aggregate_results:

            column = item["column"]
            function = item["function"]
            value = item["value"]

            # ----------------------------------------------
            # Choose the correct business metric name.
            # ----------------------------------------------

            if column in {
                "Total Amount",
                "Sales",
            }:
                metric_name = "Sales"

            elif column == "GST":
                metric_name = "GST"

            elif column == "Discount":
                metric_name = "Discount"

            else:
                metric_name = column

            # ----------------------------------------------
            # Build aggregation label.
            # ----------------------------------------------

            if function == "average":
                label = f"Average {metric_name}"

            elif function == "max":
                label = f"Maximum {metric_name}"

            elif function == "min":
                label = f"Minimum {metric_name}"

            else:
                label = f"Total {metric_name}"

            try:
                value_text = (
                    f"\u20b9{float(value):,.2f}"
                )
            except (TypeError, ValueError):
                value_text = str(value)

            answer_lines.append(
                f"{label}: {value_text}"
            )

        # ----------------------------------------------------
        # Show applied filters.
        # ----------------------------------------------------

        if filters:
            answer_lines.extend(
                [
                    "",
                    "Filters:",
                ]
            )

            answer_lines.extend(
                f"- {_describe_filter(item)}"
                for item in filters
            )

        # ----------------------------------------------------
        # Show number of source records/invoices.
        # ----------------------------------------------------

        if filtered_count:
            answer_lines.extend(
                [
                    "",
                    f"Invoices: {filtered_count}",
                ]
            )

        answer = "\n".join(
            answer_lines
        )

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }


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
    # DISTINCT VALUES ANSWER
    # --------------------------------------------------------
    distinct_values_requested = bool(
        re.search(
            r"\b(?:show|give|list|display|return|fetch|provide)\b"
            r".*?\b(?:all|every)\b"
            r".*?\bvalues?\b",
            question,
            flags=re.IGNORECASE,
        )
    )
    if (
        result.get("operation") == "count"
        and distinct_values_requested
        and result.get("column")
    ):
        distinct_column = result.get("column")
        distinct_rows = result.get("rows") or []

        value_items = []

        for item in distinct_rows:
            if not isinstance(item, dict):
                continue

            value = item.get(distinct_column)
            frequency = item.get("count", 0)

            if value is None:
                value = "(blank)"

            value_items.append(
                (str(value), frequency)
            )

        answer = (
            f"**Distinct values in `{distinct_column}`**\n\n"
            f"Found **{len(value_items)} distinct values**."
        )

        if value_items:
            answer += "\n\n"

            for value, frequency in value_items:
                answer += (
                    f"- **{value}** — {frequency} record"
                    f"{'' if frequency == 1 else 's'}\n"
                )

        if filters:
            answer += (
                "\nFilters:\n"
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
    # Count.
    # --------------------------------------------------------

   # Count.
    if result.get("operation") == "count":
        count = result.get("count", 0)
        values_count = result.get("values_count")
        column = result.get("column")

        # ------------------------------------------------------
        # Determine business entity requested by the user.
        # ------------------------------------------------------

        question_lower = question.lower()

        if re.search(r"\b(?:customer|customers|party|parties)\b", question_lower):
            entity_label = "customer"
            display_count = (
                values_count
                if column and values_count is not None
                else count
            )

        elif re.search(r"\b(?:product|products|item|items)\b", question_lower):
            entity_label = "product"
            display_count = (
                values_count
                if column and values_count is not None
                else count
            )

        elif re.search(
            r"\b(?:invoice|invoices|bill|bills)\b",
            question_lower,
        ):
            entity_label = "invoice"
            display_count = (
                values_count
                if column and values_count is not None
                else count
            )

        elif re.search(
            r"\b(?:supplier|suppliers)\b",
            question_lower,
        ):
            entity_label = "supplier"
            display_count = (
                values_count
                if column and values_count is not None
                else count
            )

        else:
            entity_label = "record"
            display_count = count

        answer = (
            f"There {'is' if display_count == 1 else 'are'} "
            f"{display_count} "
            f"{entity_label}"
            f"{'' if display_count == 1 else 's'} "
            f"in '{dataset_name}'."
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

    
     # --------------------------------------------------------
    # DISTINCT / UNIQUE COUNT.
    #
    # Examples:
    #   How many unique invoices are there?
    #   How many distinct customers are there?
    #   How many distinct products are there?
    #   How many unique GSTIN values are there?
    #
    # The DISTINCT value was already calculated by SQLite
    # in load_dynamic_data().
    # --------------------------------------------------------

    if result.get("operation") == "distinct_count":
        distinct_value = result.get(
            "distinct_count",
            result.get("value", 0),
        )

        distinct_column = result.get(
            "aggregate_column",
            result.get("column"),
        )

        # Determine a user-friendly entity name from
        # the actual resolved source column.
        distinct_entity_map = {
            "InvoiceNo": "invoice",
            "Invoice No": "invoice",
            "Invoice Number": "invoice",
            "InvoiceNumber": "invoice",
            "PartyName": "customer",
            "Party Name": "customer",
            "Customer": "customer",
            "CustomerName": "customer",
            "Product": "product",
            "Product Name": "product",
            "GSTIN": "GSTIN",
            "PaymentMode": "payment mode",
            "Payment Mode": "payment mode",
            "Category": "category",
            "PartyState": "state",
            "Party State": "state",
        }

        entity_label = distinct_entity_map.get(
            str(distinct_column),
            str(distinct_column or "value"),
        )

        answer = (
            f"There {'is' if distinct_value == 1 else 'are'} "
            f"**{distinct_value:,}** unique "
            f"{entity_label}"
            f"{'' if distinct_value == 1 else 's'} "
            f"in '{dataset_name}'."
        )

        if filters:
            answer += (
                "\n\n"
                "Filters:\n"
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
    if result.get("sql_fast_path") is True:
        result = {
            **result,
            "operation": result.get(
                "aggregate_function"
            ),
            "column": result.get(
                "aggregate_column"
            ),
        }

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

        # ----------------------------------------------------
        # Business-friendly sales summary.
        # ----------------------------------------------------

        question_norm = _normalize_text(
            question
        )

        sales_query = bool(
            re.search(
                r"\b(?:sales?|revenue|billing|turnover)\b",
                question_norm,
            )
        )

        if (
            sales_query
            and function == "sum"
        ):

            formatted_value = value

            if isinstance(
                value,
                (int, float),
            ):
                formatted_value = (
                    f"\u20b9{value:,.2f}"
                )
            else:
                try:
                    numeric_value = float(
                        str(value)
                        .replace("\u20b9", "")
                        .replace("?", "")
                        .replace(",", "")
                        .strip()
                    )

                    formatted_value = (
                        f"\u20b9{numeric_value:,.2f}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    formatted_value = str(
                        value
                    )

            answer = (
                "**SALES SUMMARY**\n\n"
                f"**Total Sales:** "
                f"{formatted_value}"
            )

            # ------------------------------------------------
            # Add filter context.
            # ------------------------------------------------

            if filters:

                answer += (
                    "\n\n"
                    "**Filters Applied**\n"
                )

                answer += "\n".join(
                    f"- {_describe_filter(item)}"
                    for item in filters
                )

            # ------------------------------------------------
            # Add invoice/customer information when rows
            # are available.
            # ------------------------------------------------

            if result.get("sql_fast_path") is True:
                invoice_count = result.get(
                    "invoice_count"
                )
                customer_count = result.get(
                    "customer_count"
                )

                if invoice_count is not None:
                    answer += (
                        "\n\n"
                        f"**Total Invoices:** "
                        f"{invoice_count}"
                    )

                if customer_count is not None:
                    answer += (
                        "\n"
                        f"**Total Customers:** "
                        f"{customer_count}"
                    )

            elif result_rows:

                invoice_column = None

                for candidate in (
                    "Invoice No",
                    "InvoiceNo",
                    "Invoice Number",
                    "InvoiceNumber",
                    "Bill No",
                    "Bill Number",
                ):
                    invoice_column = next(
                        (
                            key
                            for row in result_rows
                            for key in row.keys()
                            if str(key).lower()
                            == candidate.lower()
                        ),
                        None,
                    )

                    if invoice_column:
                        break

                customer_column = None

                for candidate in (
                    "Party Name",
                    "PartyName",
                    "Customer",
                    "Customer Name",
                    "CustomerName",
                ):
                    customer_column = next(
                        (
                            key
                            for row in result_rows
                            for key in row.keys()
                            if str(key).lower()
                            == candidate.lower()
                        ),
                        None,
                    )

                    if customer_column:
                        break

                if invoice_column:

                    invoice_values = {
                        str(
                            row.get(
                                invoice_column
                            )
                        ).strip()
                        for row in result_rows
                        if row.get(
                            invoice_column
                        ) not in (
                            None,
                            "",
                        )
                    }

                    answer += (
                        "\n\n"
                        f"**Total Invoices:** "
                        f"{len(invoice_values)}"
                    )

                if customer_column:

                    customer_values = {
                        str(
                            row.get(
                                customer_column
                            )
                        ).strip()
                        for row in result_rows
                        if row.get(
                            customer_column
                        ) not in (
                            None,
                            "",
                        )
                    }

                    answer += (
                        "\n"
                        f"**Total Customers:** "
                        f"{len(customer_values)}"
                    )

            return {
                **state,
                "answer": answer,
                "result": result,
                "error": None,
            }

        # ----------------------------------------------------
        # Existing generic aggregate behaviour.
        # ----------------------------------------------------

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

       # --------------------------------------------------------
    # Group + aggregate.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # EMPLOYEE ATTENDANCE SUMMARY
    #
    # Example:
    #   show attendance for EMP001
    #
    # Present attendance naturally instead of showing
    # "Found 2 matching records".
    # --------------------------------------------------------

    if result.get(
        "operation"
    ) == "employee_attendance_summary":

        group_column = result.get(
            "group_by",
            "Attendance Status",
        )

        status_counts = {}

        for row in result_rows:
            status = str(
                row.get(
                    group_column,
                    "Unknown",
                )
            ).strip()

            try:
                count_value = int(
                    row.get("count", 0) or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                count_value = 0

            status_counts[status] = count_value

        total_days = sum(
            status_counts.values()
        )

        employee_id_match = re.search(
            r"\bEMP\d+\b",
            question,
            flags=re.IGNORECASE,
        )

        employee_id = (
            employee_id_match.group(0).upper()
            if employee_id_match
            else "Employee"
        )

        status_order = [
            "Present",
            "Absent",
            "Leave",
            "Half Day",
            "Weekly Off",
        ]

        answer_lines = [
            f"**{employee_id} Attendance**",
            "",
        ]

        for status in status_order:
            answer_lines.append(
                f"{status}: "
                f"{status_counts.get(status, 0)} days"
            )

        answer_lines.extend(
            [
                "",
                f"**Total Days: {total_days}**",
            ]
        )

        return {
            **state,
            "answer": "\n".join(
                answer_lines
            ),
        }

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

        # ----------------------------------------------------
        # Ranking query.
        #
        # Example:
        #   Which customer has highest sales?
        #
        # The execution layer has already:
        #   1. grouped the rows
        #   2. summed sales
        #   3. sorted descending
        #
        # Therefore result_rows[0] is the highest-ranked group.
        # ----------------------------------------------------

        question_norm = _normalize_text(
            question
        )

        ranking_query = bool(
            group_by
            and re.search(
                r"\b(?:highest|maximum|most|top)\b",
                question_norm,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst)\b",
                question_norm,
            )
        )

        lowest_ranking_query = bool(
            group_by
            and re.search(
                r"\b(?:lowest|minimum|least|bottom)\b",
                question_norm,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst)\b",
                question_norm,
            )
        )

        # ----------------------------------------------------
        # EXPLICIT TOP-N GROUPED RANKING
        #
        # Examples:
        #   Show the top 3 products by sales
        #   Show the top 3 customers by sales
        #
        # The execution layer has already limited result_rows
        # to the requested Top-N groups.
        #
        # Therefore we display ALL Top-N rows instead of
        # reducing them to a single highest-ranked row.
        # ----------------------------------------------------

        top_n_match = re.search(
            r"\b(top|bottom)\s+(\d+)\b"
            r"|"
            r"\b(?:which|show|give|list)\s+(\d+)\s+"
            r"(?:customers?|products?|items?|parties?|"
            r"suppliers?|vendors?|invoices?|transactions?|records?)"
            r".*?\b(highest|lowest|maximum|minimum|most|least)\b",
            question_norm,
            flags=re.IGNORECASE,
        )

        if (
            top_n_match
            and group_by
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit)\b",
                question_norm,
            )
            and result_rows
        ):
            ranking_word = (
                top_n_match.group(1)
                or (
                    "top"
                    if top_n_match.group(4).lower()
                    in {"highest", "maximum", "most"}
                    else "bottom"
                )
            ).lower()

            top_n_value = int(
                top_n_match.group(2)
                or top_n_match.group(3)
            )

            ranking_rows = []

            for row in result_rows:
                if not isinstance(row, dict):
                    continue

                row_value = None

                for key, item_value in row.items():
                    if key == group_by:
                        continue

                    try:
                        if item_value is None:
                            continue

                        row_value = float(
                            str(item_value)
                            .replace(",", "")
                            .replace("₹", "")
                            .replace("$", "")
                            .strip()
                        )
                        break

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

                if row_value is not None:
                    ranking_rows.append(
                        (
                            row_value,
                            row,
                        )
                    )

            if not ranking_rows:
                return {
                    **state,
                    "answer": (
                        "No numeric values were available "
                        "to determine the ranking."
                    ),
                }

            # ------------------------------------------------
            # Sort according to the requested ranking.
            # Top N    → highest to lowest
            # Bottom N → lowest to highest
            # ------------------------------------------------

            ranking_rows.sort(
                key=lambda item: item[0],
                reverse=(
                    ranking_word == "top"
                ),
            )

            ranking_rows = ranking_rows[
                :top_n_value
            ]

            entity_label = group_by

            if re.search(r"\b(?:customer|customers)\b", question_norm):
                entity_label = "customers"
            elif re.search(r"\b(?:product|products|item|items)\b", question_norm):
                entity_label = "products"

            if group_by:
                normalized_group = _normalize_text(
                    group_by
                )

                if normalized_group in (
                    "party name",
                    "customer",
                    "customer name",
                ):
                    entity_label = "customers"

                elif normalized_group in (
                    "product",
                    "item",
                    "product name",
                ):
                    entity_label = "products"

                elif normalized_group in (
                    "party",
                    "parties",
                ):
                    entity_label = "parties"

                elif not entity_label:
                    entity_label = str(
                        group_by
                    )

            ranking_label = (
                "Top"
                if ranking_word == "top"
                else "Bottom"
            )

            metric_for_ranking = (
                "profit"
                if re.search(
                    r"\bprofit\b",
                    question_norm,
                )
                else "sales"
            )

            answer_lines = [
                f"**{ranking_label} {len(ranking_rows)} "
                f"{entity_label} by {metric_for_ranking}**",
                "",
            ]

            for index, (
                row_value,
                row,
            ) in enumerate(
                ranking_rows,
                start=1,
            ):
                group_value = row.get(
                    group_by,
                    "Unknown",
                )

                formatted_value = (
                    f"₹{row_value:,.2f}"
                )

                answer_lines.append(
                    f"{index}. **{group_value}** — "
                    f"**{formatted_value}**"
                )

            return {
                **state,
                "answer": "\n".join(
                    answer_lines
                ),
            }

        # ------------------------------------------------
        # SINGLE GROUP RANKING
        #
        # Examples:
        #   Which customer has highest sales?
        #   Which product has highest sales?
        # ------------------------------------------------

        if (
            ranking_query or lowest_ranking_query
        ) and result_rows:

            # ------------------------------------------------
            # Determine the requested ranking explicitly.
            #
            # Do NOT rely on result_rows[0] because time-based
            # grouped results may be returned chronologically.
            # ------------------------------------------------

            ranking_rows = []

            for row in result_rows:
                if not isinstance(row, dict):
                    continue

                row_value = None

                for key, item_value in row.items():
                    if key == group_by:
                        continue

                    try:
                        if item_value is None:
                            continue

                        row_value = float(
                            str(item_value)
                            .replace(",", "")
                            .replace("₹", "")
                            .replace("$", "")
                            .strip()
                        )
                        break

                    except (
                        TypeError,
                        ValueError,
                    ):
                        continue

                if row_value is not None:
                    ranking_rows.append(
                        (
                            row_value,
                            row,
                        )
                    )

            if not ranking_rows:
                return {
                    **state,
                    "answer": (
                        "No numeric values were available "
                        "to determine the ranking."
                    ),
                }

            if lowest_ranking_query:
                selected_value, selected_row = min(
                    ranking_rows,
                    key=lambda item: item[0],
                )
                ranking_label = "lowest"
            else:
                selected_value, selected_row = max(
                    ranking_rows,
                    key=lambda item: item[0],
                )
                ranking_label = "highest"

            group_value = selected_row.get(
                group_by
            )

            formatted_value = (
                f"₹{selected_value:,.2f}"
            )

            if re.search(
                r"\b(?:gst|totalgst|total\s+gst)\b",
                question_norm,
            ):
                metric_label = "GST"
            elif re.search(
                r"\bprofit\b",
                question_norm,
            ):
                metric_label = "profit"
            else:
                metric_label = "sales"
                           

            answer = (
                f"**{group_value}** has the "
                f"{ranking_label} {metric_label} with "
                f"**{formatted_value}**."
            )

            return {
                **state,
                "answer": answer,
            }

        # ----------------------------------------------------
        # Normal grouped result.
        # ----------------------------------------------------

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
    
    # --------------------------------------------------------
    # TOP-N ROW RANKING ANSWER
    # --------------------------------------------------------

    if result.get(
        "operation"
    ) == "top_n_rows":

        ranking_column = result.get(
            "ranking_column"
        )

        ranking_direction = result.get(
            "ranking_direction",
            "desc",
        )

        top_n_value = result.get(
            "top_n",
            len(result_rows),
        )

        if ranking_direction == "asc":
            ranking_label = "lowest"
        else:
            ranking_label = "highest"

        answer = (
            f"**Top {len(result_rows)} {ranking_label}-value "
            f"records by {ranking_column}**"
        )

        answer += "\n\n"

        answer += _format_table(
            result_rows,
            max_rows=top_n_value,
        )

        return {
            **state,
            "answer": answer,
        }

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

        # --------------------------------------------------------
    # Vyapar-style complete sales report.
    #
    # This changes ONLY the presentation.
    # The execution layer has already returned all rows.
    # --------------------------------------------------------

    question_norm = _normalize_text(
        question
    )

    complete_report_query = bool(
        re.search(
            r"\b(?:complete|full|detailed)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and re.search(
            r"\breport\b",
            question_norm,
        )
    )

    if complete_report_query and result_rows:

        # ----------------------------------------------------
        # Find important sales columns dynamically.
        # ----------------------------------------------------

        amount_column = None

        for candidate in (
            "Total Amount",
            "TotalAmount",
            "Amount",
            "Sales Amount",
            "Sales",
            "Revenue",
        ):
            if any(
                candidate.lower()
                == str(key).lower()
                for row in result_rows
                for key in row.keys()
            ):
                amount_column = next(
                    (
                        key
                        for row in result_rows
                        for key in row.keys()
                        if str(key).lower()
                        == candidate.lower()
                    ),
                    None,
                )
                break

        customer_column = None

        for candidate in (
            "Party Name",
            "PartyName",
            "Customer",
            "Customer Name",
            "CustomerName",
        ):
            customer_column = next(
                (
                    key
                    for row in result_rows
                    for key in row.keys()
                    if str(key).lower()
                    == candidate.lower()
                ),
                None,
            )

            if customer_column:
                break

        invoice_column = None

        for candidate in (
            "Invoice No",
            "InvoiceNo",
            "Invoice Number",
            "InvoiceNumber",
            "Bill No",
            "Bill Number",
        ):
            invoice_column = next(
                (
                    key
                    for row in result_rows
                    for key in row.keys()
                    if str(key).lower()
                    == candidate.lower()
                ),
                None,
            )

            if invoice_column:
                break

        # ----------------------------------------------------
        # Convert amount safely.
        # ----------------------------------------------------

        def _sales_amount(value):
            if value is None:
                return 0.0

            if isinstance(
                value,
                (int, float),
            ):
                return float(value)

            text_value = str(value)

            text_value = (
                text_value
                .replace("?", "")
                .replace(",", "")
                .strip()
            )

            try:
                return float(text_value)
            except (
                TypeError,
                ValueError,
            ):
                return 0.0

        # ----------------------------------------------------
        # Total sales.
        # ----------------------------------------------------

        total_sales = 0.0

        if amount_column:
            total_sales = sum(
                _sales_amount(
                    row.get(amount_column)
                )
                for row in result_rows
            )

        # ----------------------------------------------------
        # Invoice count.
        # ----------------------------------------------------

        if invoice_column:
            invoice_values = {
                str(row.get(invoice_column)).strip()
                for row in result_rows
                if row.get(invoice_column) not in (
                    None,
                    "",
                )
            }

            total_invoices = len(
                invoice_values
            )
        else:
            total_invoices = len(
                result_rows
            )

        # ----------------------------------------------------
        # Customer-wise sales.
        # ----------------------------------------------------

        customer_sales = {}

        if customer_column:
            for row in result_rows:

                customer = row.get(
                    customer_column
                )

                if customer in (
                    None,
                    "",
                ):
                    customer = "Unknown"

                customer = str(
                    customer
                ).strip()

                amount = 0.0

                if amount_column:
                    amount = _sales_amount(
                        row.get(
                            amount_column
                        )
                    )

                customer_sales[
                    customer
                ] = (
                    customer_sales.get(
                        customer,
                        0.0,
                    )
                    + amount
                )

        # ----------------------------------------------------
        # Build Vyapar-style report.
        # ----------------------------------------------------

        answer = (
            "**SALES REPORT**\n\n"
            f"**Total Sales:** "
            f"?{total_sales:,.2f}\n"
            f"**Total Invoices:** "
            f"{total_invoices}\n"
            f"**Total Customers:** "
            f"{len(customer_sales)}"
        )

        if customer_sales:

            answer += (
                "\n\n"
                "**Customer-wise Sales**\n\n"
                "Customer | Total Sales\n"
                "--- | ---\n"
            )

            for customer, amount in sorted(
                customer_sales.items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                answer += (
                    f"{customer} | "
                    f"?{amount:,.2f}\n"
                )

        # ----------------------------------------------------
        # Preserve export information.
        # ----------------------------------------------------

        if export_requested:

            format_label = (
                export_format.upper()
                if export_format
                else "XLSX"
            )

            answer += (
                "\n"
                f"**Ready to download "
                f"{len(result_rows)} records "
                f"as {format_label}.**"
            )

        # ----------------------------------------------------
        # Invoice details.
        # ----------------------------------------------------

        answer += (
            "\n\n"
            "**Invoice Details**\n\n"
        )

        answer += _format_table(
            result_rows,
            max_rows=50,
        )

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }

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

    # --------------------------------------------------------
    # RAW ROW RESULT
    #
    # Do not send thousands of raw records into the final
    # conversational answer. The complete rows remain in
    # result["rows"] for viewing/export.
    # --------------------------------------------------------

    if result.get("operation") == "rows":

        row_count = result.get(
            "count",
            len(result_rows),
        )

        answer = (
            f"Found {row_count} matching records "
            f"in '{dataset_name}'."
        )

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

        if export_requested:
            format_label = (
                export_format.upper()
                if export_format
                else "XLSX"
            )

            answer += (
                f"\n\nReady to download "
                f"{row_count} records "
                f"as {format_label}."
            )
        else:
            answer += (
                "\n\nThe complete records are available "
                "for viewing or export."
            )

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }

    # --------------------------------------------------------
    # Existing table formatting for non-raw-row results
    # --------------------------------------------------------

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






