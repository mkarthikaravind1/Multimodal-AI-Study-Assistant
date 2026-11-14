import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

// ── shared helpers ────────────────────────────────────────────────────────────

const inputCls =
  "w-full border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-800 placeholder-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500";

const QUESTION_TYPES = [
  ["mcq", "Multiple choice"],
  ["true_false", "True / false"],
  ["fill_blank", "Fill in the blank"],
  ["numerical", "Numerical"],
];

// Score → colour band. The number is always printed too, so it isn't colour-only.
function heat(score) {
  if (score == null) return { bg: "#F9FAFB", fg: "#9CA3AF" };
  if (score < 50) return { bg: "#FEE2E2", fg: "#B91C1C" };
  if (score < 70) return { bg: "#FFEDD5", fg: "#C2410C" };
  if (score < 85) return { bg: "#ECFCCB", fg: "#4D7C0F" };
  return { bg: "#DCFCE7", fg: "#15803D" };
}

function fmtScore(s) {
  return s == null ? "—" : `${Math.round(s)}%`;
}

function fmtDate(iso, withYear = false) {
  if (!iso) return "";
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", ...(withYear ? { year: "numeric" } : {}) });
}

function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function DueChip({ due, done }) {
  if (!due) return null;
  const overdue = !done && due < localToday();
  return (
    <span className="text-[11px] px-1.5 py-0.5 rounded" style={overdue ? { background: "#FEE2E2", color: "#B91C1C" } : { background: "#F3F4F6", color: "#6B7280" }}>
      {overdue ? "Overdue · " : "Due "}
      {fmtDate(due)}
    </span>
  );
}

function ErrorBox({ children }) {
  return children ? <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{children}</div> : null;
}

function ClassCards({ classes, onOpen, teacherView }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {classes.map((c) => (
        <button
          key={c.class_id}
          type="button"
          onClick={() => onOpen(c.class_id)}
          className="text-left bg-white rounded-2xl border border-gray-100 shadow-sm p-5 hover:shadow-md hover:-translate-y-0.5 transition-all"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-base font-semibold text-gray-800 truncate">{c.name}</p>
              <p className="text-xs text-gray-400 truncate">{c.subject || (teacherView ? "No subject" : `Teacher: ${c.teacher}`)}</p>
            </div>
            {teacherView && c.join_code && (
              <span className="font-mono text-sm font-semibold tracking-widest px-2 py-1 rounded-lg bg-indigo-50 text-indigo-700 flex-shrink-0">
                {c.join_code}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-3">
            {teacherView ? `${c.students} student${c.students === 1 ? "" : "s"} · ` : `Teacher: ${c.teacher} · `}
            {c.assignments} assignment{c.assignments === 1 ? "" : "s"}
          </p>
        </button>
      ))}
    </div>
  );
}

// ── student ───────────────────────────────────────────────────────────────────

function JoinForm({ onJoined }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function join(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/classes/join", { code });
      setCode("");
      onJoined(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't join. Check the code."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={join} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold text-gray-800">Join a class</h2>
        <p className="text-xs text-gray-400 mt-0.5">Type the 6-character code your teacher gave you.</p>
      </div>
      <div className="flex gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          maxLength={12}
          placeholder="e.g. K7QP3M"
          aria-label="Class code"
          autoCapitalize="characters"
          className={`${inputCls} font-mono tracking-widest uppercase flex-1`}
        />
        <button
          type="submit"
          disabled={busy || code.replace(/[\s-]/g, "").length < 4}
          className="px-5 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          style={{ background: "#4F46E5" }}
        >
          {busy ? <Spinner /> : "Join"}
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </form>
  );
}

function StudentClass({ detail, onLeft }) {
  const navigate = useNavigate();
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState("");

  async function start(a) {
    setBusyId(a.assignment_id);
    setError("");
    try {
      const res = await api.post(`/classes/assignments/${a.assignment_id}/start`);
      navigate("/quiz", { state: { assignmentQuiz: res.data.quiz } });
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't open the assignment."));
      setBusyId(null);
    }
  }

  async function leave() {
    if (!window.confirm(`Leave "${detail.name}"? Your own quiz results stay with you.`)) return;
    try {
      await api.post(`/classes/${detail.class_id}/leave`);
      onLeft();
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't leave the class."));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-xl font-bold text-gray-900">{detail.name}</h2>
        <p className="text-sm text-gray-500">{detail.subject ? `${detail.subject} · ` : ""}Teacher: {detail.teacher}</p>
      </div>
      <ErrorBox>{error}</ErrorBox>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Assignments</h3>
        {detail.assignments.length === 0 ? (
          <p className="text-sm text-gray-400">Nothing assigned yet.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {detail.assignments.map((a) => {
              const m = a.mine;
              const h = heat(m.latest_score);
              return (
                <li key={a.assignment_id} className="py-3 flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{a.title}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-0.5 text-xs text-gray-400">
                      <span>{a.questions} questions · {a.difficulty}</span>
                      <DueChip due={a.due_date} done={m.status === "submitted"} />
                    </div>
                  </div>
                  {m.status === "submitted" ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold px-2.5 py-1 rounded-lg" style={{ background: h.bg, color: h.fg }}>
                        {fmtScore(m.latest_score)}
                      </span>
                      {m.first_score !== m.latest_score && (
                        <span className="text-xs text-gray-400">first try {fmtScore(m.first_score)}</span>
                      )}
                      {m.latest_score < 70 && m.quiz_id && (
                        <button
                          type="button"
                          onClick={() => navigate("/quiz", { state: { remediateQuizId: m.quiz_id } })}
                          className="text-xs text-orange-600 hover:underline"
                        >
                          Fix it →
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => start(a)}
                      disabled={busyId !== null}
                      className="px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-60 flex items-center gap-2"
                      style={{ background: "#4F46E5" }}
                    >
                      {busyId === a.assignment_id ? <Spinner /> : null}
                      {m.status === "in_progress" ? "Continue" : "Start"}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-[11px] text-gray-400 mt-4">
          Your teacher sees your scores on class assignments only — your own lessons and quizzes stay private.
        </p>
      </div>
      <button type="button" onClick={leave} className="self-end text-xs text-gray-400 hover:text-red-600">
        Leave this class
      </button>
    </div>
  );
}

// ── teacher ───────────────────────────────────────────────────────────────────

function CreateClassForm({ onCreated }) {
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/classes", { name: name.trim(), subject: subject.trim() || null });
      setName("");
      setSubject("");
      onCreated(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't create the class."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={create} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-gray-800">New class</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} placeholder="Class name, e.g. CSE 2-A" aria-label="Class name" className={inputCls} />
        <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={120} placeholder="Subject (optional)" aria-label="Subject" className={inputCls} />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <button
        type="submit"
        disabled={busy || !name.trim()}
        className="self-start px-5 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        style={{ background: "#4F46E5" }}
      >
        {busy ? "Creating…" : "Create class"}
      </button>
    </form>
  );
}

function NewAssignment({ classId, onCreated }) {
  const [open, setOpen] = useState(false);
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [types, setTypes] = useState(["mcq", "true_false", "fill_blank"]);
  const [difficulty, setDifficulty] = useState("medium");
  const [count, setCount] = useState(5);
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.post(`/classes/${classId}/assignments`, {
        topic: topic.trim(),
        title: title.trim() || null,
        notes: notes.trim() || null,
        question_types: types,
        difficulty,
        count,
        due_date: due || null,
      });
      onCreated(res.data);
      setTopic("");
      setTitle("");
      setNotes("");
      setDue("");
      setOpen(false);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't create the assignment."));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start px-4 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
        style={{ background: "#4F46E5" }}
      >
        + Assign a quiz
      </button>
    );
  }

  return (
    <form onSubmit={create} className="rounded-2xl border border-indigo-100 bg-indigo-50/40 p-5 flex flex-col gap-3">
      <h4 className="text-sm font-semibold text-gray-800">Assign a quiz</h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={200} placeholder="Topic, e.g. Binary search trees" aria-label="Topic" className={inputCls} required />
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} placeholder="Title (optional)" aria-label="Title" className={inputCls} />
      </div>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        maxLength={20000}
        rows={3}
        placeholder="Paste your own notes for the quiz (optional) — leave empty and AI notes on the topic are written for you."
        aria-label="Notes"
        className={`${inputCls} resize-y`}
      />
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {QUESTION_TYPES.map(([k, label]) => (
          <label key={k} className="flex items-center gap-1.5 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={types.includes(k)}
              onChange={() => setTypes((t) => (t.includes(k) ? (t.length > 1 ? t.filter((x) => x !== k) : t) : [...t, k]))}
              className="accent-indigo-600"
            />
            {label}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-gray-500">
          Difficulty
          <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className={`${inputCls} mt-1 w-32`}>
            {["easy", "medium", "hard", "mixed"].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-500">
          Questions
          <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={`${inputCls} mt-1 w-20`}>
            {[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-500">
          Due (optional)
          <input type="date" value={due} min={localToday()} onChange={(e) => setDue(e.target.value)} className={`${inputCls} mt-1 w-40`} />
        </label>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || topic.trim().length < 2}
          className="px-5 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          style={{ background: "#4F46E5" }}
        >
          {busy ? <><Spinner /> Writing notes and questions…</> : "Assign to class"}
        </button>
        <button type="button" onClick={() => setOpen(false)} disabled={busy} className="px-4 py-2 rounded-xl text-sm text-gray-500 hover:bg-white">
          Cancel
        </button>
      </div>
    </form>
  );
}

function HeatmapView({ classId, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/classes/${classId}/heatmap`)
      .then((res) => !cancelled && setData(res.data))
      .catch((err) => !cancelled && setError(getErrorMessage(err, "Couldn't load the heatmap.")));
    return () => {
      cancelled = true;
    };
  }, [classId, refreshKey]);

  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <div className="h-48 bg-white rounded-2xl border border-gray-100 animate-pulse" />;
  if (data.students.length === 0 || data.assignments.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 text-center text-sm text-gray-400">
        {data.students.length === 0 ? "No students yet — share the join code." : "Assign a quiz to see how the class is doing."}
      </div>
    );
  }

  const weakTopics = data.topics.filter((t) => t.average != null && t.average < 70);

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Topics, weakest first</h3>
        <ul className="flex flex-col gap-2">
          {data.topics.map((t) => {
            const h = heat(t.average);
            return (
              <li key={t.topic} className="flex items-center gap-3">
                <span className="text-sm text-gray-700 w-28 sm:w-48 truncate flex-shrink-0" title={t.topic}>{t.topic}</span>
                <div className="flex-1 h-2.5 rounded-full bg-gray-100 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${t.average ?? 0}%`, background: h.fg }} />
                </div>
                <span className="text-xs font-semibold w-12 text-right" style={{ color: h.fg }}>{fmtScore(t.average)}</span>
                <span className="text-xs text-gray-400 w-28 text-right hidden sm:inline">
                  {t.average == null ? "no results yet" : t.weak_students ? `${t.weak_students} below 70%` : "all passing"}
                </span>
              </li>
            );
          })}
        </ul>
        {weakTopics.length > 0 && (
          <p className="text-xs text-gray-500 mt-3">
            💡 Worth re-teaching: <strong>{weakTopics.slice(0, 3).map((t) => t.topic).join(", ")}</strong>.
          </p>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h3 className="text-sm font-semibold text-gray-800">Every student × every assignment</h3>
          <div className="flex items-center gap-2 text-[11px] text-gray-500">
            {[["< 50", 40], ["50–69", 60], ["70–84", 75], ["85+", 90]].map(([label, s]) => (
              <span key={label} className="inline-flex items-center gap-1">
                <span className="w-3 h-3 rounded" style={{ background: heat(s).bg, border: `1px solid ${heat(s).fg}` }} />
                {label}
              </span>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="text-sm border-separate" style={{ borderSpacing: 3 }}>
            <thead>
              <tr>
                <th className="text-left text-xs font-medium text-gray-400 px-2 sticky left-0 bg-white">Student</th>
                {data.assignments.map((a) => (
                  <th key={a.assignment_id} className="text-xs font-medium text-gray-500 px-2 max-w-[120px]" title={a.title}>
                    <span className="block truncate max-w-[120px]">{a.topic}</span>
                  </th>
                ))}
                <th className="text-xs font-medium text-gray-400 px-2">Average</th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((s) => {
                const avg = data.student_averages[s.student_id];
                return (
                  <tr key={s.student_id}>
                    <td className="text-sm text-gray-700 px-2 whitespace-nowrap sticky left-0 bg-white">{s.username}</td>
                    {data.assignments.map((a) => {
                      const cell = data.cells[s.student_id][a.assignment_id];
                      const h = heat(cell.latest_score);
                      const label =
                        cell.status === "submitted"
                          ? cell.first_score !== cell.latest_score
                            ? `${Math.round(cell.first_score)}→${Math.round(cell.latest_score)}`
                            : fmtScore(cell.latest_score)
                          : cell.status === "in_progress"
                          ? "started"
                          : "—";
                      return (
                        <td
                          key={a.assignment_id}
                          className="text-center text-xs font-semibold rounded-lg px-2 py-2 min-w-[72px]"
                          style={{ background: h.bg, color: h.fg }}
                          title={
                            cell.status === "submitted"
                              ? `${s.username} · ${a.topic}: first ${fmtScore(cell.first_score)}, latest ${fmtScore(cell.latest_score)} (${cell.attempts} attempt${cell.attempts > 1 ? "s" : ""})`
                              : `${s.username} · ${a.topic}: ${cell.status === "in_progress" ? "started, not submitted" : "not started"}`
                          }
                        >
                          {label}
                        </td>
                      );
                    })}
                    <td className="text-center text-xs font-semibold px-2" style={{ color: heat(avg).fg }}>{fmtScore(avg)}</td>
                  </tr>
                );
              })}
              <tr>
                <td className="text-xs font-medium text-gray-400 px-2 sticky left-0 bg-white">Class</td>
                {data.assignments.map((a) => (
                  <td key={a.assignment_id} className="text-center text-xs font-semibold px-2" style={{ color: heat(a.average).fg }}>
                    {fmtScore(a.average)}
                    <span className="block text-[10px] font-normal text-gray-400">{a.submitted}/{data.students.length} done</span>
                  </td>
                ))}
                <td />
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-gray-400 mt-2">“40→80” = first try → latest after fix-up retests. Only class assignments are shown — students’ own study stays private.</p>
      </div>
    </div>
  );
}

function TeacherClass({ classId, onDeleted }) {
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState("heatmap");
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [copied, setCopied] = useState(false);

  const load = useCallback(
    () =>
      api
        .get(`/classes/${classId}`)
        .then((res) => setDetail(res.data))
        .catch((err) => setError(getErrorMessage(err, "Couldn't load the class."))),
    [classId]
  );

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function act(fn, fallback) {
    setError("");
    try {
      await fn();
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setError(getErrorMessage(err, fallback));
    }
  }

  if (!detail) return error ? <ErrorBox>{error}</ErrorBox> : <div className="h-40 bg-white rounded-2xl border border-gray-100 animate-pulse" />;

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col md:flex-row md:items-center gap-4">
        <div className="flex-1 min-w-0">
          <h2 className="text-xl font-bold text-gray-900 truncate">{detail.name}</h2>
          <p className="text-sm text-gray-500">
            {detail.subject ? `${detail.subject} · ` : ""}
            {detail.members.length} student{detail.members.length === 1 ? "" : "s"} · {detail.assignments.length} assignment{detail.assignments.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-center">
            <p className="text-[10px] uppercase tracking-wider text-gray-400">Join code</p>
            <p className="font-mono text-2xl font-bold tracking-[0.25em] text-indigo-700">{detail.join_code}</p>
          </div>
          <div className="flex flex-col gap-1">
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(detail.join_code).then(() => {
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                });
              }}
              className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
            >
              {copied ? "Copied ✓" : "Copy"}
            </button>
            <button
              type="button"
              onClick={() =>
                window.confirm("Make a new code? The old one stops working (students already in the class stay).") &&
                act(() => api.post(`/classes/${classId}/new-code`), "Couldn't change the code.")
              }
              className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50"
            >
              New code
            </button>
          </div>
        </div>
      </div>

      <ErrorBox>{error}</ErrorBox>

      <div className="flex gap-1 p-1 bg-white border border-gray-100 rounded-xl self-start text-sm" role="tablist">
        {[["heatmap", "📊 Heatmap"], ["assignments", "📝 Assignments"], ["students", "👥 Students"]].map(([t, label]) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className="px-3 py-1.5 rounded-lg font-medium"
            style={tab === t ? { background: "#EEF2FF", color: "#4338CA" } : { color: "#6B7280" }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "heatmap" && <HeatmapView classId={classId} refreshKey={refreshKey} />}

      {tab === "assignments" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
          <NewAssignment classId={classId} onCreated={() => setRefreshKey((k) => k + 1)} />
          {detail.assignments.length === 0 ? (
            <p className="text-sm text-gray-400">No assignments yet.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {detail.assignments.map((a) => {
                const h = heat(a.average);
                return (
                  <li key={a.assignment_id} className="py-3 flex flex-col sm:flex-row sm:items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800">{a.title}</p>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400 mt-0.5">
                        <span>{a.topic} · {a.questions} questions · {a.difficulty}</span>
                        <DueChip due={a.due_date} done />
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">{a.submitted}/{detail.members.length} submitted</span>
                    <span className="text-xs font-semibold px-2 py-1 rounded-lg" style={{ background: h.bg, color: h.fg }}>avg {fmtScore(a.average)}</span>
                    <button
                      type="button"
                      onClick={() =>
                        window.confirm(`Delete "${a.title}"? Students keep their own attempts.`) &&
                        act(() => api.delete(`/classes/${classId}/assignments/${a.assignment_id}`), "Couldn't delete it.")
                      }
                      className="text-xs text-gray-400 hover:text-red-600"
                    >
                      Delete
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {tab === "students" && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          {detail.members.length === 0 ? (
            <p className="text-sm text-gray-400">
              No students yet. Share the code <strong className="font-mono">{detail.join_code}</strong> — they join from their Classes page.
            </p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {detail.members.map((m) => (
                <li key={m.student_id} className="py-2.5 flex items-center justify-between gap-3">
                  <span className="text-sm text-gray-800">{m.username}</span>
                  <span className="text-xs text-gray-400 flex-1">joined {fmtDate(m.joined_at)}</span>
                  <button
                    type="button"
                    onClick={() =>
                      window.confirm(`Remove ${m.username} from the class?`) &&
                      act(() => api.delete(`/classes/${classId}/members/${m.student_id}`), "Couldn't remove the student.")
                    }
                    className="text-xs text-gray-400 hover:text-red-600"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={async () => {
          if (!window.confirm(`Delete "${detail.name}"? Members and assignments are removed; students keep their own results.`)) return;
          try {
            await api.delete(`/classes/${classId}`);
            onDeleted();
          } catch (err) {
            setError(getErrorMessage(err, "Couldn't delete the class."));
          }
        }}
        className="self-end text-xs text-gray-400 hover:text-red-600"
      >
        Delete class
      </button>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function Classes() {
  usePageTitle("Classes");
  const [role, setRole] = useState(null); // from /me — a role change applies without logging in again here
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);
  const [studentDetail, setStudentDetail] = useState(null);
  const [error, setError] = useState("");

  const loadClasses = useCallback(
    () =>
      api
        .get("/classes")
        .then((res) => setClasses(res.data))
        .catch((err) => setError(getErrorMessage(err, "Couldn't load your classes.")))
        .finally(() => setLoading(false)),
    []
  );

  useEffect(() => {
    api
      .get("/me")
      .then((res) => setRole(res.data.role))
      .catch(() => setRole("student"));
    loadClasses();
  }, [loadClasses]);

  const isTeacher = role === "teacher";

  async function open(classId) {
    setError("");
    if (isTeacher) {
      setOpenId(classId);
      return;
    }
    try {
      const res = await api.get(`/classes/${classId}`);
      setStudentDetail(res.data);
      setOpenId(classId);
    } catch (err) {
      setError(getErrorMessage(err, "Couldn't open the class."));
    }
  }

  function back() {
    setOpenId(null);
    setStudentDetail(null);
    loadClasses();
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">{isTeacher ? "Teacher" : "Study assistant"}</p>
            <h1 className="text-3xl font-bold text-gray-900">Classes</h1>
            <p className="text-sm text-gray-500 mt-1">
              {isTeacher
                ? "Create classes, assign quizzes and see which topics your class finds hardest."
                : "Join your teacher's class to get assignments."}
            </p>
          </div>
          {openId && (
            <button type="button" onClick={back} className="text-xs px-3 py-1.5 rounded-xl border border-gray-200 text-gray-500 hover:bg-white">
              ← All classes
            </button>
          )}
        </div>

        <div className="mb-4"><ErrorBox>{error}</ErrorBox></div>

        {role === null || loading ? (
          <div className="h-40 bg-white rounded-2xl border border-gray-100 animate-pulse" />
        ) : role === "admin" ? (
          <p className="text-sm text-gray-500">Admins manage teachers from the Admin panel.</p>
        ) : openId && isTeacher ? (
          <TeacherClass classId={openId} onDeleted={back} />
        ) : openId && studentDetail ? (
          <StudentClass detail={studentDetail} onLeft={back} />
        ) : (
          <div className="flex flex-col gap-6">
            {isTeacher ? (
              <CreateClassForm onCreated={(c) => setClasses((prev) => [c, ...prev])} />
            ) : (
              <JoinForm
                onJoined={(c) => {
                  loadClasses();
                  open(c.class_id);
                }}
              />
            )}
            {classes.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-6">
                {isTeacher ? "No classes yet — create your first one above." : "You haven't joined a class yet."}
              </p>
            ) : (
              <ClassCards classes={classes} onOpen={open} teacherView={isTeacher} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
