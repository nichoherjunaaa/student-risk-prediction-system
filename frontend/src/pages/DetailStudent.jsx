import React, { useState, useEffect } from 'react';
import { ArrowLeft, User, AlertTriangle, BookOpen, TrendingDown, Layers, ShieldAlert, XCircle, Printer, Mail, GraduationCap } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useParams, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const DetailStudent = () => {
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
          <p className="text-gray-500">Memuat profil mahasiswa...</p>
        </main>
      </div>
    );
  }

  if (!studentData) {
    return (
      <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
        <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 flex flex-col items-center justify-center">
          <p className="text-red-500">Data mahasiswa tidak ditemukan.</p>
          <Link to="/results" className="mt-4 text-primary underline">Kembali</Link>
        </main>
      </div>
    );
  }

  const { details = {}, prediction, is_risk } = studentData;
  const { 
    nama = '-', 
    prodi = '-', 
    ipk1 = 0, 
    ipk2 = 0, 
    ipk3 = 0, 
    sks3 = 0, 
    failed_subjects = [], 
    passed_subjects = [], 
    sks_passed = 0, 
    sks_failed = 0 
  } = details;

  const handlePrintProfile = () => {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text('Profil dan Laporan Prediksi Mahasiswa', 14, 22);
    
    doc.setFontSize(12);
    doc.setTextColor(50);
    doc.text(`Nama Mahasiswa: ${nama}`, 14, 32);
    doc.text(`NIM: ${nim}`, 14, 38);
    doc.text(`Program Studi: ${prodi}`, 14, 44);
    
    doc.setLineWidth(0.5);
    doc.line(14, 48, 196, 48);

    doc.setFontSize(11);
    doc.text(`Hasil Prediksi: ${prediction}`, 14, 56);
    doc.text(`Status Risiko: ${is_risk ? 'Tinggi (Berpotensi Sisip)' : 'Aman'}`, 14, 62);
    doc.text(`IPK Sem 1: ${ipk1.toFixed(2)} | IPK Sem 2: ${ipk2.toFixed(2)} | IPK Sem 3: ${ipk3.toFixed(2)}`, 14, 68);
    
    doc.text(`Total SKS Lulus: ${sks_passed} SKS | Total SKS Tidak Lulus: ${sks_failed} SKS`, 14, 76);

    let currentY = 86;
    
    if (failed_subjects.length > 0) {
      doc.text('Daftar Nilai Belum Lulus (D, E, T):', 14, currentY);
      const tableData = failed_subjects.map(s => [s.matkul, s.nilai, s.sks]);
      autoTable(doc, {
        startY: currentY + 4,
        head: [['Mata Kuliah', 'Nilai', 'SKS']],
        body: tableData,
        theme: 'grid',
        headStyles: { fillColor: [220, 38, 38] }
      });
      currentY = doc.lastAutoTable.finalY + 12;
    } else {
      doc.text('Tidak ada mata kuliah yang belum lulus.', 14, currentY);
      currentY += 12;
    }

    if (passed_subjects.length > 0) {
      doc.text('Daftar Nilai Lulus:', 14, currentY);
      const tableData = passed_subjects.map(s => [s.matkul, s.nilai, s.sks]);
      autoTable(doc, {
        startY: currentY + 4,
        head: [['Mata Kuliah', 'Nilai', 'SKS']],
        body: tableData,
        theme: 'grid',
        headStyles: { fillColor: [22, 163, 74] }
      });
    }
    
    doc.save(`Detail_Profil_${nim}.pdf`);
  };

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
          <div className="max-w-7xl mx-auto mb-6">
            <Link to={batchId ? `/batch/${batchId}` : "/results"} className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-primary transition-colors bg-white px-4 py-2 rounded-lg border border-border shadow-sm">
              <ArrowLeft className="h-4 w-4 mr-2" /> {batchId ? "Kembali ke Daftar Mahasiswa" : "Kembali ke Hasil Prediksi"}
            </Link>
          </div>

          <div className="max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden">
            {/* Profile Header */}
            <div className={`px-8 py-10 text-surface flex flex-col md:flex-row items-center md:items-start justify-between relative overflow-hidden ${is_risk ? 'bg-primary' : 'bg-green-700'}`}>
              <div className="absolute -right-20 -top-20 h-64 w-64 bg-white opacity-5 rounded-full blur-2xl"></div>
              
              <div className="flex items-center z-10">
                <div className="h-24 w-24 rounded-full bg-white/20 flex items-center justify-center border-4 border-white/30 backdrop-blur-sm shadow-inner">
                  <User className="h-12 w-12 text-white" />
                </div>
                <div className="ml-6">
                  <h2 className="text-3xl font-bold tracking-tight">{nama !== '-' ? nama : `Mahasiswa ${nim}`}</h2>
                  <div className="flex flex-wrap items-center mt-2 gap-3">
                    <span className="bg-black/20 px-3 py-1 rounded-md text-sm font-medium">NIM: {nim}</span>
                    <span className="bg-black/20 px-3 py-1 rounded-md text-sm font-medium flex items-center">
                      <GraduationCap className="h-4 w-4 mr-1"/> {prodi}
                    </span>
                    {is_risk && (
                      <span className="flex items-center text-sm font-medium text-accent">
                        <AlertTriangle className="h-4 w-4 mr-1" /> Ditandai Beresiko
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              <div className="mt-6 md:mt-0 flex flex-col items-center justify-center bg-white/10 rounded-xl px-6 py-4 backdrop-blur-sm z-10 border border-white/20">
                <p className="text-xs uppercase tracking-wider font-semibold text-white/80 mb-1">Hasil Prediksi</p>
                <p className={`text-lg font-bold ${is_risk ? 'text-accent' : 'text-green-300'}`}>{prediction}</p>
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
                      <p className="text-3xl font-bold text-secondary">{ipk1.toFixed(2)}</p>
                    </div>
                    <div className="h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center text-gray-500">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">IPK 2</p>
                      <p className="text-3xl font-bold text-secondary">{ipk2.toFixed(2)}</p>
                    </div>
                    <div className="h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center text-gray-500">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">IPK 3</p>
                      <p className="text-3xl font-bold text-secondary">{ipk3.toFixed(2)}</p>
                    </div>
                    <div className="h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center text-gray-500">
                      <TrendingDown className="h-5 w-5" />
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 border border-border rounded-xl p-5 shadow-sm hover:border-primary/30 transition-colors">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-1">Total SKS 3</p>
                      <p className="text-3xl font-bold text-secondary">{sks3}</p>
                    </div>
                    <div className="h-10 w-10 bg-gray-200 rounded-full flex items-center justify-center text-gray-500">
                      <Layers className="h-5 w-5" />
                    </div>
                  </div>
                </div>
              </div>

                
              <div className="pt-6 mt-6 border-t border-border flex flex-wrap gap-3">
                <button onClick={handlePrintProfile} className="px-5 py-2.5 bg-primary text-white font-bold border border-primary-dark rounded-lg shadow-sm hover:bg-primary-dark transition-colors flex items-center">
                  <Printer className="h-4 w-4 mr-2" /> Download Detail Profil (PDF)
                </button>
                <Link to={`/courses/${nim}${batchId ? `?batch=${batchId}` : ''}`} className="px-5 py-2.5 bg-white text-secondary font-bold border border-border rounded-lg shadow-sm hover:bg-gray-50 transition-colors flex items-center">
                  <BookOpen className="h-4 w-4 mr-2" /> Detail Matakuliah
                </Link>
              </div>

            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DetailStudent;
