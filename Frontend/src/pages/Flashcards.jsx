import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

// ── helpers ───────────────────────────────────────────────────────────────────

const RATINGS = [
  { key: "again", label: "Again", hint: "Forgot", color: "#DC2626", bg: "#FEE2E2" },
  { key: "hard", label: "Hard", hint: "Struggled", color: "#CA8A04", bg: "#FEF9C3" },
  { key: "good", label: "Good", hint: "Remembered", color: "#16A34A", bg: "#DCFCE7" },
  { key: "easy", label: "Easy", hint: "Instant", color: "#2563EB", bg: "#DBEAFE" },
];

const SOURCE_LABELS = {
  note: { label: "Lesson", bg: "#EEF2FF", fg: "#4338CA" },
  mistake: { label: "Quiz mistake", bg: "#FEE2E2", fg: "#B91C1C" },
  viva: { label: "Viva", bg: "#F3E8FF", fg: "#7E22CE" },
  solution: { label: "Solution mistake", bg: "#FFEDD5", fg: "#C2410C" },
  manual: { label: "Added by you", bg: "#F3F4F6", fg: "#4B5563" },
};

// start of the user's local day — so "reviewed today" means today where they are
function localMidnightISO() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

function dueLabel(dueAt) {
  const ms = new Date(dueAt).getTime() - Date.now();
  if (ms <= 0) return "Due now";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `Due in ${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `Due in ${hours}h`;
  return `Due in ${Math.round(hours / 24)}d`;
}

function SourceChip({ source }) {
  const s = SOURCE_LABELS[source] ?? SOURCE_LABELS.manual;
  return (
    <span className="text-[11px] font-medium px-2 py-0.5 rounded-full" style={{ background: s.bg, color: s.fg }}>
      {s.label}
    </span>
  );
}

function StatTile({ label, value, color }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center">
      <p className="text-2xl font-bold" style={{ color }}>{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
    </div>
  );
}

// ── Review tab: the daily queue ───────────────────────────────────────────────

function ReviewTab({ onStatsChange }) {
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState(false);
  const [rating, setRating] = useState(false);
  const [reviewedNow, setReviewedNow] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    return api
      .get("/flashcards/due", { params: { since: localMidnightISO() } })
      .then((res) => {
        setQueue(res.data.cards);
        setStats(res.data.stats);
        onStatsChange?.(res.data.stats);
      })
      .catch((err) => setError(getErrorMessage(err, "Could not load your review queue.")))
      .finally(() => setLoading(false));
  }, [onStatsChange]);

  useEffect(() => {
    load();
  }, [load]);

  const card = queue[0];

  const rate = useCallback(
    async (key) => {
      if (!card || rating) return;
      setRating(true);
      setError("");
      try {
        const res = await api.post(`/flashcards/${card.card_id}/review`, { rating: key });
        setReviewedNow((n) => n + 1);
        setRevealed(false);
        // "Again" → the card comes back later in this same session (like Anki)
        setQueue((q) => (key === "again" ? [...q.slice(1), res.data] : q.slice(1)));
      } catch (err) {
        setError(getErrorMessage(err, "Could not save that review. Try again."));
      } finally {
        setRating(false);
      }
    },
    [card, rating]
  );

  // Keyboard: Space/Enter shows the answer, 1–4 rate it
  useEffect(() => {
    function onKey(e) {
      if (!card || ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
      if (!revealed && (e.key === " " || e.key === "Enter")) {
        e.preventDefault();
        setRevealed(true);
      } else if (revealed && ["1", "2", "3", "4"].includes(e.key)) {
        rate(RATINGS[Number(e.key) - 1].key);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [card, revealed, rate]);

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto h-72 bg-white rounded-2xl border border-gray-100 animate-pulse" />
    );
  }

  if (!card) {
    const nextDue = stats?.next_due_at;
    return (
      <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-gray-100 shadow-sm p-10 flex flex-col items-center text-center gap-3">
        <span className="text-5xl">{stats?.total ? "🎉" : "🃏"}</span>
        <p className="text-lg font-semibold text-gray-800">
          {stats?.total ? "All caught up!" : "No flashcards yet"}
        </p>
        <p className="text-sm text-gray-500 max-w-sm">
          {stats?.total
            ? `${reviewedNow ? `You reviewed ${reviewedNow} card${reviewedNow === 1 ? "" : "s"} this session. ` : ""}` +
              (nextDue ? `Your next card is ${dueLabel(nextDue).toLowerCase()}.` : "")
            : "Make cards from any lesson in the Library tab. Wrong quiz answers and weak viva answers are added automatically."}
        </p>
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  const progressTotal = reviewedNow + queue.length;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 transition-all"
            style={{ width: `${(reviewedNow / Math.max(progressTotal, 1)) * 100}%` }}
          />
        </div>
        <span className="text-xs text-gray-500 flex-shrink-0">{queue.length} left</span>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 pt-5 flex items-center gap-2 flex-wrap">
          <SourceChip source={card.source} />
          {card.topic && <span className="text-xs text-gray-400">{card.topic}</span>}
          {card.lapses > 0 && <span className="text-xs text-orange-500">· forgotten {card.lapses}×</span>}
        </div>

        <div className="px-6 py-8 min-h-[140px] flex items-center justify-center text-center">
          <p className="text-lg font-medium text-gray-800 whitespace-pre-wrap">{card.front}</p>
        </div>

        {revealed ? (
          <div className="border-t border-dashed border-gray-200 px-6 py-6 text-center bg-gray-50/60">
            <p className="text-base text-gray-700 whitespace-pre-wrap">{card.back}</p>
          </div>
        ) : null}
      </div>

      {error && <p className="text-xs text-red-500 text-center">{error}</p>}

      {!revealed ? (
        <button
          type="button"
          onClick={() => setRevealed(true)}
          className="w-full py-3 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          Show answer <span className="opacity-60 text-xs ml-1">(Space)</span>
        </button>
      ) : (
        <div className="grid grid-cols-4 gap-2">
          {RATINGS.map((r, i) => (
            <button
              key={r.key}
              type="button"
              onClick={() => rate(r.key)}
              disabled={rating}
              className="py-2.5 rounded-xl border text-sm font-medium flex flex-col items-center gap-0.5 hover:opacity-90 disabled:opacity-50"
              style={{ background: r.bg, borderColor: r.bg, color: r.color }}
            >
              <span>{r.label}</span>
              <span className="text-[11px] opacity-80">
                {card.previews?.[r.key] ?? r.hint} · {i + 1}
              </span>
            </button>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-400 text-center">
        Be honest — the schedule adapts: hard cards come back sooner, easy ones much later.
      </p>
    </div>
  );
}

// ── Library tab: browse, add, edit, generate, export ─────────────────────────

function CardRow({ card, onDeleted, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [front, setFront] = useState(card.front);
  const [back, setBack] = useState(card.back);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setBusy(true);
    setError("");
    try {
      const res = await api.patch(`/flashcards/${card.card_id}`, { front, back });
      onSaved(res.data);
      setEditing(false);
    } catch (err) {
      setError(getErrorMessage(err, "Could not save."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete this flashcard?")) return;
    setBusy(true);
    try {
      await api.delete(`/flashcards/${card.card_id}`);
      onDeleted(card.card_id);
    } catch (err) {
      setError(getErrorMessage(err, "Could not delete."));
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <li className="py-3 flex flex-col gap-2">
        <textarea value={front} onChange={(e) => setFront(e.target.value)} rows={2} maxLength={500}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        <textarea value={back} onChange={(e) => setBack(e.target.value)} rows={3} maxLength={1500}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        {error && <p className="text-xs text-red-500">{error}</p>}
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={() => setEditing(false)} className="text-xs px-3 py-1.5 rounded-lg text-gray-500 hover:bg-gray-100">Cancel</button>
          <button type="button" onClick={save} disabled={busy || !front.trim() || !back.trim()}
            className="text-xs px-3 py-1.5 rounded-lg text-white disabled:opacity-50" style={{ background: "#4F46E5" }}>Save</button>
        </div>
      </li>
    );
  }

  return (
    <li className="py-3 flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800">{card.front}</p>
        <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">{card.back}</p>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <SourceChip source={card.source} />
          {card.topic && <span className="text-[11px] text-gray-400">{card.topic}</span>}
          <span className="text-[11px] text-gray-400">· {dueLabel(card.due_at)}</span>
          {card.interval_days >= 21 && <span className="text-[11px] text-green-600">· mastered</span>}
        </div>
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>
      <div className="flex gap-1 flex-shrink-0">
        <button type="button" onClick={() => setEditing(true)} disabled={busy}
          className="text-xs px-2 py-1 rounded-lg text-gray-500 hover:bg-gray-100" aria-label="Edit card">✏️</button>
        <button type="button" onClick={remove} disabled={busy}
          className="text-xs px-2 py-1 rounded-lg text-gray-500 hover:bg-red-50" aria-label="Delete card">🗑️</button>
      </div>
    </li>
  );
}

function LibraryTab({ onChanged, initialNoteId }) {
  const [cards, setCards] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [noteId, setNoteId] = useState(initialNoteId ? String(initialNoteId) : "");
  const [count, setCount] = useState(8);
  const [generating, setGenerating] = useState(false);
  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .get("/flashcards", { params: search.trim() ? { search: search.trim() } : {} })
        .then((res) => setCards(res.data))
        .catch((err) => setError(getErrorMessage(err, "Could not load flashcards.")))
        .finally(() => setLoading(false));
    }, 250); // debounce typing
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    api.get("/lessons/all").then((res) => {
      const list = res.data.slice().reverse();
      setLessons(list);
      setNoteId((prev) => prev || (list[0] ? String(list[0].note_id) : ""));
    }).catch(() => {});
  }, []);

  async function generate() {
    setGenerating(true);
    setMessage("");
    setError("");
    try {
      const res = await api.post("/flashcards/generate", { note_id: Number(noteId), count });
      setCards((prev) => [...res.data.added, ...prev]);
      setMessage(res.data.message);
      onChanged();
    } catch (err) {
      setError(getErrorMessage(err, "Could not generate flashcards."));
    } finally {
      setGenerating(false);
    }
  }

  async function addCard(e) {
    e.preventDefault();
    setMessage("");
    setError("");
    try {
      const res = await api.post("/flashcards", { front, back });
      setCards((prev) => [res.data, ...prev]);
      setFront("");
      setBack("");
      setMessage("Card added — it's due now.");
      onChanged();
    } catch (err) {
      setError(getErrorMessage(err, "Could not add the card."));
    }
  }

  async function exportAnki() {
    setError("");
    try {
      const res = await api.get("/flashcards/export/anki", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "study-assistant-flashcards.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setMessage("Exported. In Anki: File → Import → choose the file → Import.");
    } catch {
      setError("Nothing to export yet — add some flashcards first.");
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 flex flex-col gap-4">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-gray-800">✨ Make cards from a lesson</h3>
          {lessons.length === 0 ? (
            <p className="text-xs text-gray-400">Generate a lesson first.</p>
          ) : (
            <>
              <select value={noteId} onChange={(e) => setNoteId(e.target.value)} disabled={generating}
                className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {lessons.map((n) => <option key={n.note_id} value={String(n.note_id)}>{n.title}</option>)}
              </select>
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500">Cards</label>
                {[5, 8, 12].map((n) => (
                  <button key={n} type="button" onClick={() => setCount(n)}
                    className="w-9 h-8 rounded-lg text-xs font-medium border"
                    style={{ background: count === n ? "#EEF2FF" : "#fff", borderColor: count === n ? "#4F46E5" : "#E5E7EB", color: count === n ? "#4338CA" : "#374151" }}>
                    {n}
                  </button>
                ))}
              </div>
              <button type="button" onClick={generate} disabled={generating || !noteId}
                className="flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-medium text-white disabled:opacity-60"
                style={{ background: "#4F46E5" }}>
                {generating ? <><Spinner /> Writing cards…</> : "Generate flashcards"}
              </button>
            </>
          )}
        </div>

        <form onSubmit={addCard} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-gray-800">➕ Add a card</h3>
          <textarea value={front} onChange={(e) => setFront(e.target.value)} rows={2} maxLength={500} placeholder="Front — question or cue"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <textarea value={back} onChange={(e) => setBack(e.target.value)} rows={3} maxLength={1500} placeholder="Back — answer"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
          <button type="submit" disabled={!front.trim() || !back.trim()}
            className="py-2 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-600 hover:bg-indigo-50 disabled:opacity-50">
            Add card
          </button>
        </form>

        <button type="button" onClick={exportAnki}
          className="py-2.5 rounded-xl text-sm font-medium border border-gray-200 text-gray-600 bg-white hover:bg-gray-50">
          ⬇ Export all to Anki
        </button>
      </div>

      <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <div className="flex items-center justify-between gap-3 mb-2">
          <h3 className="text-sm font-semibold text-gray-800">
            Your cards {!loading && <span className="text-xs font-normal text-gray-400">({cards.length})</span>}
          </h3>
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search cards…"
            className="border border-gray-200 rounded-xl px-3 py-1.5 text-xs w-48 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        </div>
        {message && <p className="text-xs text-green-700 bg-green-50 rounded-lg px-3 py-2 mb-2">{message}</p>}
        {error && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-2">{error}</p>}
        {loading ? (
          <div className="flex flex-col gap-2 animate-pulse">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-14 bg-gray-100 rounded-xl" />)}
          </div>
        ) : cards.length === 0 ? (
          <p className="text-sm text-gray-400 py-10 text-center">
            {search ? "No cards match your search." : "No cards yet — generate some from a lesson."}
          </p>
        ) : (
          <ul className="divide-y divide-gray-50">
            {cards.map((c) => (
              <CardRow
                key={c.card_id}
                card={c}
                onDeleted={(id) => {
                  setCards((prev) => prev.filter((x) => x.card_id !== id));
                  onChanged();
                }}
                onSaved={(updated) => setCards((prev) => prev.map((x) => (x.card_id === updated.card_id ? updated : x)))}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function Flashcards() {
  usePageTitle("Flashcards");
  const location = useLocation();
  const [tab, setTab] = useState(location.state?.tab ?? "review");
  const [stats, setStats] = useState(null);
  const [reviewKey, setReviewKey] = useState(0);   // bump to reload the queue after library changes

  const refreshStats = useCallback(() => {
    api.get("/flashcards/stats", { params: { since: localMidnightISO() } }).then((res) => setStats(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-6">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
          <h1 className="text-3xl font-bold text-gray-900">Flashcards</h1>
          <p className="text-sm text-gray-500 mt-1">
            Spaced repetition (SM-2): each card comes back right before you'd forget it.
          </p>
        </div>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <StatTile label="Due now" value={stats.due_now} color="#4F46E5" />
            <StatTile label="Reviewed today" value={stats.reviewed_today} color="#16A34A" />
            <StatTile label="Learning" value={stats.learning + stats.new} color="#CA8A04" />
            <StatTile label="Mastered (21d+)" value={stats.mastered} color="#2563EB" />
          </div>
        )}

        <div className="flex gap-1 mb-6 bg-white border border-gray-100 rounded-xl p-1 w-fit shadow-sm">
          {[
            ["review", `Review${stats?.due_now ? ` (${stats.due_now})` : ""}`],
            ["library", "Library"],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                setTab(key);
                if (key === "review") setReviewKey((k) => k + 1);
              }}
              className="px-4 py-1.5 rounded-lg text-sm font-medium"
              style={{ background: tab === key ? "#4F46E5" : "transparent", color: tab === key ? "#fff" : "#6B7280" }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "review" ? (
          <ReviewTab key={reviewKey} onStatsChange={setStats} />
        ) : (
          <LibraryTab onChanged={refreshStats} initialNoteId={location.state?.noteId} />
        )}
      </div>
    </div>
  );
}
