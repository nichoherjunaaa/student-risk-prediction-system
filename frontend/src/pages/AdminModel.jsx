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
import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import { PRODI_LIST } from "../lib/prodi";
import axios from "axios";

// Saklar tampilan hyperparameter (Max Epochs, Batch Size, Learning Rate,
// Dropout Rate, Validation Split). Disembunyikan sementara: nilainya masih
// dikirim ke /api/train dari state di bawah, tetapi belum disimpan ke tabel
// model_registry sehingga setelan tiap model belum bisa ditelusuri.
// Lihat docs/AUDIT-PIPELINE-PREDIKSI.md — requirement "parameter yang dipilih apa".
// Ubah ke true untuk menampilkannya kembali.
const SHOW_HYPERPARAMS = false;

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
  const [learningRate, setLearningRate] = useState(0.001);
  const [dropoutRate, setDropoutRate] = useState(0.3);
  const [valSplit, setValSplit] = useState(0.2);

  // State Manajemen Registri Riwayat Model
  const [modelHistory, setModelHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [modelMetrics, setModelMetrics] = useState(null);

  useEffect(() => {
    fetchModelHistory();
  }, []);

  const fetchModelHistory = async () => {
    setHistoryLoading(true);
    try {
      const response = await axios.get("/api/models");
      setModelHistory(response.data);
    } catch (err) {
      console.error("Gagal mengambil data registri model:", err);
    }
    setHistoryLoading(false);
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
    formData.append("learning_rate", learningRate);
    formData.append("dropout_rate", dropoutRate);
    formData.append("val_split", valSplit);

    try {
      const response = await axios.post(
        "/api/train",
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
      await axios.post(`/api/models/${modelId}/activate`);
      fetchModelHistory();
    } catch (err) {
      setErrorMessage(
        err.response?.data?.error ||
          "Gagal mengaktifkan model untuk program studi ini.",
      );
      setShowErrorModal(true);
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
          title="Master Model"
          subtitle="Latih model per program studi dan tentukan model yang dipakai untuk prediksi."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto">
          {/* Form Unggah & Latih Ulang */}
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
              <Cpu className="text-primary" /> Latih Model Baru
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Tentukan Program Studi sasaran, lalu unggah berkas data latih hasil
              dari menu{" "}
              <Link
                to="/admin/preprocessing"
                className="font-semibold text-primary hover:underline"
              >
                Preprocessing Data
              </Link>{" "}
              untuk melatih kecerdasan buatan.
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
                  {PRODI_LIST.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Tahun Angkatan Latih
                </label>
                <input
                  type="text"
                  placeholder="Contoh: 2020, 2021"
                  value={angkatan}
                  onChange={(e) => setAngkatan(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                />
              </div>

              {SHOW_HYPERPARAMS && (
                <>
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

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Learning Rate
                    </label>
                    <input
                      type="number"
                      step="0.0001"
                      min="0.0001"
                      max="0.1"
                      value={learningRate}
                      onChange={(e) => setLearningRate(e.target.value)}
                      className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Dropout Rate
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="0.8"
                      value={dropoutRate}
                      onChange={(e) => setDropoutRate(e.target.value)}
                      className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Validation Split
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      min="0.1"
                      max="0.5"
                      value={valSplit}
                      onChange={(e) => setValSplit(e.target.value)}
                      className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                    />
                  </div>
                </>
              )}
            </div>

            {/* items-end: sisi bawah tombol sejajar dengan sisi bawah kotak
                unggah, tanpa memaksa tombol setinggi kotaknya. */}
            <div className="flex flex-col md:flex-row md:items-end gap-4">
              <label className="w-full md:w-auto flex-1 flex flex-col items-center justify-center px-4 py-6 bg-background rounded-xl border-2 border-dashed border-gray-300 cursor-pointer hover:border-primary transition">
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

              <Button
                onClick={handleTrain}
                disabled={loading}
                size="lg"
                className="w-full md:w-auto shrink-0"
              >
                {loading ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : (
                  <Database size={18} />
                )}
                Latih Model
              </Button>
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
              <BarChart2 className="text-accent" /> Registri Model
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Pilih satu model aktif untuk tiap program studi. Model aktif itulah
              yang dipakai saat dosen menjalankan prediksi.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-gray-50 text-xs font-semibold text-gray-500 uppercase">
                    <th scope="col" className="p-3">Nama Versi Model</th>
                    <th scope="col" className="p-3">Program Studi</th>
                    <th scope="col" className="p-3">Waktu Dilatih</th>
                    <th scope="col" className="p-3">Akurasi</th>
                    <th scope="col" className="p-3">Loss</th>
                    <th scope="col" className="p-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-border">
                  {historyLoading ? (
                    <tr>
                      <td colSpan="6" className="p-4 text-center text-gray-500">
                        Memuat registri model...
                      </td>
                    </tr>
                  ) : modelHistory.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="p-4 text-center text-gray-500">
                        Belum ada model yang tersimpan. Latih model pertama Anda di
                        panel atas.
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
                              <Star size={12} fill="currentColor" /> Model Aktif
                            </span>
                          ) : (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleActivateModel(model.id)}
                              aria-label={`Aktifkan model ${model.version_name}`}
                            >
                              Aktifkan
                            </Button>
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
              Melatih model, mohon tunggu...
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
                Model Berhasil Dilatih
              </h3>
              <p className="text-gray-600 mb-4 text-sm">
                Model sudah tersimpan di registri. Aktifkan lewat tabel di bawah
                agar dipakai untuk prediksi.
              </p>
              {modelMetrics && (
                <div className="bg-background p-3 rounded-xl border border-border w-full mb-6 grid grid-cols-2 text-left gap-2">
                  <div>
                    <span className="text-xs text-gray-500">
                      Akurasi Validasi:
                    </span>
                    <p className="text-md font-bold text-green-600">
                      {(modelMetrics.accuracy * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">
                      Tingkat Kesalahan (Loss):
                    </span>
                    <p className="text-md font-bold text-red-500">
                      {modelMetrics.loss.toFixed(4)}
                    </p>
                  </div>
                </div>
              )}
              <Button size="lg" block onClick={() => setShowSuccessModal(false)}>
                Tutup
              </Button>
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
                Proses Dihentikan
              </h3>
              <p className="text-gray-600 mb-6 text-sm">{errorMessage}</p>
              <Button variant="danger" size="lg" block onClick={() => setShowErrorModal(false)}>
                Tutup
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminModel;
