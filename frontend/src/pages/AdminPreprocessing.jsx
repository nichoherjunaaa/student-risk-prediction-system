import React, { useState } from "react";
import {
  Upload as UploadIcon,
  Wand2,
  Download,
  AlertTriangle,
  Loader2,
  Table2,
  FileSpreadsheet,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import { PRODI_LIST } from "../lib/prodi";
import axios from "axios";

const SEMESTER_OPTIONS = [1, 2, 3, 4];

// Kedua berkas ini yang dipakai sebagai acuan bentuk masukan. Sheet dikenali
// backend dari susunan kolomnya, jadi berkas per prodi yang hanya punya satu
// sheet pun tetap diterima.
const SUMBER = [
  {
    key: "pmb",
    judul: "Berkas PMB",
    isi: "Biodata pendaftar (wajib), nilai tes seleksi, dan nilai rapor SMA.",
  },
  {
    key: "akademik",
    judul: "Berkas Akademik",
    isi: "Nilai mata kuliah per semester beserta rekap IPK/SKS dan kolom Sisip Program.",
  },
];

const AdminPreprocessing = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [files, setFiles] = useState({ pmb: null, akademik: null });
  const [prodi, setProdi] = useState("");
  const [semester, setSemester] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasil, setHasil] = useState(null);

  const pilihBerkas = (key) => (e) => {
    if (e.target.files && e.target.files[0]) {
      setFiles((prev) => ({ ...prev, [key]: e.target.files[0] }));
      setError("");
    }
  };

  const handleProses = async () => {
    if (!files.pmb || !files.akademik) {
      setError("Berkas PMB dan berkas akademik harus dipilih keduanya.");
      return;
    }
    setLoading(true);
    setError("");
    setHasil(null);

    const formData = new FormData();
    formData.append("file_pmb", files.pmb);
    formData.append("file_akademik", files.akademik);
    formData.append("prodi", prodi);
    formData.append("semester", semester);

    try {
      const response = await axios.post("/api/preprocess", formData);
      setHasil(response.data);
    } catch (err) {
      // Sebutkan status HTTP kalau backend tidak mengirim pesan terstruktur,
      // supaya kegagalan di sisi server tidak menyamar jadi "berkasnya salah".
      const status = err.response?.status;
      setError(
        err.response?.data?.error ||
          (status
            ? `Server menolak permintaan (HTTP ${status}). Periksa log backend — ini bukan soal isi berkas Anda.`
            : "Tidak bisa menghubungi server. Pastikan backend sedang berjalan."),
      );
    }
    setLoading(false);
  };

  const handleUnduh = async () => {
    if (!hasil) return;
    try {
      const response = await axios.get(hasil.download_url, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = hasil.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError(
        "Gagal mengunduh hasil preprocessing. Silakan jalankan ulang prosesnya.",
      );
    }
  };

  const laporan = hasil?.report;
  const kolomPreview = hasil?.columns || [];

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Preprocessing Data"
          subtitle="Gabungkan berkas PMB dan akademik menjadi satu berkas data latih."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto">
          <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
            <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
              <Wand2 className="text-primary" /> Gabungkan Berkas Mentah Menjadi
              Data Latih
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Unggah berkas PMB dan berkas akademik untuk satu program studi.
              Sistem akan menggabungkannya menjadi satu tabel (satu baris per
              mahasiswa) berisi kolom fitur dan kolom Label, siap diunggah di
              menu Master Model untuk melatih model.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {SUMBER.map((sumber) => (
                <label
                  key={sumber.key}
                  className="flex flex-col px-5 py-5 bg-background rounded-xl border-2 border-dashed border-gray-300 cursor-pointer hover:border-primary transition"
                >
                  <span className="flex items-center gap-2 text-sm font-bold text-secondary mb-1">
                    <FileSpreadsheet size={16} className="text-primary" />
                    {sumber.judul}
                  </span>
                  <span className="text-xs text-gray-500 mb-3">
                    {sumber.isi}
                  </span>
                  <span className="flex items-center gap-2 text-sm font-medium text-gray-600">
                    <UploadIcon size={16} className="text-gray-400 shrink-0" />
                    <span className="truncate">
                      {files[sumber.key]?.name || "Pilih berkas Excel (.xlsx)"}
                    </span>
                  </span>
                  <input
                    type="file"
                    accept=".xlsx"
                    onChange={pilihBerkas(sumber.key)}
                    className="hidden"
                  />
                </label>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Program Studi
                </label>
                <select
                  value={prodi}
                  onChange={(e) => setProdi(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  <option value="">-- Deteksi dari berkas --</option>
                  {PRODI_LIST.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Data Sampai Semester
                </label>
                <select
                  value={semester}
                  onChange={(e) => setSemester(e.target.value)}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  {SEMESTER_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      Semester {s}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-2">
                  Nilai mata kuliah di atas semester ini tidak ikut dipakai
                  sebagai fitur.
                </p>
              </div>

              <div>
                {/* Label kosong sebagai pengganjal, supaya tombol sejajar dengan
                    kedua dropdown di sebelahnya, bukan turun mengikuti teks
                    bantuan di bawah dropdown Semester. */}
                <span
                  aria-hidden="true"
                  className="block text-sm font-semibold mb-2 select-none"
                >
                  &nbsp;
                </span>
                <Button
                  onClick={handleProses}
                  disabled={loading}
                  size="lg"
                  className="w-full md:w-auto"
                >
                  {loading ? (
                    <Loader2 className="animate-spin" size={18} />
                  ) : (
                    <Wand2 size={18} />
                  )}
                  Proses & Gabungkan
                </Button>
              </div>
            </div>

            {error && (
              <p className="text-red-500 text-sm flex items-start gap-1">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                {error}
              </p>
            )}
          </div>

          {hasil && (
            <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-xl font-bold flex items-center gap-2">
                    <Table2 className="text-accent" /> Hasil Preprocessing
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {hasil.prodi} — sheet{" "}
                    <span className="font-mono">{hasil.sheet}</span>. Unduh
                    berkas ini, lalu unggah di menu Master Model untuk melatih
                    model.
                  </p>
                </div>
                <Button variant="outline" onClick={handleUnduh} className="shrink-0">
                  <Download size={16} /> Unduh Data Latih (.xlsx)
                </Button>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <Statistik label="Jumlah Mahasiswa" nilai={laporan.mahasiswa} />
                <Statistik label="Jumlah Fitur" nilai={laporan.jumlah_fitur} />
                <Statistik
                  label="Mata Kuliah Terpakai"
                  nilai={laporan.jumlah_matkul}
                />
                <Statistik
                  label="Dibuang (Tanpa Label)"
                  nilai={laporan.tanpa_label}
                />
              </div>

              <div className="flex flex-wrap gap-2 mb-6 text-xs">
                {Object.entries(laporan.distribusi_label).map(([k, v]) => (
                  <span
                    key={k}
                    className="px-3 py-1.5 rounded-full bg-gray-100 border border-border font-semibold"
                  >
                    {k}: {v}
                  </span>
                ))}
                {laporan.angkatan.length > 0 && (
                  <span className="px-3 py-1.5 rounded-full bg-gray-100 border border-border font-semibold">
                    Angkatan: {laporan.angkatan.join(", ")}
                  </span>
                )}
              </div>

              <div className="overflow-x-auto border border-border rounded-xl">
                <table className="text-left border-collapse text-xs whitespace-nowrap">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 uppercase font-semibold">
                      {kolomPreview.map((col) => (
                        <th key={col} scope="col" className="p-2 border-b border-border">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {hasil.preview.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50/50">
                        {kolomPreview.map((col) => (
                          <td key={col} className="p-2 text-gray-600">
                            {row[col] === null || row[col] === undefined
                              ? "-"
                              : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                Menampilkan {hasil.preview.length} baris pertama dari{" "}
                {laporan.mahasiswa} baris, {kolomPreview.length} kolom.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

const Statistik = ({ label, nilai }) => (
  <div className="bg-background border border-border rounded-xl p-4">
    <p className="text-xs text-gray-500">{label}</p>
    <p className="text-2xl font-bold text-secondary">{nilai}</p>
  </div>
);

export default AdminPreprocessing;
