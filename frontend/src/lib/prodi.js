import { useEffect, useState } from "react";
import axios from "axios";

// Daftar program studi diatur admin di menu Format Data dan diambil dari
// /api/prodi. Untuk akun yang terikat prodi (DPA/Kaprodi), server hanya
// mengirim prodinya sendiri beserta `locked`, dan halaman tidak menawarkan
// pilihan prodi. Daftar di bawah hanya cadangan selama server belum menjawab.
const FALLBACK = { prodi: ["Informatika", "Matematika", "Teknik Mesin", "Teknik Elektro"], locked: null };

let cache = null;
let pending = null;
const listeners = new Set();

function publish(value) {
  cache = value;
  listeners.forEach((fn) => fn(value));
}

function fetchScope() {
  if (!pending) {
    pending = axios
      .get("/api/prodi")
      .then((r) => publish({ prodi: r.data.prodi, locked: r.data.locked || null }))
      .catch(() => {})
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}

// Dipanggil setelah admin menyimpan Format Data, supaya halaman lain langsung
// memakai daftar yang baru.
export function setProdiCache(list) {
  publish({ prodi: list, locked: cache?.locked || null });
}

// Dipanggil saat logout: user berikutnya di tab yang sama bisa punya prodi lain.
export function resetProdiCache() {
  cache = null;
}

export function useProdiScope() {
  const [scope, setScope] = useState(cache || FALLBACK);
  useEffect(() => {
    listeners.add(setScope);
    if (!cache) fetchScope();
    else setScope(cache);
    return () => listeners.delete(setScope);
  }, []);
  return { list: scope.prodi, locked: scope.locked };
}

export function useProdiList() {
  return useProdiScope().list;
}
