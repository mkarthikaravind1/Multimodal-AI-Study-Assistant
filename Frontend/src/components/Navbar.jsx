import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  if (!user) return null;                // hide navbar on login/register pages
  if (user.role === "admin") return null; // the admin page has its own header + logout

  return (
    <nav className="bg-blue-700 text-white px-6 py-3 flex justify-between items-center">
      <div className="flex gap-6 text-sm font-medium">
        <Link to="/dashboard" className="hover:text-blue-200">Dashboard</Link>
        <Link to="/lesson" className="hover:text-blue-200">Lessons</Link>
        <Link to="/quiz" className="hover:text-blue-200">Quiz</Link>
        <Link to="/analytics" className="hover:text-blue-200">Analytics</Link>
        <Link to="/tutor" className="hover:text-blue-200">Tutor</Link>
        <Link to="/viva" className="hover:text-blue-200">Viva</Link>
        <Link to="/flashcards" className="hover:text-blue-200">Flashcards</Link>
      </div>
      <div className="flex items-center gap-4 text-sm">
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