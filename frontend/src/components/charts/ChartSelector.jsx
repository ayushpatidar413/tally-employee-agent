import { useId } from "react";

const OPTIONS = [
  ["bar", "Bar"],
  ["stacked-bar", "Stacked Bar"],
  ["line", "Line"],
  ["area", "Area"],
  ["stacked-area", "Stacked Area"],
  ["pie", "Pie"],
  ["donut", "Donut"],
  ["scatter", "Scatter"],
  ["bubble", "Bubble"],
  ["heatmap", "Heatmap"],
  ["funnel", "Funnel"],
  ["treemap", "Treemap"],
  ["radar", "Radar"],
  ["waterfall", "Waterfall"],
  ["boxplot", "Box Plot"],
];

export default function ChartSelector({ value = "bar", onChange }) {
  const selectId = useId();

  return (
    <div className="chart-type-selector chart-type-selector-dropdown">
      <label htmlFor={selectId}>Chart type</label>
      <select
        id={selectId}
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
        aria-label="Select chart type"
      >
        {OPTIONS.map(([id, label]) => (
          <option key={id} value={id}>{label}</option>
        ))}
      </select>
    </div>
  );
}
