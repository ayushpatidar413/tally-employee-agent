"""Metric registry = the semantic layer. One place that says what 'sales', 'margin', 'ticket size' mean."""
import re

# kind: sum (add columns) | ratio (num/den*mult) | nunique
METRICS = {
    "sales":    dict(label="gross sales", kind="sum", cols=["GrossAmount", "Gross Amount", "Sales"], money=True,
                     alias=r"\bsales?\b|revenue|turnover|billing|\bspen[dt]\b|\bgross\b"),
    "profit":   dict(label="net profit", kind="sum", cols=["Profit", "NetProfit"], money=True, alias=r"\bprofit\b|\bmunafa\b"),
    "quantity": dict(label="quantity", kind="sum", cols=["Qty", "Quantity"], money=False, alias=r"\b(?:quantity|qty|units?|pieces)\b"),
    "taxable":  dict(label="taxable sales", kind="sum", cols=["TaxableAmount", "Taxable Amount"], money=True, alias=r"\btaxable\b"),
    "igst":     dict(label="IGST", kind="sum", cols=["IGST"], money=True, alias=r"\bigst\b"),
    "cgst":     dict(label="CGST", kind="sum", cols=["CGST"], money=True, alias=r"\bcgst\b"),
    "sgst":     dict(label="SGST", kind="sum", cols=["SGST"], money=True, alias=r"\bsgst\b"),
    "gst":      dict(label="total GST", kind="sum", cols=["TotalGST", "Total GST"], money=True, alias=r"(?<![a-z])gst\b"),
    "discount": dict(label="discount", kind="sum", cols=["DiscountAmt", "Discount Amount"], money=True, alias=r"\bdiscount\b"),
    "invoices": dict(label="unique invoices", kind="nunique", cols=["InvoiceNo", "Invoice No"], money=False, alias=r"\binvoices?\b"),
    "margin":   dict(label="profit margin %", kind="ratio", num="profit", den="taxable", mult=100, money=False, pct=True,
                     alias=r"\bmargins?\b"),
    "ticket":   dict(label="average ticket size", kind="ratio", num="sales", den="invoices", mult=1, money=True,
                     alias=r"ticket\s+size|per\s+(?:unique\s+)?invoice|average\s+(?:bill|invoice)"),
    "asp":      dict(label="average selling price per unit", kind="ratio", num="sales", den="quantity", mult=1, money=True,
                     alias=r"selling\s+price|\basp\b|per\s+unit"),
}


def find_col(df, names):
    low = {str(c).lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for n in names:
        k = n.lower().replace(" ", "").replace("_", "")
        if k in low:
            return low[k]
    return None


def available(df):
    """metric -> True/False depending on columns present in this dataset."""
    out = {}
    for k, m in METRICS.items():
        if m["kind"] in ("sum", "nunique"):
            out[k] = find_col(df, m["cols"]) is not None
    for k, m in METRICS.items():
        if m["kind"] == "ratio":
            out[k] = out.get(m["num"], False) and out.get(m["den"], False)
    return out


def mentioned(question):
    """Metric names whose alias appears in the question (used for the coverage check)."""
    q = question.lower()
    hit = {k for k, m in METRICS.items() if re.search(m["alias"], q)}
    # a derived metric explains the words of its parts: 'ticket size (gross sales per invoice)'
    for k in list(hit):
        m = METRICS[k]
        if m["kind"] == "ratio":
            hit.discard(m["num"]); hit.discard(m["den"])
    if "cgst" in hit or "sgst" in hit or "igst" in hit:
        hit.discard("gst")
    return hit
