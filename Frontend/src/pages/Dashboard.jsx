import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../api/axios";

// ── helpers ──────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 flex flex-col gap-1 shadow-sm">
      <span className="text-xs font-medium uppercase tracking-widest text-gray-400">
        {label}
      </span>
      <span
        className="text-4xl font-bold mt-1"
        style={{ color: accent ?? "#4F46E5" }}
      >
        {value}
      </span>
      {sub && <span className="text-sm text-gray-400 mt-0.5">{sub}</span>}
    </div>
  );
}

function TopicPill({ topic, score, isStrong }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className="relative inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium cursor-default select-none transition-transform duration-150"
      style={{
        background: isStrong ? "#DCFCE7" : "#FEE2E2",
        color: isStrong ? "#15803D" : "#B91C1C",
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
        boxShadow: hovered
          ? isStrong
            ? "0 4px 12px rgba(21,128,61,0.18)"
            : "0 4px 12px rgba(185,28,28,0.18)"
          : "none",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ background: isStrong ? "#16A34A" : "#DC2626" }}
      />
      {topic}
      {hovered && (
        <span
          className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 rounded-md text-xs font-semibold text-white whitespace-nowrap"
          style={{ background: isStrong ? "#16A34A" : "#DC2626" }}
        >
          {score}% avg
        </span>
      )}
    </div>
  );
}

function EmptyTopics() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
        style={{ background: "#EEF2FF" }}
      >
        📊
      </div>
      <p className="text-gray-500 text-sm max-w-xs">
        No quiz data yet. Generate a lesson, take a quiz, and your topic
        health will appear here.
      </p>
      <button
        onClick={() => navigate("/lesson")}
        className="mt-1 px-5 py-2 rounded-xl text-sm font-medium text-white transition-opacity hover:opacity-90"
        style={{ background: "#4F46E5" }}
      >
        Generate your first lesson
      </button>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [analytics, setAnalytics] = useState(null); // { strong, weak, topic_breakdown }
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const res = await api.get("/analytics");
        setAnalytics(res.data);
      } catch (err) {
        // 404 or empty is fine — just means no quiz data yet
        if (err.response?.status !== 404) {
          setError("Could not load analytics. Try refreshing.");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // ── derived numbers ─────────────────────────────────────────────────────────
  const totalTopics = analytics?.topic_breakdown?.length ?? 0;
  const strongCount = analytics?.strong?.length ?? 0;
  const weakCount = analytics?.weak?.length ?? 0;
  const healthPct =
    totalTopics > 0 ? Math.round((strongCount / totalTopics) * 100) : null;

  // sort breakdown: strong first, then by score desc
  const sortedBreakdown = analytics?.topic_breakdown
    ? [...analytics.topic_breakdown].sort((a, b) => b.average_score - a.average_score)
    : [];

  const strongSet = new Set(analytics?.strong ?? []);

  // greeting
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  // ── render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* ── greeting ── */}
        <div className="mb-8">
          <p className="text-sm font-medium text-gray-400 uppercase tracking-widest mb-1">
            {greeting}
          </p>
          <h1 className="text-3xl font-bold text-gray-900">
            {user?.username ?? "Student"}
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            Here's where you stand today.
          </p>
        </div>

        {/* ── error banner ── */}
        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {error}
          </div>
        )}

        {/* ── stat cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <StatCard
            label="Topics studied"
            value={loading ? "—" : totalTopics}
            sub="unique quiz topics"
            accent="#4F46E5"
          />
          <StatCard
            label="Strong topics"
            value={loading ? "—" : strongCount}
            sub="≥ 70% average score"
            accent="#16A34A"
          />
          <StatCard
            label="Needs work"
            value={loading ? "—" : weakCount}
            sub="< 70% average score"
            accent="#DC2626"
          />
        </div>

        {/* ── topic health ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-gray-800">
                Topic health
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Based on your average quiz scores. Hover a pill to see the score.
              </p>
            </div>

            {/* overall health badge */}
            {healthPct !== null && (
              <div
                className="px-3 py-1.5 rounded-xl text-xs font-semibold"
                style={{
                  background:
                    healthPct >= 70 ? "#DCFCE7" : healthPct >= 40 ? "#FEF9C3" : "#FEE2E2",
                  color:
                    healthPct >= 70 ? "#15803D" : healthPct >= 40 ? "#854D0E" : "#B91C1C",
                }}
              >
                {healthPct}% mastered
              </div>
            )}
          </div>

          {/* progress bar */}
          {totalTopics > 0 && (
            <div className="w-full h-2 rounded-full bg-gray-100 mb-5 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${healthPct}%`,
                  background:
                    healthPct >= 70
                      ? "#16A34A"
                      : healthPct >= 40
                      ? "#CA8A04"
                      : "#DC2626",
                }}
              />
            </div>
          )}

          {loading ? (
            <div className="flex gap-2 flex-wrap animate-pulse">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="h-9 rounded-full bg-gray-100"
                  style={{ width: `${80 + i * 20}px` }}
                />
              ))}
            </div>
          ) : sortedBreakdown.length === 0 ? (
            <EmptyTopics />
          ) : (
            <div className="flex flex-wrap gap-2">
              {sortedBreakdown.map(({ topic, average_score }) => (
                <TopicPill
                  key={topic}
                  topic={topic}
                  score={average_score}
                  isStrong={strongSet.has(topic)}
                />
              ))}
            </div>
          )}
        </div>

        {/* ── weak topic action ── */}
        {weakCount > 0 && !loading && (
          <div
            className="rounded-2xl p-5 flex items-center justify-between gap-4"
            style={{ background: "#FFF7ED", border: "1px solid #FED7AA" }}
          >
            <div>
              <p className="text-sm font-semibold text-orange-800">
                {weakCount} topic{weakCount > 1 ? "s" : ""} need{weakCount === 1 ? "s" : ""} attention
              </p>
              <p className="text-xs text-orange-600 mt-0.5">
                Head to Analytics to regenerate simplified notes for weak areas.
              </p>
            </div>
            <button
              onClick={() => navigate("/analytics")}
              className="flex-shrink-0 px-4 py-2 rounded-xl text-sm font-medium text-white transition-opacity hover:opacity-90"
              style={{ background: "#EA580C" }}
            >
              View analytics
            </button>
          </div>
        )}

        {/* ── quick actions ── */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            {
              label: "New lesson",
              desc: "Generate AI notes on any topic",
              icon: "📖",
              path: "/lesson",
            },
            {
              label: "Take a quiz",
              desc: "Test yourself on a lesson",
              icon: "✏️",
              path: "/quiz",
            },
            {
              label: "Ask the tutor",
              desc: "Chat about anything you're stuck on",
              icon: "💬",
              path: "/tutor",
            },
          ].map(({ label, desc, icon, path }) => (
            <button
              key={path}
              onClick={() => navigate(path)}
              className="bg-white border border-gray-100 rounded-2xl p-4 text-left shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-150 flex items-start gap-3 group"
            >
              <span className="text-2xl">{icon}</span>
              <div>
                <p className="text-sm font-semibold text-gray-800 group-hover:text-indigo-600 transition-colors">
                  {label}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}