import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api from "../api/axios";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // FastAPI OAuth2 expects form data, not JSON
      const formPayload = new URLSearchParams();
      formPayload.append("username", formData.username);
      formPayload.append("password", formData.password);

      const response = await api.post("/login", formPayload, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });

      login(response.data.access_token);
      navigate("/dashboard");

    } catch (err) {
      setError(err.response?.data?.detail || "Login failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
        document.title = "Multimodal AI Study Assistant";
    }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold text-blue-700 mb-2">Welcome Back</h1>
        <p className="text-gray-500 text-sm mb-6">Login to your study assistant</p>

        {error && (
          <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Username
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter your password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-700 text-white py-2 rounded-lg text-sm
                       font-medium hover:bg-blue-800 disabled:opacity-50
                       transition-colors duration-200"
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        <p className="text-sm text-center text-gray-500 mt-6">
          Don't have an account?{" "}
          <Link to="/register" className="text-blue-700 font-medium hover:underline">
            Register here
          </Link>
        </p>
      </div>
    </div>
  );
}