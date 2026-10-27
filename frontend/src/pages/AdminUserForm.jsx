import React, { useState, useEffect } from "react";
import { Save, ArrowLeft, AlertTriangle, Loader2, Eye, EyeOff } from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import { ROLE_OPTIONS, PRODI_OPTIONAL_ROLES, PRODI_REQUIRED_ROLES } from "../lib/roles";
import { useProdiList } from "../lib/prodi";
import axios from "axios";
import { useNavigate, useParams } from "react-router-dom";

const AdminUserForm = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const { id } = useParams();
  const navigate = useNavigate();
  const prodiList = useProdiList();

  const [formData, setFormData] = useState({ name: "", nip: "", password: "", role: "dpa", prodi: "" });

  useEffect(() => {
    if (id) {
      fetchUser(id);
    }
  }, [id]);

  const fetchUser = async (userId) => {
    try {
      const response = await axios.get(`/api/users/${userId}`);
      setFormData({
        name: response.data.name,
        nip: response.data.nip || "",
        prodi: response.data.prodi || "",
        role: response.data.role || "dpa",
        password: "",
      });
    } catch (err) {
      setError(err.response?.data?.error || "Gagal mengambil data pengguna.");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    try {
      if (id) {
        await axios.put(`/api/users/${id}`, formData);
      } else {
        await axios.post("/api/users", formData);
      }
      navigate("/admin/users");
    } catch (err) {
      setError(err.response?.data?.error || "Gagal menyimpan data pengguna");
      setLoading(false);
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title={id ? "Ubah Pengguna" : "Tambah Pengguna"}
          subtitle="Isi data akun beserta peran aksesnya di sistem."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto">
          <button
            onClick={() => navigate("/admin/users")}
            className="flex items-center text-sm font-semibold text-primary hover:text-primary-dark transition"
          >
            <ArrowLeft size={16} className="mr-2" /> Kembali ke Daftar Pengguna
          </button>
          
          <div className="bg-surface p-8 rounded-2xl shadow-sm border border-border">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-6">
              {id ? "Edit Data Pengguna" : "Tambah Akun Pengguna Baru"}
            </h2>
            
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center text-red-600 text-sm">
                  <AlertTriangle className="h-5 w-5 mr-3 shrink-0" />
                  {error}
                </div>
              )}
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Nama Lengkap</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                  placeholder="Masukkan nama lengkap pengguna"
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">NIP (Nomor Induk Pegawai)</label>
                <input
                  type="text"
                  required
                  pattern="[A-Za-z0-9 .\-]{5,30}"
                  title="NIP berisi huruf dan angka (spasi/titik/strip boleh, akan dibuang)"
                  value={formData.nip}
                  onChange={(e) => setFormData({ ...formData, nip: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition font-mono"
                  placeholder="Contoh: 198701012010011001"
                />
                <p className="text-xs text-gray-500 mt-2">Dipakai sebagai identitas login pengguna.</p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Peran Pengguna</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              
              {(PRODI_REQUIRED_ROLES.includes(formData.role) || PRODI_OPTIONAL_ROLES.includes(formData.role)) && (
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Program Studi</label>
                  <select
                    value={formData.prodi}
                    required={PRODI_REQUIRED_ROLES.includes(formData.role)}
                    onChange={(e) => setFormData({ ...formData, prodi: e.target.value })}
                    className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                  >
                    <option value="">
                      {PRODI_REQUIRED_ROLES.includes(formData.role) ? "-- Pilih program studi --" : "Semua program studi (tingkat fakultas)"}
                    </option>
                    {prodiList.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-2">
                    Pengguna hanya memprediksi dan melihat hasil untuk program studi ini. Berkas dari BAPSI tetap bisa diunduh semua prodi.
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Kata Sandi {id && <span className="text-gray-500 font-normal">(Biarkan kosong jika tidak ingin diubah)</span>}
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required={!id}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full pl-4 pr-11 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                    placeholder={id ? "Ubah kata sandi" : "Buat kata sandi aman"}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
                    aria-pressed={showPassword}
                    title={showPassword ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-secondary focus:outline-none focus-visible:text-primary transition-colors cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>
              
              <div className="pt-6 flex justify-end gap-3">
                <Button variant="ghost" size="lg" onClick={() => navigate("/admin/users")}>
                  Batal
                </Button>
                <Button type="submit" size="lg" disabled={loading}>
                  {loading ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                  {loading ? "Menyimpan..." : "Simpan Data"}
                </Button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AdminUserForm;
