import React, { useState, useEffect } from "react";
import { Users, Plus, Trash2, Edit, Shield } from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const AdminUsers = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await axios.get("http://localhost:5000/api/users");
      setUsers(response.data);
    } catch (err) {
      console.error("Gagal mengambil data pengguna:", err);
    }
  };

  const handleOpenModal = (user = null) => {
    if (user) {
      navigate(`/admin/users/edit/${user.id}`);
    } else {
      navigate("/admin/users/new");
    }
  };

  const handleDelete = async (id) => {
    if (window.confirm("Apakah Anda yakin ingin menghapus akun DPA ini?")) {
      try {
        await axios.delete(`http://localhost:5000/api/users/${id}`);
        fetchUsers();
      } catch (err) {
        alert(err.response?.data?.error || "Gagal menghapus pengguna");
      }
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header toggleSidebar={() => setSidebarOpen(!sidebarOpen)} title="Panel Utama Admin: Master Pengguna" />

        <main className="p-6 space-y-6 max-w-7xl w-full mx-auto">
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border min-h-[400px]">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
              <div>
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Users className="text-primary" /> Master Pengguna (DPA)
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Kelola master data akun DPA yang memiliki akses untuk mengunggah dan melakukan prediksi nilai mahasiswa.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate("/admin/roles")}
                  className="px-4 py-2.5 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 transition shadow-sm flex items-center gap-2 border border-gray-200"
                >
                  <Shield size={18} /> Manajemen Role
                </button>
                <button
                  onClick={() => handleOpenModal()}
                  className="px-4 py-2.5 bg-primary text-white font-semibold rounded-lg hover:bg-primary-dark transition shadow-sm flex items-center gap-2"
                >
                  <Plus size={18} /> Tambah DPA Baru
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-gray-50 text-xs font-semibold text-gray-500 uppercase">
                    <th className="p-3">Nama Dosen</th>
                    <th className="p-3">Email</th>
                    <th className="p-3">Role</th>
                    <th className="p-3 text-center">Aksi</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-border">
                  {users.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="p-4 text-center text-gray-400">
                        Belum ada akun DPA yang terdaftar.
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50/50">
                        <td className="p-3 font-semibold text-secondary">{user.name}</td>
                        <td className="p-3 text-gray-600">{user.email}</td>
                        <td className="p-3">
                          <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded uppercase">
                            {user.role}
                          </span>
                        </td>
                        <td className="p-3 text-center space-x-2">
                          <button
                            onClick={() => handleOpenModal(user)}
                            className="p-2 text-primary bg-primary-light/10 hover:bg-primary hover:text-white rounded-lg transition"
                            title="Edit Pengguna"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete(user.id)}
                            className="p-2 text-red-500 bg-red-50 hover:bg-red-500 hover:text-white rounded-lg transition"
                            title="Hapus Pengguna"
                          >
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default AdminUsers;
