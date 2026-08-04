import React, { useState } from 'react';
import { Shield, Plus, Save, Trash2, CheckSquare, UploadCloud, BarChart2, History, Settings2, Users } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useNavigate } from 'react-router-dom';

const availablePages = [
  { id: 'upload', label: 'Unggah Data', icon: <UploadCloud size={18} /> },
  { id: 'results', label: 'Hasil Prediksi', icon: <BarChart2 size={18} /> },
  { id: 'history', label: 'Log Riwayat', icon: <History size={18} /> },
  { id: 'admin_model', label: 'Master Model', icon: <Settings2 size={18} /> },
  { id: 'admin_users', label: 'Master Pengguna', icon: <Users size={18} /> },
  { id: 'admin_roles', label: 'Manajemen Role', icon: <Shield size={18} /> },
];

const initialRoles = [
  { id: 1, name: 'admin', label: 'SUPER ADMIN', permissions: ['upload', 'results', 'history', 'admin_model', 'admin_users', 'admin_roles'] },
  { id: 2, name: 'dpa', label: 'DPA', permissions: ['upload', 'results', 'history'] }
];

const AdminRoles = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [roles, setRoles] = useState(initialRoles);
  const [selectedRoleId, setSelectedRoleId] = useState(1);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  
  const navigate = useNavigate();

  const selectedRole = roles.find(r => r.id === selectedRoleId);

  const handleTogglePermission = (pageId) => {
    if (selectedRole.name === 'admin') return; // Protect super admin role from changes
    
    setRoles(roles.map(role => {
      if (role.id === selectedRoleId) {
        const hasPerm = role.permissions.includes(pageId);
        const newPerms = hasPerm 
          ? role.permissions.filter(p => p !== pageId)
          : [...role.permissions, pageId];
        return { ...role, permissions: newPerms };
      }
      return role;
    }));
  };

  const handleAddRole = (e) => {
    e.preventDefault();
    if (!newRoleName.trim()) return;
    
    const newRole = {
      id: Date.now(),
      name: newRoleName.toLowerCase().replace(/\s+/g, '_'),
      label: newRoleName,
      permissions: []
    };
    setRoles([...roles, newRole]);
    setSelectedRoleId(newRole.id);
    setNewRoleName('');
    setShowAddModal(false);
  };

  const handleDeleteRole = (id) => {
    const roleToDelete = roles.find(r => r.id === id);
    if (roleToDelete.name === 'admin' || roleToDelete.name === 'dpa') {
      alert("Role bawaan sistem tidak dapat dihapus!");
      return;
    }
    
    if (window.confirm(`Yakin ingin menghapus role ${roleToDelete.label}?`)) {
      setRoles(roles.filter(r => r.id !== id));
      if (selectedRoleId === id) setSelectedRoleId(1);
    }
  };

  const handleSave = () => {
    alert("Konfigurasi role dan hak akses berhasil disimpan sementara (Hanya UI Dummy).");
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header toggleSidebar={() => setSidebarOpen(!sidebarOpen)} title="Panel Utama Admin: Manajemen Role" />

        <main className="p-6 max-w-7xl w-full mx-auto flex-1 flex flex-col h-full">
          {/* Header Action */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
            <div>
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Shield className="text-primary" /> Hak Akses Sistem
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Kelola jenis role baru dan batasi halaman mana saja yang dapat mereka akses.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => navigate('/admin/users')}
                className="px-4 py-2.5 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 transition shadow-sm"
              >
                Kembali ke Master Pengguna
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-2.5 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition shadow-sm flex items-center gap-2"
              >
                <Save size={18} /> Simpan Perubahan
              </button>
            </div>
          </div>

          <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
            {/* KIRI: Daftar Role */}
            <div className="w-full lg:w-1/3 flex flex-col gap-4">
              <div className="bg-surface rounded-2xl shadow-sm border border-border p-5 flex-1 flex flex-col">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="font-bold text-gray-800">Daftar Role</h3>
                  <button 
                    onClick={() => setShowAddModal(true)}
                    className="p-1.5 bg-primary/10 text-primary hover:bg-primary hover:text-white rounded-md transition-colors"
                  >
                    <Plus size={18} />
                  </button>
                </div>
                
                <div className="space-y-2 flex-1 overflow-y-auto pr-2 no-scrollbar">
                  {roles.map(role => (
                    <div 
                      key={role.id}
                      onClick={() => setSelectedRoleId(role.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex justify-between items-center group ${selectedRoleId === role.id ? 'bg-primary/5 border-primary text-primary font-semibold shadow-sm' : 'bg-gray-50 border-transparent hover:border-gray-200 hover:bg-white text-gray-700'}`}
                    >
                      <span>{role.label}</span>
                      {selectedRoleId === role.id && role.name !== 'admin' && role.name !== 'dpa' && (
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDeleteRole(role.id); }}
                          className="text-red-400 hover:text-red-600 p-1"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* KANAN: Daftar Checklist Hak Akses */}
            <div className="w-full lg:w-2/3 flex flex-col">
              <div className="bg-surface rounded-2xl shadow-sm border border-border p-6 flex-1 flex flex-col">
                <div className="mb-6 pb-4 border-b border-gray-100 flex items-center gap-3">
                  <div className="h-10 w-10 bg-primary-light rounded-lg flex items-center justify-center text-primary font-bold shadow-inner">
                    <CheckSquare size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-lg text-gray-800">Konfigurasi Akses: <span className="text-primary">{selectedRole?.label}</span></h3>
                    <p className="text-xs text-gray-500">Centang halaman yang diizinkan untuk diakses oleh role ini.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {availablePages.map(page => {
                    const isChecked = selectedRole?.permissions.includes(page.id);
                    const isDisabled = selectedRole?.name === 'admin';
                    
                    return (
                      <div 
                        key={page.id}
                        onClick={() => !isDisabled && handleTogglePermission(page.id)}
                        className={`flex items-center gap-3 p-4 rounded-xl border transition-all ${isDisabled ? 'bg-gray-50 opacity-60 cursor-not-allowed' : 'cursor-pointer hover:border-primary/50'} ${isChecked ? 'bg-primary/5 border-primary/30' : 'bg-white border-gray-200'}`}
                      >
                        <div className={`flex items-center justify-center w-6 h-6 rounded border ${isChecked ? 'bg-primary border-primary text-white' : 'border-gray-300 bg-white'}`}>
                          {isChecked && <CheckSquare size={14} className="text-white" />}
                        </div>
                        <div className="flex items-center gap-3 text-gray-700 font-medium">
                          <span className={`p-1.5 rounded-md ${isChecked ? 'bg-white shadow-sm text-primary' : 'bg-gray-100 text-gray-500'}`}>
                            {page.icon}
                          </span>
                          {page.label}
                        </div>
                      </div>
                    );
                  })}
                </div>
                
                {selectedRole?.name === 'admin' && (
                  <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-yellow-800 text-sm">
                    <strong>Pemberitahuan:</strong> Role SUPER ADMIN memiliki akses penuh ke seluruh sistem dan tidak dapat dimodifikasi.
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Modal Tambah Role */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-surface rounded-2xl shadow-xl max-w-sm w-full p-6 animate-in zoom-in-95 duration-200">
            <h3 className="text-lg font-bold mb-4">Tambah Role Baru</h3>
            <form onSubmit={handleAddRole}>
              <div className="mb-4">
                <label className="block text-sm font-semibold text-gray-700 mb-1">Nama Role</label>
                <input 
                  type="text" 
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="Contoh: Dekan, Kaprodi..."
                  className="w-full border border-gray-300 px-4 py-2 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                  autoFocus
                  required
                />
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button 
                  type="button" 
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition"
                >
                  Batal
                </button>
                <button 
                  type="submit" 
                  className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark font-medium shadow-sm transition"
                >
                  Simpan
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminRoles;
