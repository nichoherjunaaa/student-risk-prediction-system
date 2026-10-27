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
import AdminPreprocessing from "./pages/AdminPreprocessing";
import AdminFormatData from "./pages/AdminFormatData";
import AdminUsers from "./pages/AdminUsers";
import AdminUserForm from "./pages/AdminUserForm";
import DetailCourses from "./pages/DetailCourses";
import BerkasMahasiswa from "./pages/BerkasMahasiswa";
import NotFound from "./pages/NotFound";
import ServerError from "./pages/ServerError";
import SessionTimeout from "./components/SessionTimeout";
import { PREDIKSI_ROLES, homePath } from "./lib/roles";

function readUser() {
  try {
    return JSON.parse(localStorage.getItem("user"));
  } catch {
    return null;
  }
}

// Penjaga route sisi klien. Tanpa token yang sah, backend tetap membalas 401,
// tapi ini mencegah halaman (dan datanya) sempat ter-render sama sekali.
// Tanpa `roles`, halaman terbuka untuk semua peran yang sudah login.
function ProtectedRoute({ children, roles }) {
  const user = readUser();
  const token = localStorage.getItem("token");
  if (!user || !token) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homePath(user.role)} replace />;
  return children;
}

const ADMIN = ["admin"];

function App() {
  return (
    <Router>
      <SessionTimeout />
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />

        <Route path="/upload" element={<ProtectedRoute roles={PREDIKSI_ROLES}><Upload /></ProtectedRoute>} />
        <Route path="/results" element={<ProtectedRoute roles={PREDIKSI_ROLES}><Results /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute roles={ADMIN}><History /></ProtectedRoute>} />
        <Route path="/detail/:nim" element={<ProtectedRoute roles={PREDIKSI_ROLES}><DetailStudent /></ProtectedRoute>} />
        <Route path="/courses/:nim" element={<ProtectedRoute roles={PREDIKSI_ROLES}><DetailCourses /></ProtectedRoute>} />
        <Route path="/batch/:id" element={<ProtectedRoute roles={PREDIKSI_ROLES}><DetailBatch /></ProtectedRoute>} />

        <Route path="/berkas" element={<ProtectedRoute><BerkasMahasiswa /></ProtectedRoute>} />

        <Route path="/admin/preprocessing" element={<ProtectedRoute roles={ADMIN}><AdminPreprocessing /></ProtectedRoute>} />
        <Route path="/admin/format-data" element={<ProtectedRoute roles={ADMIN}><AdminFormatData /></ProtectedRoute>} />
        <Route path="/admin/model" element={<ProtectedRoute roles={ADMIN}><AdminModel /></ProtectedRoute>} />
        <Route path="/admin/users" element={<ProtectedRoute roles={ADMIN}><AdminUsers /></ProtectedRoute>} />
        <Route path="/admin/users/new" element={<ProtectedRoute roles={ADMIN}><AdminUserForm /></ProtectedRoute>} />
        <Route path="/admin/users/edit/:id" element={<ProtectedRoute roles={ADMIN}><AdminUserForm /></ProtectedRoute>} />

        {/* Error Pages */}
        <Route path="/500" element={<ServerError />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
