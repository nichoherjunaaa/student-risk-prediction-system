import React, { useEffect, useState } from "react";
import { BarChart2, Database, Cpu, AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import axios from "axios";
import Button from "./Button";

// Prediksi dari Berkas Mahasiswa: server membentuk tabel uji (setara sheet TEST_SEM<n>
// di cnn_tabular_2d_v2.py) langsung dari berkas PMB & akademik di Berkas
// Mahasiswa, lalu memprediksi dengan model aktif prodi. Berkas terbaru dipilih
// otomatis, tetapi bisa diganti bila BAPSI mengunggah lebih dari satu berkas.

const SUMBER = [
  { key: "pmb", judul: "Berkas PMB" },
  { key: "akademik", judul: "Berkas Akademik" },
];

const formatDate = (iso) => {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

const InfoRow = ({ icon: Icon, label, children }) => (
  <div className="flex items-start gap-3 p-3 rounded-xl bg-background border border-border">
    <Icon size={18} className="text-primary mt-0.5 shrink-0" />
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</p>
      <div className="text-sm text-secondary">{children}</div>
    </div>
  </div>
);

const AutoPredictCard = ({ prodi, setProdi, prodiList, lockedProdi, runWithProgress }) => {
  const [sumber, setSumber] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [angkatan, setAngkatan] = useState("");
  const [daftarBerkas, setDaftarBerkas] = useState({ pmb: null, akademik: null });
  const [pilihan, setPilihan] = useState({ pmb: "", akademik: "" });

  useEffect(() => {
    SUMBER.forEach(({ key }) => {
      axios
        .get("/api/files", { params: { kategori: key } })
        .then((r) => {
          const list = r.data.files;
          setDaftarBerkas((prev) => ({ ...prev, [key]: list }));
          setPilihan((prev) => ({ ...prev, [key]: list[0] ? String(list[0].id) : "" }));
        })
        .catch(() => setDaftarBerkas((prev) => ({ ...prev, [key]: [] })));
    });
  }, []);

  const berkasParams = {
    ...(pilihan.pmb && { file_pmb_id: pilihan.pmb }),
    ...(pilihan.akademik && { file_akademik_id: pilihan.akademik }),
  };
  const berkasSiap = daftarBerkas.pmb !== null && daftarBerkas.akademik !== null;

  const loadSumber = async (target) => {
    if (!target) {
      setSumber(null);
      return;
    }
    setLoading(true);
    setError("");
    setSumber(null);
    try {
      const r = await axios.get("/api/predict/sumber", { params: { prodi: target, ...berkasParams } });
      setSumber(r.data);
      // Angkatan termuda biasanya yang sedang dipantau.
      setAngkatan(r.data.angkatan[r.data.angkatan.length - 1] || "");
    } catch (err) {
      setError(err.response?.data?.error || "Gagal memeriksa berkas dan model untuk prodi ini.");
    }
    setLoading(false);
  };

  // Tunggu daftar berkas termuat supaya pemeriksaan memakai berkas yang tampil di dropdown.
  useEffect(() => {
    if (berkasSiap) loadSumber(prodi);
  }, [prodi, pilihan.pmb, pilihan.akademik, berkasSiap]);

  const handlePredict = () => {
    setError("");
    runWithProgress(
      () => axios.post("/api/predict/berkas", { prodi, angkatan, ...berkasParams }),
      (msg) => setError(msg),
    );
  };

  const model = sumber?.model;

  return (
    <div className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
      <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
        <Database className="text-primary" /> Prediksi dari Berkas Mahasiswa
      </h2>
      <p className="text-sm text-gray-500 max-w-3xl mb-6">
        Sistem mengolah berkas PMB dan akademik yang diunggah BAPSI dengan cara yang sama seperti
        data latih model, lalu memprediksi seluruh mahasiswa pada
        angkatan yang dipilih.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {SUMBER.map(({ key, judul }) => {
          const daftar = daftarBerkas[key];
          return (
            <div key={key}>
              <label className="block text-sm font-semibold text-gray-700 mb-2">{judul}</label>
              {daftar === null ? (
                <p className="px-4 py-3 text-sm text-gray-400 flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" /> Memuat berkas...
                </p>
              ) : daftar.length === 0 ? (
                <p className="px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-500">
                  Belum ada {judul.toLowerCase()} yang diunggah BAPSI.
                </p>
              ) : (
                <select
                  value={pilihan[key]}
                  onChange={(e) => setPilihan((prev) => ({ ...prev, [key]: e.target.value }))}
                  aria-label={`Pilih ${judul}`}
                  className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition text-sm"
                >
                  {daftar.map((f, i) => (
                    <option key={f.id} value={f.id}>
                      {f.name}
                      {f.path ? ` (${f.path})` : ""} - {formatDate(f.uploaded_at)}
                      {i === 0 ? " - terbaru" : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Program Studi</label>
          {lockedProdi ? (
            <div className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-secondary font-medium">
              {lockedProdi}
              <span className="block text-xs text-gray-400 font-normal mt-0.5">Sesuai program studi akun Anda</span>
            </div>
          ) : (
            <select
              value={prodi}
              onChange={(e) => setProdi(e.target.value)}
              className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition"
            >
              <option value="">-- Pilih Program Studi --</option>
              {prodiList.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          )}
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Angkatan</label>
          <select
            value={angkatan}
            onChange={(e) => setAngkatan(e.target.value)}
            disabled={!sumber}
            className="w-full px-4 py-3 bg-background border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition disabled:opacity-50"
          >
            {!sumber && <option value="">-</option>}
            {(sumber?.angkatan || []).map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Data Sampai Semester</label>
          <div className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-secondary font-medium">
            {model?.max_semester ? `Semester ${model.max_semester}` : "-"}
            <span className="block text-xs text-gray-400 font-normal mt-0.5">
              {model?.max_semester_source === "perkiraan"
                ? "Mengikuti data latih model (diperkirakan dari fitur model)"
                : "Mengikuti data latih model"}
            </span>
          </div>
        </div>
      </div>

      {loading && (
        <p className="flex items-center text-sm text-gray-500 mb-4">
          <Loader2 size={16} className="animate-spin mr-2" /> Memeriksa berkas dan model...
        </p>
      )}

      {sumber && (
        <div className="mb-6">
          <InfoRow icon={Cpu} label="Model Aktif">
            <span className="font-medium break-all">{model.version}</span>
            <span className="block text-xs text-gray-500">Dilatih {model.trained_at}</span>
          </InfoRow>
        </div>
      )}

      {error && (
        <p className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 flex items-start gap-2">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" /> {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Button size="lg" onClick={handlePredict} disabled={!sumber || !angkatan || loading}>
          <BarChart2 size={18} /> Jalankan Prediksi
        </Button>
        <Button variant="ghost" size="lg" onClick={() => loadSumber(prodi)} disabled={!prodi || loading}>
          <RefreshCw size={16} /> Periksa Ulang Berkas
        </Button>
      </div>
    </div>
  );
};

export default AutoPredictCard;
