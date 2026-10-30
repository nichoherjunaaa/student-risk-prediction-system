// IPK & SKS di detail prediksi hanya tersedia sampai batas semester data
// (details.semester). Detail lama belum mencatatnya: semesternya diambil dari
// batch, dan batch yang lebih lama lagi selalu semester 3. IPK/SKS di luar
// batas itu dulu tersimpan sebagai 0, jadi tidak boleh ditampilkan.

export function detailSemester(details = {}, batchSemester) {
  for (const v of [details.semester, batchSemester]) {
    const n = Number(v);
    if (Number.isInteger(n) && n > 0) return n;
  }
  return 3;
}

const angka = (v) => (typeof v === "number" ? v : null);

export function ipkSemester(details = {}, k) {
  return angka(details[`ipk${k}`]);
}

export function totalSks(details = {}, semester) {
  if ("total_sks" in details) return angka(details.total_sks);
  return angka(details[`sks${semester}`]);
}

export const formatIpk = (v) => (v === null ? "-" : v.toFixed(2));
export const formatSks = (v) => (v === null ? "-" : String(v));
