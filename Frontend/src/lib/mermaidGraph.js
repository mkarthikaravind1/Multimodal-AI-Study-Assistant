// Turns a validated concept-map graph (Services/concept_map.py) into Mermaid code.
// The model never writes Mermaid itself — labels are escaped here, so a stray
// quote, bracket or "#" in a label can't break the diagram.
//
// graph = { central, nodes: [{id, label, parent, relation, detail}], links: [{from, to, label}] }

// Branch colours (one per main branch) — readable with dark text
export const BRANCH_COLORS = [
  { fill: "#EEF2FF", stroke: "#6366F1" },
  { fill: "#ECFDF5", stroke: "#10B981" },
  { fill: "#FFF7ED", stroke: "#F97316" },
  { fill: "#FDF2F8", stroke: "#EC4899" },
  { fill: "#F0F9FF", stroke: "#0EA5E9" },
  { fill: "#FEFCE8", stroke: "#CA8A04" },
  { fill: "#F5F3FF", stroke: "#8B5CF6" },
];

// Flowchart labels: quoted strings with Mermaid's #entity; codes
function esc(text) {
  return String(text ?? "")
    .replace(/#/g, "#35;")
    .replace(/"/g, "#quot;")
    .replace(/</g, "#lt;")
    .replace(/>/g, "#gt;")
    .replace(/[\r\n]+/g, " ")
    .trim();
}

// Mind-map labels: mindmap syntax has no reliable escaping for brackets,
// so they become look-alike characters instead
function mindText(text) {
  return String(text ?? "")
    .replace(/[\r\n]+/g, " ")
    .replace(/\(/g, "（").replace(/\)/g, "）")
    .replace(/\[/g, "⟦").replace(/\]/g, "⟧")
    .replace(/\{/g, "❴").replace(/\}/g, "❵")
    .replace(/"/g, "”")
    .replace(/`/g, "'")
    .trim();
}

/** Which main branch (top-level node) each node belongs to: {id: branchIndex} */
export function branchOf(graph) {
  const byId = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const top = graph.nodes.filter((n) => n.parent === "root").map((n) => n.id);
  const out = {};
  for (const n of graph.nodes) {
    let cur = n;
    let guard = 0;
    while (cur && cur.parent !== "root" && guard++ < 10) cur = byId[cur.parent];
    out[n.id] = Math.max(0, top.indexOf(cur?.id ?? n.id)) % BRANCH_COLORS.length;
  }
  return out;
}

/** Tree only — Mermaid "mindmap" (indentation = depth). */
export function toMindmap(graph) {
  const children = {};
  for (const n of graph.nodes) (children[n.parent] ??= []).push(n);
  const lines = ["mindmap", `  root((${mindText(graph.central)}))`];
  const walk = (parentId, depth) => {
    for (const n of children[parentId] ?? []) {
      lines.push(`${"  ".repeat(depth + 2)}${n.id}[${mindText(n.label)}]`);
      walk(n.id, depth + 1);
    }
  };
  walk("root", 0);
  return lines.join("\n");
}

/** Tree + relation labels + dashed cross-links — Mermaid flowchart. */
export function toFlowchart(graph) {
  const branch = branchOf(graph);
  const lines = ["flowchart LR", `  root(["${esc(graph.central)}"])`];
  for (const n of graph.nodes) lines.push(`  ${n.id}["${esc(n.label)}"]`);
  for (const n of graph.nodes) {
    const rel = n.relation ? `|"${esc(n.relation)}"|` : "";
    lines.push(`  ${n.parent} -->${rel} ${n.id}`);
  }
  for (const l of graph.links ?? []) {
    const rel = l.label ? `|"${esc(l.label)}"|` : "";
    lines.push(`  ${l.from} -.->${rel} ${l.to}`);
  }
  lines.push("  classDef rootNode fill:#4F46E5,stroke:#3730A3,color:#ffffff,font-weight:bold");
  BRANCH_COLORS.forEach((c, i) => lines.push(`  classDef b${i} fill:${c.fill},stroke:${c.stroke},color:#1F2937`));
  lines.push("  class root rootNode");
  const groups = {};
  for (const n of graph.nodes) (groups[branch[n.id]] ??= []).push(n.id);
  for (const [i, ids] of Object.entries(groups)) lines.push(`  class ${ids.join(",")} b${i}`);
  return lines.join("\n");
}
