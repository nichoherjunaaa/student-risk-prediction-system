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
        <Route path="/batch/:id" element={<DetailBatch />} />
        <Route path="/admin/model" element={<AdminModel />} />
      </Routes>
    </Router>
  );
}

export default App;
