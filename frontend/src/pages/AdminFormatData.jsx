import React, { useEffect, useState } from "react";
import {
  Save,
  RotateCcw,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  Loader2,
  FileSearch,
  CheckCircle2,
  XCircle,
  Info,
} from "lucide-react";
import axios from "axios";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import ConfirmDialog from "../components/ConfirmDialog";
import { setProdiCache } from "../lib/prodi";

// Halaman ini menyunting format berkas mentah yang dipakai preprocessing
// (backend/sisip/data_format.py). Yang diatur hanya nama kolom di berkas
// sumber dan nama fitur hasilnya; skema internal (NIM, Label, IPK n) tetap.

const INPUT =
  "w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition";

const clone = (v) => JSON.parse(JSON.stringify(v));

const Card = ({ title, subtitle, children }) => (
  <section className="bg-surface p-6 rounded-2xl shadow-sm border border-border">
    <h2 className="text-lg font-bold text-secondary">{title}</h2>
    {subtitle && <p className="text-sm text-gray-500 mt-1 mb-5">{subtitle}</p>}
    {!subtitle && <div className="mb-5" />}
    {children}
  </section>
);

const Field = ({ label, hint, value, onChange }) => (
  <label className="block">
    <span className="block text-sm font-semibold text-gray-700 mb-1.5">{label}</span>
    <input className={INPUT} value={value} onChange={(e) => onChange(e.target.value)} />
    {hint && <span className="block text-xs text-gray-400 mt-1">{hint}</span>}
  </label>
);

const TagList = ({ values, onChange, placeholder }) => {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (!v || values.some((x) => x.toLowerCase() === v.toLowerCase())) return;
    onChange([...values, v]);
    setDraft("");
  };
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {values.map((v, i) => (
          <span key={v} className="inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full bg-primary/5 border border-primary/20 text-sm text-primary font-medium">
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((_, j) => j !== i))}
              aria-label={`Hapus ${v}`}
              className="p-0.5 rounded-full hover:bg-primary/10"
            >
              <XCircle size={14} />
            </button>
          </span>
        ))}
        {values.length === 0 && <span className="text-sm text-gray-400">Belum ada isi.</span>}
      </div>
      <div className="flex gap-2 max-w-md">
        <input
          className={INPUT}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button variant="secondary" onClick={add} disabled={!draft.trim()}>
          <Plus size={16} /> Tambah
        </Button>
      </div>
    </div>
  );
};

// Tabel pemetaan "kolom di berkas -> nama hasil".
const PairTable = ({ rows, onChange, rightKey, leftLabel, rightLabel, rightHint }) => {
  const set = (i, key, value) => onChange(rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
  return (
    <div>
      <div className="overflow-x-auto border border-border rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase text-left">
              <th className="p-2.5 w-1/2">{leftLabel}</th>
              <th className="p-2.5 w-1/2">{rightLabel}</th>
              <th className="p-2.5 w-10" aria-label="Aksi" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="p-2">
                  <input className={INPUT} value={r.sumber} aria-label={`${leftLabel} baris ${i + 1}`} onChange={(e) => set(i, "sumber", e.target.value)} />
                </td>
                <td className="p-2">
                  <input className={INPUT} value={r[rightKey]} aria-label={`${rightLabel} baris ${i + 1}`} onChange={(e) => set(i, rightKey, e.target.value)} />
                </td>
                <td className="p-2 text-center">
                  <button
                    type="button"
                    onClick={() => onChange(rows.filter((_, j) => j !== i))}
                    aria-label={`Hapus baris ${i + 1}`}
                    className="p-2 rounded-lg text-red-500 hover:bg-red-50"
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={3} className="p-3 text-center text-gray-400">Tidak ada kolom.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
        {rightHint ? <p className="text-xs text-gray-400">{rightHint}</p> : <span />}
        <Button variant="ghost" size="sm" onClick={() => onChange([...rows, { sumber: "", [rightKey]: "" }])}>
          <Plus size={14} /> Tambah baris
        </Button>
      </div>
    </div>
  );
};

const GradeTable = ({ rows, onChange }) => {
  const set = (i, key, value) => onChange(rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
  const move = (i, d) => {
    const next = [...rows];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(next);
  };
  return (
    <div>
      <div className="overflow-x-auto border border-border rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase text-left">
              <th className="p-2.5 w-16">Urutan</th>
              <th className="p-2.5">Huruf</th>
              <th className="p-2.5">Bobot</th>
              <th className="p-2.5 text-center">Lulus</th>
              <th className="p-2.5 w-32" aria-label="Aksi" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r, i) => (
              <tr key={i}>
                <td className="p-2 text-gray-400 font-mono">{i + 1}</td>
                <td className="p-2">
                  <input className={`${INPUT} max-w-[6rem] font-mono`} value={r.huruf} aria-label={`Huruf baris ${i + 1}`} onChange={(e) => set(i, "huruf", e.target.value.toUpperCase())} />
                </td>
                <td className="p-2">
                  <input className={`${INPUT} max-w-[7rem]`} type="number" step="0.01" min="0" max="10" value={r.bobot} aria-label={`Bobot ${r.huruf}`} onChange={(e) => set(i, "bobot", e.target.value === "" ? "" : Number(e.target.value))} />
                </td>
                <td className="p-2 text-center">
                  <input type="checkbox" className="h-4 w-4 accent-primary" checked={r.lulus} aria-label={`${r.huruf} lulus`} onChange={(e) => set(i, "lulus", e.target.checked)} />
                </td>
                <td className="p-2">
                  <div className="flex justify-end gap-1">
                    <button type="button" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Naikkan ${r.huruf}`} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30"><ArrowUp size={15} /></button>
                    <button type="button" disabled={i === rows.length - 1} onClick={() => move(i, 1)} aria-label={`Turunkan ${r.huruf}`} className="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 disabled:opacity-30"><ArrowDown size={15} /></button>
                    <button type="button" onClick={() => onChange(rows.filter((_, j) => j !== i))} aria-label={`Hapus ${r.huruf}`} className="p-1.5 rounded-lg text-red-500 hover:bg-red-50"><Trash2 size={15} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
        <p className="text-xs text-gray-400">
          Urutan dari terbaik ke terburuk. Bila mata kuliah diulang, nilai dengan urutan lebih atas yang dipakai.
        </p>
        <Button variant="ghost" size="sm" onClick={() => onChange([...rows, { huruf: "", bobot: 0, lulus: false }])}>
          <Plus size={14} /> Tambah nilai
        </Button>
      </div>
    </div>
  );
};

const CekBerkas = ({ draft }) => {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sheets, setSheets] = useState(null);

  const run = async () => {
    setBusy(true);
    setError("");
    setSheets(null);
    const form = new FormData();
    form.append("file", file);
    form.append("format", JSON.stringify(draft));
    try {
      const r = await axios.post("/api/settings/data-format/check", form);
      setSheets(r.data.sheets);
    } catch (err) {
      setError(err.response?.data?.error || "Gagal memeriksa berkas.");
    }
    setBusy(false);
  };

  return (
    <Card
      title="Cek Berkas"
      subtitle="Unggah contoh berkas PMB atau akademik untuk melihat apakah sheet dan kolomnya cocok dengan pengaturan di halaman ini (termasuk perubahan yang belum disimpan). Berkas tidak disimpan."
    >
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center">
        <input
          type="file"
          accept=".xlsx,.csv"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="text-sm file:mr-3 file:px-4 file:py-2 file:rounded-lg file:border-0 file:bg-primary/10 file:text-primary file:font-semibold"
        />
        <Button onClick={run} disabled={!file || busy}>
          {busy ? <Loader2 size={16} className="animate-spin" /> : <FileSearch size={16} />} Cek
        </Button>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {sheets && (
        <ul className="mt-5 space-y-3">
          {sheets.map((s) => {
            const ok = s.jenis && s.kolom_tidak_ada.length === 0;
            return (
              <li key={s.sheet} className={`p-4 rounded-xl border ${s.jenis ? (ok ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50") : "border-red-200 bg-red-50/50"}`}>
                <div className="flex items-center gap-2 font-semibold text-sm">
                  {s.jenis ? (
                    <CheckCircle2 size={16} className={ok ? "text-emerald-600" : "text-amber-600"} />
                  ) : (
                    <XCircle size={16} className="text-red-600" />
                  )}
                  Sheet &ldquo;{s.sheet}&rdquo;:{" "}
                  {s.jenis ? `dikenali sebagai ${s.label}` : "tidak dikenali"}
                </div>
                {s.jenis && s.kolom_tidak_ada.length > 0 && (
                  <p className="text-sm text-amber-800 mt-1.5">
                    Kolom yang diatur tetapi tidak ada di sheet ini (akan dilewati): {s.kolom_tidak_ada.join(", ")}
                  </p>
                )}
                {!s.jenis && (
                  <p className="text-sm text-red-700 mt-1.5">
                    Paling mirip sheet {s.terdekat}, tetapi kolom wajib berikut tidak ditemukan:{" "}
                    <span className="font-semibold">{s.kolom_wajib_tidak_ada.join(", ")}</span>.
                  </p>
                )}
                <p className="text-xs text-gray-500 mt-2">Kolom di sheet: {s.kolom.join(", ")}</p>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};

const AdminFormatData = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState([]);
  const [notice, setNotice] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);

  const apply = (r) => {
    setData(r);
    setDraft(clone(r.format));
    setProdiCache(r.format.prodi);
  };

  useEffect(() => {
    axios
      .get("/api/settings/data-format")
      .then((r) => apply(r.data))
      .catch((err) => setErrors([err.response?.data?.error || "Gagal memuat format data."]));
  }, []);

  const dirty = data && draft && JSON.stringify(draft) !== JSON.stringify(data.format);

  // Mengubah nama fitur atau menambah/menghapus kolom mengubah susunan fitur
  // model, jadi model aktif perlu dilatih ulang. Perubahan nama kolom sumber
  // saja tidak.
  const fiturBerubah =
    data &&
    draft &&
    ["biodata", "nilai_tes", "nilai_rapor"].some((k) => {
      const kanan = (rows) => rows.map((r) => r.fitur ?? r.akhiran).join("|");
      return kanan(draft.pmb[k]) !== kanan(data.format.pmb[k]);
    });

  const setSection = (section, key) => (value) =>
    setDraft((d) => ({ ...d, [section]: { ...d[section], [key]: value } }));

  const save = async () => {
    setSaving(true);
    setErrors([]);
    try {
      const r = await axios.put("/api/settings/data-format", draft);
      apply(r.data);
      setNotice("Format data tersimpan. Preprocessing berikutnya memakai format ini.");
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setErrors(err.response?.data?.errors || [err.response?.data?.error || "Gagal menyimpan."]);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    setSaving(false);
  };

  const reset = async () => {
    setConfirmReset(false);
    try {
      const r = await axios.delete("/api/settings/data-format");
      apply(r.data);
      setErrors([]);
      setNotice("Format dikembalikan ke bawaan.");
      setTimeout(() => setNotice(""), 4000);
    } catch (err) {
      setErrors([err.response?.data?.error || "Gagal mengembalikan format."]);
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      {/* relative: elemen ber-position absolute di dalam halaman tetap ikut
          tergulir di wadah ini, tidak memanjangkan halaman di luar layar. */}
      <div className="relative flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Format Data"
          subtitle="Sesuaikan nama kolom berkas PMB & akademik, daftar prodi, dan tabel nilai tanpa mengubah kode."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto pb-28">
          {errors.length > 0 && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <p className="font-semibold flex items-center gap-2 mb-1">
                <AlertTriangle size={16} /> Format belum bisa disimpan:
              </p>
              <ul className="list-disc ml-6 space-y-0.5">
                {errors.map((e) => <li key={e}>{e}</li>)}
              </ul>
            </div>
          )}
          {notice && (
            <p role="status" className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700">{notice}</p>
          )}

          {!draft ? (
            errors.length === 0 && (
              <div className="flex items-center justify-center py-20 text-gray-400">
                <Loader2 className="animate-spin mr-2" size={20} /> Memuat format data...
              </div>
            )
          ) : (
            <>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 text-sm text-gray-500">
                <p className="flex items-center gap-2">
                  <Info size={16} className="text-primary shrink-0" />
                  {data.customized
                    ? `Format kustom, terakhir diubah ${data.updated_by || "admin"} pada ${new Date(data.updated_at).toLocaleString("id-ID")}.`
                    : "Saat ini memakai format bawaan."}
                </p>
                {data.customized && (
                  <Button variant="ghost" size="sm" onClick={() => setConfirmReset(true)}>
                    <RotateCcw size={14} /> Kembalikan ke bawaan
                  </Button>
                )}
              </div>

              <Card title="Program Studi" subtitle="Muncul di semua pilihan program studi (prediksi, hasil, preprocessing, training, dan data pengguna).">
                <TagList values={draft.prodi} onChange={(v) => setDraft((d) => ({ ...d, prodi: v }))} placeholder="Nama program studi" />
              </Card>

              <Card
                title="Berkas PMB"
                subtitle="Satu berkas boleh berisi beberapa sheet (biodata, nilai tes, nilai rapor). Jenis sheet dikenali dari kolom penandanya, bukan dari nama sheet."
              >
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <Field label="Kolom nomor pendaftaran" value={draft.pmb.kolom_no_pendaftaran} onChange={setSection("pmb", "kolom_no_pendaftaran")} hint="Kunci penghubung semua sheet PMB." />
                  <Field label="Kolom NIM" value={draft.pmb.kolom_nim} onChange={setSection("pmb", "kolom_nim")} hint="Dicocokkan dengan NIM di berkas akademik." />
                  <Field label="Kolom program studi" value={draft.pmb.kolom_prodi} onChange={setSection("pmb", "kolom_prodi")} />
                </div>

                <h3 className="text-sm font-bold text-secondary mb-2">Sheet biodata</h3>
                <div className="max-w-md mb-3">
                  <Field label="Kolom penanda sheet biodata" value={draft.pmb.penanda_biodata} onChange={setSection("pmb", "penanda_biodata")} hint="Kolom yang hanya ada di sheet biodata." />
                </div>
                <PairTable rows={draft.pmb.biodata} onChange={setSection("pmb", "biodata")} rightKey="fitur" leftLabel="Kolom di berkas" rightLabel="Nama fitur hasil" />

                <h3 className="text-sm font-bold text-secondary mt-8 mb-2">Sheet nilai tes seleksi</h3>
                <div className="max-w-md mb-3">
                  <Field label="Kolom penanda sheet nilai tes" value={draft.pmb.penanda_tes} onChange={setSection("pmb", "penanda_tes")} />
                </div>
                <PairTable rows={draft.pmb.nilai_tes} onChange={setSection("pmb", "nilai_tes")} rightKey="fitur" leftLabel="Kolom di berkas" rightLabel="Nama fitur hasil" />

                <h3 className="text-sm font-bold text-secondary mt-8 mb-2">Sheet nilai rapor</h3>
                <div className="max-w-md mb-3">
                  <Field label="Kolom mata pelajaran" value={draft.pmb.kolom_mapel} onChange={setSection("pmb", "kolom_mapel")} />
                </div>
                <PairTable
                  rows={draft.pmb.nilai_rapor}
                  onChange={setSection("pmb", "nilai_rapor")}
                  rightKey="akhiran"
                  leftLabel="Kolom nilai di berkas"
                  rightLabel="Akhiran nama fitur"
                  rightHint='Fitur dibentuk "<Mata Pelajaran>_<akhiran>", mis. Matematika_1.'
                />
              </Card>

              <Card title="Berkas Akademik" subtitle="Format panjang: satu baris per mahasiswa per mata kuliah. Nama mata kuliah langsung menjadi nama fitur.">
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
                  <Field label="Kolom NIM" value={draft.akademik.kolom_nim} onChange={setSection("akademik", "kolom_nim")} />
                  <Field label="Kolom nama mata kuliah" value={draft.akademik.kolom_matkul} onChange={setSection("akademik", "kolom_matkul")} />
                  <Field label="Kolom nilai huruf" value={draft.akademik.kolom_nilai} onChange={setSection("akademik", "kolom_nilai")} />
                  <Field label="Kolom semester" value={draft.akademik.kolom_semester} onChange={setSection("akademik", "kolom_semester")} />
                  <Field label="Kolom angkatan" value={draft.akademik.kolom_angkatan} onChange={setSection("akademik", "kolom_angkatan")} />
                  <Field label="Kolom IPK per semester" value={draft.akademik.kolom_ipk} onChange={setSection("akademik", "kolom_ipk")} />
                  <Field label="Kolom SKS lulus per semester" value={draft.akademik.kolom_sks_lulus} onChange={setSection("akademik", "kolom_sks_lulus")} />
                  <Field label="Kolom label sisip" value={draft.akademik.kolom_label} onChange={setSection("akademik", "kolom_label")} hint="Target yang dipelajari model." />
                </div>
                <h3 className="text-sm font-bold text-secondary mb-1">Nilai label yang berarti &ldquo;tidak sisip&rdquo;</h3>
                <p className="text-xs text-gray-400 mb-3">Tidak membedakan huruf besar/kecil. Nilai lain di kolom label dianggap sisip.</p>
                <TagList values={draft.akademik.label_aman} onChange={setSection("akademik", "label_aman")} placeholder="mis. tidak sisip program" />
              </Card>

              <Card title="Nilai Mutu" subtitle="Dipakai memilih nilai terbaik saat mata kuliah diulang, menghitung IPK contoh di template, dan memisahkan mata kuliah lulus/tidak lulus di detail mahasiswa.">
                <GradeTable rows={draft.nilai.huruf} onChange={setSection("nilai", "huruf")} />
                <div className="max-w-xs mt-6">
                  <label className="block">
                    <span className="block text-sm font-semibold text-gray-700 mb-1.5">SKS per mata kuliah</span>
                    <input
                      type="number"
                      min="1"
                      max="12"
                      className={INPUT}
                      value={draft.nilai.sks_per_matkul}
                      onChange={(e) => setSection("nilai", "sks_per_matkul")(e.target.value === "" ? "" : Number(e.target.value))}
                    />
                    <span className="block text-xs text-gray-400 mt-1">Berkas akademik tidak memuat SKS tiap mata kuliah, jadi dipakai angka rata.</span>
                  </label>
                </div>
              </Card>

              <CekBerkas draft={draft} />
            </>
          )}
        </main>

        {draft && (
          <div className="sticky bottom-0 bg-surface/95 backdrop-blur border-t border-border px-6 py-4">
            <div className="max-w-[96rem] mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <p className={`text-sm flex items-center gap-2 ${fiturBerubah ? "text-amber-700" : "text-gray-500"}`}>
                {fiturBerubah && <AlertTriangle size={16} className="shrink-0" />}
                {fiturBerubah
                  ? "Nama/jumlah fitur berubah: model yang sudah aktif perlu dilatih ulang dengan data hasil preprocessing baru."
                  : dirty
                    ? "Ada perubahan yang belum disimpan."
                    : "Tidak ada perubahan."}
              </p>
              <div className="flex gap-2 shrink-0">
                <Button variant="ghost" disabled={!dirty || saving} onClick={() => { setDraft(clone(data.format)); setErrors([]); }}>
                  Batalkan
                </Button>
                <Button onClick={save} disabled={!dirty || saving}>
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Simpan Format
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmReset}
        title="Kembalikan Format Bawaan?"
        message="Semua pengaturan kolom, daftar prodi, dan tabel nilai kembali ke bawaan aplikasi."
        confirmLabel="Ya, Kembalikan"
        onConfirm={reset}
        onCancel={() => setConfirmReset(false)}
      />
    </div>
  );
};

export default AdminFormatData;
