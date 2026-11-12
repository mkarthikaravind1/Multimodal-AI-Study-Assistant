import { Link } from "react-router-dom";
import usePageTitle from "../hooks/usePageTitle";

export default function NotFound() {
  usePageTitle("Page not found");
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#F8F7FF" }}>
      <div className="text-center flex flex-col items-center gap-3">
        <span className="text-5xl">🧭</span>
        <h1 className="text-2xl font-bold text-gray-900">Page not found</h1>
        <p className="text-sm text-gray-500">The page you're looking for doesn't exist.</p>
        <Link
          to="/"
          className="mt-2 px-5 py-2 rounded-xl text-sm font-medium text-white hover:opacity-90"
          style={{ background: "#4F46E5" }}
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
