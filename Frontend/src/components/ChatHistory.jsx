import { useEffect, useRef, useState } from "react";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "./Spinner";

// "Today", "Yesterday", "Previous 7 days", "Earlier" — by the chat's last message
function groupLabel(iso) {
  if (!iso) return "Earlier";
  const d = new Date(iso);
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const days = Math.floor((start - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  return "Earlier";
}

function SessionRow({ s, active, onOpen, onRenamed, onDeleted }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(s.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  async function save() {
    const t = title.trim();
    if (!t || t === s.title) {
      setEditing(false);
      setTitle(s.title);
      return;
    }
    setBusy(true);
    try {
      const res = await api.patch(`/chat/sessions/${s.session_id}`, { title: t });
      onRenamed(res.data);
      setEditing(false);
      setError("");
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't rename."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete the chat "${s.title}"? This can't be undone.`)) return;
    setBusy(true);
    try {
      await api.delete(`/chat/sessions/${s.session_id}`);
      onDeleted(s.session_id);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't delete."));
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="px-2 py-1.5">
        <input
          ref={inputRef}
          value={title}
          maxLength={200}
          disabled={busy}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") {
              setEditing(false);
              setTitle(s.title);
            }
          }}
          onBlur={save}
          aria-label="Chat name"
          className="w-full border border-indigo-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {error && <p className="text-[11px] text-red-500 mt-1">{error}</p>}
      </li>
    );
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={() => onOpen(s.session_id)}
        aria-current={active ? "true" : undefined}
        className="w-full text-left px-3 py-2 rounded-xl pr-14 hover:bg-white"
        style={active ? { background: "#EEF2FF" } : undefined}
      >
        <p className={`text-sm truncate ${active ? "text-indigo-700 font-medium" : "text-gray-700"}`}>
          {s.material_id ? "📄 " : ""}
          {s.title}
        </p>
        <p className="text-[11px] text-gray-400 truncate">{s.match ?? s.preview}</p>
      </button>
      {/* always visible on touch screens (no hover there); on hover / keyboard focus on desktop */}
      <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex gap-0.5 lg:opacity-0 lg:group-hover:opacity-100 lg:focus-within:opacity-100">
        {busy ? (
          <Spinner color="text-gray-400" size={3} />
        ) : (
          <>
            <button
              type="button"
              onClick={() => setEditing(true)}
              title="Rename"
              aria-label={`Rename ${s.title}`}
              className="w-6 h-6 rounded-md text-xs text-gray-400 hover:text-indigo-600 hover:bg-indigo-50"
            >
              ✎
            </button>
            <button
              type="button"
              onClick={remove}
              title="Delete"
              aria-label={`Delete ${s.title}`}
              className="w-6 h-6 rounded-md text-xs text-gray-400 hover:text-red-600 hover:bg-red-50"
            >
              🗑
            </button>
          </>
        )}
      </div>
      {error && <p className="text-[11px] text-red-500 px-3">{error}</p>}
    </li>
  );
}

/**
 * Tutor chat history: new chat, search, resume, rename, delete.
 * refreshKey — bump it after a message is saved so the list re-sorts.
 */
export default function ChatHistory({ activeId, refreshKey, onOpen, onNew, onDeleted, onRenamed }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  // debounced search; also reloads when a chat is saved
  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .get("/chat/sessions", { params: query.trim() ? { q: query.trim() } : {} })
        .then((res) => {
          if (cancelled) return;
          setSessions(res.data);
          setError("");
        })
        .catch((err) => !cancelled && setError(getErrorMessage(err, "Couldn't load your chats.")))
        .finally(() => !cancelled && setLoading(false));
    }, query ? 300 : 0);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query, refreshKey]);

  const groups = [];
  for (const s of sessions) {
    const label = groupLabel(s.updated_at);
    if (groups[groups.length - 1]?.label !== label) groups.push({ label, items: [] });
    groups[groups.length - 1].items.push(s);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 flex flex-col gap-2 border-b border-gray-100">
        <button
          type="button"
          onClick={onNew}
          className="w-full py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          + New chat
        </button>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search chats…"
          aria-label="Search chats"
          maxLength={100}
          className="w-full border border-gray-200 rounded-xl px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {loading ? (
          <div className="flex flex-col gap-2 animate-pulse px-1">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 bg-gray-100 rounded-xl" />)}
          </div>
        ) : error ? (
          <p className="text-xs text-red-500 px-2">{error}</p>
        ) : sessions.length === 0 ? (
          <p className="text-xs text-gray-400 px-2 py-4 text-center">
            {query.trim() ? `No chats mention “${query.trim()}”.` : "Your chats will appear here."}
          </p>
        ) : (
          groups.map((g) => (
            <div key={g.label} className="mb-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 px-3 py-1">{g.label}</p>
              <ul>
                {g.items.map((s) => (
                  <SessionRow
                    key={s.session_id}
                    s={s}
                    active={s.session_id === activeId}
                    onOpen={onOpen}
                    onRenamed={(updated) => {
                      setSessions((prev) => prev.map((x) => (x.session_id === updated.session_id ? { ...x, title: updated.title } : x)));
                      onRenamed?.(updated);
                    }}
                    onDeleted={(id) => {
                      setSessions((prev) => prev.filter((x) => x.session_id !== id));
                      onDeleted?.(id);
                    }}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
