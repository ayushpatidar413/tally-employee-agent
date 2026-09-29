import re
from typing import Any


# ============================================================
# UNIVERSAL COLUMN ALIASES
# ============================================================

COLUMN_ALIASES = {

    # ========================================================
    # COMMON / IDENTIFIERS
    # ========================================================

    "id": [
        "id",
        "record id",
        "unique id",
        "identifier",
    ],

    "name": [
        "name",
        "full name",
        "person name",
    ],

    # ========================================================
    # EMPLOYEE
    # ========================================================

    "employee_id": [
        "employee id",
        "emp id",
        "employee code",
        "emp code",
        "staff id",
        "staff code",
    ],

    "employee_name": [
        "employee name",
        "employee",
        "staff name",
        "staff",
        "worker name",
        "worker",
    ],

    "designation": [
        "designation",
        "job title",
        "job role",
        "role",
        "position",
    ],

    "joining_date": [
        "joining date",
        "date of joining",
        "join date",
        "hire date",
        "hiring date",
    ],

    "salary": [
        "salary",
        "monthly salary",
        "basic salary",
        "wage",
        "income",
    ],

    # ========================================================
    # PAYMENT
    # ========================================================

    "payment_mode": [
        "payment mode",
        "payment method",
        "mode of payment",
        "method of payment",
        "paymentmode",
    ],

    "payment": [
        "payment",
        "paid",
        "paid amount",
        "payment amount",
        "amount paid",
    ],

    # ========================================================
    # GST
    # ========================================================

   "gst": [
        "gst",
        "gst amount",
        "gst tax",
        "goods and services tax",
        "total gst",
        "totalgst",
    ],

    "gst_rate": [
        "gst rate",
        "gst %",
        "gst rate %",
        "gst percentage",
        "tax rate",
    ],

    "cgst": [
        "cgst",
        "central gst",
        "central goods and services tax",
    ],

    "sgst": [
        "sgst",
        "state gst",
        "state goods and services tax",
    ],

    "igst": [
        "igst",
        "integrated gst",
        "integrated goods and services tax",
    ],
    "gstin": [
        "gstin",
        "gst number",
        "gst no",
        "gst registration number",
    ],
    "party_type": [
        "party type",
        "customer type",
        "buyer type",
        "partytype",
    ],

    # ========================================================
    # STUDENT / EDUCATION
    # ========================================================

    "student_id": [
        "student id",
        "student code",
        "student number",
        "roll number",
        "roll no",
        "registration number",
        "registration id",
    ],

    "student_name": [
        "student name",
        "student",
        "learner name",
        "learner",
    ],

    "marks": [
        "marks",
        "mark",
        "score",
        "scores",
        "exam marks",
        "test marks",
        "obtained marks",
    ],

    "grade": [
        "grade",
        "letter grade",
        "result grade",
    ],

    "gpa": [
        "gpa",
        "cgpa",
        "grade point",
        "grade point average",
    ],

    "age": [
        "age",
        "student age",
        "employee age",
        "person age",
    ],

    "course": [
        "course",
        "course name",
        "program",
        "program name",
        "subject",
        "subject name",
    ],

    "semester": [
        "semester",
        "sem",
        "term",
        "academic term",
    ],

    # ========================================================
    # ORGANIZATION
    # ========================================================

    "department": [
        "department",
        "dept",
        "division",
        "business unit",
        "branch",
    ],

    "category": [
        "category",
        "class",
        "group",
    ],

    # ========================================================
    # CUSTOMER / PARTY
    # ========================================================

    "customer_id": [
        "customer id",
        "client id",
        "customer code",
        "client code",
    ],

    "customer": [
        "customer",
        "customer name",
        "client",
        "client name",
        "buyer",
        "buyer name",
        "party name",
        "partyname",
    ],

   

    "party_state": [
        "party state",
        "customer state",
        "customer location",
        "party location",
    ],

    "state": [
        "state",
        "party state",
        "customer state",
        "supplier state",
        "partystate",
    ],

    # ========================================================
    # SUPPLIER
    # ========================================================

    "supplier_id": [
        "supplier id",
        "vendor id",
        "supplier code",
        "vendor code",
    ],

    "supplier": [
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
    ],

    # ========================================================
    # PRODUCTS
    # ========================================================

    "product_id": [
        "product id",
        "product code",
        "item id",
        "item code",
        "sku",
    ],

    "product": [
        "product",
        "product name",
        "item",
        "item name",
        "goods",
    ],

    "hsn_code": [
        "hsn code",
        "hsn",
        "hsn/sac code",
        "hsn sac code",
        "hsn_code",
        "sac code",
        "sac",
    ],

    # ========================================================
    # TRANSACTIONS
    # ========================================================

    "invoice_number": [
        "invoice number",
        "invoice no",
        "invoice",
        "invoice id",
        "bill number",
        "bill no",
        "bill id",
        "invoiceno",
    ],

    "order_id": [
        "order id",
        "order number",
        "order no",
    ],

    "transaction_date": [
        "date",
        "transaction date",
        "bill date",
        "invoice date",
        "order date",
        "purchase date",
        "sales date",
        "payment date",
    ],

    # ========================================================
    # SALES / FINANCIAL AMOUNTS
    # ========================================================

    "amount": [
        "amount",
        "total",
        "total amount",
        "grand total",
        "net amount",
        "invoice amount",
        "bill amount",
        "sales amount",
        "purchase amount",
        "price",
        "value",
        "revenue",
        
    ],
    "invoice_amount": [
        "invoice total",
        "invoice value",
        "total invoice value",
        "invoice amount",
        "invoicetotal",
    ],

    "gross_amount": [
        "gross amount",
        "gross sales",
        "gross value",
        "grossamount",
    ],

    "taxable_amount": [
        "taxable amount",
        "taxable value",
        "taxable sales",
        "taxableamount",
    ],

    "quantity": [
        "quantity",
        "qty",
        "units",
        "unit count",
        "number of units",
        "total qty",
        "qty sold",
    ],

    "unit_price": [
        "unit price",
        "price per unit",
        "selling price",
        "unitprice",
    ],
    "percentage": [
        "percentage",
        "percent",
        "%",
        "share percent",
        "percentage of total",
        "percent of total",
        "of total",
    ],

    # ========================================================
    # DISCOUNT
    # ========================================================

    "discount_percent": [
        "discount percent",
        "discount percentage",
        "discount %",
        "discountpct",
    ],

    "discount": [
        "discount",
        "discount amount",
        "discountamt",
        "discount value",
    ],

    # ========================================================
    # COST / PROFIT
    # ========================================================

    "cost": [
        "cost",
        "cost amount",
        "total cost",
        "purchase cost",
    ],

    "profit": [
        "profit",
        "net profit",
        "gross profit",
        "profit amount",
    ],

    "margin_percent": [
        "margin %",
        "margin percent",
        "margin percentage",
    ],

    # ========================================================
    # PERIOD
    # ========================================================

    "month": [
        "month",
        "billing month",
        "sales month",
        "transaction month",
        "reporting month",
    ],

    # ========================================================
    # INTER-STATE
    # ========================================================

    "inter_state": [
        "inter state",
        "interstate",
        "inter state sale",
        "inter state transaction",
    ],

    # ========================================================
    # ATTENDANCE
    # ========================================================

    "attendance_status": [
        "attendance",
        "attendance status",
        "status",
        "presence",
    ],

    "check_in": [
        "check in",
        "check-in",
        "in time",
        "login time",
    ],

    "check_out": [
        "check out",
        "check-out",
        "out time",
        "logout time",
    ],

    "working_hours": [
        "working hours",
        "hours worked",
        "work hours",
        "total working hours",
    ],

    "leave_type": [
        "leave type",
        "leave",
        "leave category",
    ],

    # ========================================================
    # INVENTORY
    # ========================================================

    "stock": [
        "stock",
        "stock quantity",
        "available stock",
        "closing stock",
        "opening stock",
    ],

    # ========================================================
    # OUTSTANDING
    # ========================================================

    "outstanding": [
        "outstanding",
        "balance due",
        "due amount",
        "remaining amount",
        "outstanding amount",
    ],

    # ========================================================
    # EXPENSE
    # ========================================================

    "expense": [
        "expense",
        "expense amount",
        "expenses",
    ],
}

# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(value: Any) -> str:

    if value is None:
        return ""

    value = str(value).strip().lower()

    value = value.replace("_", " ")
    value = value.replace("-", " ")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# COLUMN NORMALIZATION
# ============================================================

def normalize_column_name(column: Any) -> str:

    value = normalize_text(column)

    value = re.sub(r"[^a-z0-9 ]", "", value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# EXACT ALIAS MATCH
# ============================================================

def find_alias_match(column_name: str):

    normalized = normalize_column_name(column_name)

    for canonical, aliases in COLUMN_ALIASES.items():

        for alias in aliases:

            if normalized == normalize_column_name(alias):
                return canonical

    return None


# ============================================================
# PARTIAL ALIAS MATCH
# ============================================================

def find_partial_alias_match(column_name: str):

    normalized = normalize_column_name(
        column_name
    )

    if not normalized:
        return None

    # --------------------------------------------------------
    # Partial matching should only use meaningful aliases.
    #
    # Very short / generic aliases such as:
    # "pay", "type", "value", "total", "amount", etc.
    # can incorrectly match unrelated columns.
    # --------------------------------------------------------

    unsafe_short_aliases = {
        "pay",
        "type",
        "role",
        "staff",
        "worker",
        "item",
        "goods",
        "total",
        "amount",
        "value",
        "price",
        "cost",
        "income",
        "payment",
        "status",
        "date",
        "name",
        "id",
        "salary",
    }

    candidates = []

    for canonical, aliases in COLUMN_ALIASES.items():

        for alias in aliases:

            alias_normalized = normalize_column_name(
                alias
            )

            if not alias_normalized:
                continue

            # Ignore dangerous short aliases during
            # partial matching.
            if alias_normalized in unsafe_short_aliases:
                continue

            # Ignore extremely short aliases.
            if len(alias_normalized) < 4:
                continue

            # ------------------------------------------------
            # Token-aware matching
            # ------------------------------------------------

            normalized_tokens = set(
                normalized.split()
            )

            alias_tokens = set(
                alias_normalized.split()
            )

            # Multi-word aliases can match when all their
            # meaningful tokens are present.
            if (
                len(alias_tokens) > 1
                and alias_tokens.issubset(
                    normalized_tokens
                )
            ):
                candidates.append(
                    (
                        canonical,
                        alias_normalized,
                        3,
                    )
                )
                continue

            # ------------------------------------------------
            # Safe substring matching
            # ------------------------------------------------

            if (
                len(alias_normalized) >= 6
                and (
                    alias_normalized in normalized
                    or normalized in alias_normalized
                )
            ):
                candidates.append(
                    (
                        canonical,
                        alias_normalized,
                        1,
                    )
                )

    if not candidates:
        return None

    # Prefer:
    # 1. longer alias
    # 2. stronger match
    candidates.sort(
        key=lambda item: (
            item[2],
            len(item[1]),
        ),
        reverse=True,
    )

    return candidates[0][0]


# ============================================================
# DATE DETECTION
# ============================================================

def detect_date_column(column_name: str, values=None) -> bool:

    normalized = normalize_column_name(column_name)

    date_keywords = [
        "date",
        "dob",
        "birth date",
        "joining date",
        "join date",
        "transaction date",
        "invoice date",
        "bill date",
        "order date",
        "payment date",
    ]

    for keyword in date_keywords:

        if keyword in normalized:
            return True

    return False


# ============================================================
# NUMERIC DETECTION
# ============================================================

def detect_numeric_column(values) -> bool:

    if values is None:
        return False

    values = list(values)

    if not values:
        return False

    valid = 0
    total = 0

    for value in values:

        if value is None:
            continue

        if str(value).strip() == "":
            continue

        total += 1

        try:

            cleaned = (
                str(value)
                .replace(",", "")
                .replace("â‚¹", "")
                .replace("$", "")
                .replace("â‚¬", "")
                .replace("Â£", "")
                .strip()
            )

            float(cleaned)

            valid += 1

        except (ValueError, TypeError):
            pass

    if total == 0:
        return False

    return (valid / total) >= 0.8


# ============================================================
# DATA TYPE DETECTION
# ============================================================

def detect_column_data_type(column_name: str, values=None) -> str:

    if detect_date_column(column_name, values):
        return "date"

    if detect_numeric_column(values):
        return "numeric"

    return "text"


# ============================================================
# COLUMN ROLE DETECTION
# ============================================================

def detect_column_role(column_name: str, values=None):

    exact = find_alias_match(column_name)

    if exact:
        return exact, 1.0

    partial = find_partial_alias_match(column_name)

    if partial:
        return partial, 0.85

    return None, 0.0


# ============================================================
# DETECT ALL COLUMNS
# ============================================================

def detect_columns(columns, rows=None):

    rows = rows or []

    detected = []

    for column in columns:

        values = [
            row.get(column)
            for row in rows
            if isinstance(row, dict)
        ]

        canonical, confidence = detect_column_role(
            column,
            values,
        )

        data_type = detect_column_data_type(
            column,
            values,
        )

        detected.append(
            {
                "source_column": column,
                "canonical_column": canonical,
                "data_type": data_type,
                "confidence": confidence,
            }
        )

    return detected


# ============================================================
# DATASET CLASSIFICATION
# ============================================================

DATASET_KEYWORDS = {
    "sales": [
        "sale",
        "sales",
        "selling",
        "invoice",
        "invoices",
        "sale invoice",
        "sale invoices",
        "sales report",
        "sales summary",
        "gst sales",
        "party wise",
        "party-wise",
        "hsn summary",
        "gst summary",
        "category summary",
        "payment mode",
        "monthly trend",
        "sales register",
    ],

    "purchase": [
        "purchase",
        "purchases",
        "purchase invoice",
        "purchase invoices",
        "purchase report",
        "purchase summary",
        "supplier",
        "suppliers",
        "vendor",
        "vendors",
        "purchase register",
    ],

    "expense": [
        "expense",
        "expenses",
        "expense report",
        "expense summary",
        "cost report",
        "expenditure",
    ],

    "payment": [
        "payment",
        "payments",
        "payment report",
        "payment summary",
        "receivable",
        "payable",
    ],

    "customer": [
        "customer",
        "customers",
        "customer master",
        "customer list",
        "client",
        "clients",
        "buyer",
        "buyers",
    ],

    "supplier": [
        "supplier",
        "suppliers",
        "supplier master",
        "supplier list",
        "vendor",
        "vendors",
    ],

    "inventory": [
        "inventory",
        "stock",
        "stock report",
        "stock summary",
        "warehouse",
        "reorder",
        "opening stock",
        "closing stock",
        "stock quantity",
        "inventory report",
    ],

    "employee": [
        "employee",
        "employees",
        "employee master",
        "staff",
        "staff list",
        "salary",
        "payroll",
        "designation",
        "joining date",
    ],

    "attendance": [
        "attendance",
        "attendance report",
        "attendance summary",
        "present",
        "absent",
        "leave",
        "check in",
        "check out",
        "working hours",
    ],

    "student": [
        "student",
        "students",
        "student record",
        "student records",
        "marks",
        "grade",
        "gpa",
        "cgpa",
        "semester",
        "academic",
    ],

    "order": [
        "order",
        "orders",
        "order report",
        "order summary",
        "order status",
    ],
}


def classify_dataset(
    filename: str,
    columns,
    rows=None,
):

    rows = rows or []

    filename_text = normalize_text(filename)

    column_text = " ".join(
        normalize_column_name(column)
        for column in columns
    )

    combined_text = f"{filename_text} {column_text}"

    scores = {
        dataset_type: 0
        for dataset_type in DATASET_KEYWORDS
    }

    # ========================================================
    # KEYWORD SCORING
    # ========================================================

    for dataset_type, keywords in DATASET_KEYWORDS.items():

        for keyword in keywords:

            keyword_normalized = normalize_text(
                keyword
            )

            if not keyword_normalized:
                continue

            if keyword_normalized in combined_text:
                scores[dataset_type] += 1

    # ========================================================
    # DETECT CANONICAL COLUMN ROLES
    # ========================================================

    detected_columns = detect_columns(
        columns,
        rows,
    )

    roles = {
        item["canonical_column"]
        for item in detected_columns
        if item["canonical_column"]
    }

    # ========================================================
    # STUDENT SIGNALS
    # ========================================================

    if "student_id" in roles:
        scores["student"] += 5

    if "student_name" in roles:
        scores["student"] += 5

    if "marks" in roles:
        scores["student"] += 4

    if "grade" in roles:
        scores["student"] += 3

    if "gpa" in roles:
        scores["student"] += 3

    if "semester" in roles:
        scores["student"] += 2

    # ========================================================
    # EMPLOYEE SIGNALS
    # ========================================================

    if "employee_id" in roles:
        scores["employee"] += 5

    if "employee_name" in roles:
        scores["employee"] += 5

    if "salary" in roles:
        scores["employee"] += 4

    if "designation" in roles:
        scores["employee"] += 3

    if "joining_date" in roles:
        scores["employee"] += 3

    # ========================================================
    # CUSTOMER SIGNALS
    # ========================================================

    if "customer_id" in roles:
        scores["customer"] += 5

    if "customer" in roles:
        scores["customer"] += 4

    # ========================================================
    # SUPPLIER / PURCHASE SIGNALS
    # ========================================================

    if "supplier_id" in roles:
        scores["purchase"] += 5

    if "supplier" in roles:
        scores["purchase"] += 4

    # ========================================================
    # ORDER SIGNALS
    # ========================================================

    if "order_id" in roles:
        scores["order"] += 5

    # ========================================================
    # ATTENDANCE SIGNALS
    # ========================================================

    if "attendance_status" in roles:
        scores["attendance"] += 5

    if "check_in" in roles:
        scores["attendance"] += 3

    if "check_out" in roles:
        scores["attendance"] += 3

    if "working_hours" in roles:
        scores["attendance"] += 3

    # ========================================================
    # INVENTORY SIGNALS
    # ========================================================

    # Product and quantity occur in sales invoices too,
    # so they are intentionally NOT strong inventory signals.

    if "product_id" in roles:
        scores["inventory"] += 5

    # ========================================================
    # SALES TRANSACTION SIGNALS
    # ========================================================

    sales_transaction_roles = {
        "invoice_number",
        "transaction_date",
        "customer",
        "invoice_amount",
        "gross_amount",
        "taxable_amount",
        "gst",
        "gst_rate",
        "payment_mode",
        "profit",
    }

    sales_role_count = len(
        sales_transaction_roles.intersection(roles)
    )

    if sales_role_count:
        scores["sales"] += (
            sales_role_count * 3
        )

    # A combination of invoice + date + party/customer
    # is a particularly strong sales transaction signal.

    if (
        "invoice_number" in roles
        and "transaction_date" in roles
        and (
            "customer" in roles
            or "supplier" in roles
        )
    ):
        scores["sales"] += 8

    # Financial sales summaries are also sales datasets.

    sales_summary_roles = {
        "taxable_amount",
        "gst",
        "invoice_amount",
        "profit",
        "gst_rate",
        "payment_mode",
        "month",
        "hsn_code",
        "category",
    }

    sales_summary_count = len(
        sales_summary_roles.intersection(roles)
    )

    if sales_summary_count >= 2:
        scores["sales"] += (
            sales_summary_count * 2
        )

    # ========================================================
    # PURCHASE OVERRIDE SIGNAL
    # ========================================================

    # Supplier + purchase-specific columns should not be
    # mistaken for ordinary sales.

    if (
        "supplier" in roles
        and "invoice_number" in roles
        and "transaction_date" in roles
        and "customer" not in roles
    ):
        scores["purchase"] += 8

    # ========================================================
    # INVENTORY CONFLICT HANDLING
    # ========================================================

    # A real inventory dataset normally has stock/warehouse
    # signals. Product + quantity alone is not sufficient.

    inventory_strong_roles = {
        "product_id",
        "stock",
        "warehouse",
        "reorder_level",
    }

    strong_inventory_count = len(
        inventory_strong_roles.intersection(roles)
    )

    if strong_inventory_count:

        scores["inventory"] += (
            strong_inventory_count * 4
        )

    # If this clearly looks like a sales transaction,
    # remove the accidental inventory competition.

    if (
        "invoice_number" in roles
        and "transaction_date" in roles
        and (
            "customer" in roles
            or "invoice_amount" in roles
            or "gross_amount" in roles
            or "taxable_amount" in roles
        )
    ):
        scores["inventory"] = min(
            scores["inventory"],
            2,
        )

    # ========================================================
    # STUDENT CONFLICT HANDLING
    # ========================================================

    if (
        "student_id" in roles
        or "student_name" in roles
    ):

        scores["student"] += 3

        if (
            "employee_id" not in roles
            and "employee_name" not in roles
        ):
            scores["employee"] = min(
                scores["employee"],
                1,
            )

    # ========================================================
    # SELECT BEST DATASET TYPE
    # ========================================================

    best_type = max(
        scores,
        key=scores.get,
    )

    best_score = scores[best_type]

    total_score = sum(
        scores.values()
    )

    if best_score == 0:

        dataset_type = "structured"
        confidence = 0.0

    else:

        dataset_type = best_type

        confidence = round(
            best_score / max(
                total_score,
                1,
            ),
            2,
        )

    return {
        "dataset_type": dataset_type,
        "confidence": confidence,
        "scores": scores,
    }



def detect_schema(
    filename: str,
    columns,
    rows=None,
):

    rows = rows or []

    detected_columns = detect_columns(
        columns,
        rows,
    )

    classification = classify_dataset(
        filename,
        columns,
        rows,
    )

    numeric_columns = [
        item["source_column"]
        for item in detected_columns
        if item["data_type"] == "numeric"
    ]

    date_columns = [
        item["source_column"]
        for item in detected_columns
        if item["data_type"] == "date"
    ]

    text_columns = [
        item["source_column"]
        for item in detected_columns
        if item["data_type"] == "text"
    ]

    return {
        "dataset_type": classification["dataset_type"],
        "confidence": classification["confidence"],
        "scores": classification["scores"],
        "columns": detected_columns,
        "row_count": len(rows),
        "column_count": len(columns),
        "numeric_columns": numeric_columns,
        "date_columns": date_columns,
        "text_columns": text_columns,
    }
