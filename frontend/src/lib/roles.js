// Satu kamus istilah peran untuk seluruh aplikasi. Sebelumnya tiap halaman
// menebak sendiri ("DPA", "Dosen", "User"), sehingga akun Kaprodi bisa muncul
// sebagai DPA di sidebar dan sebagai "Dosen" di tabel pengguna.

export const ROLE_LABELS = {
  admin: "Super Admin",
  kaprodi: "Kaprodi",
  dekan: "Dekan",
  dpa: "DPA",
  bapsi: "BAPSI",
};

export const ROLE_OPTIONS = [
  { value: "dpa", label: "Dosen Pembimbing Akademik (DPA)" },
  { value: "kaprodi", label: "Kepala Program Studi (Kaprodi)" },
  { value: "dekan", label: "Dekan" },
  { value: "bapsi", label: "BAPSI (Pengelola Berkas Mahasiswa)" },
  { value: "admin", label: "Super Admin" },
];

// Harus sama dengan PREDIKSI_ROLES / FILE_MANAGER_ROLES di backend/sisip/config.py.
export const PREDIKSI_ROLES = ["admin", "dpa", "kaprodi", "dekan"];
export const FILE_MANAGER_ROLES = ["bapsi", "admin"];
// Harus sama dengan PRODI_REQUIRED_ROLES / PRODI_OPTIONAL_ROLES di backend/sisip/config.py.
export const PRODI_REQUIRED_ROLES = ["dpa", "kaprodi"];
export const PRODI_OPTIONAL_ROLES = ["dekan"];

export function roleLabel(role) {
  if (!role) return "Pengguna";
  return ROLE_LABELS[role] || String(role);
}

// Halaman pertama setelah login, dan tujuan pengalihan saat pengguna membuka
// halaman yang bukan untuk perannya.
export function homePath(role) {
  if (role === "admin") return "/admin/model";
  if (role === "bapsi") return "/berkas";
  return "/upload";
}
