// Satu kamus istilah peran untuk seluruh aplikasi. Sebelumnya tiap halaman
// menebak sendiri ("DPA", "Dosen", "User"), sehingga akun Kaprodi bisa muncul
// sebagai DPA di sidebar dan sebagai "Dosen" di tabel pengguna.

export const ROLE_LABELS = {
  admin: "Super Admin",
  kaprodi: "Kaprodi",
  dekan: "Dekan",
  dpa: "DPA",
};

export const ROLE_OPTIONS = [
  { value: "dpa", label: "Dosen Pembimbing Akademik (DPA)" },
  { value: "kaprodi", label: "Kepala Program Studi (Kaprodi)" },
  { value: "dekan", label: "Dekan" },
];

export function roleLabel(role) {
  if (!role) return "Pengguna";
  return ROLE_LABELS[role] || String(role);
}
