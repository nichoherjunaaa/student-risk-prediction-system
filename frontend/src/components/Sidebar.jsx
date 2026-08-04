import React from "react";
import {
  UploadCloud,
  BarChart2,
  History,
  LogOut,
  X,
  Settings2,
  Users,
  ChevronDown,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const Sidebar = ({ isOpen, toggleSidebar }) => {
  const location = useLocation();
  const currentPath = location.pathname;

  // 1. DATA PENGGUNA dari localStorage
  let user = { email: "@admin.com", name: "Staf Admin", role: "admin" };
  try {
    const savedUser = localStorage.getItem("user");
    if (savedUser) {
      user = JSON.parse(savedUser);
    }
  } catch (e) {
    console.error("Gagal membaca data user", e);
  }

  const userEmail = user.email;
  const userName = user.name;
  const computedRole = user.role;

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/50 z-40 lg:hidden backdrop-blur-sm transition-opacity duration-300 ${isOpen ? "opacity-100" : "opacity-0 hidden"}`}
        onClick={toggleSidebar}
      ></div>

      <aside
        className={`w-72 bg-primary text-surface flex flex-col h-full shrink-0 border-r border-primary-dark/50 z-50 fixed lg:static inset-y-0 left-0 transform ${isOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0 transition-transform duration-300 shadow-2xl lg:shadow-xl`}
      >
        <div className="pt-8 pb-6 px-6 flex flex-col items-center justify-center border-b border-white/10 shrink-0 relative">
          <button
            onClick={toggleSidebar}
            className="lg:hidden absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-white/10 rounded-md"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src="/logo.png"
            alt="System Logo"
            className="h-14 w-14 object-contain bg-surface p-2 rounded-xl shadow-md mb-4"
          />
          <h2 className="font-bold text-xl leading-tight tracking-wide text-white text-center">
            Sistem Prediksi
          </h2>
          <span className="text-xs text-white/70 font-semibold uppercase tracking-wider mt-1 text-center">
            Sisip Program
          </span>
        </div>

        {/* Role Display mimicking the image */}
        <div className="px-6 py-4 border-b border-white/10 shrink-0">
          <div className="flex items-center justify-between bg-white/10 px-4 py-2.5 rounded-lg cursor-pointer hover:bg-white/15 transition-colors">
            <span className="text-sm font-bold tracking-wide text-white uppercase">{computedRole === 'admin' ? 'SUPER ADMIN' : 'DPA'}</span>
            <div className="h-6 w-6 bg-white/20 rounded flex items-center justify-center">
              <ChevronDown className="h-4 w-4 text-white" />
            </div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto no-scrollbar py-8 flex flex-col space-y-2">
          {/* MENU KHUSUS ADMIN */}
          {computedRole === "admin" && (
            <>
              <Link
                to="/admin/model"
                className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 mt-4 ${currentPath === "/admin/model" ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
              >
                <Settings2 className="h-5 w-5 mr-4 text-accent" />
                <span>Master Model</span>
              </Link>
              <Link
                to="/admin/users"
                className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 mt-2 mb-4 ${currentPath.startsWith("/admin/users") || currentPath.startsWith("/admin/roles") ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
              >
                <Users className="h-5 w-5 mr-4 text-accent" />
                <span>Master Pengguna</span>
              </Link>
            </>
          )}

          {/* MENU UTAMA USER / DOSEN */}
          <Link
            to="/upload"
            className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 mt-2 ${currentPath === "/upload" ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
          >
            <UploadCloud className="h-5 w-5 mr-4 text-accent" />
            <span>Unggah Data</span>
          </Link>

          <Link
            to="/results"
            className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 mt-2 ${currentPath === "/results" ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
          >
            <BarChart2 className="h-5 w-5 mr-4 text-accent" />
            <span>Hasil Prediksi</span>
          </Link>

          <Link
            to="/history"
            className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 mt-2 mb-4 ${currentPath === "/history" ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
          >
            <History className="h-5 w-5 mr-4 text-accent" />
            <span>Log Riwayat</span>
          </Link>

        </nav>

        <div className="p-6 border-t border-white/10 shrink-0">
          <div className="flex items-center mb-6">
            <div className="h-10 w-10 rounded-lg bg-primary-light flex items-center justify-center text-sm font-bold shadow-inner border border-white/20">
              AD
            </div>
            <div className="ml-3">
              <p className="text-sm font-bold text-white leading-tight">
                {userName}
              </p>
              <p className="text-xs text-white/60">{userEmail}</p>
            </div>
          </div>
          <Link
            to="/login"
            className="flex items-center justify-center px-4 py-3 w-full text-sm font-bold text-red-100 bg-red-500/20 border border-red-500/30 hover:bg-red-500/40 hover:text-white rounded-lg transition-all duration-200 shadow-sm"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Keluar Sistem
          </Link>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
