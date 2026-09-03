import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Results from "./pages/Results";
import History from "./pages/History";
import DetailStudent from "./pages/DetailStudent";
import DetailBatch from "./pages/DetailBatch";
import AdminModel from "./pages/AdminModel";
import AdminUsers from "./pages/AdminUsers";
import AdminUserForm from "./pages/AdminUserForm";
import AdminRoles from "./pages/AdminRoles";
import DetailCourses from "./pages/DetailCourses";
import NotFound from "./pages/NotFound";
import ServerError from "./pages/ServerError";
import SessionTimeout from "./components/SessionTimeout";

function readUser() {
  try {
    return JSON.parse(localStorage.getItem("user"));
  } catch {
    return null;
  }
}

// Penjaga route sisi klien. Tanpa token yang sah, backend tetap membalas 401,
// tapi ini mencegah halaman (dan datanya) sempat ter-render sama sekali.
function ProtectedRoute({ children, adminOnly = false }) {
  const user = readUser();
  const token = localStorage.getItem("token");
  if (!user || !token) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/upload" replace />;
  return children;
}

function App() {
  return (
    <Router>
      <SessionTimeout />
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />

        <Route path="/upload" element={<ProtectedRoute><Upload /></ProtectedRoute>} />
        <Route path="/results" element={<ProtectedRoute><Results /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute adminOnly><History /></ProtectedRoute>} />
        <Route path="/detail/:nim" element={<ProtectedRoute><DetailStudent /></ProtectedRoute>} />
        <Route path="/courses/:nim" element={<ProtectedRoute><DetailCourses /></ProtectedRoute>} />
        <Route path="/batch/:id" element={<ProtectedRoute><DetailBatch /></ProtectedRoute>} />

        <Route path="/admin/model" element={<ProtectedRoute adminOnly><AdminModel /></ProtectedRoute>} />
        <Route path="/admin/users" element={<ProtectedRoute adminOnly><AdminUsers /></ProtectedRoute>} />
        <Route path="/admin/users/new" element={<ProtectedRoute adminOnly><AdminUserForm /></ProtectedRoute>} />
        <Route path="/admin/users/edit/:id" element={<ProtectedRoute adminOnly><AdminUserForm /></ProtectedRoute>} />
        <Route path="/admin/roles" element={<ProtectedRoute adminOnly><AdminRoles /></ProtectedRoute>} />

        {/* Error Pages */}
        <Route path="/500" element={<ServerError />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
