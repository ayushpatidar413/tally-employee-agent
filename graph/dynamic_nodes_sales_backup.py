from typing import Any, TypedDict
import re

from services.dynamic_query_service import (
    load_dataset_rows,
    get_dataset_context,
    get_all_dataset_context,
    find_datasets_by_type,
    sum_column,
    count_rows,
    group_and_sum,
    highest_value,
    find_invoice,
    find_customer_transactions,
)


# ============================================================
# DYNAMIC AGENT STATE
# ============================================================

class DynamicAgentState(TypedDict, total=False):

    question: str

    intent: str

    dataset_id: int | None

    dataset_type: str | None

    rows: list[dict[str, Any]]

    result: dict[str, Any]

    answer: str


# ============================================================
# NORMALIZE TEXT
# ============================================================

def _normalize_text(
    value: Any,
) -> str:

    return (
        str(value)
        .strip()
        .lower()
    )


# ============================================================
# EXTRACT CUSTOMER NAME
# ============================================================

def _extract_customer_name(
    question: str,
) -> str | None:

    patterns = [
        r"(?:for|from|customer)\s+(.+?)(?:\?|$)",
        r"sales\s+(?:of|for|from)\s+(.+?)(?:\?|$)",
        r"transactions\s+(?:of|for|from)\s+(.+?)(?:\?|$)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
            re.IGNORECASE,
        )

        if match:

            name = match.group(1).strip()

            # Remove common trailing words
            name = re.sub(
                r"\s+(?:sales|transactions|details|report)$",
                "",
                name,
                flags=re.IGNORECASE,
            )

            if name:
                return name.strip()

    return None


# ============================================================
# EXTRACT INVOICE NUMBER
# ============================================================

def _extract_invoice_number(
    question: str,
) -> str | None:
    """
    Extract invoice numbers such as:

    INV101
    INV102
    INV103
    INV-103

    Important:
    Do not accidentally return the word
    'INVOICE'.
    """

    match = re.search(
        r"\bINV[\w-]+\b",
        question,
        re.IGNORECASE,
    )

    if match:

        return (
            match.group(0)
            .strip()
            .upper()
        )

    return None


# ============================================================
# DETECT INTENT
# ============================================================

def detect_dynamic_intent(
    state: DynamicAgentState,
) -> DynamicAgentState:

    question = state.get(
        "question",
        "",
    )

    text = _normalize_text(
        question
    )

    intent = "general"

    # ========================================================
    # COMPLETE REPORT
    # ========================================================

    if (
        "complete report" in text
        or "full report" in text
        or "complete sales report" in text
        or "sales report" in text
        or "business report" in text
    ):

        intent = "sales_report"

    # ========================================================
    # INVOICE
    # ========================================================

    elif (
        "invoice" in text
        and (
            _extract_invoice_number(question)
            is not None
        )
    ):

        intent = "invoice_search"

    # ========================================================
    # HIGHEST PRODUCT / PRODUCT SALES
    # ========================================================

    elif (
        "highest" in text
        or "top product" in text
        or "best selling product" in text
        or "best-selling product" in text
        or "product wise" in text
        or "product-wise" in text
        or "sales by product" in text
        or "product sales" in text
    ):

        intent = "product_sales"

    # ========================================================
    # CUSTOMER SALES
    # ========================================================

    elif (
        "customer" in text
        or "party" in text
        or "for abc" in text
        or "for xyz" in text
        or "for def" in text
        or "sales for" in text
        or "sales of" in text
        or "sales from" in text
        or "transactions for" in text
    ):

        customer = _extract_customer_name(
            question
        )

        if customer:
            intent = "customer_sales"

    # ========================================================
    # SALES COUNT
    # ========================================================

    elif (
        "how many sales" in text
        or "number of sales" in text
        or "sales count" in text
        or "number of invoices" in text
        or "invoice count" in text
        or "total invoices" in text
    ):

        intent = "sales_count"

    # ========================================================
    # TOTAL SALES
    # ========================================================

    elif (
        "total sales" in text
        or "sales total" in text
        or "total sale" in text
        or "sales amount" in text
        or "revenue" in text
        or "total revenue" in text
    ):

        intent = "total_sales"

    # ========================================================
    # DEFAULT
    # ========================================================

    state["intent"] = intent

    return state


# ============================================================
# SELECT DATASET
# ============================================================

def select_dynamic_dataset(
    state: DynamicAgentState,
) -> DynamicAgentState:

    requested_dataset_id = state.get(
        "dataset_id"
    )

    # ========================================================
    # EXPLICIT DATASET ID
    # ========================================================

    if requested_dataset_id:

        context = get_dataset_context(
            requested_dataset_id
        )

        if context:

            dataset = context["dataset"]

            state["dataset_id"] = (
                requested_dataset_id
            )

            state["dataset_type"] = (
                dataset.get(
                    "data_type"
                )
            )

            return state

    # ========================================================
    # DETERMINE DATASET TYPE FROM INTENT
    # ========================================================

    intent = state.get(
        "intent",
        "general",
    )

    dataset_type = "sales"

    if intent in {
        "total_sales",
        "sales_count",
        "customer_sales",
        "invoice_search",
        "product_sales",
        "sales_report",
    }:

        dataset_type = "sales"

    # ========================================================
    # FIND MATCHING DATASETS
    # ========================================================

    datasets = find_datasets_by_type(
        dataset_type
    )

    if datasets:

        # get_datasets() is newest first
        selected = datasets[0]

        state["dataset_id"] = selected["id"]

        state["dataset_type"] = selected.get(
            "data_type"
        )

        return state

    # ========================================================
    # FALLBACK TO ANY DATASET
    # ========================================================

    all_datasets = get_all_dataset_context()

    if all_datasets:

        selected = all_datasets[0]["dataset"]

        state["dataset_id"] = selected["id"]

        state["dataset_type"] = selected.get(
            "data_type"
        )

    else:

        state["dataset_id"] = None

        state["dataset_type"] = None

    return state


# ============================================================
# LOAD DATA
# ============================================================

def load_dynamic_data(
    state: DynamicAgentState,
) -> DynamicAgentState:

    dataset_id = state.get(
        "dataset_id"
    )

    if not dataset_id:

        state["rows"] = []

        return state

    rows = load_dataset_rows(
        dataset_id
    )

    state["rows"] = rows

    return state


# ============================================================
# EXECUTE DYNAMIC QUERY
# ============================================================

def execute_dynamic_query(
    state: DynamicAgentState,
) -> DynamicAgentState:

    rows = state.get(
        "rows",
        []
    )

    intent = state.get(
        "intent",
        "general",
    )

    question = state.get(
        "question",
        "",
    )

    # ========================================================
    # NO DATA
    # ========================================================

    if not rows:

        state["result"] = {
            "success": False,
            "message": "No data found.",
        }

        return state

    # ========================================================
    # TOTAL SALES
    # ========================================================

    if intent == "total_sales":

        total = sum_column(
            rows,
            "Total Amount",
        )

        state["result"] = {
            "success": True,
            "total_sales": total,
        }

        return state

    # ========================================================
    # SALES COUNT
    # ========================================================

    if intent == "sales_count":

        count = count_rows(
            rows
        )

        state["result"] = {
            "success": True,
            "sales_count": count,
        }

        return state

    # ========================================================
    # INVOICE SEARCH
    # ========================================================

    if intent == "invoice_search":

        invoice_number = _extract_invoice_number(
            question
        )

        if not invoice_number:

            state["result"] = {
                "success": False,
                "invoice_number": None,
                "invoice": [],
            }

            return state

        invoice_rows = find_invoice(
            rows,
            invoice_number,
        )

        state["result"] = {
            "success": bool(invoice_rows),
            "invoice_number": invoice_number,
            "invoice": invoice_rows,
        }

        return state

    # ========================================================
    # CUSTOMER SALES
    # ========================================================

    if intent == "customer_sales":

        customer_name = _extract_customer_name(
            question
        )

        if not customer_name:

            state["result"] = {
                "success": False,
                "customer": None,
                "transactions": [],
                "total_sales": 0.0,
            }

            return state

        transactions = find_customer_transactions(
            rows,
            customer_name,
        )

        total = sum_column(
            transactions,
            "Total Amount",
        )

        state["result"] = {
            "success": bool(transactions),
            "customer": customer_name,
            "transactions": transactions,
            "total_sales": total,
        }

        return state

    # ========================================================
    # PRODUCT SALES
    # ========================================================

    if intent == "product_sales":

        product_sales = group_and_sum(
            rows,
            "Product",
            "Total Amount",
        )

        highest_product = (
            product_sales[0]
            if product_sales
            else None
        )

        state["result"] = {
            "success": bool(product_sales),
            "product_sales": product_sales,
            "highest_product": highest_product,
        }

        return state

    # ========================================================
    # COMPLETE SALES REPORT
    # ========================================================

    if intent == "sales_report":

        total = sum_column(
            rows,
            "Total Amount",
        )

        invoice_count = count_rows(
            rows
        )

        product_sales = group_and_sum(
            rows,
            "Product",
            "Total Amount",
        )

        highest_product = (
            product_sales[0]
            if product_sales
            else None
        )

        highest_transaction = highest_value(
            rows,
            "Total Amount",
        )

        state["result"] = {
            "success": True,
            "total_sales": total,
            "invoice_count": invoice_count,
            "product_sales": product_sales,
            "highest_product": highest_product,
            "highest_transaction": highest_transaction,
        }

        return state

    # ========================================================
    # GENERAL QUERY
    # ========================================================

    state["result"] = {
        "success": True,
        "rows": rows,
        "row_count": len(rows),
    }

    return state


# ============================================================
# FORMAT MONEY
# ============================================================

def _format_money(
    value: Any,
) -> str:

    try:

        return f"₹{float(value):,.2f}"

    except (
        ValueError,
        TypeError,
    ):

        return "₹0.00"


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_dynamic_answer(
    state: DynamicAgentState,
) -> DynamicAgentState:

    intent = state.get(
        "intent",
        "general",
    )

    result = state.get(
        "result",
        {},
    )

    # ========================================================
    # TOTAL SALES
    # ========================================================

    if intent == "total_sales":

        total = result.get(
            "total_sales",
            0.0,
        )

        state["answer"] = (
            f"Total sales: "
            f"{_format_money(total)}"
        )

        return state

    # ========================================================
    # SALES COUNT
    # ========================================================

    if intent == "sales_count":

        count = result.get(
            "sales_count",
            0,
        )

        state["answer"] = (
            f"Total sales transactions: {count}"
        )

        return state

    # ========================================================
    # INVOICE
    # ========================================================

    if intent == "invoice_search":

        invoice_number = result.get(
            "invoice_number"
        )

        invoices = result.get(
            "invoice",
            [],
        )

        if not invoice_number:

            state["answer"] = (
                "Please provide an invoice number "
                "such as INV103."
            )

            return state

        if not invoices:

            state["answer"] = (
                f"No invoice found for "
                f"{invoice_number}."
            )

            return state

        lines = [
            f"Invoice: {invoice_number}"
        ]

        lines.append(
            "--------------------"
        )

        for row in invoices:

            for key, value in row.items():

                lines.append(
                    f"{key}: {value}"
                )

            lines.append("")

        state["answer"] = "\n".join(
            lines
        )

        return state

    # ========================================================
    # CUSTOMER SALES
    # ========================================================

    if intent == "customer_sales":

        customer = result.get(
            "customer",
            "Unknown",
        )

        transactions = result.get(
            "transactions",
            [],
        )

        total = result.get(
            "total_sales",
            0.0,
        )

        if not transactions:

            state["answer"] = (
                f"No sales found for "
                f"{customer}."
            )

            return state

        lines = [
            f"Sales for {customer}:"
        ]

        for row in transactions:

            invoice = row.get(
                "Invoice No",
                row.get(
                    "Invoice Number",
                    "N/A",
                ),
            )

            product = row.get(
                "Product",
                "N/A",
            )

            amount = row.get(
                "Total Amount",
                0,
            )

            lines.append(
                f"- {invoice} | "
                f"{product} | "
                f"{_format_money(amount)}"
            )

        lines.append("")

        lines.append(
            f"Total sales: "
            f"{_format_money(total)}"
        )

        state["answer"] = "\n".join(
            lines
        )

        return state

    # ========================================================
    # PRODUCT SALES
    # ========================================================

    if intent == "product_sales":

        product_sales = result.get(
            "product_sales",
            [],
        )

        if not product_sales:

            state["answer"] = (
                "No product sales data found."
            )

            return state

        lines = [
            "Product-wise sales:"
        ]

        for item in product_sales:

            product = item.get(
                "group",
                "Unknown",
            )

            amount = item.get(
                "total",
                0.0,
            )

            lines.append(
                f"- {product}: "
                f"{_format_money(amount)}"
            )

        highest = product_sales[0]

        highest_product = highest.get(
            "group",
            "Unknown",
        )

        highest_amount = highest.get(
            "total",
            0.0,
        )

        lines.append("")

        lines.append(
            f"Highest sales: "
            f"{highest_product} "
            f"{_format_money(highest_amount)}"
        )

        state["answer"] = "\n".join(
            lines
        )

        return state

    # ========================================================
    # COMPLETE SALES REPORT
    # ========================================================

    if intent == "sales_report":

        total = result.get(
            "total_sales",
            0.0,
        )

        invoice_count = result.get(
            "invoice_count",
            0,
        )

        product_sales = result.get(
            "product_sales",
            [],
        )

        highest_product = result.get(
            "highest_product"
        )

        lines = [
            "Complete Sales Report",
            "=====================",
            "",
            f"Total Sales: "
            f"{_format_money(total)}",
            f"Total Invoices: "
            f"{invoice_count}",
            "",
            "Product-wise Sales:",
        ]

        for item in product_sales:

            product = item.get(
                "group",
                "Unknown",
            )

            amount = item.get(
                "total",
                0.0,
            )

            lines.append(
                f"- {product}: "
                f"{_format_money(amount)}"
            )

        if highest_product:

            product = highest_product.get(
                "group",
                "Unknown",
            )

            amount = highest_product.get(
                "total",
                0.0,
            )

            lines.append("")

            lines.append(
                f"Highest Selling Product: "
                f"{product} "
                f"({_format_money(amount)})"
            )

        state["answer"] = "\n".join(
            lines
        )

        return state

    # ========================================================
    # GENERAL
    # ========================================================

    rows = result.get(
        "rows",
        [],
    )

    if not rows:

        state["answer"] = (
            "No matching data found."
        )

        return state

    lines = [
        f"Found {len(rows)} records."
    ]

    for row in rows[:10]:

        values = []

        for key, value in row.items():

            values.append(
                f"{key}: {value}"
            )

        lines.append(
            " | ".join(values)
        )

    if len(rows) > 10:

        lines.append(
            f"... and {len(rows) - 10} more records."
        )

    state["answer"] = "\n".join(
        lines
    )

    return state