import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ServerCrash, Home, RefreshCw } from 'lucide-react';

const ServerError = () => {
  const navigate = useNavigate();

  return (
    <div className="bg-background min-h-screen flex items-center justify-center p-6 font-sans text-secondary antialiased">
      <div className="bg-surface max-w-md w-full p-8 rounded-2xl shadow-xl border border-border text-center">
        <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
          <ServerCrash className="h-10 w-10 text-red-500" />
        </div>
        
        <h1 className="text-6xl font-black text-secondary tracking-tight mb-2">500</h1>
        <h2 className="text-xl font-bold mb-3">Kesalahan Server Internal</h2>
        
        <p className="text-gray-500 mb-8 text-sm leading-relaxed">
          Ups! Ada sesuatu yang salah di sisi server kami. Kami sedang berusaha 
          memperbaikinya. Silakan coba beberapa saat lagi.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button 
            onClick={() => window.location.reload()}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition duration-200 border border-gray-200 shadow-sm"
          >
            <RefreshCw className="h-4 w-4" />
            Muat Ulang
          </button>
          
          <button 
            onClick={() => navigate('/')}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-primary hover:bg-primary-dark text-white font-semibold rounded-xl transition duration-200 shadow-sm"
          >
            <Home className="h-4 w-4" />
            Beranda Utama
          </button>
        </div>
      </div>
    </div>
  );
};

export default ServerError;
