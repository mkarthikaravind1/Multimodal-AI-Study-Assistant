import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api, { getErrorMessage } from "../api/axios";
import MarkdownContent from "../components/MarkdownContent";
import Spinner from "../components/Spinner";
import usePageTitle from "../hooks/usePageTitle";

// ── question types & difficulty ──────────────────────────────────────────────
const QUESTION_TYPES = [
  { key: "mcq", label: "Multiple choice", short: "MCQ" },
  { key: "true_false", label: "True / False", short: "True/False" },
  { key: "fill_blank", label: "Fill in the blank", short: "Fill-in" },
  { key: "numerical", label: "Numerical", short: "Numerical" },
];
const TYPE_SHORT = Object.fromEntries(QUESTION_TYPES.map((t) => [t.key, t.short]));

const DIFFICULTIES = [
  { key: "easy", label: "Easy", hint: "Recall key facts" },
  { key: "medium", label: "Medium", hint: "Understand & apply" },
  { key: "hard", label: "Hard", hint: "Reason it through" },
  { key: "mixed", label: "Mixed", hint: "Easy → hard" },
];
const DIFFICULTY_COLORS = {
  easy: { bg: "#DCFCE7", fg: "#15803D" },
  medium: { bg: "#FEF9C3", fg: "#854D0E" },
  hard: { bg: "#FEE2E2", fg: "#B91C1C" },
  mixed: { bg: "#EEF2FF", fg: "#4338CA" },
};

function QuestionBadges({ type, difficulty }) {
  const d = DIFFICULTY_COLORS[difficulty];
  return (
    <span className="inline-flex items-center gap-1.5 flex-wrap">
      <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
        {TYPE_SHORT[type] ?? "MCQ"}
      </span>
      {d && (
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full capitalize" style={{ background: d.bg, color: d.fg }}>
          {difficulty}
        </span>
      )}
    </span>
  );
}

function ChoiceButton({ selected, onClick, children, className = "" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`text-left px-4 py-3 rounded-xl text-sm border transition-all duration-150 ${className}`}
      style={{
        borderColor: selected ? "#4F46E5" : "#E5E7EB",
        background: selected ? "#EEF2FF" : "#fff",
        color: selected ? "#4338CA" : "#374151",
        fontWeight: selected ? 500 : 400,
      }}
    >
      {children}
    </button>
  );
}

// One input per question type
function AnswerInput({ q, value, onChange }) {
  if (q.type === "fill_blank" || q.type === "numerical") {
    const numerical = q.type === "numerical";
    return (
      <div className="flex items-center gap-2">
        <input
          type="text"
          inputMode={numerical ? "decimal" : "text"}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          maxLength={200}
          placeholder={numerical ? "Enter a number, e.g. 9.81 or 1.5e-3" : "Type the missing word(s)"}
          className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800 placeholder-gray-300
                     focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {numerical && q.unit && <span className="text-sm text-gray-500 flex-shrink-0">{q.unit}</span>}
      </div>
    );
  }
  if (q.type === "true_false") {
    return (
      <div className="grid grid-cols-2 gap-2">
        {["True", "False"].map((opt) => (
          <ChoiceButton key={opt} selected={value === opt} onClick={() => onChange(opt)} className="text-center">
            {opt === "True" ? "✓ True" : "✗ False"}
          </ChoiceButton>
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {q.options.map((opt, optIdx) => (
        <ChoiceButton key={optIdx} selected={value === opt} onClick={() => onChange(opt)}>
          {opt}
        </ChoiceButton>
      ))}
    </div>
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
  const [difficulty, setDifficulty] = useState("medium");
  const [types, setTypes] = useState(["mcq", "true_false", "fill_blank"]);
  const [count, setCount] = useState(5);

  function toggleType(key) {
    setTypes((prev) =>
      prev.includes(key)
        ? prev.length > 1 ? prev.filter((t) => t !== key) : prev   // keep at least one
        : [...prev, key]
    );
  }

  useEffect(() => {
    async function fetchLessons() {
      try {
        const res = await api.get("/lessons/all");
        const list = res.data.slice().reverse();
        setLessons(list);
        if (list.length > 0) selectNote(list[0]);
      } catch {
        setError("Could not load lessons. Generate a lesson first.");
      } finally {
        setLoadingLessons(false);
      }
    }
    fetchLessons();
  }, []);

  // Select a lesson and auto-fill the topic from its title
  // (done in the event handler, not an effect, so there's no extra render)
  function selectNote(note) {
    setSelectedNote(String(note.note_id));
    setTopic(note.title.replace(/^Notes on /i, "").replace(/^Simplified Notes: /i, ""));
  }

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
        question_types: types,
        difficulty,
        count,
      });
      onQuizGenerated(res.data);
    } catch (err) {
      setError(getErrorMessage(err, "Quiz generation failed. Try again."));
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
            <p className="text-xs text-gray-400 mt-0.5">
              Questions from your lesson notes — every answer comes with an explanation
            </p>
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
                onChange={(e) => {
                  const note = lessons.find((n) => String(n.note_id) === e.target.value);
                  if (note) selectNote(note);
                }}
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

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Difficulty</label>
            <div className="grid grid-cols-4 gap-1.5">
              {DIFFICULTIES.map((d) => (
                <button
                  key={d.key}
                  type="button"
                  onClick={() => setDifficulty(d.key)}
                  disabled={generating}
                  title={d.hint}
                  aria-pressed={difficulty === d.key}
                  className="py-2 rounded-lg text-xs font-medium border"
                  style={{
                    background: difficulty === d.key ? DIFFICULTY_COLORS[d.key].bg : "#fff",
                    borderColor: difficulty === d.key ? DIFFICULTY_COLORS[d.key].fg : "#E5E7EB",
                    color: difficulty === d.key ? DIFFICULTY_COLORS[d.key].fg : "#374151",
                  }}
                >
                  {d.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-1">{DIFFICULTIES.find((d) => d.key === difficulty).hint}</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Question types</label>
            <div className="flex flex-wrap gap-1.5">
              {QUESTION_TYPES.map((t) => {
                const on = types.includes(t.key);
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => toggleType(t.key)}
                    disabled={generating}
                    aria-pressed={on}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium border"
                    style={{
                      background: on ? "#EEF2FF" : "#fff",
                      borderColor: on ? "#4F46E5" : "#E5E7EB",
                      color: on ? "#4338CA" : "#6B7280",
                    }}
                  >
                    {on ? "✓ " : ""}{t.label}
                  </button>
                );
              })}
            </div>
            {types.includes("numerical") && (
              <p className="text-xs text-gray-400 mt-1">Numerical questions need a lesson with something to calculate.</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1.5">Number of questions</label>
            <div className="flex gap-1.5">
              {[5, 8, 10].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCount(n)}
                  disabled={generating}
                  aria-pressed={count === n}
                  className="w-12 py-1.5 rounded-lg text-xs font-medium border"
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
              Writing {count} questions with explanations — this takes 10–20 seconds.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

// ── PHASE 2: Answer questions ─────────────────────────────────────────────────
function QuizPhase({ quiz, onSubmit, submitting }) {
  const [answers, setAnswers] = useState({}); // { questionIndex: selectedOption } — index, so duplicate text can't collide
  const [error, setError] = useState("");

  const isAnswered = (idx) => String(answers[idx] ?? "").trim() !== "";
  const answeredCount = quiz.questions.filter((_, idx) => isAnswered(idx)).length;
  const allAnswered = answeredCount === quiz.questions.length;

  function handleSubmit() {
    if (!allAnswered) { setError("Please answer all questions before submitting."); return; }
    setError("");
    const payload = quiz.questions.map((q, idx) => ({
      question: q.question,
      user_answer: String(answers[idx]).trim(),
    }));
    onSubmit(payload);
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      {/* quiz header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-800">{quiz.topic}</h2>
          <p className="text-xs text-gray-400 mt-0.5 capitalize">
            {quiz.total_questions} questions · {quiz.difficulty ?? "medium"}
          </p>
        </div>
        <span className="text-xs font-medium px-3 py-1.5 rounded-full"
          style={{ background: "#EEF2FF", color: "#4F46E5" }}>
          {answeredCount} / {quiz.total_questions} answered
        </span>
      </div>

      {/* questions */}
      {quiz.questions.map((q, idx) => (
        <div key={idx} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-start justify-between gap-3 mb-4">
            <p className="text-sm font-semibold text-gray-800">
              <span className="text-indigo-500 mr-2">Q{idx + 1}.</span>
              {q.question}
            </p>
            <QuestionBadges type={q.type} difficulty={q.difficulty} />
          </div>
          <AnswerInput
            q={q}
            value={answers[idx]}
            onChange={(v) => setAnswers((prev) => ({ ...prev, [idx]: v }))}
          />
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
// Shown under the score: start the loop (failed) or celebrate recovery (passed a retest)
function LoopCard({ result, onRemediate, remediating, loopError }) {
  const { passed, loop_round, incorrect_answers, topic, quiz_id } = result;

  if (passed && loop_round > 1) {
    return (
      <div className="rounded-2xl p-5 border" style={{ background: "#F0FDF4", borderColor: "#BBF7D0" }}>
        <p className="text-sm font-semibold text-green-800">🎉 Recovered!</p>
        <p className="text-xs text-green-700 mt-1">
          You passed <strong>{topic}</strong> after {loop_round - 1} fix-up round
          {loop_round - 1 > 1 ? "s" : ""}. The loop worked — this topic now counts toward your strong topics.
        </p>
      </div>
    );
  }
  if (passed) return null;

  return (
    <div className="rounded-2xl p-5 border" style={{ background: "#FFF7ED", borderColor: "#FED7AA" }}>
      <p className="text-sm font-semibold text-orange-800">
        🔁 Self-healing loop{loop_round > 1 ? ` · round ${loop_round} done` : ""}
      </p>
      <p className="text-xs text-orange-700 mt-1">
        You missed {incorrect_answers} question{incorrect_answers === 1 ? "" : "s"}. Get short fix-up notes that
        target exactly those concepts, then a fresh retest with new questions.
      </p>
      {loopError && <p className="text-xs text-red-600 mt-2">{loopError}</p>}
      <button
        onClick={() => onRemediate(quiz_id)}
        disabled={remediating}
        className="mt-3 flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white
                   hover:opacity-90 disabled:opacity-60"
        style={{ background: "#EA580C" }}
      >
        {remediating ? <><Spinner /> Preparing fix-up notes…</> : "Fix my mistakes"}
      </button>
    </div>
  );
}

// Fix-up notes for the questions the student missed, then the retest
function RemediationPhase({ remediation, onStart }) {
  const { loop_round, missed_count, note, quiz } = remediation;
  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="w-10 h-10 rounded-xl flex items-center justify-center text-xl" style={{ background: "#FFF7ED" }}>
            🔁
          </span>
          <div>
            <h2 className="text-base font-semibold text-gray-800">Round {loop_round} · {note.title}</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Targets the {missed_count} question{missed_count === 1 ? "" : "s"} you missed · saved to Lessons
            </p>
          </div>
        </div>
        <div className="text-sm text-gray-700 leading-relaxed">
          <MarkdownContent content={note.content} />
        </div>
      </div>
      <button
        onClick={onStart}
        className="w-full py-3 rounded-xl text-sm font-medium text-white hover:opacity-90"
        style={{ background: "#4F46E5" }}
      >
        I've read it — start the retest ({quiz.total_questions} new questions)
      </button>
    </div>
  );
}

function ResultsPhase({ result, onRetry, onRemediate, remediating, loopError }) {
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

      <LoopCard result={result} onRemediate={onRemediate} remediating={remediating} loopError={loopError} />

      {result.flashcards_added > 0 && (
        <div className="rounded-2xl px-5 py-3 border border-indigo-100 bg-indigo-50 flex items-center justify-between gap-3">
          <p className="text-xs text-indigo-700">
            🃏 {result.flashcards_added} missed question{result.flashcards_added === 1 ? " was" : "s were"} added to your
            flashcards — you'll review {result.flashcards_added === 1 ? "it" : "them"} until they stick.
          </p>
          <Link to="/flashcards" className="text-xs font-medium text-indigo-600 underline flex-shrink-0">
            Review now
          </Link>
        </div>
      )}

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
                <div className="flex items-start justify-between gap-3 mb-2">
                  <p className="text-sm font-medium text-gray-800">{r.question}</p>
                  <QuestionBadges type={r.type} difficulty={r.difficulty} />
                </div>
                <p className="text-xs text-gray-500">
                  Your answer:{" "}
                  <span
                    className="font-medium"
                    style={{ color: r.is_correct ? "#16A34A" : "#DC2626" }}
                  >
                    {r.user_answer}{r.unit ? ` ${r.unit}` : ""}
                  </span>
                </p>
                {r.note && <p className="text-xs text-green-700 mt-0.5">✓ {r.note}</p>}
                {!r.is_correct && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    Correct answer:{" "}
                    <span className="font-medium text-green-600">
                      {r.correct_answer}{r.unit ? ` ${r.unit}` : ""}
                    </span>
                  </p>
                )}
                {!r.is_correct && r.why_wrong && (
                  <div className="mt-2 rounded-lg px-3 py-2 text-xs" style={{ background: "#FEF2F2", color: "#991B1B" }}>
                    <span className="font-semibold">Why “{r.user_answer}” is wrong: </span>
                    {r.why_wrong}
                  </div>
                )}
                {r.explanation && (
                  <div className="mt-2 rounded-lg px-3 py-2 text-xs" style={{ background: "#F0FDF4", color: "#166534" }}>
                    <span className="font-semibold">{r.is_correct ? "Why it's right: " : "Explanation: "}</span>
                    {r.explanation}
                  </div>
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
  usePageTitle("Quiz");
  const location = useLocation();
  const navigate = useNavigate();
  // Analytics can send us here to continue the loop for a weak topic
  const startLoopFor = location.state?.remediateQuizId ?? null;

  // Classes page → "Start" on an assignment opens its quiz directly
  const assignmentQuiz = location.state?.assignmentQuiz ?? null;
  const [phase, setPhase] = useState(assignmentQuiz ? "quiz" : "setup"); // "setup" | "fixup" | "quiz" | "results"
  const [quiz, setQuiz] = useState(assignmentQuiz);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  // self-healing loop
  const [remediation, setRemediation] = useState(null);
  const [remediating, setRemediating] = useState(Boolean(startLoopFor));
  const [loopError, setLoopError] = useState("");
  const loopRequested = useRef(false);   // StrictMode runs effects twice — only call once

  function requestRemediation(quizId) {
    return api
      .post("/learning/remediate", { quiz_id: quizId })
      .then((res) => {
        setRemediation(res.data);
        setPhase("fixup");
      })
      .catch((err) => setLoopError(getErrorMessage(err, "Could not prepare fix-up notes. Try again.")))
      .finally(() => setRemediating(false));
  }

  function handleRemediate(quizId) {
    setRemediating(true);
    setLoopError("");
    requestRemediation(quizId);
  }

  useEffect(() => {
    if (!startLoopFor || loopRequested.current) return;
    loopRequested.current = true;
    requestRemediation(startLoopFor).then(() =>
      navigate("/quiz", { replace: true, state: null })   // don't restart the loop on refresh
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startLoopFor]);

  // don't re-open the assignment on refresh once it's in state here
  useEffect(() => {
    if (assignmentQuiz) navigate("/quiz", { replace: true, state: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      setSubmitError(getErrorMessage(err, "Submission failed. Try again."));
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
          {[remediation ? "Fix-up notes" : "Setup", "Questions", "Results"].map((label, idx) => {
            const stepPhase = [remediation ? "fixup" : "setup", "quiz", "results"][idx];
            const active = phase === stepPhase;
            const done =
              (idx === 0 && phase !== "setup" && phase !== "fixup") ||
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
        {phase === "setup" && remediating && (
          <div className="max-w-lg mx-auto bg-white rounded-2xl border border-gray-100 shadow-sm p-8 flex flex-col items-center gap-3 text-center">
            <Spinner size={5} color="text-orange-500" />
            <p className="text-sm font-medium text-gray-700">Preparing your fix-up notes and retest…</p>
            <p className="text-xs text-gray-400">This takes about 10–20 seconds.</p>
          </div>
        )}
        {phase === "setup" && !remediating && loopError && startLoopFor && (
          <div className="mb-6 max-w-lg mx-auto px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {loopError}
          </div>
        )}
        {phase === "fixup" && remediation && (
          <RemediationPhase
            remediation={remediation}
            onStart={() => {
              setQuiz(remediation.quiz);
              setResult(null);
              setPhase("quiz");
            }}
          />
        )}
        {phase === "setup" && !remediating && (
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
            onRemediate={handleRemediate}
            remediating={remediating}
            loopError={loopError}
            onRetry={() => {
              setQuiz(null);
              setResult(null);
              setRemediation(null);
              setLoopError("");
              setPhase("setup");
            }}
          />
        )}
      </div>
    </div>
  );
}