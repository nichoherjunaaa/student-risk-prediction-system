import React, { useState, useEffect, useRef } from 'react';
import { Bell, Menu } from 'lucide-react';

const Header = ({ title, subtitle, toggleSidebar }) => {
  const [showNotifications, setShowNotifications] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <>
      <div className="lg:hidden flex items-center justify-between bg-primary p-4 text-surface shrink-0 z-40 shadow-md">
        <div className="flex items-center">
          <img src="/logo.png" alt="System Logo" className="h-8 w-8 object-contain bg-surface p-1 rounded-md mr-3" />
          <span className="font-bold text-lg">Sisip Program</span>
        </div>
        <button onClick={toggleSidebar} aria-label="Buka menu" className="p-2 bg-white/10 rounded-md focus:outline-none hover:bg-white/20 transition-colors">
          <Menu className="h-6 w-6" />
        </button>
      </div>

      {/* Judul halaman versi ringkas untuk layar kecil, karena bilah atas di
          bawah ini hanya tampil mulai breakpoint lg. */}
      {title && (
        <div className="lg:hidden px-4 py-3 bg-surface border-b border-border shrink-0">
          <h1 className="text-sm font-bold text-secondary uppercase tracking-wider">{title}</h1>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      )}

      <div className="flex-none shadow-sm z-10 shrink-0">
        {/* Satu bilah saja: judul halaman di kiri, aksi akun di kanan. Bilah ini
            dulu kosong sebelah kiri karena menampung sub menu Master Pengguna
            yang sudah dihapus. */}
        <header className="min-h-14 bg-surface border-b border-border hidden lg:flex items-center justify-between gap-6 px-8 py-3">
          <div className="min-w-0">
            <h1 className="text-base font-bold text-secondary uppercase tracking-wider truncate">
              {title}
            </h1>
            {subtitle && <p className="text-sm text-gray-500 mt-0.5 truncate">{subtitle}</p>}
          </div>

          {/* Hanya notifikasi: tombol profil dan setelan sebelumnya tidak punya
              aksi apa pun, jadi lebih baik tidak ditawarkan sama sekali. */}
          <div className="flex items-center shrink-0">
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                aria-label="Notifikasi"
                aria-expanded={showNotifications}
                className="relative p-2 text-gray-500 hover:text-primary transition-colors bg-gray-100 rounded-full hover:bg-gray-200"
              >
                <Bell className="h-5 w-5" />
                {/* Optional: Tambahkan badge merah jika ada notifikasi belum dibaca */}
                {/* <span className="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full border border-white"></span> */}
              </button>

              {showNotifications && (
                <div className="absolute right-0 mt-2 w-72 bg-white border border-border rounded-xl shadow-lg py-2 z-50">
                  <div className="px-4 py-2 border-b border-border">
                    <h3 className="text-sm font-bold text-secondary">Notifikasi</h3>
                  </div>
                  <div className="max-h-64 overflow-y-auto px-4 py-6 text-center">
                    <p className="text-sm text-gray-500">Belum ada notifikasi baru untuk Anda.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>
      </div>
    </>
  );
};

export default Header;
