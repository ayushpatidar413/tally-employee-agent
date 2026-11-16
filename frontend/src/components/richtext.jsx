import { useMemo } from "react";

function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") && p.length > 4 ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>
  );
}

function parseBlocks(text) {
  const lines = String(text || "").split("\n");
  const blocks = [];
  const isList = (l) => /^\s*[-*]\s+/.test(l);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith("|")) {
      const tbl = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) { tbl.push(lines[i]); i += 1; }
      blocks.push({ type: "table", lines: tbl });
    } else if (isList(line)) {
      const items = [];
      while (i < lines.length && isList(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, "")); i += 1; }
      blocks.push({ type: "list", items });
    } else if (line.trim() === "") {
      i += 1;
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() !== "" && !lines[i].trim().startsWith("|") && !isList(lines[i])) { para.push(lines[i]); i += 1; }
      blocks.push({ type: "p", text: para.join("\n") });
    }
  }
  return blocks;
}

/** Light markdown: paragraphs, **bold**, bullet lists and pipe tables. */
export default function RichText({ text, hideTables }) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  return (
    <div className="vx-richtext">
      {blocks.map((b, i) => {
        if (b.type === "p") return <p key={i}>{inline(b.text)}</p>;
        if (b.type === "list") return <ul key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>;
        if (hideTables) return null;
        const rows = b.lines
          .map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()))
          .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c)));
        if (!rows.length) return null;
        return (
          <div className="vx-md-table" key={i}>
            <table>
              <thead><tr>{rows[0].map((c, j) => <th key={j}>{inline(c)}</th>)}</tr></thead>
              <tbody>{rows.slice(1).map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
