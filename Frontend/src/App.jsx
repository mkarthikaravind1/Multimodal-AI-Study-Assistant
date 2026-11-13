import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import Navbar from "./components/Navbar";
import Spinner from "./components/Spinner";
import { useAuth } from "./context/useAuth";

// Every page is its own chunk, downloaded the first time it's opened —
// so the first load doesn't pay for the tutor, quiz, planner, maps, … all at once.
const Login       = lazy(() => import("./pages/Login"));
const Register    = lazy(() => import("./pages/Register"));
const Dashboard   = lazy(() => import("./pages/Dashboard"));
const Lesson      = lazy(() => import("./pages/Lesson"));
const LessonPrint = lazy(() => import("./pages/LessonPrint"));
const Quiz        = lazy(() => import("./pages/Quiz"));
const Analytics   = lazy(() => import("./pages/Analytics"));
const Tutor       = lazy(() => import("./pages/Tutor"));
const Admin       = lazy(() => import("./pages/Admin"));
const NotFound    = lazy(() => import("./pages/NotFound"));
const Viva        = lazy(() => import("./pages/Viva"));
const Flashcards  = lazy(() => import("./pages/Flashcards"));
const CheckWork   = lazy(() => import("./pages/CheckWork"));
const Planner     = lazy(() => import("./pages/Planner"));
const ConceptMaps = lazy(() => import("./pages/ConceptMaps"));

function DefaultRedirect() {
  const { user } = useAuth();
  return <Navigate to={user?.role === "admin" ? "/admin" : "/dashboard"} replace />;
}

function PageLoading() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center" role="status" aria-label="Loading page">
      <Spinner size={5} color="text-indigo-600" />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Suspense fallback={<PageLoading />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes */}
          <Route path="/dashboard"  element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/lesson"     element={<ProtectedRoute><Lesson /></ProtectedRoute>} />
          <Route path="/quiz"       element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
          <Route path="/analytics"  element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
          <Route path="/tutor"      element={<ProtectedRoute><Tutor /></ProtectedRoute>} />
          <Route path="/viva"       element={<ProtectedRoute><Viva /></ProtectedRoute>} />
          <Route path="/flashcards" element={<ProtectedRoute><Flashcards /></ProtectedRoute>} />
          <Route path="/check-work" element={<ProtectedRoute><CheckWork /></ProtectedRoute>} />
          <Route path="/planner"    element={<ProtectedRoute><Planner /></ProtectedRoute>} />
          <Route path="/maps"       element={<ProtectedRoute><ConceptMaps /></ProtectedRoute>} />
          <Route path="/print/lesson/:noteId" element={<ProtectedRoute><LessonPrint /></ProtectedRoute>} />

          {/* Admin only */}
          <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />

          {/* Default */}
          <Route path="/" element={<DefaultRedirect />} />

          {/* Anything else */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
