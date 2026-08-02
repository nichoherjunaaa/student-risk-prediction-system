import React, { useState, useEffect } from "react";
import {
  UploadCloud,
  BarChart2,
  AlertTriangle,
  CheckCircle,
  Loader2,
  FileSpreadsheet,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const Upload = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [previewData, setPreviewData] = useState(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictProgress, setPredictProgress] = useState(0);
  const [prodi, setProdi] = useState("");
  const [angkatan, setAngkatan] = useState("");
  const navigate = useNavigate();

  // Memanggil pratinjau data excel (10 baris pertama) ke backend
  const fetchPreview = async (selectedFile, currentProdi, currentAngkatan) => {
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("prodi", currentProdi);
    formData.append("angkatan", currentAngkatan);
    try {
      const response = await axios.post(
        "http://localhost:5000/api/preview",
        formData,
      );
      setPreviewData(response.data);
    } catch (err) {
      console.error("Preview error:", err);
    }
  };

  useEffect(() => {
    if (file && (prodi || angkatan)) {
      fetchPreview(file, prodi, angkatan);
    }
  }, [prodi, angkatan]);

  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setError("");
      setPreviewData(null);
      await fetchPreview(selectedFile, prodi, angkatan);
    }
  };

  // Fungsi menjalankan prediksi menggunakan model pilihan aktif Admin
  const handlePredict = async () => {
    if (!file) {
      setError("Silakan pilih berkas Excel data mahasiswa terlebih dahulu.");
      return;
    }
    setLoading(true);
    setIsPredicting(true);
    setPredictProgress(5);

    // Animasi progress bar palsu agar UI terasa interaktif saat backend menghitung matriks CNN
    const progressInterval = setInterval(() => {
      setPredictProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + Math.floor(Math.random() * 8) + 4;
      });
    }, 400);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("prodi", prodi);
    formData.append("angkatan", angkatan);

    try {
      const response = await axios.post(
        "http://localhost:5000/api/predict",
        formData,
      );
      clearInterval(progressInterval);
      setPredictProgress(100);

      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        // Mengalihkan halaman ke grafik hasil analisis bawaan proyek
        navigate("/results", {
          state: { predictionData: response.data, prodi },
        });
      }, 500);
    } catch (err) {
      clearInterval(progressInterval);
      setPredictProgress(100);
      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        setError(
          err.response?.data?.error ||
            "Gagal mengeksekusi prediksi pada berkas data baru Anda.",
        );
      }, 500);
    }
    setLoading(false);
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      {/* Sidebar dipanggil dengan peran user/dosen agar menu kelola AI tidak mengintip */}
      <Sidebar
        isOpen={sidebarOpen}
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        role="user"
      />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Analisis Evaluasi: Prediksi Mahasiswa Berpotensi Sisip"
        />

        <main className="p-6 space-y-6 max-w-7xl w-full mx-auto">
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
              <UploadCloud className="text-primary" /> Unggah Berkas Evaluasi
              Baru
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Silakan tentukan parameter filter program studi dan masukkan file
              rekap nilai mahasiswa semester 3 untuk dianalisis oleh kecerdasan
              buatan.
            </p>

            {/* Sektor Filter Dropdown Sesuai Aturan Main Bawaan */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Program Studi
                </label>
                <select
                  value={prodi}
                  onChange={(e) => setProdi(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                >
                  <option value="">-- Semua Program Studi --</option>
                  <option value="Informatika">Informatika</option>
                  <option value="Matematika">Matematika</option>
                  <option value="Teknik Mesin">Teknik Mesin</option>
                  <option value="Teknik Elektro">Teknik Elektro</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Tahun Angkatan
                </label>
                <select
                  value={angkatan}
                  onChange={(e) => setAngkatan(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
                >
                  <option value="">-- Semua Angkatan --</option>
                  <option value="2020">2020</option>
                  <option value="2021">2021</option>
                  <option value="2022">2022</option>
                  <option value="2023">2023</option>
                  <option value="2024">2024</option>
                </select>
              </div>
            </div>

            {/* Sektor Seret Kotak File */}
            <div className="flex flex-col items-center justify-center">
              <label className="w-full flex flex-col items-center px-4 py-8 bg-background rounded-2xl border-2 border-dashed border-gray-300 cursor-pointer hover:border-primary transition text-center mb-4">
                <FileSpreadsheet className="h-10 w-10 text-gray-400 mb-3" />
                <span className="text-sm font-semibold text-gray-600">
                  {file
                    ? file.name
                    : "Seret atau Pilih Berkas Excel Rekap Nilai (.xlsx)"}
                </span>
                <input
                  type="file"
                  accept=".xlsx"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>

              {file && (
                <button
                  onClick={handlePredict}
                  disabled={loading}
                  className="w-full md:w-auto px-8 py-3.5 bg-accent text-white font-bold rounded-xl hover:bg-accent-dark transition disabled:opacity-50 flex items-center justify-center gap-2 shadow-md shadow-accent/20"
                >
                  {loading ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <BarChart2 size={18} />
                  )}{" "}
                  Jalankan Proses Analisis Prediksi
                </button>
              )}
            </div>

            {error && (
              <p className="text-red-500 text-sm mt-4 flex items-center gap-2 font-medium bg-red-50 p-3 rounded-xl border border-red-100">
                <AlertTriangle size={16} />
                {error}
              </p>
            )}
          </div>

          {/* Sektor Pratinjau Tabel Data Excel */}
          {previewData && (
            <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
              <h3 className="text-md font-bold text-secondary mb-1">
                Pratinjau Lembar Kerja Spreadsheet
              </h3>
              <p className="text-xs text-gray-400 mb-4">
                Menampilkan 10 baris teratas dari total{" "}
                <strong>{previewData.total_rows}</strong> rekaman mahasiswa yang
                terdeteksi.
              </p>

              <div className="overflow-x-auto border border-border rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-gray-50 border-b border-border text-gray-500 font-semibold uppercase tracking-wider">
                      {previewData.columns.map((col, idx) => (
                        <th key={idx} className="p-3 whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border text-gray-600">
                    {previewData.data.map((row, rowIdx) => (
                      <tr key={rowIdx} className="hover:bg-gray-50/50">
                        {previewData.columns.map((col, colIdx) => (
                          <td key={colIdx} className="p-3 whitespace-nowrap">
                            {row[col] !== null ? String(row[col]) : "-"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Progress Pop-Up Modal */}
      {isPredicting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border px-8 py-6 flex flex-col items-center w-full max-w-md">
            <h3 className="text-lg font-bold text-secondary mb-4">
              Sedang Memproses Pola Prediksi...
            </h3>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden border border-gray-300">
              <div
                className="bg-accent h-4 rounded-full transition-all duration-300"
                style={{ width: `${predictProgress}%` }}
              ></div>
            </div>
            <p className="text-sm font-medium text-gray-600">
              {predictProgress}% Selesai
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
export default Upload;
