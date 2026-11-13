import { useEffect, useId, useRef, useState } from "react";
import Spinner from "./Spinner";

// Mermaid is ~1 MB, so it's downloaded only when a diagram is first shown,
// and initialised once.
let mermaidPromise = null;
function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict", // no scripts or clickable HTML in labels
        theme: "base",
        fontFamily: "inherit",
        themeVariables: {
          primaryColor: "#EEF2FF",
          primaryBorderColor: "#6366F1",
          primaryTextColor: "#1F2937",
          lineColor: "#94A3B8",
          fontSize: "15px",
        },
        flowchart: { curve: "basis", padding: 12, nodeSpacing: 30, rankSpacing: 60 },
        mindmap: { padding: 14 },
      });
      return mermaid;
    }).catch((err) => {
      mermaidPromise = null; // allow a retry (e.g. after a network blip)
      throw err;
    });
  }
  return mermaidPromise;
}

/**
 * Renders Mermaid code to SVG. `zoom` scales the drawing (1 = fit width).
 * onSvg(svgString) receives the rendered SVG (for download).
 */
export default function MermaidDiagram({ code, zoom = 1, onSvg, label }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reactId = useId();
  const counter = useRef(0);
  const onSvgRef = useRef(onSvg);

  useEffect(() => {
    onSvgRef.current = onSvg;
  }, [onSvg]);

  useEffect(() => {
    let cancelled = false;
    const renderId = `mmd-${reactId.replace(/[^a-zA-Z0-9]/g, "")}-${++counter.current}`;
    loadMermaid()
      .then((mermaid) => mermaid.render(renderId, code))
      .then(({ svg: out }) => {
        if (cancelled) return;
        setSvg(out);
        setError("");
        onSvgRef.current?.(out);
      })
      .catch(() => {
        if (!cancelled) setError("This map couldn't be drawn. Try the other view, or regenerate it.");
        // mermaid leaves an error element behind on failure
        document.getElementById(`d${renderId}`)?.remove();
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [code, reactId]);

  if (error) return <p className="text-sm text-red-600 py-10 text-center">{error}</p>;
  if (loading && !svg) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-sm text-gray-400">
        <Spinner color="text-indigo-600" /> Drawing the map…
      </div>
    );
  }
  return (
    <div className="overflow-auto" role="img" aria-label={label}>
      <div
        className="mermaid-host mx-auto"
        style={{ width: `${Math.round(zoom * 100)}%`, minWidth: zoom > 1 ? undefined : "min(100%, 640px)" }}
        // SVG produced by mermaid with securityLevel "strict" (sanitised)
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </div>
  );
}
