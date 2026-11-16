
import re
import unittest


# ============================================================
# QUERY UNDERSTANDING PROTOTYPE
# Independent testing only - no production code is modified.
# ============================================================

COLUMN_ALIASES = {
    "Qty": [
        "quantity",
        "units sold",
        "total units",
        "items sold",
        "volume sold",
    ],
    "UnitPrice": [
        "unit price",
        "product price",
        "selling price",
        "price per unit",
    ],
    "GrossAmount": [
        "gross sales",
        "gross billing",
        "sales revenue",
        "revenue",
        "sales",
    ],
    "Profit": [
        "net profit",
        "profit",
        "earnings",
    ],
    "Product": [
        "product name",
        "products",
        "product",
        "item",
    ],
    "PartyName": [
        "customer name",
        "customer",
        "party name",
        "buyer",
    ],
    "Date": [
        "invoice date",
        "date",
    ],
}


def normalize_query(question):
    """Normalize text while preserving word boundaries."""
    question = str(question or "").strip().lower()
    question = question.replace("₹", " rs ")
    question = re.sub(r"\s+", " ", question)
    return question.strip()

def resolve_column(question, available_columns):
    """Resolve a user phrase to an actual dataset column."""
    q = normalize_query(question)

    # Exact column names have priority.
    for column in available_columns:
        if column.lower() in q:
            return column

    # Alias matching.
    for column, aliases in COLUMN_ALIASES.items():
        if column not in available_columns:
            continue

        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(r"\b" + re.escape(alias) + r"\b", q):
                return column

    return None

def resolve_metric(question, available_columns):
    """Resolve calculation metric using semantic priority."""
    q = normalize_query(question)

    priority = [
        ("Qty", [
            "total quantity",
            "quantity sold",
            "units sold",
            "total units",
            "quantity",
            "units",
            "items sold",
        ]),
        ("Profit", [
            "net profit",
            "total profit",
            "profit",
            "earnings",
        ]),
        ("GrossAmount", [
            "gross sales",
            "sales revenue",
            "gross billing",
            "revenue",
            "sales",
        ]),
        ("TaxableAmount", [
            "taxable amount",
        ]),
        ("UnitPrice", [
            "unit price",
            "selling price",
            "price per unit",
            "product price",
        ]),
    ]

    for column, aliases in priority:
        if column not in available_columns:
            continue

        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", q):
                return column

    return None


def resolve_multiple_metrics(question, available_columns):
    """Resolve all requested metrics without duplicates."""

    q = normalize_query(question)

    metric_aliases = {
        "Qty": [
            "total quantity",
            "quantity sold",
            "total units",
            "units sold",
            "quantity",
            "units"
        ],
        "Profit": [
            "total profit",
            "net profit",
            "profit",
            "earnings"
        ],
        "GrossAmount": [
            "total sales",
            "gross sales",
            "sales revenue",
            "gross billing",
            "revenue",
            "sales"
        ],
        "TaxableAmount": [
            "taxable amount"
        ]
    }

    resolved = []

    for column, aliases in metric_aliases.items():
        if column not in available_columns:
            continue

        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(
                r"\b" + re.escape(alias) + r"\b",
                q
            ):
                resolved.append(column)
                break

    return resolved


def resolve_ranking_metric(question, metrics):
    """Resolve ranking metric only when explicitly identifiable."""

    if not metrics:
        return None

    q = normalize_query(question)

    metric_aliases = {
        "Qty": [
            "total quantity",
            "quantity sold",
            "highest quantity",
            "quantity",
            "qty",
            "units sold",
            "units",
        ],
        "Profit": [
            "total profit",
            "net profit",
            "profit",
            "earnings",
        ],
        "GrossAmount": [
            "total sales",
            "gross sales",
            "sales revenue",
            "gross billing",
            "revenue",
            "sales",
        ],
        "TaxableAmount": [
            "taxable amount",
        ],
    }

    # Explicit "by profit", "by sales", etc.
    by_match = re.search(
        r"\bby\s+"
        r"(total\s+quantity|quantity|qty|units|"
        r"net\s+profit|total\s+profit|profit|"
        r"total\s+sales|gross\s+sales|revenue|sales)\b",
        q
    )

    if by_match:
        phrase = by_match.group(1)

        for metric, aliases in metric_aliases.items():
            if metric in metrics and phrase in aliases:
                return metric

    # Find ranking keyword.
    ranking_match = re.search(
        r"\b(top|highest|lowest|most|least|maximum|minimum)\b",
        q
    )

    if not ranking_match:
        return metrics[0] if len(metrics) == 1 else None

    # Only inspect the text immediately after ranking keyword.
    tail = q[ranking_match.end():].strip()

    # Remove harmless qualifiers.
    tail = re.sub(
        r"^(?:total|net|gross|average|avg|mean)\s+",
        "",
        tail
    )

    candidates = []

    for metric, aliases in metric_aliases.items():
        if metric not in metrics:
            continue

        for alias in sorted(aliases, key=len, reverse=True):
            if re.match(
                r"^" + re.escape(alias) + r"\b",
                tail
            ):
                candidates.append((len(alias), metric))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]

    # No explicit ranking metric: do not guess.
    return metrics[0] if len(metrics) == 1 else None


def detect_intent(question):
    """Detect the primary query intent with ranking priority."""

    q = normalize_query(question)

    # 1. Comparison
    if re.search(r"\b(compare|comparison|versus|vs)\b", q):
        return "comparison"

    # 2. Ranking: explicit ranking words + measurable metric.
    # A numeric filter should not override ranking intent.
    has_ranking = re.search(
        r"\b(top|highest|lowest|maximum|minimum|most|least)\b",
        q,
    )

    has_metric = re.search(
        r"\b(sales|revenue|profit|quantity|qty|units|"
        r"billing|amount)\b",
        q,
    )

    if has_ranking and has_metric:
        return "ranking"

    # 3. Ratio / percentage
    if re.search(
        r"\b(ratio|percentage|percent|margin|share)\b",
        q,
    ):
        return "ratio_or_percentage"

    # 4. Distinct count
    if re.search(
        r"\b(distinct|unique|how many different)\b",
        q,
    ):
        return "distinct_count"

    # 5. Group aggregate
    if re.search(
        r"\b(month-wise|state-wise|category-wise|product-wise)\b",
        q,
    ):
        return "group_aggregate"

    # 6. Aggregate
    if re.search(r"\b(total|sum|average|avg|mean)\b", q):
        return "aggregate"

    # 7. Simple filters
    if re.search(
        r"\b(show|find|filter|where|greater than|less than)\b",
        q,
    ):
        return "filter"

    return "unknown"



def extract_numeric_filter(question, available_columns):
    """Resolve the column immediately before a comparison operator."""
    q = normalize_query(question)
    q = re.sub(
        r"\s+is(?=\s*(?:greater than|more than|above|over|>|less than|below|under|<))",
        "",
        q,
    )

    pattern = (
        r"\b(greater than|more than|above|over|>|"
        r"less than|below|under|<)\s*"
        r"(?:rs\s*)?([0-9,]+(?:\.[0-9]+)?)"
    )

    match = re.search(pattern, q)

    if not match:
        return None

    left_context = q[:match.start()].strip()
    operator_text = match.group(1)
    value = float(match.group(2).replace(",", ""))

    # Only match aliases at the END of the text before the operator.
    candidates = []

    for column in available_columns:
        aliases = COLUMN_ALIASES.get(column, [])
        aliases = aliases + [column.lower()]

        for alias in aliases:
            alias = alias.lower().strip()

            if left_context.endswith(alias):
                candidates.append((len(alias), column))

    if not candidates:
        return None

    # Longest matching suffix wins.
    candidates.sort(reverse=True)
    column = candidates[0][1]

    operator = (
        ">"
        if operator_text in [
            "greater than", "more than", "above", "over", ">"
        ]
        else "<"
    )

    return {
        "column": column,
        "operator": operator,
        "value": value,
    }


def extract_numeric_filters(question, available_columns):
    """Extract multiple numeric filters from one question."""
    q = normalize_query(question)
    q = re.sub(
        r"\s+is(?=\s*(?:greater than|more than|above|over|>|less than|below|under|<))",
        "",
        q,
    )

    pattern = (
        r"\b(greater than|more than|above|over|>|"
        r"less than|below|under|<)\s*"
        r"(?:rs\s*)?([0-9,]+(?:\.[0-9]+)?)"
    )

    results = []

    for match in re.finditer(pattern, q):
        left_context = q[:match.start()].strip()
        operator_text = match.group(1)
        value = float(match.group(2).replace(",", ""))

        candidates = []

        for column in available_columns:
            aliases = COLUMN_ALIASES.get(column, [])
            aliases = aliases + [column.lower()]

            for alias in aliases:
                alias = alias.lower().strip()

                if left_context.endswith(alias):
                    candidates.append((len(alias), column))

        if not candidates:
            continue

        candidates.sort(reverse=True)
        column = candidates[0][1]

        operator = (
            ">"
            if operator_text in [
                "greater than", "more than", "above", "over", ">"
            ]
            else "<"
        )

        results.append({
            "column": column,
            "operator": operator,
            "value": value
        })

    return results



from datetime import date
import calendar



def extract_date_filter(question, available_columns):
    """Extract month, financial quarter and financial year."""

    if "Date" not in available_columns:
        return None

    q = normalize_query(question)

    # 1. Month: March 2026
    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|"
        r"august|september|october|november|december)"
        r"\s+(\d{4})\b",
        q
    )

    if month_match:
        month_name = month_match.group(1)
        year = int(month_match.group(2))
        month = list(calendar.month_name).index(
            month_name.capitalize()
        )
        last_day = calendar.monthrange(year, month)[1]

        return {
            "column": "Date",
            "period_type": "month",
            "start_date": f"{year}-{month:02d}-01",
            "end_date": f"{year}-{month:02d}-{last_day:02d}"
        }

    # 2. Financial Quarter: Q3 FY 2025-26
    # IMPORTANT: Check quarter before financial year.
    quarter_match = re.search(
        r"\bq([1-4])\s*fy\s*(\d{4})\s*[-/]?\s*(?:\d{2,4})?\b",
        q
    )

    if quarter_match:
        quarter = int(quarter_match.group(1))
        start_year = int(quarter_match.group(2))

        periods = {
            1: (start_year, 4, start_year, 6),
            2: (start_year, 7, start_year, 9),
            3: (start_year, 10, start_year, 12),
            4: (start_year + 1, 1, start_year + 1, 3)
        }

        sy, sm, ey, em = periods[quarter]
        last_day = calendar.monthrange(ey, em)[1]

        return {
            "column": "Date",
            "period_type": "financial_quarter",
            "start_date": f"{sy}-{sm:02d}-01",
            "end_date": f"{ey}-{em:02d}-{last_day:02d}"
        }

    # 3. Financial Year: FY 2025-26
    fy_match = re.search(
        r"\bfy\s*(\d{4})\s*[-/]\s*(\d{2,4})\b",
        q
    )

    if fy_match:
        start_year = int(fy_match.group(1))

        return {
            "column": "Date",
            "period_type": "financial_year",
            "start_date": f"{start_year}-04-01",
            "end_date": f"{start_year + 1}-03-31"
        }

    return None




def build_query_plan(question, available_columns):
    """Build a query plan with multiple numeric and date filters."""

    q = normalize_query(question)

    numeric_filters = extract_numeric_filters(
        q, available_columns
    )

    date_filter = extract_date_filter(
        q, available_columns
    )

    metric_question = q

    for numeric_filter in numeric_filters:
        aliases = COLUMN_ALIASES.get(
            numeric_filter["column"], []
        )
        aliases = aliases + [
            numeric_filter["column"].lower()
        ]

        aliases = sorted(set(aliases), key=len, reverse=True)

        alias_pattern = "|".join(
            re.escape(alias) for alias in aliases
        )

        operator_pattern = (
            r"greater than|more than|above|over|>|"
            r"less than|below|under|<"
        )

        filter_pattern = (
            r"(?:"
            + alias_pattern
            + r")(?:\s+is)?\s*(?:"
            + operator_pattern
            + r")\s*(?:rs\s*)?[0-9,]+(?:\.[0-9]+)?"
        )

        metric_question = re.sub(
            filter_pattern,
            " ",
            metric_question,
            count=1
        )

    intent = detect_intent(q)

    metric = resolve_metric(
        metric_question,
        available_columns
    )
    metrics = resolve_multiple_metrics(
        metric_question,
        available_columns
    )

    if not metrics and metric:
        metrics = [metric]
    group_by = None

    if re.search(r"\b(product|products|item)\b", q):
        if "Product" in available_columns:
            group_by = "Product"

    elif re.search(r"\b(customer|customers|buyer|buyers)\b", q):
        group_by = resolve_column("customer", available_columns)

    elif re.search(r"\b(category|categories)\b", q):
        group_by = resolve_column("category", available_columns)

    elif re.search(r"\b(state|states)\b", q):
        group_by = resolve_column("state", available_columns)

    # Implicit product ranking:
    # "highest sales", "top 5 by profit", etc.
    elif (
        re.search(r"\b(top|highest|lowest|most|least|maximum|minimum)\b", q)
        and re.search(r"\b(sales|revenue|profit|quantity|units)\b", q)
        and "Product" in available_columns
    ):
        group_by = "Product"

    operation = None

    if re.search(r"\b(average|avg|mean)\b", metric_question):
        operation = "average"

    elif metric and re.search(
        r"\b(total|sum|quantity|units)\b",
        metric_question
    ):
        operation = "sum"

    # Resolve operation independently for every requested metric.
    metric_operations = {}

    for current_metric in metrics:
        metric_operations[current_metric] = "sum"

    if re.search(r"\b(average|avg|mean)\b", metric_question):
        average_patterns = {
            "Profit": r"\b(average|avg|mean)\s+(?:net\s+)?profit\b",
            "GrossAmount": r"\b(average|avg|mean)\s+(?:gross\s+)?(sales|revenue|billing)\b",
            "Qty": r"\b(average|avg|mean)\s+(quantity|qty|units)\b",
            "TaxableAmount": r"\b(average|avg|mean)\s+taxable\s+amount\b",
        }

        for current_metric, pattern in average_patterns.items():
            if current_metric in metric_operations and re.search(pattern, metric_question):
                metric_operations[current_metric] = "average"

    ranking = (
        "descending"
        if re.search(
            r"\b(top|highest|lowest|most|least|maximum|minimum)\b",
            q
        )
        else None
    )

    ranking_metric = (
        resolve_ranking_metric(metric_question, metrics)
        if ranking
        else None
    )

    limit_match = re.search(r"\btop\s+(\d+)\b", q)

    limit = (
        int(limit_match.group(1))
        if limit_match
        else (1 if ranking else None)
    )

    return {
        "intent": intent,
        "metric": metric,
        "metrics": metrics,
        "operation": operation,
        "metric_operations": metric_operations,
        "group_by": group_by,
        "filters": numeric_filters,
        "date_filter": date_filter,
        "ranking": ranking,
        "ranking_metric": ranking_metric,
        "limit": limit
        
    }



def resolve_followup_context(previous_plan, followup_question, available_columns):
    """Resolve a follow-up while retaining the previous query context."""

    q = normalize_query(followup_question)

    if not previous_plan:
        return build_query_plan(followup_question, available_columns)

    new_plan = dict(previous_plan)

    # Copy mutable fields to avoid modifying the original plan.
    new_plan["metrics"] = list(previous_plan.get("metrics", []))
    new_plan["filters"] = list(previous_plan.get("filters", []))
    new_plan["metric_operations"] = dict(
        previous_plan.get("metric_operations", {})
    )

    if previous_plan.get("date_filter"):
        new_plan["date_filter"] = dict(previous_plan["date_filter"])

    # New date mentioned: replace previous date filter.
    new_date_filter = extract_date_filter(q, available_columns)

    if new_date_filter:
        new_plan["date_filter"] = new_date_filter

    # Explicit request to show top N.
    top_match = re.search(r"\btop\s+(\d+)\b", q)

    if top_match:
        new_plan["limit"] = int(top_match.group(1))

    # Retain ranking unless explicitly changed.
    if re.search(r"\b(lowest|least|minimum)\b", q):
        new_plan["ranking"] = "ascending"
    elif re.search(r"\b(highest|most|maximum|top)\b", q):
        new_plan["ranking"] = "descending"

    # Resolve a newly requested metric.
    new_metrics = resolve_multiple_metrics(q, available_columns)
    new_metric = resolve_metric(q, available_columns)

    if new_metrics:
        new_plan["metrics"] = new_metrics
        new_plan["metric"] = new_metric or new_metrics[0]

        new_plan["metric_operations"] = {
            metric: "sum" for metric in new_metrics
        }

    elif new_metric:
        new_plan["metric"] = new_metric
        new_plan["metrics"] = [new_metric]
        new_plan["metric_operations"] = {
            new_metric: "sum"
        }

    # Explicit ranking metric in follow-up.
    if new_plan.get("ranking"):
        ranking_metric = resolve_ranking_metric(
            q,
            new_plan["metrics"]
        )

        if ranking_metric:
            new_plan["ranking_metric"] = ranking_metric

    # Explicit grouping requested in the follow-up.
    if re.search(r"\b(product|products|item|items)\b", q):
        if "Product" in available_columns:
            new_plan["group_by"] = "Product"

    elif re.search(r"\b(customer|customers|buyer|buyers)\b", q):
        column = resolve_column("customer", available_columns)
        if column:
            new_plan["group_by"] = column

    elif re.search(r"\b(category|categories)\b", q):
        column = resolve_column("category", available_columns)
        if column:
            new_plan["group_by"] = column

    elif re.search(r"\b(state|states)\b", q):
        column = resolve_column("state", available_columns)
        if column:
            new_plan["group_by"] = column

    # Follow-up asks for another metric of the same entity.
    elif re.search(r"\b(its|their|same|that)\b", q):
        new_plan["group_by"] = previous_plan.get("group_by")

    # Preserve original filters and group when follow-up
    # does not explicitly replace them.
    new_plan["intent"] = (
        "ranking" if new_plan.get("ranking")
        else previous_plan.get("intent")
    )

    return new_plan

import calendar
from datetime import date


def _make_month_period(year, month, column="Date"):
    """Create a standard monthly date-filter dictionary."""
    last_day = calendar.monthrange(year, month)[1]

    return {
        "column": column,
        "period_type": "month",
        "start_date": f"{year}-{month:02d}-01",
        "end_date": f"{year}-{month:02d}-{last_day:02d}",
    }


def _shift_month(year, month, offset):
    """Shift a year/month pair by a number of months."""
    total = (year * 12) + (month - 1) + offset
    return total // 12, (total % 12) + 1


def resolve_comparative_followup_context(
    previous_plan,
    followup_question,
    available_columns,
):
    """
    Resolve comparison follow-ups while preserving previous query context.

    Supports:
    - Compare with previous month.
    - Compare with same month last year.
    - Compare multiple explicitly named months.
    - Percentage difference after a comparison was established.
    """

    plan = resolve_followup_context(
        previous_plan,
        followup_question,
        available_columns,
    )

    q = normalize_query(followup_question)

    previous_periods = previous_plan.get("comparison_periods", [])
    plan["comparison_periods"] = [
        dict(period) for period in previous_periods
    ]

    date_filter = previous_plan.get("date_filter")

    if not date_filter or "Date" not in available_columns:
        # A percentage follow-up can still refer to an existing comparison.
        if re.search(r"\b(percent|percentage|difference|change)\b", q):
            if previous_periods:
                plan["intent"] = "comparison"
                plan["comparison_type"] = "percentage_change"
        return plan

    try:
        base_start = date.fromisoformat(date_filter["start_date"])
    except (KeyError, TypeError, ValueError):
        return plan

    base_period = dict(date_filter)

    wants_percentage = bool(
        re.search(r"\b(percent|percentage|difference|change)\b", q)
    )

    # Case 1: Compare with previous month.
    if re.search(
        r"\b(previous|last|preceding)\s+month\b",
        q,
    ):
        year, month = _shift_month(
            base_start.year,
            base_start.month,
            -1,
        )

        comparison_period = _make_month_period(
            year,
            month,
            date_filter.get("column", "Date"),
        )

        plan["intent"] = "comparison"
        plan["comparison_type"] = (
            "percentage_change" if wants_percentage
            else "period_comparison"
        )
        plan["comparison_periods"] = [
            base_period,
            comparison_period,
        ]

        return plan

    # Case 2: Compare with the same month last year.
    if re.search(
        r"\b(same\s+month|corresponding\s+month)\b.*"
        r"\b(last\s+year|previous\s+year|prior\s+year)\b",
        q,
    ) or re.search(
        r"\b(last\s+year|previous\s+year|prior\s+year)\b.*"
        r"\b(same\s+month|corresponding\s+month)\b",
        q,
    ):
        comparison_period = _make_month_period(
            base_start.year - 1,
            base_start.month,
            date_filter.get("column", "Date"),
        )

        plan["intent"] = "comparison"
        plan["comparison_type"] = "year_over_year"
        plan["comparison_periods"] = [
            base_period,
            comparison_period,
        ]

        return plan

    # Case 3: Compare explicitly named months.
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

    found_months = []

    for month_name, month_number in month_names.items():
        if re.search(rf"\b{month_name}\b", q):
            found_months.append((month_number, month_name))

    if (
        re.search(r"\b(compare|comparison|versus|vs)\b", q)
        and len(found_months) >= 2
    ):
        found_months.sort(key=lambda item: item[0])

        periods = []

        for month_number, _ in found_months:
            periods.append(
                _make_month_period(
                    base_start.year,
                    month_number,
                    date_filter.get("column", "Date"),
                )
            )

        plan["intent"] = "comparison"
        plan["comparison_type"] = "multi_period_comparison"
        plan["comparison_periods"] = periods

        return plan

    # Case 4: Percentage difference after a comparison.
    if re.search(
        r"\b(percent|percentage|difference|change)\b",
        q,
    ) and previous_periods:
        plan["intent"] = "comparison"
        plan["comparison_type"] = "percentage_change"
        plan["comparison_periods"] = [
            dict(period) for period in previous_periods
        ]

    return plan
def calculate_period_comparison(current, previous):
    """
    Compare current and previous period values.
    Supports numeric values and handles missing/zero values safely.
    """

    if current is None or previous is None:
        return {
            "status": "missing_data",
            "difference": None,
            "percentage_change": None,
        }

    current = float(current)
    previous = float(previous)

    difference = current - previous

    if previous == 0:
        percentage_change = None
        percentage_status = "undefined_zero_baseline"
    else:
        percentage_change = (difference / abs(previous)) * 100
        percentage_status = "calculated"

    return {
        "status": "success",
        "current": current,
        "previous": previous,
        "difference": round(difference, 2),
        "percentage_change": (
            round(percentage_change, 2)
            if percentage_change is not None
            else None
        ),
        "percentage_status": percentage_status,
        "trend": (
            "increase" if difference > 0
            else "decrease" if difference < 0
            else "unchanged"
        ),
    }


def calculate_multi_metric_comparison(current, previous):
    """
    Compare multiple metrics independently.
    """

    results = {}

    for metric, current_value in current.items():
        previous_value = previous.get(metric)

        results[metric] = calculate_period_comparison(
            current_value,
            previous_value,
        )

    return results
# ============================================================
# TEST CASES
# ============================================================

class TestQueryUnderstanding(unittest.TestCase):

    columns = [
        "InvoiceNo",
        "Date",
        "PartyName",
        "Category",
        "Product",
        "Qty",
        "UnitPrice",
        "GrossAmount",
        "Profit",
        "TaxableAmount",
    ]

    def test_unit_price_alias(self):
        self.assertEqual(
            resolve_column("unit price", self.columns),
            "UnitPrice",
        )

    def test_quantity_alias(self):
        self.assertEqual(
            resolve_column("units sold", self.columns),
            "Qty",
        )

    def test_revenue_alias(self):
        self.assertEqual(
            resolve_column("sales revenue", self.columns),
            "GrossAmount",
        )

    def test_ranking_intent(self):
        self.assertEqual(
            detect_intent("Which product has the highest sales?"),
            "ranking",
        )

    def test_comparison_intent(self):
        self.assertEqual(
            detect_intent("Compare sales in 2025 vs 2026"),
            "comparison",
        )

    def test_ratio_intent(self):
        self.assertEqual(
            detect_intent("What is the profit margin percentage?"),
            "ratio_or_percentage",
        )

    def test_numeric_greater_than_filter(self):
        result = extract_numeric_filter(
            "unit price greater than 1500",
            self.columns,
        )

        self.assertEqual(
            result,
            {
                "column": "UnitPrice",
                "operator": ">",
                "value": 1500.0,
            },
        )

    def test_numeric_less_than_filter(self):
        result = extract_numeric_filter(
            "unit price less than 2000",
            self.columns,
        )

        self.assertEqual(result["operator"], "<")
        self.assertEqual(result["value"], 2000.0)

    def test_complete_ranking_query_plan(self):
        result = build_query_plan(
            "Which product recorded the highest total quantity "
            "sold where unit price greater than 1500?",
            self.columns,
        )

        self.assertEqual(result["intent"], "ranking")
        self.assertEqual(result["metric"], "Qty")
        self.assertEqual(result["operation"], "sum")
        self.assertEqual(result["group_by"], "Product")
        self.assertEqual(result["ranking"], "descending")
        self.assertEqual(result["limit"], 1)
        self.assertEqual(
            result["filters"][0]["column"],
            "UnitPrice",
        )
        

    def test_missing_column_does_not_guess(self):
        result = resolve_column(
            "employee salary",
            self.columns,
        )
        self.assertIsNone(result)
        
    def test_quantity_sold_with_unit_price_filter(self):
        columns = [
            "Product", "Qty", "UnitPrice",
            "GrossAmount", "Profit"
        ]
        question = (
            "Which product recorded the highest total quantity "
            "sold where unit price greater than 1500?"
        )

        plan = build_query_plan(question, columns)

        self.assertEqual(plan["metric"], "Qty")
        self.assertEqual(plan["group_by"], "Product")
        self.assertEqual(plan["filters"][0]["column"], "UnitPrice")
        self.assertEqual(plan["filters"][0]["operator"], ">")
        self.assertEqual(plan["filters"][0]["value"], 1500.0)

    def test_quantity_with_less_than_filter(self):
        columns = ["Product", "Qty", "UnitPrice"]
        question = "Top product by quantity where unit price below 1000"

        plan = build_query_plan(question, columns)

        self.assertEqual(plan["metric"], "Qty")
        self.assertEqual(plan["filters"][0]["column"], "UnitPrice")
        self.assertEqual(plan["filters"][0]["operator"], "<")

    def test_profit_ranking(self):
        columns = ["Product", "Qty", "Profit", "GrossAmount"]
        plan = build_query_plan(
            "Which product has highest total profit?",
            columns
        )

        self.assertEqual(plan["metric"], "Profit")
        self.assertEqual(plan["group_by"], "Product")
        self.assertEqual(plan["operation"], "sum")

    def test_revenue_ranking(self):
        columns = ["Product", "Qty", "GrossAmount", "Profit"]
        plan = build_query_plan(
            "Which product has highest total sales?",
            columns
        )

        self.assertEqual(plan["metric"], "GrossAmount")
        self.assertEqual(plan["group_by"], "Product")

    def test_filter_and_metric_are_separate(self):
        columns = ["Product", "Qty", "UnitPrice"]
        question = "Highest quantity sold for products with unit price above 2000"

        plan = build_query_plan(question, columns)

        self.assertEqual(plan["metric"], "Qty")
        self.assertEqual(plan["filters"][0]["column"], "UnitPrice")

    def test_multiple_numeric_filters(self):
        question = (
            "Which product has highest quantity "
            "where unit price above 1500 "
            "and quantity greater than 5?"
        )

        plan = build_query_plan(question, self.columns)

        self.assertEqual(len(plan["filters"]), 2)
        self.assertEqual(
            plan["filters"][0]["column"], "UnitPrice"
        )
        self.assertEqual(
            plan["filters"][1]["column"], "Qty"
        )

    def test_march_2026_date_filter(self):
        result = extract_date_filter(
            "Show sales in March 2026",
            self.columns
        )

        self.assertEqual(result["start_date"], "2026-03-01")
        self.assertEqual(result["end_date"], "2026-03-31")

    def test_financial_year_filter(self):
        result = extract_date_filter(
            "Show total sales in FY 2025-26",
            self.columns
        )

        self.assertEqual(result["start_date"], "2025-04-01")
        self.assertEqual(result["end_date"], "2026-03-31")

    def test_financial_quarter_filter(self):
        result = extract_date_filter(
            "Show profit in Q3 FY 2025-26",
            self.columns
        )

        self.assertEqual(result["start_date"], "2025-10-01")
        self.assertEqual(result["end_date"], "2025-12-31")

    def test_date_filter_without_date_column(self):
        result = extract_date_filter(
            "Show sales in March 2026",
            ["Product", "Qty", "GrossAmount"]
        )

        self.assertIsNone(result)
    
    def test_q1_financial_quarter(self):
        result = extract_date_filter(
            "Sales in Q1 FY 2025-26",
            self.columns
        )
        self.assertEqual(result["start_date"], "2025-04-01")
        self.assertEqual(result["end_date"], "2025-06-30")

    def test_q2_financial_quarter(self):
        result = extract_date_filter(
            "Sales in Q2 FY 2025-26",
            self.columns
        )
        self.assertEqual(result["start_date"], "2025-07-01")
        self.assertEqual(result["end_date"], "2025-09-30")

    def test_q4_financial_quarter(self):
        result = extract_date_filter(
            "Sales in Q4 FY 2025-26",
            self.columns
        )
        self.assertEqual(result["start_date"], "2026-01-01")
        self.assertEqual(result["end_date"], "2026-03-31")

    def test_multiple_sales_profit_metrics(self):
        result = resolve_multiple_metrics(
            "total sales and total profit",
            self.columns
        )
        self.assertEqual(
            result,
            ["Profit", "GrossAmount"]
        )

    def test_sales_profit_quantity_metrics(self):
        result = resolve_multiple_metrics(
            "total sales, profit and quantity",
            self.columns
        )
        self.assertEqual(
            result,
            ["Qty", "Profit", "GrossAmount"]
        )

    def test_quantity_and_sales_metrics(self):
        result = resolve_multiple_metrics(
            "total quantity and sales",
            self.columns
        )
        self.assertEqual(
            result,
            ["Qty", "GrossAmount"]
        )

    def test_average_profit_and_total_sales(self):
        result = resolve_multiple_metrics(
            "average profit and total sales",
            self.columns
        )
        self.assertEqual(
            result,
            ["Profit", "GrossAmount"]
        )

    def test_missing_metric_column_is_ignored(self):
        columns = ["Product", "Qty", "GrossAmount"]

        result = resolve_multiple_metrics(
            "total sales, profit and quantity",
            columns
        )

        self.assertEqual(
            result,
            ["Qty", "GrossAmount"]
        )

    def test_plan_with_sales_and_profit(self):
        plan = build_query_plan(
            "show total sales and total profit",
            self.columns
        )
        self.assertEqual(
            set(plan["metrics"]),
            {"GrossAmount", "Profit"}
        )

    def test_plan_with_three_metrics(self):
        plan = build_query_plan(
            "show total sales, profit and quantity",
            self.columns
        )
        self.assertEqual(
            set(plan["metrics"]),
            {"GrossAmount", "Profit", "Qty"}
        )

    def test_plan_with_quantity_and_sales(self):
        plan = build_query_plan(
            "show total quantity and sales",
            self.columns
        )
        self.assertEqual(
            set(plan["metrics"]),
            {"Qty", "GrossAmount"}
        )

    def test_plan_with_average_profit_and_sales(self):
        plan = build_query_plan(
            "average profit and total sales",
            self.columns
        )
        self.assertEqual(
            set(plan["metrics"]),
            {"Profit", "GrossAmount"}
        )

    def test_plan_multiple_metrics_with_date_filter(self):
        plan = build_query_plan(
            "show total sales and profit in Q3 FY 2025-26",
            self.columns
        )
        self.assertEqual(
            set(plan["metrics"]),
            {"GrossAmount", "Profit"}
        )
        self.assertEqual(
            plan["date_filter"]["start_date"],
            "2025-10-01"
        )
        self.assertEqual(
            plan["date_filter"]["end_date"],
            "2025-12-31"
        )
    def test_average_profit_and_total_sales_operations(self):
        plan = build_query_plan(
            "average profit and total sales",
            self.columns
        )

        self.assertEqual(
            plan["metric_operations"]["Profit"],
            "average"
        )
        self.assertEqual(
            plan["metric_operations"]["GrossAmount"],
            "sum"
        )

    def test_total_sales_and_average_profit_operations(self):
        plan = build_query_plan(
            "total sales and average profit",
            self.columns
        )

        self.assertEqual(
            plan["metric_operations"]["GrossAmount"],
            "sum"
        )
        self.assertEqual(
            plan["metric_operations"]["Profit"],
            "average"
        )

    def test_average_quantity_and_total_profit(self):
        plan = build_query_plan(
            "average quantity and total profit",
            self.columns
        )

        self.assertEqual(
            plan["metric_operations"]["Qty"],
            "average"
        )
        self.assertEqual(
            plan["metric_operations"]["Profit"],
            "sum"
        )

    def test_all_total_metrics_use_sum(self):
        plan = build_query_plan(
            "total sales, total profit and total quantity",
            self.columns
        )

        self.assertEqual(
            set(plan["metric_operations"].values()),
            {"sum"}
        )

    def test_single_average_profit_operation(self):
        plan = build_query_plan(
            "average profit",
            self.columns
        )

        self.assertEqual(
            plan["metric_operations"]["Profit"],
            "average"
        )
    # ========================================================
    # COMPOUND QUERY TESTS
    # ========================================================

    def test_compound_sales_profit_with_unit_price_filter(self):
        plan = build_query_plan(
            "show total sales and profit for products "
            "where unit price is greater than 1500",
            self.columns
        )

        self.assertEqual(
            set(plan["metrics"]),
            {"GrossAmount", "Profit"}
        )

        self.assertEqual(
            plan["filters"],
            [{
                "column": "UnitPrice",
                "operator": ">",
                "value": 1500.0
            }]
        )

    def test_quantity_sales_with_quarter_filter(self):
        plan = build_query_plan(
            "which product has highest quantity and total sales "
            "in Q3 FY 2025-26",
            self.columns
        )

        self.assertEqual(
            set(plan["metrics"]),
            {"Qty", "GrossAmount"}
        )

        self.assertEqual(plan["group_by"], "Product")
        self.assertEqual(plan["ranking"], "descending")

        self.assertEqual(
            plan["date_filter"]["start_date"],
            "2025-10-01"
        )

        self.assertEqual(
            plan["date_filter"]["end_date"],
            "2025-12-31"
        )

    def test_average_profit_sales_with_category_and_month(self):
        plan = build_query_plan(
            "show average profit and total sales "
            "for Bags category in March 2026",
            self.columns
        )

        self.assertEqual(
            set(plan["metrics"]),
            {"Profit", "GrossAmount"}
        )

        self.assertEqual(
            plan["metric_operations"]["Profit"],
            "average"
        )

        self.assertEqual(
            plan["metric_operations"]["GrossAmount"],
            "sum"
        )

        self.assertEqual(plan["group_by"], "Category")

        self.assertEqual(
            plan["date_filter"]["start_date"],
            "2026-03-01"
        )

        self.assertEqual(
            plan["date_filter"]["end_date"],
            "2026-03-31"
        )

    def test_three_metrics_with_two_numeric_filters(self):
        plan = build_query_plan(
            "show total sales, profit and quantity "
            "where unit price is greater than 1000 "
            "and quantity is less than 10",
            self.columns
        )

        self.assertEqual(
            set(plan["metrics"]),
            {"GrossAmount", "Profit", "Qty"}
        )

        self.assertEqual(len(plan["filters"]), 2)

        filters = {
            item["column"]: item
            for item in plan["filters"]
        }

        self.assertEqual(
            filters["UnitPrice"]["operator"],
            ">"
        )

        self.assertEqual(
            filters["UnitPrice"]["value"],
            1000.0
        )

        self.assertEqual(
            filters["Qty"]["operator"],
            "<"
        )

        self.assertEqual(
            filters["Qty"]["value"],
            10.0
        )

    def test_highest_quantity_sales_with_date_filter(self):
        plan = build_query_plan(
            "which product has highest total quantity and sales "
            "in March 2026",
            self.columns
        )

        self.assertEqual(plan["group_by"], "Product")
        self.assertEqual(plan["ranking"], "descending")
        self.assertEqual(plan["limit"], 1)

        self.assertEqual(
            set(plan["metrics"]),
            {"Qty", "GrossAmount"}
        )

        self.assertEqual(
            plan["date_filter"]["start_date"],
            "2026-03-01"
        )

        self.assertEqual(
            plan["date_filter"]["end_date"],
            "2026-03-31"
        )


    def test_ranking_by_quantity_in_compound_query(self):
        plan = build_query_plan(
            "Which product has highest quantity and total sales in March 2026?",
            self.columns
        )

        self.assertEqual(plan["ranking"], "descending")
        self.assertEqual(plan["ranking_metric"], "Qty")
        self.assertEqual(plan["group_by"], "Product")
        self.assertEqual(
            set(plan["metrics"]),
            {"Qty", "GrossAmount"}
        )


    def test_ranking_by_profit_with_multiple_metrics(self):
        columns = ["Product", "Profit", "GrossAmount", "Qty"]

        plan = build_query_plan(
            "Show top 5 products by profit and sales",
            columns
        )

        self.assertEqual(plan["ranking_metric"], "Profit")
        self.assertEqual(plan["limit"], 5)


    def test_ranking_by_sales_with_average_profit(self):
        columns = ["Product", "Profit", "GrossAmount", "Qty"]

        plan = build_query_plan(
            "Which product has highest sales and average profit?",
            columns
        )

        self.assertEqual(plan["ranking_metric"], "GrossAmount")


    def test_single_metric_ranking(self):
        columns = ["Product", "Profit", "GrossAmount"]

        plan = build_query_plan(
            "Which product has highest total profit?",
            columns
        )

        self.assertEqual(plan["ranking_metric"], "Profit")


    def test_ambiguous_multi_metric_ranking(self):
        columns = ["Product", "Profit", "GrossAmount", "Qty"]

        plan = build_query_plan(
            "Show highest product with sales, profit and quantity",
            columns
        )

        self.assertIsNone(plan["ranking_metric"])

    def test_followup_retains_previous_date_and_group(self):
        previous = build_query_plan(
            "Which product has highest quantity and sales in March 2026?",
            self.columns
        )

        result = resolve_followup_context(
            previous,
            "Show its profit",
            self.columns
        )

        self.assertEqual(result["group_by"], "Product")
        self.assertEqual(result["date_filter"]["start_date"], "2026-03-01")
        self.assertEqual(result["metrics"], ["Profit"])


    def test_followup_changes_month_only(self):
        previous = build_query_plan(
            "Which product has highest quantity in March 2026?",
            self.columns
        )

        result = resolve_followup_context(
            previous,
            "What about February 2026?",
            self.columns
        )

        self.assertEqual(result["date_filter"]["start_date"], "2026-02-01")
        self.assertEqual(result["date_filter"]["end_date"], "2026-02-28")
        self.assertEqual(result["group_by"], "Product")


    def test_followup_changes_top_limit(self):
        previous = build_query_plan(
            "Which product has highest total profit?",
            self.columns
        )

        result = resolve_followup_context(
            previous,
            "Show top 5 instead",
            self.columns
        )

        self.assertEqual(result["limit"], 5)
        self.assertEqual(result["group_by"], "Product")


    def test_followup_retains_previous_filters(self):
        previous = build_query_plan(
            "Which product has highest quantity where unit price above 1500?",
            self.columns
        )

        result = resolve_followup_context(
            previous,
            "Show its profit",
            self.columns
        )

        self.assertEqual(len(result["filters"]), 1)
        self.assertEqual(result["filters"][0]["column"], "UnitPrice")
        self.assertEqual(result["group_by"], "Product")


    def test_followup_does_not_modify_previous_plan(self):
        previous = build_query_plan(
            "Which product has highest quantity in March 2026?",
            self.columns
        )

        original_date = dict(previous["date_filter"])

        resolve_followup_context(
            previous,
            "What about February 2026?",
            self.columns
        )

        self.assertEqual(previous["date_filter"], original_date)
    def test_compare_with_previous_month(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        result = resolve_comparative_followup_context(
            previous,
            "Compare it with previous month",
            columns,
        )

        self.assertEqual(result["intent"], "comparison")
        self.assertEqual(
            result["comparison_periods"][0]["start_date"],
            "2026-03-01",
        )
        self.assertEqual(
            result["comparison_periods"][1]["start_date"],
            "2026-02-01",
        )
        self.assertEqual(result["metric"], "GrossAmount")
        self.assertEqual(result["group_by"], "Product")

    def test_compare_same_month_last_year(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        result = resolve_comparative_followup_context(
            previous,
            "Compare with same month last year",
            columns,
        )

        self.assertEqual(
            result["comparison_type"],
            "year_over_year",
        )
        self.assertEqual(
            result["comparison_periods"][0]["start_date"],
            "2026-03-01",
        )
        self.assertEqual(
            result["comparison_periods"][1]["start_date"],
            "2025-03-01",
        )

    def test_percentage_difference_retains_comparison(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        comparison = resolve_comparative_followup_context(
            previous,
            "Compare it with previous month",
            columns,
        )

        result = resolve_comparative_followup_context(
            comparison,
            "What is the percentage difference?",
            columns,
        )

        self.assertEqual(
            result["comparison_type"],
            "percentage_change",
        )
        self.assertEqual(len(result["comparison_periods"]), 2)
        self.assertEqual(result["metric"], "GrossAmount")

    def test_compare_multiple_months(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        result = resolve_comparative_followup_context(
            previous,
            "Compare February, March and April",
            columns,
        )

        self.assertEqual(
            result["comparison_type"],
            "multi_period_comparison",
        )
        self.assertEqual(len(result["comparison_periods"]), 3)

        self.assertEqual(
            [
                p["start_date"]
                for p in result["comparison_periods"]
            ],
            [
                "2026-02-01",
                "2026-03-01",
                "2026-04-01",
            ],
        )

    def test_comparison_retains_previous_numeric_filters(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Show highest sales in March 2026 "
            "where unit price is greater than 1500",
            columns,
        )

        result = resolve_comparative_followup_context(
            previous,
            "Compare it with previous month",
            columns,
        )

        self.assertEqual(result["filters"], previous["filters"])
        self.assertEqual(result["metric"], "GrossAmount")
        self.assertEqual(result["group_by"], "Product")

    def test_comparison_does_not_modify_previous_plan(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        original_date_filter = dict(previous["date_filter"])

        resolve_comparative_followup_context(
            previous,
            "Compare it with previous month",
            columns,
        )

        self.assertEqual(
            previous["date_filter"],
            original_date_filter,
        )
        self.assertNotIn("comparison_periods", previous)

    def test_percentage_without_comparison_does_not_guess(self):
        columns = [
            "Date", "Product", "GrossAmount",
            "Profit", "Qty", "UnitPrice"
        ]

        previous = build_query_plan(
            "Which product has highest sales in March 2026?",
            columns,
        )

        result = resolve_comparative_followup_context(
            previous,
            "What is the percentage difference?",
            columns,
        )

        self.assertEqual(
            result.get("comparison_periods", []),
            [],
        )         
    def test_period_comparison_increase(self):
        result = calculate_period_comparison(150000, 100000)

        self.assertEqual(result["difference"], 50000)
        self.assertEqual(result["percentage_change"], 50.0)
        self.assertEqual(result["trend"], "increase")

    def test_period_comparison_decrease(self):
        result = calculate_period_comparison(80000, 100000)

        self.assertEqual(result["difference"], -20000)
        self.assertEqual(result["percentage_change"], -20.0)
        self.assertEqual(result["trend"], "decrease")

    def test_period_comparison_unchanged(self):
        result = calculate_period_comparison(100000, 100000)

        self.assertEqual(result["difference"], 0)
        self.assertEqual(result["percentage_change"], 0)
        self.assertEqual(result["trend"], "unchanged")

    def test_period_comparison_zero_previous(self):
        result = calculate_period_comparison(50000, 0)

        self.assertEqual(result["difference"], 50000)
        self.assertIsNone(result["percentage_change"])
        self.assertEqual(
            result["percentage_status"],
            "undefined_zero_baseline",
        )

    def test_period_comparison_missing_current(self):
        result = calculate_period_comparison(None, 100000)

        self.assertEqual(result["status"], "missing_data")
        self.assertIsNone(result["difference"])

    def test_period_comparison_missing_previous(self):
        result = calculate_period_comparison(100000, None)

        self.assertEqual(result["status"], "missing_data")
        self.assertIsNone(result["percentage_change"])

    def test_multi_metric_comparison(self):
        current = {
            "GrossAmount": 150000,
            "Profit": 30000,
            "Qty": 500,
        }

        previous = {
            "GrossAmount": 100000,
            "Profit": 20000,
            "Qty": 400,
        }

        result = calculate_multi_metric_comparison(
            current,
            previous,
        )

        self.assertEqual(
            result["GrossAmount"]["percentage_change"], 50.0
        )
        self.assertEqual(
            result["Profit"]["percentage_change"], 50.0
        )
        self.assertEqual(
            result["Qty"]["percentage_change"], 25.0
        )

    def test_multi_metric_missing_previous_metric(self):
        current = {
            "GrossAmount": 150000,
            "Profit": 30000,
        }

        previous = {
            "GrossAmount": 100000,
        }

        result = calculate_multi_metric_comparison(
            current,
            previous,
        )

        self.assertEqual(
            result["Profit"]["status"], "missing_data"
        )
if __name__ == "__main__":
    unittest.main(verbosity=2)
