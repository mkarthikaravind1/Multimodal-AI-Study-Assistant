import axios from "axios";

// Base URL — all requests go to FastAPI
const api = axios.create({
  baseURL: "http://localhost:8000",
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
// If token expired, redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;