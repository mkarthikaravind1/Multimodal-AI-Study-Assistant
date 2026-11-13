import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import LanguageMenu from "./LanguageMenu";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!user) return null;                // hide navbar on login/register pages
  if (user.role === "admin") return null; // the admin page has its own header + logout
  if (location.pathname.startsWith("/print/")) return null; // clean printable pages

  return (
    <nav className="no-print bg-blue-700 text-white px-6 py-3 flex flex-wrap justify-between items-center gap-4">
      {/* wraps on narrow screens instead of running off the edge */}
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-medium">
        <Link to="/dashboard" className="hover:text-blue-200">Dashboard</Link>
        <Link to="/lesson" className="hover:text-blue-200">Lessons</Link>
        <Link to="/quiz" className="hover:text-blue-200">Quiz</Link>
        <Link to="/analytics" className="hover:text-blue-200">Analytics</Link>
        <Link to="/tutor" className="hover:text-blue-200">Tutor</Link>
        <Link to="/library" className="hover:text-blue-200">Library</Link>
        <Link to="/viva" className="hover:text-blue-200">Viva</Link>
        <Link to="/flashcards" className="hover:text-blue-200">Flashcards</Link>
        <Link to="/check-work" className="hover:text-blue-200">Check Work</Link>
        <Link to="/planner" className="hover:text-blue-200">Planner</Link>
        <Link to="/maps" className="hover:text-blue-200">Maps</Link>
      </div>
      <div className="flex items-center gap-4 text-sm flex-shrink-0">
        <LanguageMenu />
        <span className="text-blue-200">Hi, {user.username}</span>
        <button
          onClick={handleLogout}
          className="bg-blue-900 px-3 py-1 rounded hover:bg-blue-800"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}