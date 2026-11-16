from pathlib import Path
import re
import sys

root = Path("frontend/src")
app_path = root / "App.jsx"
backup_path = root / "App.jsx.before-modular-refactor.bak"

if not app_path.exists():
    sys.exit("ERROR: frontend/src/App.jsx nahi mila. Project root se run karo.")

if not backup_path.exists():
    sys.exit("ERROR: Backup nahi mila. Pehle App.jsx ka backup banao.")

source = app_path.read_text(encoding="utf-8")

selector_start = source.find("function ChartSelector(")
chart_start = source.find("function Chart(", selector_start)
app_end = source.find("export default App;", chart_start)

if min(selector_start, chart_start, app_end) < 0:
    sys.exit("ERROR: Expected chart boundaries nahi mile. App.jsx change nahi kiya.")

selector_code = source[selector_start:chart_start].strip()
chart_code = source[chart_start:app_end].strip()

if "selectedPieSlice" not in chart_code or "ScatterChart" not in chart_code:
    sys.exit("ERROR: Existing chart code verification failed. App.jsx change nahi kiya.")

charts_dir = root / "components" / "charts"
charts_dir.mkdir(parents=True, exist_ok=True)

selector_file = charts_dir / "ChartSelector.jsx"
renderer_file = charts_dir / "ChartRenderer.jsx"

selector_content = """import {
  Activity, BarChart3, PieChart,
} from "lucide-react";

""" + selector_code + "\n\nexport default ChartSelector;\n"

renderer_content = """import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";

const RUPEE = "\\u20B9";
const NON_NUMERIC_CHARS = /[\\u20B9,%\\s]/g;

function numericValue(value) {
  if (value === null || value === undefined) return 0;
  const number = Number(String(value).replace(NON_NUMERIC_CHARS, "").trim());
  return Number.isFinite(number) ? number : 0;
}

""" + chart_code + "\n\nexport default Chart;\n"

# Create extracted modules first.
selector_file.write_text(selector_content, encoding="utf-8")
renderer_file.write_text(renderer_content, encoding="utf-8")

# Remove original chart definitions using indexes from unchanged source.
updated = source[:selector_start] + source[app_end:]

# Replace chart component calls, without changing ChartSelector calls.
updated = re.sub(r"<Chart(?=\s)", "<ChartRenderer", updated)

# Add imports to App.jsx.
import_block = (
    'import ChartSelector from "./components/charts/ChartSelector.jsx";\n'
    'import ChartRenderer from "./components/charts/ChartRenderer.jsx";\n'
)

if "import ChartRenderer from " not in updated:
    api_marker = 'const API = "http://127.0.0.1:8000";'
    if api_marker not in updated:
        sys.exit("ERROR: API import location nahi mili. App.jsx update nahi kiya.")
    updated = updated.replace(api_marker, import_block + "\n" + api_marker, 1)

# Verify expected call-site updates before saving App.jsx.
if "<Chart " in updated or "<Chart\n" in updated:
    sys.exit("ERROR: Kuch Chart references unresolved hain. App.jsx save nahi kiya.")

if "export default App;" not in updated:
    sys.exit("ERROR: App export missing. App.jsx save nahi kiya.")

app_path.write_text(updated, encoding="utf-8")

print("SUCCESS: Chart components extracted.")
print(f"Created: {selector_file}")
print(f"Created: {renderer_file}")
print("Updated: frontend/src/App.jsx")
print("Existing Bar, Line, Pie and Scatter rendering code was retained.")


