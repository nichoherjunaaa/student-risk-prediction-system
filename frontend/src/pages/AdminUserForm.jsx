import React, { useState, useEffect } from "react";
import { Save, ArrowLeft, AlertTriangle, Loader2 } from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import axios from "axios";
import { useNavigate, useParams } from "react-router-dom";

const AdminUserForm = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { id } = useParams();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({ name: "", email: "", password: "", role: "dpa" });

  useEffect(() => {
    if (id) {
      fetchUser(id);
    }
  }, [id]);

  const fetchUser = async (userId) => {
    try {
      const response = await axios.get(`http://localhost:5000/api/users/${userId}`);
      setFormData({
        name: response.data.name,
        email: response.data.email,
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
        await axios.put(`http://localhost:5000/api/users/${id}`, formData);
      } else {
        await axios.post("http://localhost:5000/api/users", formData);
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
        <Header toggleSidebar={() => setSidebarOpen(!sidebarOpen)} title="Form Master Pengguna" />

        <main className="p-6 space-y-6 max-w-7xl w-full mx-auto">
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
                  placeholder="Masukkan nama lengkap DPA"
                />
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Alamat Email</label>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                  placeholder="dpa@contoh.com"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Role Pengguna</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                >
                  <option value="dpa">Dosen Pembimbing (DPA)</option>
                  <option value="kaprodi">Kepala Program Studi (Kaprodi)</option>
                  <option value="dekan">Dekan</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Kata Sandi {id && <span className="text-gray-400 font-normal">(Biarkan kosong jika tidak ingin diubah)</span>}
                </label>
                <input
                  type="password"
                  required={!id}
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
                  placeholder={id ? "Ubah kata sandi" : "Buat kata sandi aman"}
                />
              </div>
              
              <div className="pt-6 flex justify-end gap-4">
                <button
                  type="button"
                  onClick={() => navigate("/admin/users")}
                  className="px-6 py-3 text-gray-600 font-bold hover:bg-gray-100 rounded-xl transition"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-8 py-3 bg-primary text-white font-bold rounded-xl hover:bg-primary-dark transition flex items-center gap-2 disabled:opacity-50 shadow-md shadow-primary/20"
                >
                  {loading ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />} 
                  {loading ? "Menyimpan..." : "Simpan Data"}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AdminUserForm;
