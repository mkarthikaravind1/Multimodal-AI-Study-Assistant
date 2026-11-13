import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import MermaidDiagram from "../components/MermaidDiagram";
import usePageTitle from "../hooks/usePageTitle";
import { BRANCH_COLORS, branchOf, toFlowchart, toMindmap } from "../lib/mermaidGraph";

const KIND_ICON = { lesson: "📖", pdf: "📄", video: "🎬" };
const ZOOMS = [0.75, 1, 1.5, 2, 3];

// ── source picker ─────────────────────────────────────────────────────────────

function SourceList({ sources, loading, busyKey, activeKey, onPick }) {
  const [tab, setTab] = useState("notes");
  const rows =
    tab === "notes"
      ? sources.notes.map((n) => ({ key: `note-${n.note_id}`, type: "note", id: n.note_id, title: n.title, icon: "📖", mapId: n.map_id }))
      : sources.materials.map((m) => ({
          key: `material-${m.material_id}`, type: "material", id: m.material_id, title: m.filename,
          icon: KIND_ICON[m.file_type] ?? "📄", mapId: m.map_id,
        }));

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3 no-print">
      <h2 className="text-sm font-semibold text-gray-800">Map something</h2>
      <div className="flex gap-1 p-1 bg-gray-100 rounded-xl text-xs">
        {[["notes", `Lessons (${sources.notes.length})`], ["materials", `PDFs & videos (${sources.materials.length})`]].map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className="flex-1 px-2 py-1.5 rounded-lg font-medium"
            style={tab === t ? { background: "#fff", color: "#4338CA", boxShadow: "0 1px 2px rgba(0,0,0,.06)" } : { color: "#6B7280" }}
          >
            {label}
          </button>
        ))}
      </div>
      {loading ? (
        <div className="flex flex-col gap-2 animate-pulse">
          {[0, 1, 2].map((i) => <div key={i} className="h-10 bg-gray-100 rounded-xl" />)}
        </div>
      ) : rows.length === 0 ? (
        <p className="text-xs text-gray-400 py-2">
          {tab === "notes" ? "No lessons yet — make one on the Lessons page." : "Upload a PDF or video in the Tutor to map it."}
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5 max-h-[60vh] overflow-y-auto pr-1">
          {rows.map((r) => (
            <li key={r.key}>
              <button
                type="button"
                onClick={() => onPick(r.type, r.id)}
                disabled={busyKey !== null}
                className="w-full text-left px-3 py-2 rounded-xl border flex items-center gap-2.5 hover:border-indigo-200 hover:bg-indigo-50/40 disabled:opacity-60"
                style={{ borderColor: activeKey === r.key ? "#A5B4FC" : "#F3F4F6", background: activeKey === r.key ? "#EEF2FF" : undefined }}
              >
                <span className="text-base flex-shrink-0">{r.icon}</span>
                <span className="text-sm text-gray-700 flex-1 min-w-0 truncate" title={r.title}>{r.title}</span>
                {busyKey === r.key ? (
                  <Spinner color="text-indigo-600" />
                ) : (
                  <span className="text-[11px] flex-shrink-0" style={{ color: r.mapId ? "#16A34A" : "#6366F1" }}>
                    {r.mapId ? "Open" : "Make"}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── one map ───────────────────────────────────────────────────────────────────

function KeyIdeas({ graph }) {
  const branch = useMemo(() => branchOf(graph), [graph]);
  const children = useMemo(() => {
    const out = {};
    for (const n of graph.nodes) (out[n.parent] ??= []).push(n);
    return out;
  }, [graph]);

  const renderNode = (n, depth) => (
    <li key={n.id} className={depth ? "mt-1" : "mt-3"}>
      <p className={depth ? "text-sm text-gray-700" : "text-sm font-semibold"} style={depth ? undefined : { color: BRANCH_COLORS[branch[n.id]].stroke }}>
        {n.label}
        {n.relation && depth > 0 && <span className="text-xs text-gray-400"> · {n.relation}</span>}
      </p>
      {n.detail && <p className="text-xs text-gray-500 leading-relaxed">{n.detail}</p>}
      {children[n.id] && <ul className="pl-4 border-l border-gray-100 ml-1">{children[n.id].map((c) => renderNode(c, depth + 1))}</ul>}
    </li>
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 print-flat">
      <h3 className="text-sm font-semibold text-gray-800">Key ideas</h3>
      <ul>{(children.root ?? []).map((n) => renderNode(n, 0))}</ul>
      {graph.links.length > 0 && (
        <>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mt-5 mb-1">Connections across topics</h4>
          <ul className="text-sm text-gray-700 space-y-0.5">
            {graph.links.map((l) => {
              const label = (id) => graph.nodes.find((n) => n.id === id)?.label ?? id;
              return (
                <li key={`${l.from}-${l.to}`}>
                  {label(l.from)} <span className="text-gray-400">— {l.label || "relates to"} →</span> {label(l.to)}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

function MapView({ map, onRegenerate, onDelete, regenerating }) {
  const [view, setView] = useState("mind"); // mind | concept
  const [zoomIdx, setZoomIdx] = useState(1);
  const svgRef = useRef("");
  const code = useMemo(() => (view === "mind" ? toMindmap(map.graph) : toFlowchart(map.graph)), [map.graph, view]);
  const handleSvg = useCallback((svg) => {
    svgRef.current = svg;
  }, []);

  function downloadSvg() {
    if (!svgRef.current) return;
    const blob = new Blob([svgRef.current], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${map.title.replace(/[^A-Za-z0-9]+/g, "-").slice(0, 50) || "map"}-${view === "mind" ? "mind-map" : "concept-map"}.svg`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const btn = "px-3 py-1.5 rounded-xl text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50";

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 print-flat">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            <p className="text-xs text-gray-400">{KIND_ICON[map.source_kind]} {map.source_kind === "lesson" ? "Lesson" : map.source_kind.toUpperCase()}</p>
            <h2 className="text-lg font-bold text-gray-900 truncate">{map.title}</h2>
          </div>
          <div className="flex gap-1 p-1 bg-gray-100 rounded-xl text-xs no-print" role="tablist" aria-label="Map style">
            {[["mind", "🧠 Mind map"], ["concept", "🔗 Concept map"]].map(([v, label]) => (
              <button
                key={v}
                type="button"
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className="px-3 py-1.5 rounded-lg font-medium"
                style={view === v ? { background: "#fff", color: "#4338CA", boxShadow: "0 1px 2px rgba(0,0,0,.06)" } : { color: "#6B7280" }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <MermaidDiagram
          code={code}
          zoom={ZOOMS[zoomIdx]}
          onSvg={handleSvg}
          label={`${view === "mind" ? "Mind map" : "Concept map"} of ${map.title}. The same ideas are listed under Key ideas.`}
        />
        {view === "concept" && (
          <p className="text-[11px] text-gray-400 mt-2 no-print">Solid arrows: how an idea connects to its parent · dashed: links across branches.</p>
        )}

        <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-gray-100 no-print">
          <div className="flex items-center gap-1">
            <button type="button" className={btn} onClick={() => setZoomIdx((i) => Math.max(0, i - 1))} disabled={zoomIdx === 0} aria-label="Zoom out">−</button>
            <span className="text-xs text-gray-500 w-12 text-center">{Math.round(ZOOMS[zoomIdx] * 100)}%</span>
            <button type="button" className={btn} onClick={() => setZoomIdx((i) => Math.min(ZOOMS.length - 1, i + 1))} disabled={zoomIdx === ZOOMS.length - 1} aria-label="Zoom in">+</button>
          </div>
          <span className="flex-1" />
          <button type="button" className={btn} onClick={downloadSvg}>⬇ SVG</button>
          <button type="button" className={btn} onClick={() => window.print()}>🖨 Print / PDF</button>
          <button type="button" className={btn} onClick={onRegenerate} disabled={regenerating}>
            {regenerating ? "Regenerating…" : "↻ Regenerate"}
          </button>
          <button type="button" className={`${btn} hover:text-red-600`} onClick={onDelete}>Delete</button>
        </div>
      </div>
      <KeyIdeas graph={map.graph} />
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function ConceptMaps() {
  usePageTitle("Concept maps");
  const location = useLocation();
  const [sources, setSources] = useState({ notes: [], materials: [] });
  const [loading, setLoading] = useState(true);
  const [map, setMap] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState("");
  const autoOpened = useRef(false);

  const refreshSources = useCallback(
    () =>
      api
        .get("/maps/sources")
        .then((res) => setSources(res.data))
        .catch(() => {})
        .finally(() => setLoading(false)),
    []
  );

  const pick = useCallback(
    async (type, id, regenerate = false) => {
      const key = `${type}-${id}`;
      setError("");
      if (regenerate) setRegenerating(true);
      else setBusyKey(key);
      try {
        const res = await api.post("/maps", { source_type: type, source_id: id, regenerate });
        setMap(res.data);
        refreshSources();
      } catch (err) {
        setError(getErrorMessage(err, "Couldn't make the map. Try again."));
      } finally {
        setBusyKey(null);
        setRegenerating(false);
      }
    },
    [refreshSources]
  );

  useEffect(() => {
    refreshSources();
  }, [refreshSources]);

  // "🧠 Mind map" on a lesson card opens straight into its map
  useEffect(() => {
    const s = location.state;
    if (!autoOpened.current && s?.sourceType && s?.sourceId) {
      autoOpened.current = true;
      pick(s.sourceType, s.sourceId);
    }
  }, [location.state, pick]);

  async function remove() {
    if (!map || !window.confirm(`Delete the map of "${map.title}"?`)) return;
    try {
      await api.delete(`/maps/${map.map_id}`);
      setMap(null);
      refreshSources();
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't delete the map."));
    }
  }

  const activeKey = map ? `${map.source_type}-${map.source_id}` : null;

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8 no-print">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
          <h1 className="text-3xl font-bold text-gray-900">Concept maps</h1>
          <p className="text-sm text-gray-500 mt-1">See how the ideas in a lesson, PDF or video fit together — as a mind map or a concept map.</p>
        </div>

        {error && <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100 no-print">{error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          <div className="lg:col-span-1 lg:sticky lg:top-6">
            <SourceList sources={sources} loading={loading} busyKey={busyKey} activeKey={activeKey} onPick={(t, id) => pick(t, id)} />
          </div>
          <div className="lg:col-span-3">
            {map ? (
              <MapView
                key={map.map_id}
                map={map}
                regenerating={regenerating}
                onRegenerate={() => pick(map.source_type, map.source_id, true)}
                onDelete={remove}
              />
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 flex flex-col items-center text-center gap-3 no-print">
                {busyKey ? (
                  <>
                    <Spinner size={5} color="text-indigo-600" />
                    <p className="text-sm text-gray-500">Finding the key ideas and how they connect…</p>
                  </>
                ) : (
                  <>
                    <span className="text-4xl">🧠</span>
                    <p className="text-sm font-medium text-gray-700">Pick a lesson, PDF or video</p>
                    <p className="text-xs text-gray-400 max-w-sm">
                      The AI pulls out the main ideas and how they link. Maps are saved, so opening one again is instant.
                    </p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
