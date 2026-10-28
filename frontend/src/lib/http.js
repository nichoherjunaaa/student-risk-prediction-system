import axios from "axios";
import { clearSession } from "./session";

// Satu tempat untuk aturan autentikasi HTTP di sisi klien:
//  - lampirkan Bearer token dari localStorage ke setiap permintaan /api
//  - saat backend membalas 401 (token kedaluwarsa / hilang), bersihkan sesi
//    dan lempar pengguna ke halaman login.
// Semua halaman memakai singleton `axios` default, jadi cukup diatur sekali di sini
// (diimpor dari main.jsx).

axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 dari SSO berarti link SIA ditolak, bukan sesi habis: halaman SsoSia
    // yang menampilkan pesannya.
    const fromSso = error.config?.url?.startsWith("/api/sso/");
    if (error.response?.status === 401 && !fromSso) {
      clearSession();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export default axios;
