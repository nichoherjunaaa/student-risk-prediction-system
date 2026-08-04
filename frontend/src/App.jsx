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
import DetailCourses from "./pages/DetailCourses";
import NotFound from "./pages/NotFound";
import ServerError from "./pages/ServerError";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login" element={<Login />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/results" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/detail/:nim" element={<DetailStudent />} />
        <Route path="/courses/:nim" element={<DetailCourses />} />
        <Route path="/batch/:id" element={<DetailBatch />} />
        <Route path="/admin/model" element={<AdminModel />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/users/new" element={<AdminUserForm />} />
        <Route path="/admin/users/edit/:id" element={<AdminUserForm />} />
        
        {/* Error Pages */}
        <Route path="/500" element={<ServerError />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
