import React from "react";
import {
  Sparkles,
  BarChart2,
  History,
  LogOut,
  X,
  Settings2,
  Users,
  Wand2,
  FolderOpen,
  TableProperties,
} from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearSession } from "../lib/session";
import { PREDIKSI_ROLES, roleLabel } from "../lib/roles";
import { readAsal } from "../lib/navigasi";

// Menu dikelompokkan mengikuti alur kerja: siapkan data & model dulu, baru
// jalankan prediksi, sisanya administrasi. `match` menentukan menu induk mana
// yang menyala saat pengguna berada di halaman anak (detail mahasiswa, detail
// batch, form pengguna), supaya orientasi tidak hilang. `roles` membatasi
// peran yang melihat grup itu; tanpa `roles`, grup tampil untuk semua peran.
// Saklar menu Format Data. Disembunyikan sementara: halamannya masih bisa
// dibuka lewat /admin/format-data. Ubah ke true untuk menampilkannya kembali.
const SHOW_FORMAT_DATA = false;

const MENU_GROUPS = [
  {
    label: "Data & Model",
    roles: ["admin"],
    items: [
      ...(SHOW_FORMAT_DATA
        ? [
            {
              to: "/admin/format-data",
              label: "Format Data",
              icon: TableProperties,
              match: (p) => p === "/admin/format-data",
            },
          ]
        : []),
      {
        to: "/admin/preprocessing",
        label: "Preprocessing Data",
        icon: Wand2,
        match: (p) => p === "/admin/preprocessing",
      },
      {
        to: "/admin/model",
        label: "Master Model",
        icon: Settings2,
        match: (p) => p === "/admin/model",
      },
    ],
  },
  {
    label: "Prediksi",
    roles: PREDIKSI_ROLES,
    items: [
      {
        to: "/prediksi",
        label: "Buat Prediksi",
        icon: Sparkles,
        match: (p) => p === "/prediksi",
      },
      {
        to: "/results",
        label: "Hasil Prediksi",
        icon: BarChart2,
        // Halaman batch & detail menyala di sini kecuali dibuka dari Log Riwayat.
        match: (p, s) =>
          p === "/results" ||
          (/^\/(batch|detail|courses)\//.test(p) && readAsal(s).from !== "history"),
      },
    ],
  },
  {
    label: "Data Mahasiswa",
    items: [
      {
        to: "/berkas",
        label: "Berkas Mahasiswa",
        icon: FolderOpen,
        match: (p) => p === "/berkas",
      },
    ],
  },
  {
    label: "Administrasi",
    roles: ["admin"],
    items: [
      {
        to: "/admin/users",
        label: "Master Pengguna",
        icon: Users,
        match: (p) => p.startsWith("/admin/users"),
      },
      {
        to: "/history",
        label: "Log Riwayat",
        icon: History,
        match: (p, s) =>
          p === "/history" ||
          (/^\/(batch|detail|courses)\//.test(p) && readAsal(s).from === "history"),
      },
    ],
  },
];

const Sidebar = ({ isOpen, toggleSidebar }) => {
  const location = useLocation();
  const currentPath = location.pathname;
  const navigate = useNavigate();

  const handleLogout = (e) => {
    e.preventDefault();
    clearSession();
    navigate("/login");
  };

  let user = { nip: "", name: "Pengguna", role: "" };
  try {
    const savedUser = localStorage.getItem("user");
    if (savedUser) {
      user = JSON.parse(savedUser);
    }
  } catch (e) {
    console.error("Gagal membaca data user", e);
  }

  const { nip: userNip, name: userName, role: computedRole, prodi: userProdi } = user;
  const initials = (userName || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  const groups = MENU_GROUPS.filter(
    (g) => !g.roles || g.roles.includes(computedRole),
  );

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
            aria-label="Tutup menu"
            className="lg:hidden absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-white/10 rounded-md"
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src="/logo.png"
            alt="Logo Sisip Program"
            className="h-14 w-14 object-contain bg-surface p-2 rounded-xl shadow-md mb-4"
          />
          <h2 className="font-bold text-xl leading-tight tracking-wide text-white text-center">
            Sistem Prediksi
          </h2>
          <span className="text-xs text-white/70 font-semibold uppercase tracking-wider mt-1 text-center">
            Sisip Program
          </span>
        </div>

        {/* Penanda peran — hanya informasi, bukan tombol. */}
        <div className="px-6 py-4 border-b border-white/10 shrink-0">
          <div className="bg-white/10 px-4 py-2.5 rounded-lg">
            <span className="text-sm font-bold tracking-wide text-white uppercase">
              {roleLabel(computedRole)}
            </span>
          </div>
        </div>

        {/* overflow-y-auto tanpa menyembunyikan scrollbar: di layar pendek menu
            memang perlu digulir, dan pengguna harus tahu masih ada isinya. */}
        <nav className="flex-1 overflow-y-auto py-6 space-y-6">
          {groups.map((group) => (
            <div key={group.label}>
              <p className="px-8 mb-2 text-[11px] font-bold uppercase tracking-widest text-white/40">
                {group.label}
              </p>
              <div className="space-y-2">
                {group.items.map(({ to, label, icon: Icon, match }) => {
                  const active = match(currentPath, location.search);
                  return (
                    <Link
                      key={to}
                      to={to}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center px-4 py-3 mx-4 rounded-lg font-medium transition duration-200 border border-dashed border-white/20 ${active ? "bg-surface text-primary font-bold shadow-md border-solid" : "text-white/80 bg-white/5 hover:bg-white/10 hover:text-white"}`}
                    >
                      <Icon className="h-5 w-5 mr-4 text-accent" />
                      <span>{label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="p-6 border-t border-white/10 shrink-0">
          <div className="flex items-center mb-6">
            <div className="h-10 w-10 rounded-lg bg-primary-light flex items-center justify-center text-sm font-bold shadow-inner border border-white/20">
              {initials}
            </div>
            <div className="ml-3 min-w-0">
              <p className="text-sm font-bold text-white leading-tight truncate">
                {userName}
              </p>
              <p className="text-xs text-white/60 truncate">
                {[userNip && `NIP ${userNip}`, userProdi].filter(Boolean).join(" · ")}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center justify-center px-4 py-3 w-full text-sm font-bold text-red-100 bg-red-500/20 border border-red-500/30 hover:bg-red-500/40 hover:text-white rounded-lg transition-all duration-200 shadow-sm"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Keluar Sistem
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
