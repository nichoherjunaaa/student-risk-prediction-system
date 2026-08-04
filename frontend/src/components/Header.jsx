import React, { useState, useEffect, useRef } from 'react';
import { Bell, Calendar, Menu, ChevronDown, User, Settings, Users, Shield } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

const Header = ({ title, subtitle, toggleSidebar }) => {
  const [showNotifications, setShowNotifications] = useState(false);
  const dropdownRef = useRef(null);
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;

  // Fungsi untuk mendapatkan Tahun Akademik dan Semester yang dinamis
  const getAcademicSemester = () => {
    const now = new Date();
    const month = now.getMonth() + 1; // 1-12
    const year = now.getFullYear();
    
    // Ganjil: Agustus (8) hingga Januari (1)
    // Genap: Februari (2) hingga Juli (7)
    let semester = "Ganjil";
    let startYear = year;
    let endYear = year + 1;
    
    if (month >= 8) {
      semester = "Ganjil";
      startYear = year;
      endYear = year + 1;
    } else if (month <= 1) {
      semester = "Ganjil";
      startYear = year - 1;
      endYear = year;
    } else {
      semester = "Genap";
      startYear = year - 1;
      endYear = year;
    }
    
    return `Semester ${semester} ${startYear}/${endYear}`;
  };

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
        <button onClick={toggleSidebar} className="p-2 bg-white/10 rounded-md focus:outline-none hover:bg-white/20 transition-colors">
          <Menu className="h-6 w-6" />
        </button>
      </div>

      <div className="flex-none shadow-sm z-10 shrink-0">
        <header className="h-14 bg-surface border-b border-border hidden lg:flex items-center justify-between px-6">
          <div className="flex space-x-2">
            {(currentPath === '/admin/users' || currentPath.startsWith('/admin/users/') || currentPath === '/admin/roles') ? (
              <>
                <button 
                  onClick={() => navigate('/admin/users')}
                  className={`flex items-center px-4 py-1.5 text-sm font-medium rounded transition-colors ${(currentPath === '/admin/users' || currentPath.startsWith('/admin/users/')) ? 'bg-primary text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  <Users className="w-4 h-4 mr-2" />
                  Daftar Pengguna
                </button>
                <button 
                  onClick={() => navigate('/admin/roles')}
                  className={`flex items-center px-4 py-1.5 text-sm font-medium rounded transition-colors ${currentPath === '/admin/roles' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  <Shield className="w-4 h-4 mr-2" />
                  Manajemen Role
                </button>
              </>
            ) : null}
          </div>
          
          <div className="flex items-center space-x-3 ml-auto">
            <div className="text-sm text-gray-600 font-medium mr-4 flex items-center bg-gray-50 border border-border px-3 py-1.5 rounded-md">
              <Calendar className="h-4 w-4 mr-2 text-primary" />
              <span>{getAcademicSemester()}</span>
            </div>

            <button className="p-1.5 text-gray-400 hover:text-primary transition-colors bg-gray-100 rounded-full hover:bg-gray-200">
              <User className="h-5 w-5" />
            </button>
            <button className="p-1.5 text-gray-400 hover:text-primary transition-colors bg-gray-100 rounded-full hover:bg-gray-200">
              <Settings className="h-5 w-5" />
            </button>
          <div className="relative" ref={dropdownRef}>
            <button 
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 text-gray-400 hover:text-primary transition-colors bg-gray-50 rounded-full hover:bg-gray-100"
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

        {/* Area Judul Halaman */}
        <div className="px-8 py-5 bg-white border-b border-border shadow-sm hidden lg:block">
          <h1 className="text-xl font-bold text-secondary uppercase tracking-wider">{title}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>
        </div>
      </div>
    </>
  );
};

export default Header;
