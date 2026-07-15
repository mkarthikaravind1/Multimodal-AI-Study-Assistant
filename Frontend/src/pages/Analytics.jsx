import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function ScoreBar({ score }) {
  const color = score >= 70 ? "#16A34A" : score >= 40 ? "#CA8A04" : "#DC2626";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="text-xs font-semibold w-10 text-right" style={{ color }}>
        {score}%
      </span>
    </div>
  );
}

function TopicRow({ topic, score, isStrong, onRegenerate, regenerating }) {
  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-50 last:border-0">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: isStrong ? "#16A34A" : "#DC2626" }}
          />
          <p className="text-sm font-medium text-gray-800 truncate">{topic}</p>
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0"
            style={{
              background: isStrong ? "#DCFCE7" : "#FEE2E2",
              color: isStrong ? "#15803D" : "#B91C1C",
            }}
          >
            {isStrong ? "Strong" : "Weak"}
          </span>
        </div>
        <ScoreBar score={score} />
      </div>

      {!isStrong && (
        <button
          onClick={() => onRegenerate(topic)}
          disabled={regenerating === topic}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium
                     text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          style={{ background: "#EA580C" }}
        >
          {regenerating === topic ? (
            <>
              <Spinner />
              Generating…
            </>
          ) : (
            "Simplify notes"
          )}
        </button>
      )}
    </div>
  );
}

export default function Analytics() {
  const navigate = useNavigate();

  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // regeneration state
  const [regenerating, setRegenerating] = useState(null); // topic string
  const [regenSuccess, setRegenSuccess] = useState(null);
  const [regenError, setRegenError] = useState("");
  const [classFor, setClassFor] = useState(""); // class picker for regen

  useEffect(() => {
    async function load() {
      try {
        const res = await api.get("/analytics");
        setAnalytics(res.data);
      } catch (err) {
        if (err.response?.status !== 404) {
          setError("Could not load analytics. Try refreshing.");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleRegenerate(topic) {
    if (!classFor.trim()) {
      setRegenError("Please enter your education level first.");
      return;
    }
    setRegenerating(topic);
    setRegenSuccess(null);
    setRegenError("");
    
    try {
      await api.post("/lessons/regenerate-weak", {
        topic,
        student_class: classFor,
      });
      setTimeout(()=>{setRegenSuccess(null)},5000)
    } catch (err) {
      setRegenError(
        err.response?.data?.detail || "Regeneration failed. Try again."
      );
    } finally {
      setRegenerating(null);
    }
  }

  // sorted: weak first (needs attention), then strong, both by score desc
  const sorted = analytics?.topic_breakdown
    ? [...analytics.topic_breakdown].sort((a, b) => {
        const aStrong = analytics.strong.includes(a.topic);
        const bStrong = analytics.strong.includes(b.topic);
        if (aStrong !== bStrong) return aStrong ? 1 : -1;
        return b.average_score - a.average_score;
      })
    : [];

  const strongSet = new Set(analytics?.strong ?? []);
  const totalTopics = sorted.length;
  const strongCount = analytics?.strong?.length ?? 0;
  const weakCount = analytics?.weak?.length ?? 0;

  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-3xl mx-auto px-6 py-10">

        {/* ── header ── */}
        <div className="mb-8">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">
            Study assistant
          </p>
          <h1 className="text-3xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">
            Your average quiz scores by topic — see what to review next.
          </p>
        </div>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {error}
          </div>
        )}

        {/* ── summary cards ── */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[
            { label: "Topics", value: loading ? "—" : totalTopics, color: "#4F46E5" },
            { label: "Strong", value: loading ? "—" : strongCount, color: "#16A34A" },
            { label: "Weak", value: loading ? "—" : weakCount, color: "#DC2626" },
          ].map(({ label, value, color }) => (
            <div
              key={label}
              className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center"
            >
              <p className="text-2xl font-bold" style={{ color }}>{value}</p>
              <p className="text-xs text-gray-400 mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* ── class picker for regeneration ── */}
        {!loading && weakCount > 0 && (
          <div className="flex items-center gap-3 mb-4">
            <p className="text-xs text-gray-500 flex-shrink-0">
              Regenerate notes for:
            </p>
            <input
              list="education-levels"
              value={classFor}
              onChange={(e) => setClassFor(e.target.value)}
              placeholder="e.g. UG 2nd Year, Class 10, M.Tech"
              className="border border-gray-200 rounded-xl px-3 py-1.5 text-xs text-gray-700
                        focus:outline-none focus:ring-2 bg-white"
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
        )}

        {/* ── regen feedback ── */}
        {regenSuccess && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-green-50 text-green-700 text-sm border border-green-100 flex items-center justify-between">
            <span>
              Simplified notes for <strong>{regenSuccess}</strong> generated and saved to Lessons.
            </span>
            <button
              onClick={() => navigate("/lesson")}
              className="text-xs underline ml-3 flex-shrink-0"
            >
              View lesson →
            </button>
          </div>
        )}
        {regenError && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {regenError}
          </div>
        )}

        {/* ── topic list ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm px-6 py-2">
          {loading ? (
            <div className="py-6 flex flex-col gap-4 animate-pulse">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <div className="h-3 bg-gray-100 rounded w-1/3" />
                  <div className="h-2 bg-gray-100 rounded w-full" />
                </div>
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="py-12 flex flex-col items-center gap-3 text-center">
              <span className="text-4xl">📊</span>
              <p className="text-sm font-medium text-gray-700">No quiz data yet</p>
              <p className="text-xs text-gray-400 max-w-xs">
                Complete at least one quiz and your topic scores will appear here.
              </p>
              <button
                onClick={() => navigate("/quiz")}
                className="mt-1 px-5 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
                style={{ background: "#4F46E5" }}
              >
                Take a quiz
              </button>
            </div>
          ) : (
            sorted.map(({ topic, average_score }) => (
              <TopicRow
                key={topic}
                topic={topic}
                score={average_score}
                isStrong={strongSet.has(topic)}
                onRegenerate={handleRegenerate}
                regenerating={regenerating}
              />
            ))
          )}
        </div>

        {/* ── threshold note ── */}
        {!loading && sorted.length > 0 && (
          <p className="text-xs text-gray-400 text-center mt-4">
            Topics with ≥ 70% average are marked strong. Below 70% → weak.
          </p>
        )}
      </div>
    </div>
  );
}