import React, { useState, useEffect, useRef } from 'react';
import { Users, AlertTriangle, TrendingUp, ClipboardList, Download } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import Chart from 'chart.js/auto';
import axios from 'axios';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

const Results = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const [data, setData] = useState(() => {
    if (location.state?.predictionData) {
      localStorage.setItem('lastPrediction', JSON.stringify(location.state.predictionData));
      return location.state.predictionData;
    }
    const saved = localStorage.getItem('lastPrediction');
    return saved ? JSON.parse(saved) : { total: 0, atRisk: 0, safe: 0, results: [], batch_id: null };
  });
  const navigate = useNavigate();
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const prodiToFilter = location.state?.prodi || data.prodi || localStorage.getItem('lastProdi') || 'Unknown';
  const [selectedProdi, setSelectedProdi] = useState(prodiToFilter);

  const PRODI_LIST = ['Informatika', 'Teknik Elektro', 'Matematika', 'Teknik Mesin'];

  useEffect(() => {
    localStorage.setItem('lastProdi', selectedProdi);
  }, [selectedProdi]);

  useEffect(() => {
    // Fetch real history for the chart
    const fetchHistoryAndDrawChart = async () => {
      try {
        const response = await axios.get('/api/history');
        
        // Filter by selected prodi
        const batches = response.data.batches.filter(b => b.prodi === selectedProdi);
        
        // Group by angkatan, taking the most recent upload (first in the descending array)
        const angkatanMap = new Map();
        for (const b of batches) {
          if (!angkatanMap.has(b.angkatan) && b.angkatan) {
            angkatanMap.set(b.angkatan, b);
          }
        }
        
        // Sort angkatan ascending
        const sortedAngkatan = Array.from(angkatanMap.keys()).sort();
        
        let labels = [];
        let atRiskData = [];
        let safeData = [];
        let batchIds = [];
        
        if (sortedAngkatan.length > 0) {
          labels = sortedAngkatan;
          for (const ang of sortedAngkatan) {
            const b = angkatanMap.get(ang);
            atRiskData.push(b.at_risk);
            safeData.push(b.safe);
            batchIds.push(b.id);
          }
        } else {
          // Fallback
          labels = [data.angkatan || 'Current'];
          atRiskData = [data.atRisk];
          safeData = [data.safe];
          batchIds = [data.batch_id];
        }

        if (chartRef.current) {
          if (chartInstance.current) {
            chartInstance.current.destroy();
          }
          
          const ctx = chartRef.current.getContext('2d');

          chartInstance.current = new Chart(ctx, {
            type: 'bar',
            data: {
              labels: labels,
              datasets: [
                {
                  label: 'Sisip',
                  data: atRiskData,
                  backgroundColor: 'rgba(128, 0, 0, 0.8)',
                  borderColor: '#800000',
                  borderWidth: 1,
                  barPercentage: 1.0,
                  categoryPercentage: 0.8
                },
                {
                  label: 'Tidak Sisip',
                  data: safeData,
                  backgroundColor: 'rgba(37, 99, 235, 0.8)',
                  borderColor: '#2563eb',
                  borderWidth: 1,
                  barPercentage: 1.0,
                  categoryPercentage: 0.8
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                title: {
                  display: true,
                  text: `Distribusi hasil prediksi prodi ${selectedProdi} tiap angkatan`,
                  font: { size: 16 }
                },
                tooltip: {
                  titleFont: { size: 18 },
                  bodyFont: { size: 16, weight: 'bold' },
                  padding: 12
                }
              },
              onClick: (e, elements) => {
                if (elements.length > 0) {
                  const index = elements[0].index;
                  const datasetIndex = elements[0].datasetIndex;
                  const batchId = batchIds[index];
                  const filter = datasetIndex === 0 ? 'sisip' : 'tidak_sisip';
                  if (batchId) {
                    navigate(`/batch/${batchId}?filter=${filter}`);
                  }
                }
              }
            }
          });
        }
      } catch (error) {
        console.error("Failed to fetch history for chart", error);
      }
    };

    fetchHistoryAndDrawChart();
    
  }, [data, selectedProdi, navigate]);

  const sisipRate = data.total > 0 ? ((data.atRisk / data.total) * 100).toFixed(1) : 0;
  const atRiskStudents = data.results.filter(r => r.isRisk);

  const handleDownloadPDF = () => {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text('Laporan Prediksi Mahasiswa Berpotensi Sisip', 14, 22);
    
    doc.setFontSize(11);
    doc.setTextColor(100);
    doc.text(`Total Diproses: ${data.total} | Berpotensi Sisip: ${data.atRisk} | Persentase Sisip: ${sisipRate}%`, 14, 30);
    doc.text(`Tanggal: ${new Date().toLocaleDateString()}`, 14, 36);

    const tableData = atRiskStudents.map(student => [
      student.nim,
      student.nama || '-',
      student.prodi || '-',
      student.prediction
    ]);

    if (tableData.length === 0) {
      tableData.push(['-', '-', '-', 'Tidak ada mahasiswa berisiko']);
    }

    autoTable(doc, {
      startY: 45,
      head: [['NIM', 'Nama Mahasiswa', 'Prodi', 'Prediksi']],
      body: tableData,
      theme: 'grid',
      headStyles: { fillColor: [128, 0, 0] } // Primary color (maroon)
    });

    const timestamp = new Date().getTime();
    doc.save(`Laporan_Prediksi_Sisip_${timestamp}.pdf`);
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-background relative z-10">
        <Header 
          title="Hasil Prediksi" 
          subtitle="Tinjau mahasiswa yang ditandai 'Beresiko' (Tidak Lolos Sisip Program)." 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 max-w-7xl mx-auto">
            <div className="bg-surface rounded-2xl p-6 border border-border shadow-sm flex items-center">
              <div className="h-12 w-12 rounded-full bg-blue-50 flex items-center justify-center mr-4 border border-blue-100">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">Total Diproses</p>
                <h3 className="text-2xl font-bold text-secondary mt-1">{data.total} <span className="text-sm font-normal text-gray-400">mahasiswa</span></h3>
              </div>
            </div>
            
            <div className="bg-surface rounded-2xl p-6 border border-border shadow-sm flex items-center">
              <div className="h-12 w-12 rounded-full bg-red-50 flex items-center justify-center mr-4 border border-red-100">
                <AlertTriangle className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">Ditandai "Beresiko"</p>
                <h3 className="text-2xl font-bold text-red-600 mt-1">{data.atRisk} <span className="text-sm font-normal text-gray-400">mahasiswa</span></h3>
              </div>
            </div>
            
            <div className="bg-surface rounded-2xl p-6 border border-border shadow-sm flex items-center">
              <div className="h-12 w-12 rounded-full bg-red-50 flex items-center justify-center mr-4 border border-red-100">
                <TrendingUp className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500 uppercase tracking-wide">Persentase Berpotensi Sisip</p>
                <h3 className="text-2xl font-bold text-red-600 mt-1">{sisipRate}%</h3>
              </div>
            </div>
          </div>

          <div className="flex justify-end mb-4 max-w-7xl mx-auto">
             <button onClick={handleDownloadPDF} className="px-5 py-2.5 bg-primary text-white font-bold rounded-lg hover:bg-primary-dark transition-colors shadow-sm flex items-center">
                <Download className="h-4 w-4 mr-2" />
                Unduh Laporan Keseluruhan (PDF)
              </button>
          </div>

          <div className="mb-8 w-full max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border p-6 relative overflow-hidden">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 relative z-10">
              <div>
                <h2 className="text-xl font-bold text-secondary flex items-center tracking-tight">
                  <TrendingUp className="h-6 w-6 mr-2 text-primary" />
                  Distribusi Tiap Angkatan
                </h2>
                <p className="text-sm text-gray-500 mt-1 ml-8">Klik pada batang grafik untuk melihat detail mahasiswa di angkatan tersebut.</p>
              </div>
              {/* Prodi Filter Buttons */}
              <div className="flex flex-wrap gap-2 mt-3 sm:mt-0">
                {PRODI_LIST.map(p => (
                  <button
                    key={p}
                    onClick={() => setSelectedProdi(p)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${
                      selectedProdi === p
                        ? 'bg-primary text-white border-primary shadow-sm'
                        : 'bg-white text-gray-600 border-border hover:border-primary hover:text-primary'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <div className="relative h-[450px] w-full z-10 overflow-x-auto no-scrollbar">
              <div style={{ minWidth: '700px', height: '100%' }}>
                <canvas ref={chartRef}></canvas>
              </div>
            </div>
          </div>

          {/* Daftar mahasiswa yang ditandai beresiko pada prediksi ini */}
          <div className="w-full max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden mb-8">
            <div className="px-6 py-5 border-b border-border bg-gray-50/50">
              <h2 className="text-lg font-bold text-secondary flex items-center">
                <ClipboardList className="h-5 w-5 mr-2 text-primary" />
                Mahasiswa Ditandai Beresiko ({atRiskStudents.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-border">
                  <tr>
                    <th className="px-6 py-4 font-semibold">NIM</th>
                    <th className="px-6 py-4 font-semibold">Nama Mahasiswa</th>
                    <th className="px-6 py-4 font-semibold">Prodi</th>
                    <th className="px-6 py-4 font-semibold">Prediksi</th>
                    <th className="px-6 py-4 font-semibold text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {atRiskStudents.map((s, idx) => (
                    <tr key={s.nim || idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                      <td className="px-6 py-4 font-medium text-secondary">{s.nim}</td>
                      <td className="px-6 py-4">{s.nama || '-'}</td>
                      <td className="px-6 py-4">{s.prodi || '-'}</td>
                      <td className="px-6 py-4">
                        <span className="bg-red-100 text-red-800 text-xs font-bold px-2 py-1 rounded">{s.prediction}</span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link
                          to={data.batch_id ? `/detail/${s.nim}?batch=${data.batch_id}` : `/detail/${s.nim}`}
                          className="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md text-red-700 bg-red-100 border border-red-200 hover:bg-red-200 transition-colors"
                        >
                          Lihat Detail
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {atRiskStudents.length === 0 && (
                    <tr className="bg-white">
                      <td colSpan="5" className="px-6 py-4 text-center text-gray-500">
                        Tidak ada mahasiswa yang ditandai beresiko pada prediksi ini.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Results;
