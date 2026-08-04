import React, { useState, useEffect } from 'react';
import { ArrowLeft, Archive, ClipboardList, Download } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useParams, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const DetailBatch = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { id } = useParams();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const filterParam = searchParams.get('filter') || 'sisip'; // 'sisip' or 'tidak_sisip'
  
  const [batch, setBatch] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBatch = async () => {
      try {
        const response = await axios.get(`http://localhost:5000/api/batch/${id}`);
        setBatch(response.data);
      } catch (error) {
        console.error("Failed to fetch batch details", error);
      }
      setLoading(false);
    };
    fetchBatch();
  }, [id]);

  if (loading) {
    return (
      <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
        <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 flex flex-col h-full items-center justify-center">
          <p className="text-gray-500">Memuat arsip batch...</p>
        </main>
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
        <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 flex flex-col h-full items-center justify-center">
          <p className="text-red-500">Batch tidak ditemukan atau terjadi kesalahan saat memuat data.</p>
          <Link to="/history" className="mt-4 text-primary underline">Kembali ke Log Riwayat</Link>
        </main>
      </div>
    );
  }

  const sisipRate = batch.total_records > 0 ? ((batch.at_risk / batch.total_records) * 100).toFixed(1) : 0;
  
  const flaggedStudents = batch.results.filter(r => {
    if (filterParam === 'tidak_sisip') return !r.is_risk;
    return r.is_risk;
  });

  const displayTitle = filterParam === 'tidak_sisip' ? 'Mahasiswa Tidak Sisip (Aman)' : 'Mahasiswa Beresiko (Sisip)';
  const emptyText = filterParam === 'tidak_sisip' 
    ? 'Tidak ada mahasiswa yang aman pada batch ini.' 
    : 'Tidak ada mahasiswa yang ditandai beresiko pada batch ini.';

  const handleDownloadPDF = () => {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text(`Arsip Laporan Prediksi - Batch ${batch.batch_name}`, 14, 22);
    
    doc.setFontSize(11);
    doc.setTextColor(100);
    doc.text(`Total Diproses: ${batch.total_records} | Mahasiswa Berisiko: ${batch.at_risk} | Persentase Sisip: ${sisipRate}%`, 14, 30);
    doc.text(`Tanggal Upload: ${batch.date_uploaded}`, 14, 36);

    const tableData = flaggedStudents.map(student => {
       const details = student.details ? JSON.parse(student.details) : {};
       return [
         student.nim,
         details.nama || '-',
         details.prodi || '-',
         student.prediction
       ];
    });

    if (tableData.length === 0) {
      tableData.push(['-', '-', '-', 'Tidak ada mahasiswa di kategori ini']);
    }

    autoTable(doc, {
      startY: 45,
      head: [['NIM', 'Nama Mahasiswa', 'Prodi', 'Prediksi']],
      body: tableData,
      theme: 'grid',
      headStyles: { fillColor: [128, 0, 0] }
    });

    doc.save(`Arsip_Prediksi_${batch.batch_name}.pdf`);
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-background relative z-10">
        <Header 
          title="Detail Arsip Batch" 
          subtitle="Meninjau hasil prediksi historis dari sesi sebelumnya." 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-7xl mx-auto mb-6">
            <Link to="/history" className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-primary transition-colors bg-white px-4 py-2 rounded-lg border border-border shadow-sm">
              <ArrowLeft className="h-4 w-4 mr-2" /> Kembali ke Log Riwayat
            </Link>
          </div>

          {/* Batch Metadata Header */}
          <div className="max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden mb-8 p-6 lg:p-8 flex flex-col lg:flex-row justify-between items-start lg:items-center">
            <div>
              <h2 className="text-2xl font-bold text-secondary flex items-center mb-2">
                <Archive className="h-6 w-6 mr-2 text-primary" />
                Batch {batch.batch_name}
              </h2>
              <p className="text-sm text-gray-500">Diproses pada <span className="font-medium text-secondary">{batch.date_uploaded}</span> oleh Staf Admin</p>
            </div>
            
            <div className="mt-4 lg:mt-0 flex gap-4">
              <div className="bg-gray-50 border border-border rounded-xl px-6 py-4 text-center">
                <p className="text-xs text-gray-500 uppercase font-semibold mb-1">Total Data</p>
                <p className="text-2xl font-bold text-secondary">{batch.total_records}</p>
              </div>
              <div className="bg-red-50 border border-red-100 rounded-xl px-6 py-4 text-center">
                <p className="text-xs text-red-800 uppercase font-semibold mb-1">Beresiko</p>
                <p className="text-2xl font-bold text-red-600">{batch.at_risk}</p>
              </div>
              <div className="bg-red-50 border border-red-100 rounded-xl px-6 py-4 text-center">
                <p className="text-xs text-red-800 uppercase font-semibold mb-1">Persentase Sisip</p>
                <p className="text-2xl font-bold text-red-600">{sisipRate}%</p>
              </div>
            </div>
          </div>

          {/* Read-Only Prediction Table Container */}
          <div className="w-full max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden">
            <div className="px-6 py-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gray-50/50">
              <div>
                <h2 className="text-lg font-bold text-secondary flex items-center">
                  <ClipboardList className="h-5 w-5 mr-2 text-primary" />
                  {displayTitle} (Catatan Historis)
                </h2>
              </div>
              
              <button onClick={handleDownloadPDF} className="px-5 py-2.5 bg-white text-secondary font-bold border border-border rounded-lg hover:bg-gray-50 transition-colors shadow-sm whitespace-nowrap flex items-center">
                <Download className="h-4 w-4 mr-2" />
                Unduh Ulang Laporan PDF
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-border">
                  <tr>
                    <th scope="col" className="px-6 py-4 font-semibold w-1/4">NIM</th>
                    <th scope="col" className="px-6 py-4 font-semibold w-1/4">Nama Mahasiswa</th>
                    <th scope="col" className="px-6 py-4 font-semibold w-1/4">IPK Semester 3</th>
                    <th scope="col" className="px-6 py-4 font-semibold text-right w-1/4">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {flaggedStudents.map((student, idx) => {
                    const details = student.details ? JSON.parse(student.details) : {};
                    return (
                    <tr key={idx} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}>
                      <td className="px-6 py-4 font-medium text-secondary">{student.nim}</td>
                      <td className="px-6 py-4">{details.nama || '-'}</td>
                      <td className="px-6 py-4">
                        <span className="bg-gray-100 text-secondary text-xs font-bold px-2 py-1 rounded">
                          {details.ipk3 ? details.ipk3.toFixed(2) : '-'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link to={`/detail/${student.nim}`} className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-primary bg-primary/10 border border-primary/20 rounded-md hover:bg-primary/20 transition-colors">
                          Lihat Detail
                        </Link>
                      </td>
                    </tr>
                    );
                  })}
                  {flaggedStudents.length === 0 && (
                    <tr className="bg-white">
                      <td colSpan="3" className="px-6 py-4 text-center text-gray-500">{emptyText}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            
            <div className="px-6 py-4 bg-gray-50 border-t border-border flex justify-center">
              <p className="text-xs text-gray-400 italic">Ini adalah cuplikan arsip (hanya baca). Data tidak dapat diubah.</p>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default DetailBatch;
