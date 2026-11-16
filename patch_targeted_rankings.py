from pathlib import Path
from datetime import datetime
import re

p = Path("graph/analytics_extra.py")
s = p.read_text(encoding="utf-8")

marker = '''    def numeric(frame, name):
        return pd.to_numeric(frame[name], errors="coerce").fillna(0.0)

    # STATE_RANKING_AND_PAYMENT_MODE_FY_QUARTER_V1
'''

if marker not in s:
    raise RuntimeError("Insertion point not found. No changes made.")

patch = r'''    def numeric(frame, name):
        return pd.to_numeric(frame[name], errors="coerce").fillna(0.0)

    # TARGETED FIX: dealer with highest billing + that dealer's top category.
    party_name_col = col("PartyName", "Party Name", "Customer Name")
    compound_dealer_category = (
        bool(re.search(r"\bb2b\s+dealers?\b", q, re.I))
        and bool(re.search(r"\b(highest|maximum|max|top|largest|most)\b", q, re.I))
        and bool(re.search(r"\b(gross\s+billing|billing|sales|revenue)\b", q, re.I))
        and bool(re.search(r"\b(top\s+product\s+category|product\s+category|category)\b", q, re.I))
        and bool(re.search(r"\band\b", q, re.I))
    )

    compound_qtr = re.search(
        r"\bQ([1-4])\s*(?:of\s*)?FY\s*(20\d{2})\s*[-/]\s*(\d{2,4})\b",
        q, re.I
    )

    if (
        compound_dealer_category and compound_qtr
        and date_col and sales_col and party_type_col
        and state_col and party_name_col and category_col
    ):
        quarter = int(compound_qtr.group(1))
        fy_start_year = int(compound_qtr.group(2))
        suffix = compound_qtr.group(3)
        fy_end_year = (
            int(suffix) if len(suffix) == 4
            else (fy_start_year // 100) * 100 + int(suffix)
        )
        if fy_end_year <= fy_start_year:
            fy_end_year += 100

        start_month = 4 + 3 * (quarter - 1)
        start_year = fy_start_year
        if start_month > 12:
            start_month -= 12
            start_year += 1

        start = pd.Timestamp(start_year, start_month, 1)
        end = start + pd.DateOffset(months=3)

        work = df.copy()
        work[date_col] = _to_dt(work[date_col])
        work = work.dropna(subset=[date_col])
        work = work[
            (work[date_col] >= start) & (work[date_col] < end)
        ].copy()

        actual_party = work[party_type_col].astype(str).str.strip().str.casefold()
        work = work[actual_party == "b2b dealer"].copy()

        states = sorted(
            df[state_col].dropna().astype(str).str.strip().unique(),
            key=len, reverse=True
        )
        requested_state = next(
            (v for v in states if v and re.search(re.escape(v), q, re.I)),
            None
        )
        if requested_state:
            work = work[
                work[state_col].astype(str).str.strip().str.casefold()
                == requested_state.casefold()
            ].copy()

        if work.empty:
            return _out(
                "No matching B2B Dealer records were found for the requested state and quarter.",
                table=[], table_rows=0, filtered_rows=0
            )

        work["__gross__"] = numeric(work, sales_col)
        dealer_totals = (
            work.groupby(work[party_name_col].astype(str).str.strip())["__gross__"]
            .sum().sort_values(ascending=False)
        )

        if dealer_totals.empty:
            return None

        winner = str(dealer_totals.index[0])
        winner_billing = float(dealer_totals.iloc[0])
        winner_rows = work[
            work[party_name_col].astype(str).str.strip() == winner
        ].copy()

        category_totals = (
            winner_rows.groupby(winner_rows[category_col].astype(str).str.strip())["__gross__"]
            .sum().sort_values(ascending=False)
        )
        if category_totals.empty:
            return _out(
                "%s generated %s gross billing, but no product category is available."
                % (winner, _fmt("sales", winner_billing)),
                table=[], table_rows=0, filtered_rows=len(winner_rows)
            )

        top_category = str(category_totals.index[0])
        category_billing = float(category_totals.iloc[0])
        period = "Q%d FY%d-%02d" % (quarter, fy_start_year, fy_end_year % 100)

        records = [
            {"Dealer": winner, "Gross Billing": winner_billing},
            {"Top Product Category": top_category, "Category Gross Billing": category_billing},
        ]
        answer = (
            "Highest B2B Dealer in %s: %s\n"
            "Dealer gross billing: %s\n"
            "Top product category for this dealer: %s\n"
            "Category gross billing: %s\n"
            "Financial period: %s"
        ) % (
            requested_state or "the requested state",
            winner, _fmt("sales", winner_billing),
            top_category, _fmt("sales", category_billing), period
        )
        return _out(
            answer, table=records, table_rows=len(records),
            filtered_rows=int(len(winner_rows)),
            aggregate_column=sales_col,
            aggregate_function="dealer_then_category_rank",
            group_by=party_name_col,
            period_label=period
        )

    # TARGETED FIX: top N products by total profit inside a named category.
    top_n_match = re.search(r"\btop\s+(\d+)\b", q, re.I)
    asks_products = bool(re.search(r"\bproducts?\b", q, re.I))
    asks_profit = bool(re.search(r"\b(net\s+)?profit\b", q, re.I))
    asks_rank = bool(re.search(r"\b(top|highest|most|largest)\b", q, re.I))

    if (
        top_n_match and asks_products and asks_profit and asks_rank
        and category_col and product_col and profit_col
    ):
        available_categories = sorted(
            df[category_col].dropna().astype(str).str.strip().unique(),
            key=len, reverse=True
        )
        requested_category = next(
            (
                value for value in available_categories
                if value and re.search(re.escape(value), q, re.I)
            ),
            None
        )

        if requested_category:
            n = max(1, min(int(top_n_match.group(1)), 20))
            work = df[
                df[category_col].astype(str).str.strip().str.casefold()
                == requested_category.casefold()
            ].copy()
            work["__profit__"] = numeric(work, profit_col)

            ranked = (
                work.groupby(work[product_col].astype(str).str.strip())["__profit__"]
                .sum().sort_values(ascending=False).head(n)
            )
            records = [
                {"Rank": i + 1, "Product": str(name), "Total Net Profit": float(value)}
                for i, (name, value) in enumerate(ranked.items())
            ]
            display = [
                [r["Rank"], r["Product"], _fmt("profit", r["Total Net Profit"])]
                for r in records
            ]
            answer = _table(
                "Top %d products by total net profit in %s"
                % (n, requested_category),
                ["Rank", "Product", "Total Net Profit"], display
            )
            if not records:
                answer = "No products with profit data were found in category %s." % requested_category

            return _out(
                answer, table=records, table_rows=len(records),
                filtered_rows=int(len(work)),
                aggregate_column=profit_col,
                aggregate_function="group_rank",
                group_by=product_col,
                scope_notes=["Category filter applied: %s." % requested_category]
            )

    # STATE_RANKING_AND_PAYMENT_MODE_FY_QUARTER_V1
'''

backup = p.with_name(
    p.name + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
)
backup.write_text(s, encoding="utf-8")
p.write_text(s.replace(marker, patch, 1), encoding="utf-8")
print("PATCH APPLIED")
print("Backup:", backup)
