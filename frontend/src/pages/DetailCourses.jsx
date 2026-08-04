import React, { useState, useEffect } from 'react';
import { ArrowLeft, BookOpen, ShieldAlert, XCircle } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useParams, Link, useLocation } from 'react-router-dom';
import axios from 'axios';

const DetailCourses = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { nim } = useParams();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const batchId = searchParams.get('batch');
  
  const [studentData, setStudentData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStudent = async () => {
      try {
        let url = `http://localhost:5000/api/student/${nim}`;
        if (batchId) {
          url += `?batch=${batchId}`;
        }
        const response = await axios.get(url);
        setStudentData(response.data);
      } catch (error) {
        console.error("Gagal mengambil data mahasiswa", error);
      }
      setLoading(false);
    };
    fetchStudent();
  }, [nim, batchId]);

  if (loading) {
    return (
      <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
        <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-gray-500">Memuat detail mata kuliah...</p>
        </main>
      </div>
    );
  }

  if (!studentData) {
    return (
      <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
        <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 flex flex-col items-center justify-center">
          <p className="text-red-500 mb-4">Mahasiswa tidak ditemukan.</p>
          <Link to="/history" className="text-primary underline">Kembali ke Riwayat</Link>
        </main>
      </div>
    );
  }

  const { details = {} } = studentData;
  const { 
    nama = '-', 
    failed_subjects = [], 
    passed_subjects = [], 
    sks_passed = 0, 
    sks_failed = 0 
  } = details;

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <main className="flex-1 flex flex-col h-full relative overflow-hidden">
        <Header 
          title="Detail Matakuliah" 
          subtitle={`Rincian SKS & Matakuliah untuk ${nama}`} 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />

        <div className="flex-1 overflow-y-auto p-8 relative z-10">
          <div className="max-w-7xl mx-auto">
            <div className="mb-6">
              <Link to={`/detail/${nim}${batchId ? `?batch=${batchId}` : ''}`} className="inline-flex items-center text-gray-500 hover:text-primary transition-colors font-medium">
                <ArrowLeft className="h-5 w-5 mr-2" /> Kembali ke Profil Mahasiswa
              </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Box Lulus */}
              <div className="bg-green-50 border border-green-200 rounded-xl p-6 shadow-sm flex flex-col h-full">
                <h3 className="text-xl font-bold text-green-800 mb-4 flex items-center border-b border-green-200 pb-4">
                  <BookOpen className="h-6 w-6 mr-3" /> Telah Lulus ({sks_passed} SKS)
                </h3>
                <div className="flex-1 overflow-y-auto pr-2" style={{ maxHeight: 'calc(100vh - 280px)' }}>
                  {passed_subjects.length > 0 ? (
                    <ul className="space-y-3">
                      {passed_subjects.map((sub, idx) => (
                        <li key={idx} className="flex items-start bg-white p-4 rounded-xl border border-green-100 shadow-sm transition hover:shadow-md">
                          <div className="w-full flex justify-between items-center">
                             <div>
                               <span className="block text-sm text-green-900 font-bold mb-1">{sub.matkul}</span>
                               <span className="block text-xs text-green-700 font-medium">{sub.sks} SKS</span>
                             </div>
                             <span className="text-sm text-green-800 font-bold bg-green-100 px-3 py-1.5 rounded-lg border border-green-200">
                               Nilai: {sub.nilai}
                             </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="h-full flex items-center justify-center flex-col text-green-700/60 py-10">
                      <BookOpen className="h-12 w-12 mb-3 opacity-50" />
                      <p className="font-medium">Belum ada data nilai lulus.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Box Tidak Lulus */}
              <div className="bg-red-50 border border-red-200 rounded-xl p-6 shadow-sm flex flex-col h-full">
                <h3 className="text-xl font-bold text-red-800 mb-4 flex items-center border-b border-red-200 pb-4">
                  <ShieldAlert className="h-6 w-6 mr-3" /> Belum Lulus ({sks_failed} SKS)
                </h3>
                <div className="flex-1 overflow-y-auto pr-2" style={{ maxHeight: 'calc(100vh - 280px)' }}>
                  {failed_subjects.length > 0 ? (
                    <ul className="space-y-3">
                      {failed_subjects.map((sub, idx) => (
                        <li key={idx} className="flex items-start bg-white p-4 rounded-xl border border-red-100 shadow-sm transition hover:shadow-md">
                          <XCircle className="h-6 w-6 text-red-500 mr-4 shrink-0" />
                          <div className="w-full flex justify-between items-center">
                             <div>
                               <span className="block text-sm text-red-900 font-bold mb-1">{sub.matkul}</span>
                               <span className="block text-xs text-red-700 font-medium">{sub.sks} SKS</span>
                             </div>
                             <span className="text-sm text-red-800 font-bold bg-red-100 px-3 py-1.5 rounded-lg border border-red-200">
                               Nilai: {sub.nilai}
                             </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="h-full flex items-center justify-center flex-col text-red-700/60 py-10">
                      <XCircle className="h-12 w-12 mb-3 opacity-50" />
                      <p className="font-medium">Tidak ada riwayat matakuliah tidak lulus.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DetailCourses;
