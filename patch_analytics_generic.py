from pathlib import Path
from datetime import datetime
import re
import shutil

p = Path("graph/analytics_extra.py")
s = p.read_text(encoding="utf-8")

backup = p.with_name(
    p.name + "." + datetime.now().strftime("%Y%m%d_%H%M%S") + ".bak"
)
shutil.copy2(p, backup)
print("BACKUP:", backup)

# 1. Fix product-quarter dictionary key mismatch.
old = 'first_sales = quarter_results[0]["SalesRevenue"]'
new = 'first_sales = quarter_results[0]["Sales Revenue"]'

if old in s:
    s = s.replace(old, new, 1)
    print("FIXED: product quarter Sales Revenue key")
elif new in s:
    print("SKIP: product quarter key already fixed")
else:
    raise RuntimeError("Product quarter key location not found")

# 2. Add state column detection.
anchor = '    party_type_col = col("PartyType", "Party Type")'
if anchor not in s:
    raise RuntimeError("PartyType column declaration not found")

if 'state_col = col("PartyState"' not in s:
    s = s.replace(
        anchor,
        anchor + '\n    state_col = col("PartyState", "Party State", "State")',
        1
    )

# 3. Generic category profit and FY-quarter handlers.
category_handler = r'''
    # CATEGORY_PROFIT_FY_QUARTER_GENERIC_V1
    # Handles one or two explicitly requested financial quarters.
    category_profit_request = (
        bool(re.search(r"\bprofit\b", q))
        and bool(re.search(r"\bcategory\b", q))
        and bool(re.search(r"\bq[1-4]\b", q))
        and bool(re.search(r"\bfy\s*20\d{2}\s*[-/]\s*\d{2,4}\b", q))
    )

    if category_profit_request and date_col and profit_col and category_col:
        refs = list(re.finditer(
            r"\bQ([1-4])\s*(?:of\s*)?FY\s*(20\d{2})\s*[-/]\s*(\d{2,4})\b",
            q, re.I
        ))

        available_categories = sorted(
            df[category_col].dropna().astype(str).str.strip().unique(),
            key=len,
            reverse=True
        )
        selected_category = None
        for candidate in available_categories:
            if candidate and re.search(re.escape(candidate), q, re.I):
                selected_category = candidate
                break

        if selected_category and refs:
            work = df.copy()
            work[date_col] = _to_dt(work[date_col])
            work["__profit__"] = numeric(work, profit_col)
            work["__category__"] = (
                work[category_col].astype(str).str.strip().str.casefold()
            )
            work = work[
                work["__category__"] == selected_category.casefold()
            ].dropna(subset=[date_col]).copy()

            quarter_specs = []
            for ref in refs[:2]:
                quarter = int(ref.group(1))
                fy_year = int(ref.group(2))
                suffix = ref.group(3)
                end_year = (
                    int(suffix) if len(suffix) == 4
                    else (fy_year // 100) * 100 + int(suffix)
                )
                if end_year <= fy_year:
                    end_year += 100

                month = 4 + 3 * (quarter - 1)
                year = fy_year
                if month > 12:
                    month -= 12
                    year += 1

                start = pd.Timestamp(year, month, 1)
                end = start + pd.DateOffset(months=3)
                quarter_specs.append((
                    "Q%d FY%d-%02d" % (quarter, fy_year, end_year % 100),
                    start, end
                ))

            results = []
            for label, start, end in quarter_specs:
                selected = work[
                    (work[date_col] >= start) & (work[date_col] < end)
                ]
                results.append({
                    "Financial Quarter": label,
                    "Category": selected_category,
                    "Total Profit": float(selected["__profit__"].sum()),
                    "Transactions": int(len(selected)),
                })

            if len(refs) >= 2 and bool(re.search(
                r"\b(compare|comparison|versus|vs|change)\b", q
            )):
                if any(row["Transactions"] == 0 for row in results):
                    return _out(
                        "Insufficient matching records to compare both requested financial quarters.",
                        table=results,
                        table_rows=len(results),
                        filtered_rows=int(len(work)),
                        scope_notes=["Category: " + selected_category]
                    )

                first = results[0]["Total Profit"]
                second = results[1]["Total Profit"]
                difference = second - first
                pct = (difference / first * 100) if first else None

                display = [
                    [r["Financial Quarter"], _fmt("sales", r["Total Profit"]),
                     "{:,}".format(r["Transactions"])]
                    for r in results
                ]
                answer = _table(
                    "Category profit: financial-quarter comparison",
                    ["Financial Quarter", "Total Profit", "Transactions"],
                    display
                )
                answer += (
                    "\n\n- Category: " + selected_category
                    + "\n- Profit difference: " + _fmt("sales", difference)
                    + "\n- Percentage change: "
                    + ("Not calculable because the first quarter profit is zero."
                       if pct is None else _fmt("pct", pct))
                )
            else:
                r = results[0]
                if r["Transactions"] == 0:
                    return _out(
                        "Information is not available in the uploaded file for "
                        + selected_category + " in " + r["Financial Quarter"] + ".",
                        table=[],
                        table_rows=0,
                        filtered_rows=0,
                        scope_notes=["Category: " + selected_category]
                    )

                display = [[
                    r["Financial Quarter"],
                    _fmt("sales", r["Total Profit"]),
                    "{:,}".format(r["Transactions"])
                ]]
                answer = _table(
                    "Category profit for financial quarter",
                    ["Financial Quarter", "Total Profit", "Transactions"],
                    display
                )
                answer += "\n- Category: " + selected_category

            return _out(
                answer,
                table=results,
                table_rows=len(results),
                filtered_rows=int(len(work)),
                period_label=" vs ".join(r["Financial Quarter"] for r in results),
                scope_notes=[
                    "Category: " + selected_category,
                    "Financial quarters follow April to March."
                ],
                chart_spec={
                    "type": "bar",
                    "x": "Financial Quarter",
                    "series": ["Total Profit"],
                    "interactive": True,
                    "data": results
                }
            )

    # GST_FILTERED_RATIO_GENERIC_V1
    gst_ratio_request = (
        bool(re.search(r"\bigst\b", q))
        and bool(re.search(r"\btotal\s+tax\b|\bcgst\b", q))
        and bool(re.search(r"\bratio\b|\bpercentage\b|\bpercent\b|\bshare\b", q))
    )

    if gst_ratio_request:
        igst_col = col("IGST")
        cgst_col = col("CGST")
        sgst_col = col("SGST")

        if not all([igst_col, cgst_col, sgst_col]):
            return _out(
                "Required IGST, CGST or SGST columns are unavailable in the uploaded dataset.",
                table=[],
                table_rows=0
            )

        work = df.copy()

        # Apply exact PartyType filter when the query names one.
        if party_type_col:
            party_match = re.search(
                r"\b(retail\s+customer|b2b\s+dealer|wholesale\s+distributor|online\s+marketplace\s+buyer)s?\b",
                q, re.I
            )
            if party_match:
                wanted_party = re.sub(r"\s+", " ", party_match.group(1)).casefold()
                actual_party = work[party_type_col].astype(str).str.strip().str.casefold()
                work = work[actual_party == wanted_party]

        # Apply exact state filter when the query names a state.
        if state_col:
            states = sorted(
                work[state_col].dropna().astype(str).str.strip().unique(),
                key=len,
                reverse=True
            )
            wanted_state = next(
                (v for v in states if v and re.search(re.escape(v), q, re.I)),
                None
            )
            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]

        if work.empty:
            return _out(
                "No matching records were found for the requested PartyType and State. "
                "The IGST-to-total-tax ratio cannot be calculated.",
                table=[],
                table_rows=0,
                filtered_rows=0
            )

        igst = float(numeric(work, igst_col).sum())
        cgst = float(numeric(work, cgst_col).sum())
        sgst = float(numeric(work, sgst_col).sum())
        total_tax = igst + cgst + sgst

        if total_tax == 0:
            return _out(
                "Matching records exist, but total tax is zero. The ratio cannot be calculated.",
                table=[],
                table_rows=0,
                filtered_rows=int(len(work))
            )

        ratio = igst / total_tax * 100
        records = [{
            "IGST": igst,
            "CGST": cgst,
            "SGST": sgst,
            "Total Tax": total_tax,
            "IGST to Total Tax %": ratio
        }]
        display = [[
            _fmt("gst", igst),
            _fmt("gst", cgst),
            _fmt("gst", sgst),
            _fmt("gst", total_tax),
            _fmt("share", ratio)
        ]]
        answer = _table(
            "IGST share of total tax",
            ["IGST", "CGST", "SGST", "Total Tax", "IGST / Total Tax"],
            display
        )
        return _out(
            answer,
            table=records,
            table_rows=1,
            filtered_rows=int(len(work)),
            scope_notes=["Ratio = IGST / (IGST + CGST + SGST) × 100"]
        )

    # HIGHEST_MONTHLY_IGST_GENERIC_V1
    highest_igst_month_request = (
        bool(re.search(r"\bigst\b", q))
        and bool(re.search(r"\b(highest|maximum|max|largest|most)\b", q))
        and bool(re.search(r"\bmonth\b", q))
    )

    if highest_igst_month_request and date_col:
        igst_col = col("IGST")
        if not igst_col:
            return _out("IGST column is unavailable in the uploaded dataset.", table=[])

        work = df.copy()

        if party_type_col:
            party_match = re.search(
                r"\b(retail\s+customer|b2b\s+dealer|wholesale\s+distributor|online\s+marketplace\s+buyer)s?\b",
                q, re.I
            )
            if party_match:
                wanted_party = re.sub(r"\s+", " ", party_match.group(1)).casefold()
                work = work[
                    work[party_type_col].astype(str).str.strip().str.casefold()
                    == wanted_party
                ]

        if state_col:
            states = sorted(
                work[state_col].dropna().astype(str).str.strip().unique(),
                key=len,
                reverse=True
            )
            wanted_state = next(
                (v for v in states if v and re.search(re.escape(v), q, re.I)),
                None
            )
            if wanted_state:
                work = work[
                    work[state_col].astype(str).str.strip().str.casefold()
                    == wanted_state.casefold()
                ]

        work[date_col] = _to_dt(work[date_col])
        work["__igst__"] = numeric(work, igst_col)
        work = work.dropna(subset=[date_col])

        if work.empty:
            return _out(
                "No matching records were found for the requested PartyType and State. "
                "The highest IGST month cannot be determined.",
                table=[],
                table_rows=0,
                filtered_rows=0
            )

        monthly = work.groupby(work[date_col].dt.to_period("M"))["__igst__"].sum()
        if monthly.empty:
            return _out("No monthly IGST data is available.", table=[], table_rows=0)

        peak = monthly.idxmax()
        peak_value = float(monthly.loc[peak])
        records = [{
            "Month": peak.strftime("%B %Y"),
            "IGST": peak_value
        }]
        answer = _table(
            "Month with highest IGST collection",
            ["Calendar Month", "IGST"],
            [[peak.strftime("%B %Y"), _fmt("gst", peak_value)]]
        )
        return _out(
            answer,
            table=records,
            table_rows=1,
            filtered_rows=int(len(work)),
            period_label=peak.strftime("%B %Y"),
            highest_month=peak.strftime("%Y-%m")
        )

'''

if "CATEGORY_PROFIT_FY_QUARTER_GENERIC_V1" not in s:
    marker = "    # SKU_GROSS_REVENUE_WITH_MARGIN_THRESHOLD_V1"
    if marker not in s:
        raise RuntimeError("SKU handler insertion marker not found")
    s = s.replace(marker, category_handler + "\n" + marker, 1)
    print("ADDED: category profit, GST ratio, monthly IGST handlers")
else:
    print("SKIP: generic handlers already present")

p.write_text(s, encoding="utf-8")
print("UPDATED:", p)
