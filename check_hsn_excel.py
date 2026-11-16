import openpyxl
from collections import defaultdict

path = r".\test_data\Vyapar_Style_Accessories_Sales_Report.xlsx"

wb = openpyxl.load_workbook(path, data_only=True)
ws = wb["Sale Invoices"]

headers = [cell.value for cell in ws[1]]
idx = {
    str(value): i + 1
    for i, value in enumerate(headers)
    if value is not None
}

hsn_sales = defaultdict(float)

for row in range(2, ws.max_row + 1):
    hsn = str(ws.cell(row, idx["HSN_Code"]).value)
    gross = float(ws.cell(row, idx["GrossAmount"]).value or 0)
    hsn_sales[hsn] += gross

print("DIRECT EXCEL HSN SALES (GrossAmount):")

for hsn, amount in sorted(
    hsn_sales.items(),
    key=lambda item: item[1],
    reverse=True,
):
    print(f"{hsn} => ?{amount:,.2f}")
