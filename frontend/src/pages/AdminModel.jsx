import React, { useState, useEffect } from "react";
import {
  Upload as UploadIcon,
  Database,
  Cpu,
  CheckCircle,
  AlertTriangle,
  Loader2,
  BarChart2,
  Star,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import axios from "axios";

const AdminModel = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isTraining, setIsTraining] = useState(false);
  const [trainProgress, setTrainProgress] = useState(0);

  // State Saringan Utama Pilihan Prodi Admin
  const [prodi, setProdi] = useState("");
  const [angkatan, setAngkatan] = useState("");

  // State Hyperparameter Eksperimen Model
  const [epochs, setEpochs] = useState(10);
  const [batchSize, setBatchSize] = useState(32);

  // State Manajemen Registri Riwayat Model
  const [modelHistory, setModelHistory] = useState([]);
  const [modelMetrics, setModelMetrics] = useState(null);

  useEffect(() => {
    fetchModelHistory();
  }, []);

  const fetchModelHistory = async () => {
    try {
      const response = await axios.get("http://localhost:5000/api/models");
      setModelHistory(response.data);
    } catch (err) {
      console.error("Gagal mengambil data registri model:", err);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError("");
    }
  };

  const handleTrain = async () => {
    if (!prodi) {
      setError(
        "Silakan tentukan Target Program Studi terlebih dahulu sebelum melatih model.",
      );
      return;
    }
    if (!file) {
      setError(
        "Silakan tentukan berkas Excel data latih historis terlebih dahulu.",
      );
      return;
    }
    setLoading(true);
    setIsTraining(true);
    setTrainProgress(5);

    const progressInterval = setInterval(() => {
      setTrainProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + Math.floor(Math.random() * 10) + 5;
      });
    }, 500);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("prodi", prodi);
    formData.append("angkatan", angkatan);
    formData.append("epochs", epochs);
    formData.append("batch_size", batchSize);

    try {
      const response = await axios.post(
        "http://localhost:5000/api/train",
        formData,
      );
      clearInterval(progressInterval);
      setTrainProgress(100);

      setTimeout(() => {
        setIsTraining(false);
        setTrainProgress(0);
        setModelMetrics(response.data.metrics);
        setShowSuccessModal(true);
        setFile(null);
        fetchModelHistory();
      }, 600);
    } catch (err) {
      clearInterval(progressInterval);
      setTrainProgress(100);
      setTimeout(() => {
        setIsTraining(false);
        setTrainProgress(0);
        setErrorMessage(
          err.response?.data?.error ||
            "Gagal mengeksekusi pelatihan arsitektur CNN.",
        );
        setShowErrorModal(true);
      }, 600);
    }
    setLoading(false);
  };

  const handleActivateModel = async (modelId) => {
    try {
      await axios.post(`http://localhost:5000/api/models/${modelId}/activate`);
      fetchModelHistory();
    } catch (err) {
      alert("Gagal mengunci model aktif untuk prodi ini.");
    }
  };
  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Panel Utama Admin: Manajemen Model Sistem"
        />

        <main className="p-6 space-y-6 max-w-7xl w-full mx-auto">
          {/* Form Unggah & Latih Ulang */}
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
              <Cpu className="text-primary" /> Pembuatan & Eksperimen Model Baru
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Silakan tentukan Program Studi sasaran, lalu unggah rekap
              spreadsheet berkas akademis historis gabungan untuk melatih
              kecerdasan buatan.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Target Program Studi
                </label>
                <select
                  value={prodi}
                  onChange={(e) => setProdi(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  <option value="">-- Semua Prodi --</option>
                  <option value="Informatika">Informatika</option>
                  <option value="Matematika">Matematika</option>
                  <option value="Teknik Mesin">Teknik Mesin</option>
                  <option value="Teknik Elektro">Teknik Elektro</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Tahun Angkatan Latih
                </label>
                <select
                  value={angkatan}
                  onChange={(e) => setAngkatan(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  <option value="">-- Semua Angkatan --</option>
                  <option value="2020">2020</option>
                  <option value="2021">2021</option>
                  <option value="2022">2022</option>
                  <option value="2023">2023</option>
                  <option value="2024">2024</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Max Epochs
                </label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={epochs}
                  onChange={(e) => setEpochs(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Batch Size
                </label>
                <select
                  value={batchSize}
                  onChange={(e) => setBatchSize(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  <option value="8">8</option>
                  <option value="16">16</option>
                  <option value="32">32</option>
                  <option value="64">64</option>
                  <option value="128">128</option>
                </select>
              </div>
            </div>

            <div className="flex flex-col md:flex-row items-center gap-4">
              <label className="w-full md:w-auto flex-1 flex flex-col items-center px-4 py-6 bg-background rounded-xl border-2 border-dashed border-gray-300 cursor-pointer hover:border-primary transition">
                <UploadIcon className="text-gray-400 mb-2" />
                <span className="text-sm font-medium text-gray-600">
                  {file ? file.name : "Pilih Berkas Excel Data Latih (.xlsx)"}
                </span>
                <input
                  type="file"
                  accept=".xlsx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>

              <button
                onClick={handleTrain}
                disabled={loading}
                className="w-full md:w-auto px-6 py-4 bg-primary text-white font-bold rounded-xl hover:bg-primary-dark transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 className="animate-spin" /> : <Database />}{" "}
                Eksperimen Latih Model
              </button>
            </div>
            {error && (
              <p className="text-red-500 text-sm mt-2 flex items-center gap-1">
                <AlertTriangle size={16} />
                {error}
              </p>
            )}
          </div>

          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border min-h-[400px]">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-4">
              <BarChart2 className="text-accent" /> Hasil Modeling & Kontrol
              Akses User
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Tentukan model terbaik untuk masing-masing program studi yang akan
              dikunci untuk melayani proses prediksi di sisi akun Dosen.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-gray-50 text-xs font-semibold text-gray-500 uppercase">
                    <th className="p-3">Nama/Versi Versi Model</th>
                    <th className="p-3">Target Prodi</th>
                    <th className="p-3">Waktu di Bangun Model</th>
                    <th className="p-3">Skor Akurasi</th>
                    <th className="p-3">Skor Loss</th>
                    <th className="p-3 text-center">
                      Status Penggunaan Sistem
                    </th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-border">
                  {modelHistory.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="p-4 text-center text-gray-400">
                        Belum ada riwayat model hasil eksperimen prodi yang
                        tersimpan.
                      </td>
                    </tr>
                  ) : (
                    modelHistory.map((model) => (
                      <tr key={model.id} className="hover:bg-gray-50/50">
                        <td className="p-3 font-mono text-secondary text-xs">
                          {model.version_name}
                        </td>
                        <td className="p-3 font-semibold text-primary text-xs capitalize">
                          {model.prodi && model.prodi !== "Global"
                            ? model.prodi
                            : model.version_name
                                .split("_")[2]
                                ?.replace("-", " ")}
                        </td>
                        <td className="p-3 text-gray-500 text-xs">
                          {model.trained_at}
                        </td>
                        <td className="p-3 text-green-600 font-semibold">
                          {(model.accuracy * 100).toFixed(1)}%
                        </td>
                        <td className="p-3 text-red-500 font-semibold">
                          {model.loss.toFixed(3)}
                        </td>
                        <td className="p-3 text-center">
                          {model.is_active ? (
                            <span className="bg-green-100 text-green-800 text-xs font-bold px-3 py-1.5 rounded-full inline-flex items-center gap-1">
                              <Star size={12} fill="currentColor" /> Dikunci
                              untuk Prediksi User
                            </span>
                          ) : (
                            <button
                              onClick={() => handleActivateModel(model.id)}
                              className="text-xs bg-white hover:bg-primary hover:text-white px-3 py-1.5 rounded-lg border border-gray-300 font-medium transition shadow-sm"
                            >
                              Gunakan Model Ini
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>

      {/* Progress Modal */}
      {isTraining && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border px-8 py-6 flex flex-col items-center w-full max-w-md">
            <h3 className="text-lg font-bold text-secondary mb-4">
              Menyaring Data & Melatih Model CNN per Prodi...
            </h3>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden border border-gray-300">
              <div
                className="bg-primary h-4 rounded-full transition-all duration-300"
                style={{ width: `${trainProgress}%` }}
              ></div>
            </div>
            <p className="text-sm font-medium text-gray-600">
              {trainProgress}% Selesai
            </p>
          </div>
        </div>
      )}

      {/* Success Modal */}
      {showSuccessModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6">
            <div className="flex flex-col items-center text-center">
              <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center mb-4 border border-green-200">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-bold text-secondary mb-2">
                Eksperimen Prodi Berhasil!
              </h3>
              <p className="text-gray-600 mb-4 text-sm">
                Model spesifik program studi Anda telah dicatatkan secara aman.
              </p>
              {modelMetrics && (
                <div className="bg-background p-3 rounded-xl border border-border w-full mb-6 grid grid-cols-2 text-left gap-2">
                  <div>
                    <span className="text-xs text-gray-400">
                      Akurasi Validasi:
                    </span>
                    <p className="text-md font-bold text-green-600">
                      {(modelMetrics.accuracy * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-gray-400">
                      Tingkat Kesalahan (Loss):
                    </span>
                    <p className="text-md font-bold text-red-500">
                      {modelMetrics.loss.toFixed(4)}
                    </p>
                  </div>
                </div>
              )}
              <button
                onClick={() => setShowSuccessModal(false)}
                className="w-full py-2.5 bg-primary text-white font-semibold rounded-lg hover:bg-primary-dark transition shadow-sm"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Modal */}
      {showErrorModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6">
            <div className="flex flex-col items-center text-center">
              <div className="h-16 w-16 bg-red-100 rounded-full flex items-center justify-center mb-4 border border-red-200">
                <AlertTriangle className="h-8 w-8 text-red-600" />
              </div>
              <h3 className="text-xl font-bold text-secondary mb-2">
                Pelatihan Dihentikan
              </h3>
              <p className="text-gray-600 mb-6 text-sm">{errorMessage}</p>
              <button
                onClick={() => setShowErrorModal(false)}
                className="w-full py-2.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition shadow-sm"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminModel;
