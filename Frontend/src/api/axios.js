import axios from "axios";

// Base URL — set VITE_API_URL in Frontend/.env.local to point at another backend
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Interceptor — automatically adds JWT token to every request
// So you don't have to manually add Authorization header everywhere
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 globally
// If token expired, redirect to login.
// A 401 from /login itself just means wrong password — let the Login page show it.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url === "/login";
    if (error.response?.status === 401 && !isLoginRequest) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

/**
 * Turns any API error into a readable string.
 * FastAPI validation errors (422) return `detail` as an ARRAY of objects —
 * rendering that directly in JSX would crash the page.
 */
export function getErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
        const msg = (d.msg || "").replace(/^Value error, /, "");
        return field && field !== "body" ? `${field}: ${msg}` : msg;
      })
      .join(" · ");
  }
  if (err?.response?.status === 413) return "File is too large.";
  if (!err?.response) return "Cannot reach the server. Is the backend running?";
  return fallback;
}

export default api;
