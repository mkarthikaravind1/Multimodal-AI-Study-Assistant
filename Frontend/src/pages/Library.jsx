import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import CitationViewer from "../components/CitationViewer";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

const TYPES = {
  pdf: { icon: "📄", label: "PDF", bg: "#FEF2F2", fg: "#B91C1C" },
  video: { icon: "🎬", label: "Video", bg: "#EFF6FF", fg: "#1D4ED8" },
  image: { icon: "🖼️", label: "Image", bg: "#F0FDF4", fg: "#15803D" },
};
const FILTERS = [
  ["all", "All"],
  ["pdf", "PDFs"],
  ["video", "Videos"],
  ["image", "Images"],
];

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";
}

function MaterialRow({ m, onOpen, onDeleted }) {
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const t = TYPES[m.file_type] ?? TYPES.pdf;

  async function remove() {
    if (
      !window.confirm(
        `Delete "${m.filename}"?\n\nThe file and everything indexed from it are removed — the tutor won't use it any more. This can't be undone.`
      )
    )
      return;
    setDeleting(true);
    setError("");
    try {
      await api.delete(`/upload/materials/${m.material_id}`);
      onDeleted(m.material_id);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't delete it."));
      setDeleting(false);
    }
  }

  const btn = "px-2.5 py-1.5 rounded-lg text-xs font-medium border hover:opacity-90 disabled:opacity-50";

  return (
    <li className="bg-white rounded-2xl border border-gray-100 shadow-sm px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <span className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0" style={{ background: t.bg }}>
          {t.icon}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate" title={m.filename}>{m.filename}</p>
          <p className="text-xs text-gray-400">
            <span style={{ color: t.fg }}>{t.label}</span> · {formatDate(m.uploaded_at)} · {m.total_chunks} section{m.total_chunks === 1 ? "" : "s"} indexed
          </p>
          {error && <p className="text-xs text-red-500 mt-0.5">{error}</p>}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 sm:justify-end">
        <button type="button" onClick={() => onOpen(m)} className={`${btn} border-gray-200 text-gray-600`}>
          Open
        </button>
        <button
          type="button"
          onClick={() => navigate("/tutor", { state: { focusMaterial: { id: m.material_id, filename: m.filename, type: m.file_type } } })}
          className={`${btn} border-indigo-200 text-indigo-700 bg-indigo-50`}
          title="Chat with the tutor using only this document"
        >
          💬 Ask about this
        </button>
        {(m.file_type === "pdf" || m.file_type === "video") && (
          <button
            type="button"
            onClick={() => navigate("/maps", { state: { sourceType: "material", sourceId: m.material_id } })}
            className={`${btn} border-gray-200 text-gray-600`}
          >
            🧠 Map
          </button>
        )}
        <button
          type="button"
          onClick={remove}
          disabled={deleting}
          aria-label={`Delete ${m.filename}`}
          className={`${btn} border-gray-200 text-gray-400 hover:text-red-600 hover:border-red-200`}
        >
          {deleting ? <Spinner color="text-red-500" size={3} /> : "Delete"}
        </button>
      </div>
    </li>
  );
}

export default function Library() {
  usePageTitle("Library");
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);
  const [uploading, setUploading] = useState(null); // filename being uploaded
  const [notice, setNotice] = useState("");
  const fileRef = useRef(null);

  useEffect(() => {
    api
      .get("/upload/materials")
      .then((res) => setMaterials(res.data))
      .catch((err) => setError(getErrorMessage(err, "Couldn't load your library.")))
      .finally(() => setLoading(false));
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return materials.filter((m) => (filter === "all" || m.file_type === filter) && (!q || m.filename.toLowerCase().includes(q)));
  }, [materials, query, filter]);

  const counts = useMemo(() => {
    const c = { all: materials.length };
    for (const m of materials) c[m.file_type] = (c[m.file_type] ?? 0) + 1;
    return c;
  }, [materials]);

  async function upload(file) {
    if (!file) return;
    const type = file.type === "application/pdf" || /\.pdf$/i.test(file.name) ? "pdf" : file.type.startsWith("video/") ? "video" : null;
    if (!type) {
      setError("Upload a PDF or a video here. To ask about an image, attach it in the Tutor.");
      return;
    }
    setUploading(file.name);
    setError("");
    setNotice("");
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post(type === "pdf" ? "/upload/pdf" : "/upload/video", form);
      const res = await api.get("/upload/materials");
      setMaterials(res.data);
      setNotice(`“${file.name}” is in your library — the tutor can use it now.`);
    } catch (err) {
      setError(getErrorMessage(err, "Upload failed."));
    } finally {
      setUploading(null);
    }
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
            <h1 className="text-3xl font-bold text-gray-900">Library</h1>
            <p className="text-sm text-gray-500 mt-1">Everything you've uploaded — the tutor searches all of it, or just one file.</p>
          </div>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading !== null}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60 flex items-center gap-2"
            style={{ background: "#4F46E5" }}
          >
            {uploading ? <><Spinner /> Uploading…</> : "+ Upload PDF or video"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,video/mp4,video/mpeg,video/webm,video/quicktime"
            className="hidden"
            onChange={(e) => {
              upload(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </div>

        {uploading && (
          <p className="mb-4 text-xs text-gray-500">
            Indexing “{uploading}”… {/\.(mp4|webm|mov|mpeg)$/i.test(uploading) ? "Videos take a minute or two (transcript + frames)." : ""}
          </p>
        )}
        {notice && <div className="mb-4 px-4 py-3 rounded-xl bg-green-50 text-green-700 text-sm border border-green-100">{notice}</div>}
        {error && <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by file name…"
            aria-label="Search the library"
            className="flex-1 border border-gray-200 rounded-xl px-4 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <div className="flex gap-1 p-1 bg-white border border-gray-100 rounded-xl text-xs">
            {FILTERS.map(([f, label]) => (
              <button
                key={f}
                type="button"
                aria-pressed={filter === f}
                onClick={() => setFilter(f)}
                className="px-3 py-1.5 rounded-lg font-medium"
                style={filter === f ? { background: "#EEF2FF", color: "#4338CA" } : { color: "#6B7280" }}
              >
                {label} {counts[f] ? <span className="text-gray-400">{counts[f]}</span> : null}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col gap-2 animate-pulse">
            {[0, 1, 2].map((i) => <div key={i} className="h-16 bg-white rounded-2xl border border-gray-100" />)}
          </div>
        ) : materials.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 text-center">
            <p className="text-4xl mb-2">📚</p>
            <p className="text-sm font-medium text-gray-700">Your library is empty</p>
            <p className="text-xs text-gray-400 mt-1">Upload lecture PDFs or recorded classes, and the tutor will answer from them with citations.</p>
          </div>
        ) : shown.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">Nothing matches.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {shown.map((m) => (
              <MaterialRow
                key={m.material_id}
                m={m}
                onOpen={(mat) => setOpen({ material_id: mat.material_id, type: mat.file_type, filename: mat.filename, label: mat.filename })}
                onDeleted={(id) => setMaterials((prev) => prev.filter((x) => x.material_id !== id))}
              />
            ))}
          </ul>
        )}
      </div>

      {open && <CitationViewer citation={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
