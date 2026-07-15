import { useEffect, useState } from "react";
import api from "../api/axios";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function StatCard({ label, value, icon, color }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
        style={{ background: `${color}18` }}
      >
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold" style={{ color }}>{value}</p>
        <p className="text-xs text-gray-400 mt-0.5">{label}</p>
      </div>
    </div>
  );
}

function RoleBadge({ role }) {
  const isAdmin = role === "admin";
  return (
    <span
      className="text-xs font-semibold px-2.5 py-1 rounded-full"
      style={{
        background: isAdmin ? "#EEF2FF" : "#F3F4F6",
        color: isAdmin ? "#4338CA" : "#6B7280",
      }}
    >
      {isAdmin ? "Admin" : "Student"}
    </span>
  );
}

export default function Admin() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [statsRes, usersRes] = await Promise.allSettled([
          api.get("/admin/stats"),
          api.get("/admin/users"),
        ]);
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (usersRes.status === "fulfilled") setUsers(usersRes.value.data);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load admin data.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = users.filter((u) =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    (u.student_class ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const STAT_CARDS = stats
    ? [
        { label: "Total users",    value: stats.total_users,    icon: "👤", color: "#4F46E5" },
        { label: "Lessons",        value: stats.total_notes,    icon: "📖", color: "#0891B2" },
        { label: "Quizzes taken",  value: stats.total_quizzes,  icon: "✏️", color: "#16A34A" },
        { label: "Tutor sessions", value: stats.total_sessions, icon: "💬", color: "#9333EA" },
        { label: "Uploads",        value: stats.total_uploads,  icon: "📁", color: "#EA580C" },
      ]
    : [];
    
  useEffect(() => {
      document.title = "Admin Panel | Multimodal AI Study Assistant";
  }, []);
  
  return (
    <div className="min-h-screen" style={{ background: "#F8F7FF" }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* ── header ── */}
        <div className="mb-8 flex justify-between items-start">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">
              Admin panel
            </p>
            <h1 className="text-3xl font-bold text-gray-900">Overview</h1>
            <p className="text-sm text-gray-500 mt-1">
              Platform-wide stats and registered user list.
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="bg-red-500 text-white px-4 py-2 rounded-xl text-sm hover:bg-red-600 transition-colors"
          >
            Logout
          </button>
        </div>
        {/* <div className="mb-8">
          <p className="text-xs font-medium uppercase tracking-widest text-gray-400 mb-1">
            Admin panel
          </p>
          <h1 className="text-3xl font-bold text-gray-900">Overview</h1>
          <p className="text-sm text-gray-500 mt-1">
            Platform-wide stats and registered user list.
          </p>
        </div> */}
          

        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-50 text-red-600 text-sm border border-red-100">
            {error}
          </div>
        )}

        {/* ── stat cards ── */}
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 animate-pulse">
                <div className="w-11 h-11 rounded-xl bg-gray-100 mb-3" />
                <div className="h-5 bg-gray-100 rounded w-1/2 mb-1" />
                <div className="h-3 bg-gray-100 rounded w-3/4" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
            {STAT_CARDS.map((s) => (
              <StatCard key={s.label} {...s} />
            ))}
          </div>
        )}

        {/* ── users table ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* table header */}
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-4">
            <h2 className="text-sm font-semibold text-gray-800">
              Registered users
              {!loading && (
                <span className="ml-2 text-xs font-normal text-gray-400">
                  ({filtered.length} of {users.length})
                </span>
              )}
            </h2>
            <input
              type="text"
              placeholder="Search by name or class…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border border-gray-200 rounded-xl px-3 py-1.5 text-xs text-gray-700
                         focus:outline-none focus:ring-2 focus:ring-indigo-500 w-48"
            />
          </div>

          {loading ? (
            <div className="p-6 flex flex-col gap-3 animate-pulse">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 bg-gray-100 rounded-xl" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-14 flex flex-col items-center gap-2 text-center">
              <span className="text-3xl">🔍</span>
              <p className="text-sm text-gray-500">No users match your search.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">ID</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Username</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Class</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Role</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-400 uppercase tracking-wider">Registered</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => (
                    <tr
                      key={u.user_id}
                      className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-6 py-3.5 text-gray-400 text-xs">{u.user_id}</td>
                      <td className="px-6 py-3.5 font-medium text-gray-800">{u.username}</td>
                      <td className="px-6 py-3.5 text-gray-500">{u.student_class ?? "—"}</td>
                      <td className="px-6 py-3.5"><RoleBadge role={u.role} /></td>
                      <td className="px-6 py-3.5 text-gray-400 text-xs">
                        {u.registered_date
                          ? new Date(u.registered_date).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>  
    </div>
  );
}