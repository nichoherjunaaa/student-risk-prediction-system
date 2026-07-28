import React, { useState, useEffect } from 'react';
import { TrendingUp, Activity, List, CheckCircle, XCircle } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { Link } from 'react-router-dom';
import axios from 'axios';

const History = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const response = await axios.get('http://localhost:5000/api/history');
        setBatches(response.data.batches);
      } catch (error) {
        console.error("Failed to fetch history", error);
      }
      setLoading(false);
    };
    fetchHistory();
  }, []);

  const totalBatches = batches.length;
  const totalRecords = batches.reduce((acc, curr) => acc + curr.total_records, 0);

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-background relative z-10">
        <Header 
          title="Riwayat & Analitik" 
          subtitle="Tinjau batch prediksi sebelumnya dan lacak performa historis." 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8 max-w-7xl mx-auto">
            
            {/* Card 1: Batch Comparison */}
            <div className="bg-surface rounded-2xl p-6 border border-border shadow-sm flex flex-col h-64">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-secondary flex items-center">
                  <TrendingUp className="h-5 w-5 mr-2 text-primary" />
                  Tren Beresiko (3 Batch Terakhir)
                </h3>
                <span className="text-xs font-medium bg-gray-100 text-gray-600 px-2 py-1 rounded-md">2026</span>
              </div>
              
              <div className="flex-1 flex flex-col justify-end space-y-4">
                {batches.slice(0, 3).map((batch, index) => {
                  const riskPercentage = batch.total_records > 0 ? Math.round((batch.at_risk / batch.total_records) * 100) : 0;
                  return (
                    <div key={index} className="flex items-center">
                      <span className="w-24 text-sm text-gray-500 font-medium truncate">{batch.batch_name}</span>
                      <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden mx-3">
                        <div className={`h-full rounded-full ${index === 0 ? 'bg-primary' : (index === 1 ? 'bg-primary/70' : 'bg-primary/40')}`} style={{ width: `${riskPercentage}%` }}></div>
                      </div>
                      <span className="text-sm font-bold text-secondary w-8 text-right">{riskPercentage}%</span>
                    </div>
                  );
                })}
                {batches.length === 0 && !loading && (
                   <div className="text-sm text-gray-400">Belum ada batch yang diproses.</div>
                )}
              </div>
            </div>

            {/* Card 2: Overall System Usage */}
            <div className="bg-surface rounded-2xl p-6 border border-border shadow-sm flex flex-col h-64">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-bold text-secondary flex items-center">
                  <Activity className="h-5 w-5 mr-2 text-blue-600" />
                  Analitik Penggunaan Sistem
                </h3>
                <span className="text-xs font-medium bg-blue-50 text-blue-600 px-2 py-1 rounded-md">Semua Waktu</span>
              </div>
              
              <div className="flex-1 flex items-center justify-around">
                <div className="text-center">
                  <div className="h-20 w-20 rounded-full border-4 border-gray-100 flex items-center justify-center mx-auto mb-3">
                    <span className="text-2xl font-bold text-secondary">{totalBatches}</span>
                  </div>
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Total Batch</p>
                </div>
                <div className="text-center">
                  <div className="h-20 w-20 rounded-full border-4 border-blue-100 flex items-center justify-center mx-auto mb-3 relative">
                    <svg className="absolute inset-0 h-full w-full transform -rotate-90 text-blue-500" viewBox="0 0 36 36">
                      <path strokeDasharray="75, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round"></path>
                    </svg>
                    <span className="text-2xl font-bold text-blue-600">{totalRecords > 1000 ? (totalRecords/1000).toFixed(1) + 'k' : totalRecords}</span>
                  </div>
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Data Diproses</p>
                </div>
              </div>
            </div>

          </div>

          {/* History Logs Table */}
          <div className="w-full max-w-7xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden">
            <div className="px-6 py-5 border-b border-border bg-gray-50/50">
              <h2 className="text-lg font-bold text-secondary flex items-center">
                <List className="h-5 w-5 mr-2 text-primary" />
                Log Prediksi
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-border">
                  <tr>
                    <th scope="col" className="px-6 py-4 font-semibold">ID Batch</th>
                    <th scope="col" className="px-6 py-4 font-semibold">Tanggal Unggah</th>
                    <th scope="col" className="px-6 py-4 font-semibold">Total Data</th>
                    <th scope="col" className="px-6 py-4 font-semibold">Status Sistem</th>
                    <th scope="col" className="px-6 py-4 font-semibold text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {loading ? (
                    <tr>
                      <td colSpan="5" className="px-6 py-4 text-center">Memuat riwayat...</td>
                    </tr>
                  ) : batches.map((batch) => (
                    <tr key={batch.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 font-medium text-secondary">{batch.batch_name}</td>
                      <td className="px-6 py-4">{batch.date_uploaded}</td>
                      <td className="px-6 py-4">{batch.total_records} Mahasiswa</td>
                      <td className="px-6 py-4">
                        {batch.status === 'Processed' ? (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold bg-green-100 text-green-800 border border-green-200">
                            <CheckCircle className="h-3 w-3 mr-1" /> Diproses
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold bg-red-100 text-red-800 border border-red-200">
                            <XCircle className="h-3 w-3 mr-1" /> Gagal
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <Link to={`/batch/${batch.id}`} className="inline-flex items-center px-3 py-1.5 text-xs font-bold text-primary bg-white border border-border rounded-md hover:bg-gray-50 hover:text-primary-dark transition-colors shadow-sm">
                          Tinjau Ulang Batch
                        </Link>
                      </td>
                    </tr>
                  ))}
                  {batches.length === 0 && !loading && (
                    <tr>
                      <td colSpan="5" className="px-6 py-4 text-center">Log prediksi tidak ditemukan.</td>
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

export default History;
