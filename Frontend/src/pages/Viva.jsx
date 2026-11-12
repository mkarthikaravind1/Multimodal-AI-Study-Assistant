import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";
import useSpeech from "../hooks/useSpeech";
import useVoiceRecorder from "../hooks/useVoiceRecorder";

// ── helpers ───────────────────────────────────────────────────────────────────

function scoreColors(score, max = 10) {
  const pct = (score / max) * 100;
  if (pct >= 70) return { fg: "#16A34A", bg: "#DCFCE7" };
  if (pct >= 40) return { fg: "#CA8A04", bg: "#FEF9C3" };
  return { fg: "#DC2626", bg: "#FEE2E2" };
}

function readVoicePref() {
  try {
    return localStorage.getItem("viva_voice") !== "off";
  } catch {
    return true;
  }
}

function saveVoicePref(on) {
  try {
    localStorage.setItem("viva_voice", on ? "on" : "off");
  } catch {
    /* private mode etc. — preference just isn't remembered */
  }
}

function MicIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
      <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
      <path d="M19 10v2a7 7 0 01-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function ProgressDots({ total, graded, current }) {
  return (
    <div className="flex items-center gap-1.5" aria-label={`Question ${current + 1} of ${total}`}>
      {Array.from({ length: total }, (_, i) => {
        const g = graded[i];
        const color = g ? scoreColors(g.score).fg : i === current ? "#4F46E5" : "#E5E7EB";
        return (
          <span
            key={i}
            className="h-2 rounded-full transition-all"
            style={{ width: i === current ? 22 : 8, background: color }}
            title={g ? `Q${i + 1}: ${g.score}/10` : `Q${i + 1}`}
          />
        );
      })}
    </div>
  );
}

// ── setup: pick a lesson, see past vivas ─────────────────────────────────────

function SetupPhase({ onStarted, onOpen, voiceOn, setVoiceOn }) {
  const [lessons, setLessons] = useState([]);
  const [history, setHistory] = useState([]);
  const [noteId, setNoteId] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.allSettled([api.get("/lessons/all"), api.get("/viva/history")]).then(([l, h]) => {
      if (l.status === "fulfilled") {
        const list = l.value.data.slice().reverse();
        setLessons(list);
        if (list.length) setNoteId(String(list[0].note_id));
      }
      if (h.status === "fulfilled") setHistory(h.value.data);
      setLoading(false);
    });
  }, []);

  async function start(e) {
    e.preventDefault();
    if (!noteId) return;
    setStarting(true);
    setError("");
    try {
      const res = await api.post("/viva/start", { note_id: Number(noteId), num_questions: count });
      onStarted(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Could not start the viva. Try again."));
      setStarting(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <form onSubmit={start} className="lg:col-span-3 bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style={{ background: "#EEF2FF" }}>🎙️</span>
          <div>
            <h2 className="text-base font-semibold text-gray-800">Start an oral exam</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              The examiner asks open questions out loud — answer by speaking (or typing) and get graded instantly.
            </p>
          </div>
        </div>

        {error && <div className="px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{error}</div>}

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Lesson</label>
          {loading ? (
            <div className="h-10 bg-gray-100 rounded-xl animate-pulse" />
          ) : lessons.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No lessons yet — generate one on the Lessons page first.</p>
          ) : (
            <select
              value={noteId}
              onChange={(e) => setNoteId(e.target.value)}
              disabled={starting}
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 bg-white
                         focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {lessons.map((n) => (
                <option key={n.note_id} value={String(n.note_id)}>{n.title}</option>
              ))}
            </select>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-6">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Questions</label>
            <div className="flex gap-1.5">
              {[3, 5, 8].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCount(n)}
                  className="w-10 h-9 rounded-lg text-sm font-medium border"
                  style={{
                    background: count === n ? "#EEF2FF" : "#fff",
                    borderColor: count === n ? "#4F46E5" : "#E5E7EB",
                    color: count === n ? "#4338CA" : "#374151",
                  }}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none pb-2">
            <input
              type="checkbox"
              checked={voiceOn}
              onChange={(e) => setVoiceOn(e.target.checked)}
              className="w-4 h-4 accent-indigo-600"
            />
            Read questions & feedback aloud
          </label>
        </div>

        <button
          type="submit"
          disabled={starting || !noteId}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white
                     hover:opacity-90 disabled:opacity-60"
          style={{ background: "#4F46E5" }}
        >
          {starting ? <><Spinner /> The examiner is preparing questions…</> : "Start viva"}
        </button>
      </form>

      <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Past vivas</h3>
        {loading ? (
          <div className="flex flex-col gap-2 animate-pulse">
            {[0, 1, 2].map((i) => <div key={i} className="h-12 bg-gray-100 rounded-xl" />)}
          </div>
        ) : history.length === 0 ? (
          <p className="text-xs text-gray-400">Your vivas will appear here.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {history.map((v) => {
              const c = v.finished ? scoreColors(v.total_score, v.max_score) : null;
              return (
                <li key={v.viva_id}>
                  <button
                    type="button"
                    onClick={() => onOpen(v.viva_id)}
                    className="w-full text-left px-3 py-2.5 rounded-xl border border-gray-100 hover:border-indigo-200
                               hover:bg-indigo-50/40 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{v.topic}</p>
                      <p className="text-xs text-gray-400">
                        {v.started_at ? new Date(v.started_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""}
                        {" · "}
                        {v.finished ? "Finished" : `${v.answered}/${v.total_questions} answered — resume`}
                      </p>
                    </div>
                    {v.finished ? (
                      <span className="text-xs font-semibold px-2 py-1 rounded-lg flex-shrink-0" style={{ background: c.bg, color: c.fg }}>
                        {v.total_score}/{v.max_score}
                      </span>
                    ) : (
                      <span className="text-xs text-indigo-600 flex-shrink-0">▶</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── one question: listen, answer by voice or text ────────────────────────────

function QuestionPhase({ viva, onGraded, voiceOn, speech }) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const recorder = useVoiceRecorder((text) =>
    setAnswer((prev) => (prev ? `${prev} ${text}` : text))
  );
  const { speak, stop, speaking, supported } = speech;

  // Read each new question aloud
  useEffect(() => {
    if (voiceOn && viva.current_question) speak(viva.current_question);
  }, [viva.current_question, voiceOn, speak]);

  async function submit() {
    if (!answer.trim()) return;
    stop();
    setSubmitting(true);
    setError("");
    try {
      const res = await api.post(`/viva/${viva.viva_id}/answer`, { answer: answer.trim() });
      onGraded(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Grading failed. Your answer is still here — try again."));
      setSubmitting(false);
    }
  }

  function toggleMic() {
    if (recorder.recording) {
      recorder.stop();
    } else {
      stop(); // don't record the examiner's voice
      recorder.start();
    }
  }

  const busy = submitting || recorder.transcribing;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-500">
          Question {viva.current_index + 1} of {viva.total_questions} · {viva.topic}
        </p>
        <ProgressDots total={viva.total_questions} graded={viva.graded} current={viva.current_index} />
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-start gap-3">
          <span className="text-2xl flex-shrink-0">🧑‍🏫</span>
          <p className="text-base font-medium text-gray-800 leading-relaxed flex-1">{viva.current_question}</p>
        </div>
        {supported && (
          <button
            type="button"
            onClick={() => (speaking ? stop() : speak(viva.current_question))}
            className="mt-3 text-xs text-indigo-600 hover:underline"
          >
            {speaking ? "■ Stop reading" : "🔊 Read the question aloud"}
          </button>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col items-center gap-4">
        <button
          type="button"
          onClick={toggleMic}
          disabled={busy}
          aria-label={recorder.recording ? "Stop recording" : "Start recording your answer"}
          className="w-20 h-20 rounded-full flex items-center justify-center text-white shadow-md
                     transition-transform hover:scale-105 disabled:opacity-50"
          style={{
            background: recorder.recording ? "#EF4444" : "#4F46E5",
            animation: recorder.recording ? "viva-pulse 1.2s ease-out infinite" : "none",
          }}
        >
          {recorder.transcribing ? <Spinner size={5} /> : <MicIcon />}
        </button>
        <p className="text-xs text-gray-500 -mt-1">
          {recorder.recording
            ? "Listening… tap again when you're done"
            : recorder.transcribing
            ? "Transcribing your answer…"
            : "Tap to answer out loud — or type below"}
        </p>
        {recorder.error && <p className="text-xs text-red-500 text-center">{recorder.error}</p>}

        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={5}
          maxLength={3000}
          disabled={submitting || recorder.recording}
          placeholder="Your answer appears here — you can edit it before submitting."
          className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-300
                     focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y disabled:opacity-60"
        />

        {error && <p className="text-xs text-red-500 self-start">{error}</p>}

        <button
          type="button"
          onClick={submit}
          disabled={busy || recorder.recording || answer.trim().length < 3}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white
                     hover:opacity-90 disabled:opacity-50"
          style={{ background: "#4F46E5" }}
        >
          {submitting ? <><Spinner /> The examiner is grading…</> : "Submit answer"}
        </button>
      </div>
    </div>
  );
}

// ── feedback on one answer ───────────────────────────────────────────────────

function GradedCard({ result, children }) {
  const c = scoreColors(result.score);
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <div
          className="w-16 h-16 rounded-full flex flex-col items-center justify-center flex-shrink-0"
          style={{ background: c.bg, color: c.fg }}
        >
          <span className="text-xl font-bold leading-none">{result.score}</span>
          <span className="text-[10px] font-medium">/ 10</span>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">{result.feedback}</p>
      </div>

      <div className="rounded-xl bg-gray-50 px-4 py-3">
        <p className="text-xs font-medium text-gray-400 mb-1">Your answer</p>
        <p className="text-sm text-gray-700">{result.answer}</p>
      </div>

      {result.ideal_answer && (
        <div className="rounded-xl px-4 py-3" style={{ background: "#F0FDF4" }}>
          <p className="text-xs font-medium text-green-700 mb-1">Model answer</p>
          <p className="text-sm text-gray-700">{result.ideal_answer}</p>
        </div>
      )}

      {result.missed_points?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-400 mb-1.5">Points you missed</p>
          <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
            {result.missed_points.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </div>
      )}
      {children}
    </div>
  );
}

function GradedPhase({ graded, viva, onNext }) {
  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-500">
          Question {graded.question_index + 1} of {viva.total_questions} · graded
        </p>
        <ProgressDots total={viva.total_questions} graded={viva.graded} current={graded.question_index} />
      </div>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-6 py-4">
        <p className="text-sm font-medium text-gray-800">{graded.result.question}</p>
      </div>
      <GradedCard result={graded.result}>
        <button
          type="button"
          onClick={onNext}
          className="w-full py-2.5 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          {viva.finished ? "See my results" : "Next question →"}
        </button>
      </GradedCard>
    </div>
  );
}

// ── final results ─────────────────────────────────────────────────────────────

function FinishedPhase({ viva, onNew }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(null);
  const pct = Math.round(((viva.total_score ?? 0) / viva.max_score) * 100);
  const c = scoreColors(viva.total_score ?? 0, viva.max_score);
  const verdict = pct >= 70 ? "Excellent — you can explain this topic well." : pct >= 40 ? "Good effort — review the model answers below." : "Keep practising — the model answers show what to cover.";

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 flex flex-col items-center text-center gap-3">
        <div className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-bold" style={{ background: c.bg, color: c.fg }}>
          {pct}%
        </div>
        <p className="text-lg font-semibold text-gray-800">{verdict}</p>
        <p className="text-sm text-gray-400">
          {viva.topic} · {viva.total_score}/{viva.max_score} points
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {viva.graded.map((q, i) => {
          const qc = scoreColors(q.score);
          return (
            <div key={i} className="bg-white rounded-2xl border border-gray-100 shadow-sm">
              <button
                type="button"
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full text-left px-5 py-4 flex items-center gap-3"
              >
                <span className="text-xs font-bold px-2 py-1 rounded-lg flex-shrink-0" style={{ background: qc.bg, color: qc.fg }}>
                  {q.score}/10
                </span>
                <span className="text-sm text-gray-800 flex-1">{q.question}</span>
                <span className="text-gray-400" style={{ transform: open === i ? "rotate(180deg)" : "none" }}>▾</span>
              </button>
              {open === i && (
                <div className="px-5 pb-5">
                  <GradedCard result={q} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={() => navigate("/tutor", { state: { noteId: viva.note_id, noteTitle: viva.topic } })}
          className="flex-1 py-3 rounded-xl text-sm font-medium border border-indigo-200 text-indigo-600 hover:bg-indigo-50"
        >
          💬 Discuss weak answers with the tutor
        </button>
        <button
          type="button"
          onClick={onNew}
          className="flex-1 py-3 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          New viva
        </button>
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function Viva() {
  usePageTitle("Viva");
  const speech = useSpeech();
  const [phase, setPhase] = useState("setup"); // setup | question | graded | finished
  const [viva, setViva] = useState(null);
  const [graded, setGraded] = useState(null);
  const [voiceOn, setVoiceOnState] = useState(readVoicePref);
  const [openError, setOpenError] = useState("");

  function setVoiceOn(on) {
    setVoiceOnState(on);
    saveVoicePref(on);
    if (!on) speech.stop();
  }

  function begin(state) {
    setViva(state);
    setGraded(null);
    setPhase(state.finished ? "finished" : "question");
  }

  async function openViva(vivaId) {
    setOpenError("");
    try {
      const res = await api.get(`/viva/${vivaId}`);
      begin(res.data);
    } catch (err) {
      setOpenError(getErrorMessage(err, "Could not open that viva."));
    }
  }

  function handleGraded(data) {
    setGraded(data);
    setViva(data.state);
    setPhase("graded");
    if (voiceOn) speech.speak(`You scored ${data.result.score} out of 10. ${data.result.feedback}`);
  }

  function next() {
    speech.stop();
    setGraded(null);
    setPhase(viva.finished ? "finished" : "question");
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <style>{`
        @keyframes viva-pulse {
          0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.5); }
          70%  { box-shadow: 0 0 0 16px rgba(239,68,68,0); }
          100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
        }
      `}</style>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">Study assistant</p>
            <h1 className="text-3xl font-bold text-gray-900">Viva</h1>
            <p className="text-sm text-gray-500 mt-1">
              Practise explaining a topic out loud — like a real oral exam.
            </p>
          </div>
          {phase !== "setup" && (
            <button
              type="button"
              onClick={() => {
                speech.stop();
                setPhase("setup");
                setViva(null);
              }}
              className="text-xs px-3 py-1.5 rounded-xl border border-gray-200 text-gray-500 hover:bg-white"
            >
              ← All vivas
            </button>
          )}
        </div>

        {openError && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">{openError}</div>
        )}

        {phase === "setup" && (
          <SetupPhase onStarted={begin} onOpen={openViva} voiceOn={voiceOn} setVoiceOn={setVoiceOn} />
        )}
        {phase === "question" && viva && (
          <QuestionPhase
            key={viva.current_index}
            viva={viva}
            onGraded={handleGraded}
            voiceOn={voiceOn}
            speech={speech}
          />
        )}
        {phase === "graded" && graded && viva && <GradedPhase graded={graded} viva={viva} onNext={next} />}
        {phase === "finished" && viva && (
          <FinishedPhase
            viva={viva}
            onNew={() => {
              setViva(null);
              setPhase("setup");
            }}
          />
        )}
      </div>
    </div>
  );
}
