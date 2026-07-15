import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import Navbar from "./components/Navbar";
import { useAuth } from "./context/AuthContext";

import Login     from "./pages/Login";
import Register  from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Lesson    from "./pages/Lesson";
import Quiz      from "./pages/Quiz";
import Analytics from "./pages/Analytics";
import Tutor     from "./pages/Tutor";
import Admin     from "./pages/Admin";

function DefaultRedirect() {
  const { user } = useAuth();
  return <Navigate to={user?.role === "admin" ? "/admin" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        {/* Public routes */}
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Protected routes */}
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/lesson"    element={<ProtectedRoute><Lesson /></ProtectedRoute>} />
        <Route path="/quiz"      element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
        <Route path="/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
        <Route path="/tutor"     element={<ProtectedRoute><Tutor /></ProtectedRoute>} />

        {/* Admin only */}
        <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />

        {/* Default */}
        <Route path="/" element={<DefaultRedirect />} />
      </Routes>
    </BrowserRouter>
  );
}