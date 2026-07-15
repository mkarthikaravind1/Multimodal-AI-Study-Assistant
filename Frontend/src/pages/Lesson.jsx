import { useEffect, useState } from "react";
import api from "../api/axios";
import MarkdownContent from "../components/MarkdownContent";

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}

function LessonCard({ lesson, isOpen, onToggle }) {
  return (
    <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">
      {/* ── header (always visible) ── */}
      <button
        onClick={onToggle}
        className="w-full text-left px-5 py-4 flex items-center justify-between gap-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0"
            style={{ background: "#EEF2FF", color: "#4F46E5" }}
          >
            📖
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-800 truncate">
              {lesson.title}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
              {lesson.created_at
                ? new Date(lesson.created_at).toLocaleDateString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })
                : "Just now"}
            </p>
          </div>
        </div>
        <span
          className="text-gray-400 flex-shrink-0 transition-transform duration-200"
          style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          ▾
        </span>
      </button>

      {/* ── expanded content ── */}
      {isOpen && (
        <div className="px-5 pb-5 border-t border-gray-100">
          <div className="mt-4 text-sm text-gray-700 leading-relaxed">
              <MarkdownContent content={lesson.content}/>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Lesson() {
  // ── form state ──────────────────────────────────────────────────────────────
  const [topic, setTopic] = useState("");
  const [studentClass, setStudentClass] = useState("");
  const [generating, setGenerating] = useState(false);
  const [formError, setFormError] = useState("");

  // ── lessons list state ──────────────────────────────────────────────────────
  const [lessons, setLessons] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [openId, setOpenId] = useState(null); // which card is expanded

  // ── load all existing lessons on mount ─────────────────────────────────────
  useEffect(() => {
    async function fetchLessons() {
      try {
        const res = await api.get("/lessons/all");
        // newest first
        setLessons(res.data.slice().reverse());
      } catch {
        // empty list is fine
      } finally {
        setLoadingList(false);
      }
    }
    fetchLessons();
  }, []);

  // ── generate new lesson ────────────────────────────────────────────────────
  async function handleGenerate(e) {
    e.preventDefault();
    if (!topic.trim()) {
      setFormError("Please enter a topic.");
      return;
    }

    if (!studentClass.trim()) {
      setFormError("Please enter your education level.");
      return;
    }
    setFormError("");
    setGenerating(true);
    try {
      const res = await api.post("/lessons/generate", {
        topic: topic.trim(),
        student_class: studentClass,
      });
      // prepend to list and auto-open the new lesson
      const newLesson = {
        note_id: res.data.note_id,
        title: res.data.title,
        content: res.data.content,
        created_at: new Date().toISOString(),
      };
      setLessons((prev) => [newLesson, ...prev]);
      setOpenId(newLesson.note_id);
      setTopic("");
    } catch (err) {
      setFormError(
        err.response?.data?.detail || "Generation failed. Please try again."
      );
    } finally {
      setGenerating(false);
    }
  }

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* ── page header ── */}
        <div className="mb-8">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">
            Study assistant
          </p>
          <h1 className="text-3xl font-bold text-gray-900">Lessons</h1>
          <p className="text-sm text-gray-500 mt-1">
            Generate AI-powered study notes on any topic.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── LEFT: generate form ── */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 sticky top-6">
              <h2 className="text-sm font-semibold text-gray-800 mb-4">
                New lesson
              </h2>

              <form onSubmit={handleGenerate} className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">
                    Topic
                  </label>
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="e.g. Dijkstra's algorithm"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800
                               placeholder-gray-300 focus:outline-none focus:ring-2 focus:border-transparent"
                    style={{ "--tw-ring-color": "#4F46E5" }}
                    disabled={generating}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">
                    Education Level
                  </label>

                  <input
                    list="education-levels"
                    value={studentClass}
                    onChange={(e) => setStudentClass(e.target.value)}
                    placeholder="e.g. UG 2nd Year, Class 10, M.Tech"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-800
                              placeholder-gray-300 focus:outline-none focus:ring-2 focus:border-transparent"
                    style={{ "--tw-ring-color": "#4F46E5" }}
                    disabled={generating}
                  />

                  <datalist id="education-levels">
                    <option value="Class 6" />
                    <option value="Class 7" />
                    <option value="Class 8" />
                    <option value="Class 9" />
                    <option value="Class 10" />
                    <option value="Class 11" />
                    <option value="Class 12" />

                    <option value="Diploma 1st Year" />
                    <option value="Diploma 2nd Year" />
                    <option value="Diploma 3rd Year" />

                    <option value="UG 1st Year" />
                    <option value="UG 2nd Year" />
                    <option value="UG 3rd Year" />
                    <option value="UG 4th Year" />

                    <option value="M.Tech" />
                    <option value="MBA" />
                    <option value="M.Sc" />
                    <option value="PhD" />

                    <option value="Working Professional" />
                  </datalist>
                </div>

                {formError && (
                  <p className="text-xs text-red-500">{formError}</p>
                )}

                <button
                  type="submit"
                  disabled={generating}
                  className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm
                             font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60"
                  style={{ background: "#4F46E5" }}
                >
                  {generating ? (
                    <>
                      <Spinner />
                      Generating…
                    </>
                  ) : (
                    "Generate lesson"
                  )}
                </button>

                {generating && (
                  <p className="text-xs text-center text-gray-400">
                    The AI is writing your notes — this takes 5–15 seconds.
                  </p>
                )}
              </form>
            </div>
          </div>

          {/* ── RIGHT: lessons list ── */}
          <div className="lg:col-span-2 flex flex-col gap-3">
            {loadingList ? (
              // skeleton
              [...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="bg-white border border-gray-100 rounded-2xl shadow-sm p-5 animate-pulse"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-gray-100" />
                    <div className="flex-1">
                      <div className="h-3.5 bg-gray-100 rounded w-2/3 mb-2" />
                      <div className="h-3 bg-gray-100 rounded w-1/3" />
                    </div>
                  </div>
                </div>
              ))
            ) : lessons.length === 0 ? (
              // empty state
              <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-10 flex flex-col items-center text-center gap-3">
                <span className="text-4xl">📭</span>
                <p className="text-sm font-medium text-gray-700">
                  No lessons yet
                </p>
                <p className="text-xs text-gray-400 max-w-xs">
                  Generate your first lesson using the form. It will be saved
                  here and available for quizzes.
                </p>
              </div>
            ) : (
              lessons.map((lesson) => (
                <LessonCard
                  key={lesson.note_id}
                  lesson={lesson}
                  isOpen={openId === lesson.note_id}
                  onToggle={() =>
                    setOpenId((prev) =>
                      prev === lesson.note_id ? null : lesson.note_id
                    )
                  }
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}