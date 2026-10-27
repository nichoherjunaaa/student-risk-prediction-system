"""Skema kolom internal: nama kolom pada data latih/uji yang dibentuk sistem.

Berbeda dengan nama kolom berkas mentah (lihat data_format.py, bisa diubah admin),
nilai di sini adalah kontrak antara preprocessing, training, template, dan
prediksi. Model yang sudah dilatih menyimpan nama-nama ini, jadi mengubahnya
berarti semua model lama harus dilatih ulang."""
import re

# Nama sheet berkas Excel yang dihasilkan/dibaca sistem.
TRAIN_SHEET_PREFIX = 'TRAIN_SEM'
TRAIN_SHEET = 'TRAIN_SEM3'
TEST_SHEET = 'TEST_SEM3'

# Kolom target dan nilainya.
LABEL_COL = 'Label'
LABEL_AMAN = 'TIDAK SISIP'
LABEL_RISIKO = 'SISIP'


def is_risk_label(label):
    """Model lama memakai label lain ('1', 'TIDAK LOLOS', 'AT RISK'), jadi
    semuanya tetap dikenali sebagai berisiko."""
    s = str(label).strip().upper()
    return s == LABEL_RISIKO or 'TIDAK LOLOS' in s or s == '1' or 'AT RISK' in s


# Kolom identitas hasil preprocessing (urutan = urutan kolom di berkas latih).
IDENTITY_COLS = ['NIM', 'Nomor PMB', 'Prodi', 'Angkatan']

# Kolom identitas/rekap pada template prediksi.
TEMPLATE_IDENTITY_COLS = [
    'NIM', 'Nomor PMB', 'Nama', 'Prodi', 'Angkatan', 'Semester',
    'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3',
]

# Kolom yang bukan fitur model saat training.
TRAIN_ID_COLS = ('NIM', 'Nomor PMB', 'Nomor Pendaftaran', 'Nama', 'Prodi', 'Angkatan', 'Semester')
_REPORTING_COL_RE = re.compile(r'^(IPK|IPS|Total SKS|SKS Lulus|SKS Tidak Lulus)\s*\d*$',
                               re.IGNORECASE)


def is_reporting_col(col):
    """IPK/SKS hanya untuk laporan, bukan fitur."""
    return bool(_REPORTING_COL_RE.match(str(col).strip()))


def non_feature_columns(columns):
    return [c for c in columns if c in TRAIN_ID_COLS or is_reporting_col(c)]


# Kolom berkas prediksi yang tidak mungkin berisi nilai mata kuliah, dilewati
# saat menyusun daftar mata kuliah lulus/tidak lulus di detail mahasiswa.
NON_MATKUL_COLS = set(TEMPLATE_IDENTITY_COLS) | {
    'Nomor Pendaftaran', 'Nama Mahasiswa', LABEL_COL,
}

# Nama kolom internal yang tidak boleh dipakai sebagai nama fitur hasil
# pemetaan kolom, karena sudah punya arti lain di data latih.
RESERVED_COLS = set(IDENTITY_COLS) | {LABEL_COL, 'Nama', 'Semester'}
