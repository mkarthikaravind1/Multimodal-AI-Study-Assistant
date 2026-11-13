import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

// ── helpers ───────────────────────────────────────────────────────────────────

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]; // 0 = Monday, like Python

const KINDS = {
  learn: { label: "Learn", fg: "#4338CA", bg: "#EEF2FF" },
  practice: { label: "Practice", fg: "#0369A1", bg: "#E0F2FE" },
  review: { label: "Quick review", fg: "#7E22CE", bg: "#F3E8FF" },
  revise: { label: "Revise", fg: "#B45309", bg: "#FEF3C7" },
  quiz: { label: "Quiz yourself", fg: "#BE123C", bg: "#FFE4E6" },
  mock: { label: "Mock test", fg: "#15803D", bg: "#DCFCE7" },
};

const STATUS = {
  weak: { label: "Weak", fg: "#DC2626", bg: "#FEE2E2", tip: "Your quizzes/viva on this were below 70% — it gets extra time" },
  ok: { label: "OK", fg: "#CA8A04", bg: "#FEF9C3", tip: "70–85% recently" },
  strong: { label: "Strong", fg: "#16A34A", bg: "#DCFCE7", tip: "85%+ recently — less time needed" },
  new: { label: "New", fg: "#6B7280", bg: "#F3F4F6", tip: "No quiz or viva on this yet" },
};

const SIZES = [
  { value: 1, label: "S", title: "Small — about an hour" },
  { value: 2, label: "M", title: "Medium" },
  { value: 3, label: "L", title: "Large or hard" },
];

// the student's own calendar date (not UTC)
function localISO(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseISO(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function daysBetween(fromISO, toISO) {
  return Math.round((parseISO(toISO) - parseISO(fromISO)) / 86400000);
}

function formatDay(iso, opts = { weekday: "short", day: "numeric", month: "short" }) {
  return parseISO(iso).toLocaleDateString("en-IN", opts);
}

function formatMinutes(min) {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function pct(progress) {
  return progress.total_minutes ? Math.round((100 * progress.done_minutes) / progress.total_minutes) : 0;
}

function ProgressBar({ value, height = 8 }) {
  return (
    <div className="w-full rounded-full bg-gray-100 overflow-hidden" style={{ height }}>
      <div className="h-full rounded-full transition-all" style={{ width: `${value}%`, background: "#4F46E5" }} />
    </div>
  );
}

const inputCls =
  "w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500";

// ── list of plans ─────────────────────────────────────────────────────────────

function PlanList({ plans, loading, onOpen, onNew }) {
  const today = localISO();
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800">Your exam plans</h2>
        <button
          type="button"
          onClick={onNew}
          className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          + New plan
        </button>
      </div>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
          {[0, 1].map((i) => <div key={i} className="h-32 bg-white rounded-2xl border border-gray-100" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {plans.map((p) => {
            const left = daysBetween(today, p.exam_date);
            const done = pct(p.progress);
            return (
              <button
                key={p.plan_id}
                type="button"
                onClick={() => onOpen(p.plan_id)}
                className="text-left bg-white rounded-2xl border border-gray-100 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 transition-all"
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="min-w-0">
                    <p className="text-base font-semibold text-gray-800 truncate">{p.exam_name}</p>
                    <p className="text-xs text-gray-400">
                      {formatDay(p.exam_date, { day: "numeric", month: "short", year: "numeric" })} · {p.topics} topics
                    </p>
                  </div>
                  <span
                    className="text-xs font-semibold px-2 py-1 rounded-lg flex-shrink-0"
                    style={
                      left < 0
                        ? { background: "#F3F4F6", color: "#6B7280" }
                        : left <= 3
                        ? { background: "#FEE2E2", color: "#DC2626" }
                        : { background: "#EEF2FF", color: "#4338CA" }
                    }
                  >
                    {left < 0 ? "Done" : left === 0 ? "Exam today" : `${left} day${left === 1 ? "" : "s"} left`}
                  </span>
                </div>
                <ProgressBar value={done} />
                <p className="text-xs text-gray-400 mt-1.5">{done}% of study time done</p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── step 1: syllabus → topics ────────────────────────────────────────────────

function SyllabusStep({ onExtracted, onManual, onCancel, canCancel }) {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("file"); // file | text
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  async function submit(e) {
    e.preventDefault();
    const form = new FormData();
    if (mode === "file") {
      if (!file) return;
      form.append("file", file);
    } else {
      if (text.trim().length < 20) {
        setError("Paste a bit more of the syllabus.");
        return;
      }
      form.append("text", text.trim());
    }
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/planner/extract", form);
      onExtracted(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't read the syllabus. Try again."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4 max-w-2xl mx-auto w-full">
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style={{ background: "#EEF2FF" }}>🗓️</span>
        <div>
          <h2 className="text-base font-semibold text-gray-800">1 · Your syllabus</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            The topics are pulled out of it and matched with your quiz and viva results — weak topics get extra time.
          </p>
        </div>
      </div>

      <div className="flex gap-1 p-1 bg-gray-100 rounded-xl self-start text-sm">
        {[["file", "Upload PDF"], ["text", "Paste text"]].map(([m, label]) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className="px-3 py-1.5 rounded-lg font-medium"
            style={mode === m ? { background: "#fff", color: "#4338CA", boxShadow: "0 1px 2px rgba(0,0,0,.06)" } : { color: "#6B7280" }}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

      {mode === "file" ? (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="rounded-2xl border-2 border-dashed border-gray-200 hover:border-indigo-300 bg-gray-50/50 py-10 flex flex-col items-center gap-1"
        >
          <span className="text-2xl">📄</span>
          <span className="text-sm font-medium text-gray-700">{file ? file.name : "Choose the syllabus PDF"}</span>
          <span className="text-xs text-gray-400">{file ? "Click to choose another" : "PDF or .txt, up to 20 MB"}</span>
        </button>
      ) : (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          maxLength={20000}
          disabled={busy}
          placeholder={"UNIT I – Trees: binary trees, BST, AVL trees\nUNIT II – Graphs: BFS, DFS, shortest paths…"}
          className={`${inputCls} resize-y`}
        />
      )}
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt,application/pdf,text/plain"
        className="hidden"
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          e.target.value = "";
        }}
      />

      <button
        type="submit"
        disabled={busy || (mode === "file" ? !file : !text.trim())}
        className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
        style={{ background: "#4F46E5" }}
      >
        {busy ? <><Spinner /> Reading the syllabus…</> : "Find the topics"}
      </button>
      <div className="flex items-center justify-between text-xs">
        <button type="button" onClick={onManual} disabled={busy} className="text-indigo-600 hover:underline">
          No syllabus? Type the topics yourself →
        </button>
        {canCancel && (
          <button type="button" onClick={onCancel} disabled={busy} className="text-gray-400 hover:text-gray-600">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

// ── step 2: check topics, pick dates ─────────────────────────────────────────

let topicKey = 0;
const withKeys = (topics) => topics.map((t) => ({ ...t, key: ++topicKey }));

function SetupStep({ extracted, onCreated, onBack }) {
  const today = localISO();
  const [examName, setExamName] = useState(extracted.exam_name || "");
  const [examDate, setExamDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return localISO(d);
  });
  const [minDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return localISO(d);
  });
  const [hours, setHours] = useState(2);
  const [restDays, setRestDays] = useState([6]);
  const [topics, setTopics] = useState(() => withKeys(extracted.topics));
  const [newTopic, setNewTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const daysLeft = daysBetween(today, examDate);
  const weakCount = topics.filter((t) => t.status === "weak").length;
  const valid = examName.trim() && daysLeft >= 1 && topics.length > 0 && topics.every((t) => t.topic.trim().length >= 2);

  function update(key, patch) {
    setTopics((prev) => prev.map((t) => (t.key === key ? { ...t, ...patch } : t)));
  }

  function addTopic(e) {
    e.preventDefault();
    const name = newTopic.trim();
    if (name.length < 2) return;
    setTopics((prev) => [...prev, ...withKeys([{ unit: "", topic: name, size: 2, status: "new", score: null }])]);
    setNewTopic("");
  }

  async function create() {
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/planner/plans", {
        exam_name: examName.trim(),
        exam_date: examDate,
        start_date: today,
        minutes_per_day: Math.round(hours * 60),
        rest_days: restDays,
        topics: topics.map((t) => ({ unit: t.unit || "", topic: t.topic.trim(), size: t.size })),
        syllabus_filename: extracted.syllabus_filename || null,
      });
      onCreated(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't create the plan."));
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 items-start">
      {/* topics */}
      <div className="lg:col-span-3 bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">2 · Check the topics</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Rename, remove or resize anything the AI got wrong.
            {weakCount > 0 && <> <span className="text-red-600 font-medium">{weakCount} weak topic{weakCount > 1 ? "s" : ""}</span> from your quiz/viva results will get extra time.</>}
          </p>
        </div>
        {topics.length === 0 && <p className="text-sm text-gray-400 italic">No topics yet — add them below.</p>}
        <ul className="flex flex-col gap-2">
          {topics.map((t, i) => {
            const st = STATUS[t.status] ?? STATUS.new;
            const showUnit = t.unit && t.unit !== topics[i - 1]?.unit;
            return (
              <li key={t.key}>
                {showUnit && <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mt-2 mb-1">{t.unit}</p>}
                <div className="flex items-center gap-2">
                  <input
                    value={t.topic}
                    onChange={(e) => update(t.key, { topic: e.target.value })}
                    maxLength={120}
                    aria-label="Topic name"
                    className={`${inputCls} flex-1 min-w-0`}
                  />
                  <span
                    className={`text-[11px] font-semibold px-2 py-1 rounded-lg flex-shrink-0 cursor-help ${t.status === "new" ? "hidden sm:inline" : ""}`}
                    style={{ background: st.bg, color: st.fg }}
                    title={t.score != null ? `${st.tip} (${Math.round(t.score)}% on "${t.matched_topic}")` : st.tip}
                  >
                    {st.label}
                    {t.score != null ? ` ${Math.round(t.score)}%` : ""}
                  </span>
                  <div className="flex rounded-lg border border-gray-200 overflow-hidden flex-shrink-0" role="radiogroup" aria-label="Size">
                    {SIZES.map((s) => (
                      <button
                        key={s.value}
                        type="button"
                        title={s.title}
                        role="radio"
                        aria-checked={t.size === s.value}
                        onClick={() => update(t.key, { size: s.value })}
                        className="w-7 h-8 text-xs font-medium"
                        style={t.size === s.value ? { background: "#4F46E5", color: "#fff" } : { color: "#6B7280" }}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setTopics((prev) => prev.filter((x) => x.key !== t.key))}
                    aria-label={`Remove ${t.topic}`}
                    className="text-gray-300 hover:text-red-500 px-1 flex-shrink-0"
                  >
                    ✕
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
        {topics.length < 40 && (
          <form onSubmit={addTopic} className="flex gap-2">
            <input
              value={newTopic}
              onChange={(e) => setNewTopic(e.target.value)}
              maxLength={120}
              placeholder="Add a topic"
              className={`${inputCls} flex-1`}
            />
            <button type="submit" className="px-4 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-700 hover:bg-indigo-50">
              Add
            </button>
          </form>
        )}
      </div>

      {/* dates + hours */}
      <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4 lg:sticky lg:top-6">
        <h2 className="text-base font-semibold text-gray-800">3 · When and how much</h2>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Exam / subject</label>
          <input value={examName} onChange={(e) => setExamName(e.target.value)} maxLength={200} placeholder="e.g. Data Structures end-sem" className={inputCls} />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Exam date</label>
          <input type="date" value={examDate} min={minDate} onChange={(e) => setExamDate(e.target.value)} className={inputCls} />
          <p className="text-xs mt-1" style={{ color: daysLeft >= 1 ? "#6B7280" : "#DC2626" }}>
            {daysLeft >= 1 ? `${daysLeft} day${daysLeft > 1 ? "s" : ""} from today` : "Pick a date after today"}
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">
            Study time per day: <span className="text-gray-800">{formatMinutes(Math.round(hours * 60))}</span>
          </label>
          <input type="range" min={0.5} max={8} step={0.5} value={hours} onChange={(e) => setHours(Number(e.target.value))} className="w-full accent-indigo-600" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Days off</label>
          <div className="flex flex-wrap gap-1.5">
            {WEEKDAYS.map((w, i) => {
              const on = restDays.includes(i);
              return (
                <button
                  key={w}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setRestDays((prev) => (on ? prev.filter((x) => x !== i) : [...prev, i]))}
                  className="w-11 h-8 rounded-lg text-xs font-medium border"
                  style={on ? { background: "#FEF3C7", borderColor: "#F59E0B", color: "#92400E" } : { borderColor: "#E5E7EB", color: "#374151" }}
                >
                  {w}
                </button>
              );
            })}
          </div>
        </div>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <button
          type="button"
          onClick={create}
          disabled={!valid || busy}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
          style={{ background: "#4F46E5" }}
        >
          {busy ? <><Spinner /> Building your plan…</> : "Create my plan"}
        </button>
        <button type="button" onClick={onBack} disabled={busy} className="text-xs text-gray-400 hover:text-gray-600">
          ← Back to syllabus
        </button>
      </div>
    </div>
  );
}

// ── the plan ──────────────────────────────────────────────────────────────────

function ItemRow({ item, onToggle, saving, compact }) {
  const navigate = useNavigate();
  const k = KINDS[item.kind] ?? KINDS.learn;
  const action =
    item.kind === "learn" || item.kind === "practice"
      ? { label: "Make a lesson", go: () => navigate("/lesson", { state: { topic: item.topic } }) }
      : item.kind === "quiz"
      ? { label: "Take a quiz", go: () => navigate("/quiz") }
      : item.kind === "review"
      ? { label: "Flashcards", go: () => navigate("/flashcards") }
      : item.kind === "revise"
      ? { label: "Ask the tutor", go: () => navigate("/tutor", { state: { prefill: `Give me a quick revision summary of ${item.topic}, with the key points I must remember for the exam.` } }) }
      : null;
  return (
    <li className="flex items-center gap-3 py-1.5">
      <input
        type="checkbox"
        checked={item.done}
        disabled={saving}
        onChange={(e) => onToggle(item.id, e.target.checked)}
        aria-label={`Mark ${k.label} ${item.topic} done`}
        className="w-4 h-4 accent-indigo-600 flex-shrink-0"
      />
      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md flex-shrink-0" style={{ background: k.bg, color: k.fg }}>
        {k.label}
      </span>
      <span className={`text-sm flex-1 min-w-0 truncate ${item.done ? "line-through text-gray-400" : "text-gray-800"}`}>{item.topic}</span>
      <span className="text-xs text-gray-400 flex-shrink-0">{formatMinutes(item.minutes)}</span>
      {!compact && action && !item.done && (
        <button type="button" onClick={action.go} className="text-xs text-indigo-600 hover:underline flex-shrink-0 hidden sm:inline">
          {action.label} →
        </button>
      )}
    </li>
  );
}

function CalendarExport({ plan }) {
  const [time, setTime] = useState("18:00");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function download() {
    setBusy(true);
    setMsg("");
    try {
      const res = await api.get(`/planner/plans/${plan.plan_id}/ics`, { params: { start_time: time }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `study-plan-${plan.exam_name.replace(/[^A-Za-z0-9]+/g, "-").slice(0, 40) || "exam"}.ics`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setMsg("Downloaded. Open it, or import it in Google Calendar → Settings → Import.");
    } catch (err) {
      setMsg(getErrorMessage(err, "Export failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-gray-800">📅 Add to your calendar</h3>
      <p className="text-xs text-gray-400">Each session becomes an event, back to back with 10-minute breaks, plus the exam day.</p>
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label className="block text-[11px] font-medium text-gray-500 mb-1">Daily start time</label>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value || "18:00")} className={inputCls} />
        </div>
        <button
          type="button"
          onClick={download}
          disabled={busy}
          className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60 flex items-center gap-2"
          style={{ background: "#4F46E5" }}
        >
          {busy ? <Spinner /> : null} Download .ics
        </button>
      </div>
      {msg && <p className="text-xs text-gray-500">{msg}</p>}
    </div>
  );
}

function DayCard({ day, highlight, onToggle, savingId }) {
  const total = day.items.reduce((s, i) => s + i.minutes, 0);
  const doneMin = day.items.filter((i) => i.done).reduce((s, i) => s + i.minutes, 0);
  return (
    <div
      className="bg-white rounded-2xl border shadow-sm px-5 py-4"
      style={{ borderColor: highlight ? "#A5B4FC" : "#F3F4F6", boxShadow: highlight ? "0 0 0 3px #EEF2FF" : undefined }}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <p className="text-sm font-semibold text-gray-800">
          {highlight ? "Today · " : ""}
          {formatDay(day.date)}
        </p>
        {day.exam ? (
          <span className="text-xs font-semibold px-2 py-0.5 rounded-lg bg-red-600 text-white">📝 Exam day</span>
        ) : day.rest ? (
          <span className="text-xs text-amber-700">Day off</span>
        ) : (
          <span className="text-xs text-gray-400">{doneMin ? `${formatMinutes(doneMin)} / ` : ""}{formatMinutes(total)}</span>
        )}
      </div>
      {day.exam ? (
        <p className="text-sm text-gray-500">All the best! Sleep early the night before and skim your flashcards in the morning.</p>
      ) : day.rest ? (
        <p className="text-xs text-gray-400">Rest — no sessions planned.</p>
      ) : day.items.length === 0 ? (
        <p className="text-xs text-gray-400">Nothing planned.</p>
      ) : (
        <ul className="divide-y divide-gray-50">
          {day.items.map((it) => (
            <ItemRow key={it.id} item={it} onToggle={onToggle} saving={savingId === it.id} compact={!highlight} />
          ))}
        </ul>
      )}
    </div>
  );
}

function PlanView({ plan, setPlan, onDeleted }) {
  const today = localISO();
  const [savingId, setSavingId] = useState(null);
  const [replanning, setReplanning] = useState(false);
  const [error, setError] = useState("");
  const [showPast, setShowPast] = useState(false);

  const left = daysBetween(today, plan.exam_date);
  const done = pct(plan.progress);
  const todayDay = plan.days.find((d) => d.date === today);
  const missed = useMemo(
    () => plan.days.filter((d) => d.date < today).flatMap((d) => d.items.filter((i) => !i.done)),
    [plan.days, today]
  );
  const upcoming = plan.days.filter((d) => d.date > today);
  const past = plan.days.filter((d) => d.date < today);

  async function toggle(itemId, isDone) {
    setSavingId(itemId);
    setError("");
    // optimistic tick
    setPlan({
      ...plan,
      days: plan.days.map((d) => ({ ...d, items: d.items.map((i) => (i.id === itemId ? { ...i, done: isDone } : i)) })),
    });
    try {
      const res = await api.patch(`/planner/plans/${plan.plan_id}/items/${encodeURIComponent(itemId)}`, { done: isDone });
      setPlan(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't save that tick."));
      setPlan(plan);
    } finally {
      setSavingId(null);
    }
  }

  async function doReplan() {
    setReplanning(true);
    setError("");
    try {
      const res = await api.post(`/planner/plans/${plan.plan_id}/replan`, { today });
      setPlan(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't re-plan."));
    } finally {
      setReplanning(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete the plan for "${plan.exam_name}"?`)) return;
    try {
      await api.delete(`/planner/plans/${plan.plan_id}`);
      onDeleted();
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't delete the plan."));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* header */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col md:flex-row md:items-center gap-5">
        <div
          className="w-20 h-20 rounded-2xl flex flex-col items-center justify-center flex-shrink-0"
          style={left <= 3 && left >= 0 ? { background: "#FEE2E2", color: "#DC2626" } : { background: "#EEF2FF", color: "#4338CA" }}
        >
          <span className="text-2xl font-bold leading-none">{Math.max(0, left)}</span>
          <span className="text-[11px] font-medium mt-0.5">day{left === 1 ? "" : "s"} left</span>
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-gray-900 truncate">{plan.exam_name}</h2>
          <p className="text-xs text-gray-400 mb-3">
            Exam on {formatDay(plan.exam_date, { weekday: "long", day: "numeric", month: "long" })} · {formatMinutes(plan.minutes_per_day)} a day
            {plan.rest_days.length ? ` · ${plan.rest_days.map((d) => WEEKDAYS[d]).join(", ")} off` : ""}
          </p>
          <ProgressBar value={done} />
          <p className="text-xs text-gray-500 mt-1.5">
            {done}% done · {formatMinutes(plan.progress.done_minutes)} of {formatMinutes(plan.progress.total_minutes)}
          </p>
        </div>
      </div>

      {error && <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

      {missed.length > 0 && left > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <p className="text-sm text-amber-800 flex-1">
            <strong>{missed.length} session{missed.length > 1 ? "s" : ""}</strong> from earlier days aren't ticked off
            ({formatMinutes(missed.reduce((s, i) => s + i.minutes, 0))}). Re-plan to spread what's left over the remaining days —
            weak topics are re-checked against your latest scores.
          </p>
          <button
            type="button"
            onClick={doReplan}
            disabled={replanning}
            className="px-4 py-2 rounded-xl text-sm font-medium text-white flex items-center gap-2 flex-shrink-0 disabled:opacity-60"
            style={{ background: "#D97706" }}
          >
            {replanning ? <Spinner /> : "↻"} Re-plan from today
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 flex flex-col gap-3">
          {todayDay && <DayCard day={todayDay} highlight onToggle={toggle} savingId={savingId} />}
          {!todayDay && left > 0 && parseISO(plan.start_date) > parseISO(today) && (
            <p className="text-sm text-gray-500">Your plan starts on {formatDay(plan.start_date)}.</p>
          )}
          {upcoming.length > 0 && <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mt-2">Coming up</h3>}
          {upcoming.map((d) => <DayCard key={d.date} day={d} onToggle={toggle} savingId={savingId} />)}
          {past.length > 0 && (
            <button type="button" onClick={() => setShowPast((s) => !s)} className="self-start text-xs text-gray-500 hover:text-indigo-600 mt-2">
              {showPast ? "▾ Hide" : "▸ Show"} past days ({past.length})
            </button>
          )}
          {showPast && past.slice().reverse().map((d) => <DayCard key={d.date} day={d} onToggle={toggle} savingId={savingId} />)}
        </div>

        <div className="flex flex-col gap-4 lg:sticky lg:top-6">
          <CalendarExport plan={plan} />
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-3">Topics and time</h3>
            <ul className="flex flex-col gap-2">
              {plan.topics.map((t) => {
                const st = STATUS[t.status] ?? STATUS.new;
                return (
                  <li key={t.topic} className="flex items-center gap-2 text-sm">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: st.fg }} title={st.tip} />
                    <span className="flex-1 min-w-0 truncate text-gray-700" title={t.topic}>{t.topic}</span>
                    {t.status !== "new" && (
                      <span className="text-[11px] px-1.5 py-0.5 rounded flex-shrink-0" style={{ background: st.bg, color: st.fg }}>
                        {st.label}
                      </span>
                    )}
                    <span className="text-xs text-gray-400 flex-shrink-0 w-14 text-right">{t.minutes ? formatMinutes(t.minutes) : "revise"}</span>
                  </li>
                );
              })}
            </ul>
          </div>
          <button type="button" onClick={remove} className="self-end text-xs text-gray-400 hover:text-red-600">
            Delete this plan
          </button>
        </div>
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function Planner() {
  usePageTitle("Exam planner");
  const [view, setView] = useState("list"); // list | syllabus | setup | plan
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [extracted, setExtracted] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");

  // loads the plan list; with no plans yet, go straight to making one
  function loadPlans() {
    return api
      .get("/planner/plans")
      .then((res) => res.data)
      .catch(() => [])
      .then((list) => {
        setPlans(list);
        setLoading(false);
        if (list.length === 0) setView("syllabus");
      });
  }

  useEffect(() => {
    api
      .get("/planner/plans")
      .then((res) => res.data)
      .catch(() => [])
      .then((list) => {
        setPlans(list);
        setLoading(false);
        if (list.length === 0) setView("syllabus");
      });
  }, []);

  async function open(planId) {
    setError("");
    try {
      const res = await api.get(`/planner/plans/${planId}`);
      setPlan(res.data);
      setView("plan");
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't open that plan."));
    }
  }

  function backToList() {
    setPlan(null);
    setExtracted(null);
    setView("list");
    setLoading(true);
    loadPlans();
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
            <h1 className="text-3xl font-bold text-gray-900">Exam planner</h1>
            <p className="text-sm text-gray-500 mt-1">A day-by-day plan to your exam — with extra time for your weak topics.</p>
          </div>
          {view !== "list" && plans.length > 0 && (
            <button type="button" onClick={backToList} className="text-xs px-3 py-1.5 rounded-xl border border-gray-200 text-gray-500 hover:bg-white">
              ← All plans
            </button>
          )}
        </div>

        {error && <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

        {view === "list" && <PlanList plans={plans} loading={loading} onOpen={open} onNew={() => setView("syllabus")} />}
        {view === "syllabus" && (
          <SyllabusStep
            canCancel={plans.length > 0}
            onCancel={() => setView("list")}
            onExtracted={(data) => {
              setExtracted(data);
              setView("setup");
            }}
            onManual={() => {
              setExtracted({ exam_name: "", topics: [], syllabus_filename: null });
              setView("setup");
            }}
          />
        )}
        {view === "setup" && extracted && (
          <SetupStep
            extracted={extracted}
            onBack={() => setView("syllabus")}
            onCreated={(p) => {
              setPlan(p);
              setPlans((prev) => [...prev, { plan_id: p.plan_id }]);
              setView("plan");
            }}
          />
        )}
        {view === "plan" && plan && <PlanView key={plan.plan_id} plan={plan} setPlan={setPlan} onDeleted={backToList} />}
      </div>
    </div>
  );
}
