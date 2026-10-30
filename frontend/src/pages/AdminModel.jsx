import { useState, useEffect } from "react";
import {
  Upload as UploadIcon,
  Database,
  Cpu,
  CheckCircle,
  AlertTriangle,
  Loader2,
  BarChart2,
  Star,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import axios from "axios";

// Saklar tampilan hyperparameter (Max Epochs, Batch Size, Learning Rate,
// Dropout Rate, Validation Split). Disembunyikan sementara: nilainya masih
// dikirim ke /api/train dari state di bawah, tetapi belum disimpan ke tabel
// model_registry sehingga setelan tiap model belum bisa ditelusuri.
// Lihat docs/AUDIT-PIPELINE-PREDIKSI.md — requirement "parameter yang dipilih apa".
// Ubah ke true untuk menampilkannya kembali.
const SHOW_HYPERPARAMS = false;

// Jumlah model per halaman di tabel Registri Model.
const MODELS_PER_PAGE = 10;

// Recall kelas SISIP = mahasiswa sisip yang tertangkap / seluruh mahasiswa sisip
// di data validasi. Akurasi saja menipu karena sebagian besar mahasiswa tidak
// sisip. Jumlahnya ikut ditampilkan karena data validasi kecil.
const RecallSisip = ({ metrics }) => {
  if (metrics.recall_sisip == null) {
    return (
      <span
        className="text-gray-400"
        title={
          metrics.val_sisip_total === 0
            ? "Tidak ada mahasiswa SISIP di data validasi"
            : "Model lama: recall belum dicatat. Latih ulang untuk melihatnya."
        }
      >
        —
      </span>
    );
  }
  const pct = metrics.recall_sisip * 100;
  const color =
    pct < 50 ? "text-red-600" : pct < 75 ? "text-amber-600" : "text-green-600";
  return (
    <span className={`font-semibold ${color}`}>
      {pct.toFixed(1)}%{" "}
      <span className="font-normal text-gray-500">
        ({metrics.val_sisip_caught}/{metrics.val_sisip_total})
      </span>
    </span>
  );
};

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

  // Pilihan angkatan dibaca server dari berkas yang dipilih: null = belum ada
  // berkas, "loading" = sedang dibaca, array = angkatan yang ada di berkas.
  const [angkatanOptions, setAngkatanOptions] = useState(null);
  const [angkatanDipilih, setAngkatanDipilih] = useState([]);

  // State Hyperparameter Eksperimen Model
  const [epochs, setEpochs] = useState(100);
  const [batchSize, setBatchSize] = useState(32);
  const [learningRate, setLearningRate] = useState(0.001);
  const [dropoutRate, setDropoutRate] = useState(0.3);
  const [valSplit, setValSplit] = useState(0.2);

  // State Manajemen Registri Riwayat Model
  const [modelHistory, setModelHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalModels, setTotalModels] = useState(0);
  const [modelMetrics, setModelMetrics] = useState(null);

  useEffect(() => {
    fetchModelHistory(1);
  }, []);

  // Server membatasi page ke halaman terakhir yang ada, jadi halaman yang
  // dikembalikan dipakai apa adanya.
  const fetchModelHistory = async (targetPage = page) => {
    setHistoryLoading(true);
    try {
      const response = await axios.get("/api/models", {
        params: { page: targetPage, per_page: MODELS_PER_PAGE },
      });
      setModelHistory(response.data.items);
      setPage(response.data.page);
      setTotalPages(response.data.total_pages);
      setTotalModels(response.data.total);
    } catch (err) {
      console.error("Gagal mengambil data registri model:", err);
    }
    setHistoryLoading(false);
  };

  const handleFileChange = async (e) => {
    if (!e.target.files || !e.target.files[0]) return;
    const picked = e.target.files[0];
    setFile(picked);
    setError("");
    setAngkatanOptions("loading");
    setAngkatanDipilih([]);
    const formData = new FormData();
    formData.append("file", picked);
    try {
      const { data } = await axios.post("/api/train/angkatan", formData);
      setAngkatanOptions(data.angkatan);
      setAngkatanDipilih(data.angkatan);
    } catch (err) {
      setAngkatanOptions([]);
      setError(err.response?.data?.error || "Gagal membaca angkatan dari berkas data latih.");
    }
  };

  const toggleAngkatan = (a) =>
    setAngkatanDipilih((prev) =>
      prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a].sort(),
    );
  const semuaAngkatan = Array.isArray(angkatanOptions) ? angkatanOptions : [];
  const semuaDipilih = semuaAngkatan.length > 0 && angkatanDipilih.length === semuaAngkatan.length;

  const handleTrain = async () => {
    if (!file) {
      setError(
        "Silakan tentukan berkas Excel data latih historis terlebih dahulu.",
      );
      return;
    }
    if (semuaAngkatan.length > 0 && angkatanDipilih.length === 0) {
      setError("Pilih minimal satu tahun angkatan untuk dilatih.");
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
    // Semua angkatan dipilih = tanpa filter (server melatih seluruh berkas).
    formData.append("angkatan", semuaDipilih ? "" : angkatanDipilih.join(","));
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
        setModelMetrics({ ...response.data.metrics, prodi: response.data.prodi });
        setShowSuccessModal(true);
        setFile(null);
        setAngkatanOptions(null);
        setAngkatanDipilih([]);
        fetchModelHistory(1);
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
              Unggah berkas data latih hasil dari menu{" "}
              <Link
                to="/admin/preprocessing"
                className="font-semibold text-primary hover:underline"
              >
                Preprocessing Data
              </Link>{" "}
              untuk melatih kecerdasan buatan. Program studi model dideteksi
              otomatis dari kolom Prodi di berkas tersebut.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <fieldset className="md:col-span-2 lg:col-span-4">
                <legend className="block text-sm font-semibold text-gray-700 mb-2">
                  Tahun Angkatan Latih
                </legend>
                {angkatanOptions === null ? (
                  <p className="text-sm text-gray-500">
                    Pilih berkas data latih di bawah; angkatan yang ada di berkas akan muncul di sini.
                  </p>
                ) : angkatanOptions === "loading" ? (
                  <p className="text-sm text-gray-500 flex items-center gap-2">
                    <Loader2 size={14} className="animate-spin" /> Membaca angkatan dari berkas...
                  </p>
                ) : semuaAngkatan.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    Berkas tidak memuat kolom Angkatan; seluruh data dilatih.
                  </p>
                ) : (
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      aria-pressed={semuaDipilih}
                      onClick={() => setAngkatanDipilih(semuaDipilih ? [] : semuaAngkatan)}
                      className={`px-3 py-1.5 rounded-lg border text-sm font-semibold transition ${
                        semuaDipilih
                          ? "bg-primary text-white border-primary"
                          : "bg-surface text-secondary border-border hover:bg-gray-50"
                      }`}
                    >
                      Semua
                    </button>
                    {semuaAngkatan.map((a) => {
                      const aktif = angkatanDipilih.includes(a);
                      return (
                        <button
                          key={a}
                          type="button"
                          aria-pressed={aktif}
                          onClick={() => toggleAngkatan(a)}
                          className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition ${
                            aktif
                              ? "bg-primary/10 text-primary border-primary/40"
                              : "bg-surface text-gray-500 border-border hover:bg-gray-50"
                          }`}
                        >
                          {a}
                        </button>
                      );
                    })}
                  </div>
                )}
              </fieldset>

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
                    <th scope="col" className="p-3">Tahun Angkatan</th>
                    <th scope="col" className="p-3">Waktu Dilatih</th>
                    <th scope="col" className="p-3">Akurasi</th>
                    <th scope="col" className="p-3">Recall SISIP</th>
                    <th scope="col" className="p-3">Loss</th>
                    <th scope="col" className="p-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-border">
                  {historyLoading ? (
                    <tr>
                      <td colSpan="8" className="p-4 text-center text-gray-500">
                        Memuat registri model...
                      </td>
                    </tr>
                  ) : modelHistory.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="p-4 text-center text-gray-500">
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
                        <td className="p-3 text-xs">
                          {model.angkatan ? (
                            model.angkatan
                          ) : (
                            <span
                              className="text-gray-400"
                              title="Model lama: angkatan belum dicatat. Latih ulang untuk melihatnya."
                            >
                              —
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-gray-500 text-xs">
                          {model.trained_at}
                        </td>
                        <td className="p-3 text-green-600 font-semibold">
                          {(model.accuracy * 100).toFixed(1)}%
                        </td>
                        <td className="p-3 text-xs">
                          <RecallSisip metrics={model} />
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

            {totalModels > 0 && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-4 text-sm text-gray-500">
                <span>
                  Halaman {page} dari {totalPages} · {totalModels} model
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => fetchModelHistory(page - 1)}
                    disabled={historyLoading || page <= 1}
                  >
                    <ChevronLeft size={14} /> Sebelumnya
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => fetchModelHistory(page + 1)}
                    disabled={historyLoading || page >= totalPages}
                  >
                    Berikutnya <ChevronRight size={14} />
                  </Button>
                </div>
              </div>
            )}
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
                Model{" "}
                {modelMetrics?.prodi && (
                  <>
                    prodi{" "}
                    <span className="font-semibold text-secondary">
                      {modelMetrics.prodi}
                    </span>{" "}
                  </>
                )}
                sudah tersimpan di registri. Aktifkan lewat tabel di bawah agar
                dipakai untuk prediksi.
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
                  <div className="col-span-2 border-t border-border pt-2">
                    <span className="text-xs text-gray-500">
                      Recall SISIP (mahasiswa sisip yang tertangkap di data validasi):
                    </span>
                    <div className="text-md">
                      <RecallSisip metrics={modelMetrics} />
                    </div>
                    {modelMetrics.n_train_samples != null && (
                      <p className="text-xs text-gray-500 mt-1">
                        Dilatih dari {modelMetrics.n_train_samples} mahasiswa
                        berlabel
                        {modelMetrics.angkatan
                          ? ` angkatan ${modelMetrics.angkatan}`
                          : ""}
                        .
                      </p>
                    )}
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
