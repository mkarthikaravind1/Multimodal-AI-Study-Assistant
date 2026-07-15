import { useEffect, useState } from "react";
import api from "../api/axios";

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

// ── PHASE 1: Setup form ───────────────────────────────────────────────────────
function SetupPhase({ onQuizGenerated }) {
  const [lessons, setLessons] = useState([]);
  const [loadingLessons, setLoadingLessons] = useState(true);
  const [selectedNote, setSelectedNote] = useState("");
  const [topic, setTopic] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchLessons() {
      try {
        const res = await api.get("/lessons/all");
        const list = res.data.slice().reverse();
        setLessons(list);
        if (list.length > 0) setSelectedNote(String(list[0].note_id));
      } catch {
        setError("Could not load lessons. Generate a lesson first.");
      } finally {
        setLoadingLessons(false);
      }
    }
    fetchLessons();
  }, []);

  // auto-fill topic from selected note title
  useEffect(() => {
    if (!selectedNote) return;
    const note = lessons.find((n) => String(n.note_id) === selectedNote);
    if (note) {
      // strip "Notes on " prefix if present
      setTopic(note.title.replace(/^Notes on /i, "").replace(/^Simplified Notes: /i, ""));
    }
  }, [selectedNote, lessons]);

  async function handleGenerate(e) {
    e.preventDefault();
    if (!selectedNote) { setError("Select a lesson first."); return; }
    if (!topic.trim()) { setError("Enter a topic for the quiz."); return; }
    setError("");
    setGenerating(true);
    try {
      const res = await api.post("/quiz/generate", {
        note_id: parseInt(selectedNote),
        topic: topic.trim(),
      });
      onQuizGenerated(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Quiz generation failed. Try again.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
        <div className="flex items-center gap-3 mb-6">
          <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
            style={{ background: "#EEF2FF" }}>✏️</span>
          <div>
            <h2 className="text-base font-semibold text-gray-800">Generate a quiz</h2>
            <p className="text-xs text-gray-400 mt-0.5">5 MCQs generated from your lesson notes</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {error}
          </div>
        )}

        <form onSubmit={handleGenerate} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Select lesson
            </label>
            {loadingLessons ? (
              <div className="h-10 bg-gray-100 rounded-xl animate-pulse" />
            ) : lessons.length === 0 ? (
              <p className="text-sm text-gray-400 italic">
                No lessons found. Generate a lesson first.
              </p>
            ) : (
              <select
                value={selectedNote}
                onChange={(e) => setSelectedNote(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800
                           focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                disabled={generating}
              >
                {lessons.map((n) => (
                  <option key={n.note_id} value={String(n.note_id)}>
                    {n.title}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">
              Topic label
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Dijkstra's algorithm"
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800
                         placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              disabled={generating}
            />
            <p className="text-xs text-gray-400 mt-1">
              Used to track your score in Analytics.
            </p>
          </div>

          <button
            type="submit"
            disabled={generating || lessons.length === 0}
            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm
                       font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60 mt-1"
            style={{ background: "#4F46E5" }}
          >
            {generating ? <><Spinner /> Generating…</> : "Start quiz"}
          </button>
          {generating && (
            <p className="text-xs text-center text-gray-400">
              Generating 5 questions — this takes a few seconds.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ── PHASE 2: Answer questions ─────────────────────────────────────────────────
function QuizPhase({ quiz, onSubmit, submitting }) {
  const [answers, setAnswers] = useState({}); // { question: selectedOption }
  const [error, setError] = useState("");

  const allAnswered = quiz.questions.every((q) => answers[q.question]);

  function handleSubmit() {
    if (!allAnswered) { setError("Please answer all questions before submitting."); return; }
    setError("");
    const payload = quiz.questions.map((q) => ({
      question: q.question,
      user_answer: answers[q.question],
    }));
    onSubmit(payload);
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      {/* quiz header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-800">{quiz.topic}</h2>
          <p className="text-xs text-gray-400 mt-0.5">{quiz.total_questions} questions</p>
        </div>
        <span className="text-xs font-medium px-3 py-1.5 rounded-full"
          style={{ background: "#EEF2FF", color: "#4F46E5" }}>
          {Object.keys(answers).length} / {quiz.total_questions} answered
        </span>
      </div>

      {/* questions */}
      {quiz.questions.map((q, idx) => (
        <div key={idx} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <p className="text-sm font-semibold text-gray-800 mb-4">
            <span className="text-indigo-500 mr-2">Q{idx + 1}.</span>
            {q.question}
          </p>
          <div className="flex flex-col gap-2">
            {q.options.map((opt) => {
              const selected = answers[q.question] === opt;
              return (
                <button
                  key={opt}
                  onClick={() => setAnswers((prev) => ({ ...prev, [q.question]: opt }))}
                  className="text-left px-4 py-3 rounded-xl text-sm border transition-all duration-150"
                  style={{
                    borderColor: selected ? "#4F46E5" : "#E5E7EB",
                    background: selected ? "#EEF2FF" : "#fff",
                    color: selected ? "#4338CA" : "#374151",
                    fontWeight: selected ? 500 : 400,
                  }}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {error && (
        <p className="text-sm text-red-500 text-center">{error}</p>
      )}

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm
                   font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
        style={{ background: "#4F46E5" }}
      >
        {submitting ? <><Spinner /> Submitting…</> : "Submit answers"}
      </button>
    </div>
  );
}

// ── PHASE 3: Results ──────────────────────────────────────────────────────────
function ResultsPhase({ result, onRetry }) {
  const { topic, total_questions, correct_answers, incorrect_answers, score_percentage, results } = result;

  const scoreColor =
    score_percentage >= 70 ? "#16A34A" : score_percentage >= 40 ? "#CA8A04" : "#DC2626";
  const scoreBg =
    score_percentage >= 70 ? "#DCFCE7" : score_percentage >= 40 ? "#FEF9C3" : "#FEE2E2";
  const scoreLabel =
    score_percentage >= 70 ? "Great work!" : score_percentage >= 40 ? "Keep going!" : "Needs practice";

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      {/* score card */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 flex flex-col items-center text-center gap-3">
        <div
          className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-bold"
          style={{ background: scoreBg, color: scoreColor }}
        >
          {score_percentage}%
        </div>
        <div>
          <p className="text-lg font-semibold text-gray-800">{scoreLabel}</p>
          <p className="text-sm text-gray-400 mt-0.5">
            {topic} · {correct_answers}/{total_questions} correct
          </p>
        </div>
        <div className="flex gap-6 mt-1">
          <div className="text-center">
            <p className="text-xl font-bold" style={{ color: "#16A34A" }}>{correct_answers}</p>
            <p className="text-xs text-gray-400">Correct</p>
          </div>
          <div className="w-px bg-gray-100" />
          <div className="text-center">
            <p className="text-xl font-bold" style={{ color: "#DC2626" }}>{incorrect_answers}</p>
            <p className="text-xs text-gray-400">Incorrect</p>
          </div>
        </div>
      </div>

      {/* per-question breakdown */}
      <div className="flex flex-col gap-3">
        {results.map((r, idx) => (
          <div
            key={idx}
            className="bg-white rounded-2xl border shadow-sm p-5"
            style={{ borderColor: r.is_correct ? "#BBF7D0" : "#FECACA" }}
          >
            <div className="flex items-start gap-3">
              <span
                className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                style={{
                  background: r.is_correct ? "#DCFCE7" : "#FEE2E2",
                  color: r.is_correct ? "#16A34A" : "#DC2626",
                }}
              >
                {r.is_correct ? "✓" : "✗"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 mb-2">{r.question}</p>
                <p className="text-xs text-gray-500">
                  Your answer:{" "}
                  <span
                    className="font-medium"
                    style={{ color: r.is_correct ? "#16A34A" : "#DC2626" }}
                  >
                    {r.user_answer}
                  </span>
                </p>
                {!r.is_correct && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    Correct answer:{" "}
                    <span className="font-medium text-green-600">{r.correct_answer}</span>
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={onRetry}
        className="w-full py-3 rounded-xl text-sm font-medium text-white
                   transition-opacity hover:opacity-90"
        style={{ background: "#4F46E5" }}
      >
        Take another quiz
      </button>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────
export default function Quiz() {
  const [phase, setPhase] = useState("setup"); // "setup" | "quiz" | "results"
  const [quiz, setQuiz] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  async function handleSubmit(answers) {
    setSubmitting(true);
    setSubmitError("");
    try {
      const res = await api.post("/quiz/submit", {
        quiz_id: quiz.quiz_id,
        answers,
      });
      setResult(res.data);
      setPhase("results");
    } catch (err) {
      setSubmitError(err.response?.data?.detail || "Submission failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* ── page header ── */}
        <div className="mb-8">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">
            Study assistant
          </p>
          <h1 className="text-3xl font-bold text-gray-900">Quiz</h1>
          <p className="text-sm text-gray-500 mt-1">
            Test yourself on a lesson — your score is tracked in Analytics.
          </p>
        </div>

        {/* ── step indicator ── */}
        <div className="flex items-center gap-2 mb-8">
          {["Setup", "Questions", "Results"].map((label, idx) => {
            const stepPhase = ["setup", "quiz", "results"][idx];
            const active = phase === stepPhase;
            const done =
              (idx === 0 && phase !== "setup") ||
              (idx === 1 && phase === "results");
            return (
              <div key={label} className="flex items-center gap-2">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-6 h-6 rounded-full text-xs font-semibold flex items-center justify-center"
                    style={{
                      background: done ? "#16A34A" : active ? "#4F46E5" : "#E5E7EB",
                      color: done || active ? "#fff" : "#9CA3AF",
                    }}
                  >
                    {done ? "✓" : idx + 1}
                  </span>
                  <span
                    className="text-xs font-medium"
                    style={{ color: active ? "#4F46E5" : done ? "#16A34A" : "#9CA3AF" }}
                  >
                    {label}
                  </span>
                </div>
                {idx < 2 && <div className="w-8 h-px bg-gray-200" />}
              </div>
            );
          })}
        </div>

        {submitError && (
          <div className="mb-6 max-w-2xl mx-auto px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {submitError}
          </div>
        )}

        {/* ── phase render ── */}
        {phase === "setup" && (
          <SetupPhase
            onQuizGenerated={(data) => {
              setQuiz(data);
              setPhase("quiz");
            }}
          />
        )}
        {phase === "quiz" && quiz && (
          <QuizPhase
            quiz={quiz}
            onSubmit={handleSubmit}
            submitting={submitting}
          />
        )}
        {phase === "results" && result && (
          <ResultsPhase
            result={result}
            onRetry={() => {
              setQuiz(null);
              setResult(null);
              setPhase("setup");
            }}
          />
        )}
      </div>
    </div>
  );
}