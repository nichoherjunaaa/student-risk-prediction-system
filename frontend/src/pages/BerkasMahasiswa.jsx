import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Folder,
  FolderPlus,
  FileSpreadsheet,
  FileText,
  File as FileIcon,
  UploadCloud,
  Download,
  Pencil,
  FolderInput,
  Trash2,
  Search,
  ChevronRight,
  Home,
  Loader2,
  AlertTriangle,
  X,
  LayoutGrid,
  List,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";
import axios from "axios";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import Button from "../components/Button";
import ConfirmDialog from "../components/ConfirmDialog";

// Harus sama dengan FILE_KATEGORI / FILE_EXT di backend/sisip/routes/files.py. Berkas PMB dan
// akademik yang diunggah di sini muncul sebagai pilihan di halaman
// Preprocessing Data dan prediksi tanpa template, jadi keduanya dibatasi ke
// format yang bisa dibaca preprocessing: Excel (.xlsx) atau CSV.
const KATEGORI = {
  pmb: { label: "Berkas PMB", short: "PMB", accept: ".xlsx,.csv", cls: "bg-blue-50 text-blue-700 border-blue-200" },
  akademik: { label: "Berkas Akademik", short: "Akademik", accept: ".xlsx,.csv", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  lainnya: { label: "Lainnya", short: "Lainnya", accept: ".xlsx,.xls,.csv,.pdf,.docx,.zip", cls: "bg-gray-100 text-gray-600 border-gray-200" },
};

const VIEW_KEY = "berkasView";

function formatSize(bytes) {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fileIcon(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  if (["xlsx", "xls", "csv"].includes(ext)) return FileSpreadsheet;
  if (["pdf", "docx"].includes(ext)) return FileText;
  return FileIcon;
}

function apiError(err, fallback) {
  return err.response?.data?.error || fallback;
}

function readView() {
  try {
    return localStorage.getItem(VIEW_KEY) === "grid" ? "grid" : "list";
  } catch {
    return "list";
  }
}

const KategoriBadge = ({ kategori }) => {
  const k = KATEGORI[kategori] || KATEGORI.lainnya;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md border text-[11px] font-semibold ${k.cls}`}>
      {k.short}
    </span>
  );
};

const Modal = ({ title, onClose, children }) => (
  <div
    role="dialog"
    aria-modal="true"
    aria-label={title}
    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
  >
    <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-bold text-secondary">{title}</h3>
        <button onClick={onClose} aria-label="Tutup" className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-secondary">
          <X size={18} />
        </button>
      </div>
      {children}
    </div>
  </div>
);

// Satu dialog isian nama untuk "Folder Baru", "Ganti Nama Folder", dan
// "Ganti Nama Berkas".
const NameDialog = ({ title, label, initial = "", submitLabel, onSubmit, onClose }) => {
  const [value, setValue] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handle = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit(value.trim());
    } catch (err) {
      setError(apiError(err, "Gagal menyimpan."));
      setBusy(false);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={handle} className="space-y-4">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">{label}</label>
          <input
            autoFocus
            required
            maxLength={150}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full px-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Batal</Button>
          <Button type="submit" disabled={busy || !value.trim()}>
            {busy && <Loader2 size={16} className="animate-spin" />}
            {submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

const UploadDialog = ({ folderName, initialFiles, onUpload, onClose }) => {
  const [files, setFiles] = useState(initialFiles || []);
  const [kategori, setKategori] = useState("pmb");
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const accept = KATEGORI[kategori].accept;
  const allowed = accept.split(",");
  const invalid = files.filter((f) => !allowed.some((ext) => f.name.toLowerCase().endsWith(ext)));

  const handle = async () => {
    setError("");
    setProgress(0);
    try {
      await onUpload(files, kategori, setProgress);
    } catch (err) {
      setError(apiError(err, "Gagal mengunggah berkas."));
      setProgress(null);
    }
  };

  return (
    <Modal title="Unggah Berkas" onClose={progress === null ? onClose : undefined}>
      <div className="space-y-5">
        <p className="text-sm text-gray-500">
          Tujuan: <span className="font-semibold text-secondary">{folderName}</span>
        </p>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Kategori Berkas</label>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(KATEGORI).map(([key, k]) => (
              <button
                key={key}
                type="button"
                onClick={() => setKategori(key)}
                aria-pressed={kategori === key}
                className={`px-3 py-2.5 rounded-xl border text-sm font-semibold transition ${kategori === key ? "border-primary bg-primary/5 text-primary" : "border-border text-gray-600 hover:bg-gray-50"}`}
              >
                {k.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">
            {kategori === "lainnya"
              ? "Berkas pendukung, tidak dipakai preprocessing."
              : "Dipakai Preprocessing Data dan prediksi tanpa template (berkas terbaru dipakai otomatis). Format: .xlsx atau .csv."}
          </p>
        </div>

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="w-full flex flex-col items-center justify-center gap-2 px-4 py-8 border-2 border-dashed border-gray-300 rounded-xl hover:border-primary transition text-sm text-gray-600"
        >
          <UploadCloud className="text-primary" size={28} />
          <span className="font-semibold">Pilih berkas dari komputer</span>
          <span className="text-xs text-gray-400">Bisa lebih dari satu berkas, maks. 50 MB per berkas</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          className="hidden"
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
        />

        {files.length > 0 && (
          <ul className="border border-border rounded-xl divide-y divide-border text-sm max-h-48 overflow-y-auto">
            {files.map((f, i) => {
              const bad = invalid.includes(f);
              return (
                <li key={i} className="flex items-center justify-between gap-3 px-3 py-2">
                  <span className={`truncate ${bad ? "text-red-600" : ""}`}>{f.name}</span>
                  <span className="text-xs text-gray-400 shrink-0">{bad ? "format tidak didukung" : formatSize(f.size)}</span>
                </li>
              );
            })}
          </ul>
        )}

        {progress !== null && (
          <div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-xs text-gray-500 mt-1">Mengunggah... {progress}%</p>
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={progress !== null}>Batal</Button>
          <Button onClick={handle} disabled={!files.length || invalid.length > 0 || progress !== null}>
            {progress !== null ? <Loader2 size={16} className="animate-spin" /> : <UploadCloud size={16} />}
            Unggah {files.length > 0 ? `${files.length} Berkas` : ""}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

// Penjelajah folder mini untuk memilih tujuan pemindahan berkas.
const MoveDialog = ({ file, onMove, onClose }) => {
  const [folderId, setFolderId] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setData(null);
    axios
      .get("/api/files", { params: folderId ? { folder_id: folderId } : {} })
      .then((r) => setData(r.data))
      .catch((err) => setError(apiError(err, "Gagal memuat folder.")));
  }, [folderId]);

  const handle = async () => {
    setBusy(true);
    try {
      await onMove(folderId);
    } catch (err) {
      setError(apiError(err, "Gagal memindahkan berkas."));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Pindahkan "${file.name}"`} onClose={onClose}>
      <div className="space-y-4">
        <Breadcrumb trail={data?.breadcrumb || []} onNavigate={setFolderId} />
        <div className="border border-border rounded-xl divide-y divide-border min-h-[160px] max-h-64 overflow-y-auto">
          {!data ? (
            <p className="p-4 text-sm text-gray-500">Memuat...</p>
          ) : data.folders.length === 0 ? (
            <p className="p-4 text-sm text-gray-500">Tidak ada subfolder di sini.</p>
          ) : (
            data.folders.map((f) => (
              <button
                key={f.id}
                onClick={() => setFolderId(f.id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left hover:bg-gray-50"
              >
                <Folder size={18} className="text-amber-500 shrink-0" />
                <span className="truncate flex-1">{f.name}</span>
                <ChevronRight size={16} className="text-gray-400" />
              </button>
            ))
          )}
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>Batal</Button>
          <Button onClick={handle} disabled={busy || folderId === file.folder_id}>
            <FolderInput size={16} /> Pindahkan ke Sini
          </Button>
        </div>
      </div>
    </Modal>
  );
};

const Breadcrumb = ({ trail, onNavigate }) => (
  <nav aria-label="Lokasi folder" className="flex items-center flex-wrap gap-1 text-sm">
    <button
      onClick={() => onNavigate(null)}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-gray-100 ${trail.length === 0 ? "font-bold text-secondary" : "text-gray-500"}`}
    >
      <Home size={15} /> Beranda
    </button>
    {trail.map((b, i) => (
      <React.Fragment key={b.id}>
        <ChevronRight size={14} className="text-gray-300" />
        <button
          onClick={() => onNavigate(b.id)}
          className={`px-2 py-1 rounded-md hover:bg-gray-100 truncate max-w-[12rem] ${i === trail.length - 1 ? "font-bold text-secondary" : "text-gray-500"}`}
        >
          {b.name}
        </button>
      </React.Fragment>
    ))}
  </nav>
);

const IconAction = ({ label, onClick, icon: Icon, danger }) => (
  <button
    onClick={(e) => {
      e.stopPropagation();
      onClick();
    }}
    aria-label={label}
    title={label}
    className={`p-2 rounded-lg transition ${danger ? "text-red-500 hover:bg-red-50" : "text-gray-500 hover:bg-gray-100 hover:text-primary"}`}
  >
    <Icon size={16} />
  </button>
);

const BerkasMahasiswa = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [params, setParams] = useSearchParams();
  const folderId = params.get("folder") ? Number(params.get("folder")) : null;

  const [data, setData] = useState({ breadcrumb: [], folders: [], files: [], can_manage: false });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [view, setView] = useState(readView);
  const [dragging, setDragging] = useState(false);
  // { type: "upload" | "newFolder" | "renameFolder" | "renameFile" | "move" | "delete", item?, files? }
  const [dialog, setDialog] = useState(null);

  const canManage = data.can_manage;
  const searching = query.trim().length > 0;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = query.trim();
      const r = await axios.get("/api/files", {
        params: q ? { q } : folderId ? { folder_id: folderId } : {},
      });
      setData(r.data);
      setError("");
    } catch (err) {
      if (err.response?.status === 404 && folderId) {
        setParams({});
        return;
      }
      setError(apiError(err, "Gagal memuat daftar berkas."));
    }
    setLoading(false);
  }, [folderId, query, setParams]);

  useEffect(() => {
    // Kotak cari diberi jeda supaya tidak memanggil server di setiap ketukan.
    const t = setTimeout(load, query ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, query]);

  const openFolder = (id) => {
    setQuery("");
    setParams(id ? { folder: String(id) } : {});
  };

  const changeView = (v) => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* preferensi tampilan tidak wajib tersimpan */
    }
  };

  const flash = (msg) => {
    setNotice(msg);
    setTimeout(() => setNotice(""), 3000);
  };

  const close = () => setDialog(null);
  const done = (msg) => {
    close();
    flash(msg);
    load();
  };

  const currentFolderName = data.breadcrumb.length ? data.breadcrumb[data.breadcrumb.length - 1].name : "Beranda";

  const handleUpload = async (files, kategori, setProgress) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("kategori", kategori);
    if (folderId) form.append("folder_id", folderId);
    await axios.post("/api/files", form, {
      onUploadProgress: (e) => e.total && setProgress(Math.round((e.loaded / e.total) * 100)),
    });
    done(`${files.length} berkas berhasil diunggah.`);
  };

  const handleDownload = async (file) => {
    try {
      const r = await axios.get(`/api/files/${file.id}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(r.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("Gagal mengunduh berkas. Mungkin berkas sudah dihapus.");
    }
  };

  const handleDelete = async () => {
    const { item } = dialog;
    try {
      if (item.kind === "folder") await axios.delete(`/api/folders/${item.id}`);
      else await axios.delete(`/api/files/${item.id}`);
      done(item.kind === "folder" ? "Folder dihapus." : "Berkas dihapus.");
    } catch (err) {
      close();
      setError(apiError(err, "Gagal menghapus."));
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer?.files || []);
    if (canManage && !searching && files.length) setDialog({ type: "upload", files });
  };

  const items = [
    ...data.folders.map((f) => ({ ...f, kind: "folder" })),
    ...data.files.map((f) => ({ ...f, kind: "file" })),
  ];

  const actionsFor = (item) => {
    if (item.kind === "folder") {
      return canManage ? (
        <>
          <IconAction label="Ganti nama" icon={Pencil} onClick={() => setDialog({ type: "renameFolder", item })} />
          <IconAction label="Hapus folder" icon={Trash2} danger onClick={() => setDialog({ type: "delete", item })} />
        </>
      ) : null;
    }
    return (
      <>
        <IconAction label="Unduh" icon={Download} onClick={() => handleDownload(item)} />
        {canManage && (
          <>
            <IconAction label="Ganti nama" icon={Pencil} onClick={() => setDialog({ type: "renameFile", item })} />
            <IconAction label="Pindahkan" icon={FolderInput} onClick={() => setDialog({ type: "move", item })} />
            <IconAction label="Hapus berkas" icon={Trash2} danger onClick={() => setDialog({ type: "delete", item })} />
          </>
        )}
      </>
    );
  };

  const activate = (item) => (item.kind === "folder" ? openFolder(item.id) : handleDownload(item));

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar isOpen={sidebarOpen} toggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Berkas Mahasiswa"
          subtitle={
            canManage
              ? "Unggah dan kelola berkas data mahasiswa terbaru untuk preprocessing."
              : "Unduh berkas data mahasiswa yang diunggah BAPSI."
          }
        />

        <main
          className="p-6 space-y-6 max-w-[96rem] w-full mx-auto"
          onDragOver={(e) => {
            if (!canManage || searching) return;
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false);
          }}
          onDrop={onDrop}
        >
          <div className={`relative bg-surface p-6 rounded-2xl shadow-sm border min-h-[480px] transition ${dragging ? "border-primary border-dashed border-2 bg-primary/5" : "border-border"}`}>
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-5">
              <div className="relative w-full lg:max-w-sm">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Cari nama berkas di semua folder"
                  aria-label="Cari berkas"
                  className="w-full pl-9 pr-3 py-2.5 bg-background border border-border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex border border-border rounded-lg overflow-hidden" role="group" aria-label="Tampilan">
                  <button
                    onClick={() => changeView("list")}
                    aria-pressed={view === "list"}
                    aria-label="Tampilan daftar"
                    className={`p-2 ${view === "list" ? "bg-primary text-white" : "text-gray-500 hover:bg-gray-50"}`}
                  >
                    <List size={16} />
                  </button>
                  <button
                    onClick={() => changeView("grid")}
                    aria-pressed={view === "grid"}
                    aria-label="Tampilan kisi"
                    className={`p-2 ${view === "grid" ? "bg-primary text-white" : "text-gray-500 hover:bg-gray-50"}`}
                  >
                    <LayoutGrid size={16} />
                  </button>
                </div>
                {canManage && !searching && (
                  <>
                    <Button variant="secondary" onClick={() => setDialog({ type: "newFolder" })}>
                      <FolderPlus size={16} /> Folder Baru
                    </Button>
                    <Button onClick={() => setDialog({ type: "upload" })}>
                      <UploadCloud size={16} /> Unggah Berkas
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="mb-4 min-h-8">
              {searching ? (
                <p className="text-sm text-gray-500">
                  Hasil pencarian <span className="font-semibold text-secondary">&ldquo;{query.trim()}&rdquo;</span> di semua folder
                </p>
              ) : (
                <Breadcrumb trail={data.breadcrumb} onNavigate={openFolder} />
              )}
            </div>

            {error && (
              <p className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600 flex items-center gap-2">
                <AlertTriangle size={16} className="shrink-0" /> {error}
              </p>
            )}
            {notice && (
              <p role="status" className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-700">
                {notice}
              </p>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-20 text-gray-400">
                <Loader2 className="animate-spin mr-2" size={20} /> Memuat berkas...
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Folder size={48} className="text-gray-200 mb-3" />
                <p className="font-semibold text-gray-600">
                  {searching ? "Tidak ada berkas yang cocok." : "Folder ini masih kosong."}
                </p>
                {canManage && !searching && (
                  <p className="text-sm text-gray-400 mt-1">Seret berkas ke sini atau klik &ldquo;Unggah Berkas&rdquo;.</p>
                )}
              </div>
            ) : view === "grid" ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
                {items.map((item) => {
                  const Icon = item.kind === "folder" ? Folder : fileIcon(item.name);
                  return (
                    <div
                      key={`${item.kind}-${item.id}`}
                      role="button"
                      tabIndex={0}
                      onClick={() => activate(item)}
                      onKeyDown={(e) => e.key === "Enter" && activate(item)}
                      className="group border border-border rounded-xl p-4 hover:border-primary/40 hover:shadow-sm cursor-pointer transition flex flex-col"
                    >
                      <Icon size={36} className={item.kind === "folder" ? "text-amber-500" : "text-primary"} />
                      <p className="mt-3 text-sm font-semibold truncate" title={item.name}>{item.name}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {item.kind === "folder" ? `${item.item_count} item` : formatSize(item.size)}
                      </p>
                      {item.kind === "file" && <div className="mt-2"><KategoriBadge kategori={item.kategori} /></div>}
                      <div className="mt-2 -ml-2 flex flex-wrap">{actionsFor(item)}</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-gray-50 text-xs font-semibold text-gray-500 uppercase">
                      <th scope="col" className="p-3">Nama</th>
                      <th scope="col" className="p-3">Kategori</th>
                      {searching && <th scope="col" className="p-3">Lokasi</th>}
                      <th scope="col" className="p-3">Diunggah</th>
                      <th scope="col" className="p-3">Ukuran</th>
                      <th scope="col" className="p-3 text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((item) => {
                      const Icon = item.kind === "folder" ? Folder : fileIcon(item.name);
                      return (
                        <tr
                          key={`${item.kind}-${item.id}`}
                          onDoubleClick={() => activate(item)}
                          className="hover:bg-gray-50 transition"
                        >
                          <td className="p-3">
                            <button
                              onClick={() => activate(item)}
                              className="flex items-center gap-3 text-left font-medium text-gray-900 hover:text-primary max-w-md"
                            >
                              <Icon size={20} className={`shrink-0 ${item.kind === "folder" ? "text-amber-500" : "text-primary"}`} />
                              <span className="truncate">{item.name}</span>
                            </button>
                          </td>
                          <td className="p-3">
                            {item.kind === "file" ? <KategoriBadge kategori={item.kategori} /> : <span className="text-gray-400 text-xs">Folder · {item.item_count} item</span>}
                          </td>
                          {searching && <td className="p-3 text-gray-500">{item.path || "Beranda"}</td>}
                          <td className="p-3 text-gray-500 whitespace-nowrap">
                            {item.kind === "file" ? (
                              <>
                                {formatDate(item.uploaded_at)}
                                {item.uploaded_by && <span className="block text-xs text-gray-400">{item.uploaded_by}</span>}
                              </>
                            ) : (
                              formatDate(item.created_at)
                            )}
                          </td>
                          <td className="p-3 text-gray-500 whitespace-nowrap">{item.kind === "file" ? formatSize(item.size) : "-"}</td>
                          <td className="p-3">
                            <div className="flex justify-end">{actionsFor(item)}</div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {dragging && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl">
                <div className="bg-surface/95 px-6 py-4 rounded-xl shadow-lg border border-primary text-primary font-semibold flex items-center gap-2">
                  <UploadCloud size={20} /> Lepaskan untuk mengunggah ke &ldquo;{currentFolderName}&rdquo;
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      {dialog?.type === "upload" && (
        <UploadDialog folderName={currentFolderName} initialFiles={dialog.files} onUpload={handleUpload} onClose={close} />
      )}
      {dialog?.type === "newFolder" && (
        <NameDialog
          title="Folder Baru"
          label="Nama folder"
          submitLabel="Buat Folder"
          onClose={close}
          onSubmit={async (name) => {
            await axios.post("/api/folders", { name, parent_id: folderId });
            done(`Folder "${name}" dibuat.`);
          }}
        />
      )}
      {dialog?.type === "renameFolder" && (
        <NameDialog
          title="Ganti Nama Folder"
          label="Nama folder"
          initial={dialog.item.name}
          submitLabel="Simpan"
          onClose={close}
          onSubmit={async (name) => {
            await axios.patch(`/api/folders/${dialog.item.id}`, { name });
            done("Nama folder diperbarui.");
          }}
        />
      )}
      {dialog?.type === "renameFile" && (
        <NameDialog
          title="Ganti Nama Berkas"
          label="Nama berkas (ekstensi dipertahankan otomatis)"
          initial={dialog.item.name}
          submitLabel="Simpan"
          onClose={close}
          onSubmit={async (name) => {
            await axios.patch(`/api/files/${dialog.item.id}`, { name });
            done("Nama berkas diperbarui.");
          }}
        />
      )}
      {dialog?.type === "move" && (
        <MoveDialog
          file={dialog.item}
          onClose={close}
          onMove={async (target) => {
            await axios.patch(`/api/files/${dialog.item.id}`, { folder_id: target });
            done("Berkas dipindahkan.");
          }}
        />
      )}
      <ConfirmDialog
        open={dialog?.type === "delete"}
        title={dialog?.item?.kind === "folder" ? "Hapus Folder?" : "Hapus Berkas?"}
        message={
          dialog?.item?.kind === "folder"
            ? `Folder "${dialog.item.name}" beserta seluruh subfolder dan berkas di dalamnya akan dihapus.`
            : `Berkas "${dialog?.item?.name}" akan dihapus dan tidak bisa lagi diunduh atau dipakai preprocessing.`
        }
        confirmLabel="Ya, Hapus"
        onConfirm={handleDelete}
        onCancel={close}
      />
    </div>
  );
};

export default BerkasMahasiswa;
