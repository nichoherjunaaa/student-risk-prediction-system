// Semua kunci localStorage yang terikat ke satu sesi login. Hasil prediksi
// terakhir ikut dibersihkan supaya user berikutnya di browser yang sama tidak
// melihat hasil milik user sebelumnya.
const SESSION_KEYS = ["user", "token", "loginTime", "lastPrediction", "lastProdi"];

export function clearSession() {
  SESSION_KEYS.forEach((key) => localStorage.removeItem(key));
}
