import React from 'react';
import { Bell, Calendar, Menu } from 'lucide-react';

const Header = ({ title, subtitle, toggleSidebar }) => {
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

      <header className="h-20 bg-surface border-b border-border hidden lg:flex items-center justify-between px-8 shrink-0 z-10 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-secondary">{title}</h1>
          <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
        </div>
        
        <div className="flex items-center space-x-4">
          <button className="p-2 text-gray-400 hover:text-primary transition-colors bg-gray-50 rounded-full hover:bg-gray-100">
            <Bell className="h-5 w-5" />
          </button>
          <div className="h-8 w-px bg-border"></div>
          <div className="text-sm text-gray-600 font-medium bg-white border border-border px-4 py-2 rounded-lg shadow-sm flex items-center">
            <Calendar className="h-4 w-4 mr-2 text-primary" />
            <span>Semester Ganjil 2026/2027</span>
          </div>
        </div>
      </header>
    </>
  );
};

export default Header;
