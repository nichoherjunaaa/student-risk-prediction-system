import React, { useState, useEffect } from 'react';
import { FileSpreadsheet, Upload as UploadIcon, Database, Search, Cpu, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const Upload = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictProgress, setPredictProgress] = useState(0);
  const [isTraining, setIsTraining] = useState(false);
  const [trainProgress, setTrainProgress] = useState(0);
  const [prodi, setProdi] = useState('');
  const [angkatan, setAngkatan] = useState('');
  const navigate = useNavigate();

  const fetchPreview = async (selectedFile, currentProdi, currentAngkatan) => {
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('prodi', currentProdi);
    formData.append('angkatan', currentAngkatan);
    try {
      const response = await axios.post('http://localhost:5000/api/preview', formData);
      setPreviewData(response.data);
    } catch (err) {
      console.error("Preview error:", err);
    }
  };

  useEffect(() => {
    if (file && prodi && angkatan) {
      fetchPreview(file, prodi, angkatan);
    }
  }, [prodi, angkatan]);

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setError('');
      await fetchPreview(selectedFile, prodi, angkatan);
    }
  };

  const handleTrain = async () => {
    if (!file) {
      setError('Silakan pilih file Excel terlebih dahulu.');
      return;
    }
    setLoading(true);
    setIsTraining(true);
    setTrainProgress(5);
    
    const progressInterval = setInterval(() => {
      setTrainProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.floor(Math.random() * 10) + 5;
      });
    }, 500);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('prodi', prodi);
    formData.append('angkatan', angkatan);
    try {
      await axios.post('http://localhost:5000/api/train', formData);
      clearInterval(progressInterval);
      setTrainProgress(100);
      setTimeout(() => {
        setIsTraining(false);
        setTrainProgress(0);
        setShowSuccessModal(true);
      }, 600);
    } catch (err) {
      clearInterval(progressInterval);
      setTrainProgress(100);
      setTimeout(() => {
        setIsTraining(false);
        setTrainProgress(0);
        setErrorMessage(err.response?.data?.error || 'Gagal melatih model.');
        setShowErrorModal(true);
      }, 600);
    }
    setLoading(false);
  };

  const handlePredict = async () => {
    if (!file) {
      setError('Silakan pilih file Excel terlebih dahulu.');
      return;
    }
    setLoading(true);
    setIsPredicting(true);
    setPredictProgress(5);

    const progressInterval = setInterval(() => {
      setPredictProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.floor(Math.random() * 8) + 4;
      });
    }, 400);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('prodi', prodi);
    formData.append('angkatan', angkatan);
    try {
      const response = await axios.post('http://localhost:5000/api/predict', formData);
      clearInterval(progressInterval);
      setPredictProgress(100);
      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        navigate('/results', { state: { predictionData: response.data, prodi } });
      }, 500);
    } catch (err) {
      clearInterval(progressInterval);
      setPredictProgress(100);
      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        setError(err.response?.data?.error || 'Gagal memprediksi. Apakah Anda sudah melatih model terlebih dahulu?');
      }, 500);
    }
    setLoading(false);
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      {isTraining && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border px-8 py-6 flex flex-col items-center w-full max-w-md">
            <h3 className="text-lg font-bold text-secondary mb-4">Sedang Melatih Model...</h3>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden border border-gray-300">
              <div 
                className="bg-primary h-4 rounded-full transition-all duration-300 ease-out flex items-center justify-center"
                style={{ width: `${trainProgress}%` }}
              >
              </div>
            </div>
            <p className="text-sm font-medium text-gray-600">{trainProgress}% Selesai</p>
          </div>
        </div>
      )}

      {isPredicting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border px-8 py-6 flex flex-col items-center w-full max-w-md">
            <h3 className="text-lg font-bold text-secondary mb-4">Sedang Memproses Prediksi...</h3>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden border border-gray-300">
              <div
                className="bg-accent h-4 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${predictProgress}%` }}
              >
              </div>
            </div>
            <p className="text-sm font-medium text-gray-600">{predictProgress}% Selesai</p>
            <p className="text-xs text-gray-400 mt-1">Harap tunggu, ini mungkin memakan waktu.</p>
          </div>
        </div>
      )}

      {showSuccessModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6 transform transition-all duration-300 scale-100">
            <div className="flex flex-col items-center text-center">
              <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center mb-4 border border-green-200">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-bold text-secondary mb-2">Pelatihan Berhasil!</h3>
              <p className="text-gray-600 mb-6">Model berhasil dilatih! Anda sekarang dapat menjalankan prediksi pada data Anda.</p>
              <button 
                onClick={() => setShowSuccessModal(false)}
                className="w-full py-2.5 bg-primary text-white font-semibold rounded-lg hover:bg-primary-dark transition-colors shadow-sm"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {showErrorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6 transform transition-all duration-300 scale-100">
            <div className="flex flex-col items-center text-center">
              <div className="h-16 w-16 bg-red-100 rounded-full flex items-center justify-center mb-4 border border-red-200">
                <AlertTriangle className="h-8 w-8 text-red-600" />
              </div>
              <h3 className="text-xl font-bold text-secondary mb-2">Pelatihan Gagal</h3>
              <p className="text-gray-600 mb-6">{errorMessage}</p>
              <button 
                onClick={() => setShowErrorModal(false)}
                className="w-full py-2.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-colors shadow-sm"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 flex flex-col h-full overflow-hidden bg-background relative z-10">
        <Header 
          title="Unggah Data Excel" 
          subtitle="Impor catatan akademik mahasiswa untuk pemrosesan prediksi." 
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)} 
        />
        
        <div className="flex-1 overflow-y-auto p-8">
          <div className="w-full max-w-4xl mx-auto mb-10">
            {error && (
              <div className="mb-4 p-4 text-red-700 bg-red-100 rounded-lg">
                {error}
              </div>
            )}
            
            <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Program Studi</label>
                <select 
                  className="w-full border border-border rounded-lg px-4 py-2 bg-surface text-secondary focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                  value={prodi}
                  onChange={(e) => setProdi(e.target.value)}
                >
                  <option value="">-- Pilih Program Studi --</option>
                  <option value="Informatika">Informatika</option>
                  <option value="Teknik Elektro">Teknik Elektro</option>
                  <option value="Teknik Mesin">Teknik Mesin</option>
                  <option value="Matematika">Matematika</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Angkatan (Target Prediksi)</label>
                <select 
                  className="w-full border border-border rounded-lg px-4 py-2 bg-surface text-secondary focus:ring-2 focus:ring-primary focus:border-primary outline-none"
                  value={angkatan}
                  onChange={(e) => setAngkatan(e.target.value)}
                >
                  <option value="">Pilih Angkatan...</option>
                  <option value="2020">2020</option>
                  <option value="2021">2021</option>
                  <option value="2022">2022</option>
                  <option value="2023">2023</option>
                  <option value="2024">2024</option>
                </select>
              </div>
            </div>

            <label htmlFor="file-upload" className={`block w-full border-2 border-dashed border-gray-300 rounded-2xl bg-surface p-12 text-center hover:border-primary hover:bg-primary/5 transition-all cursor-pointer group ${(!prodi || !angkatan) ? 'opacity-50 pointer-events-none' : ''}`}>
              <div className="mx-auto h-20 w-20 bg-gray-50 rounded-full flex items-center justify-center mb-6 group-hover:bg-primary/10 transition-colors shadow-sm border border-border group-hover:border-primary/30">
                <FileSpreadsheet className="h-10 w-10 text-gray-400 group-hover:text-primary transition-colors" />
              </div>
              <h3 className="text-xl font-semibold text-secondary mb-2">
                {file ? file.name : "Tarik & Lepas file Excel Anda di sini"}
              </h3>
              <p className="text-gray-500 mb-6">Format yang didukung: .xlsx, .xls</p>
              
              <div className="px-6 py-2.5 bg-primary text-white font-medium rounded-lg hover:bg-primary-dark transition-colors shadow-sm inline-flex items-center">
                <UploadIcon className="h-4 w-4 mr-2" />
                {file ? 'Ubah File' : 'Pilih File'}
              </div>
              {(!prodi || !angkatan) && <p className="mt-4 text-red-500 text-sm">Silakan pilih Prodi dan isi Angkatan terlebih dahulu.</p>}
              <input type="file" id="file-upload" className="hidden" accept=".xlsx, .xls" onChange={handleFileChange} disabled={!prodi || !angkatan} />
            </label>
            
            {file && (
              <div className="mt-6 flex gap-4 justify-center">
                <button onClick={handleTrain} disabled={loading} className="px-6 py-2.5 bg-gray-600 text-white font-medium rounded-lg hover:bg-gray-700 transition-colors shadow-sm disabled:opacity-50">
                  {loading ? 'Memproses...' : 'Latih Model'}
                </button>
              </div>
            )}
          </div>

          <div className="w-full max-w-6xl mx-auto bg-surface rounded-2xl shadow-sm border border-border overflow-hidden">
            <div className="px-6 py-5 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gray-50/50">
              <div>
                <h2 className="text-lg font-bold text-secondary flex items-center">
                  <Database className="h-5 w-5 mr-2 text-primary" />
                  Pratinjau Data
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  {previewData ? `Menampilkan 10 dari ${previewData.total_rows} data` : 'Pratinjau data file'}
                </p>
              </div>
              
              <div className="flex items-center space-x-3">
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <Search className="h-4 w-4" />
                  </div>
                  <input type="text" className="block w-full sm:w-64 pl-10 pr-3 py-2 border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary bg-white" placeholder="Cari berdasarkan ID atau Nama..." />
                </div>
                
                <button onClick={handlePredict} disabled={loading || !file} className="px-4 py-2 bg-accent text-secondary font-bold rounded-lg hover:bg-accent-hover transition-colors shadow-sm whitespace-nowrap flex items-center disabled:opacity-50">
                  {isPredicting ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Memprediksi...</>
                  ) : (
                    <><Cpu className="h-4 w-4 mr-2" /> Jalankan Prediksi</>
                  )}
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              {!previewData ? (
                <div className="p-8 text-center text-gray-500">
                  {file ? 'Memuat pratinjau...' : 'Tidak ada data untuk dipratinjau. Unggah file terlebih dahulu.'}
                </div>
              ) : (
                <table className="w-full text-left text-sm text-gray-600 whitespace-nowrap">
                  <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-border">
                    <tr>
                      {previewData.columns.slice(0, 10).map((col, idx) => (
                        <th key={idx} scope="col" className="px-6 py-4 font-semibold">{col}</th>
                      ))}
                      {previewData.columns.length > 10 && <th className="px-6 py-4 font-semibold">...</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {previewData.data.map((row, idx) => (
                      <tr key={idx} className="hover:bg-gray-50 transition-colors">
                        {previewData.columns.slice(0, 10).map((col, cIdx) => (
                          <td key={cIdx} className="px-6 py-4">{row[col] !== null ? String(row[col]) : ''}</td>
                        ))}
                        {previewData.columns.length > 10 && <td className="px-6 py-4">...</td>}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Upload;
