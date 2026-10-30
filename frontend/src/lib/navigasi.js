// Halaman batch, detail mahasiswa, dan detail mata kuliah bisa dibuka dari
// chart Hasil Prediksi atau dari Log Riwayat (khusus admin). Asal halaman dan
// filter Sisip/Tidak Sisip dibawa lewat query string, bukan location.state,
// supaya tombol kembali tetap benar setelah refresh atau dibuka di tab baru.

function isAdmin() {
  try {
    return JSON.parse(localStorage.getItem("user"))?.role === "admin";
  } catch {
    return false;
  }
}

// Bawaan "results": Log Riwayat hanya untuk admin, jadi peran lain tidak
// pernah dikembalikan ke sana walaupun URL-nya menyebut from=history.
export function readAsal(search) {
  const q = new URLSearchParams(search);
  return {
    from: q.get("from") === "history" && isAdmin() ? "history" : "results",
    filter: q.get("filter") === "tidak_sisip" ? "tidak_sisip" : "sisip",
  };
}

export function withQuery(path, params) {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  return q ? `${path}?${q}` : path;
}

// Parameter yang diteruskan ke halaman berikutnya; asal bawaan tidak ditulis
// supaya URL dari chart tetap pendek.
export function asalParams(asal) {
  return { filter: asal.filter, from: asal.from === "history" ? "history" : undefined };
}

// Tujuan & label tombol kembali dari halaman batch.
export function kembaliDariBatch(asal) {
  return asal.from === "history"
    ? { to: "/history", label: "Kembali ke Log Riwayat" }
    : { to: "/results", label: "Kembali ke Hasil Prediksi" };
}
