from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from services.dynamic_query_service import (
    get_all_dataset_context,
    get_dataset_schema,
    load_dataset_rows,
    load_dataset_column_values,
    check_dataset_has_matching_dates,
    run_sql_aggregate,
    run_sql_distinct_count,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# UNIVERSAL QUERY PLANNER LLM
# ============================================================

_dynamic_query_llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0
)

# ============================================================
# STATE
# ============================================================

class DynamicAgentState(TypedDict, total=False):
    question: str
    original_question: str
    query_plan: Dict[str, Any]
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
    chart: Dict[str,Any]
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
    text = re.sub(r"(?<!\d)-|-(?!\d)", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text

def _normalize_query(question: Any) -> str:
    """
    Normalize only the user's query.

    IMPORTANT:
    Do not use this for dataset values or source columns.

    This layer:
    1. normalizes spacing / separators
    2. corrects common business-query spelling mistakes
    3. keeps the underlying dataset values untouched
    """
    text = _normalize_text(question)

    if not text:
        return ""

    # --------------------------------------------------------
    # Common query spelling / typing corrections
    # --------------------------------------------------------
    corrections = {
        # ---------------- SALES ----------------
        "sal": "sales",
        "sals": "sales",
        "sale": "sales",
        "salees": "sales",
        "saless": "sales",
        "salse": "sales",
        "salses": "sales",

        # ---------------- REVENUE ----------------
        "revenu": "revenue",
        "reveneu": "revenue",
        "revene": "revenue",
        "revenuee": "revenue",
        "revnue": "revenue",
        "revinue": "revenue",

        # ---------------- PRODUCT ----------------
        "prodcut": "product",
        "prodct": "product",
        "produc": "product",
        "prodcuts": "products",
        "produts": "products",
        "produtc": "product",

        # ---------------- CUSTOMER ----------------
        "custmer": "customer",
        "custmor": "customer",
        "custumer": "customer",
        "customr": "customer",
        "custmers": "customers",
        "custmors": "customers",
        "custumer": "customer",
        "coustomer": "customer",
        "coustmers": "customers",

        # ---------------- SUPPLIER ----------------
        "suplier": "supplier",
        "supplir": "supplier",
        "suppler": "supplier",
        "supplierss": "suppliers",
        "supliers": "suppliers",

        # ---------------- QUANTITY ----------------
        "quanity": "quantity",
        "quantitiy": "quantity",
        "quantitty": "quantity",
        "quantty": "quantity",
        "quntity": "quantity",
        "quantiy": "quantity",
        "qantity": "quantity",
        "qty": "quantity",

        # ---------------- PROFIT ----------------
        "profitt": "profit",
        "profot": "profit",
        "proft": "profit",
        "profi": "profit",
        "profti": "profit",
        "prof": "profit",
        "profits": "profits",

        # ---------------- DISCOUNT ----------------
        "discont": "discount",
        "discunt": "discount",
        "disocunt": "discount",
        "discout": "discount",
        "discnt": "discount",
        "discunts": "discounts",

        # ---------------- AMOUNT ----------------
        "amout": "amount",
        "ammount": "amount",
        "amnt": "amount",
        "amunt": "amount",

        # ---------------- INVOICE ----------------
        "invoce": "invoice",
        "invocie": "invoice",
        "invoie": "invoice",
        "invoise": "invoice",
        "invoic": "invoice",
        "invoices": "invoices",

        # ---------------- MONTH ----------------
        "mont": "month",
        "mnth": "month",
        "moth": "month",
        "monht": "month",
        "mounth": "month",
        "months": "months",

        # ---------------- YEAR ----------------
        "yer": "year",
        "yeer": "year",
        "yar": "year",
        "yaer": "year",
        "yeare": "year",

        # ---------------- QUARTER ----------------
        "quater": "quarter",
        "quartre": "quarter",
        "qaurter": "quarter",
        "quartr": "quarter",
        "quaterly": "quarterly",
        "qtr": "quarter",

        # ---------------- DATE ----------------
        "dat": "date",
        "dte": "date",
        "daet": "date",

        # ---------------- CATEGORY ----------------
        "catagory": "category",
        "categary": "category",
        "categry": "category",
        "catgory": "category",
        "categoy": "category",

        # ---------------- EMPLOYEE ----------------
        "employe": "employee",
        "emplyee": "employee",
        "employ": "employee",
        "employess": "employees",
        "employes": "employees",

        # ---------------- PAYMENT ----------------
        "paymant": "payment",
        "payement": "payment",
        "pament": "payment",
        "paymnt": "payment",

        # ---------------- GST ----------------
        "gts": "gst",
        "gstt": "gst",

        # ---------------- COST ----------------
        "coast": "cost",
        "cst": "cost",
        "costt": "cost",

        # ---------------- AVERAGE ----------------
        "avrage": "average",
        "averge": "average",
        "avarege": "average",
        "avergae": "average",
        "avragee": "average",
        "avg": "average",

        # ---------------- HIGHEST / LOWEST ----------------
        "higest": "highest",
        "heighest": "highest",
        "highst": "highest",
        "higgest": "highest",
        "hightest": "highest",

        "lowst": "lowest",
        "lowes": "lowest",
        "lowset": "lowest",
        "lowestt": "lowest",

        # ---------------- TOP / BOTTOM ----------------
        "topp": "top",
        "botom": "bottom",
        "botton": "bottom",
        "buttom": "bottom",

        # ---------------- LAST / LATEST / PREVIOUS ----------------
        "lst": "last",
        "las": "last",
        "laast": "last",

        "latst": "latest",
        "lates": "latest",
        "latestt": "latest",

        "previus": "previous",
        "prevous": "previous",
        "prevoius": "previous",

        # ---------------- GROUPING ----------------
        "wis": "wise",
        "wse": "wise",
        "wisee": "wise",
        "accordng": "according",
        "acording": "according",
        "accordin": "according",

        # ---------------- COMMON QUERY WORDS ----------------
        "whch": "which",
        "whta": "what",
        "waht": "what",
        "showw": "show",
        "shwo": "show",
        "giv": "give",
        "gve": "give",
    }

    words = text.split()
    words = text.split()

    corrected_words = []

    for word in words:
        match = re.match(r'^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$', word)

        if match:
            prefix, core, suffix = match.groups()
        else:
            prefix, core, suffix = '', word, ''

        corrected_core = corrections.get(core, core)
        corrected_words.append(prefix + corrected_core + suffix)

    return ' '.join(corrected_words)
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
                    [],
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
                    [],
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
                    [],
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
                    [],
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
                    [],
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
                    [],
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
            "count",
            "counts",
            "year",
            "years",
            "yearly",
            "annual",
            "month",
            "months",
            "monthly",
            "quarter",
            "quarters",
            "quarterly",
            "day",
            "days",
            "daily",
            "week",
            "weeks",
            "weekly",
            "trend",
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
        
        # Ignore aggregate/time/grouping suffixes attached to a valid metric.
        candidate_clean = re.sub(
            r"\b(?:year|years|yearly|annual|month|months|monthly|quarter|quarters|quarterly|day|days|daily|week|weeks|weekly|wise|trend)\b",
            " ",
            candidate_norm,
            flags=re.IGNORECASE,
        )

        candidate_clean = re.sub(r"\s+", " ", candidate_clean).strip()

        if candidate_clean and _resolve_column(
            candidate_clean,
            dataset,
            schema,
                    [],
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
    Extract numeric filters dynamically from natural-language questions.

    Supports examples such as:
        invoices above 30000
        invoices below 500
        profit above 100000
        GST above 5000
        discount above 1000
        quantity above 500
        unit price above 3000
        sales between 10000 and 20000
        profit between 5000 and 10000

    The metric/column is resolved dynamically from the uploaded
    dataset rather than being tied to one particular file.
    """

    filters: List[Dict[str, Any]] = []

    question_norm = _normalize_text(question)

    # --------------------------------------------------------
    # Normalize currency and number formatting
    # --------------------------------------------------------

    question_norm = question_norm.replace("?", "")
    question_norm = question_norm.replace("rs.", "")
    question_norm = question_norm.replace("rs ", "")
    question_norm = question_norm.replace(",", "")

    # --------------------------------------------------------
    # Dynamically resolve common business metric phrases
    # --------------------------------------------------------

    metric_aliases = [
        (
            r"\binvoice(?:s)?(?:\s+(?:value|amount|total))?\b",
            "InvoiceTotal",
        ),
        (
            r"\bsales?\b|\brevenue\b|\bbilling\b|\bturnover\b",
            "InvoiceTotal",
        ),
        (
            r"\bprofit\b",
            "Profit",
        ),
        (
            r"\bgst\b|\btotal\s+gst\b",
            "TotalGST",
        ),
        (
            r"\bcgst\b",
            "CGST",
        ),
        (
            r"\bsgst\b",
            "SGST",
        ),
        (
            r"\bigst\b",
            "IGST",
        ),
        (
            r"\bdiscount(?:\s+amount)?\b",
            "DiscountAmt",
        ),
        (
            r"\bquantity\b|\bqty\b",
            "Qty",
        ),
        (
            r"\bunit\s+price\b|\bprice\b",
            "UnitPrice",
        ),
        (
            r"\btaxable\s+amount\b|\btaxable\b",
            "TaxableAmount",
        ),
        (
            r"\bcost\b",
            "Cost",
        ),
        (
            r"\bgross\s+amount\b|\bgross\b",
            "GrossAmount",
        ),
    ]

    def resolve_metric(metric_name: str) -> Optional[str]:
        """
        Resolve a metric alias to an actual uploaded column.
        """
        column = _resolve_column(
            metric_name,
            dataset,
            schema,
                    [],
        )

        if column:
            return column

        # Try canonical/normalized alternatives.
        normalized_metric = _normalize_text(metric_name)

        for schema_item in schema:
            source_column = (
                schema_item.get("source_column")
                or schema_item.get("column")
                or schema_item.get("name")
            )

            if not source_column:
                continue

            canonical = _canonical_name(
                source_column,
                schema,
            )

            if (
                _normalize_text(source_column)
                == normalized_metric
                or _normalize_text(canonical or "")
                == normalized_metric
            ):
                return source_column

        return None

    def infer_metric_from_question(text: str) -> Optional[str]:
        """
        Infer the numeric metric from the natural-language question.

        More specific metrics must be checked before generic
        sales/invoice detection.
        """

        # Most specific metrics first.
        specific_metric_aliases = [
            (
                r"\btotal\s+gst\b|\bgst\b",
                "TotalGST",
            ),
            (
                r"\bcgst\b",
                "CGST",
            ),
            (
                r"\bsgst\b",
                "SGST",
            ),
            (
                r"\bigst\b",
                "IGST",
            ),
            (
                r"\bdiscount(?:\s+amount)?\b",
                "DiscountAmt",
            ),
            (
                r"\bunit\s+price\b",
                "UnitPrice",
            ),
            (
                r"\btaxable\s+amount\b|\btaxable\b",
                "TaxableAmount",
            ),
            (
                r"\bgross\s+amount\b|\bgross\b",
                "GrossAmount",
            ),
            (
                r"\bprofit\b",
                "Profit",
            ),
            (
                r"\bcost\b",
                "Cost",
            ),
            (
                r"\bquantity\b|\bqty\b",
                "Qty",
            ),
            (
                r"\bsales?\b|\brevenue\b|\bbilling\b|\bturnover\b",
                "InvoiceTotal",
            ),
            (
                r"\binvoice(?:s)?(?:\s+(?:value|amount|total))?\b",
                "InvoiceTotal",
            ),
        ]

        for pattern, metric_name in specific_metric_aliases:
            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                column = resolve_metric(metric_name)

                if column:
                    return column

        return None

    # ========================================================
    # BETWEEN
    # ========================================================

    between_patterns = [
        re.compile(
            r"(?P<metric>[A-Za-z][A-Za-z0-9 _-]{0,60}?)"
            r"\s+between\s+"
            r"(?P<low>-?\d+(?:\.\d+)?)"
            r"\s+(?:and|to)\s+"
            r"(?P<high>-?\d+(?:\.\d+)?)",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"(?P<low>-?\d+(?:\.\d+)?)"
            r"\s+(?:to|-)\s+"
            r"(?P<high>-?\d+(?:\.\d+)?)"
            r".*?\b(?P<metric>"
            r"sales?|revenue|profit|gst|discount|quantity|qty|"
            r"price|unit\s+price|cost|taxable|gross"
            r")\b",
            flags=re.IGNORECASE,
        ),
    ]

    for between_pattern in between_patterns:
        for match in between_pattern.finditer(question_norm):

            low = _to_number(match.group("low"))
            high = _to_number(match.group("high"))

            if low is None or high is None:
                continue

            raw_metric = match.groupdict().get("metric")

            column = None

            if raw_metric:
                column = resolve_metric(raw_metric)

            if not column:
                column = infer_metric_from_question(
                    question_norm
                )

            if not column:
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

            # A between expression has already been handled.
            break

        if filters:
            break

    # ========================================================
    # EXPLICIT COMPARISON
    # ========================================================

    comparison_pattern = re.compile(
        r"(?P<metric>"
        r"(?:invoices?|records?|transactions?)"
        r"|(?:products?|items?)"
        r"|(?:customers?|parties?)"
        r"|(?:sales?|revenue|billing|turnover)"
        r"|(?:profit)"
        r"|(?:gst|total\s+gst|cgst|sgst|igst)"
        r"|(?:discount(?:\s+amount)?)"
        r"|(?:quantity|qty)"
        r"|(?:unit\s+price|price)"
        r"|(?:taxable(?:\s+amount)?)"
        r"|(?:gross(?:\s+amount)?)"
        r"|(?:cost)"
        r")"
        r"(?:\s+with)?"
        r"(?:\s+"
        r"(?:sales?|revenue|profit|gst|discount|quantity|qty|"
        r"unit\s+price|price|cost|taxable|gross|invoice\s+(?:value|amount|total))"
        r")?"
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

        raw_metric = match.group("metric").strip()
        raw_operator = match.group("operator").strip().lower()
        raw_value = match.group("value").strip()

        # Resolve the actual numeric metric.
        column = resolve_metric(raw_metric)

        # If the captured phrase is an entity such as "invoices",
        # "products", or "customers", infer the actual metric from
        # the rest of the question.
        if not column or _normalize_text(raw_metric) in {
            "invoice",
            "invoices",
            "record",
            "records",
            "transaction",
            "transactions",
            "product",
            "products",
            "item",
            "items",
            "customer",
            "customers",
            "party",
            "parties",
        }:
            column = infer_metric_from_question(
                question_norm
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
    # FALLBACK:
    # METRIC + COMPARISON WHERE THE METRIC WAS NOT CAPTURED
    # ========================================================

    if not filters:

        fallback_pattern = re.compile(
            r"\b(?:above|over|greater\s+than|more\s+than|"
            r"below|under|less\s+than|lower\s+than|"
            r"at\s+least|at\s+most)\b"
            r"\s*"
            r"(?P<value>-?\d+(?:\.\d+)?)",
            flags=re.IGNORECASE,
        )

        fallback_match = fallback_pattern.search(
            question_norm
        )

        if fallback_match:

            column = infer_metric_from_question(
                question_norm
            )

            if column:

                raw_operator_match = re.search(
                    r"\b(?:above|over|greater\s+than|more\s+than|"
                    r"below|under|less\s+than|lower\s+than|"
                    r"at\s+least|at\s+most)\b",
                    question_norm,
                    flags=re.IGNORECASE,
                )

                if raw_operator_match:

                    raw_operator = (
                        raw_operator_match.group(0)
                        .strip()
                        .lower()
                    )

                    operator = operator_map.get(
                        raw_operator
                    )

                    numeric_value = _to_number(
                        fallback_match.group("value")
                    )

                    if (
                        operator
                        and numeric_value is not None
                    ):
                        filters.append(
                            {
                                "column": column,
                                "operator": operator,
                                "value": numeric_value,
                                "type": "numeric",
                            }
                        )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_filters: List[Dict[str, Any]] = []
    seen = set()

    for item in filters:

        key = (
            item.get("column"),
            item.get("operator"),
            item.get("value"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_filters.append(item)

    return unique_filters


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
                    [],
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
    # NATURAL PAYMENT PHRASE
    #
    # Examples:
    #   paid by UPI
    #   paid by Cash
    #   paid by Card
    # ============================================================

    paid_by_match = re.search(
        r"\bpaid\s+by\s+(?P<value>[A-Za-z][A-Za-z0-9 _-]*?)"
        r"(?=\s+(?:for|with|where|having|and|or)\s+|[,;]|$)",
        question,
        flags=re.IGNORECASE,
    )

    if paid_by_match:
        payment_value = paid_by_match.group("value").strip()

        payment_column = _resolve_column(
            "payment mode",
            dataset,
            schema,
                    [],
        )

        if not payment_column:
            payment_column = _resolve_column(
                "payment method",
                dataset,
                schema,
                    [],
            )

        if payment_column and _to_number(payment_value) is None:
            filters.append(
                {
                    "column": payment_column,
                    "operator": "=",
                    "value": payment_value,
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
                    [],
        )

        if not invoice_column:
            invoice_column = _resolve_column(
                "invoice number",
                dataset,
                schema,
                    [],
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
    # NATURAL INTERSTATE / INTRASTATE PHRASE
    #
    # Examples:
    #   sales for interstate transactions
    #   sales for inter-state transactions
    #   sales for intrastate transactions
    #   sales for intra-state transactions
    #
    # Dataset representation:
    #   InterState = Yes -> interstate
    #   InterState = No  -> intrastate
    # ============================================================

    interstate_match = re.search(
        r"\b(?:inter[\s-]?state)\s+transactions?\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    intrastate_match = re.search(
        r"\bintra[\s-]?state\s+transactions?\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    interstate_column = _resolve_column(
        "InterState",
        dataset,
        schema,
                    [],
    )

    if interstate_column:
        if interstate_match:
            filters.append(
                {
                    "column": interstate_column,
                    "operator": "=",
                    "value": "Yes",
                    "type": "categorical",
                }
            )
        elif intrastate_match:
            filters.append(
                {
                    "column": interstate_column,
                    "operator": "=",
                    "value": "No",
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
                    [],
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
                    [],
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
        # Keep the complete question available for dynamic
        # value discovery.
        #
        # Example:
        #   "... for Delhi with UPI payments"
        #
        # We must still discover Delhi even though UPI
        # appears after "with".
        dynamic_value_question = question_norm

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
        "by",
        "per",
        "each",
        "wise",
        "group",
        "grouped",
        "please",
        "me",

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

    # Load persisted rows only when dynamic categorical matching is required.
    # Planner context may not contain rows, so use the actual dataset ID.
    if not rows:
        try:
            dataset_id = dataset.get("id")
            if dataset_id is not None:
                rows = load_dataset_rows(int(dataset_id))
        except Exception:
            rows = []


    # ============================================================
    # 9. GET DATASET COLUMNS ONLY WHEN DYNAMIC MATCHING IS NEEDED
    # ============================================================

    columns = _dataset_columns(
        dataset,
        schema,
                    [],
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

        # ============================================================
        # MULTIPLE EXACT VALUES FROM THE SAME COLUMN
        #
        # Example:
        #   "Show sales for Delhi and Maharashtra"
        #
        # becomes:
        #   PartyState IN ["Delhi", "Maharashtra"]
        #
        # This is intentionally handled before the existing
        # single-value matcher so the existing break-based logic
        # remains unchanged for normal queries.
        # ============================================================

        multi_value_matches = []

        for candidate_value in unique_values:
            normalized_candidate = _normalize_text(
                candidate_value
            )

            if len(normalized_candidate) < 2:
                continue

            if _to_number(candidate_value) is not None:
                continue

            if _parse_date(candidate_value) is not None:
                continue

            if normalized_candidate in dynamic_value_question:
                multi_value_matches.append(candidate_value)

        # An exact whole-word dataset value found in the question takes
        # precedence over partial token matching. Without this, a longer
        # value that shares one token ("Shalini Sharma" for "Pooja Sharma")
        # is reached first in the loop below and wins.
        if len(multi_value_matches) == 1:
            exact_candidate = multi_value_matches[0]
            exact_normalized = _normalize_text(exact_candidate)
            exact_tokens = {
                token
                for token in _tokens(exact_normalized)
                if len(token) >= 2 and token not in ignored_query_words
            }

            if (
                exact_tokens
                and exact_normalized != _normalize_column(column)
                and re.search(
                    r"\b" + re.escape(exact_normalized) + r"\b",
                    dynamic_value_question,
                )
            ):
                filters.append(
                    {
                        "column": column,
                        "operator": "=",
                        "value": exact_candidate,
                        "type": "categorical",
                    }
                )
                continue

        # Only use the multi-value operator when at least two
        # distinct dataset values are explicitly present.
        if len(multi_value_matches) >= 2:
            filters.append(
                {
                    "column": column,
                    "operator": "in",
                    "value": multi_value_matches,
                    "type": "categorical",
                }
            )
            continue

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

                        # Collect ALL values sharing the token. Stopping at two
                        # would silently drop the rest (e.g. 6 'Sharma' parties).

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

                # If multiple dataset values contain the same
                # partial token, preserve ALL matching values
                # instead of arbitrarily selecting one.
                #
                # Example:
                #   Pooja -> Pooja Patel + Pooja Sharma
                #
                # This keeps partial-name matching deterministic
                # and prevents guessing a customer.
                if (
                    len(token_matches) > 1
                    and matched_tokens
                ):
                    filters.append(
                        {
                            "column": column,
                            "operator": "in",
                            "value": token_matches,
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
                    [],
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

    Supports:
        Compare September 2026 with August 2026
        Compare September sales with August sales
        Compare 2026 sales with 2025 sales
        What is the sales percentage increase from July 2025 to August 2025?
        Did sales increase or decrease in August 2025 compared to July 2025?
        Show month over month sales growth
    """

    date_column = _find_date_column(
        dataset,
        schema,
                    [],
    )

    if not date_column:
        return None

    question_norm = _normalize_text(question)

    # ========================================================
    # Detect the metric dynamically
    # ========================================================

    metric_patterns = [
        (
            r"\b(?:profit|profitability)\b",
            "profit",
            "Profit",
        ),
        (
            r"\b(?:total\s+gst|gst|gst\s+amount)\b",
            "gst",
            "GST",
        ),
        (
            r"\bcgst\b",
            "cgst",
            "CGST",
        ),
        (
            r"\bsgst\b",
            "sgst",
            "SGST",
        ),
        (
            r"\bigst\b",
            "igst",
            "IGST",
        ),
        (
            r"\b(?:discount|discount\s+amount)\b",
            "discount",
            "Discount",
        ),
        (
            r"\b(?:quantity|qty)\b",
            "quantity",
            "Quantity",
        ),
        (
            r"\b(?:taxable\s+amount|taxable)\b",
            "taxable_amount",
            "Taxable Amount",
        ),
        (
            r"\b(?:gross\s+amount|gross)\b",
            "gross_amount",
            "Gross Amount",
        ),
        (
            r"\bcost\b",
            "cost",
            "Cost",
        ),
        (
            r"\b(?:unit\s+price|unitprice)\b",
            "unit_price",
            "Unit Price",
        ),
    ]

    metric_key = "sales"
    metric_label = "Sales"

    for pattern, key, label in metric_patterns:
        if re.search(pattern, question_norm):
            metric_key = key
            metric_label = label
            break

    # ========================================================
    # Month names
    # ========================================================

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
    
    # ========================================================
    # Explicit day-to-day comparison
    # ========================================================

    day_matches = re.findall(
        r"\b(\d{1,2})\s+"
        r"(january|february|march|april|may|june|"
        r"july|august|september|october|november|december)"
        r"(?:\s+(20\d{2}))?\b",
        question_norm,
    )

    if len(day_matches) >= 2:

        first_day, first_month_name, first_year = day_matches[0]
        second_day, second_month_name, second_year = day_matches[1]

        first_month = month_names[first_month_name]
        second_month = month_names[second_month_name]

        available_dates = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if available_dates:
            latest_date = max(available_dates)

            # If only one month has an explicit year, apply that
            # year to both months.
            if first_year:
                year_1 = int(first_year)
            elif second_year:
                year_1 = int(second_year)
            else:
                year_1 = latest_date.year

            if second_year:
                year_2 = int(second_year)
            elif first_year:
                year_2 = int(first_year)
            else:
                year_2 = latest_date.year

            return {
                "column": date_column,
                "period_type": "day",

                # Preserve the user's requested order.
                "period_1": (
                    f"{year_1:04d}-{first_month:02d}-{int(first_day):02d}"
                ),
                "period_2": (
                    f"{year_2:04d}-{second_month:02d}-{int(second_day):02d}"
                ),

                "metric_key": metric_key,
                "metric_label": metric_label,
            }

    # ========================================================
    # Explicit month-to-month comparison
    # ========================================================
   
    month_matches = re.findall(
        r"\b("
        r"january|february|march|april|may|june|"
        r"july|august|september|october|november|december"
        r")"
        r"(?:\s*(20\d{2}))?\b",
        question_norm,
    )

    if len(month_matches) >= 2:

        first_month_name, first_year = month_matches[0]
        second_month_name, second_year = month_matches[1]

        first_month = month_names[first_month_name]
        second_month = month_names[second_month_name]

        available_dates = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if available_dates:
            latest_date = max(available_dates)

            # If only one month has an explicit year, apply that
            # year to both months.
            if first_year:
                year_1 = int(first_year)
            elif second_year:
                year_1 = int(second_year)
            else:
                year_1 = latest_date.year

            if second_year:
                year_2 = int(second_year)
            elif first_year:
                year_2 = int(first_year)
            else:
                year_2 = latest_date.year

            return {
                "column": date_column,
                "period_type": "month",

                # Preserve the user's requested order.
                "period_1": (
                    f"{year_1:04d}-{first_month:02d}"
                ),
                "period_2": (
                    f"{year_2:04d}-{second_month:02d}"
                ),

                "metric_key": metric_key,
                "metric_label": metric_label,
            }

    # ========================================================
    # Explicit year-to-year comparison
    # ========================================================

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

            # Preserve question order.
            "period_1": str(unique_years[0]),
            "period_2": str(unique_years[1]),

            "metric_key": metric_key,
            "metric_label": metric_label,
        }

    # ========================================================
    # Month-over-month comparison
    # ========================================================

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
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
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
                f"{previous_year:04d}-{previous_month:02d}"
            ),
            "period_2": (
                f"{current_year:04d}-{current_month:02d}"
            ),
            "metric_key": metric_key,
            "metric_label": metric_label,
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
                    [],
    )

    if not date_column:
        return filters

    # Explicit quarter filters: Q1/Q2/Q3/Q4 + year
    quarter_match = re.search(
        r'\bQ([1-4])\s*(?:of|[-/ ]*)?\s*(20\d{2})\b',
        question,
        flags=re.IGNORECASE,
    )
    if not quarter_match:
        quarter_match = re.search(
            r'\b(?:quarter|qtr)\s*([1-4])\s*(?:of|[-/ ]*)?\s*(20\d{2})\b',
            question,
            flags=re.IGNORECASE,
        )
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        start_month = (quarter - 1) * 3 + 1
        start_date = f'{year:04d}-{start_month:02d}-01'
        end_date = (
            f'{year + 1:04d}-01-01'
            if quarter == 4
            else f'{year:04d}-{start_month + 3:02d}-01'
        )
        return [
            {'column': date_column, 'operator': '>=', 'value': start_date, 'type': 'date'},
            {'column': date_column, 'operator': '<', 'value': end_date, 'type': 'date'},
        ]

    question_norm = _normalize_text(question)

    # ========================================================
    # NUMERIC DATE FORMATS
    #
    # Supported:
    #   YYYY-MM       -> 2026-08
    #   MM-YYYY       -> 08-2026
    #   DD-MM-YYYY    -> 15-08-2026
    #   YYYY-MM-DD    -> 2026-08-15
    # ========================================================

    numeric_date_filters_added = False

    # YYYY-MM-DD
    ymd_match = re.search(
        r"\b(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])\b",
        question,
    )

    ymd_is_range = bool(
        re.search(
            r"\b(?:from|between)\s+"
            r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4})"
            r"\s+(?:to|and)\s+"
            r"(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4})\b",
            question,
            flags=re.IGNORECASE,
        )
    )

    if ymd_match and not ymd_is_range:
        year = int(ymd_match.group(1))
        month = int(ymd_match.group(2))
        day = int(ymd_match.group(3))

        filters.extend([
            {
                "column": date_column,
                "operator": "year",
                "value": year,
                "type": "date",
            },
            {
                "column": date_column,
                "operator": "month",
                "value": month,
                "type": "date",
            },
            {
                "column": date_column,
                "operator": "date",
                "value": f"{year:04d}-{month:02d}-{day:02d}",
                "type": "date",
            },
        ])
        numeric_date_filters_added = True

    # YYYY-MM
    if not numeric_date_filters_added:
        ym_match = re.search(
            r"\b(20\d{2})-(0?[1-9]|1[0-2])\b",
            question,
        )

        if ym_match:
            year = int(ym_match.group(1))
            month = int(ym_match.group(2))

            filters.extend([
                {
                    "column": date_column,
                    "operator": "year",
                    "value": year,
                    "type": "date",
                },
                {
                    "column": date_column,
                    "operator": "month",
                    "value": month,
                    "type": "date",
                },
            ])
            numeric_date_filters_added = True

    # DD-MM-YYYY
    if not numeric_date_filters_added:
        dmy_match = re.search(
            r"\b(0?[1-9]|[12]\d|3[01])-(0?[1-9]|1[0-2])-(20\d{2})\b",
            question,
        )

        if dmy_match:
            day = int(dmy_match.group(1))
            month = int(dmy_match.group(2))
            year = int(dmy_match.group(3))

            # Do not add an exact-date filter when this DMY date
            # is part of a date range. The range logic below will
            # add the >= and <= filters.
            dmy_is_range = bool(
                re.search(
                    r"\b(?:from|between)\s+"
                    r"(?:\d{1,2}-\d{1,2}-20\d{2})"
                    r"\s+(?:to|and)\s+"
                    r"(?:\d{1,2}-\d{1,2}-20\d{2})\b",
                    question,
                    flags=re.IGNORECASE,
                )
            )

            if not dmy_is_range:
                filters.extend([
                    {
                        "column": date_column,
                        "operator": "year",
                        "value": year,
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "month",
                        "value": month,
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "date",
                        "value": f"{year:04d}-{month:02d}-{day:02d}",
                        "type": "date",
                    },
                ])

                numeric_date_filters_added = True

    # MM-YYYY
    if not numeric_date_filters_added:
        my_match = re.search(
            r"\b(0?[1-9]|1[0-2])-(20\d{2})\b",
            question,
        )

        if my_match:
            month = int(my_match.group(1))
            year = int(my_match.group(2))

            filters.extend([
                {
                    "column": date_column,
                    "operator": "year",
                    "value": year,
                    "type": "date",
                },
                {
                    "column": date_column,
                    "operator": "month",
                    "value": month,
                    "type": "date",
                },
            ])
            numeric_date_filters_added = True

    # ========================================================
    # Numeric date/month filters are complete.
    # Do not allow later temporal logic to modify them.
    if numeric_date_filters_added:
        return _deduplicate_filters(filters)

    # NATURAL LANGUAGE DAY + MONTH + YEAR
    #
    # Examples:
    #   20 August 2026 -> 2026-08-20
    #   20 Aug 2026    -> 2026-08-20
    #   23 July 2026   -> 2026-07-23
    #   23 Jul 2026    -> 2026-07-23
    # ========================================================

    if not numeric_date_filters_added:
        natural_date_match = re.search(
            r'\b(0?[1-9]|[12]\d|3[01])\s+'
            r'(January|February|March|April|May|June|July|August|September|October|November|December|'
            r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+'
            r'(20\d{2})\b',
            question,
            flags=re.IGNORECASE,
        )

        if natural_date_match:
            day = int(natural_date_match.group(1))
            month_text = natural_date_match.group(2).lower()
            year = int(natural_date_match.group(3))

            natural_months = {
                'jan': 1, 'january': 1,
                'feb': 2, 'february': 2,
                'mar': 3, 'march': 3,
                'apr': 4, 'april': 4,
                'may': 5,
                'jun': 6, 'june': 6,
                'jul': 7, 'july': 7,
                'aug': 8, 'august': 8,
                'sep': 9, 'sept': 9, 'september': 9,
                'oct': 10, 'october': 10,
                'nov': 11, 'november': 11,
                'dec': 12, 'december': 12,
            }

            month = natural_months.get(month_text)

            if month:
                filters.extend([
                    {
                        'column': date_column,
                        'operator': 'year',
                        'value': year,
                        'type': 'date',
                    },
                    {
                        'column': date_column,
                        'operator': 'month',
                        'value': month,
                        'type': 'date',
                    },
                    {
                        'column': date_column,
                        'operator': 'date',
                        'value': f'{year:04d}-{month:02d}-{day:02d}',
                        'type': 'date',
                    },
                ])

                return _deduplicate_filters(filters)

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

    if not exact_date_present and not numeric_date_filters_added:
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
    # RELATIVE AVAILABLE MONTH / LAST N MONTHS
    # --------------------------------------------------------
    # Use periods actually available in the uploaded dataset.
    #
    # Supported:
    #   latest month
    #   last month
    #   previous month
    #   last N months
    #
    # "latest" = latest available period
    # "last"/"previous" = previous available period
    # "last N months" = latest N available monthly periods
    #
    # Missing months are NOT converted to zero.

    relative_month_match = re.search(
        r"\b(?:latest|last|previous)\s+(?:available\s+)?"
        r"(?:month|months)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    relative_n_month_match = re.search(
        r"\b(?:last|previous)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+months?\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    first_n_month_match = re.search(
        r"\bfirst\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+months?\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if relative_month_match or relative_n_month_match or first_n_month_match:
        available_dates = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if available_dates:
            available_months = sorted(
                {
                    (parsed_date.year, parsed_date.month)
                    for parsed_date in available_dates
                }
            )

            # ----------------------------------------------------
            # LAST N MONTHS
            # FIRST / LAST / PREVIOUS N MONTHS
            # ----------------------------------------------------
            if relative_n_month_match or first_n_month_match:
                n_match = relative_n_month_match or first_n_month_match
                n_value = n_match.group(1).lower()

                word_to_number = {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                    "four": 4,
                    "five": 5,
                    "six": 6,
                    "seven": 7,
                    "eight": 8,
                    "nine": 9,
                    "ten": 10,
                    "eleven": 11,
                    "twelve": 12,
                }

                requested_n = (
                    int(n_value)
                    if n_value.isdigit()
                    else word_to_number.get(n_value)
                )

                if not requested_n:
                    requested_n = 1

                if first_n_month_match:
                    selected_months = available_months[:requested_n]

                elif re.search(
                    r"\bprevious\s+",
                    question_norm,
                    flags=re.IGNORECASE,
                ):
                    selected_months = available_months[
                        -requested_n - 1:-1
                    ]

                else:
                    selected_months = available_months[-requested_n:]

                if selected_months:
                    start_year, start_month = selected_months[0]
                    end_year, end_month = selected_months[-1]

                    start_date = (
                        f"{start_year:04d}-{start_month:02d}-01"
                    )

                    if end_month == 12:
                        next_year = end_year + 1
                        next_month = 1
                    else:
                        next_year = end_year
                        next_month = end_month + 1

                    end_date_exclusive = (
                        f"{next_year:04d}-{next_month:02d}-01"
                    )

                    filters.extend(
                        [
                            {
                                "column": date_column,
                                "operator": ">=",
                                "value": start_date,
                                "type": "date",
                            },
                            {
                                "column": date_column,
                                "operator": "<",
                                "value": end_date_exclusive,
                                "type": "date",
                            },
                        ]
                    )

            # ----------------------------------------------------
            # SINGLE RELATIVE MONTH
            # ----------------------------------------------------
            else:
                latest_year, latest_month = available_months[-1]

                relative_text = (
                    relative_month_match.group(0).lower()
                )

                if relative_text.startswith(
                    ("last", "previous")
                ) and len(available_months) >= 2:
                    target_year, target_month = (
                        available_months[-2]
                    )
                else:
                    target_year, target_month = (
                        latest_year,
                        latest_month,
                    )

                filters.extend(
                    [
                        {
                            "column": date_column,
                            "operator": "year",
                            "value": target_year,
                            "type": "date",
                        },
                        {
                            "column": date_column,
                            "operator": "month",
                            "value": target_month,
                            "type": "date",
                        },
                    ]
                )
    # --------------------------------------------------------
    # FIRST / LAST / PREVIOUS N YEARS, QUARTERS, DAYS
    # Use only periods actually available in the dataset.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # SINGLE FIRST YEAR
    # first year -> first available year
    # --------------------------------------------------------

    first_single_year_match = re.search(
        r"\bfirst\s+(?:available\s+)?year\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if first_single_year_match:
        available_years = sorted(
            {
                parsed_date.year
                for row in rows
                for row_data in [
                    row.get("data", row)
                    if isinstance(row, dict)
                    else {}
                ]
                for parsed_date in [_parse_date(row_data.get(date_column))]
                if parsed_date
            }
        )

        if available_years:
            target_year = available_years[0]

            filters.extend(
                [
                    {
                        "column": date_column,
                        "operator": ">=",
                        "value": f"{target_year:04d}-01-01",
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "<",
                        "value": f"{target_year + 1:04d}-01-01",
                        "type": "date",
                    },
                ]
            )

    # --------------------------------------------------------
    # SINGLE RELATIVE YEAR
    # latest year  -> latest available year
    # last year     -> previous available year
    # previous year -> previous available year
    # --------------------------------------------------------

    relative_single_year_match = re.search(
        r"\b(latest|last|previous)\s+(?:available\s+)?year\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if relative_single_year_match:
        available_years = sorted(
            {
                parsed_date.year
                for row in rows
                for row_data in [
                    row.get("data", row)
                    if isinstance(row, dict)
                    else {}
                ]
                for parsed_date in [_parse_date(row_data.get(date_column))]
                if parsed_date
            }
        )

        if available_years:
            direction = relative_single_year_match.group(1).lower()

            if direction == "latest":
                target_year = available_years[-1]
            elif len(available_years) >= 2:
                target_year = available_years[-2]
            else:
                target_year = available_years[-1]

            filters.extend(
                [
                    {
                        "column": date_column,
                        "operator": ">=",
                        "value": f"{target_year:04d}-01-01",
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "<",
                        "value": f"{target_year + 1:04d}-01-01",
                        "type": "date",
                    },
                ]
            )

    # --------------------------------------------------------
    # SINGLE RELATIVE QUARTER
    #
    # latest quarter   -> latest available quarter
    # last quarter     -> previous available quarter
    # previous quarter -> previous available quarter
    #
    # Use only quarters that actually exist in the dataset.
    # --------------------------------------------------------

    relative_single_quarter_match = re.search(
        r"\b(latest|last|previous)\s+"
        r"(?:available\s+)?quarter\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if relative_single_quarter_match:
        available_quarters = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                quarter_number = (
                    (parsed_date.month - 1) // 3
                ) + 1

                available_quarters.append(
                    (
                        parsed_date.year,
                        quarter_number,
                    )
                )

        available_quarters = sorted(
            set(available_quarters)
        )

        if available_quarters:
            direction = (
                relative_single_quarter_match
                .group(1)
                .lower()
            )

            if (
                direction == "latest"
                or len(available_quarters) == 1
            ):
                target_year, target_quarter = (
                    available_quarters[-1]
                )
            else:
                target_year, target_quarter = (
                    available_quarters[-2]
                )

            start_month = (
                (target_quarter - 1) * 3
            ) + 1

            start_date = (
                f"{target_year:04d}-"
                f"{start_month:02d}-01"
            )

            if target_quarter == 4:
                next_year = target_year + 1
                next_month = 1
            else:
                next_year = target_year
                next_month = (
                    target_quarter * 3
                ) + 1

            end_date_exclusive = (
                f"{next_year:04d}-"
                f"{next_month:02d}-01"
            )

            filters.extend(
                [
                    {
                        "column": date_column,
                        "operator": ">=",
                        "value": start_date,
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "<",
                        "value": end_date_exclusive,
                        "type": "date",
                    },
                ]
            )

    # --------------------------------------------------------
    # SINGLE RELATIVE WEEK
    #
    # latest week   -> latest available 7-day week
    # last week     -> previous available 7-day week
    # previous week -> previous available 7-day week
    #
    # Use only dates that actually exist in the dataset.
    # --------------------------------------------------------

    relative_single_week_match = re.search(
        r"\b(latest|last|previous)\s+"
        r"(?:available\s+)?week\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if relative_single_week_match:
        available_dates = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date.date())

        available_dates = sorted(set(available_dates))

        if available_dates:
            direction = (
                relative_single_week_match
                .group(1)
                .lower()
            )

            latest_date = available_dates[-1]

            # Find the Monday of the latest available week.
            latest_week_start = (
                latest_date
                - __import__("datetime").timedelta(
                    days=latest_date.weekday()
                )
            )

            if direction == "latest":
                target_week_start = latest_week_start
            else:
                target_week_start = (
                    latest_week_start
                    - __import__("datetime").timedelta(days=7)
                )

            target_week_end = (
                target_week_start
                + __import__("datetime").timedelta(days=7)
            )

            filters.extend(
                [
                    {
                        "column": date_column,
                        "operator": ">=",
                        "value": target_week_start.strftime("%Y-%m-%d"),
                        "type": "date",
                    },
                    {
                        "column": date_column,
                        "operator": "<",
                        "value": target_week_end.strftime("%Y-%m-%d"),
                        "type": "date",
                    },
                ]
            )
    temporal_n_match = re.search(
        r"\b(first|last|previous|latest)\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"(days?|weeks?|quarters?|years?)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if temporal_n_match:
        direction = temporal_n_match.group(1).lower()
        n_value = temporal_n_match.group(2).lower()
        period = temporal_n_match.group(3).lower()

        word_to_number = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        requested_n = (
            int(n_value)
            if n_value.isdigit()
            else word_to_number.get(n_value, 1)
        )

        available_dates = []

        for row in rows:
            row_data = (
                row.get("data", row)
                if isinstance(row, dict)
                else {}
            )

            parsed_date = _parse_date(
                row_data.get(date_column)
            )

            if parsed_date:
                available_dates.append(parsed_date)

        if available_dates:
            if period.startswith("year"):
                available_periods = sorted(
                    {parsed_date.year for parsed_date in available_dates}
                )

                if direction == "first":
                    selected_periods = available_periods[:requested_n]
                else:
                    selected_periods = available_periods[-requested_n:]

                if selected_periods:
                    start_date = f"{selected_periods[0]:04d}-01-01"
                    end_year = selected_periods[-1] + 1
                    end_date_exclusive = f"{end_year:04d}-01-01"

                    filters.extend(
                        [
                            {
                                "column": date_column,
                                "operator": ">=",
                                "value": start_date,
                                "type": "date",
                            },
                            {
                                "column": date_column,
                                "operator": "<",
                                "value": end_date_exclusive,
                                "type": "date",
                            },
                        ]
                    )

            elif period.startswith("quarter"):
                available_periods = sorted(
                    {
                        (
                            parsed_date.year,
                            ((parsed_date.month - 1) // 3) + 1,
                        )
                        for parsed_date in available_dates
                    }
                )

                if direction == "first":
                    selected_periods = available_periods[:requested_n]
                else:
                    selected_periods = available_periods[-requested_n:]

                if selected_periods:
                    start_year, start_quarter = selected_periods[0]
                    end_year, end_quarter = selected_periods[-1]

                    start_month = ((start_quarter - 1) * 3) + 1
                    start_date = f"{start_year:04d}-{start_month:02d}-01"

                    if end_quarter == 4:
                        next_year = end_year + 1
                        next_month = 1
                    else:
                        next_year = end_year
                        next_month = (end_quarter * 3) + 1

                    end_date_exclusive = f"{next_year:04d}-{next_month:02d}-01"

                    filters.extend(
                        [
                            {
                                "column": date_column,
                                "operator": ">=",
                                "value": start_date,
                                "type": "date",
                            },
                            {
                                "column": date_column,
                                "operator": "<",
                                "value": end_date_exclusive,
                                "type": "date",
                            },
                        ]
                    )

            elif period.startswith("day"):
                available_periods = sorted(
                    {parsed_date.date() for parsed_date in available_dates}
                )

                if direction == "first":
                    selected_periods = available_periods[:requested_n]
                else:
                    selected_periods = available_periods[-requested_n:]

                if selected_periods:
                    start_date = selected_periods[0].strftime("%Y-%m-%d")
                    end_date = selected_periods[-1].strftime("%Y-%m-%d")

                    filters.extend(
                        [
                            {
                                "column": date_column,
                                "operator": ">=",
                                "value": start_date,
                                "type": "date",
                            },
                            {
                                "column": date_column,
                                "operator": "<=",
                                "value": end_date,
                                "type": "date",
                            },
                        ]
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
        r"((?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4}))"
        r"\s+(?:to|and)\s+"
        r"((?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4}))\b",
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


def _reconcile_partial_entity_filters(
    filters: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    A partial entity (for example "Pooja") is resolved against the
    actual dataset into a categorical "in" filter listing real values.
    A raw "=" / "contains" filter on the same column that carries only
    the partial value conflicts with it. It is dropped only when every
    resolved value contains the raw value as a whole-word fragment.
    """
    resolved: Dict[Any, List[str]] = {}

    for item in filters or []:
        if (
            isinstance(item, dict)
            and str(item.get("operator", "")).lower() in {"in", "one_of"}
            and isinstance(item.get("value"), (list, tuple, set))
            and item.get("value")
        ):
            resolved.setdefault(item.get("column"), []).extend(
                str(v).strip().lower() for v in item["value"]
            )

    if not resolved:
        return filters

    raw_operators = {
        "=", "==", "eq", "equals", "contains", "like", "icontains",
    }
    result = []

    for item in filters or []:
        if (
            isinstance(item, dict)
            and str(item.get("operator", "")).lower() in raw_operators
        ):
            raw = str(item.get("value") or "").strip().lower()
            values = resolved.get(item.get("column"))

            if raw and values and all(
                re.search(r"\b" + re.escape(raw) + r"\b", v)
                for v in values
            ):
                continue

        result.append(item)

    return result


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
                    [],
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
        r"\b(?:month|months|monthly)\s*(?:wise|wise)?\b",
        question_norm,
    ) or (
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\bmonths?\b",
            question_norm,
        )
    ):
        return {
            "column": date_column,
            "period": "month",
        }

    # --------------------------------------------------------
    # QUARTER
    # --------------------------------------------------------

    if re.search(
        r"\b(?:quarter|quarters|quarterly)\s*(?:wise|wise)?\b",
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
        r"\b(?:year|years|yearly|annual|annually)\s*(?:wise|wise)?\b",
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
    # TEMPORAL RANKING
    #
    # Examples:
    #   Which month has highest sales?
    #   Which month highest sales are done?
    #   Which year has highest revenue?
    #   Which quarter has highest profit?
    # --------------------------------------------------------

    temporal_ranking_match = (
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|"
            r"totalgst|total\s+gst|cgst|sgst|igst|quantity|qty|"
            r"invoice\s+(?:value|amount|total)|invoicevalue|invoiceamount|invoicetotal)\b",
            question_norm,
        )
    )

    if temporal_ranking_match:
        time_grouping = _extract_time_grouping(
            question,
            dataset,
            schema,
                    [],
        )

        if time_grouping:
            return time_grouping

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
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst|discount|unit\s+price|unitprice|price|quantity|qty|taxable|taxable\s+amount|taxableamount|cost|gross|gross\s+amount|grossamount|invoice\s+(?:value|amount|total)|invoicevalue|invoiceamount|invoicetotal|cgst|sgst|igst)\b",
            question_norm,
        )
    ):
        for candidate in (
            "customer",
            "customers",
            "party type",
            "party types",
            "party",
            "parties",
            "product",
            "products",
            "item",
            "items",
            "payment mode",
            "payment modes",
            "payment method",
            "payment methods",
            "party type",
            "party types",
            "partytypes",
            "partytype",
            "hsn code",
            "hsn codes",
            "hsncodes",
            "hsncode",
            "gst rate",
            "gst rates",
            "gstrates",
            "gstrate",
            "state",
            "states",
            "category",
            "categories",
        ):
            if re.search(
                rf"\b{re.escape(candidate)}\b",
                question_norm,
            ):
                # State queries may use "state", while the
                # actual source column can be PartyState.
                if candidate in ("state", "states"):
                    resolved = _resolve_column(
                        "PartyState",
                        dataset,
                        schema,
                    [],
                    )

                    if resolved:
                        return resolved

                resolved = _resolve_column(
                    candidate,
                    dataset,
                    schema,
                    [],
                )

                if resolved:
                    return resolved
                
                if candidate in ("party type", "party types"):
                    resolved = _resolve_column(
                        "PartyType",
                        dataset,
                        schema,
                    [],
                    )
                    if resolved:
                        return resolved

                if candidate in ("hsn code", "hsn codes"):
                    resolved = _resolve_column(
                        "HSN_Code",
                        dataset,
                        schema,
                    [],
                    )
                    if resolved:
                        return resolved

                if candidate in ("gst rate", "gst rates"):
                    resolved = _resolve_column(
                        "GST_Rate",
                        dataset,
                        schema,
                    [],
                    )
                    if resolved:
                        return resolved

                if candidate in ("state", "states"):
                    resolved = _resolve_column(
                        "PartyState",
                        dataset,
                        schema,
                    [],
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
                    [],
        )

        if resolved_status_column:
            return resolved_status_column
        
    # --------------------------------------------------------
    # ENTITY-FIRST NUMERIC THRESHOLD QUERIES
    #
    # Examples:
    #   Show products with profit above ?100000
    #   Show customers with sales above ?500000
    #   Show products with quantity above 500
    #
    # These queries need grouping BEFORE applying the numeric
    # threshold. Therefore we must identify the entity here.
    # --------------------------------------------------------

    numeric_entity_match = re.search(
        r"\b(?:show|list|find|get|display|give)\s+"
        r"(customers?|parties?|products?|items?|"
        r"suppliers?|vendors?)\b"
        r".*?"
        r"\b(?:with|having)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if numeric_entity_match:
        entity = numeric_entity_match.group(1).strip()

        entity_candidates = []

        if re.match(
            r"^(?:customer|customers|party|parties)$",
            entity,
            flags=re.IGNORECASE,
        ):
            entity_candidates = [
                "customer",
                "customers",
                "party name",
                "party",
                "PartyName",
            ]

        elif re.match(
            r"^(?:product|products|item|items)$",
            entity,
            flags=re.IGNORECASE,
        ):
            entity_candidates = [
                "product",
                "products",
                "item",
                "items",
                "Product",
            ]

        elif re.match(
            r"^(?:supplier|suppliers|vendor|vendors)$",
            entity,
            flags=re.IGNORECASE,
        ):
            entity_candidates = [
                "supplier",
                "suppliers",
                "vendor",
                "vendors",
                "SupplierName",
                "Supplier",
            ]

        for candidate in entity_candidates:
            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                    [],
            )

            if resolved:
                return resolved

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
        # "sales by customer in July 2025"
        # "GST by product during August 2025"
        # "profit by category for 2026"
        r"\bby\s+(.+?)(?=\s+(?:in|during|on|for|from|between|where|with|having|and|or)\b|$)",

        # "group by customer in July 2025"
        r"\bgroup(?:ed)?\s+by\s+(.+?)(?=\s+(?:in|during|on|for|from|between|where|with|having|and|or)\b|$)",

        # "per customer in July 2025"
        r"\bper\s+(.+?)(?=\s+(?:in|during|on|for|from|between|where|with|having|and|or)\b|$)",

        # "each customer in July 2025"
        r"\beach\s+(.+?)(?=\s+(?:in|during|on|for|from|between|where|with|having|and|or)\b|$)",
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
                    [],
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
                    [],
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
                    [],
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
                    [],
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
                    [],
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

        # ----------------------------------------------------
        # Remove query-intent and metric words from the
        # beginning of "... wise" expressions.
        #
        # Example:
        #   "show quantity product wise"
        #       -> "product"
        #
        #   "show sales customer wise"
        #       -> "customer"
        #
        #   "show quantity and sales product wise"
        #       -> "product"
        # ----------------------------------------------------

        candidate = re.sub(
            r"\b(?:show|give|list|display|return|fetch|"
            r"provide|find|get|tell|me|the|all|"
            r"total|sum|average|avg|mean|maximum|max|"
            r"minimum|min|highest|lowest|top|bottom|"
            r"count|number|of|and|"
            r"sales?|revenue|billing|turnover|"
            r"profit|discount|gst|cgst|sgst|igst|"
            r"invoice|invoices|amount|value|"
            r"quantity|qty)\b",
            " ",
            candidate,
            flags=re.IGNORECASE,
        )

        candidate = re.sub(
            r"\s+",
            " ",
            candidate,
        ).strip()

        if candidate:

            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                    [],
            )

            if resolved:
                return resolved

        # Preserve the original fallback behavior.
        original_candidate = wise_match.group(1).strip()

        resolved = _resolve_column(
            original_candidate,
            dataset,
            schema,
                    [],
        )

        if resolved:
            return resolved

        # ----------------------------------------------------
        # Fallback: try the original candidate.
        # ----------------------------------------------------

        resolved = _resolve_column(
            wise_match.group(1).strip(),
            dataset,
            schema,
                    [],
        )

        if resolved:
            return resolved

    if wise_match:
        candidate = wise_match.group(1).strip()

        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
                    [],
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
                    [],
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
                    [],
            )

            if resolved:
                return resolved

    # --------------------------------------------------------
    # FALLBACK: DATE COLUMN FOR YEAR / QUARTER GROUPING
    #
    # Detailed invoice datasets often contain InvoiceDate
    # instead of separate Year / Quarter columns.
    #
    # Example:
    #   year wise    -> InvoiceDate
    #   quarter wise -> InvoiceDate
    #
    # The query executor can then derive the requested
    # temporal period from the date column.
    # --------------------------------------------------------

    if re.search(
        r"\b(?:yearly|year\s+wise|year-wise|annual)\b",
        question_norm,
        flags=re.IGNORECASE,
    ):
        for candidate in (
            "InvoiceDate",
            "Invoice Date",
            "Date",
            "TransactionDate",
            "Transaction Date",
            "Bill Date",
            "Billing Date",
        ):
            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                    [],
            )

            if resolved:
                return resolved

    if re.search(
        r"\b(?:quarterly|quarter\s+wise|quarter-wise)\b",
        question_norm,
        flags=re.IGNORECASE,
    ):
        for candidate in (
            "InvoiceDate",
            "Invoice Date",
            "Date",
            "TransactionDate",
            "Transaction Date",
            "Bill Date",
            "Billing Date",
        ):
            resolved = _resolve_column(
                candidate,
                dataset,
                schema,
                    [],
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
    
    # ==========================================================
    # EARLY INVOICE COUNT HANDLING
    # ==========================================================

    invoice_count_query = bool(
        re.search(
            r"\b(?:invoice\s+count|invoice\s+counts|"
            r"count\s+(?:of\s+)?invoices?|"
            r"number\s+of\s+invoices?|"
            r"how\s+many\s+invoices?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if invoice_count_query:
        invoice_column = None

        # Find the real InvoiceNo source column.
        for source_column in _dataset_columns(
            dataset,
            schema,
                    [],
        ):
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

        # Fallback to resolver.
        if not invoice_column:
            invoice_column = _resolve_column(
                "InvoiceNo",
                dataset,
                schema,
                    [],
            )

        if invoice_column:
            return "count", invoice_column
    
    columns = _dataset_columns(
        dataset,
        schema,
                    [],
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

    # ----------------------------------------------------------
    # INVOICE COUNT -> ALWAYS COUNT THE INVOICE IDENTIFIER
    #
    # Examples:
    #   Show invoice count
    #   Show invoice count year wise
    #   Count invoices month wise
    #   Number of invoices by year
    #
    # InvoiceNo is an identifier, not a numeric measure.
    # Therefore never allow numeric-column fallback such as
    # GrossAmount to be selected for an invoice-count query.
    # ----------------------------------------------------------

    invoice_count_query = bool(
        re.search(
            r"\b(?:invoice\s+count|invoice\s+counts|"
            r"count\s+(?:of\s+)?invoices?|"
            r"number\s+of\s+invoices?|"
            r"how\s+many\s+invoices?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if invoice_count_query:
        function = "count"

        invoice_column = None

        # First: resolve from actual dataset/schema columns.
        for source_column in columns:
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

        # Fallback: resolve through the generic column resolver.
        if not invoice_column:
            invoice_column = _resolve_column(
                "InvoiceNo",
                dataset,
                schema,
                    [],
            )

        if invoice_column:
            aggregate_column = invoice_column

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
                    [],
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
        r"rows?|entries?)"
        r"(?=\s*$|\s+(?:by|per|wise|where|in|for)\b)",
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
                r"\b(?:profit|gst|totalgst|total\s+gst|quantity|qty)\b",
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
                    [],
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

    # Customer/product/payment ranking queries must NOT be
    # intercepted by the exact source-column scalar aggregate
    # shortcut.
    #
    # Example:
    #   "Which customer has the highest taxable amount?"
    #
    # This must become:
    #   GROUP BY customer -> SUM(TaxableAmount) -> highest
    #
    # while:
    #   "Show total TaxableAmount"
    #
    # must continue using the normal scalar aggregate path.
    grouped_ranking_request = bool(
        re.search(
            r"\b(?:highest|maximum|top|most|lowest|minimum|least|bottom)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:customer|customers|product|products|item|items|"
            r"payment\s+modes?|payment\s+methods?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    grouped_by_request = bool(
        re.search(
            r"\b(?:by|group(?:ed)?\s+by|per|each)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    explicit_aggregate_column_match = bool(
        function
        and not grouped_ranking_request
        and not grouped_by_request
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

        if re.search(r"\bdiscount\b", question_norm):
            ranking_columns = [
                "DiscountAmt",
                "Discount Amount",
                "DiscountAmount",
            ]
        else:
            ranking_columns = [
                "GrossAmount",
                "Gross Amount",
                "Sales Amount",
                "SalesAmount",
                "Revenue",
                "Turnover",
                "Amount",
                "Taxable Value",
                "TaxableAmount",
                "Invoice Value",
                "InvoiceTotal",
                "Invoice Total",
                "Total Amount",
                "TotalAmount",
            ]

        for preferred in ranking_columns:

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
                    [],
            )

            if resolved_trend_metric:
                # Detect whether the user explicitly requested a metric.
                #
                # This must support business aliases as well as exact
                # uploaded column names.
                #
                # Examples:
                #   discount       -> DiscountAmt
                #   profit         -> Profit
                #   quantity       -> Qty / Qty Sold / Quantity
                #   gst             -> GST / Total GST
                #   taxable amount -> Taxable Value
                #   invoice value  -> Invoice Value

                explicit_metric_aliases = {
                    "sales": (
                        "Invoice Value",
                        "Invoice Total",
                        "Total Amount",
                        "Sales Amount",
                        "Amount",
                    ),
                    "revenue": (
                        "Invoice Value",
                        "Invoice Total",
                        "Total Amount",
                        "Revenue",
                    ),
                    "discount": (
                        "DiscountAmt",
                        "Discount Amt",
                        "Discount Amount",
                        "DiscountAmount",
                    ),
                    "profit": (
                        "Profit",
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
                    "gst": (
                        "GST",
                        "Total GST",
                        "TotalGST",
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
                    "taxable amount": (
                        "Taxable Value",
                        "TaxableAmount",
                    ),
                    "taxable value": (
                        "Taxable Value",
                        "TaxableAmount",
                    ),
                }

                explicit_metric_requested = False

                # 1. Exact uploaded-column match.
                for column in numeric_columns:
                    column_norm = _normalize_text(column)

                    if not column_norm:
                        continue

                    if re.search(
                        rf"\b{re.escape(column_norm)}\b",
                        question_norm,
                        flags=re.IGNORECASE,
                    ):
                        explicit_metric_requested = True
                        break

                # 2. Business-language alias match.
                if not explicit_metric_requested:

                    for alias, possible_columns in explicit_metric_aliases.items():

                        if not re.search(
                            rf"\b{re.escape(alias)}\b",
                            question_norm,
                            flags=re.IGNORECASE,
                        ):
                            continue

                        for possible_column in possible_columns:

                            possible_norm = _normalize_text(
                                possible_column
                            )

                            if not possible_norm:
                                continue

                            for column in numeric_columns:

                                column_norm = _normalize_text(column)

                                if column_norm == possible_norm:
                                    explicit_metric_requested = True
                                    break

                            if explicit_metric_requested:
                                break

                        if explicit_metric_requested:
                            break

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
                    [],
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
                    "Gross Amount",
                    "GrossAmount",
                    "Sales Amount",
                    "SalesAmount",
                    "Revenue",
                    "Turnover",
                    "Amount",
                    "Invoice Value",
                    "InvoiceTotal",
                    "Invoice Total",
                    "Total Amount",
                    "TotalAmount",
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


            # HSN_Code is the grouping dimension in
            # queries such as 'total sales by HSN code'.
            # Do not sum HSN codes themselves; let the
            # generic sales metric fallback select GrossAmount.
            if (
                re.search(
                    r"\b(?:sale|sales|revenue|billing|turnover)\b",
                    question_norm,
                    flags=re.IGNORECASE,
                )
                and re.search(
                    r"\b(?:by|group(?:ed)?\s+by|per|each)\b",
                    question_norm,
                    flags=re.IGNORECASE,
                )
                and _normalize_text(column_text) in {
                    "hsncode",
                    "hsn code",
                }
            ):
                continue
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

    explicit_invoice_value_query = bool(
        re.search(
            r"\binvoice\s+(?:value|amount|total)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if (
        has_sales_term
        and numeric_columns
        and not explicit_invoice_value_query
    ):
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
            "Gross Amount",
            "GrossAmount",
            "Sales Amount",
            "SalesAmount",
            "Revenue",
            "Turnover",
            "Amount",
            "Invoice Value",
            "InvoiceTotal",
            "Invoice Total",
            "Total Amount",
            "TotalAmount",
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
        numeric_columns
        and re.search(
            r"\binvoice\s+(?:value|amount|total)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    ):
        # Explicit invoice value/amount/total means monetary
        # invoice value. "total" must aggregate with SUM,
        # not COUNT.
        if re.search(
            r"\btotal\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            function = "sum"
        
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
                    [],
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
                    [],
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
    # ==========================================================
    # 10. NO UNSAFE GENERIC NUMERIC FALLBACK
    # ==========================================================
    # Never select an arbitrary numeric column when the requested
    # metric could not be semantically resolved.
    # Unsupported metric -> no metric -> Data not available.

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
                    [],
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
                    [],
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
                    [],
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

def _extract_implicit_group_metrics(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect multiple business metrics used in grouped/chart-style
    questions where the aggregation word is omitted.

    Examples:
        Show sales and profit quarter wise
        Show quantity and sales product wise
        Show invoice count and discount year wise

    These are interpreted as SUM by default, except invoice count,
    which is interpreted as COUNT.
    """

    question_norm = _normalize_text(question)

    # This parser is only for grouped/chart-style questions.
    if not re.search(
        r"\b(?:wise|by|per|each|month|monthly|quarter|quarterly|"
        r"year|yearly|day|daily)\b",
        question_norm,
    ):
        return []

    metric_patterns = [
        (
            "invoice_count",
            "count",
            (
                "invoice count",
                "invoice counts",
                "number of invoices",
                "count of invoices",
                "count invoices",
                "invoices",
            ),
        ),
        (
            "sales",
            "sum",
            (
                "sales",
                "sale",
                "revenue",
                "billing",
                "turnover",
            ),
        ),
        (
            "profit",
            "sum",
            (
                "profit",
                "profits",
            ),
        ),
        (
            "quantity",
            "sum",
            (
                "quantity",
                "qty",
            ),
        ),
        (
            "discount",
            "sum",
            (
                "discount",
                "discount amount",
                "discount amt",
            ),
        ),
        (
            "gst",
            "sum",
            (
                "gst",
                "total gst",
            ),
        ),
        (
            "cgst",
            "sum",
            (
                "cgst",
            ),
        ),
        (
            "sgst",
            "sum",
            (
                "sgst",
            ),
        ),
        (
            "igst",
            "sum",
            (
                "igst",
            ),
        ),
        (
            "taxable",
            "sum",
            (
                "taxable amount",
                "taxable",
            ),
        ),
        (
            "cost",
            "sum",
            (
                "cost",
            ),
        ),
    ]

    detected = []

    for metric_name, function, aliases in metric_patterns:

        # Avoid matching "discount" inside another word.
        matched_alias = None

        for alias in aliases:
            if re.search(
                rf"\b{re.escape(alias)}\b",
                question_norm,
            ):
                matched_alias = alias
                break

        if not matched_alias:
            continue

        column = None

        if metric_name == "invoice_count":
            # Prefer InvoiceNo because it represents one invoice.
            for candidate in (
                "InvoiceNo",
                "Invoice No",
                "Invoice Number",
                "InvoiceNumber",
            ):
                column = _resolve_column(
                    candidate,
                    dataset,
                    schema,
                    [],
                )
                if column:
                    break

            # Fallback to any available column if InvoiceNo is absent.
            if not column:
                columns = _dataset_columns(
                    dataset,
                    schema,
                    [],
                )
                if columns:
                    column = columns[0]

        elif metric_name == "sales":
            column = _resolve_column(
                "sales",
                dataset,
                schema,
                    [],
            )

            if not column:
                column = _resolve_column(
                    "amount",
                    dataset,
                    schema,
                    [],
                )

            if not column:
                column = _resolve_column(
                    "GrossAmount",
                    dataset,
                    schema,
                    [],
                )

        elif metric_name == "profit":
            column = _resolve_column(
                "profit",
                dataset,
                schema,
                    [],
            )

        elif metric_name == "quantity":
            column = _resolve_column(
                "quantity",
                dataset,
                schema,
                    [],
            )

            if not column:
                column = _resolve_column(
                    "qty",
                    dataset,
                    schema,
                    [],
                )

        elif metric_name == "discount":
            column = _resolve_column(
                "discount amount",
                dataset,
                schema,
                    [],
            )

            if not column:
                column = _resolve_column(
                    "discount",
                    dataset,
                    schema,
                    [],
                )

        elif metric_name == "gst":
            column = _resolve_column(
                "total gst",
                dataset,
                schema,
                    [],
            )

            if not column:
                column = _resolve_column(
                    "gst",
                    dataset,
                    schema,
                    [],
                )

        else:
            column = _resolve_column(
                metric_name,
                dataset,
                schema,
                    [],
            )

        if not column:
            continue

        detected.append(
            {
                "metric": metric_name,
                "function": function,
                "column": column,
            }
        )

    # This parser should only activate for genuine multi-metric
    # questions. Single-metric questions continue through the
    # existing _extract_aggregate() path.
    if len(detected) < 2:
        return []

    # Remove duplicate columns/metrics.
    unique = []
    seen = set()

    for item in detected:
        key = (
            item["metric"],
            item["function"],
            item["column"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique
def _group_implicit_metrics(
    rows: List[Dict[str, Any]],
    group_column: str,
    metrics: List[Dict[str, Any]],
    time_period: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Group rows once and calculate multiple metrics for every group.

    Supports:
        sum
        count
    """

    if not rows or not group_column or not metrics:
        return []

    grouped = {}

    for row in rows:

        raw_group = row.get(group_column)

        if raw_group in (None, ""):
            continue

        group_value = raw_group

        # Temporal grouping.
        if time_period:
            parsed = _parse_date_value(raw_group)

            if parsed is not None:

                if time_period == "day":
                    group_value = parsed.strftime("%Y-%m-%d")

                elif time_period == "month":
                    group_value = parsed.strftime("%Y-%m")

                elif time_period == "year":
                    group_value = parsed.strftime("%Y")

                elif time_period == "quarter":
                    quarter = ((parsed.month - 1) // 3) + 1
                    group_value = (
                        f"{parsed.year}-Q{quarter}"
                    )

        key = str(group_value)

        if key not in grouped:
            grouped[key] = {
                group_column: group_value,
                "_rows": [],
            }

        grouped[key]["_rows"].append(row)

    output = []

    for group_value, group_data in grouped.items():

        group_rows = group_data["_rows"]

        result_row = {
            group_column: group_data[group_column]
        }

        for metric in metrics:

            metric_name = metric["metric"]
            function = metric["function"]
            column = metric["column"]

            if function == "count":

                values = [
                    row.get(column)
                    for row in group_rows
                    if row.get(column) not in (None, "")
                ]

                value = len(values)

            else:

                values = []

                for row in group_rows:
                    number = _to_number(
                        row.get(column)
                    )

                    if number is not None:
                        values.append(number)

                if function == "sum":
                    value = sum(values)

                elif function == "average":
                    value = (
                        sum(values) / len(values)
                        if values
                        else 0
                    )

                elif function == "max":
                    value = max(values) if values else 0

                elif function == "min":
                    value = min(values) if values else 0

                else:
                    value = sum(values)

            # Use the same human-friendly names expected
            # by the chart service.
            if metric_name == "sales":
                output_column = "Total Sales"

            elif metric_name == "profit":
                output_column = "Total Profit"

            elif metric_name == "quantity":
                output_column = "Total Qty"

            elif metric_name == "invoice_count":
                output_column = "Invoice Count"

            elif metric_name == "discount":
                output_column = "Total Discount"

            elif metric_name == "gst":
                output_column = "Total GST"

            elif metric_name == "cgst":
                output_column = "Total CGST"

            elif metric_name == "sgst":
                output_column = "Total SGST"

            elif metric_name == "igst":
                output_column = "Total IGST"

            elif metric_name == "taxable":
                output_column = "Total Taxable Amount"

            elif metric_name == "cost":
                output_column = "Total Cost"

            else:
                output_column = f"Total {column}"

            result_row[output_column] = value

        output.append(result_row)

    # Keep temporal results chronological.
    if time_period:
        output.sort(
            key=lambda row: str(
                row.get(group_column, "")
            )
        )

    return output

def _extract_multi_aggregate(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Detect multiple aggregate metrics in one question.

    Supports:
        total sales and total profit
        average sales and average profit
        maximum sales and minimum profit
        average GST and total discount

    Business terms such as sales/profit/GST are resolved to
    the actual source columns.
    """

    question_norm = _normalize_text(question)

    if not re.search(
        r"\b(?:total|sum|average|avg|mean|maximum|max|highest|minimum|min|lowest)\b",
        question_norm,
    ):
        return []

    dataset_columns = _dataset_columns(
        dataset,
        schema,
                    [],
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

    # Also inspect actual row values so numeric columns that are
    # not correctly mapped in the schema can still participate.
    for column in dataset_columns:

        if column in numeric_columns:
            continue

        values = [
            row.get(column)
            for row in rows[:100]
            if isinstance(row, dict)
            and row.get(column) not in (None, "")
        ]

        numeric_count = 0

        for value in values:
            try:
                float(
                    str(value)
                    .replace(",", "")
                    .replace("?", "")
                    .strip()
                )
                numeric_count += 1
            except (TypeError, ValueError):
                continue

        if values and numeric_count >= max(
            1,
            int(len(values) * 0.6),
        ):
            numeric_columns.append(column)

    results = []

    # ----------------------------------------------------------
    # Helper: add a resolved aggregate.
    # ----------------------------------------------------------

    def add_result(function: str, column: Optional[str]) -> None:

        if not column:
            return

        if column not in numeric_columns:
            return

        item = {
            "function": function,
            "column": column,
        }

        if item not in results:
            results.append(item)

    # ----------------------------------------------------------
    # Helper: convert aggregation word to execution function.
    # ----------------------------------------------------------

    def resolve_function(word: str) -> str:

        word = _normalize_text(word)

        if word in {
            "average",
            "avg",
            "mean",
        }:
            return "average"

        if word in {
            "maximum",
            "max",
            "highest",
        }:
            return "max"

        if word in {
            "minimum",
            "min",
            "lowest",
        }:
            return "min"

        return "sum"

    # ----------------------------------------------------------
    # Explicit source-column aggregates.
    #
    # Example:
    #   average Profit
    #   total GST
    #   maximum DiscountAmt
    # ----------------------------------------------------------

    for column in dataset_columns:

        column_norm = _normalize_text(column)

        if not column_norm:
            continue

        column_pattern = re.escape(column_norm)

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

        for aggregation_word in aggregation_matches:
            add_result(
                resolve_function(aggregation_word),
                column,
            )

    # ----------------------------------------------------------
    # Business-domain "sales".
    #
    # Generic sales -> actual sales/revenue column.
    #
    # Important:
    #   average sales -> average sales column
    #   maximum sales -> max sales column
    #   minimum sales -> min sales column
    #   total sales   -> sum sales column
    # ----------------------------------------------------------

    sales_matches = re.findall(
        r"\b("
        r"average|avg|mean|"
        r"maximum|max|highest|"
        r"minimum|min|lowest|"
        r"sum|total"
        r")\s+(?:of\s+)?sales?\b",
        question_norm,
    )

    if sales_matches:

        sales_column = _resolve_column(
            "sales",
            dataset,
            schema,
                    [],
        )

        if not sales_column:
            sales_column = _resolve_column(
                "amount",
                dataset,
                schema,
                    [],
            )

        for aggregation_word in sales_matches:
            add_result(
                resolve_function(aggregation_word),
                sales_column,
            )

    # ----------------------------------------------------------
    # Business-domain "profit".
    # ----------------------------------------------------------

    profit_matches = re.findall(
        r"\b("
        r"average|avg|mean|"
        r"maximum|max|highest|"
        r"minimum|min|lowest|"
        r"sum|total"
        r")\s+(?:of\s+)?profit\b",
        question_norm,
    )

    if profit_matches:

        profit_column = _resolve_column(
            "profit",
            dataset,
            schema,
                    [],
        )

        for aggregation_word in profit_matches:
            add_result(
                resolve_function(aggregation_word),
                profit_column,
            )

    # ----------------------------------------------------------
    # Business-domain quantity.
    # ----------------------------------------------------------

    quantity_matches = re.findall(
        r"\b("
        r"average|avg|mean|"
        r"maximum|max|highest|"
        r"minimum|min|lowest|"
        r"sum|total"
        r")\s+(?:of\s+)?"
        r"(?:quantity|qty)\b",
        question_norm,
    )

    if quantity_matches:

        quantity_column = _resolve_column(
            "quantity",
            dataset,
            schema,
                    [],
        )

        for aggregation_word in quantity_matches:
            add_result(
                resolve_function(aggregation_word),
                quantity_column,
            )

    # ----------------------------------------------------------
    # Business-domain GST.
    # ----------------------------------------------------------

    gst_matches = re.findall(
        r"\b("
        r"average|avg|mean|"
        r"maximum|max|highest|"
        r"minimum|min|lowest|"
        r"sum|total"
        r")\s+(?:of\s+)?gst\b",
        question_norm,
    )

    if gst_matches:

        gst_column = _resolve_column(
            "gst",
            dataset,
            schema,
                    [],
        )

        for aggregation_word in gst_matches:
            add_result(
                resolve_function(aggregation_word),
                gst_column,
            )

    # ----------------------------------------------------------
    # Business-domain discount.
    # ----------------------------------------------------------

    discount_matches = re.findall(
        r"\b("
        r"average|avg|mean|"
        r"maximum|max|highest|"
        r"minimum|min|lowest|"
        r"sum|total"
        r")\s+(?:of\s+)?discount\b",
        question_norm,
    )

    if discount_matches:

        discount_column = _resolve_column(
            "discount",
            dataset,
            schema,
                    [],
        )

        if not discount_column:
            discount_column = _resolve_column(
                "discount amount",
                dataset,
                schema,
                    [],
            )

        for aggregation_word in discount_matches:
            add_result(
                resolve_function(aggregation_word),
                discount_column,
            )

    # ----------------------------------------------------------
    # Preserve source order while removing duplicates.
    # ----------------------------------------------------------

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

    # This function is specifically for multiple metrics.
    if len(unique_results) < 2:
        return []

    return unique_results


# ============================================================
# IMPLICIT GROUPED MULTI-METRIC AGGREGATION
# ============================================================

def _extract_implicit_group_metrics(
    question: str,
    dataset: Dict[str, Any],
    schema: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect multiple metrics in natural-language grouped/chart queries.

    Examples:
        Show sales and profit quarter wise
        Show quantity and sales product wise
        Show invoice count and discount year wise
        Show GST and sales month wise

    This is intentionally separate from _extract_multi_aggregate()
    because those queries require explicit aggregation words such
    as "total", "sum", "average", etc.
    """

    question_norm = _normalize_text(question)

    # This helper is only for grouped/chart-style questions.
    if not re.search(
        r"\b(?:wise|by|per|each|month|quarter|year|day)\b",
        question_norm,
        flags=re.IGNORECASE,
    ):
        return []

    metric_patterns = [
        (
            "invoice_count",
            r"\b(?:invoice\s+count|invoice\s+counts|"
            r"number\s+of\s+invoices|count\s+of\s+invoices|"
            r"invoice\s+number\s+count)\b",
            "count",
            None,
        ),
        (
            "sales",
            r"\b(?:sales|sale|revenue|turnover|billing)\b",
            "sum",
            "sales",
        ),
        (
            "profit",
            r"\bprofit\b",
            "sum",
            "profit",
        ),
        (
            "quantity",
            r"\b(?:quantity|qty)\b",
            "sum",
            "quantity",
        ),
        (
            "discount",
            r"\bdiscount\b",
            "sum",
            "discount",
        ),
        (
            "gst",
            r"\bgst\b",
            "sum",
            "gst",
        ),
        (
            "cgst",
            r"\bcgst\b",
            "sum",
            "cgst",
        ),
        (
            "sgst",
            r"\bsgst\b",
            "sum",
            "sgst",
        ),
        (
            "igst",
            r"\bigst\b",
            "sum",
            "igst",
        ),
        (
            "taxable",
            r"\btaxable(?:\s+amount)?\b",
            "sum",
            "taxable",
        ),
        (
            "cost",
            r"\bcost\b",
            "sum",
            "cost",
        ),
    ]

    detected = []

    for metric_name, pattern, function, resolve_name in metric_patterns:

        if not re.search(
            pattern,
            question_norm,
            flags=re.IGNORECASE,
        ):
            continue

        # Resolve the actual source column.
        if function == "count":
            resolved_column = None

            # Prefer invoice-number columns when counting invoices.
            for candidate in (
                "InvoiceNo",
                "Invoice No",
                "Invoice Number",
                "invoice number",
                "invoice no",
            ):
                resolved_column = _resolve_column(
                    candidate,
                    dataset,
                    schema,
                    [],
                )

                if resolved_column:
                    break

        else:
            resolved_column = _resolve_column(
                resolve_name,
                dataset,
                schema,
                    [],
            )

            # ------------------------------------------------
            # Metric-specific fallbacks for dynamic business
            # datasets.
            #
            # Example:
            #   sales    -> GrossAmount / InvoiceTotal
            #   quantity -> Qty
            #   discount -> DiscountAmt
            # ------------------------------------------------

            if not resolved_column and metric_name == "sales":
                for candidate in (
                    "GrossAmount",
                    "Gross Amount",
                    "InvoiceTotal",
                    "Invoice Total",
                    "Total Amount",
                    "TotalAmount",
                    "Sales Amount",
                    "SalesAmount",
                    "Amount",
                    "Revenue",
                    "Turnover",
                ):
                    resolved_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                    [],
                    )

                    if resolved_column:
                        break

            elif not resolved_column and metric_name == "quantity":
                for candidate in (
                    "Qty",
                    "Quantity",
                ):
                    resolved_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                    [],
                    )

                    if resolved_column:
                        break

            elif not resolved_column and metric_name == "discount":
                for candidate in (
                    "DiscountAmt",
                    "Discount Amount",
                    "Discount",
                ):
                    resolved_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                    [],
                    )

                    if resolved_column:
                        break

            elif not resolved_column and metric_name == "profit":
                for candidate in (
                    "Profit",
                    "Total Profit",
                    "Profit Amount",
                ):
                    resolved_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                    [],
                    )

                    if resolved_column:
                        break

            elif not resolved_column and metric_name == "gst":
                for candidate in (
                    "TotalGST",
                    "Total GST",
                    "GST",
                ):
                    resolved_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                    [],
                    )

                    if resolved_column:
                        break

        if not resolved_column and function != "count":
            continue

        detected.append(
            {
                "metric": metric_name,
                "function": function,
                "column": resolved_column,
            }
        )

    # Remove duplicates while preserving order.
    unique = []
    seen = set()

    for item in detected:
        key = (
            item["metric"],
            item["function"],
            item["column"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    # We only want this helper to activate for 2+ metrics.
    if len(unique) < 2:
        return []

    return unique


def _group_multi_metrics(
    rows: List[Dict[str, Any]],
    group_column: str,
    metrics: List[Dict[str, Any]],
    time_period: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate multiple aggregates over the same groups.

    For normal metrics, reuse _group_aggregate().

    For metric-level COUNT, calculate one numeric count per
    group instead of using _group_aggregate()'s frequency
    breakdown format.

    Example:
        Show invoice count year wise

    Produces:
        2025 -> 4481
        2026 -> 3844
    """

    merged: Dict[str, Dict[str, Any]] = {}

    for metric in metrics:

        function = metric.get("function")
        column = metric.get("column")
        metric_name = metric.get("metric")

        # ----------------------------------------------------
        # COUNT METRIC
        #
        # In multi-metric queries such as:
        #
        #   Show invoice count and discount year wise
        #
        # COUNT means "number of non-empty values in this
        # column per group".
        #
        # Do NOT call _group_aggregate() here because its
        # COUNT-with-column mode creates a frequency breakdown:
        #
        #   Date | InvoiceNo | Count
        #
        # We need:
        #
        #   Date | Invoice Count
        # ----------------------------------------------------

        if function == "count":

            grouped_count: Dict[str, Dict[str, Any]] = {}

            for row in rows:

                if not isinstance(row, dict):
                    continue

                group_value = row.get(group_column)

                # Apply the same temporal grouping used by
                # _group_aggregate().
                if time_period:
                    parsed_group_date = _parse_date(
                        group_value
                    )

                    if parsed_group_date:

                        if time_period == "year":
                            group_value = str(
                                parsed_group_date.year
                            )

                        elif time_period == "quarter":
                            quarter = (
                                (parsed_group_date.month - 1)
                                // 3
                            ) + 1

                            group_value = (
                                f"{parsed_group_date.year}-Q{quarter}"
                            )

                        elif time_period == "month":
                            group_value = (
                                f"{parsed_group_date.year}-"
                                f"{parsed_group_date.month:02d}"
                            )

                        elif time_period == "day":
                            group_value = (
                                parsed_group_date.strftime(
                                    "%Y-%m-%d"
                                )
                            )

                group_key = str(group_value)

                if group_key not in grouped_count:

                    grouped_count[group_key] = {
                        group_column: group_value,
                        "count": 0,
                    }

                value = (
                    row.get(column)
                    if column
                    else None
                )

                if value not in (None, ""):

                    grouped_count[group_key][
                        "count"
                    ] += 1

            for group_key, grouped_row in (
                grouped_count.items()
            ):

                if group_key not in merged:

                    merged[group_key] = {
                        group_column: grouped_row.get(
                            group_column
                        ),
                    }

                if metric_name == "invoice_count":

                    result_column = "Invoice Count"

                else:

                    result_column = "Count"

                merged[group_key][result_column] = (
                    grouped_row.get("count", 0)
                )

            continue

        # ----------------------------------------------------
        # ALL NON-COUNT METRICS
        #
        # Keep the existing aggregation behavior.
        # ----------------------------------------------------

        grouped = _group_aggregate(
                    [],
            group_column,
            function,
            column,
            time_period=time_period,
        )

        for grouped_row in grouped:

            if not isinstance(grouped_row, dict):
                continue

            group_value = grouped_row.get(
                group_column,
            )

            group_key = str(
                group_value
            )

            if group_key not in merged:

                merged[group_key] = {
                    group_column: group_value,
                }

            # Find the aggregate value generated by
            # _group_aggregate().
            aggregate_value = None
            result_column = None

            for key, value in grouped_row.items():

                if key == group_column:
                    continue

                aggregate_value = value
                result_column = key
                break

            if metric_name == "sales":
                result_column = "Total Sales"

            elif metric_name == "profit":
                result_column = "Total Profit"

            elif metric_name == "quantity":
                result_column = "Total Quantity"

            elif metric_name == "discount":
                result_column = "Total Discount"

            elif metric_name == "gst":
                result_column = "Total GST"

            elif metric_name == "cgst":
                result_column = "Total CGST"

            elif metric_name == "sgst":
                result_column = "Total SGST"

            elif metric_name == "igst":
                result_column = "Total IGST"

            elif metric_name == "taxable":
                result_column = "Total Taxable Amount"

            elif metric_name == "cost":
                result_column = "Total Cost"

            elif metric_name == "invoice_count":
                result_column = "Invoice Count"

            if result_column:

                merged[group_key][result_column] = (
                    aggregate_value
                )

    # --------------------------------------------------------
    # Return merged multi-metric rows.
    # --------------------------------------------------------

    return list(merged.values())

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

        elif operator == "in":
            expected_values = (
                expected
                if isinstance(expected, (list, tuple, set))
                else [expected]
            )

            if any(
                _values_equal(actual, value)
                for value in expected_values
            ):
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
            # TEMPORAL COUNT
            #
            # Example:
            #   Show invoice count year wise
            #
            # Group:
            #   Date -> year
            #
            # Count:
            #   InvoiceNo
            #
            # We need ONE row per period:
            #   2025 -> 4480
            #   2026 -> 3845
            #
            # Do not expand InvoiceNo into separate rows.
            # ------------------------------------------------

            if time_period and aggregate_column:

                result.append(
                    {
                        group_column: group_value,
                        result_column: len(
                            [
                                row
                                for row in group_rows
                                if row.get(aggregate_column)
                                not in (None, "")
                            ]
                        ),
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
    # SEMANTIC QUERY COMPATIBILITY
    # ==========================================================
    #
    # Prefer datasets that can satisfy the requested entity AND
    # metric together.
    #
    # Example:
    #   "which client has highest sales"
    #
    # The winning dataset should contain:
    #   client/customer -> PartyName
    #   sales           -> GrossAmount
    #
    # This is intentionally schema-driven. It does not special-case
    # a particular natural-language query.
    # ==========================================================

    try:
        ranking_match = re.search(
            r"\b(?:which|what)\s+(.+?)\s+"
            r"(?:has|have|with)\s+"
            r"(?:highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
            r"(.+?)\s*$",
            question_text,
            flags=re.IGNORECASE,
        )

    
        if ranking_match:
                requested_entity = ranking_match.group(1).strip()
                requested_metric = re.sub(
                    r"[?!.]+$",
                    "",
                    ranking_match.group(2).strip(),
                ).strip()

                # Resolve the requested grouping concept against the
                # current dataset schema.
                resolved_group = _resolve_column(
                    requested_entity,
                    dataset,
                    schema,
                    [],
                )

                # Try the existing semantic aliases through the same
                # resolver. No physical source column is hardcoded.
                if not resolved_group:
                    entity_aliases = {
                        "client": (
                            "customer",
                            "party",
                            "party name",
                        ),
                        "buyer": (
                            "customer",
                            "party",
                            "party name",
                        ),
                        "customer": (
                            "customer",
                            "party",
                            "party name",
                        ),
                        "party": (
                            "party",
                            "party name",
                            "customer",
                        ),
                        "item": (
                            "item",
                            "product",
                        ),
                    }

                    entity_norm = _normalize_text(
                        requested_entity
                    )

                    for alias, candidates in entity_aliases.items():
                        if not re.search(
                            rf"\b{re.escape(alias)}s?\b",
                            entity_norm,
                            flags=re.IGNORECASE,
                        ):
                            continue

                        for candidate in candidates:
                            resolved_group = _resolve_column(
                                candidate,
                                dataset,
                                schema,
                                [],
                            )
                            if resolved_group:
                                break

                        if resolved_group:
                            break

                # Resolve the requested metric against the same dataset.
                resolved_metric = None

                if requested_metric:
                    try:
                        resolved_metric = _resolve_universal_metric(
                            requested_metric,
                            dataset,
                            schema,
                            [],
                        )
                    except Exception:
                        resolved_metric = None

                # Strong preference only when BOTH semantic requirements
                # are actually supported by this dataset.
                if resolved_group and resolved_metric:
                    score += 750

                # A dataset that supports only one side should not receive
                # this compatibility bonus.
                elif resolved_group or resolved_metric:
                    score += 100

    except Exception:
        # Dataset scoring must never fail because semantic resolution
        # is unavailable for a particular dataset.
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
    # INVOICE COUNT / INVOICE NUMBER QUERY PREFERENCE
    # ==========================================================
    #
    # Invoice-count questions should prefer a transaction-level
    # dataset containing an invoice identifier such as InvoiceNo.
    #
    # This prevents summary datasets such as "Monthly Trend"
    # from winning merely because they contain an "Invoices"
    # or "Invoice Value" column.
    # ==========================================================

    invoice_count_query = bool(
        re.search(
            r"\b(?:invoice\s+count|invoice\s+counts|"
            r"count\s+(?:of\s+)?invoices?|"
            r"number\s+of\s+invoices?|"
            r"how\s+many\s+invoices?)\b",
            question_text,
            flags=re.IGNORECASE,
        )
    )

    if invoice_count_query:
        normalized_invoice_columns = {
            _normalize_column(column)
            for column in columns
            if _normalize_column(column)
        }

        invoice_identifier_columns = {
            "invoiceno",
            "invoice number",
            "invoice no",
            "bill no",
            "bill number",
            "invoice id",
            "invoice identifier",
        }

        invoice_identifier_match = (
            normalized_invoice_columns
            .intersection(
                {
                    _normalize_column(value)
                    for value in invoice_identifier_columns
                }
            )
        )

        if invoice_identifier_match:
            # Strong preference for transaction-level datasets
            # containing an actual invoice identifier.
            score += 500

        # Summary datasets with only an invoice-count/metric
        # column should not beat transaction-level invoice data.
        summary_invoice_columns = {
            "invoices",
            "invoice count",
            "invoice counts",
            "invoice value",
            "total invoice value",
        }

        summary_match = (
            normalized_invoice_columns
            .intersection(
                {
                    _normalize_column(value)
                    for value in summary_invoice_columns
                }
            )
        )

        if (
            summary_match
            and not invoice_identifier_match
        ):
            score -= 100
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
    # contains a genuine free-form categorical value.
    #
    # Metric/time-analysis queries such as:
    #   "Show invoice count and discount year wise"
    #   "Show sales month wise"
    #   "Show profit quarter wise"
    #
    # do not need a full dataset row scan during dataset
    # selection. Their columns are resolved from schema/metadata.
    #
    # Free-form value queries such as:
    #   "sales for Delhi"
    #   "customer Shalini Sharma"
    #   "product Ladies Watch"
    #
    # still use the row-value matching logic.
    time_or_metric_query = bool(
        re.search(
            r"\b(?:year|yearly|annual|month|monthly|quarter|"
            r"quarterly|day|daily|week|weekly|"
            r"wise|trend|over\s+time|period)\b",
            question_text,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|invoice|invoices|"
            r"quantity|qty|amount|value|discount|taxable|gst|cgst|"
            r"sgst|igst|profit|cost|total|count|average|avg|mean|"
            r"maximum|max|highest|minimum|min|lowest|top|bottom)\b",
            question_text,
            flags=re.IGNORECASE,
        )
    )

    if row_match_tokens and not time_or_metric_query:

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
            r"\b(?:sales?|sale|selling|revenue|turnover|billing|"
            r"business|business\s+value|business\s+amount|"
            r"sales\s+value|selling\s+value|business\s+done)\b",
            question_text,
        )
        and not re.search(
            r"\b(?:by|per|each|product|products|customer|customers|"
            r"party|parties|category|categories|payment|"
            r"month|monthly|day|daily|date|year|yearly|"
            r"profit)\b",
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

    text = _normalize_query(question)

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
        "original_question": question,
        "question": text,
        "intent": intent,
        "export_requested": export_requested,
        "export_format": export_format,
    }
    
# ============================================================
# UNIVERSAL QUERY PLANNER
# ============================================================

def universal_query_planner(
    state: DynamicAgentState,
) -> DynamicAgentState:
    """
    Convert the user's natural-language query into a canonical
    query that the existing deterministic query engine can execute.

    The LLM is used only for:
        - understanding natural language
        - synonyms
        - spelling mistakes
        - Hindi / Hinglish
        - mapping business terms to actual dataset columns
        - temporal intent interpretation

    The LLM MUST NOT calculate numeric answers.

    Actual calculations remain inside the existing Python/SQL
    execution engine.
    """

    original_question = (
        state.get("original_question")
        or state.get("question")
        or ""
    ).strip()

    dataset = state.get("dataset") or {}
    schema = state.get("schema") or []

    if not original_question:
        return {
            **state,
            "query_plan": {
                "status": "DATA_NOT_AVAILABLE",
                "reason": "Empty query",
            },
            "error": "Information is not available in the uploaded data.",
        }

    # --------------------------------------------------------
    # Build schema description.
    #
    # Only actual uploaded columns are provided to the model.
    # No full dataset is sent.
    # --------------------------------------------------------

    schema_lines = []

    for item in schema:
        if not isinstance(item, dict):
            continue

        source_column = item.get("source_column")
        data_type = item.get("data_type")
        normalized_name = item.get("normalized_column")

        if not source_column:
            continue

        schema_lines.append(
            {
                "column": str(source_column),
                "data_type": str(data_type or ""),
                "normalized_name": str(
                    normalized_name or ""
                ),
            }
        )

    if not schema_lines:
        return {
            **state,
            "query_plan": {
                "status": "DATA_NOT_AVAILABLE",
                "reason": "Dataset schema is empty",
            },
            "error": "Information is not available in the uploaded data.",
        }

    dataset_name = str(
        dataset.get("name")
        or dataset.get("filename")
        or dataset.get("file_name")
        or "uploaded dataset"
    )

    dataset_type = str(
        dataset.get("data_type")
        or state.get("dataset_type")
        or ""
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Tell the model that temporal expressions refer to the
    # latest period AVAILABLE IN THE DATASET, not today's date.
    # --------------------------------------------------------

    prompt = f"""
You are the Universal Query Planner for a business analytics
application.

Your job is to understand the user's business question and
convert it into ONE canonical English query that an existing
deterministic Python query engine can execute.

You are NOT the calculator.

Never calculate sales, profit, quantity, GST, discount, counts,
percentages, or any other numeric answer.

The actual uploaded dataset will be queried later by Python.

DATASET:
{dataset_name}

DATASET TYPE:
{dataset_type}

AVAILABLE COLUMNS:
{schema_lines}

USER QUESTION:
{original_question}

IMPORTANT RULES:

1. Use ONLY columns that actually exist in AVAILABLE COLUMNS.

2. Never invent a column.

3. Business synonyms are allowed ONLY when they refer to
   the same business concept.

   Examples of valid semantic mappings:

   customer -> PartyName / Customer Name / actual customer column
   client -> customer column
   buyer -> customer column

   sales -> actual sales/revenue amount column
   sale -> actual sales amount column
   revenue -> actual sales/revenue amount column
   turnover -> actual sales/revenue amount column
   billing -> actual sales/billing amount column

   profit -> actual profit column

   qty -> actual quantity column
   quantity -> actual quantity column

   GST -> actual GST / TotalGST column
   CGST -> actual CGST column
   SGST -> actual SGST column
   IGST -> actual IGST column

   discount -> actual discount amount/percentage column

   invoice value -> actual invoice-total/value column
   invoice amount -> actual invoice amount column
   invoice total -> actual invoice-total column

   product -> actual Product / Item column
   item -> actual Product / Item column

   state -> actual state column
   category -> actual category column

   IMPORTANT:
   Do NOT treat different business concepts as synonyms merely
   because an available numeric column could be used to calculate
   a number.

   Examples of INVALID substitutions:

   purchase != sales
   purchase != taxable amount
   purchase != invoice total
   purchase != revenue

   salary != profit
   salary != sales
   salary != taxable amount

   phone number != GSTIN
   phone number != invoice number

   city != state
   city != party state

   If the requested business concept does not exist in the
   AVAILABLE COLUMNS, return DATA_NOT_AVAILABLE.

   Never use a merely similar numeric column as a substitute for
   a missing business concept.

   3A. SALES / INVOICE VALUE PRIORITY:

      When AVAILABLE COLUMNS contains a dedicated sales amount
      column such as GrossAmount, SalesAmount, Sales, Revenue,
      Turnover, or BillingAmount:

      - "sales", "sale", "revenue", "turnover", and "billing"
        MUST refer to that dedicated sales amount column.
      - Do NOT map generic "sales" to InvoiceTotal merely because
        InvoiceTotal is numeric.
      - "invoice value", "invoice amount", and "invoice total"
        refer to InvoiceTotal or the actual invoice-total column.
      - Therefore, if both GrossAmount and InvoiceTotal exist:
          sales -> GrossAmount
          invoice value -> InvoiceTotal

      This distinction is mandatory even when both columns are
      numeric.
      
    3B. ADDITIONAL SALES / BUSINESS SYNONYMS:

      The following expressions refer to the SALES business
      concept when a dedicated sales amount column exists:

      - business value
      - business amount
      - business done
      - total business
      - sales amount
      - sales value
      - selling amount
      - selling value
      - selling
      - selling done
      - kitni selling hui
      - kitna business hua
      - kitna business hua hai
      - kitni sales hui
      - kitni sale hui
      - kitna sale hua
      - business kitna hua

      These expressions MUST map to the same dedicated sales
      amount column used for "sales".

      If both GrossAmount and InvoiceTotal exist:
          business value -> GrossAmount
          sales amount -> GrossAmount
          selling -> GrossAmount
          kitni selling hui -> GrossAmount
          kitna business hua -> GrossAmount

      Never map these sales expressions to InvoiceTotal merely
      because InvoiceTotal is numeric.

   3C. ADDITIONAL PROFIT SYNONYMS:

      The following expressions refer to the PROFIT business
      concept when a dedicated profit column exists:

      - earning
      - earnings
      - gain
      - gains
      - profit amount
      - profit value
      - profit earned
      - kamai
      - kamaai
      - fayda
      - faayda
      - kitna profit hua
      - kitni kamai hui
      - kitna fayda hua
      - kitna gain hua

      These expressions MUST map to the same dedicated profit
      column used for "profit".

      Example:
          earning -> Profit
          gain -> Profit
          kamai -> Profit
          fayda -> Profit

      Do NOT map earning, gain, kamai, or fayda to sales,
      invoice value, taxable amount, or another numeric column.

   3D. CONTEXT-SAFE SEMANTIC MAPPING:

      Semantic synonyms are allowed only when the corresponding
      business concept can be resolved against AVAILABLE COLUMNS.

      For example:

      If AVAILABLE COLUMNS contains:
          GrossAmount
          InvoiceTotal
          Profit

      then:
          business value -> GrossAmount
          selling -> GrossAmount
          earning -> Profit
          gain -> Profit
          kamai -> Profit
          fayda -> Profit

      If AVAILABLE COLUMNS does NOT contain a sales amount concept,
      do not invent one.

      If AVAILABLE COLUMNS does NOT contain a profit concept,
      do not invent one.

      If a requested concept cannot be resolved safely, return:
          status = "DATA_NOT_AVAILABLE"

      Never substitute an unrelated numeric column.

4. Prefer the exact uploaded source column when possible.

5. Understand English, Hindi and Hinglish.

   Examples:
   "sabse zyada sales wala customer"
   "kis customer ki highest sale hai"
   "customer wise profit batao"
   "last month ka total"
   "pichle mahine ki sales"
   "august me highest sales"

   These should be understood as business queries.
    5A. DATA-AWARE NATURAL LANGUAGE RESOLUTION

    The user does NOT need to know the exact uploaded column names or
    exact stored values.

    Understand the user's meaning using the uploaded dataset context.

    PARTIAL NAME MATCHING:

    If the user provides only part of a customer, party, product,
    employee, category, or other uploaded value, resolve it against
    the actual uploaded data when available.

    Example:

    Uploaded value:
    "Pooja Sharma"

    User:
    "Pooja ki sales"

    Interpret the request as sales for the matching uploaded customer.

    IMPORTANT:
    - Never invent the missing part of a name.
    - Only complete a partial name when the uploaded data supports it.
    - If exactly one uploaded value matches, use that value.
    - If multiple values match, do not arbitrarily choose one.
    - If a unique answer is required but the match is ambiguous,
    return DATA_NOT_AVAILABLE or preserve the filter for Python
    resolution.

    Examples:

    "Pooja" -> matching PartyName value such as "Pooja Sharma"
    "Rahul" -> matching uploaded customer/employee value
    "Sharma" -> matching uploaded PartyName values

    The Python execution layer must verify the final value against
    actual uploaded rows.

    VALUE MATCHING:

    Resolve natural-language references to actual uploaded values.

    Examples:

    "watch" -> matching Product/Category values
    "mobile" -> matching Product/Category values
    "pooja" -> matching PartyName values
    "cash" -> matching PaymentMode values

    Never invent a matching value.

    If no matching value exists in the uploaded data, return
    DATA_NOT_AVAILABLE.

    5B. SPELLING ERROR AND TYPO HANDLING

    Correct obvious spelling mistakes internally before interpreting
    the query.

    Examples:

    custmer -> customer
    customer -> customer
    profitt -> profit
    proft -> profit
    saless -> sales
    sles -> sales
    quntity -> quantity
    quantaty -> quantity
    avergae -> average
    avrage -> average
    avrg -> average
    invoce -> invoice
    invc -> invoice
    prodct -> product
    catgory -> category
    maxium -> maximum
    minmum -> minimum

    Understand spelling mistakes even when the misspelled word is
    combined with other words.

    Examples:

    "avergae profit"
    -> average profit

    "profitt latest month"
    -> profit latest month

    "quntity by product"
    -> quantity by product

    "top custmers by saless"
    -> top customers by sales

    Do not reject a query merely because of spelling mistakes.

    If the intended concept cannot be determined safely, return
    DATA_NOT_AVAILABLE instead of guessing.

    5C. FIRST / EARLIEST / LATEST / PREVIOUS PERIOD

    Temporal words MUST be resolved relative to the actual uploaded
    dataset.

    IMPORTANT:

    "first month" means the earliest month actually present in the
    uploaded dataset.

    "first year" means the earliest year actually present.

    "latest month" means the latest month actually present.

    "latest year" means the latest year actually present.

    "previous month" means the immediately preceding available month.

    "previous year" means the immediately preceding available year.

    "last 3 months" means the three latest available months.

    Do NOT assume:

    first month = January
    first year = 2020
    latest month = current calendar month
    latest year = current calendar year

    unless the uploaded dataset actually contains and supports that
    interpretation.

    Examples:

    "first month sales"
    -> sales for the earliest available month

    "latest month profit"
    -> profit for the latest available month

    "previous month sales"
    -> sales for the month immediately before the latest available month

    "first month average sales"
    -> average sales for the earliest available month

    The actual period must ultimately be verified by Python against the
    uploaded Date column.

    5D. TIME EXPRESSIONS

    Understand:

    first month
    earliest month
    starting month

    latest month
    last month
    most recent month

    first year
    earliest year

    latest year
    current/latest available year

    previous year
    prior year

    last 3 months
    previous 3 months

    first quarter
    earliest quarter

    latest quarter
    most recent quarter

    Q1
    Q2
    Q3
    Q4

    January 2026
    08-2026
    2026-08
    15-08-2026
    15 August 2026

    Preserve the temporal meaning in the query plan.

    Do NOT calculate numeric results.

    Do NOT invent missing dates.
6. Correct obvious spelling mistakes internally.

   Examples:
   custmer -> customer
   profitt -> profit
   saless -> sales
   quntity -> quantity
   invoce -> invoice

7. Temporal expressions MUST use the latest period available
   in the uploaded dataset.

   "latest month"
   "last month"
   "pichla month"
   "latest year"

   must NOT be interpreted using today's calendar date.
   DATA-AWARE VALUE RESOLUTION

    The LLM must understand the user's meaning, but it must never invent actual values that are not present in the uploaded dataset.

    Examples:

    User:
    "Pooja ki sales"

    If AVAILABLE COLUMNS contains:
    PartyName, GrossAmount, Date, Product

    The planner should understand:
    - customer/entity column = PartyName
    - sales metric = GrossAmount
    - user-provided value = "Pooja"

    Do NOT invent:
    "Pooja Sharma"

    Instead, preserve the user value "Pooja" for Python-side data resolution.

    Python will check the actual uploaded PartyName values and may resolve:
    "Pooja" -> "Pooja Sharma"

    Only an actual value present in the uploaded dataset may be used.

    Similarly:

    User:
    "first month sales"

    The planner should understand that:
    - metric = sales
    - aggregate_column = the actual sales source column
    - time position = first/earliest available period

    Do NOT assume January 2024, January 2025, January 2026, or any other month.

    Python must determine the earliest actual month available in the uploaded dataset.

    Similarly:

    User:
    "latest month sales"

    Do NOT use the current calendar month automatically.

    Python must determine the latest month actually present in the uploaded dataset.

    The LLM is responsible for:
    - understanding intent
    - correcting spelling
    - identifying metric
    - identifying source column
    - identifying entity/filter
    - identifying time intent
    - identifying aggregation
    - creating the query plan

    Python is responsible for:
    - resolving actual uploaded values
    - resolving partial names
    - resolving spelling against actual values when safely possible
    - resolving first/earliest available period
    - resolving latest available period
    - resolving previous period
    - validating columns
    - validating values
    - filtering actual rows
    - calculating actual numeric results

    Never invent missing data.
    Never guess an entity value.
    Never guess a date/period that is not present in the uploaded dataset.

8. If the requested metric, dimension, entity type, or information
   cannot be represented using the AVAILABLE COLUMNS, return:

   status = "DATA_NOT_AVAILABLE"

9. Do not invent values or columns.

10. Keep the canonical query simple and explicit.

   10A. Preserve ALL requested business metrics when the user asks
       for multiple metrics in the same question.

       Examples:

       "sales and profit last 3 months"
       -> "Show sales and profit for the last 3 months, grouped by month"

       "sales profit average last 3 months"
       -> "Show average sales and average profit for the last 3 months"

       "sales and GST month wise"
       -> "Show sales and GST grouped by month"

       "quantity and discount product wise"
       -> "Show quantity and discount grouped by product"

       IMPORTANT:
       - Never silently drop one of the requested metrics.
       - Multiple metrics are valid even though the JSON has one
         "metric" field.
       - For multiple metrics, "metric" may contain a comma-separated
         list of business metrics.
       - Do NOT mark a query DATA_NOT_AVAILABLE merely because
         "metric" contains multiple requested metrics.
       - Validate each requested metric concept separately.
       - Preserve the original multi-metric meaning in canonical_query.


11. Preserve ranking limits.

   "top 5 customers by sales"
   -> "Show top 5 customers by total sales"

12. Preserve grouping.

   "customer wise profit"
   -> "Show total profit grouped by customer"

13. Preserve aggregation.

   AGGREGATE FUNCTION MAPPING:
   - total, sum, "how much", "kitna total" -> "sum"
   - average, avg, mean, ausat -> "average"
   - maximum, max, highest, largest, "sabse zyada" -> "max"
   - minimum, min, lowest, smallest, "sabse kam" -> "min"
   - median, middle value -> "median"
   - count, "how many", "number of" -> "count"

   Put the requested aggregation in "aggregate_function".
   Do NOT calculate the numeric result.
   If no aggregation is explicitly requested, infer "sum" for business metrics when the user asks for the metric itself or asks for it for a time period.


   "average invoice value"
   -> "Show average invoice value"
    13A. DEFAULT AGGREGATION FOR BUSINESS METRICS

    If the user asks for a business metric without explicitly specifying
    an aggregation function, use SUM.

    Examples:

    "profit latest month"
    -> aggregate_function = "sum"

    "sales 2026"
    -> aggregate_function = "sum"

    "quantity August"
    -> aggregate_function = "sum"

    "GST last year"
    -> aggregate_function = "sum"

    "first month sales"
    -> aggregate_function = "sum"

    "average profit"
    -> aggregate_function = "average"

    "avergae profit"
    -> aggregate_function = "average"

    "highest sales"
    -> aggregate_function = "max"

    "lowest profit"
    -> aggregate_function = "min"

    "how many invoices"
    -> aggregate_function = "count"

    Use null ONLY when aggregation does not apply, such as:

    - detail records
    - projection
    - lookup
    - raw transaction rows
14. Preserve comparisons.

   "July vs August sales"
   -> "Compare sales for July and August"

15. Preserve filters.

   "sales above 50000"
   -> "Show sales above 50000"

16. Preserve detail and lookup intent exactly.

   IMPORTANT:
   - If the user asks to "show invoices", "list invoices", "display invoices", "show transactions", or similar detail records, DO NOT convert the request into a projection of a single column such as InvoiceNo.
   - Preserve the requested entity as the canonical query.
   - Example:
     "show invoices for Pooja Sharma"
     -> "Show invoices for Pooja Sharma"
   - Example:
     "list invoices for Pooja Sharma"
     -> "List invoices for Pooja Sharma"
   - Do NOT rewrite:
     "show invoices for Pooja Sharma"
     -> "Show InvoiceNo for PartyName = 'Pooja Sharma'"
   - Only use operation = "projection" when the user explicitly asks for specific columns.
     Example:
     "show InvoiceNo and Date for Pooja Sharma"
     -> operation = "projection"
   - A request for invoices/transactions without explicit column names means detail rows, not a column projection.

16. Do not answer the question yourself.

Return ONLY valid JSON.

Required JSON structure:

{{
  "status": "OK" or "DATA_NOT_AVAILABLE",
  "canonical_query": "...",
  "operation": "aggregate|group_aggregate|ranking|comparison|filter|projection|lookup|count|search",
  "metric": "...",
  "metrics": [],
  "aggregate_function": "sum|average|max|min|median|count|null",
  "aggregate_column":"...",
  "group_by": "...",
  "filters": [],
  "time": null,
  "limit": null,
  "direction": "asc|desc|null",
  "reason": ""
}}
AGGREGATE COLUMN RULES

"aggregate_column":
- Must contain the actual uploaded source column used for the requested metric.
- Must exist in AVAILABLE COLUMNS.
- Must be resolved from the uploaded dataset schema.
- Never invent a column.
- Never use an unrelated numeric column as a substitute.
- If the requested metric cannot be mapped to an available source column, return DATA_NOT_AVAILABLE.

Examples:
- profit -> "Profit"
- quantity -> "Qty"
- sales -> "GrossAmount" when GrossAmount is the dedicated sales column
- GST -> "TotalGST" when TotalGST is the requested GST amount
- invoice value -> "InvoiceTotal"
- taxable amount -> "TaxableAmount"
- discount -> "DiscountAmt"
- cost -> "Cost"

Important:
The LLM must identify the SOURCE COLUMN only.
The LLM must NOT calculate the numeric result.
Python will calculate the actual result from uploaded data.
Additional structured fields:

"metrics":
- List every requested metric separately.
- Example:
  "sales and profit"
  -> ["sales", "profit"]
- For a single metric:
  ["sales"]

"filters":
- Preserve explicit filters from the user query.
- Each filter should contain:
  {{
    "column": "...",
    "operator": "...",
    "value": "..."
  }}
- Use only actual uploaded columns or valid business concepts.

"time":
- Preserve explicit temporal intent.
- Example:
  "latest month"
  -> {{
       "type": "relative",
       "period": "month",
       "position": "latest"
     }}
- Example:
  "last 3 months"
  -> {{
       "type": "relative",
       "period": "month",
       "count": 3,
       "position": "last"
     }}
- Example:
  "August 2026"
  -> {{
       "type": "absolute",
       "period": "month",
       "value": "August 2026"
     }}
- Example:
  "July vs August"
  -> {{
       "type": "comparison",
       "period": "month",
       "values": ["July", "August"]
     }}

IMPORTANT:
- Do not calculate dates.
- Do not calculate metric values.
- Preserve the user's temporal meaning.
- Relative temporal expressions refer to the latest period available
  in the uploaded dataset.

For fields that are not applicable, use null.

For DATA_NOT_AVAILABLE:
- canonical_query must be ""
- reason must briefly explain what information is missing.
"""

    # ============================================================
    # DETERMINISTIC FAST PATH
    # ============================================================
    # If the query can be resolved completely from the uploaded
    # schema without requiring LLM interpretation, return the
    # structured plan immediately.
    #
    # This avoids unnecessary LLM latency for queries such as:
    #   total sales
    #   total profitt
    #   total quntity
    #   average profit
    #   which client has highest sales
    #   top 3 buyers by revenue
    #
    # Ambiguous queries continue to the LLM below.
    # ============================================================

    fast_question = _normalize_text(original_question).strip()

    # Never short-circuit relative temporal queries here.
    # Their actual period must be resolved later from uploaded data.
    has_relative_time = bool(
        re.search(
            r"\b(?:latest|current|most\s+recent|recent|previous|prior|last)"
            r"(?:\s+\d+)?\s+(?:available\s+)?"
            r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
            fast_question,
            flags=re.IGNORECASE,
        )
    )

    # Never short-circuit explicit period comparisons.
    has_period_comparison = bool(
        re.search(
            r"\b(?:growth|difference|change|compare|comparison)"
            r"\b.*\b(?:20\d{2}|year|years|month|months|quarter|quarters)\b",
            fast_question,
            flags=re.IGNORECASE,
        )
    )

    fast_plan = None

    if not has_relative_time and not has_period_comparison:
        # --------------------------------------------------------
        # TOP / BOTTOM N RANKING
        # --------------------------------------------------------
        top_match = re.search(
            r"\b(top|bottom)\s+(\d+)\s+(.+?)\s+by\s+(.+?)\s*$",
            fast_question,
            flags=re.IGNORECASE,
        )

        if top_match:
            direction_word = top_match.group(1).lower()
            limit = int(top_match.group(2))
            requested_entity = top_match.group(3).strip()
            requested_metric = top_match.group(4).strip()

            resolved_group = _resolve_column(
                requested_entity,
                dataset,
                schema,
                    [],
            )

            # Common semantic entity aliases.
            if not resolved_group:
                entity_aliases = {
                    "client": ("customer", "party", "party name"),
                    "clients": ("customer", "party", "party name"),
                    "buyer": ("customer", "party", "party name"),
                    "buyers": ("customer", "party", "party name"),
                    "customer": ("customer", "party", "party name"),
                    "customers": ("customer", "party", "party name"),
                    "party": ("party", "party name", "customer"),
                    "parties": ("party", "party name", "customer"),
                    "item": ("item", "product"),
                    "items": ("item", "product"),
                }

                aliases = entity_aliases.get(
                    _normalize_text(requested_entity)
                )

                if aliases:
                    for alias in aliases:
                        resolved_group = _resolve_column(
                            alias,
                            dataset,
                            schema,
                    [],
                        )
                        if resolved_group:
                            break

            resolved_metric = _resolve_universal_metric(
                requested_metric,
                dataset,
                schema,
                [],
            )

            if resolved_group and resolved_metric:
                fast_plan = {
                    "status": "OK",
                    "canonical_query": original_question,
                    "operation": "ranking",
                    "metric": requested_metric,
                    "metrics": [requested_metric],
                    "aggregate_function": "sum",
                    "group_by": resolved_group,
                    "filters": [],
                    "time": None,
                    "limit": limit,
                    "direction": (
                        "asc"
                        if direction_word == "bottom"
                        else "desc"
                    ),
                    "reason": "Deterministic semantic ranking fast path",
                }

        # --------------------------------------------------------
        # --------------------------------------------------------
        # TOP / BOTTOM / BEST / WORST N WITH TIME FILTER
        # Default metric = sales
        #
        # Examples:
        #   top 5 customers in January 2026
        #   best 5 customers in January 2026
        #   bottom 5 customers in January 2026
        #   worst 5 products in 2026
        #   highest 3 categories in Q1 2026
        #   lowest 3 categories in 2025
        # --------------------------------------------------------
        if fast_plan is None:
            ranking_time_match = re.search(
                r"\b(top|bottom|best|worst|highest|lowest|largest|smallest)"
                r"\s+(\d+)\s+"
                r"(customers?|clients?|buyers?|parties?|"
                r"products?|items?|categories?|category)"
                r"\s+(?:in|for|during)\s+(.+?)\s*$",
                fast_question,
                flags=re.IGNORECASE,
            )

            if ranking_time_match:
                ranking_word = ranking_time_match.group(1).lower()
                limit = int(ranking_time_match.group(2))
                requested_entity = ranking_time_match.group(3).strip()
                requested_period = ranking_time_match.group(4).strip()

                entity_aliases = {
                    "customer": ("customer", "party", "party name"),
                    "customers": ("customer", "party", "party name"),
                    "client": ("customer", "party", "party name"),
                    "clients": ("customer", "party", "party name"),
                    "buyer": ("customer", "party", "party name"),
                    "buyers": ("customer", "party", "party name"),
                    "party": ("party", "party name", "customer"),
                    "parties": ("party", "party name", "customer"),
                    "product": ("product", "item"),
                    "products": ("product", "item"),
                    "item": ("item", "product"),
                    "items": ("item", "product"),
                    "category": ("category",),
                    "categories": ("category",),
                }

                aliases = entity_aliases.get(
                    _normalize_text(requested_entity)
                )

                resolved_group = None

                if aliases:
                    for alias in aliases:
                        resolved_group = _resolve_column(
                            alias,
                            dataset,
                            schema,
                            [],
                        )
                        if resolved_group:
                            break

                # Default metric = sales.
                resolved_metric = _resolve_universal_metric(
                    "sales",
                    dataset,
                    schema,
                    [],
                )

                period_filters = []

                try:
                    period_filters = _extract_date_filters(
                        requested_period,
                        dataset,
                        schema,
                        [],
                    )
                except Exception:
                    period_filters = []

                if resolved_group and resolved_metric:
                    fast_plan = {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": "sales",
                        "metrics": ["sales"],
                        "aggregate_function": "sum",
                        "group_by": resolved_group,
                        "filters": period_filters,
                        "time": None,
                        "limit": limit,
                        "direction": (
                            "asc"
                            if ranking_word in (
                                "bottom",
                                "worst",
                                "lowest",
                                "smallest",
                            )
                            else "desc"
                        ),
                        "reason": (
                            "Deterministic ranking with period "
                            "filter and default sales metric"
                        ),
                    }
        # --------------------------------------------------------
        # NATURAL-LANGUAGE SINGLE RANKING WITH TIME FILTER
        # Examples:
        #   who has highest sales in January 2026
        #   who has lowest profit in 2025
        # --------------------------------------------------------
        if fast_plan is None:
            who_ranking_match = re.search(
                r"\bwho\s+(?:has|have|had)\s+"
                r"(highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
                r"(.+?)\s+(?:in|for|during)\s+(.+?)\s*$",
                fast_question,
                flags=re.IGNORECASE,
            )

            if who_ranking_match:
                direction_word = who_ranking_match.group(1).lower()
                requested_metric = who_ranking_match.group(2).strip()
                requested_period = who_ranking_match.group(3).strip()

                resolved_group = _resolve_column(
                    "customer",
                    dataset,
                    schema,
                    [],
                )

                resolved_metric = _resolve_universal_metric(
                    requested_metric,
                    dataset,
                    schema,
                    [],
                )

                period_filters = []

                try:
                    period_filters = _extract_date_filters(
                        requested_period,
                        dataset,
                        schema,
                        [],
                    )
                except Exception:
                    period_filters = []

                if resolved_group and resolved_metric:
                    fast_plan = {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": requested_metric,
                        "metrics": [requested_metric],
                        "aggregate_function": "sum",
                        "group_by": resolved_group,
                        "filters": period_filters,
                        "time": None,
                        "limit": 1,
                        "direction": (
                            "asc"
                            if direction_word in (
                                "lowest",
                                "minimum",
                                "min",
                                "smallest",
                            )
                            else "desc"
                        ),
                        "reason": (
                            "Deterministic natural-language "
                            "ranking with period filter"
                        ),
                    }

        # --------------------------------------------------------
        # SOLD THE MOST / SOLD THE LEAST
        # Examples:
        #   which product sold the most in 2026
        #   which product sold the least in January 2026
        # --------------------------------------------------------
        if fast_plan is None:
            sold_ranking_match = re.search(
                r"\b(?:which|what)\s+"
                r"(product|products|item|items|category|categories)"
                r"\s+sold\s+the\s+"
                r"(most|least)"
                r"(?:\s+(?:in|for|during)\s+(.+?))?\s*$",
                fast_question,
                flags=re.IGNORECASE,
            )

            if sold_ranking_match:
                requested_entity = sold_ranking_match.group(1).strip()
                direction_word = sold_ranking_match.group(2).lower()
                requested_period = (
                    sold_ranking_match.group(3) or ""
                ).strip()

                entity_aliases = {
                    "product": ("product", "item"),
                    "products": ("product", "item"),
                    "item": ("item", "product"),
                    "items": ("item", "product"),
                    "category": ("category",),
                    "categories": ("category",),
                }

                resolved_group = None

                aliases = entity_aliases.get(
                    _normalize_text(requested_entity)
                )

                if aliases:
                    for alias in aliases:
                        resolved_group = _resolve_column(
                            alias,
                            dataset,
                            schema,
                            [],
                        )
                        if resolved_group:
                            break

                resolved_metric = _resolve_universal_metric(
                    "sales",
                    dataset,
                    schema,
                    [],
                )

                period_filters = []

                if requested_period:
                    try:
                        period_filters = _extract_date_filters(
                            requested_period,
                            dataset,
                            schema,
                            [],
                        )
                    except Exception:
                        period_filters = []

                if resolved_group and resolved_metric:
                    fast_plan = {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": "sales",
                        "metrics": ["sales"],
                        "aggregate_function": "sum",
                        "group_by": resolved_group,
                        "filters": period_filters,
                        "time": None,
                        "limit": 1,
                        "direction": (
                            "asc"
                            if direction_word == "least"
                            else "desc"
                        ),
                        "reason": (
                            "Deterministic sold-most/sold-least "
                            "ranking"
                        ),
                    }
        # --------------------------------------------------------
        # HIGHEST / LOWEST N ENTITY BY METRIC WITH TIME FILTER
        # Examples:
        #   highest 3 customers by GST in Q1 2026
        #   lowest 5 products by profit in 2025
        #   highest 10 categories by sales in 2026
        # --------------------------------------------------------
        if fast_plan is None:
            highest_lowest_match = re.search(
                r"\b(highest|lowest|maximum|minimum|largest|smallest)"
                r"\s+(\d+)\s+"
                r"(customers?|clients?|buyers?|parties?|"
                r"products?|items?|categories?|category)"
                r"\s+by\s+(.+?)"
                r"(?:\s+(?:in|for|during)\s+(.+?))?\s*$",
                fast_question,
                flags=re.IGNORECASE,
            )

            if highest_lowest_match:
                ranking_word = highest_lowest_match.group(1).lower()
                limit = int(highest_lowest_match.group(2))
                requested_entity = highest_lowest_match.group(3).strip()
                requested_metric = highest_lowest_match.group(4).strip()
                requested_period = (
                    highest_lowest_match.group(5) or ""
                ).strip()

                entity_aliases = {
                    "customer": ("customer", "party", "party name"),
                    "customers": ("customer", "party", "party name"),
                    "client": ("customer", "party", "party name"),
                    "clients": ("customer", "party", "party name"),
                    "buyer": ("customer", "party", "party name"),
                    "buyers": ("customer", "party", "party name"),
                    "party": ("party", "party name", "customer"),
                    "parties": ("party", "party name", "customer"),
                    "product": ("product", "item"),
                    "products": ("product", "item"),
                    "item": ("item", "product"),
                    "items": ("item", "product"),
                    "category": ("category",),
                    "categories": ("category",),
                }

                resolved_group = None
                aliases = entity_aliases.get(
                    _normalize_text(requested_entity)
                )

                if aliases:
                    for alias in aliases:
                        resolved_group = _resolve_column(
                            alias,
                            dataset,
                            schema,
                            [],
                        )
                        if resolved_group:
                            break

                resolved_metric = _resolve_universal_metric(
                    requested_metric,
                    dataset,
                    schema,
                    [],
                )

                period_filters = []

                if requested_period:
                    try:
                        period_filters = _extract_date_filters(
                            requested_period,
                            dataset,
                            schema,
                            [],
                        )
                    except Exception:
                        period_filters = []

                if resolved_group and resolved_metric:
                    fast_plan = {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": requested_metric,
                        "metrics": [requested_metric],
                        "aggregate_function": "sum",
                        "group_by": resolved_group,
                        "filters": period_filters,
                        "time": None,
                        "limit": limit,
                        "direction": (
                            "asc"
                            if ranking_word in (
                                "lowest",
                                "minimum",
                                "smallest",
                            )
                            else "desc"
                        ),
                        "reason": (
                            "Deterministic highest/lowest N "
                            "ranking with metric and period"
                        ),
                    }
        # WHICH / WHAT ENTITY HAS HIGHEST / LOWEST METRIC
        # --------------------------------------------------------
        if fast_plan is None:
            ranking_match = re.search(
                r"\b(?:which|what)\s+(.+?)\s+"
                r"(?:has|have|with)\s+"
                r"(highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
                r"(.+?)\s*$",
                fast_question,
                flags=re.IGNORECASE,
            )

            if ranking_match:
                requested_entity = ranking_match.group(1).strip()
                direction_word = ranking_match.group(2).lower()
                requested_metric = ranking_match.group(3).strip()

                resolved_group = _resolve_column(
                    requested_entity,
                    dataset,
                    schema,
                    [],
                )

                if not resolved_group:
                    entity_aliases = {
                        "client": ("customer", "party", "party name"),
                        "clients": ("customer", "party", "party name"),
                        "buyer": ("customer", "party", "party name"),
                        "buyers": ("customer", "party", "party name"),
                        "customer": ("customer", "party", "party name"),
                        "customers": ("customer", "party", "party name"),
                        "party": ("party", "party name", "customer"),
                        "parties": ("party", "party name", "customer"),
                        "item": ("item", "product"),
                        "items": ("item", "product"),
                    }

                    aliases = entity_aliases.get(
                        _normalize_text(requested_entity)
                    )

                    if aliases:
                        for alias in aliases:
                            resolved_group = _resolve_column(
                                alias,
                                dataset,
                                schema,
                    [],
                            )
                            if resolved_group:
                                break

                resolved_metric = _resolve_universal_metric(
                    requested_metric,
                    dataset,
                    schema,
                    [],
                )

                if resolved_group and resolved_metric:
                    fast_plan = {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": requested_metric,
                        "metrics": [requested_metric],
                        "aggregate_function": "sum",
                        "group_by": resolved_group,
                        "filters": [],
                        "time": None,
                        "limit": 1,
                        "direction": (
                            "asc"
                            if direction_word
                            in (
                                "lowest",
                                "minimum",
                                "min",
                                "smallest",
                            )
                            else "desc"
                        ),
                        "reason": "Deterministic semantic ranking fast path",
                    }

        # --------------------------------------------------------
        # SIMPLE AGGREGATE
        # --------------------------------------------------------
        grouped_query = bool(
            re.search(
                r"\b(?:by|per|wise|each)\b",
                fast_question,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b(?:month|year|quarter)\s+wise\b",
                fast_question,
                flags=re.IGNORECASE,
            )
        )

        if (
            fast_plan is None
            and not grouped_query
            and not re.search(
                r"\b(?:highest|lowest|maximum|minimum|max|min|largest|smallest)\s+"
                r"(?:sales|revenue|turnover|profit|quantity|amount|gst|tax)\s+"
                r"(?:category|categories|product|products|customer|customers|client|clients)\b",
                fast_question,
                flags=re.IGNORECASE,
            )
            # Queries such as:
            #   "sales for Pooja"
            #   "profit for Pooja Sharma"
            #   "sales from Pooja"
            # must reach the planner/filter executor instead of
            # becoming an unfiltered aggregate.
            and not re.search(
                r"\b(?:for|from)\s+[A-Za-z][A-Za-z0-9_-]*"
                r"(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,3}\b",
                fast_question,
                flags=re.IGNORECASE,
            )

        ):
            fallback_filters = []

            # Resolve entity/categorical filters against actual persisted rows.
            try:
                filter_rows = state.get("rows") or []

                if not filter_rows:
                    dataset_id = dataset.get("id")
                    if dataset_id is not None:
                        filter_rows = load_dataset_rows(int(dataset_id))

                fallback_filters = _extract_categorical_filters(
                    fast_question,
                    dataset,
                    schema,
                    filter_rows,
                ) or []
            except Exception:
                fallback_filters = []

            aggregate_function, aggregate_column = _extract_aggregate(
                fast_question,
                dataset,
                schema,
                fallback_filters,
            )


            # Final entity-filter resolution before constructing the fast plan.
            # Always resolve free-form values against the actual uploaded rows.
            try:
                fast_filter_rows = state.get("rows") or []
                if not fast_filter_rows:
                    fast_dataset_id = dataset.get("id")
                    if fast_dataset_id is not None:
                        fast_filter_rows = load_dataset_rows(int(fast_dataset_id))

                resolved_entity_filters = _extract_categorical_filters(
                    original_question,
                    dataset,
                    schema,
                    fast_filter_rows,
                ) or []

                fallback_filters = _deduplicate_filters(
                    (fallback_filters or []) + resolved_entity_filters
                )
            except Exception as exc:
                print("[FAST FILTER RESOLUTION ERROR] =", repr(exc))

            if aggregate_function and aggregate_column:
                fast_plan = {
                    "status": "OK",
                    "canonical_query": original_question,
                    "operation": "aggregate",
                    "metric": aggregate_column,
                    "metrics": [aggregate_column],
                    "aggregate_function": aggregate_function,
                    "aggregate_column": aggregate_column,
                    "group_by": None,
                    "filters": fallback_filters,
                    "time": None,
                    "limit": None,
                    "direction": None,
                    "reason": "Deterministic aggregate fast path",
                }


        # Final deterministic entity-filter enrichment before fast-path return.
        # Resolve free-form values against the actual uploaded dataset.
        try:
            final_filter_rows = state.get("rows") or []
            if not final_filter_rows:
                final_dataset_id = dataset.get("id")
                if final_dataset_id is not None:
                    final_filter_rows = load_dataset_rows(int(final_dataset_id))

            final_entity_filters = _extract_categorical_filters(
                original_question,
                dataset,
                schema,
                final_filter_rows,
            ) or []

            if fast_plan is not None and final_entity_filters:
                fast_plan["filters"] = _deduplicate_filters(
                    (fast_plan.get("filters") or []) + final_entity_filters
                )
        
        except Exception as exc:
            print("[FAST FILTER ENRICHMENT ERROR] =", repr(exc))
    if fast_plan is not None:
        return {
            **state,
            "original_question": original_question,
            "question": original_question,
            "query_plan": fast_plan,
            "error": None,
        }

    # ============================================================
    # EXISTING LLM PATH
    # ============================================================
    try:
        response = _dynamic_query_llm.invoke(prompt)

        raw_content = getattr(
            response,
            "content",
            "",
        )

        if isinstance(raw_content, list):
            raw_content = "".join(
                (
                    part.get("text", "")
                    if isinstance(part, dict)
                    else str(part)
                )
                for part in raw_content
            )

        raw_content = str(raw_content).strip()

        # ----------------------------------------------------
        # Remove accidental markdown JSON fences.
        # ----------------------------------------------------

        if raw_content.startswith("```"):
            raw_content = re.sub(
                r"^```(?:json)?\s*",
                "",
                raw_content,
                flags=re.IGNORECASE,
            )

            raw_content = re.sub(
                r"\s*```$",
                "",
                raw_content,
            ).strip()

        import json

        plan = json.loads(raw_content)

    except Exception as exc:
        # ----------------------------------------------------
        # Deterministic semantic fallback.
        #
        # If the LLM planner is unavailable (for example,
        # rate-limited), try the existing universal metric
        # resolver before falling back to the legacy parser.
        #
        # The resolver validates every semantic mapping against
        # the uploaded schema, so this path must never invent a
        # column or substitute an unrelated numeric field.
        # ----------------------------------------------------

        # ----------------------------------------------------
        # GENERIC DETERMINISTIC SEMANTIC FALLBACK
        #
        # Decompose common natural-language ranking queries into:
        #   entity/group + metric + direction + limit
        #
        # Example:
        #   "which client has highest sales?"
        #       -> group_by = client
        #       -> metric   = sales
        #       -> direction = desc
        #       -> limit = 1
        #
        # The actual columns are resolved against the uploaded
        # schema. The executor performs the calculation.
        # ----------------------------------------------------

        fallback_question = _normalize_text(
            original_question
        ).strip()

        fallback_rows = state.get("rows") or []

        fallback_question = _normalize_text(original_question).strip()
        fallback_rows = state.get("rows") or []
        fallback_filters = []

        # Generic temporal aggregate fallback.
        temporal_aggregate_match = re.search(
            r"\b(?:latest|current|most recent|recent|previous|prior|last)\s+"
            r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
            fallback_question,
            flags=re.IGNORECASE,
        )

        if temporal_aggregate_match:
            temporal_schema = state.get("schema") or []

            # Resolve the metric independently from temporal words.
            # Example:
            #   "latest month profit" -> "profit"
            #   "previous year sales" -> "sales"
            #   "last quarter GST" -> "GST"
            metric_question = re.sub(
                r"\b(?:latest|current|most recent|previous|prior|last)\s+"
                r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
                " ",
                fallback_question,
                flags=re.IGNORECASE,
            )
            metric_question = re.sub(
                r"\s+",
                " ",
                metric_question,
            ).strip()

            temporal_metric = None

            # Resolve the cleaned metric semantically.
            # Example: "latest month profit" -> "profit" -> Profit
            try:
                temporal_metric = _resolve_universal_metric(
                    metric_question,
                    dataset,
                    temporal_schema,
                    fallback_rows,
                )
            except Exception:
                temporal_metric = None

            # Generic schema resolver fallback.
            # This resolves the requested metric against the uploaded
            # dataset instead of hardcoding a particular column.
            if not temporal_metric:
                try:
                    resolved_column = _resolve_column(
                        metric_question,
                        dataset,
                        temporal_schema,
                        fallback_rows,
                    )
                except Exception:
                    resolved_column = None

                if resolved_column:
                    temporal_metric = {
                        "column": resolved_column,
                        "label": str(resolved_column),
                        "requested": metric_question,
                        "function": "sum",
                    }

            # The planner runs before load_data, so state["filters"]
            # may still be empty. Extract temporal filters directly
            # from the original question here.
            temporal_filters = state.get("filters") or []

            if not temporal_filters:
                try:
                    temporal_filters = _extract_date_filters(
                        _normalize_query(original_question),
                        dataset,
                        temporal_schema,
                        fallback_rows,
                    )
                except Exception:
                    temporal_filters = []

            if temporal_metric:
                metric_column = temporal_metric.get("column")
                metric_label = (
                    temporal_metric.get("label")
                    or temporal_metric.get("requested")
                    or metric_column
                )

                return {
                    **state,
                    "query_plan": {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "aggregate",
                        "metric": metric_label,
                        "metrics": [metric_label],
                        "aggregate_function": "sum",
                        "aggregate_column": metric_column,
                        "group_by": None,
                        "filters": temporal_filters,
                        "time": None,
                        "limit": None,
                        "direction": None,
                        "reason": "Deterministic semantic temporal aggregate fallback",
                    },
                    "filters": temporal_filters,
                    "question": _normalize_query(original_question),
                }

    # Generic Top-N / Bottom-N deterministic fallback.
        top_n_match = re.search(
            r"\b(top|bottom)\s+(\d+)\s+(.+?)\s+by\s+(.+?)\s*$",
            fallback_question,
            flags=re.IGNORECASE,
        )

        if top_n_match:
            ranking_direction_text = top_n_match.group(1).lower()
            ranking_limit = max(1, int(top_n_match.group(2)))
            requested_group = top_n_match.group(3).strip()
            metric_text = top_n_match.group(4).strip()

            entity_aliases = {
                "client": ("customer", "party", "party name"),
                "clients": ("customer", "party", "party name"),
                "buyer": ("customer", "party", "party name"),
                "buyers": ("customer", "party", "party name"),
                "customer": ("customer", "party", "party name"),
                "customers": ("customer", "party", "party name"),
                "party": ("party", "party name", "customer"),
                "parties": ("party", "party name", "customer"),
                "item": ("item", "product"),
                "items": ("item", "product"),
            }

            group_by = _resolve_column(
                requested_group,
                dataset,
                schema,
                fallback_rows,
            )

            if not group_by:
                for candidate in entity_aliases.get(
                    requested_group.lower(),
                    (),
                ):
                    group_by = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                        fallback_rows,
                    )
                    if group_by:
                        break

            resolved_metric = None
            try:
                resolved_metric = _resolve_universal_metric(
                    metric_text,
                    dataset,
                    schema,
                    fallback_rows,
                )
            except Exception:
                resolved_metric = None

            if group_by and resolved_metric:
                direction = (
                    "asc"
                    if ranking_direction_text == "bottom"
                    else "desc"
                )

                return {
                    **state,
                    "original_question": original_question,
                    "query_plan": {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": metric_text,
                        "metrics": [metric_text],
                        "aggregate_function": resolved_metric.get(
                            "function",
                            "sum",
                        ),
                        "group_by": group_by,
                        "filters": [],
                        "time": None,
                        "limit": ranking_limit,
                        "direction": direction,
                        "reason": (
                            "Deterministic semantic Top-N fallback"
                        ),
                    },
                    "question": _normalize_query(
                        original_question
                    ),
                }

        ranking_match = re.search(
            r"\b(?:which|what)\s+"
            r"(.+?)\s+"
            r"(?:has|have|with)\s+"
            r"(highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
            r"(.+?)\s*$",
            fallback_question,
            flags=re.IGNORECASE,
        )

        if ranking_match:
            entity_text = ranking_match.group(1).strip()
            ranking_word = ranking_match.group(2).strip().lower()
            metric_text = ranking_match.group(3).strip()

            # Remove trailing question punctuation.
            metric_text = re.sub(
                r"[?!.]+$",
                "",
                metric_text,
            ).strip()

            group_by = _resolve_column(
                entity_text,
                dataset,
                schema,
                fallback_rows,
            )

            # If the complete entity phrase does not resolve,
            # try the final semantic token.
            if not group_by:
                entity_tokens = entity_text.split()
                if entity_tokens:
                    group_by = _resolve_column(
                        entity_tokens[-1],
                        dataset,
                        schema,
                        fallback_rows,
                    )

            resolved_metric = None
            if metric_text:
                try:
                    resolved_metric = _resolve_universal_metric(
                        metric_text,
                        dataset,
                        schema,
                        fallback_rows,
                    )
                except Exception:
                    resolved_metric = None

            if group_by and resolved_metric:
                direction = (
                    "asc"
                    if ranking_word in {
                        "lowest",
                        "minimum",
                        "min",
                        "smallest",
                    }
                    else "desc"
                )

                # Generic Top-N / Bottom-N ranking.
                # Examples:
                #   top 3 clients by sales
                #   top 5 products by profit
                #   bottom 3 customers by quantity
                top_n_match = re.search(
                    r"\b(top|bottom)\s+(\d+)\b",
                    _normalize_query(original_question),
                    flags=re.IGNORECASE,
                )

                if top_n_match:
                    ranking_direction = (
                        "asc"
                        if top_n_match.group(1).lower() == "bottom"
                        else "desc"
                    )
                    ranking_limit = max(
                        1,
                        int(top_n_match.group(2)),
                    )
                else:
                    ranking_direction = direction
                    ranking_limit = 1

                return {
                    **state,
                    "original_question": original_question,
                    "query_plan": {
                        "status": "OK",
                        "canonical_query": original_question,
                        "operation": "ranking",
                        "metric": metric_text,
                        "metrics": [metric_text],
                        "aggregate_function": resolved_metric.get(
                            "function",
                            "sum",
                        ),
                        "group_by": group_by,
                        "filters": [],
                        "time": None,
                        "limit": ranking_limit,
                        "direction": ranking_direction,
                        "reason": (
                            "Deterministic semantic ranking fallback"
                        ),
                    },
                    "question": _normalize_query(
                        original_question
                    ),
                }

        # ----------------------------------------------------
        # Generic semantic metric fallback.
        # ----------------------------------------------------

        # The normal pipeline may not keep raw rows in state.
        # Load them only when the deterministic fallback needs
        # actual data values for entity/value resolution.
        fallback_rows = state.get("rows") or []

        if not fallback_rows:
            try:
                dataset_id = dataset.get("id")
                if dataset_id is not None:
                    fallback_rows = load_dataset_rows(int(dataset_id))
            except Exception:
                fallback_rows = []

        fallback_metric = _normalize_text(
            original_question
        ).strip()

        # ----------------------------------------------------
        # Separate the requested business metric from a
        # free-form entity/value filter.
        #
        # Examples:
        #   "Show total sales for Pooja"
        #       -> metric question: "Show total sales"
        #
        #   "profit for Rahul"
        #       -> metric question: "profit"
        #
        #   "Pooja ki sales"
        #       -> metric question: "sales"
        #
        # Entity values are resolved independently from the
        # actual uploaded rows by fallback_categorical_filters.
        # ----------------------------------------------------
        metric_fallback_question = fallback_metric

        metric_fallback_question = re.sub(
            r"\b(?:for|from|of)\s+"
            r"[A-Za-z][A-Za-z0-9_-]*"
            r"(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,4}\b",
            " ",
            metric_fallback_question,
            flags=re.IGNORECASE,
        )

        metric_fallback_question = re.sub(
            r"\b\S+\s+(?:ki|ka|ke)\s+"
            r"(?=(?:sales|revenue|turnover|profit|quantity|qty|"
            r"amount|gst|tax|billing|business|invoice|invoices)\b)",
            " ",
            metric_fallback_question,
            flags=re.IGNORECASE,
        )

        metric_fallback_question = re.sub(
            r"\s+",
            " ",
            metric_fallback_question,
        ).strip()

        resolved_fallback = None

        if metric_fallback_question:
            try:
                resolved_fallback = _resolve_universal_metric(
                    metric_fallback_question,
                    dataset,
                    schema,
                    fallback_rows,
                )
            except Exception:
                resolved_fallback = None

        # Existing deterministic aggregate resolver is the final
        # metric fallback. It resolves aliases such as:
        #   total sales -> GrossAmount
        #   profit      -> Profit
        #   quantity    -> Qty
        # without allowing the entity value to affect the metric.
        if not resolved_fallback:
            try:
                fallback_function, fallback_column = _extract_aggregate(
                    metric_fallback_question,
                    dataset,
                    schema,
                    fallback_rows,
                )

                if fallback_function and fallback_column:
                    resolved_fallback = {
                        "function": fallback_function,
                        "column": fallback_column,
                        "label": fallback_column,
                        "requested": metric_fallback_question,
                    }
            except Exception:
                resolved_fallback = None

        # Resolve free-form entity/value references against the
        # actual uploaded rows. This keeps partial names such as
        # "Pooja" data-driven instead of hardcoding names.
        fallback_categorical_filters = []
        fallback_numeric_filters = []

        if fallback_rows:
            try:
                fallback_categorical_filters = _extract_categorical_filters(
                    original_question,
                    dataset,
                    schema,
                    fallback_rows,
                )
            except Exception:
                fallback_categorical_filters = []

            try:
                fallback_numeric_filters = _extract_numeric_filters(
                    original_question,
                    dataset,
                    schema,
                    fallback_rows,
                )
            except Exception:
                fallback_numeric_filters = []

        fallback_filters = _deduplicate_filters(
            fallback_numeric_filters
            + fallback_categorical_filters
        )

        if resolved_fallback:
            return {
                **state,
                "original_question": original_question,
                "filters": fallback_filters,
                "query_plan": {
                    "status": "OK",
                    "canonical_query": original_question,
                    "operation": "aggregate",
                    "metric": (
                        resolved_fallback.get("label")
                        or resolved_fallback.get("column")
                        or fallback_metric
                    ),
                    "metrics": [
                        (
                            resolved_fallback.get("label")
                            or resolved_fallback.get("column")
                            or fallback_metric
                        )
                    ],
                    "aggregate_column": resolved_fallback.get("column"),
                    "aggregate_function": resolved_fallback.get(
                        "function",
                        "sum",
                    ),
                    "group_by": None,
                    "filters": fallback_filters,
                    "time": None,
                    "limit": None,
                    "direction": None,
                    "reason": (
                        "Deterministic semantic fallback: "
                        + str(exc)
                    ),
                },
                "question": _normalize_query(
                    original_question
                ),
            }

        # No safe semantic metric was found.
        # Preserve the original deterministic engine.
        return {
            **state,
            "original_question": original_question,
            "query_plan": {
                "status": "FALLBACK",
                "reason": "LLM planner unavailable; deterministic fallback",
            },
            "question": _normalize_query(
                original_question
            ),
        }

    if not isinstance(plan, dict):
        return {
            **state,
            "original_question": original_question,
            "query_plan": {
                "status": "FALLBACK",
                "reason": "Planner returned invalid JSON object",
            },
            "question": _normalize_query(
                original_question
            ),
        }

    status = str(
        plan.get("status") or ""
    ).strip().upper()
    # --------------------------------------------------------
    # Normalize structured planner fields.
    #
    # These fields are interpretation only. The deterministic
    # executor remains responsible for actual calculations.
    # --------------------------------------------------------

    if not isinstance(plan.get("metrics"), list):
        metric_value = plan.get("metric")

        if isinstance(metric_value, str):
            plan["metrics"] = [
                item.strip()
                for item in re.split(r"\s*,\s*", metric_value)
                if item.strip()
            ]
        elif metric_value:
            plan["metrics"] = [str(metric_value)]
        else:
            plan["metrics"] = []

    if not isinstance(plan.get("filters"), list):
        plan["filters"] = []

    # --------------------------------------------------------
    # DETERMINISTIC FILTER ENRICHMENT
    # Resolve free-form values against actual uploaded rows.
    # The LLM interprets; Python validates against real data.
    # --------------------------------------------------------

    filter_rows = state.get("rows") or []

    if not filter_rows:
        try:
            dataset_id = dataset.get("id")
            if dataset_id is not None:
                filter_rows = load_dataset_rows(int(dataset_id))
        except Exception:
            filter_rows = []

    if filter_rows:
        try:
            deterministic_categorical_filters = (
                _extract_categorical_filters(
                    original_question,
                    dataset,
                    schema,
                    filter_rows,
                )
            )
        except Exception:
            deterministic_categorical_filters = []

        try:
            deterministic_numeric_filters = (
                _extract_numeric_filters(
                    original_question,
                    dataset,
                    schema,
                    filter_rows,
                )
            )
        except Exception:
            deterministic_numeric_filters = []

        plan["filters"] = _reconcile_partial_entity_filters(
            _deduplicate_filters(
                (plan.get("filters") or [])
                + deterministic_numeric_filters
                + deterministic_categorical_filters
            )
        )


    if "time" not in plan:
        plan["time"] = None

    # Normalize the requested aggregate function.
    aggregate_function = plan.get("aggregate_function")

    if aggregate_function is not None:
        aggregate_function = str(
            aggregate_function
        ).strip().lower()

        aggregate_aliases = {
            "avg": "average",
            "mean": "average",
            "maximum": "max",
            "highest": "max",
            "largest": "max",
            "minimum": "min",
            "lowest": "min",
            "smallest": "min",
            "total": "sum",
        }

        aggregate_function = aggregate_aliases.get(
            aggregate_function,
            aggregate_function,
        )

        if aggregate_function not in {
            "sum",
            "average",
            "max",
            "min",
            "median",
            "count",
        }:
            aggregate_function = None

    plan["aggregate_function"] = aggregate_function


    if plan.get("limit") is not None:
        try:
            plan["limit"] = int(plan["limit"])
        except (TypeError, ValueError):
            plan["limit"] = None

    if plan.get("direction") is not None:
        direction = str(
            plan.get("direction")
        ).strip().lower()

        if direction not in {"asc", "desc"}:
            plan["direction"] = None
        else:
            plan["direction"] = direction
    # --------------------------------------------------------
    # DATA NOT AVAILABLE
    # --------------------------------------------------------

    if status == "DATA_NOT_AVAILABLE":
        # ----------------------------------------------------
        # Deterministic semantic recovery.
        #
        # Before accepting DATA_NOT_AVAILABLE from the planner,
        # try to resolve grouped ranking queries safely against
        # the real uploaded schema.
        # ----------------------------------------------------

        fallback_question = _normalize_text(
            original_question
        ).strip()

        fallback_rows = state.get("rows") or []
        recovered_plan = None

        # Deterministic temporal aggregate fallback.
        # Reuse the already extracted temporal filters and resolve
        # the requested metric from the dataset schema.
        temporal_aggregate_match = re.search(
            r"\b(?:latest|current|most recent|previous|prior|last)\s+"
            r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
            fallback_question,
            flags=re.IGNORECASE,
        )

        if temporal_aggregate_match:
            temporal_metric = _resolve_universal_metric(fallback_question, dataset, state.get("schema") or [], fallback_rows)
            temporal_filters = state.get("filters") or []

            if temporal_metric and temporal_filters:
                metric_column = temporal_metric.get("column")
                metric_label = (
                    temporal_metric.get("label")
                    or temporal_metric.get("requested")
                    or metric_column
                )

                recovered_plan = {
                    "status": "OK",
                    "canonical_query": original_question,
                    "operation": "aggregate",
                    "metric": metric_label,
                    "metrics": [metric_label],
                    "aggregate_function": "sum",
                    "aggregate_column": metric_column,
                    "group_by": None,
                    "filters": temporal_filters,
                    "time": None,
                    "limit": None,
                    "direction": None,
                    "reason": "Deterministic semantic temporal aggregate fallback",
                }

        ranking_match = re.search(
            r"\b(?:which|what)\s+"
            r"(.+?)\s+"
            r"(?:has|have|with)\s+"
            r"(highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
            r"(.+?)\s*$",
            fallback_question,
            flags=re.IGNORECASE,
        )

        if ranking_match:
            entity_text = ranking_match.group(1).strip()
            ranking_word = ranking_match.group(2).strip().lower()

            metric_text = re.sub(
                r"[?!.]+$",
                "",
                ranking_match.group(3).strip(),
            ).strip()

            # Resolve the grouping/entity column using the
            # existing schema-aware resolver.
            group_by = _resolve_column(
                entity_text,
                dataset,
                schema,
                fallback_rows,
            )

            # Try common semantic aliases only through the
            # resolver. No source column is hardcoded here.
            if not group_by:
                entity_aliases = {
                    "client": (
                        "customer",
                        "party name",
                        "party",
                    ),
                    "customer": (
                        "customer",
                        "party name",
                        "party",
                    ),
                    "buyer": (
                        "customer",
                        "party name",
                        "party",
                    ),
                    "party": (
                        "party",
                        "party name",
                        "customer",
                    ),
                    "product": (
                        "product",
                        "item",
                    ),
                    "item": (
                        "item",
                        "product",
                    ),
                    "category": (
                        "category",
                    ),
                    "supplier": (
                        "supplier",
                        "vendor",
                    ),
                    "vendor": (
                        "vendor",
                        "supplier",
                    ),
                }

                entity_norm = _normalize_text(
                    entity_text
                )

                for alias, candidates in entity_aliases.items():
                    if not re.search(
                        rf"\b{re.escape(alias)}s?\b",
                        entity_norm,
                        flags=re.IGNORECASE,
                    ):
                        continue

                    for candidate in candidates:
                        group_by = _resolve_column(
                            candidate,
                            dataset,
                            schema,
                            fallback_rows,
                        )

                        if group_by:
                            break

                    if group_by:
                        break

            # Resolve metric independently against the schema.
            resolved_metric = None

            if metric_text:
                try:
                    resolved_metric = (
                        _resolve_universal_metric(
                            metric_text,
                            dataset,
                            schema,
                            fallback_rows,
                        )
                    )
                except Exception:
                    resolved_metric = None

            if group_by and resolved_metric:
                direction = (
                    "asc"
                    if ranking_word in {
                        "lowest",
                        "minimum",
                        "min",
                        "smallest",
                    }
                    else "desc"
                )

                recovered_plan = {
                    **plan,
                    "status": "OK",
                    "canonical_query": original_question,
                    "operation": "ranking",
                    "metric": metric_text,
                    "metrics": [metric_text],
                    "aggregate_function": resolved_metric.get(
                        "function",
                        "sum",
                    ),
                    "group_by": group_by,
                    "filters": [],
                    "time": None,
                    "limit": 1,
                    "direction": direction,
                    "reason": (
                        "Recovered by deterministic semantic "
                        "ranking resolver."
                    ),
                }

        if recovered_plan is not None:
            return {
                **state,
                "original_question": original_question,
                "query_plan": recovered_plan,
                "question": original_question,
                "error": None,
            }

        reason = str(
            plan.get("reason")
            or "Requested information is not available in the uploaded data."
        )

        return {
            **state,
            "original_question": original_question,
            "query_plan": plan,
            "question": original_question,
            "error": (
                "Information is not available in the uploaded data."
            ),
        }

    canonical_query = str(
        plan.get("canonical_query")
        or ""
    ).strip()

    if not canonical_query:
        return {
            **state,
            "original_question": original_question,
            "query_plan": {
                **plan,
                "status": "FALLBACK",
            },
            "question": _normalize_query(
                original_question
            ),
        }

    # --------------------------------------------------------
    # Schema safety validation.
    #
    # We do not blindly trust the LLM.
    # Any explicitly returned metric/group_by must exist in the
    # uploaded schema, unless it is a natural business alias.
    # --------------------------------------------------------

    actual_columns = {
        _normalize_column(
            item.get("source_column")
        )
        for item in schema
        if isinstance(item, dict)
        and item.get("source_column")
    }

    def _schema_column_exists(
        value: Any,
    ) -> bool:
        if not value:
            return True

        normalized = _normalize_column(value)

        if not normalized:
            return True

        if normalized in actual_columns:
            return True

        metric_prefixes = (
            "total ",
            "sum ",
            "average ",
            "avg ",
            "mean ",
            "maximum ",
            "max ",
            "minimum ",
            "min ",
            "count ",
        )

        for prefix in metric_prefixes:
            if normalized.startswith(prefix):
                base_column = normalized[len(prefix):].strip()

                if base_column in actual_columns:
                    return True

                semantic_aliases = {
                    "sales", "sale", "revenue", "turnover", "billing",
                    "business value", "business amount", "business done",
                    "total business", "sales amount", "sales value",
                    "selling", "selling amount", "selling value",
                    "earning", "earnings", "gain", "gains",
                    "profit amount", "profit value", "kamai", "kamaai",
                    "fayda", "faayda",
                    "profit", "quantity", "qty", "gst", "total gst",
                    "cgst", "sgst", "igst", "discount", "discount amount",
                    "taxable amount", "taxable value", "invoice value",
                    "invoice amount", "invoice total", "customer",
                    "customers", "party", "product", "products", "item",
                    "items", "category", "categories", "supplier",
                    "employee", "date", "month", "year", "quarter",
                }

                if base_column in semantic_aliases:
                    return True

        semantic_terms = {
            "sales",
            "sale",
            "revenue",
            "turnover",
            "billing",
            "business value",
            "business amount",
            "business done",
            "total business",
            "sales amount",
            "sales value",
            "selling",
            "selling amount",
            "selling value",
            "earning",
            "earnings",
            "gain",
            "gains",
            "profit amount",
            "profit value",
            "kamai",
            "kamaai",
            "fayda",
            "faayda",
            "profit",
            "quantity",
            "qty",
            "gst",
            "total gst",
            "cgst",
            "sgst",
            "igst",
            "discount",
            "discount amount",
            "taxable amount",
            "taxable value",
            "invoice value",
            "invoice amount",
            "invoice total",
            "customer",
            "customers",
            "party",
            "product",
            "products",
            "item",
            "items",
            "category",
            "categories",
            "supplier",
            "employee",
            "date",
            "month",
            "year",
            "quarter",
        }

        semantic_terms.add("unit price")
        semantic_terms.add("price")
        semantic_terms.add("cost")
        semantic_terms.add("gross amount")
        semantic_terms.add("taxable")
        semantic_terms.add("units")
        semantic_terms.add("invoice no")
        semantic_terms.add("invoice number")

        return normalized in semantic_terms

    metric = plan.get("metric")
    group_by = plan.get("group_by")

    # ------------------------------------------------------------
    # Validate multiple metrics independently.
    #
    # The planner may return:
    #     "sales, profit"
    #
    # These are two valid business concepts, not one column name.
    # ------------------------------------------------------------
    metric_values = []

    if isinstance(metric, str):
        metric_values = [
            item.strip()
            for item in re.split(r"\s*,\s*", metric)
            if item.strip()
        ]
    elif isinstance(metric, list):
        metric_values = [
            str(item).strip()
            for item in metric
            if str(item).strip()
        ]
    elif metric:
        metric_values = [str(metric).strip()]

    unavailable_metrics = [
        item
        for item in metric_values
        if not _schema_column_exists(item)
    ]

    if unavailable_metrics:
        return {
            **state,
            "original_question": original_question,
            "query_plan": {
                **plan,
                "status": "DATA_NOT_AVAILABLE",
                "unavailable_metrics": unavailable_metrics,
            },
            "question": original_question,
            "error": (
                "Information is not available in the uploaded data."
            ),
        }

    if not _schema_column_exists(group_by):
        return {
            **state,
            "original_question": original_question,
            "query_plan": {
                **plan,
                "status": "DATA_NOT_AVAILABLE",
            },
            "question": original_question,
            "error": (
                "Information is not available in the uploaded data."
            ),
        }

    # --------------------------------------------------------
    # Canonical query becomes the input for the existing
    # deterministic query engine.
    # --------------------------------------------------------

    return {
        **state,
        "original_question": original_question,
        "query_plan": plan,
        "question": canonical_query,
        "error": None,
    }
def _normalize_planner_plan(
    state: DynamicAgentState,
) -> DynamicAgentState:
    """
    Normalize the structured query plan produced by the universal
    planner.

    This function does NOT calculate anything.

    It only converts planner output into a predictable structure
    that the existing deterministic query engine can safely use.
    """

    plan = state.get("query_plan")

    if not isinstance(plan, dict):
        return state

    if str(plan.get("status", "")).upper() != "OK":
        return state

    normalized_plan = dict(plan)

    # --------------------------------------------------------
    # Normalize metrics
    # --------------------------------------------------------

    metrics = normalized_plan.get("metrics")

    if not isinstance(metrics, list):
        metric = normalized_plan.get("metric")

        if isinstance(metric, str):
            metrics = [
                item.strip()
                for item in re.split(
                    r"\s*,\s*",
                    metric,
                )
                if item.strip()
            ]
        elif metric:
            metrics = [str(metric).strip()]
        else:
            metrics = []

    normalized_plan["metrics"] = metrics

    # --------------------------------------------------------
    # Normalize operation
    # --------------------------------------------------------

    operation = str(
        normalized_plan.get("operation") or ""
    ).strip().lower()

    normalized_plan["operation"] = operation or None

    # --------------------------------------------------------
    # Normalize limit
    # --------------------------------------------------------

    limit = normalized_plan.get("limit")

    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None

    normalized_plan["limit"] = limit

    # --------------------------------------------------------
    # Normalize direction
    # --------------------------------------------------------

    direction = normalized_plan.get("direction")

    if direction is not None:
        direction = str(direction).strip().lower()

        if direction not in {
            "asc",
            "desc",
        }:
            direction = None

    normalized_plan["direction"] = direction

    # --------------------------------------------------------
    # Normalize filters
    # --------------------------------------------------------

    filters = normalized_plan.get("filters")

    if not isinstance(filters, list):
        filters = []

    normalized_plan["filters"] = filters

    # --------------------------------------------------------
    # Preserve temporal interpretation
    # --------------------------------------------------------

    if "time" not in normalized_plan:
        normalized_plan["time"] = None

    # --------------------------------------------------------
    # Store normalized plan
    # --------------------------------------------------------

    return {
        **state,
        "query_plan": normalized_plan,
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
    
    # --------------------------------------------------------
    # EXPLICIT PERIOD COMPARISON DETECTION
    #
    # Do not reject a detailed dataset during the normal
    # single-period date filter stage when the question asks
    # for a comparison such as:
    #
    #   from January 2024 to July 2025
    #
    # The dedicated period-comparison eligibility logic below
    # will check both requested periods.
    # --------------------------------------------------------

    explicit_period_comparison = bool(
        re.search(
            r"\bfrom\b.*?"
            r"\b(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december|\d{4})\b"
            r".*?"
            r"\bto\b.*?"
            r"\b(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december|\d{4})\b",
            _normalize_text(question),
            flags=re.IGNORECASE,
        )
        or re.search(
            r"\b(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december)\b.*?"
            r"\b(?:vs|versus|compared\s+with|compared\s+to|against)\b.*?"
            r"\b(?:january|february|march|april|may|june|"
            r"july|august|september|october|november|december)\b",
            _normalize_text(question),
            flags=re.IGNORECASE,
        )
    )
    # --------------------------------------------------------
    # Temporal ranking query
    #
    # Queries such as:
    #   Which month had highest sales?
    #   Which year had highest sales?
    #   Which quarter had highest sales?
    #
    # should prefer detailed transaction datasets over tiny
    # manual/test/summary datasets.
    # --------------------------------------------------------

    temporal_ranking_query = bool(
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|"
            r"totalgst|total\s+gst|cgst|sgst|igst|"
            r"quantity|qty|discount|taxable|taxable\s+amount)\b",
            question,
            re.IGNORECASE,
        )
    )


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
            
            
        # Prefer detailed transaction data for temporal
        # ranking queries. This prevents small/manual/test
        # datasets from winning merely because their semantic
        # score is slightly higher.
        if (
            temporal_ranking_query
            and _is_detailed_transaction_dataset(
                dataset,
                schema,
            )
        ):
            score += 1000

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

        candidate_rows = load_dataset_rows(dataset_id)

        date_filters = _extract_date_filters(
            question,
            dataset,
            schema,
            candidate_rows,
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

                if not period_exists and not explicit_period_comparison:
                    continue
                
                
                    if row_matches:
                        period_exists = True
                        break

                date_eligibility_cache[dataset_id] = (
                    period_exists
                )

                if not period_exists and not explicit_period_comparison :
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
            r"\bby\s+(.+?)(?=\s+(?:where|with|having|for|from|and|or)\b|$)",
            _normalize_text(question),
        )

        if group_match:
            requested_group = group_match.group(1).strip()

            # Resolve grouping column from schema/metadata first.
            # Full dataset rows are loaded only as a fallback when
            # schema-based resolution cannot identify the column.
            candidate_rows = []

            grouping_column = _resolve_column(
                requested_group,
                dataset,
                schema,
                [],
            )

            if not grouping_column:
                try:
                    candidate_rows = load_dataset_rows(
                        dataset_id
                    )
                except Exception:
                    candidate_rows = []

                grouping_column = _resolve_column(
                    requested_group,
                    dataset,
                    schema,
                    candidate_rows,
                )

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

        invoice_count_query = bool(
            re.search(
                r"\b(?:invoice\s+count|invoice\s+counts|"
                r"count\s+(?:of\s+)?invoices?|"
                r"number\s+of\s+invoices?|"
                r"how\s+many\s+invoices?)\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
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
        # DETAILED TEMPORAL DATASET PREFERENCE
        #
        # For year-wise / quarter-wise queries, prefer a large
        # detailed transaction dataset containing an actual date
        # column over tiny/manual datasets.
        # --------------------------------------------------------

        asks_for_year_or_quarter = bool(
            re.search(
                r"\b(?:year|years|yearly|annual|year\s+wise|"
                r"year-wise|quarter|quarters|quarterly|"
                r"quarter\s+wise|quarter-wise)\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
        )

        if asks_for_year_or_quarter:
            candidate_columns = [
                _normalize_text(
                    schema_item.get("source_column", "")
                )
                for schema_item in schema
            ]

            candidate_columns = [
                column
                for column in candidate_columns
                if column
            ]

            has_actual_date_column = any(
                column in {
                    "date",
                    "invoice date",
                    "invoicedate",
                    "transaction date",
                    "transactiondate",
                    "bill date",
                    "billdate",
                    "billing date",
                    "billingdate",
                }
                or column.endswith(" date")
                for column in candidate_columns
            )

            try:
                temporal_row_count = int(
                    dataset.get("row_count", 0) or 0
                )
            except (TypeError, ValueError):
                temporal_row_count = 0

            if (
                dataset.get("data_type")
                in {
                    "sales",
                    "purchase",
                    "expense",
                    "payment",
                }
                and has_actual_date_column
                and temporal_row_count >= 100
                and _is_detailed_transaction_dataset(
                    dataset,
                    schema,
                )
            ):
                score += 600

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

            # ------------------------------------------------
            # Determine which metrics the USER actually asked
            # for. The summary dataset must contain all of
            # those metrics before receiving the large bonus.
            # ------------------------------------------------

            requested_summary_metrics = set()

            if re.search(
                r"\b(?:invoice\s+count|invoice\s+counts|"
                r"number\s+of\s+invoices|count\s+of\s+invoices|"
                r"count\s+invoices|invoices)\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "invoices"
                )

            if re.search(
                r"\b(?:sales?|revenue|billing|turnover)\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "invoice value"
                )

            if re.search(
                r"\b(?:taxable|taxable\s+amount|"
                r"taxable\s+value|taxableamount)\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "taxable value"
                )

            if re.search(
                r"\b(?:gst|total\s+gst|totalgst)\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "gst"
                )

            if re.search(
                r"\bprofit\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "profit"
                )

            if re.search(
                r"\bdiscount\b",
                normalized_question,
                flags=re.IGNORECASE,
            ):
                requested_summary_metrics.add(
                    "discount"
                )

            # ------------------------------------------------
            # Check whether every requested metric exists in
            # this dataset.
            #
            # Examples:
            #
            #   sales + profit
            #       -> Invoice Value + Profit
            #
            #   invoice count + discount
            #       -> Invoices + Discount
            #
            # Dataset 28 has Invoices but NO Discount,
            # therefore it must NOT receive the +1000 bonus.
            # ------------------------------------------------

            summary_metric_aliases = {
                "invoices": {
                    "invoices",
                    "invoice count",
                    "invoice counts",
                },
                "invoice value": {
                    "invoice value",
                    "invoice total",
                    "total amount",
                    "sales amount",
                    "sale amount",
                    "revenue",
                },
                "taxable value": {
                    "taxable value",
                    "taxable amount",
                    "taxable",
                },
                "gst": {
                    "gst",
                    "total gst",
                },
                "profit": {
                    "profit",
                },
                "discount": {
                    "discount",
                    "discount amount",
                    "discount amt",
                    "discountamount",
                },
            }

            def _summary_metric_available(
                metric_name,
            ):
                aliases = summary_metric_aliases.get(
                    metric_name,
                    {metric_name},
                )

                for column in candidate_columns:
                    for alias in aliases:
                        if (
                            column == alias
                            or alias in column
                        ):
                            return True

                return False

            requested_metrics_available = all(
                _summary_metric_available(metric)
                for metric in requested_summary_metrics
            )

            # If no specific metric was detected, retain the
            # original trend-summary behavior.
            if not requested_summary_metrics:
                requested_metrics_available = True

            is_month_query = bool(
                re.search(
                    r"\b(?:month|months|monthly|month\s+wise|month-wise)\b",
                    normalized_question,
                    flags=re.IGNORECASE,
                )
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
                and requested_metrics_available
                and not invoice_count_query
                and is_month_query
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
                # Prefer the detailed transaction dataset for monthly
                # ranking questions when one is available.
                #
                # Example:
                # "Which month had the highest sales?"
                #
                # A detailed transaction dataset can calculate the
                # ranking directly from all transactions.
                #
                # Keep the summary bonus only when no detailed
                # transaction dataset exists.
                if not detailed_transaction_datasets:
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

                    # Resolve from schema first.
                    # Do NOT load full dataset rows during
                    # normal dataset selection.
                    resolved_metric_column = _resolve_column(
                        metric_phrase,
                        dataset,
                        schema,
                        [],
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


        # --------------------------------------------------------
        # STATE SALES RANKING DATASET PREFERENCE
        #
        # Examples:
        #   Which state has the highest sales?
        #   Which state has the lowest sales?
        #   Which are the top 3 states by sales?
        #   Which are the bottom 3 states by sales?
        #
        # Prefer a detailed transaction dataset containing
        # PartyState + InvoiceTotal over a small summary/ledger
        # dataset containing State + Invoice Value.
        # --------------------------------------------------------

        state_sales_ranking_query = bool(
            re.search(
                r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
            and re.search(
                r"\b(?:state|states)\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover)\b",
                normalized_question,
                flags=re.IGNORECASE,
            )
        )

        if (
            state_sales_ranking_query
            and _is_detailed_transaction_dataset(
                dataset,
                schema,
            )
        ):
                # Resolve metric columns from schema first.
                # Loading all rows is only needed as a fallback
                # when schema-based resolution cannot identify
                # the requested metric.
            candidate_rows = []

            state_column = _resolve_column(
                "PartyState",
                dataset,
                schema,
                candidate_rows,
            )

            sales_column = _resolve_column(
                "InvoiceTotal",
                dataset,
                schema,
                candidate_rows,
            )

            if state_column and sales_column:
                score += 1000

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

    # --------------------------------------------------------
    # MONTHLY RANKING DETAILED DATASET PREFERENCE
    #
    # For questions such as:
    #   "Which month has highest sales?"
    #   "Which month has lowest profit?"
    #
    # prefer the detailed transaction dataset when available.
    #
    # This prevents tiny/manual/sample datasets from winning
    # only because their schema matches the question strongly.
    # --------------------------------------------------------

    if monthly_ranking_query and detailed_transaction_datasets:
        detailed_scored = [
            item
            for item in scored
            if _is_detailed_transaction_dataset(
                item[2].get("dataset", {}),
                item[2].get("schema", []),
            )
        ]

        if detailed_scored:
            detailed_scored.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                ),
                reverse=True,
            )

            best_score, best_id, best_item = detailed_scored[0]
        else:
            best_score, best_id, best_item = scored[0]
    else:
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

        normalized_period_question = _normalize_text(question)

        date_query_detected = bool(
            re.search(
                r"\b(?:for|in|during)\b.*?"
                r"\b(?:\d{4}|january|february|march|april|may|"
                r"june|july|august|september|october|november|"
                r"december)\b",
                normalized_period_question,
                flags=re.IGNORECASE,
            )
        )

        # Explicit period-comparison queries.
        #
        # Examples:
        #   from January 2024 to July 2025
        #   from July 2025 to August 2025
        #   January 2024 vs July 2025
        #   January 2024 compared with July 2025
        #
        # These queries must use a detailed transaction dataset.
        explicit_period_comparison = bool(
            re.search(
                r"\bfrom\b.*?"
                r"\b(?:january|february|march|april|may|june|"
                r"july|august|september|october|november|"
                r"december|\d{4})\b"
                r".*?"
                r"\bto\b.*?"
                r"\b(?:january|february|march|april|may|june|"
                r"july|august|september|october|november|"
                r"december|\d{4})\b",
                normalized_period_question,
                flags=re.IGNORECASE,
            )
            or re.search(
                r"\b(?:january|february|march|april|may|june|"
                r"july|august|september|october|november|"
                r"december)\b.*?"
                r"\b(?:vs|versus|compared\s+with|compared\s+to|"
                r"against)\b.*?"
                r"\b(?:january|february|march|april|may|june|"
                r"july|august|september|october|november|"
                r"december)\b",
                normalized_period_question,
                flags=re.IGNORECASE,
            )
        )

        if explicit_period_comparison:
            date_query_detected = True

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

                # ------------------------------------------------
                # PERIOD COMPARISON
                # ------------------------------------------------
                #
                # Do NOT use date_eligibility_cache here.
                #
                # _extract_date_filters() represents a normal
                # single-period query. For:
                #
                #   January 2024 -> July 2025
                #
                # it extracts only:
                #
                #   year=2024 AND month=1
                #
                # which incorrectly rejects a dataset that contains
                # July 2025.
                #
                # Instead, let _extract_period_comparison() identify
                # the two requested periods and check whether the
                # detailed dataset contains data in at least one of
                # them.
                # ------------------------------------------------

                if explicit_period_comparison:

                    try:
                        detailed_schema = get_dataset_schema(
                            detailed_id
                        )
                    except Exception:
                        detailed_schema = []

                    try:
                        detailed_rows = load_dataset_rows(
                            detailed_id
                        )
                    except Exception:
                        detailed_rows = []

                    try:
                        period_info = _extract_period_comparison(
                            question,
                            detailed_dataset,
                            detailed_schema,
                            detailed_rows,
                        )
                    except Exception:
                        period_info = None

                    if period_info:

                        period_1 = period_info.get(
                            "period_1"
                        )
                        period_2 = period_info.get(
                            "period_2"
                        )
                        comparison_date_column = (
                            period_info.get("column")
                        )

                        period_1_exists = False
                        period_2_exists = False

                        if (
                            comparison_date_column
                            and detailed_rows
                            and period_1
                            and period_2
                        ):

                            for row in detailed_rows:

                                row_data = (
                                    row.get("data", row)
                                    if isinstance(row, dict)
                                    else {}
                                )

                                raw_date = row_data.get(
                                    comparison_date_column
                                )

                                if raw_date is None:
                                    continue

                                date_text = str(
                                    raw_date
                                ).strip()

                                parsed_row_date = _parse_date(
                                    raw_date
                                )

                                if not parsed_row_date:
                                    continue

                                period_type = period_info.get(
                                    "period_type",
                                    "month",
                                )

                                if period_type == "day":
                                    row_period = parsed_row_date.strftime(
                                        "%Y-%m-%d"
                                    )

                                elif period_type == "year":
                                    row_period = parsed_row_date.strftime(
                                        "%Y"
                                    )

                                else:
                                    row_period = parsed_row_date.strftime(
                                        "%Y-%m"
                                    )

                                if row_period == period_1:
                                    period_1_exists = True

                                if row_period == period_2:
                                    period_2_exists = True

                                if (
                                    period_1_exists
                                    or period_2_exists
                                ):
                                    break

                        detailed_period_exists = (
                            period_1_exists
                            or period_2_exists
                        )

                    else:
                        detailed_period_exists = False

                else:

                    # Existing behavior for normal single-period
                    # date queries remains unchanged.
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
    # Top-N queries must NOT use scalar SQL MAX/MIN.
    #
    # Examples:
    #   Which 5 invoices have the highest invoice value?
    #   Which 10 invoices have the highest sales?
    #   Which 5 invoices have the lowest invoice value?
    #
    # These require the actual rows, not one scalar aggregate.
    # --------------------------------------------------------

    top_n_match = _extract_top_n(question)

    if top_n_match[0]:
        return False, None, None

    # --------------------------------------------------------
    # Grouped ranking queries must NOT use scalar SQL MAX/MIN.
    #
    # Examples:
    #   which client has highest sales
    #   which customer has highest profit
    #   which product has lowest quantity
    #   which category has maximum revenue
    #
    # These queries require grouping by an entity and then
    # aggregating the requested metric.
    # --------------------------------------------------------

    grouped_ranking_query = bool(
        re.search(
            r"\b(?:which|what)\s+.+?\s+"
            r"(?:has|have|with)\s+"
            r"(?:highest|maximum|max|largest|lowest|minimum|min|smallest)\s+"
            r".+",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if grouped_ranking_query:
        return False, None, None

    # Payment-mode ranking must use grouped SUM(InvoiceTotal),
    # never scalar MAX/MIN on individual invoices.
    payment_mode_ranking = bool(
        re.search(
            r"\b(?:payment\s+modes?|payment\s+methods?)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:highest|maximum|most|lowest|minimum|least)\b",
            question_norm,
        )
    )

    if payment_mode_ranking:
        return False, None, None
    
    # --------------------------------------------------------
    # Numeric-filter queries must NOT use the scalar SQL
    # aggregate fast path.
    #
    # Examples:
    #   Show invoices with invoice total above ?20000
    #   Show invoices with invoice total below ?30000
    #   Show invoices with invoice total between ?20000 and ?30000
    #   Show invoices with profit at least ?10000
    # --------------------------------------------------------

    numeric_filter_query = bool(
        re.search(
            r"\b(?:above|below|over|under|greater\s+than|"
            r"less\s+than|at\s+least|at\s+most|between)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if numeric_filter_query:
        return False, None, None
    # --------------------------------------------------------
    # Relative/ordered month queries must use the date-filter
    # path instead of the scalar SQL fast path.
    #
    # Examples:
    #   total sales first 3 months
    #   total sales last 3 months
    #   total sales previous 3 months
    # --------------------------------------------------------

    relative_temporal_query = bool(
        re.search(
            r"\b(?:first|last|previous|latest)\s+"
            r"(?:(?:\d+|one|two|three|four|five|six|seven|eight|"
            r"nine|ten|eleven|twelve)\s+)?"
            r"(?:available\s+)?"
            r"(?:day|days|week|weeks|month|months|quarter|quarters|year|years)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if relative_temporal_query:
        return False, None, None
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
        # Relative temporal queries must use the row-based path.
        #
        # Examples:
        #   average sales last 3 months
        #   total profit last month
        #   sales previous 2 months
        #
        # These queries must use the latest available periods from
        # the uploaded dataset rather than the scalar SQL fast path.
        # --------------------------------------------------------

        relative_temporal_query = bool(
            re.search(
                r"\b(?:last|previous|latest)\s+"
                r"(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+)?"
                r"(?:available\s+)?"
                r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )

        if relative_temporal_query:
            return False, None, None

        # --------------------------------------------------------
        # Multiple business metrics must use the row-based path.
        #
        # Examples:
        #   average sales and average profit
        #   sales and GST
        #   quantity and discount
        #
        # A scalar SQL aggregate can return only one metric, so
        # these queries must reach the multi-aggregate engine.
        # --------------------------------------------------------

        metric_terms = re.findall(
            r"\b(?:sales?|selling|revenue|turnover|billing|business|"
            r"quantity|qty|gst|total\s+gst|cgst|sgst|igst|"
            r"discount|taxable(?:\s+amount)?|cost|"
            r"invoice\s+(?:value|amount|total))\b",
            question_norm,
            flags=re.IGNORECASE,
        )

        unique_metric_terms = {
            _normalize_text(item)
            for item in metric_terms
        }

        if len(unique_metric_terms) >= 2:
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
            r"\b(?:sales?|revenue|billing|turnover|quantity|qty)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|product|products|item|items|category|categories|hsn\s+code|hsn\s+codes|state|states)\b",
            question_norm,
        )
    )

    if grouped_sales_ranking:
        return False, None, None


    # --------------------------------------------------------
    # Time-based ranking must NOT use scalar SQL MAX/MIN.
    #
    # Examples:
    #   Which month has highest sales?
    #   Which month highest sales are done?
    #   Which year has highest sales?
    #   Which month has lowest profit?
    #
    # These require:
    #   GROUP BY month/year
    #   SUM(metric)
    #   ORDER BY aggregate DESC/ASC
    # --------------------------------------------------------

    temporal_ranking = bool(
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|"
            r"totalgst|total\s+gst|cgst|sgst|igst|"
            r"quantity|qty|discount|taxable|taxable\s+amount|"
            r"invoice\s+value|invoice\s+amount|invoice\s+total)\b",
            question_norm,
        )
    )

    if temporal_ranking:
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
            r"\b(?:gst|totalgst|total\s+gst|cgst|sgst|igst)\b",
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
    # Entity/value-filter queries must NOT use scalar SQL.
    #
    # Examples:
    #   Show total sales for Pooja
    #   Show sales of Pooja Sharma
    #   Profit for Rahul
    #   Quantity for product ABC
    #   Pooja ki sales
    #
    # These queries require actual row filtering first.
    # The Python filter resolver will match the value against
    # the uploaded dataset and then calculate the aggregate.
    # --------------------------------------------------------

    entity_filter_query = bool(
        re.search(
            r"\b(?:for|from|of)\s+"
            r"[A-Za-z][A-Za-z0-9_-]*"
            r"(?:\s+[A-Za-z][A-Za-z0-9_-]*){0,4}\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        or re.search(
            r"\b\S+\s+(?:ki|ka|ke)\s+"
            r"(?:sales|revenue|turnover|profit|quantity|qty|"
            r"amount|gst|tax|billing|business|invoice|invoices)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if entity_filter_query:
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
        r"\b(?:sum|total|how\s+much|kitna|kitni|kitne)\b",
        question_norm,
    ):
        function = "sum"

    else:
        implicit_sum_query = bool(
            re.search(
                r"\b(?:business\s+value|business\s+amount|"
                r"business\s+done|sales\s+value|"
                r"selling\s+value)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )

        if implicit_sum_query:
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
    # IMPORTANT:
    #   "sales", "revenue", "billing", "turnover"
    #   use GrossAmount.
    #
    # Explicit invoice-value wording continues to use
    # InvoiceTotal / Invoice Value.
    #
    # Examples:
    #   Show total sales
    #       -> GrossAmount
    #
    #   Show total revenue
    #       -> GrossAmount
    #
    #   Show total gross amount
    #       -> GrossAmount
    #
    #   Show total invoice value
    #       -> InvoiceTotal
    #
    #   Show total invoice amount
    #       -> InvoiceTotal
    #
    #   Show total invoice total
    #       -> InvoiceTotal
    # --------------------------------------------------------

    generic_sales_query = bool(
        re.search(
            r"\b(?:sales?|selling|revenue|turnover|billing|"
            r"business|business\s+value|business\s+amount|"
            r"sales\s+value|selling\s+value|business\s+done)\b",
            question_norm,
        )
    )

    invoice_value_query = bool(
        re.search(
            r"\binvoice\s+(?:value|amount|total)\b",
            question_norm,
        )
    )

    if generic_sales_query:
        sales_candidates = [
            "GrossAmount",
            "Gross Amount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
            "Revenue",
            "Turnover",
            "InvoiceTotal",
            "Invoice Total",
            "Invoice Value",
            "Total Amount",
            "TotalAmount",
        ]

    elif invoice_value_query:
        sales_candidates = [
            "InvoiceTotal",
            "Invoice Total",
            "Invoice Value",
            "Total Amount",
            "TotalAmount",
            "GrossAmount",
            "Gross Amount",
            "Sales Amount",
            "SalesAmount",
            "Amount",
        ]

    else:
        sales_candidates = []

    for candidate in sales_candidates:
        candidate_norm = _normalize_text(candidate)

        for source_column in numeric_columns:
            if (
                _normalize_text(source_column)
                == candidate_norm
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
    # --------------------------------------------------------
    # FINAL SQL FAST-PATH SAFETY GATE
    #
    # Scalar SQL aggregation cannot safely handle relative
    # temporal queries or multiple requested metrics.
    # --------------------------------------------------------
    _normalized_question = _normalize_text(question)

    # Explicit numeric date/month queries must use the
    # filtered row-based path, not SQL fast path.
    _explicit_numeric_date_sql_block = bool(
        re.search(
            r"\b(?:20\d{2}\s+(?:0?[1-9]|1[0-2])(?:\s+(?:0?[1-9]|[12]\d|3[01]))?|(?:0?[1-9]|1[0-2])\s+20\d{2}|(?:0?[1-9]|[12]\d|3[01])\s+(?:0?[1-9]|1[0-2])\s+20\d{2})\b",
            _normalized_question,
            flags=re.IGNORECASE,
        )
    )

    _relative_temporal_sql_block = bool(
        re.search(
            r"\b(?:last|previous|latest)\s+"
            r"(?:\d+\s+)?(?:available\s+)?"
            r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
            question,
            flags=re.IGNORECASE,
        )
    )

    _metric_terms_sql_block = re.findall(
        r"\b(?:sales?|selling|revenue|turnover|billing|business|"
        r"quantity|qty|gst|total\s+gst|cgst|sgst|igst|"
        r"discount|taxable(?:\s+amount)?|cost|"
        r"invoice\s+(?:value|amount|total))\b",
        question,
        flags=re.IGNORECASE,
    )

    _unique_metric_terms_sql_block = {
        _normalize_text(item)
        for item in _metric_terms_sql_block
    }

    _multiple_metrics_sql_block = (
        len(_unique_metric_terms_sql_block) >= 2
    )

    if (
        _relative_temporal_sql_block
        or _multiple_metrics_sql_block
        or _explicit_numeric_date_sql_block
    ):
        sql_fast_path = False
        sql_function = None
        sql_column = None
    else:
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
    planner_filters_sql_block = (
        (state.get("query_plan") or {}).get("filters") or []
    )
    if (
        sql_fast_path
        and sql_function
        and sql_column
        and not planner_filters_sql_block
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

    # ========================================================
    # GENERIC TEMPORAL FILTER EXTRACTION
    #
    # This must happen AFTER rows are loaded because relative
    # periods such as "latest month" and "previous year" are
    # defined by periods actually available in the dataset.
    #
    # The planner may know the metric, but the loaded dataset
    # is the source of truth for temporal filters.
    # ========================================================

    _plan_for_filters = state.get("query_plan")
    existing_filters = list(state.get("filters") or []) + list(
        (
            _plan_for_filters.get("filters")
            if isinstance(_plan_for_filters, dict)
            else None
        )
        or []
    )

    try:
        loaded_date_filters = _extract_date_filters(
            question,
            dataset,
            schema,
            cleaned_rows,
        )
    except Exception:
        loaded_date_filters = []

    combined_filters = _deduplicate_filters(
        list(existing_filters) + list(loaded_date_filters)
    )

    updated_query_plan = state.get("query_plan")

    if isinstance(updated_query_plan, dict):
        updated_query_plan = {
            **updated_query_plan,
            "filters": combined_filters,
        }

    return {
        **state,
        "rows": cleaned_rows,
        "filters": combined_filters,
        "query_plan": updated_query_plan,
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
    # 0. latest N / most recent N
    #
    # "latest 5 invoices" means the latest available
    # invoice dates, not the highest invoice values.
    #
    # The execution layer handles this as Date DESC.
    latest_match = re.search(
        r"\b(?:latest|most\s+recent)\s+(\d+)\s+"
        r"(?:invoices?|transactions?|records?)\b",
        question_norm,
        flags=re.IGNORECASE,
    )

    if latest_match:
        return (
            int(latest_match.group(1)),
            "desc",
            "latest",
        )
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
        r"suppliers?|vendors?|payment\s+modes?|payment\s+methods?)\b"
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

    # --------------------------------------------------------
    # 5. Temporal ranking without explicit N
    # --------------------------------------------------------
    if (
        re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    ):
        ranking_match = re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
            flags=re.IGNORECASE,
        )

        ranking_word = (
            ranking_match.group(0).lower()
            if ranking_match
            else "highest"
        )

        direction = (
            "asc"
            if ranking_word in ("lowest", "minimum", "least", "bottom")
            else "desc"
        )

        return (
            1,
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

    # Normalize the structured LLM plan before
    # entering the existing deterministic engine.
    state = _normalize_planner_plan(state)

    question = state.get("question", "")
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
        

    # --------------------------------------------------------
    # UNIVERSAL QUERY PLAN EXECUTION
    # --------------------------------------------------------

    # Universal executor handles non-temporal generic queries.
    # Temporal queries continue through the existing deterministic
    # temporal engine so latest/last/previous periods are resolved
    # from the uploaded dataset.
    planner_plan = state.get("query_plan") or {}
    planner_time = planner_plan.get("time")

    # Relative temporal queries must use the deterministic
    # date-filter engine because "latest/previous/last"
    # depends on periods actually available in the dataset.
    relative_temporal_query = bool(
        re.search(
            r"\b(?:latest|current|most recent|recent|previous|prior|last)"
            r"\s+(?:\d+\s+)?(?:available\s+)?"
            r"(?:\d+\s+)?(?:month|months|year|years|quarter|quarters)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    planner_operation = (
        planner_plan.get("operation")
        if isinstance(planner_plan, dict)
        else None
    )

    temporal_aggregate_query = bool(
        planner_operation == "aggregate"
        and planner_plan.get("aggregate_function")
        and (
            planner_plan.get("metrics")
            or planner_plan.get("metric")
        )
        and (
            planner_time
            or relative_temporal_query
        )
    )
    if temporal_aggregate_query:
        universal_result = _execute_universal_plan(
            state,
            dataset,
            schema,
            rows,
        )
    elif planner_time or relative_temporal_query:
        universal_result = None
    else:
        universal_result = _execute_universal_plan(
            state,
            dataset,
            schema,
            rows,
        )

    if universal_result is not None:

        if universal_result.get("status") == "DATA_NOT_AVAILABLE":
            return {
                **state,
                "result": universal_result,
                "answer": universal_result.get(
                    "message",
                    "Data not available in uploaded file/data",
                ),
                "error": None,
            }

        return {
            **state,
            "result": universal_result,
            "rows": universal_result.get("rows", []),
            "intent": (
                "group_aggregate"
                if universal_result.get("operation")
                in {
                    "group_aggregate",
                    "ranking",
                }
                else "aggregate"
            ),
            "group_by": universal_result.get(
                "group_by"
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
            [],
        )
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

    distinct_values_requested = bool(
        re.search(
            r"\b(?:unique|distinct)\b",
            question_norm,
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
                    [],
        )

        categorical_filters = _extract_categorical_filters(
            question,
            dataset,
            schema,
                    [],
        )


        date_filters = _extract_date_filters(
            question,
            dataset,
            schema,
                    [],
        )


    filters = _deduplicate_filters(
        numeric_filters
        + categorical_filters
        + date_filters
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
                    [],
    )
    temporal_ranking_query = bool(
        re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question,
            re.IGNORECASE,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|"
            r"totalgst|total\s+gst|cgst|sgst|igst|"
            r"quantity|qty|discount|taxable|taxable\s+amount|invoice\s+(?:value|amount|total)|invoicevalue|invoiceamount|invoicetotal)\b",
            question,
            re.IGNORECASE,
        )
    )    

    group_by = _extract_group_by(
        question,
        dataset,
        schema,
                    [],
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
        
    # --------------------------------------------------------
    # FALLBACK TIME GROUPING FOR IMPLICIT MULTI-METRIC QUERIES
    #
    # Examples:
    #   Show invoice count and discount year wise
    #   Show sales and profit quarter wise
    #   Show quantity and sales month wise
    #
    # If the normal time-grouping detector did not resolve the
    # period, resolve the actual date column directly.
    # --------------------------------------------------------

    if (
        not time_grouping
        and not group_by
        and re.search(
            r"\b(?:year|yearly|month|monthly|quarter|quarterly|"
            r"day|daily)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:wise|by|per|each)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    ):
        fallback_date_column = None

        for candidate in (
            "Date",
            "Transaction Date",
            "TransactionDate",
            "Bill Date",
            "BillDate",
            "Invoice Date",
            "InvoiceDate",
        ):
            fallback_date_column = _resolve_column(
                candidate,
                dataset,
                schema,
                    [],
            )

            if fallback_date_column:
                break

        if fallback_date_column:
            group_by = fallback_date_column

            if re.search(
                r"\b(?:year|yearly)\b",
                question_norm,
                flags=re.IGNORECASE,
            ):
                fallback_period = "year"

            elif re.search(
                r"\b(?:quarter|quarterly)\b",
                question_norm,
                flags=re.IGNORECASE,
            ):
                fallback_period = "quarter"

            elif re.search(
                r"\b(?:month|monthly)\b",
                question_norm,
                flags=re.IGNORECASE,
            ):
                fallback_period = "month"

            else:
                fallback_period = "day"

            time_grouping = {
                "column": fallback_date_column,
                "period": fallback_period,
            }

    # --------------------------------------------------------
    # RELATIVE SINGLE-PERIOD QUERY OVERRIDE
    # --------------------------------------------------------
    # latest/last/previous month means one available month,
    # not a month-wise grouped result.

    relative_single_month_query = bool(
        re.search(
            r"\b(?:latest|last|previous)\s+(?:available\s+)?month\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and not re.search(
            r"\b(?:by|wise|per|each)\s+month\b"
            r"|\bmonth\s+wise\b"
            r"|\bmonthly\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if relative_single_month_query:
        group_by = None
        time_grouping = None
   
    relative_multi_month_query = bool(
        re.search(
            r"\b(?:last|previous|prior)\s+\d+\s+(?:available\s+)?months?\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and not re.search(
            r"\b(?:by|wise|per|each)\s+month\b"
            r"|\bmonth\s+wise\b"
            r"|\bmonthly\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if relative_multi_month_query:
        group_by = None
        time_grouping = None
        requested_columns = []
    # --------------------------------------------------------
    # RELATIVE SINGLE-PERIOD QUERY OVERRIDE
    #
    # latest/last/previous year or quarter means one
    # available period, not a grouped result.
    #
    # Examples:
    #   latest year profit
    #   previous year sales
    #   latest quarter GST
    # --------------------------------------------------------

    relative_single_period_query = bool(
        re.search(
            r"\b(?:latest|current|most recent|recent|previous|prior|last)"
            r"\s+(?:available\s+)?"
            r"(?:year|years|quarter|quarters)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and not re.search(
            r"\b(?:by|wise|per|each)\s+"
            r"(?:year|years|quarter|quarters)\b"
            r"|\b(?:year|years|quarter|quarters)\s+wise\b"
            r"|\b(?:yearly|quarterly)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if relative_single_period_query:
        group_by = None
        time_grouping = None
        
    aggregate_function, aggregate_column = (
        _extract_aggregate(
            question,
            dataset,
            schema,
                    [],
        )
    )
    
    # --------------------------------------------------------
    # HONOR VALID UNIVERSAL PLANNER AGGREGATE
    #
    # The planner has already resolved semantic queries such as:
    #   latest month profit
    #   previous year sales
    #   latest quarter GST
    #
    # _extract_aggregate() may not recognize the temporal wording
    # itself, so preserve the planner's deterministic aggregate
    # when it is already valid.
    # --------------------------------------------------------

    planner_plan = state.get("query_plan") or {}

    if (
        isinstance(planner_plan, dict)
        and planner_plan.get("status") == "OK"
        and planner_plan.get("operation") == "aggregate"
        and planner_plan.get("aggregate_function")
        and planner_plan.get("aggregate_column")
    ):
        aggregate_function = planner_plan.get(
            "aggregate_function"
        )
        aggregate_column = planner_plan.get(
            "aggregate_column"
        )
    
    # --------------------------------------------------------
    # IMPLICIT MULTI-METRIC GROUPED QUERY
    #
    # Examples:
    #   Show sales and profit quarter wise
    #   Show invoice count and discount year wise
    #   Show quantity and sales product wise
    #
    # These queries imply SUM/COUNT even though they do not
    # explicitly say "total" or "sum".
    # --------------------------------------------------------

    implicit_group_metrics = []

    if group_by:
        implicit_group_metrics = (
            _extract_implicit_group_metrics(
                question,
                dataset,
                schema,
                    [],
            )
        )

    
 
    # --------------------------------------------------------
    # Temporal sales ranking metric
    #
    # Generic sales/revenue/month ranking must use GrossAmount.
    # Explicit invoice value/amount/total must remain InvoiceTotal.
    #
    # Examples:
    #   highest sales month
    #       -> GrossAmount
    #
    #   lowest sales month
    #       -> GrossAmount
    #
    #   highest invoice value month
    #       -> InvoiceTotal
    # --------------------------------------------------------

    if (
        temporal_ranking_query
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and not re.search(
            r"\binvoice\s+(?:value|amount|total)\b"
            r"|\binvoicevalue\b"
            r"|\binvoiceamount\b"
            r"|\binvoicetotal\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    ):
        gross_amount_column = _resolve_column(
            "GrossAmount",
            dataset,
            schema,
                    [],
        )

        if gross_amount_column:
            aggregate_function = "sum"
            aggregate_column = gross_amount_column
    
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
        and re.search(
            r"\b(?:invoice\s*no|invoiceno|invoice\s+number)\b",
            question_norm,
            flags=re.IGNORECASE,
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
        not top_n
        and (
            re.search(
                r"\b(?:show|give|list|display|return|fetch|provide|export)\b"
                r".*?\b(?:all|every)\b"
                r".*?\b(?:rows?|records?|transactions?|"
                r"invoices?(?!\s+(?:count|counts)))\b",
                question_norm,
                flags=re.IGNORECASE,
            )
            or
            re.search(
                r"\b(?:show|give|list|display|return|fetch|provide|export)\b"
                r".*?\b(?:rows?|records?|transactions?|"
                r"invoices?(?!\s+(?:count|counts)))\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )
    )
    
    # --------------------------------------------------------
    # INVOICE COUNT IS AN AGGREGATE QUERY, NOT RAW ROW REQUEST
    # --------------------------------------------------------

    invoice_count_query = bool(
        re.search(
            r"\b(?:invoice\s+count|invoice\s+counts|"
            r"count\s+(?:of\s+)?invoices?|"
            r"number\s+of\s+invoices?|"
            r"how\s+many\s+invoices?)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if invoice_count_query:
        raw_rows_requested = False

    # --------------------------------------------------------
    # EXPLICIT COLUMN PROJECTION IS ALSO A DETAIL REQUEST
    #
    # Example:
    #   Show InvoiceNo and Date for Pooja Sharma
    #
    # Return at most 20 rows by default.
    # --------------------------------------------------------

    projection_rows_requested = bool(
        not top_n
        and not re.search(
            r"\b(?:all|every)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:show|display|list|give|get|fetch|return)\b"
            r".*?\b(?:invoice(?:s)?|invoiceno|invoice\s*no|date|partyname|"
            r"product|category|quantity|qty|profit|grossamount|"
            r"invoicetotal|paymentmode|record(?:s)?|transaction(?:s)?|row(?:s)?)\b",
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

    if raw_rows_requested or projection_rows_requested:
        aggregate_function = None
        aggregate_column = None
        group_by = None
        time_grouping = None

    # --------------------------------------------------------
    # EXPLICIT TOP-N INVOICE ROW RANKING PRIORITY
    #
    # Examples:
    #   Show top 5 invoices by invoice value
    #   Show bottom 5 invoices by invoice value
    #   Show top 10 invoices by profit
    #   Show highest 5 invoices by sales
    #
    # Invoice is an individual row/entity here.
    # It must NOT become:
    #
    #   GROUP BY InvoiceNo
    #
    # because TOP-N individual ranking must sort all
    # matching invoice rows and then apply the limit.
    # --------------------------------------------------------

    top_n_invoice_row_priority = bool(
        top_n
        and re.search(
            r"\b(?:invoice|invoices|transaction|transactions)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:invoice\s+(?:value|amount|total)|"
            r"invoicevalue|invoiceamount|invoicetotal|"
            r"sales?|revenue|billing|turnover|"
            r"profit|discount|quantity|qty|"
            r"gst|total\s+gst|totalgst|"
            r"cgst|sgst|igst|"
            r"taxable|taxable\s+amount|taxableamount|"
            r"cost|gross|gross\s+amount|grossamount|"
            r"unit\s+price|unitprice|price)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if top_n_invoice_row_priority:
        group_by = None
        time_grouping = None

    ranking_group_query = bool(
        group_by
        and re.search(
            r"\b(?:highest|maximum|top)\b|(?<!at )\bmost\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|discount|quantity|qty|taxable|taxable\s+amount|taxableamount|cost|gross|gross\s+amount|grossamount|cgst|sgst|igst|gst|totalgst|total\s+gst|profit)\b",
            question_norm,
        )
    )

    lowest_ranking_group_query = bool(
        group_by
        and re.search(
            r"\b(?:lowest|minimum|bottom)\b|(?<!at )\bleast\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|"
            r"profit|gst|totalgst|total\s+gst|"
            r"cgst|sgst|igst|discount|"
            r"quantity|qty|taxable|taxable\s+amount|"
            r"taxableamount|cost|gross|gross\s+amount|"
            r"grossamount|unit\s+price|unitprice|price)\b",
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
            "TotalGST",
            "Total GST",
            "CGST",
            "SGST",
            "IGST",
            "DiscountAmt",
            "Discount Amount",
            "Cost",
            "Qty",
            "Quantity",
            "UnitPrice",
            "Unit Price",
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

    original_filtered_row_count = len(filtered_rows)

    if raw_rows_requested or projection_rows_requested:
        if requested_row_count is not None:
            filtered_rows = filtered_rows[:requested_row_count]
        else:
            filtered_rows = filtered_rows[:20]
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
                    [],
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
                    [],
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

            if period_type == "day":
                row_period = parsed_date.strftime(
                    "%Y-%m-%d"
                )

            elif period_type == "month":
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
        # Resolve the requested comparison metric.
        # ----------------------------------------------------

        comparison_metric_key = period_comparison.get(
            "metric_key",
            "sales",
        )

        comparison_metric_label = period_comparison.get(
            "metric_label",
            "Sales",
        )

        comparison_column_value = _resolve_column(
            comparison_metric_key,
            dataset,
            schema,
                    [],
        )

        # Sales fallback
        if not comparison_column_value:
            comparison_column_value = _resolve_column(
                "sales",
                dataset,
                schema,
                    [],
            )

        # Final fallback
        if not comparison_column_value:
            comparison_column_value = _resolve_column(
                "amount",
                dataset,
                schema,
                    [],
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
            "metric_key": comparison_metric_key,
            "metric_label": comparison_metric_label,
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
                    comparison_metric_label: (
                        period_1_total
                        if period_1_has_data
                        else None
                    ),
                },
                {
                    "Period": period_2,
                    comparison_metric_label: (
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
            "filtered_rows": original_filtered_row_count,
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
    # PAYMENT MODE SALES RANKING
    # --------------------------------------------------------
    #
    # Examples:
    #   Which payment mode has the highest sales?
    #   Which payment mode has the lowest sales?
    #   Which payment modes have the highest sales?
    #   Which payment modes have the lowest sales?
    #   Which 3 payment modes have the highest sales?
    #
    # Payment modes must always be ranked by:
    #
    #   PaymentMode -> SUM(InvoiceTotal)
    #
    # Never use MAX/MIN on individual InvoiceTotal rows.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # TEMPORAL TOP-N RANKING
    # --------------------------------------------------------
    #
    # Examples:
    #   What are the top 3 sales months?
    #   What are the bottom 3 sales months?
    #   What are the top 3 invoice value months?
    #   What are the bottom 3 invoice value months?
    #
    # Aggregate by time period first, then rank the periods.
    # Do NOT rank individual invoice rows.
    # --------------------------------------------------------

    temporal_top_n_query = bool(
        time_grouping
        and top_n
        and re.search(
            r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|profit|gst|"
            r"totalgst|total\s+gst|cgst|sgst|igst|quantity|qty|"
            r"discount|taxable|taxable\s+amount|"
            r"invoice\s+(?:value|amount|total)|"
            r"invoicevalue|invoiceamount|invoicetotal)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if temporal_top_n_query:

        temporal_group_column = time_grouping["column"]
        temporal_period = time_grouping.get("period")

        # Explicit invoice value -> InvoiceTotal.
        if re.search(
            r"\binvoice\s+(?:value|amount|total)\b"
            r"|\binvoicevalue\b"
            r"|\binvoiceamount\b"
            r"|\binvoicetotal\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "InvoiceTotal",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bprofit\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "Profit",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\b(?:total\s+gst|totalgst|gst)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "TotalGST",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bdiscount\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "DiscountAmt",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\b(?:taxable|taxable\s+amount)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "TaxableAmount",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\b(?:quantity|qty)\b",
            question_norm,
            flags=re.IGNORECASE,
        ):
            temporal_metric_column = _resolve_column(
                "Qty",
                dataset,
                schema,
                filtered_rows,
            )

        else:
            # Generic sales/revenue -> GrossAmount.
            temporal_metric_column = _resolve_column(
                "GrossAmount",
                dataset,
                schema,
                filtered_rows,
            )

        if temporal_metric_column:

            temporal_grouped = _group_aggregate(
                filtered_rows,
                temporal_group_column,
                "sum",
                temporal_metric_column,
                time_period=temporal_period,
            )

            def _temporal_ranking_value(row):
                if not isinstance(row, dict):
                    return 0.0

                for key, value in row.items():
                    if key == temporal_group_column:
                        continue

                    numeric_value = _to_number(value)

                    if numeric_value is not None:
                        return numeric_value

                return 0.0

            temporal_grouped.sort(
                key=_temporal_ranking_value,
                reverse=(top_direction != "asc"),
            )

            temporal_grouped = temporal_grouped[:top_n]

            result = {
                "operation": "group_aggregate",
                "group_by": temporal_group_column,
                "aggregate_function": "sum",
                "aggregate_column": temporal_metric_column,
                "time_period": temporal_period,
                "rows": temporal_grouped,
                "count": len(temporal_grouped),
                "source_rows": len(rows),
                "filtered_rows": len(filtered_rows),
            }

            return {
                **state,
                "intent": "group_aggregate",
                "requested_columns": requested_columns,
                "unavailable_columns": unavailable_columns,
                "filters": filters,
                "group_by": temporal_group_column,
                "aggregate_function": "sum",
                "aggregate_column": temporal_metric_column,
                "rows": temporal_grouped,
                "result": result,
            }
    payment_mode_sales_ranking = bool(
        re.search(
            r"\b(?:payment\s+modes?|payment\s+methods?)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover)\b",
            question_norm,
        )
        and (
            top_n
            or re.search(
                r"\b(?:highest|maximum|most|lowest|minimum|least)\b",
                question_norm,
            )
        )
    )

    if payment_mode_sales_ranking:

        payment_mode_group = _resolve_column(
            "PaymentMode",
            dataset,
            schema,
            filtered_rows,
        )

        if not payment_mode_group:
            payment_mode_group = _resolve_column(
                "payment mode",
                dataset,
                schema,
                filtered_rows,
            )

        payment_mode_amount = _resolve_column(
            "InvoiceTotal",
            dataset,
            schema,
            filtered_rows,
        )

        if not payment_mode_amount:
            payment_mode_amount = _resolve_column(
                "invoice total",
                dataset,
                schema,
                filtered_rows,
            )

        if payment_mode_group and payment_mode_amount:

            payment_mode_grouped = _group_aggregate(
                filtered_rows,
                payment_mode_group,
                "sum",
                payment_mode_amount,
            )

            # Lowest / bottom must be ascending.
            if re.search(
                r"\b(?:lowest|minimum|bottom)\b|(?<!at )\bleast\b",
                question_norm,
            ):
                def _payment_mode_value(row):
                    if not isinstance(row, dict):
                        return 0.0

                    for key, value in row.items():
                        if key == payment_mode_group:
                            continue

                        numeric_value = _to_number(value)

                        if numeric_value is not None:
                            return numeric_value

                    return 0.0

                payment_mode_grouped.sort(
                    key=_payment_mode_value
                )

            # Highest / top stays descending.
            else:
                def _payment_mode_value(row):
                    if not isinstance(row, dict):
                        return 0.0

                    for key, value in row.items():
                        if key == payment_mode_group:
                            continue

                        numeric_value = _to_number(value)

                        if numeric_value is not None:
                            return numeric_value

                    return 0.0

                payment_mode_grouped.sort(
                    key=_payment_mode_value,
                    reverse=True,
                )

            # Explicit Top-N.
            if top_n:
                payment_mode_grouped = payment_mode_grouped[
                    :top_n
                ]

            # No number means return the single highest/lowest
            # payment mode.
            else:
                payment_mode_grouped = payment_mode_grouped[
                    :1
                ]

            result = {
                "operation": "group_aggregate",
                "group_by": payment_mode_group,
                "aggregate_function": "sum",
                "aggregate_column": payment_mode_amount,
                "rows": payment_mode_grouped,
                "count": len(payment_mode_grouped),
                "source_rows": len(rows),
                "filtered_rows": len(filtered_rows),
            }

            return {
                **state,
                "intent": "group_aggregate",
                "requested_columns": requested_columns,
                "unavailable_columns": unavailable_columns,
                "filters": filters,
                "group_by": payment_mode_group,
                "aggregate_function": "sum",
                "aggregate_column": payment_mode_amount,
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
            r"\b(?:highest|maximum|top|most|lowest|minimum|least|bottom)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:sales?|revenue|billing|turnover|taxable|taxable\s+amount|taxableamount|cost|gross|gross\s+amount|grossamount|unit\s+price|unitprice|price|quantity|qty|discount|invoice\s+(?:value|amount|total)|invoicevalue|invoiceamount|invoicetotal)\b",
            question_norm,
        )
        and re.search(
            r"\b(?:customer|customers|product|products|item|items|"
            r"category|categories|payment\s+modes?|payment\s+methods?|"
            r"hsn\s+code|hsn\s+codes|state|states)\b",
            question_norm,
        )
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

        elif re.search(
            r"\b(?:category|categories)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "category",
                dataset,
                schema,
                filtered_rows,
            )

            if not group_by:
                group_by = _resolve_column(
                    "Category",
                    dataset,
                    schema,
                    filtered_rows,
                )

        elif re.search(
            r"\b(?:payment\s+modes?|payment\s+methods?)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "PaymentMode",
                dataset,
                schema,
                filtered_rows,
            )

            if not group_by:
                group_by = _resolve_column(
                    "payment mode",
                    dataset,
                    schema,
                    filtered_rows,
                )
                
        elif re.search(
            r"\b(?:hsn\s+code|hsn\s+codes)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "HSN_Code",
                dataset,
                schema,
                filtered_rows,
            )

            if not group_by:
                group_by = _resolve_column(
                    "hsn code",
                    dataset,
                    schema,
                    filtered_rows,
                )

        elif re.search(
            r"\b(?:state|states)\b",
            question_norm,
        ):
            group_by = _resolve_column(
                "PartyState",
                dataset,
                schema,
                filtered_rows,
            )

            if not group_by:
                group_by = _resolve_column(
                    "state",
                    dataset,
                    schema,
                    filtered_rows,
                )

        # --------------------------------------------------------
        # Select the metric requested by the question.
        #
        # Customer/product ranking means:
        #   GROUP BY customer/product
        #   aggregate the requested metric
        #   sort highest/lowest
        #
        # Unit price is a per-unit value, so use MAX/MIN.
        # Other financial/quantity metrics are summed.
        # --------------------------------------------------------

        aggregate_function = "sum"
        aggregate_column = None

        requested_metric_map = [
            (
                r"\b(?:unit\s+price|unitprice|price)\b",
                "UnitPrice",
                "max",
            ),
            (
                r"\b(?:taxable\s+amount|taxableamount|taxable)\b",
                "TaxableAmount",
                "sum",
            ),
            (
                r"\bcost\b",
                "Cost",
                "sum",
            ),
            (
                r"\b(?:gross\s+amount|grossamount|gross)\b",
                "GrossAmount",
                "sum",
            ),
            (
                r"\b(?:quantity|qty)\b",
                "Qty",
                "sum",
            ),
            (
                r"\bdiscount\b",
                "DiscountAmt",
                "sum",
            ),
            (
                r"\bcgst\b",
                "CGST",
                "sum",
            ),
            (
                r"\bsgst\b",
                "SGST",
                "sum",
            ),
            (
                r"\bigst\b",
                "IGST",
                "sum",
            ),
            (
                r"\b(?:total\s+gst|totalgst|gst)\b",
                "TotalGST",
                "sum",
            ),
            (
                r"\bprofit\b",
                "Profit",
                "sum",
            ),
            (
                r"\b(?:sales?|revenue|billing|turnover)\b",
                "GrossAmount",
                "sum",
            ),
        ]

        for metric_pattern, metric_column_name, metric_function in requested_metric_map:

            if re.search(
                metric_pattern,
                question_norm,
            ):
                resolved_metric = _resolve_column(
                    metric_column_name,
                    dataset,
                    schema,
                    filtered_rows,
                )

                if resolved_metric:
                    aggregate_column = resolved_metric
                    aggregate_function = metric_function
                    break

        # Deterministic value-metric fallback.
        #
        # sales/revenue/billing/turnover -> actual sales column
        # invoice value/amount/total    -> InvoiceTotal
        #
        # Never use InvoiceTotal as a generic fallback for sales.
        # Never guess an unrelated numeric column for unsupported
        # metrics such as salary.
        if not aggregate_column:
            sales_context = bool(
                re.search(
                    r"\b(?:sales?|selling|revenue|billing|turnover)\b",
                    question_norm,
                    flags=re.IGNORECASE,
                )
            )

            invoice_value_context = bool(
                re.search(
                    r"\binvoice\s+(?:value|amount|total)\b",
                    question_norm,
                    flags=re.IGNORECASE,
                )
            )

            if sales_context:
                for candidate in (
                    "GrossAmount",
                    "Gross Amount",
                    "Sales Amount",
                    "SalesAmount",
                    "Revenue",
                ):
                    aggregate_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                        filtered_rows,
                    )

                    if aggregate_column:
                        break

            elif invoice_value_context:
                for candidate in (
                    "InvoiceTotal",
                    "Invoice Total",
                    "Invoice Value",
                    "Total Amount",
                    "TotalAmount",
                ):
                    aggregate_column = _resolve_column(
                        candidate,
                        dataset,
                        schema,
                        filtered_rows,
                    )

                    if aggregate_column:
                        break

        if aggregate_column:

            grouped = _group_aggregate(
                filtered_rows,
                group_by,
                aggregate_function,
                aggregate_column,
            )

            # Highest/lowest ranking.
            def _ranking_value(row):
                if not isinstance(row, dict):
                    return 0.0

                for key, value in row.items():
                    if key == group_by:
                        continue

                    try:
                        return float(
                            str(value)
                            .replace(",", "")
                            .replace("?", "")
                            .replace("?", "")
                            .replace("$", "")
                            .strip()
                        )
                    except (TypeError, ValueError):
                        continue

                return 0.0

            grouped.sort(
                key=_ranking_value,
                reverse=not bool(
                    re.search(
                        r"\b(?:lowest|minimum|least|bottom)\b",
                        question_norm,
                    )
                ),
            )

            # Singular question: return exactly one group.
            # Explicit Top-N queries are handled by the existing
            # Top-N grouped-ranking path because top_n is excluded
            # from this detection block.
            if top_n:
                grouped = grouped[:top_n]
            else:
                grouped = grouped[:1]

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
        and not re.search(
            r"\b(?:customer|customers|product|products|item|items|"
            r"category|categories|payment\s+modes?|payment\s+methods?|"
            r"hsn\s+code|hsn\s+codes|state|states)\b",
            question_norm,
        )
    )

    if top_n_row_query:

        ranking_column = None

        # ----------------------------------------------------
        # LATEST N INVOICES
        #
        # "latest 5 invoices" means the latest available
        # invoice dates in the uploaded dataset.
        #
        # It must NOT use InvoiceTotal/GrossAmount ranking.
        # ----------------------------------------------------

        latest_n_invoice_query = bool(
            top_n
            and re.search(
                r"\b(?:latest|most\s+recent)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
            and re.search(
                r"\b(?:invoice|invoices|transaction|transactions)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
            and not re.search(
                r"\b(?:invoice\s+(?:value|total|amount)|"
                r"sales?|revenue|billing|turnover|"
                r"profit|discount|quantity|qty|"
                r"gst|total\s+gst|cgst|sgst|igst|"
                r"taxable|taxable\s+amount|"
                r"cost|gross|gross\s+amount|"
                r"unit\s+price|unitprice|price)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )

        if latest_n_invoice_query:

            date_column = _resolve_column(
                "date",
                dataset,
                schema,
                filtered_rows,
            )

            if date_column:

                ranked_rows = []

                for row in filtered_rows:

                    raw_date = row.get(date_column)
                    parsed_date = _parse_date(raw_date)

                    if parsed_date is None:
                        continue

                    ranked_rows.append(
                        (
                            parsed_date,
                            row,
                        )
                    )

                ranked_rows.sort(
                    key=lambda item: item[0],
                    reverse=True,
                )

                selected_rows = [
                    row
                    for _, row in ranked_rows[:top_n]
                ]

                result = {
                    "operation": "top_n_rows",
                    "ranking_column": date_column,
                    "ranking_direction": "desc",
                    "ranking_type": "latest",
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
                    "aggregate_column": date_column,
                }

        # ----------------------------------------------------
        # GST / CGST / SGST / IGST / Discount
        # ----------------------------------------------------

        if re.search(
            r"\b(?:total\s+gst|totalgst|gst)\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "TotalGST",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bcgst\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "CGST",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bsgst\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "SGST",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bigst\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "IGST",
                dataset,
                schema,
                filtered_rows,
            )

        elif re.search(
            r"\bdiscount(?:\s+amount)?\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "DiscountAmt",
                dataset,
                schema,
                filtered_rows,
            )

        # ----------------------------------------------------
        # Highest/lowest profit
        # ----------------------------------------------------
        elif re.search(
            r"\b(?:quantity|qty)\b",
            question_norm,
        ):
            ranking_column = _resolve_column(
                "Qty",
                dataset,
                schema,
                filtered_rows,
            )
            
        elif re.search(
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

            # ------------------------------------------------
            # Invoice value / invoice total must rank using
            # InvoiceTotal, not GrossAmount.
            #
            # "invoice value" means the final invoice value.
            # "invoice total" means the final invoice total.
            # ------------------------------------------------

            if re.search(
                r"\binvoice\s+(?:value|total|amount)\b",
                question_norm,
            ):

                ranking_column = _resolve_column(
                    "InvoiceTotal",
                    dataset,
                    schema,
                    filtered_rows,
                )

            elif re.search(
                r"\b(?:sales?|revenue|billing|turnover)\b",
                question_norm,
            ):

                ranking_column = _resolve_column(
                    "GrossAmount",
                    dataset,
                    schema,
                    filtered_rows,
                )

            # ------------------------------------------------
            # Otherwise use the normal generic ranking
            # candidates.
            # ------------------------------------------------

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
    # GROUPED NUMERIC THRESHOLD QUERY
    #
    # Examples:
    #   Show customers with sales above ?500000
    #   Show products with profit above ?100000
    #   Show products with quantity above 500
    #
    # These queries mean:
    #
    #   1. GROUP BY the requested entity
    #   2. SUM the requested metric
    #   3. Apply the numeric threshold to the grouped result
    #
    # They must NOT filter individual invoice rows first.
    # --------------------------------------------------------

    grouped_numeric_threshold_query = bool(
        group_by
        and numeric_filters
        and re.search(
            r"\b(?:customer|customers|product|products|item|items|"
            r"party|parties|supplier|suppliers|vendor|vendors)\b",
            question_norm,
        )
    )

    if grouped_numeric_threshold_query:

        # ----------------------------------------------------
        # Determine the metric requested by the question.
        # ----------------------------------------------------

        threshold_metric = None

        if re.search(
            r"\b(?:profit|profits|margin)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "profit",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:quantity|qty|units?)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "qty",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:gst|total\s+gst)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "TotalGST",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:discount|discount\s+amount)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "DiscountAmt",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:unit\s+price|price)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "UnitPrice",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:taxable|taxable\s+amount)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "TaxableAmount",
                dataset,
                schema,
                    [],
            )

        elif re.search(
            r"\b(?:cost)\b",
            question_norm,
        ):
            threshold_metric = _resolve_column(
                "Cost",
                dataset,
                schema,
                    [],
            )

        else:
            # Sales / revenue / billing / turnover
            threshold_metric = _resolve_column(
                "InvoiceTotal",
                dataset,
                schema,
                    [],
            )

        if threshold_metric and group_by:

            # ------------------------------------------------
            # Group ALL source rows first.
            #
            # Important:
            # Do NOT use filtered_rows here because the
            # numeric threshold is supposed to apply AFTER
            # aggregation.
            # ------------------------------------------------

            grouped_source_rows = _group_aggregate(
                rows,
                group_by,
                "sum",
                threshold_metric,
            )

            # ------------------------------------------------
            # Apply every numeric threshold to the grouped
            # result.
            # ------------------------------------------------

            thresholded_grouped_rows = (
                grouped_source_rows
            )

            for numeric_filter in numeric_filters:

                filter_column = (
                    numeric_filter.get("column")
                )

                operator = (
                    numeric_filter.get("operator")
                )

                threshold_value = (
                    numeric_filter.get("value")
                )

                # The extractor may have resolved the
                # requested metric to its actual source
                # column name.
                if (
                    _normalize_text(
                        filter_column
                    )
                    != _normalize_text(
                        threshold_metric
                    )
                ):
                    continue

                def _group_result_value(
                    grouped_row
                ):
                    if not isinstance(
                        grouped_row,
                        dict,
                    ):
                        return None

                    for key, value in (
                        grouped_row.items()
                    ):
                        if (
                            _normalize_text(key)
                            == _normalize_text(
                                group_by
                            )
                        ):
                            continue

                        numeric_value = _to_number(
                            value
                        )

                        if numeric_value is not None:
                            return numeric_value

                    return None

                def _passes_group_threshold(
                    grouped_row
                ):
                    numeric_value = (
                        _group_result_value(
                            grouped_row
                        )
                    )

                    if numeric_value is None:
                        return False

                    if operator == ">":
                        return (
                            numeric_value
                            > threshold_value
                        )

                    if operator == ">=":
                        return (
                            numeric_value
                            >= threshold_value
                        )

                    if operator == "<":
                        return (
                            numeric_value
                            < threshold_value
                        )

                    if operator == "<=":
                        return (
                            numeric_value
                            <= threshold_value
                        )

                    if operator == "=":
                        return (
                            numeric_value
                            == threshold_value
                        )

                    return True

                thresholded_grouped_rows = [
                    grouped_row
                    for grouped_row
                    in thresholded_grouped_rows
                    if _passes_group_threshold(
                        grouped_row
                    )
                ]

            result = {
                "operation": "group_aggregate",
                "group_by": group_by,
                "aggregate_function": "sum",
                "aggregate_column": threshold_metric,
                "rows": thresholded_grouped_rows,
                "count": len(
                    thresholded_grouped_rows
                ),
                "source_rows": len(rows),
                "filtered_rows": len(
                    thresholded_grouped_rows
                ),
            }

            return {
                **state,
                "intent": "group_aggregate",
                "requested_columns": requested_columns,
                "unavailable_columns": unavailable_columns,
                "filters": numeric_filters,
                "group_by": group_by,
                "aggregate_function": "sum",
                "aggregate_column": threshold_metric,
                "result": result,
            }

    # --------------------------------------------------------
    # Group + aggregate.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # Temporal invoice-value ranking
    #
    # Highest/lowest invoice value month/year means the
    # SUM of InvoiceTotal for each period.
    # The ranking direction decides which period wins;
    # it must not change the within-period aggregation.
    # --------------------------------------------------------

    temporal_invoice_value_ranking = bool(
        time_grouping
        and re.search(
            r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
            question_norm,
            flags=re.IGNORECASE,
        )
        and re.search(
            r"\binvoice\s+(?:value|amount|total)\b"
            r"|\binvoicevalue\b"
            r"|\binvoiceamount\b"
            r"|\binvoicetotal\b",
            question_norm,
            flags=re.IGNORECASE,
        )
    )

    if temporal_invoice_value_ranking:
        invoice_total_column = _resolve_column(
            "InvoiceTotal",
            dataset,
            schema,
                    [],
        )

        if invoice_total_column:
            aggregate_function = "sum"
            aggregate_column = invoice_total_column

    # --------------------------------------------------------
    # Implicit grouped multi-metric queries.
    #
    # Examples:
    #   Show sales and profit quarter wise
    #   Show quantity and sales product wise
    #   Show invoice count and discount year wise
    #
    # These queries do not necessarily contain words such
    # as "total" or "sum", so _extract_multi_aggregate()
    # intentionally does not handle them.
    # --------------------------------------------------------

    implicit_group_metrics = []

    if group_by:
        implicit_group_metrics = (
            _extract_implicit_group_metrics(
                question,
                dataset,
                schema,
                filtered_rows,
            )
        )

    if (
        group_by
        and len(implicit_group_metrics) >= 2
    ):
        grouped_multi = _group_multi_metrics(
            filtered_rows,
            group_by,
            implicit_group_metrics,
            time_period=(
                time_grouping.get("period")
                if time_grouping
                else None
            ),
        )

        result = {
            "operation": "group_multi_aggregate",
            "group_by": group_by,
            "aggregate_function": "multi",
            "aggregate_column": None,
            "aggregate_metrics": implicit_group_metrics,
            "rows": grouped_multi,
            "count": len(grouped_multi),
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
            "aggregate_function": "multi",
            "aggregate_column": None,
            "result": result,
        }


    # --------------------------------------------------------
    # Explicit grouped multi-metric aggregate.
    #
    # Example:
    #   sales profit average last 3 months
    #
    # This must run before the single-metric grouped branch.
    # --------------------------------------------------------
    query_plan = state.get("query_plan") or {}

    explicit_multi_metrics = _extract_multi_aggregate(
        (
            query_plan.get("canonical_query")
            if isinstance(query_plan, dict)
            else None
        )
        or question,
        dataset,
        schema,
        filtered_rows,
    )

    if group_by and len(explicit_multi_metrics) >= 2:
        grouped_metrics = []

        sales_column = _resolve_column(
            "sales",
            dataset,
            schema,
            filtered_rows,
        )

        profit_column = _resolve_column(
            "profit",
            dataset,
            schema,
            filtered_rows,
        )

        for metric in explicit_multi_metrics:
            column = metric.get("column")
            function = metric.get("function")

            if not column or not function:
                continue

            if column == sales_column:
                metric_name = "sales"
            elif column == profit_column:
                metric_name = "profit"
            else:
                metric_name = _normalize_text(str(column))

            grouped_metrics.append(
                {
                    "metric": metric_name,
                    "function": function,
                    "column": column,
                }
            )

        if len(grouped_metrics) >= 2:
            grouped_multi = _group_multi_metrics(
                filtered_rows,
                group_by,
                grouped_metrics,
                time_period=(
                    time_grouping.get("period")
                    if time_grouping
                    else None
                ),
            )

            # Rename generic helper output according to the
            # requested aggregation function.
            for row in grouped_multi:
                for metric in grouped_metrics:
                    metric_name = metric["metric"]
                    function = metric["function"]

                    if metric_name == "sales":
                        old_name = "Total Sales"
                        base_name = "Sales"
                    elif metric_name == "profit":
                        old_name = "Total Profit"
                        base_name = "Profit"
                    else:
                        continue

                    if old_name in row:
                        if function == "average":
                            new_name = f"Average {base_name}"
                        elif function == "sum":
                            new_name = f"Total {base_name}"
                        elif function == "max":
                            new_name = f"Maximum {base_name}"
                        elif function == "min":
                            new_name = f"Minimum {base_name}"
                        else:
                            new_name = old_name

                        row[new_name] = row.pop(old_name)

            result = {
                "operation": "group_multi_aggregate",
                "group_by": group_by,
                "aggregate_function": "multi",
                "aggregate_column": None,
                "aggregate_metrics": grouped_metrics,
                "rows": grouped_multi,
                "count": len(grouped_multi),
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
                "aggregate_function": "multi",
                "aggregate_column": None,
                "result": result,
            }

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
                            .replace("?", "")
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

        if (
            (
                ranking_group_query
                or lowest_ranking_group_query
                or temporal_invoice_value_ranking
            )
            and not top_n
            and grouped
        ):
            if time_grouping and temporal_ranking_query:

                def _temporal_numeric_value(row):
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
                                .replace("?", "")
                                .replace("$", "")
                                .strip()
                            )
                        except (TypeError, ValueError):
                            continue

                    return 0.0

                temporal_lowest = bool(
                    re.search(
                        r"\b(?:lowest|minimum|bottom)\b|(?<!at )\bleast\b",
                        question,
                        re.IGNORECASE,
                    )
                )

                grouped.sort(
                    key=_temporal_numeric_value,
                    reverse=not temporal_lowest,
                )
                

            grouped = grouped[:1]

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
    # EXPLICIT PROJECTION VS VALID PLANNER AGGREGATE
    #
    # A valid planner aggregate is authoritative.
    # Do not let inferred requested columns such as:
    #   Profit, Month
    # turn a semantic query like:
    #   latest month profit
    # into a raw-row projection.
    #
    # Explicit projection still wins for genuine requests such
    # as:
    #   show Profit and Month
    # --------------------------------------------------------

    planner_plan = state.get("query_plan") or {}

    planner_is_aggregate = bool(
        isinstance(planner_plan, dict)
        and planner_plan.get("status") == "OK"
        and planner_plan.get("operation") == "aggregate"
        and planner_plan.get("aggregate_function")
        and planner_plan.get("aggregate_column")
    )

    explicit_projection = (
        len(requested_columns) >= 2
        and not planner_is_aggregate
    )

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

    # Use the planner's canonical query for multi-metric extraction.
    # The original user wording may be shorthand such as:
    #   "sales profit average last 3 months"
    # while the planner normalizes it to:
    #   "Show average sales and average profit for the last 3 months"

    multi_aggregate_question = question

    if isinstance(query_plan, dict):
        multi_aggregate_question = (
            query_plan.get("canonical_query")
            or question
        )

    multi_aggregates = _extract_multi_aggregate(
        multi_aggregate_question,
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
            result["rows"] = []

    else:
        # No aggregate was detected.
        # Explicit requested columns must be projected.
        if requested_columns:
            result_rows = _project_rows(
                filtered_rows,
                requested_columns,
            )
        else:
            result_rows = filtered_rows

        result = {
            "operation": "rows",
            "rows": result_rows,
            "count": len(result_rows),
            "source_rows": len(rows),
            "filtered_rows": original_filtered_row_count,
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
        "rows": result.get("rows", []),
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
                    [],
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
                    [],
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
# BUILD DYNAMIC CHART
# ============================================================

def build_dynamic_chart(
    state: DynamicAgentState,
) -> DynamicAgentState:
    """
    Convert an existing dynamic query result into chart
    configuration.

    This function does NOT execute another query and does
    NOT modify the existing query engine.
    """

    question = state.get(
        "question",
        "",
    )

    result = state.get(
        "result",
        {},
    )

    if not isinstance(result, dict):
        return {
            **state,
            "chart": {
                "enabled": False,
                "reason": "Invalid query result.",
            },
        }

    result_rows = result.get(
        "rows",
        [],
    )

    if not isinstance(result_rows, list):
        result_rows = []

    # --------------------------------------------------------
    # No usable rows -> no chart
    # --------------------------------------------------------

    if not result_rows:
        return {
            **state,
            "chart": {
                "enabled": False,
                "reason": "No chartable rows found.",
            },
        }

    # --------------------------------------------------------
    # Import here to avoid unnecessary import coupling.
    # --------------------------------------------------------

    try:
        from services.chart_service import (
            build_chart_config,
        )
    except Exception as exc:
        return {
            **state,
            "chart": {
                "enabled": False,
                "reason": f"Chart service unavailable: {exc}",
            },
        }

    # --------------------------------------------------------
    # Build chart from existing query result.
    # --------------------------------------------------------

    try:
        chart_config = build_chart_config(
            question,
            result_rows,
        )

    except Exception as exc:
        chart_config = {
            "enabled": False,
            "reason": f"Chart generation failed: {exc}",
        }

    return {
        **state,
        "chart": chart_config,
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

    display_rows = rows

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
    return "\n".join(lines)

# ============================================================
# GPT-STYLE ANSWER HELPERS
# ============================================================

def _format_inr(value: Any) -> str:
    """
    Format numeric values as Indian Rupees.
    Example:
        857886.23 -> ?8,57,886.23
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    sign = "-" if number < 0 else ""
    number = abs(number)

    formatted = f"{number:,.2f}"

    return f"{sign}\u20b9{formatted}"


def _human_metric_name(column: str) -> str:
    normalized = str(column).strip().lower()
    normalized = normalized.replace("_", "")
    normalized = normalized.replace(" ", "")

    if "invoicetotal" in normalized:
        return "sales"

    if "totalamount" in normalized:
        return "sales"

    if "profit" in normalized:
        return "profit"

    if "totalgst" in normalized:
        return "GST"

    if normalized == "cgst":
        return "CGST"

    if normalized == "sgst":
        return "SGST"

    if normalized == "igst":
        return "IGST"

    if "discountamt" in normalized:
        return "discount"

    if "taxableamount" in normalized:
        return "taxable amount"

    if normalized == "cost":
        return "cost"

    if normalized == "qty":
        return "quantity"

    if "unitprice" in normalized:
        return "unit price"

    if "grossamount" in normalized:
        return "gross sales"

    return str(column).replace(
        "_",
        " ",
    ).lower()


def _human_entity_name(column: str) -> str:
    mapping = {
        "PartyName": "customers",
        "Customer": "customers",
        "Product": "products",
        "PaymentMode": "payment modes",
        "Category": "categories",
        "PartyState": "states",
        "state": "states",
        "HSN_Code": "HSN codes",
        "GST_Rate": "GST rates",
        "Month": "months",
        "Date": "dates",
    }

    return mapping.get(
        column,
        str(column).replace("_", " ").lower(),
    )


def _grouped_result_metric_column(
    result_rows: List[Dict[str, Any]],
    group_by: Optional[str] = None,
) -> Optional[str]:
    """
    Find the numeric aggregate column from grouped results.
    """
    if not result_rows:
        return None

    preferred = [
        "InvoiceTotal",
        "TotalAmount",
        "Profit",
        "TotalGST",
        "CGST",
        "SGST",
        "IGST",
        "DiscountAmt",
        "TaxableAmount",
        "Cost",
        "Qty",
        "UnitPrice",
        "GrossAmount",
    ]

    columns = list(result_rows[0].keys())

    for column in preferred:
        if column in columns:
            return column

    for column in columns:
        if column == group_by:
            continue

        values = [
            row.get(column)
            for row in result_rows
        ]

        numeric_count = 0

        for value in values:
            try:
                float(value)
                numeric_count += 1
            except (TypeError, ValueError):
                pass

        if numeric_count > 0:
            return column

    return None


def _format_grouped_gpt_answer(
    result_rows: List[Dict[str, Any]],
    group_by: str,
    question: str = "",
) -> str:
    """
    Convert grouped database output into a concise GPT-style answer.
    print("[DEBUG GROUP FORMAT] group_by=", repr(group_by), "question=", repr(question))
    """

    entity_name = _human_entity_name(group_by)

    # Use the requested time period for temporal ranking output.
    if group_by == "Date":
        question_for_entity = _normalize_text(question)

        if re.search(
            r"\b(?:month|months|monthly)\b",
            question_for_entity,
        ):
            entity_name = "months"

        elif re.search(
            r"\b(?:quarter|quarters|quarterly)\b",
            question_for_entity,
        ):
            entity_name = "quarters"

        elif re.search(
            r"\b(?:year|years|yearly|annual|annually)\b",
            question_for_entity,
        ):
            entity_name = "years"

    singular_entity_map = {
        "customers": "customer",
        "products": "product",
        "payment modes": "payment mode",
        "categories": "category",
        "states": "state",
        "HSN codes": "HSN code",
        "months": "month",
        "dates": "date",
    }

    singular_entity = singular_entity_map.get(
        entity_name,
        entity_name,
    )

    if not result_rows:
        return f"No matching {entity_name} were found."

    metric_column = _grouped_result_metric_column(
        result_rows,
        group_by,
    )

    # Keep the actual result column separate from the
    # semantic metric requested by the user.
    result_metric_column = metric_column
    display_metric_column = metric_column

    question_norm = _normalize_text(question)

    requested_metric_map = [
        (
            r"\b(?:unit\s+price|unitprice|price)\b",
            "UnitPrice",
        ),
        (
            r"\b(?:taxable\s+amount|taxableamount|taxable)\b",
            "TaxableAmount",
        ),
        (
            r"\bgross(?:\s+amount|amount)?\b",
            "GrossAmount",
        ),
        (
            r"\bcgst\b",
            "CGST",
        ),
        (
            r"\bsgst\b",
            "SGST",
        ),
        (
            r"\bigst\b",
            "IGST",
        ),
        (
            r"\b(?:total\s+gst|totalgst|gst)\b",
            "TotalGST",
        ),
        (
            r"\bdiscount\b",
            "DiscountAmt",
        ),
        (
            r"\bcost\b",
            "Cost",
        ),
        (
            r"\b(?:quantity|qty)\b",
            "Qty",
        ),
        (
            r"\bprofit\b",
            "Profit",
        ),
    ]

    requested_metric = None

    for metric_pattern, metric_column_name in requested_metric_map:
        if re.search(metric_pattern, question_norm):
            requested_metric = metric_column_name
            break

    # Use the requested metric for DISPLAY.
    # Keep the actual result column for reading values.
    if requested_metric:
        display_metric_column = requested_metric

        if requested_metric in result_rows[0]:
            result_metric_column = requested_metric

    if not metric_column:
        entity_phrase = (
            singular_entity
            if len(result_rows) == 1
            else entity_name
        )

        verb = "was" if len(result_rows) == 1 else "were"

        return (
            f"{len(result_rows)} {entity_phrase} "
            f"{verb} found matching your request."
        )

    metric_name = _human_metric_name(display_metric_column)


    question_lower = question.lower()

    is_quantity = metric_column in ("Qty", "Quantity", "TotalQty")
    is_quantity = is_quantity or metric_name.lower() in (
        "quantity",
        "qty",
        "total qty",
    )

    is_count = (
        str(metric_column).strip().lower()
        in ("count", "invoice count", "count of invoices")
        or str(result_metric_column).strip().lower()
        in ("count", "invoice count", "count of invoices")
        or str(display_metric_column).strip().lower()
        in ("count", "invoice count", "count of invoices")
        or bool(
            re.search(
                r"\b(?:invoice\s+count|invoice\s+counts|"
                r"count\s+(?:of\s+)?invoices?|"
                r"number\s+of\s+invoices?|"
                r"how\s+many\s+invoices?)\b",
                question_norm,
                flags=re.IGNORECASE,
            )
        )
)
    is_quantity = is_quantity or metric_name.lower() in ("quantity", "qty", "total qty")

    metric_label = (
        "quantity"
        if is_quantity
        else metric_name
    )

    # --------------------------------------------------------
    # Invoice-value temporal ranking label
    #
    # InvoiceTotal is displayed as "invoice value" for
    # highest/lowest month/year/quarter questions.
    # Keep the existing "sales" label for generic sales
    # queries.
    # --------------------------------------------------------

    if (
        display_metric_column == "InvoiceTotal"
        and re.search(
            r"\binvoice\s+(?:value|amount|total)\b"
            r"|\binvoicevalue\b"
            r"|\binvoiceamount\b"
            r"|\binvoicetotal\b",
            question_lower,
            flags=re.IGNORECASE,
        )
    ):
        metric_label = "invoice value"
    # --------------------------------------------------------
    # TEMPORAL RANKING FORMAT
    # Convert grouped Date results into natural month/year/
    # quarter answers instead of "Top 1 date by ...".
    # --------------------------------------------------------

    temporal_period = None

    if re.search(
        r"\b(?:month|months|monthly)\b",
        question_lower,
    ):
        temporal_period = "month"

    elif re.search(
        r"\b(?:quarter|quarters|quarterly)\b",
        question_lower,
    ):
        temporal_period = "quarter"

    elif re.search(
        r"\b(?:year|years|yearly|annual|annually)\b",
        question_lower,
    ):
        temporal_period = "year"

    temporal_highest = bool(
        re.search(
            r"\b(?:highest|maximum|most|top)\b",
            question_lower,
        )
    )

    temporal_lowest = bool(
        re.search(
            r"\b(?:lowest|minimum|least|bottom)\b",
            question_lower,
        )
    )

    if (
        group_by == "Date"
        and temporal_period
        and (temporal_highest or temporal_lowest)
        and len(result_rows) == 1
    ):
        period_value = result_rows[0].get(
            group_by,
            "",
        )

        # Format YYYY-MM as "August 2025"
        if temporal_period == "month":
            try:
                year, month = str(
                    period_value
                ).split("-")

                month_names = [
                    "",
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ]

                period_value = (
                    f"{month_names[int(month)]} {year}"
                )
            except Exception:
                pass

        # Format YYYY-Qn as "Q4 2025"
        elif temporal_period == "quarter":
            try:
                year, quarter = str(
                    period_value
                ).split("-Q")

                period_value = (
                    f"Q{quarter} {year}"
                )
            except Exception:
                pass

        # Format YYYY as "2025"
        elif temporal_period == "year":
            period_value = str(
                period_value
            )

        metric_value = result_rows[0].get(
            result_metric_column,
            "",
        )

        try:
            numeric_value = float(
                str(metric_value).replace(",", "")
            )

            if is_count:
                formatted_value = f"{int(numeric_value):,}"

            elif is_quantity:
                if numeric_value.is_integer():
                    formatted_value = (
                        f"{int(numeric_value):,}"
                    )
                else:
                    formatted_value = (
                        f"{numeric_value:,.2f}"
                    )

            else:
                formatted_value = _format_inr(
                    numeric_value
                )

        except Exception:
            formatted_value = str(metric_value)
        ranking_word = (
            "highest"
            if temporal_highest
            else "lowest"
        )

        return (
            f"{period_value} had the "
            f"{ranking_word} "
            f"{metric_label} with "
            f"{formatted_value}."
        )

    def format_threshold(value):
        try:
            number = float(
                str(value).replace(",", "")
            )

            if is_quantity:
                if number.is_integer():
                    return f"{int(number):,}"
                return f"{number:,.2f}"

            if number.is_integer():
                return f"?{int(number):,}"

            return _format_inr(number)

        except Exception:
            return str(value)

    between_match = re.search(
        r"\bbetween\s+"
        r"(?:\u20b9|rs\.?|inr)?\s*"
        r"([\d,]+(?:\.\d+)?)"
        r"\s+and\s+"
        r"(?:\u20b9|rs\.?|inr)?\s*"
        r"([\d,]+(?:\.\d+)?)",
        question,
        flags=re.IGNORECASE,
    )

    threshold_match = re.search(
        r"(?:\u20b9|rs\.?|inr)?\s*"
        r"([\d,]+(?:\.\d+)?)",
        question,
        flags=re.IGNORECASE,
    )

    threshold_text = ""

    if between_match:
        low_value = format_threshold(
            between_match.group(1)
        )
        high_value = format_threshold(
            between_match.group(2)
        )

        threshold_text = (
            f"{low_value} and {high_value}"
        )

    elif threshold_match:
        threshold_text = format_threshold(
            threshold_match.group(1)
        )

    if "at least" in question_lower:
        condition_text = "of at least"
    elif "at most" in question_lower:
        condition_text = "of at most"
    elif "above" in question_lower:
        condition_text = "above"
    elif "below" in question_lower:
        condition_text = "below"
    elif "between" in question_lower:
        condition_text = "between"
    else:
        condition_text = ""

    entity_phrase = (
        singular_entity
        if len(result_rows) == 1
        else entity_name
    )

    verb = "has" if len(result_rows) == 1 else "have"

    if condition_text and threshold_text:
        if condition_text == "between":
            intro = (
                f"{len(result_rows)} {entity_phrase} {verb} "
                f"{metric_label} between "
                f"{threshold_text}:"
            )
        else:
            intro = (
                f"{len(result_rows)} {entity_phrase} {verb} "
                f"{metric_label} {condition_text} "
                f"{threshold_text}:"
            )
    elif condition_text:
        intro = (
            f"{len(result_rows)} {entity_phrase} {verb} "
            f"{metric_label} {condition_text}:"
        )
    else:
        is_highest_request = bool(
            re.search(
                r"\b(?:highest|maximum|top)\b",
                question_lower,
            )
        )

        is_lowest_request = bool(
            re.search(
                r"\b(?:lowest|minimum|bottom)\b",
                question_lower,
            )
        )

        if is_highest_request:
            intro = (
                f"Top {len(result_rows)} {entity_phrase} by "
                f"{metric_label}:"
            )
        elif is_lowest_request:
            intro = (
                f"Bottom {len(result_rows)} {entity_phrase} by "
                f"{metric_label}:"
            )
        else:
            intro = (
                f"{metric_label.capitalize()} by "
                f"{entity_name}:"
            )

    lines = [intro, ""]

    for row in result_rows:
        entity_value = row.get(
            group_by,
            "",
        )

        metric_value = row.get(
            result_metric_column,
            "",
        )

        if metric_value in (None, ""):
            continue

        try:
            if is_count:
                formatted_value = f"{int(float(metric_value)):,}"

            elif is_quantity:
                numeric_value = float(
                    metric_value
                )

                if numeric_value.is_integer():
                    formatted_value = (
                        f"{int(numeric_value):,}"
                    )
                else:
                    formatted_value = (
                        f"{numeric_value:,.2f}"
                    )

            else:
                formatted_value = _format_inr(
                    metric_value
                )

        except Exception:
            formatted_value = str(metric_value)

        lines.append(
            f"- {entity_value} - {formatted_value}"
        )

    return "\n".join(lines)


# NODE 5 - ANSWER GENERATION
# ============================================================

def generate_dynamic_answer(
    state: DynamicAgentState,
) -> DynamicAgentState:
    time_grouping = None
    temporal_ranking_query = False
    answer_lines = []
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
    # TEMPORAL RANKING ANSWER
    # Handle month/year/quarter ranking before any generic
    # top-N formatter can overwrite the answer.
    # --------------------------------------------------------

    if (
        result.get("operation") == "top_n_rows"
        and result_rows
    ):
        temporal_grouping = _extract_time_grouping(
            question,
            dataset,
            state.get("schema", []),
            result_rows,
        )

        temporal_query = bool(
            temporal_grouping
            and re.search(
                r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
                question,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
                question,
                re.IGNORECASE,
            )
        )

        if temporal_query:
            ranking_column = result.get(
                "ranking_column"
            )

            ranking_direction = result.get(
                "ranking_direction",
                "desc",
            )

            selected_row = result_rows[0]

            period_column = temporal_grouping.get(
                "column"
            )

            period = temporal_grouping.get(
                "period",
                "period",
            )

            period_value = selected_row.get(
                period_column,
                "Unknown",
            )

            # Friendly period name
            if period == "month":
                try:
                    year, month = str(
                        period_value
                    ).split("-")

                    month_names = [
                        "",
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ]

                    period_value = (
                        f"{month_names[int(month)]} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "quarter":
                try:
                    year, quarter = str(
                        period_value
                    ).split("-Q")

                    period_value = (
                        f"Q{quarter} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "year":
                period_value = str(
                    period_value
                )

            # Friendly metric name
            if re.search(
                r"\b(?:quantity|qty)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "quantity"

            elif re.search(
                r"\b(?:taxable|taxable\s+amount|taxableamount)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "taxable amount"

            elif re.search(
                r"\bdiscount\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "discount"

            elif re.search(
                r"\bprofit\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "profit"

            elif re.search(
                r"\b(?:gst|totalgst|total\s+gst)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "GST"

            else:
                metric_name = "sales"

            ranking_word = (
                "highest"
                if ranking_direction != "asc"
                else "lowest"
            )

            selected_value = selected_row.get(
                ranking_column
            )

            if metric_name == "quantity":
                try:
                    formatted_value = (
                        f"{float(selected_value):,.0f}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    formatted_value = str(
                        selected_value
                    )
            else:
                formatted_value = _format_inr(
                    selected_value
                )

            return {
                **state,
                "answer": (
                    f"{period_value} had the "
                    f"{ranking_word} "
                    f"{metric_name} with "
                    f"{formatted_value}."
                ),
                "result": result,
                "error": None,
            }  
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

        difference = result.get("difference")

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
        # Determine the metric being compared.
        # ----------------------------------------------------

        metric_name = (
            result.get("metric_label")
            or result.get("metric")
            or result.get("measure")
            or result.get("field")
            or result.get("column")
            or "Sales"
        )

        metric_text = str(metric_name).strip()

        # Normalize common metric names.
        metric_lower = metric_text.lower()

        if "profit" in metric_lower:
            metric_text = "Profit"
        elif "gst" in metric_lower:
            metric_text = "GST"
        elif "discount" in metric_lower:
            metric_text = "Discount"
        elif "sales" in metric_lower or "amount" in metric_lower:
            metric_text = "Sales"

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
                f"{metric_text} period comparison:\n\n"
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

        difference_value = float(difference or 0)

        difference_text = (
            f"\u20b9{abs(difference_value):,.2f}"
        )

        if percentage_change is not None:
            percentage_text = (
                f"{abs(float(percentage_change)):.2f}%"
            )
        else:
            percentage_text = "N/A"

        # ----------------------------------------------------
        # period_1 = older period
        # period_2 = newer period
        #
        # Therefore:
        #   period_1 -> period_2
        # is the chronological direction.
        # ----------------------------------------------------

        if difference_value > 0:
            change_word = "increased"
        elif difference_value < 0:
            change_word = "decreased"
        else:
            change_word = "remained unchanged"

        if difference_value == 0:
            change_sentence = (
                f"{metric_text} remained unchanged between "
                f"{period_2} and {period_1}."
            )
        else:
            change_sentence = (
                f"{metric_text} {change_word} by "
                f"{difference_text} "
                f"({percentage_text}) from "
                f"{period_1} to {period_2}."
            )

        answer = (
            f"{metric_text} period comparison:\n\n"
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
                "GrossAmount",
            }:
                metric_name = "Sales"

            elif column == "Profit":
                metric_name = "Profit"

            elif column in {"Qty", "Quantity"}:
                metric_name = "Quantity"

            elif column in {"GST", "TotalGST"}:
                metric_name = "GST"

            elif column == "Discount":
                metric_name = "Discount"

            elif column == "InvoiceTotal":
                metric_name = "Invoice Value"

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
            f"Distinct values in `{distinct_column}`\n\n"
            f"Found {len(value_items)} distinct values."
        )

        if value_items:
            answer += "\n\n"

            for value, frequency in value_items:
                answer += (
                    f"- {value} ? {frequency} record"
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
            f"{distinct_value:,} unique "
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
        # Universal SQL fast-path aggregate formatter.
        # Keep SQL results consistent with universal aggregates.
        # ----------------------------------------------------

        metric_label = str(
            column or "value"
        ).strip()

        metric_label_map = {
            "GrossAmount": "sales",
            "Profit": "profit",
            "Qty": "quantity",
            "DiscountAmt": "discount",
            "TotalGST": "GST",
            "CGST": "CGST",
            "SGST": "SGST",
            "IGST": "IGST",
            "TaxableAmount": "taxable amount",
            "Cost": "cost",
            "UnitPrice": "unit price",
            "InvoiceTotal": "invoice total",
        }

        metric_label = metric_label_map.get(
            str(column),
            metric_label,
        )
        financial_metrics = {
            "sales",
            "profit",
            "discount",
            "gst",
            "cgst",
            "sgst",
            "igst",
            "taxable amount",
            "cost",
            "unit price",
            "invoice total",
        }


        if value is None and not column:
            answer = "Information is not available in the uploaded data."
            return {
                **state,
                "answer": answer,
            }

        if value is None:
            formatted_value = "N/A"

        elif metric_label.lower() in financial_metrics:
            try:
                formatted_value = _format_inr(value)
            except Exception:
                try:
                    formatted_value = f"?{float(value):,.2f}"
                except (TypeError, ValueError):
                    formatted_value = str(value)

        else:
            try:
                formatted_value = f"{float(value):,.2f}"
            except (TypeError, ValueError):
                formatted_value = str(value)

        operation_label_map = {
            "sum": "Total",
            "average": "Average",
            "max": "Maximum",
            "min": "Minimum",
        }
        operation_label = operation_label_map.get(
            function,
            str(function).capitalize(),
        )

        

        answer = (
            f"{operation_label} "
            f"{metric_label}: "
            f"{formatted_value}"
        )

        # SQL fast-path non-sales aggregates can return now.
        if not (str(metric_label).lower() == "sales" and function == "sum"):
            if filters:
                answer += "\n\nFilters Applied\n"
                answer += "\n".join(
                    f"- {_describe_filter(item)}"
                    for item in filters
                )

            return {
                **state,
                "answer": answer,
                "result": result,
                "error": None,
            }

        # ----------------------------------------------------
        # Business-friendly sales summary.
        # ----------------------------------------------------

        question_norm = _normalize_text(
            question
        )

        sales_query = bool(
            re.search(
                r"\b(?:sales?|selling|revenue|billing|turnover|business|"
                r"business\s+value|business\s+amount|sales\s+value|"
                r"selling\s+value|business\s+done)\b",
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
                "SALES SUMMARY\n\n"
                f"Total Sales: "
                f"{formatted_value}"
            )

            # ------------------------------------------------
            # Add filter context.
            # ------------------------------------------------

            if filters:

                answer += (
                    "\n\n"
                    "Filters Applied\n"
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
                        f"Total Invoices: "
                        f"{invoice_count}"
                    )

                if customer_count is not None:
                    answer += (
                        "\n"
                        f"Total Customers: "
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
                        f"Total Invoices: "
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
                        f"Total Customers: "
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
                f"of '{column}' is {value}."
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
                    f"'{column}' is {value}."
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
                    f"is {value}."
                )

        else:
            answer = (
                f"{function.title()} of '{column}' "
                f"is {value}."
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
            f"{employee_id} Attendance",
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
                f"Total Days: {total_days}",
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
                r"\b(?:highest|maximum|top)\b|(?<!at )\bmost\b",
                question_norm,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst|discount|invoice\s+value|invoice\s+amount|invoice\s+total)\b",
                question_norm,
            )
        )

        lowest_ranking_query = bool(
            group_by
            and re.search(
                r"\b(?:lowest|minimum|bottom)\b|(?<!at )\bleast\b",
                question_norm,
            )
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst|discount|invoice\s+value|invoice\s+amount|invoice\s+total)\b",
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
            r"suppliers?|vendors?|payment\s+modes?|payment\s+methods?|"
            r"invoices?|transactions?|records?|"
            r"months?|years?|quarters?)"
            r".*?\b(highest|lowest|maximum|minimum|most|least)\b",
            question_norm,
            flags=re.IGNORECASE,
        )

        if (
            top_n_match
            and group_by
            and re.search(
                r"\b(?:sales?|revenue|billing|turnover|profit|gst|totalgst|total\s+gst|discount|invoice\s+value|invoice\s+amount|invoice\s+total)\b",
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
                            .replace("?", "")
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
            # Top N    ? highest to lowest
            # Bottom N ? lowest to highest
            # ------------------------------------------------

            ranking_rows.sort(
                key=lambda item: item[0],
                reverse=(
                    ranking_word == "top"
                ),
            )

            # "Which month/year/quarter had highest/lowest ..."
            # asks for one winning period, not a Top-N list.
            ranking_limit = (
                1
                if (
                    locals().get("time_grouping")
                    and locals().get("temporal_ranking_query")
                )
                else top_n_value
            )

            ranking_rows = ranking_rows[
                :ranking_limit
            ]

            entity_label = group_by

            if re.search(
                r"\b(?:customer|customers)\b",
                question_norm,
            ):
                entity_label = "customers"

            elif re.search(
                r"\b(?:product|products|item|items)\b",
                question_norm,
            ):
                entity_label = "products"

            elif re.search(
                r"\b(?:payment\s+mode|payment\s+modes|payment\s+method|payment\s+methods)\b",
                question_norm,
            ):
                entity_label = "payment modes"

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
                    "payment mode",
                    "payment modes",
                    "payment method",
                    "payment methods",
                ):
                    entity_label = "payment modes"

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

            if time_grouping and temporal_ranking_query:
                period_label = time_grouping.get(
                    "period",
                    "period",
                )

                if ranking_rows:
                    selected_value, selected_row = ranking_rows[0]

                    period_value = selected_row.get(
                        group_by,
                        "Unknown",
                    )

                    if period_label == "month":
                        try:
                            year, month = str(
                                period_value
                            ).split("-")

                            month_names = [
                                "",
                                "January",
                                "February",
                                "March",
                                "April",
                                "May",
                                "June",
                                "July",
                                "August",
                                "September",
                                "October",
                                "November",
                                "December",
                            ]

                            period_value = (
                                f"{month_names[int(month)]} {year}"
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            pass

                    elif period_label == "quarter":
                        try:
                            year, quarter = str(
                                period_value
                            ).split("-Q")

                            period_value = (
                                f"Q{quarter} {year}"
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            pass

                    elif period_label == "year":
                        period_value = str(
                            period_value
                        )

                    metric_for_temporal = (
                        "GST"
                        if re.search(
                            r"\b(?:gst|totalgst|total\s+gst)\b",
                            question_norm,
                        )
                        else (
                            "profit"
                            if re.search(
                                r"\bprofit\b",
                                question_norm,
                            )
                            else (
                                "discount"
                                if re.search(
                                    r"\bdiscount\b",
                                    question_norm,
                                )
                                else (
                                    "quantity"
                                    if re.search(
                                        r"\b(?:quantity|qty)\b",
                                        question_norm,
                                    )
                                    else (
                                        "taxable amount"
                                        if re.search(
                                            r"\b(?:taxable|taxable\s+amount|taxableamount)\b",
                                            question_norm,
                                        )
                                        else "sales"
                                    )
                                )
                            )
                        )
                    )

                    ranking_word_label = (
                        "highest"
                        if ranking_label == "Top"
                        else "lowest"
                    )

                    formatted_value = _format_inr(
                        selected_value
                    )

                    return {
                        **state,
                        "answer": (
                            f"{period_value} had the "
                            f"{ranking_word_label} "
                            f"{metric_for_temporal} "
                            f"with {formatted_value}."
                        ),
                    }
            metric_for_ranking = (
                "GST"
                if re.search(r"\b(?:gst|totalgst|total\s+gst)\b", question_norm)
                else (
                    "profit"
                    if re.search(r"\bprofit\b", question_norm)
                    else (
                        "discount"
                        if re.search(r"\bdiscount\b", question_norm)
                        else (
                            "quantity"
                            if re.search(r"\b(?:quantity|qty)\b", question_norm)
                            else (
                                "taxable amount"
                                if re.search(r"\b(?:taxable|taxable\s+amount|taxableamount)\b", question_norm)
                                else (
                                    "cost"
                                    if re.search(r"\bcost\b", question_norm)
                                    else (
                                        "gross amount"
                                        if re.search(r"\b(?:gross|gross\s+amount|grossamount)\b", question_norm)
                                        else (
                                            "CGST"
                                            if re.search(r"\bcgst\b", question_norm)
                                            else (
                                                "SGST"
                                                if re.search(r"\bsgst\b", question_norm)
                                                else (
                                                    "IGST"
                                                    if re.search(r"\bigst\b", question_norm)
                                                    else (
                                                        "unit price"
                                                        if re.search(r"\b(?:unit\s+price|unitprice|price)\b", question_norm)
                                                        else "sales"
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )

            # Temporal ranking questions such as
            # "Which quarter had highest taxable amount?"
            # should return only the winning period, not every period.
            if time_grouping and temporal_ranking_query and ranking_rows:
                ranking_rows = ranking_rows[:1]

            if time_grouping and temporal_ranking_query and ranking_rows:
                selected_value, selected_row = ranking_rows[0]

                period_value = selected_row.get(
                    group_by,
                    "Unknown",
                )

                period = time_grouping.get(
                    "period",
                    "period",
                )

                if period == "month":
                    try:
                        year, month = str(
                            period_value
                        ).split("-")

                        month_names = [
                            "",
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        ]

                        period_value = (
                            f"{month_names[int(month)]} {year}"
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

                elif period == "quarter":
                    period_text = str(period_value)

                    if "-Q" in period_text:
                        year, quarter = period_text.split(
                            "-Q",
                            1,
                        )
                        period_value = (
                            f"Q{quarter} {year}"
                        )

                formatted_value = _format_inr(
                    selected_value
                )

                article = "an" if metric_for_ranking == "IGST" else "a"

                answer = (
                    f"{period_value} had the "
                    f"{ranking_label.lower()} "
                    f"{metric_for_ranking} with "
                    f"{formatted_value}."
                )

                return {
                    **state,
                    "answer": answer,
                }

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

                formatted_value = _format_inr(
                    row_value
                )

                answer_lines.append(
                    f"{index}. {group_value} - "
                    f"{formatted_value}"
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
                            .replace("?", "")
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
                _format_inr(selected_value)
            )

            if re.search(
                r"\bprofit\b",
                question_norm,
            ):
                metric_label = "profit"
            elif re.search(
                r"\b(?:gst|totalgst|total\s+gst)\b",
                question_norm,
            ):
                metric_label = "GST"
            elif re.search(
                r"\bdiscount\b",
                question_norm,
            ):
                metric_label = "discount"
            elif re.search(
                r"\b(?:quantity|qty)\b",
                question_norm,
            ):
                metric_label = "quantity"
            elif re.search(
                r"\b(?:taxable|taxable\s+amount|taxableamount)\b",
                question_norm,
            ):
                metric_label = "taxable amount"
            elif re.search(
                r"\bcost\b",
                question_norm,
            ):
                metric_label = "cost"
            elif re.search(
                r"\b(?:gross|gross\s+amount|grossamount)\b",
                question_norm,
            ):
                metric_label = "gross amount"
            elif re.search(
                r"\bcgst\b",
                question_norm,
            ):
                metric_label = "CGST"
            elif re.search(
                r"\bsgst\b",
                question_norm,
            ):
                metric_label = "SGST"
            elif re.search(
                r"\bigst\b",
                question_norm,
            ):
                metric_label = "IGST"
            elif re.search(
                r"\b(?:unit\s+price|unitprice|price)\b",
                question_norm,
            ):
                metric_label = "unit price"
            elif re.search(
                r"\binvoice\s+(?:value|amount|total)\b"
                r"|\binvoicevalue\b"
                r"|\binvoiceamount\b"
                r"|\binvoicetotal\b",
                question_norm,
                flags=re.IGNORECASE,
            ):
                metric_label = "invoice value"
            else:
                metric_label = "sales"
                           

            answer = (
                f"{group_value} has the "
                f"{ranking_label} {metric_label} with "
                f"{formatted_value}."
            )

            return {
                **state,
                "answer": answer,
            }

        # ----------------------------------------------------
        # Normal grouped result.
        # ----------------------------------------------------

        # ----------------------------------------------------
        # GPT-STYLE GROUPED RESULT
        # ----------------------------------------------------

        group_labels = {
            "PartyName": "customers",
            "Customer": "customers",
            "Product": "products",
            "PaymentMode": "payment modes",
            "Category": "categories",
            "PartyState": "states",
            "state": "states",
            "HSN_Code": "HSN codes",
        }

        entity_label = group_labels.get(
            group_by,
            str(group_by).replace("_", " "),
        )

        if not result_rows:
            answer = (
                f"No matching {entity_label} were found."
            )
        else:
            answer = _format_grouped_gpt_answer(
                result_rows=result_rows,
                group_by=group_by,
                question=question,
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
    # GPT-STYLE TOP-N ROW RANKING ANSWER
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
        # ----------------------------------------------------
        # TEMPORAL RANKING: return immediately before the
        # generic Top-N row formatter can overwrite the answer.
        # ----------------------------------------------------
        
        schema = get_dataset_schema(
            dataset.get("id")
        )
        
        temporal_grouping = _extract_time_grouping(
            question,
            dataset,
            schema,
            result_rows,
        )

        temporal_query = bool(
            temporal_grouping
            and re.search(
                r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
                question,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
                question,
                re.IGNORECASE,
            )
        )

        if temporal_query and result_rows:
            ranking_column = result.get(
                "ranking_column"
            )

            ranking_direction = result.get(
                "ranking_direction",
                "desc",
            )

            selected_row = result_rows[0]

            period_column = temporal_grouping.get(
                "column"
            )

            period = temporal_grouping.get(
                "period",
                "period",
            )

            period_value = selected_row.get(
                period_column
            )

            # Friendly period name
            if period == "month":
                try:
                    year, month = str(
                        period_value
                    ).split("-")

                    month_names = [
                        "",
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ]

                    period_value = (
                        f"{month_names[int(month)]} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "quarter":
                try:
                    year, quarter = str(
                        period_value
                    ).split("-Q")

                    period_value = (
                        f"Q{quarter} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "year":
                period_value = str(
                    period_value
                )

            # Friendly metric name
            if re.search(
                r"\b(?:quantity|qty)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "quantity"

            elif re.search(
                r"\b(?:taxable|taxable\s+amount|taxableamount)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "taxable amount"

            elif re.search(
                r"\bdiscount\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "discount"

            elif re.search(
                r"\bprofit\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "profit"

            elif re.search(
                r"\b(?:gst|totalgst|total\s+gst)\b",
                question,
                re.IGNORECASE,
            ):
                metric_name = "GST"

            else:
                metric_name = "sales"

            ranking_word = (
                "highest"
                if ranking_direction != "asc"
                else "lowest"
            )

            selected_value = selected_row.get(
                ranking_column
            )

            if metric_name == "quantity":
                try:
                    formatted_value = (
                        f"{float(selected_value):,.0f}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    formatted_value = str(
                        selected_value
                    )
            else:
                formatted_value = _format_inr(
                    selected_value
                )

            return {
                **state,
                "answer": (
                    f"{period_value} had the "
                    f"{ranking_word} "
                    f"{metric_name} with "
                    f"{formatted_value}."
                ),
            }
        if ranking_direction == "asc":
            ranking_label = "lowest"
        else:
            ranking_label = "highest"

        ranking_metric = _human_metric_name(
            ranking_column
        )

        question_norm = _normalize_text(
            question
        )

        # ----------------------------------------------------
        # Determine the row/entity name.
        # ----------------------------------------------------

        entity_column = None
        entity_label = "records"

        if re.search(
            r"\b(?:invoice|invoices)\b",
            question_norm,
        ):
            entity_candidates = [
                "InvoiceNo",
                "Invoice No",
                "Invoice Number",
                "InvoiceNumber",
            ]

            entity_label = "invoices"

        elif re.search(
            r"\b(?:transaction|transactions)\b",
            question_norm,
        ):
            entity_candidates = [
                "InvoiceNo",
                "Invoice No",
                "TransactionNo",
                "Transaction No",
                "TransactionNumber",
            ]

            entity_label = "transactions"

        else:
            entity_candidates = [
                "InvoiceNo",
                "Invoice No",
                "Invoice Number",
                "InvoiceNumber",
            ]

        available_columns = (
            list(result_rows[0].keys())
            if result_rows
            else []
        )

        for candidate in entity_candidates:
            candidate_normalized = (
                str(candidate)
                .strip()
                .lower()
                .replace("_", "")
                .replace(" ", "")
            )

            for column in available_columns:
                column_normalized = (
                    str(column)
                    .strip()
                    .lower()
                    .replace("_", "")
                    .replace(" ", "")
                )

                if (
                    column_normalized
                    == candidate_normalized
                ):
                    entity_column = column
                    break

            if entity_column:
                break

        # ----------------------------------------------------
        # For invoice questions, also show customer when
        # available.
        # ----------------------------------------------------

        customer_column = None

        if entity_label == "invoices":
            for candidate in (
                "PartyName",
                "Customer",
                "CustomerName",
                "Party Name",
            ):
                candidate_normalized = (
                    str(candidate)
                    .strip()
                    .lower()
                    .replace("_", "")
                    .replace(" ", "")
                )

                for column in available_columns:
                    column_normalized = (
                        str(column)
                        .strip()
                        .lower()
                        .replace("_", "")
                        .replace(" ", "")
                    )

                    if (
                        column_normalized
                        == candidate_normalized
                    ):
                        customer_column = column
                        break

                if customer_column:
                    break

                if customer_column:
                    break

        # ----------------------------------------------------
        # Friendly metric wording.
        # ----------------------------------------------------

        if ranking_metric == "sales":
            metric_phrase = "sales"
        else:
            metric_phrase = ranking_metric

        # ----------------------------------------------------
        # Friendly answer for month/year/quarter rankings.
        # ----------------------------------------------------

        time_grouping = _extract_time_grouping(
            question,
            dataset,
            schema,
            result_rows,
        )

        temporal_ranking_query = bool(
            time_grouping
            and re.search(
                r"\b(?:highest|maximum|most|top|lowest|minimum|least|bottom)\b",
                question_norm,
            )
            and re.search(
                r"\b(?:month|months|monthly|year|years|yearly|quarter|quarters|quarterly)\b",
                question_norm,
            )
        )

        if temporal_ranking_query and result_rows:
            selected_row = result_rows[0]

            period_column = time_grouping.get(
                "column"
            )
            period = time_grouping.get(
                "period",
                "period",
            )

            period_value = selected_row.get(
                period_column,
                "Unknown",
            )

            # Convert period to friendly wording.
            if period == "month":
                try:
                    year, month = str(
                        period_value
                    ).split("-")

                    month_names = [
                        "",
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ]

                    period_value = (
                        f"{month_names[int(month)]} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "quarter":
                try:
                    year, quarter = str(
                        period_value
                    ).split("-Q")

                    period_value = (
                        f"Q{quarter} {year}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    pass

            elif period == "year":
                period_value = str(
                    period_value
                )

            ranking_word = (
                "highest"
                if ranking_label == "highest"
                else "lowest"
            )

            formatted_value = _format_inr(
                selected_row.get(
                    ranking_column
                )
            )

            answer = (
                f"{period_value} had the "
                f"{ranking_word} "
                f"{metric_phrase} with "
                f"{formatted_value}."
            )
            
            return {
                
                **state,
                "answer": answer,
            }

        else:
            answer = (
                f"{len(result_rows)} {ranking_label}-"
                f"{metric_phrase} {entity_label}:"
            )

            answer += "\n\n"

        # ----------------------------------------------------
        # Display only useful fields instead of all 26
        # database columns.
        # ----------------------------------------------------

        for index, row in enumerate(
            result_rows,
            start=1,
        ):

            entity_value = ""

            if entity_column:
                entity_value = row.get(
                    entity_column,
                    "",
                )

            metric_value = row.get(
                ranking_column,
                "",
            )

            if re.search(
                r"\b(?:quantity|qty)\b",
                question_norm,
            ):
                try:
                    formatted_metric = (
                        f"{float(metric_value):,.0f}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    formatted_metric = str(
                        metric_value
                    )
            else:
                try:
                    formatted_metric = _format_inr(
                        metric_value
                    )
                except Exception:
                    formatted_metric = str(
                        metric_value
                    )

            if entity_value:
                line = (
                    f"{index}. "
                    f"{entity_value}"
                )
            else:
                line = f"{index}."

            if (
                customer_column
                and customer_column != entity_column
            ):
                customer_value = row.get(
                    customer_column,
                    "",
                )

                if customer_value:
                    line += (
                        f" - {customer_value}"
                    )

            line += (
                f" - {formatted_metric}"
            )

            answer += line + "\n"

        return {
            **state,
            "answer": answer.strip(),
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
    elif result.get("operation") == "ranking" and result.get("rows"):
        ranking_rows = result.get("rows", [])
        ranking_group = (
            result.get("group_by")
            or state.get("group_by")
            or "Entity"
        )

        metric_name = "sales"
        metrics = result.get("metrics") or []

        if metrics and isinstance(metrics[0], dict):
            metric_name = (
                metrics[0].get("label")
                or metrics[0].get("requested")
                or "sales"
            )

        direction = str(
            state.get("ranking_direction")
            or state.get("direction")
            or result.get("direction")
            or (
                "asc"
                if re.search(
                    r"\b(?:bottom|lowest|minimum|min|smallest|least)\b",
                    question.lower(),
                )
                else "desc"
            )
        ).lower()

        metric_label = metric_name.replace("_", " ").title()
        group_label = ranking_group.replace("_", " ").title()

        if direction == "asc":
            title = f"Lowest {metric_label} by {group_label}"
        else:
            title = f"Highest {metric_label} by {group_label}"

        ranking_lines = []

        for row in ranking_rows:
            group_value = row.get(ranking_group)
            metric_value = row.get(metric_name)

            if metric_value is None:
                for key, value in row.items():
                    if (
                        key != ranking_group
                        and isinstance(value, (int, float))
                    ):
                        metric_value = value
                        break

            formatted_metric = _format_inr(metric_value)

            ranking_lines.append(
                f"{group_value} - {formatted_metric}"
            )

        answer = title + "\n\n" + "\n".join(ranking_lines)

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
            "SALES REPORT\n\n"
            f"Total Sales: "
            f"?{total_sales:,.2f}\n"
            f"Total Invoices: "
            f"{total_invoices}\n"
            f"Total Customers:"
            f"{len(customer_sales)}"
        )

        if customer_sales:

            answer += (
                "\n\n"
                "Customer-wise Sales\n\n"
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
                f"Ready to download "
                f"{len(result_rows)} records "
                f"as {format_label}."
            )

        # ----------------------------------------------------
        # Invoice details.
        # ----------------------------------------------------

        answer += (
            "\n\n"
            "Invoice Details\n\n"
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

    answer = locals().get("prefix") or answer

    # --------------------------------------------------------
    # UNIVERSAL AGGREGATE RESULT FORMATTER
    # --------------------------------------------------------

    result_operation = str(
        result.get("operation") or ""
    ).strip().lower()

    if result_operation == "aggregate":
        values = result.get("values") or {}
        metrics = result.get("metrics") or []

        if not values:
            return {
                **state,
                "answer": "Data not available in uploaded file.",
                "result": result,
                "error": None,
            }

        answer = ""

        for index, (metric_name, value) in enumerate(
            values.items()
        ):
            metric_info = {}

            for item in metrics:
                if (
                    isinstance(item, dict)
                    and str(item.get("requested"))
                    == str(metric_name)
                ):
                    metric_info = item
                    break

            function = str(
                metric_info.get("function") or ""
            ).lower()

            label = str(
                metric_info.get("label")
                or metric_name
            ).strip()

            # Normalize internal source-column names for user-facing answers.
            display_metric_labels = {
                "GrossAmount": "Sales",
                "Profit": "Profit",
                "Qty": "Quantity",
                "Quantity": "Quantity",
                "TotalGST": "GST",
                "GST": "GST",
                "CGST": "CGST",
                "SGST": "SGST",
                "IGST": "IGST",
                "DiscountAmt": "Discount",
                "TaxableAmount": "Taxable Amount",
                "Cost": "Cost",
                "UnitPrice": "Unit Price",
                "InvoiceTotal": "Invoice Value",
            }
            label = display_metric_labels.get(label, label)


            # Human-readable operation name.
            operation_labels = {
                "sum": "Total",
                "average": "Average",
                "avg": "Average",
                "max": "Maximum",
                "min": "Minimum",
                "median": "Median",
                "count": "Count",
            }

            operation_label = operation_labels.get(
                function,
                function.title() if function else "",
            )

            # Quantity/count-like values should not be shown
            # as currency.
            is_quantity = bool(
                re.search(
                    r"\b(?:quantity|qty|units|count)\b",
                    label.lower(),
                )
            )

            if value is None:
                formatted_value = "N/A"

            elif is_quantity:
                try:
                    formatted_value = (
                        f"{float(value):,.0f}"
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    formatted_value = str(value)

            else:
                try:
                    formatted_value = _format_inr(
                        value
                    )
                except Exception:
                    formatted_value = str(value)

            if operation_label:
                line = (
                    f"{operation_label} "
                    f"{label}: "
                    f"{formatted_value}"
                )
            else:
                line = (
                    f"{label}: "
                    f"{formatted_value}"
                )

            if index > 0:
                answer += "\n"

            answer += line

        return {
            **state,
            "answer": answer,
            "result": result,
            "error": None,
        }

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

    # ----------------------------------------------------
    # GPT-STYLE RAW ROW RESULT
    # ----------------------------------------------------

    if result.get("operation") == "rows":

        if not result_rows:
            answer = "No matching records were found."
        else:
            row_count = len(result_rows)

            answer = (
                f"{row_count} matching records:\n\n"
            )

            answer += _format_table(
                result_rows,
                max_rows=len(result_rows),
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

    if result_rows and result.get("operation") != "ranking":
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
# ============================================================
# UNIVERSAL METRIC RESOLVER
# ============================================================

def _resolve_universal_metric(
    metric: str,
    dataset,
    schema,
    rows,
):
    """
    Resolve a user-facing business metric to an actual uploaded column.

    Important:
    - Never invent a column.
    - Direct uploaded columns always have priority.
    - Semantic mappings are validated through _resolve_column().
    - Aggregation words are separated from the business metric.
    """

    if not metric:
        return None

    original_metric = str(metric).strip()
    text = _normalize_text(original_metric).strip()

    if not text:
        return None

    # ------------------------------------------------------------
    # Detect aggregation words that may be embedded in the metric.
    # Example:
    #   "average sales" -> metric = "sales", function = "average"
    #   "avg profit"    -> metric = "profit", function = "average"
    #   "maximum sales" -> metric = "sales", function = "max"
    # ------------------------------------------------------------

    function = None

    aggregation_aliases = {
        "average": "average",
        "avg": "average",
        "mean": "average",
        "typical average": "average",

        "maximum": "max",
        "max": "max",
        "highest": "max",
        "largest": "max",
        "top": "max",

        "minimum": "min",
        "min": "min",
        "lowest": "min",
        "smallest": "min",

        "total": "sum",
        "sum": "sum",
    }

    # Longest phrases first so "typical average" is checked
    # before individual words.
    for alias in sorted(
        aggregation_aliases,
        key=len,
        reverse=True,
    ):
        if text == alias:
            # A bare aggregation word is not a business metric.
            return None

        prefix = alias + " "
        if text.startswith(prefix):
            function = aggregation_aliases[alias]
            text = text[len(prefix):].strip()
            break

    # Also support aggregation words at the end.
    if function is None:
        for alias in sorted(
            aggregation_aliases,
            key=len,
            reverse=True,
        ):
            suffix = " " + alias
            if text.endswith(suffix):
                candidate_text = text[:-len(suffix)].strip()

                if candidate_text:
                    function = aggregation_aliases[alias]
                    text = candidate_text
                    break

    # Default aggregation.
    if function is None:
        function = "sum"

    # ------------------------------------------------------------
    # Direct uploaded column first.
    # ------------------------------------------------------------

    direct = _resolve_column(
        original_metric,
        dataset,
        schema,
                    [],
    )

    if direct:
        return {
            "column": direct,
            "function": function,
            "label": original_metric,
        }

    # Try the cleaned metric after removing aggregation words.
    direct_cleaned = _resolve_column(
        text,
        dataset,
        schema,
                    [],
    )

    if direct_cleaned:
        return {
            "column": direct_cleaned,
            "function": function,
            "label": original_metric,
        }

    # ------------------------------------------------------------
    # Business semantic mappings.
    #
    # The candidate column is STILL validated against the uploaded
    # schema below. Therefore a synonym can never invent a column.
    # ------------------------------------------------------------

    semantic_candidates = {
        # Sales / revenue / business value
        "sales": ["GrossAmount"],
        "sale": ["GrossAmount"],
        "selling": ["GrossAmount"],
        "selling amount": ["GrossAmount"],
        "sales amount": ["GrossAmount"],
        "revenue": ["GrossAmount"],
        "turnover": ["GrossAmount"],
        "billing": ["GrossAmount"],
        "business": ["GrossAmount"],
        "business value": ["GrossAmount"],
        "business amount": ["GrossAmount"],
        "sales value": ["GrossAmount"],
        "sales volume": ["GrossAmount"],
        "selling value": ["GrossAmount"],
        "total business": ["GrossAmount"],
        "business done": ["GrossAmount"],

        # Profit
        "profit": ["Profit"],
        "profits": ["Profit"],
        "earning": ["Profit"],
        "earnings": ["Profit"],
        "gain": ["Profit"],
        "gains": ["Profit"],
        "kamai": ["Profit"],
        "fayda": ["Profit"],
        "benefit": ["Profit"],
        "profit amount": ["Profit"],
        "profit value": ["Profit"],

        # Quantity
        "quantity": ["Qty"],
        "qty": ["Qty"],
        "units": ["Qty"],
        "unit": ["Qty"],
        "number of units": ["Qty"],
        "items sold": ["Qty"],
        "items": ["Qty"],

        # Discount
        "discount": ["DiscountAmt"],
        "discount amount": ["DiscountAmt"],
        "discount value": ["DiscountAmt"],

        # GST
        "gst": ["TotalGST"],
        "total gst": ["TotalGST"],
        "gst amount": ["TotalGST"],

        "cgst": ["CGST"],
        "cgst amount": ["CGST"],

        "sgst": ["SGST"],
        "sgst amount": ["SGST"],

        "igst": ["IGST"],
        "igst amount": ["IGST"],

        # Taxable amount
        "taxable": ["TaxableAmount"],
        "taxable amount": ["TaxableAmount"],
        "taxable value": ["TaxableAmount"],

        # Cost
        "cost": ["Cost"],
        "cost amount": ["Cost"],
        "cost value": ["Cost"],

        # Unit price
        "unit price": ["UnitPrice"],
        "price": ["UnitPrice"],
        "selling price": ["UnitPrice"],

        # Invoice value
        "invoice value": ["InvoiceTotal"],
        "invoice amount": ["InvoiceTotal"],
        "invoice total": ["InvoiceTotal"],
        "invoice value amount": ["InvoiceTotal"],
    }

    candidates = semantic_candidates.get(text)

    if not candidates:
        return None

    # ------------------------------------------------------------
    # Validate every semantic candidate against uploaded data.
    # ------------------------------------------------------------

    for candidate in candidates:
        resolved = _resolve_column(
            candidate,
            dataset,
            schema,
                    [],
        )

        if not resolved:
            continue

        resolved_function = function

        # Unit price is a per-row metric.
        # If the user did not explicitly request max/min/sum,
        # average is the safest default.
        if (
            text in {
                "unit price",
                "price",
                "selling price",
            }
            and function == "sum"
        ):
            resolved_function = "average"

        return {
            "column": resolved,
            "function": resolved_function,
            "label": original_metric,
        }

    # No matching uploaded column.
    return None

# ============================================================
# UNIVERSAL QUERY PLAN EXECUTOR
# ============================================================

def _execute_universal_plan(
    state,
    dataset,
    schema,
    rows,
):
    """
    Execute a validated universal query plan.

    This layer performs deterministic calculations on uploaded
    data. It does not ask the LLM to calculate numbers.
    """

    plan = state.get("query_plan")

    if not isinstance(plan, dict):
        return None

    if plan.get("status") != "OK":
        return None

    operation = str(
        plan.get("operation") or ""
    ).strip().lower()

    if operation not in {
        "aggregate",
        "group_aggregate",
        "count",
        "ranking",
    }:
        return None

    metrics = plan.get("metrics") or []

    if not metrics:
        metric = plan.get("metric")

        if metric:
            metrics = (
                metric
                if isinstance(metric, list)
                else [metric]
            )

    if not metrics:
        return None

    resolved_metrics = []

    for metric in metrics:

        resolved = _resolve_universal_metric(
            metric,
            dataset,
            schema,
                    [],
        )

        if not resolved:
            return {
                "status": "DATA_NOT_AVAILABLE",
                "message": "Data not available in uploaded file/data",
                "unavailable_metric": metric,
            }

        resolved_metrics.append(
            {
                "requested": metric,
                **resolved,
            }
        )

    # Planner aggregation overrides the metric resolver default.
    planner_aggregate_function = state.get("query_plan", {}).get(
        "aggregate_function"
    )

    if planner_aggregate_function:
        for resolved_metric in resolved_metrics:
            resolved_metric["function"] = planner_aggregate_function

    # Apply planner filters.
    # --------------------------------------------------------

    working_rows = list(rows)

    planner_filters = plan.get("filters") or []
    state_filters = state.get("filters") or []

    # Deterministic date filters are more reliable than planner date filters.
    # Keep non-date planner filters, then add the parser-generated date filters.
    if any(
        isinstance(f, dict) and f.get("type") == "date"
        for f in state_filters
    ):
        non_date_planner_filters = [
            f
            for f in planner_filters
            if not (
                isinstance(f, dict)
                and f.get("type") == "date"
            )
        ]
        filters = _deduplicate_filters(
            non_date_planner_filters + state_filters
        )
    else:
        filters = planner_filters

    if filters:

        filtered = []

        for row in working_rows:

            matched = True

            for item in filters:

                if not isinstance(item, dict):
                    continue

                requested_column = item.get("column")
                operator = str(
                    item.get("operator") or "eq"
                ).lower()

                value = item.get("value")

                actual_column = _resolve_column(
                    requested_column,
                    dataset,
                    schema,
                    working_rows,
                )

                if not actual_column:
                    matched = False
                    break

                actual_value = row.get(
                    actual_column
                )

                # ------------------------------------------------
                # DATE FILTERS
                # ------------------------------------------------
                # Date values are commonly stored as strings such
                # as "2026-08-15 00:00:00". They must not go through
                # numeric comparison logic.
                # ------------------------------------------------
                if item.get("type") == "date":

                    actual_text = str(
                        actual_value or ""
                    ).strip()

                    target_text = str(
                        value or ""
                    ).strip()

                    actual_date = actual_text[:10]
                    target_date = target_text[:10]

                    if operator == "year":
                        try:
                            if int(actual_date[:4]) != int(value):
                                matched = False
                                break
                        except (ValueError, TypeError):
                            matched = False
                            break

                    elif operator == "month":
                        try:
                            if int(actual_date[5:7]) != int(value):
                                matched = False
                                break
                        except (ValueError, TypeError):
                            matched = False
                            break

                    elif operator in {
                        "eq",
                        "=",
                        "==",
                    }:

                        if actual_date != target_date:
                            matched = False
                            break

                    elif operator in {
                        ">",
                        "gt",
                    }:

                        if actual_date <= target_date:
                            matched = False
                            break

                    elif operator in {
                        "<",
                        "lt",
                    }:

                        if actual_date >= target_date:
                            matched = False
                            break

                    elif operator in {
                        ">=",
                        "gte",
                    }:

                        if actual_date < target_date:
                            matched = False
                            break

                    elif operator in {
                        "<=",
                        "lte",
                    }:

                        if actual_date > target_date:
                            matched = False
                            break

                    continue

                if operator in {
                    "eq",
                    "=",
                    "==",
                }:

                    if str(actual_value).strip().lower() != str(
                        value
                    ).strip().lower():
                        matched = False
                        break

                elif operator in {
                    "contains",
                }:

                    if str(value).lower() not in str(
                        actual_value
                    ).lower():
                        matched = False
                        break

                elif operator in {
                    "in",
                    "one_of",
                }:

                    allowed_values = (
                        value
                        if isinstance(
                            value,
                            (list, tuple, set),
                        )
                        else [value]
                    )

                    normalized_allowed_values = {
                        str(item).strip().lower()
                        for item in allowed_values
                    }

                    if (
                        str(actual_value).strip().lower()
                        not in normalized_allowed_values
                    ):
                        matched = False
                        break


                elif operator in {
                    ">",
                    "gt",
                }:

                    if (
                        _to_number(actual_value) is None
                        or _to_number(value) is None
                        or _to_number(actual_value)
                        <= _to_number(value)
                    ):
                        matched = False
                        break

                elif operator in {
                    "<",
                    "lt",
                }:

                    if (
                        _to_number(actual_value) is None
                        or _to_number(value) is None
                        or _to_number(actual_value)
                        >= _to_number(value)
                    ):
                        matched = False
                        break

                elif operator in {
                    ">=",
                    "gte",
                }:

                    if (
                        _to_number(actual_value) is None
                        or _to_number(value) is None
                        or _to_number(actual_value)
                        < _to_number(value)
                    ):
                        matched = False
                        break

                elif operator in {
                    "<=",
                    "lte",
                }:

                    if (
                        _to_number(actual_value) is None
                        or _to_number(value) is None
                        or _to_number(actual_value)
                        > _to_number(value)
                    ):
                        matched = False
                        break

            if matched:
                filtered.append(row)

        working_rows = filtered

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if operation == "count":

        return {
            "operation": "count",
            "value": len(working_rows),
            "filtered_rows": len(working_rows),
            "source_rows": len(rows),
            "metrics": resolved_metrics,
        }

    # --------------------------------------------------------
    # GROUP AGGREGATE / RANKING
    # --------------------------------------------------------

    group_by_requested = plan.get(
        "group_by"
    )

    group_by = None

    if group_by_requested:

        group_by = _resolve_column(
            group_by_requested,
            dataset,
            schema,
            working_rows,
        )

        if not group_by:
            return {
                "status": "DATA_NOT_AVAILABLE",
                "message": "Data not available in uploaded file/data",
                "unavailable_column": group_by_requested,
            }

    direction = str(
        plan.get("direction") or "desc"
    ).lower()

    limit = plan.get("limit")

    try:
        limit = int(limit) if limit else None
    except (TypeError, ValueError):
        limit = None

    # --------------------------------------------------------
    # GROUPED RESULT
    # --------------------------------------------------------

    if group_by:

        grouped_rows = []

        # Build groups manually so multiple metrics can be
        # calculated without adding new query-specific code.

        groups = {}

        for row in working_rows:

            key = row.get(group_by)

            if key is None:
                key = ""

            groups.setdefault(
                str(key),
                [],
            ).append(row)

        for group_value, group_rows in groups.items():

            result_row = {
                group_by: group_value,
            }

            for metric in resolved_metrics:

                column = metric["column"]
                function = metric["function"]

                values = []

                for row in group_rows:

                    numeric_value = _to_number(
                        row.get(column)
                    )

                    if numeric_value is not None:
                        values.append(
                            numeric_value
                        )

                if not values:
                    result_row[
                        metric["requested"]
                    ] = None
                    continue

                if function == "average":

                    calculated = (
                        sum(values) / len(values)
                    )

                elif function == "max":

                    calculated = max(values)

                elif function == "min":

                    calculated = min(values)

                else:

                    calculated = sum(values)

                result_row[
                    metric["requested"]
                ] = calculated

            grouped_rows.append(result_row)

        # ----------------------------------------------------
        # Ranking.
        # ----------------------------------------------------

        if operation == "ranking" or limit:

            ranking_metric = (
                resolved_metrics[0]["requested"]
            )

            grouped_rows.sort(
                key=lambda item: (
                    item.get(
                        ranking_metric
                    )
                    if item.get(
                        ranking_metric
                    ) is not None
                    else 0
                ),
                reverse=(
                    direction != "asc"
                ),
            )

        if limit:
            grouped_rows = grouped_rows[:limit]

        return {
            "operation": (
                "ranking"
                if operation == "ranking"
                else "group_aggregate"
            ),
            "group_by": group_by,
            "rows": grouped_rows,
            "count": len(grouped_rows),
            "source_rows": len(rows),
            "filtered_rows": len(working_rows),
            "metrics": resolved_metrics,
        }

    # --------------------------------------------------------
    # SINGLE AGGREGATE
    # --------------------------------------------------------

    result = {}

    for metric in resolved_metrics:

        column = metric["column"]
        function = metric["function"]

        values = []

        for row in working_rows:

            numeric_value = _to_number(
                row.get(column)
            )

            if numeric_value is not None:
                values.append(
                    numeric_value
                )

        if not values:
            result[
                metric["requested"]
            ] = None
            continue

        if function == "average":

            calculated = (
                sum(values) / len(values)
            )

        elif function == "max":

            calculated = max(values)

        elif function == "min":

            calculated = min(values)

        else:

            calculated = sum(values)

        result[
            metric["requested"]
        ] = calculated

    return {
        "operation": "aggregate",
        "values": result,
        "metrics": resolved_metrics,
        "source_rows": len(rows),
        "filtered_rows": len(working_rows),
    }
































