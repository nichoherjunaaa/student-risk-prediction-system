import axios from "axios";

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
    if (error.response?.status === 401) {
      localStorage.removeItem("user");
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export default axios;
