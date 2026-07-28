import React, { useState } from 'react';
import { ArrowLeft, User, AlertTriangle, BookOpen, TrendingDown, Layers, ShieldAlert, XCircle, Printer, Mail } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useParams, Link } from 'react-router-dom';

const DetailStudent = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { nim } = useParams();

  // In a real app, you would fetch the student's full data from the backend using the nim
  
  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-background relative z-10">
        <Header 
          title="Detail Mahasiswa" 
          subtitle="Tinjau profil akademik komprehensif dan faktor risiko." 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto mb-6">
            <Link to="/results" className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-primary transition-colors bg-white px-4 py-2 rounded-lg border border-border shadow-sm">
              <ArrowLeft className="h-4 w-4 mr-2" /> Kembali ke Hasil Prediksi
            </Link>
          </div>

          <div className="max-w-5xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden">
            {/* Profile Header */}
            <div className="bg-primary px-8 py-10 text-surface flex flex-col md:flex-row items-center md:items-start justify-between relative overflow-hidden">
              <div className="absolute -right-20 -top-20 h-64 w-64 bg-white opacity-5 rounded-full blur-2xl"></div>
              
              <div className="flex items-center z-10">
                <div className="h-24 w-24 rounded-full bg-white/20 flex items-center justify-center border-4 border-white/30 backdrop-blur-sm shadow-inner">
                  <User className="h-12 w-12 text-white" />
                </div>
                <div className="ml-6">
                  <h2 className="text-3xl font-bold tracking-tight">Mahasiswa {nim}</h2>
                  <div className="flex items-center mt-2 space-x-4">
                    <span className="bg-black/20 px-3 py-1 rounded-md text-sm font-medium">NIM: {nim}</span>
                    <span className="flex items-center text-sm font-medium text-accent">
                      <AlertTriangle className="h-4 w-4 mr-1" /> Ditandai Beresiko
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="mt-6 md:mt-0 flex flex-col items-center justify-center bg-white/10 rounded-xl px-6 py-4 backdrop-blur-sm z-10 border border-white/20">
                <p className="text-xs uppercase tracking-wider font-semibold text-white/80 mb-1">Hasil Prediksi</p>
                <p className="text-lg font-bold text-accent">SISIP PROGRAM</p>
              </div>
            </div>

            {/* Profile Content */}
            <div className="p-8">
              <h3 className="text-lg font-bold text-secondary mb-6 flex items-center">
                <BookOpen className="h-5 w-5 mr-2 text-primary" /> Rincian Akademik
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">IPK 1</p>
                      <p className="text-3xl font-bold text-secondary">2.20</p>
                    </div>
                    <div className="h-10 w-10 bg-yellow-100 rounded-full flex items-center justify-center text-yellow-600">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-4 w-full bg-gray-200 rounded-full h-1.5">
                    <div className="bg-yellow-500 h-1.5 rounded-full" style={{ width: '55%' }}></div>
                  </div>
                  <p className="text-xs text-yellow-600 font-medium mt-2">Peringatan: Ambang Batas</p>
                </div>
                
                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">IPK 2</p>
                      <p className="text-3xl font-bold text-secondary">2.00</p>
                    </div>
                    <div className="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center text-red-600">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-4 w-full bg-gray-200 rounded-full h-1.5">
                    <div className="bg-red-500 h-1.5 rounded-full" style={{ width: '50%' }}></div>
                  </div>
                  <p className="text-xs text-red-600 font-medium mt-2">Penurunan Kritis</p>
                </div>

                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">IPK 3</p>
                      <p className="text-3xl font-bold text-secondary">2.10</p>
                    </div>
                    <div className="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center text-red-600">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-4 w-full bg-gray-200 rounded-full h-1.5">
                    <div className="bg-red-500 h-1.5 rounded-full" style={{ width: '52.5%' }}></div>
                  </div>
                  <p className="text-xs text-red-600 font-medium mt-2">Di bawah ambang batas minimum 2.75</p>
                </div>
                
                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">Total SKS 3</p>
                      <p className="text-3xl font-bold text-secondary">45</p>
                    </div>
                    <div className="h-10 w-10 bg-yellow-100 rounded-full flex items-center justify-center text-yellow-600">
                      <Layers className="h-5 w-5" />
                    </div>
                  </div>
                  <div className="mt-4 w-full bg-gray-200 rounded-full h-1.5">
                    <div className="bg-yellow-500 h-1.5 rounded-full" style={{ width: '31%' }}></div>
                  </div>
                  <p className="text-xs text-yellow-600 font-medium mt-2">Tertinggal dari rata-rata semester</p>
                </div>
              </div>

              <div className="bg-red-50 border border-red-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-bold text-red-800 mb-3 flex items-center">
                  <ShieldAlert className="h-5 w-5 mr-2" /> Faktor Risiko Utama yang Diidentifikasi
                </h3>
                <ul className="space-y-2">
                  <li className="flex items-start">
                    <XCircle className="h-5 w-5 text-red-500 mr-2 mt-0.5 shrink-0" />
                    <span className="text-sm text-red-900 font-medium">Penurunan IPK berturut-turut dalam 2 semester terakhir.</span>
                  </li>
                  <li className="flex items-start">
                    <XCircle className="h-5 w-5 text-red-500 mr-2 mt-0.5 shrink-0" />
                    <span className="text-sm text-red-900 font-medium">Diprediksi sebagai SISIP oleh model pembelajaran mesin.</span>
                  </li>
                </ul>
                
                <div className="mt-6 pt-6 border-t border-red-200/50 flex space-x-3">
                  <button className="px-5 py-2.5 bg-white text-red-700 font-bold border border-red-200 rounded-lg shadow-sm hover:bg-red-50 transition-colors flex items-center">
                    <Printer className="h-4 w-4 mr-2" /> Cetak Profil
                  </button>
                  <button className="px-5 py-2.5 bg-red-600 text-white font-bold rounded-lg shadow-sm hover:bg-red-700 transition-colors flex items-center">
                    <Mail className="h-4 w-4 mr-2" /> Kirim Surat Peringatan
                  </button>
                </div>
              </div>

            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DetailStudent;
