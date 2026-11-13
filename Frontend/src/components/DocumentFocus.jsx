import { useEffect, useRef, useState } from "react";
import api from "../api/axios";
import Spinner from "./Spinner";

const ICONS = { pdf: "📄", video: "🎬", image: "🖼️" };

/**
 * "Only search this document" picker for the tutor.
 * value: {id, filename, type} or null (= search all materials).
 */
export default function DocumentFocus({ value, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  const [materials, setMaterials] = useState(null); // null until loaded
  const [filter, setFilter] = useState("");
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .get("/upload/materials")
      .then((res) => !cancelled && setMaterials(res.data))
      .catch(() => !cancelled && setMaterials([]));
    const onDown = (e) => !rootRef.current?.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      cancelled = true;
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const shown = (materials ?? []).filter((m) => m.filename.toLowerCase().includes(filter.trim().toLowerCase()));

  return (
    <div ref={rootRef} className="relative inline-flex items-center gap-1">
      {value ? (
        <span className="inline-flex items-center gap-1.5 pl-2.5 pr-1 py-1 rounded-lg text-xs bg-amber-50 border border-amber-200 text-amber-800 max-w-[260px]">
          <span className="truncate">
            {ICONS[value.type] ?? "📄"} Only: <strong className="font-medium">{value.filename}</strong>
          </span>
          <button
            type="button"
            onClick={() => onChange(null)}
            disabled={disabled}
            aria-label="Search all materials again"
            title="Search all materials again"
            className="w-5 h-5 rounded hover:bg-amber-100 flex-shrink-0"
          >
            ✕
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs border border-gray-200 text-gray-500 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
        >
          🔎 Searching all my materials ▾
        </button>
      )}

      {open && !value && (
        <div className="absolute bottom-full left-0 mb-2 w-80 max-w-[85vw] bg-white rounded-2xl shadow-lg border border-gray-100 p-2 z-30">
          <p className="text-xs text-gray-400 px-2 pt-1 pb-2">Only search one document — the tutor will answer from it alone.</p>
          {materials && materials.length > 6 && (
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter…"
              aria-label="Filter documents"
              className="w-full border border-gray-200 rounded-lg px-2 py-1 text-sm mb-1 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          )}
          {materials === null ? (
            <div className="flex justify-center py-4"><Spinner color="text-indigo-600" /></div>
          ) : materials.length === 0 ? (
            <p className="text-xs text-gray-400 px-2 py-3">No uploads yet — attach a PDF or video with the paperclip.</p>
          ) : (
            <ul role="listbox" className="max-h-64 overflow-y-auto">
              {shown.map((m) => (
                <li key={m.material_id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onClick={() => {
                      onChange({ id: m.material_id, filename: m.filename, type: m.file_type });
                      setOpen(false);
                    }}
                    className="w-full text-left px-2 py-1.5 rounded-lg text-sm text-gray-700 hover:bg-indigo-50 flex items-center gap-2"
                  >
                    <span>{ICONS[m.file_type] ?? "📄"}</span>
                    <span className="truncate">{m.filename}</span>
                  </button>
                </li>
              ))}
              {shown.length === 0 && <li className="text-xs text-gray-400 px-2 py-2">No match.</li>}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
