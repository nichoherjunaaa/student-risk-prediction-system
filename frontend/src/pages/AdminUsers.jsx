import React, { useState, useEffect } from "react";
import { Plus, Trash2, Edit } from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import ConfirmDialog from "../components/ConfirmDialog";
import { roleLabel } from "../lib/roles";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const AdminUsers = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [userToDelete, setUserToDelete] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await axios.get("/api/users");
      setUsers(response.data);
      setError("");
    } catch (err) {
      setError(
        err.response?.data?.error || "Gagal memuat daftar pengguna dari server.",
      );
    }
    setLoading(false);
  };

  const handleOpenForm = (user = null) => {
    navigate(user ? `/admin/users/edit/${user.id}` : "/admin/users/new");
  };

  const handleDelete = async () => {
    const target = userToDelete;
    setUserToDelete(null);
    if (!target) return;
    try {
      await axios.delete(`/api/users/${target.id}`);
      fetchUsers();
    } catch (err) {
      setError(err.response?.data?.error || "Gagal menghapus pengguna.");
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Master Pengguna"
          subtitle="Kelola akun dan hak akses pengguna sistem."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto">
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border min-h-[400px]">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
              <div>
                <h2 className="text-xl font-bold">Daftar Pengguna</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Akun DPA, Kaprodi, dan Dekan yang dapat masuk ke sistem.
                </p>
              </div>
              <Button onClick={() => handleOpenForm()}>
                <Plus size={18} /> Tambah Pengguna
              </Button>
            </div>

            {error && (
              <p className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
                {error}
              </p>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-gray-50 text-xs font-semibold text-gray-500 uppercase">
                    <th scope="col" className="p-3">Nama Pengguna</th>
                    <th scope="col" className="p-3">Email</th>
                    <th scope="col" className="p-3">Peran</th>
                    <th scope="col" className="p-3 text-center">Aksi</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-border">
                  {loading ? (
                    <tr>
                      <td colSpan="4" className="p-4 text-center text-gray-500">
                        Memuat daftar pengguna...
                      </td>
                    </tr>
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="p-4 text-center text-gray-500">
                        Belum ada akun pengguna yang terdaftar.
                      </td>
                    </tr>
                  ) : (
                    users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50 transition">
                        <td className="p-3 font-medium text-gray-900">{user.name}</td>
                        <td className="p-3 text-gray-600">{user.email}</td>
                        <td className="p-3 text-gray-600">
                          <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded-md text-xs font-semibold uppercase">
                            {roleLabel(user.role)}
                          </span>
                        </td>
                        <td className="p-3 text-center space-x-2">
                          <button
                            onClick={() => handleOpenForm(user)}
                            className="p-2 text-primary bg-primary-light/10 hover:bg-primary hover:text-white rounded-lg transition"
                            aria-label={`Ubah pengguna ${user.name}`}
                            title="Ubah pengguna"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            onClick={() => setUserToDelete(user)}
                            className="p-2 text-red-500 bg-red-50 hover:bg-red-500 hover:text-white rounded-lg transition"
                            aria-label={`Hapus pengguna ${user.name}`}
                            title="Hapus pengguna"
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

      <ConfirmDialog
        open={Boolean(userToDelete)}
        title="Hapus Akun Pengguna?"
        message={
          userToDelete
            ? `Akun ${userToDelete.name} (${roleLabel(userToDelete.role)}) akan dihapus permanen dan tidak bisa dipulihkan.`
            : ""
        }
        confirmLabel="Ya, Hapus"
        onConfirm={handleDelete}
        onCancel={() => setUserToDelete(null)}
      />
    </div>
  );
};

export default AdminUsers;
