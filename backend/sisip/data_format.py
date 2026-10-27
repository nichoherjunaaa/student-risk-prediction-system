"""Format berkas mentah kampus (PMB & akademik), daftar prodi, dan tabel nilai mutu.

Sebelumnya semua ini ditulis langsung di kode, sehingga perubahan nama kolom di
berkas PMB/SIA berarti mengedit kode dan deploy ulang. Sekarang nilai bawaannya
ada di DEFAULT_FORMAT, dan admin bisa menimpanya dari halaman Format Data;
versi yang disimpan admin tersimpan di tabel app_settings.

Yang diatur di sini hanya nama kolom di berkas *sumber* (sisi kiri pemetaan)
dan nama fitur hasilnya. Skema kolom internal (NIM, Label, IPK n, ...) tetap di
constants.py karena menjadi kontrak dengan model yang sudah dilatih."""
import copy
import json
import numbers

from .constants import RESERVED_COLS

SETTINGS_KEY = 'data_format'

DEFAULT_FORMAT = {
    'prodi': ['Informatika', 'Matematika', 'Teknik Mesin', 'Teknik Elektro'],
    'pmb': {
        'kolom_no_pendaftaran': 'Nomor Pendaftaran',
        'kolom_nim': 'Nomor Mahasiswa',
        'kolom_prodi': 'Prodi',
        'penanda_biodata': 'Nama Sekolah',
        'biodata': [
            {'sumber': 'Propinsi', 'fitur': 'Propinsi Asal Lahir'},
            {'sumber': 'Kabupaten', 'fitur': 'Kabupaten Asal Lahir'},
            {'sumber': 'Propinsi Sekolah', 'fitur': 'Propinsi Asal Sekolah'},
            {'sumber': 'Kabupaten Sekolah', 'fitur': 'Kabupaten Asal Sekolah'},
            {'sumber': 'Nama Sekolah', 'fitur': 'Nama Sekolah'},
            {'sumber': 'Jurusan Sekolah', 'fitur': 'Jurusan Sekolah'},
            {'sumber': 'Status Sekolah', 'fitur': 'Profil Sekolah'},
            {'sumber': 'Nama Jalur', 'fitur': 'Jalur Pendaftaran'},
        ],
        'penanda_tes': 'Penalaran Verbal',
        'nilai_tes': [
            {'sumber': 'Penalaran Verbal', 'fitur': 'Nilai Penalaran Verbal'},
            {'sumber': 'Kemampuan Numerik', 'fitur': 'Nilai Kemampuan Numerik'},
            {'sumber': 'Penalaran Mekanik', 'fitur': 'Nilai Penalaran Mekanik'},
            {'sumber': 'Hubungan Ruang', 'fitur': 'Nilai Hubungan Ruang'},
            {'sumber': 'Bahasa Inggris', 'fitur': 'Nilai Bahasa Inggris'},
            {'sumber': 'Rata-Rata Nilai', 'fitur': 'Nilai Final Rata-Rata'},
        ],
        'kolom_mapel': 'Mata Pelajaran',
        'nilai_rapor': [
            {'sumber': 'Kelas 2 Semester 1', 'akhiran': '1'},
            {'sumber': 'Kelas 2 Semester 2', 'akhiran': '2'},
        ],
    },
    'akademik': {
        'kolom_nim': 'NIM',
        'kolom_matkul': 'Nama Mtk',
        'kolom_nilai': 'Nilai',
        'kolom_semester': 'Semester',
        'kolom_angkatan': 'Angkatan',
        'kolom_ipk': 'IPK Per Semester',
        'kolom_sks_lulus': 'SKS Lulus Per Semester',
        'kolom_label': 'Sisip Program',
        'label_aman': ['tidak sisip program'],
    },
    'nilai': {
        # Urutan = peringkat, dari terbaik ke terburuk. Dipakai memilih nilai
        # terbaik saat mata kuliah diulang.
        'huruf': [
            {'huruf': 'A', 'bobot': 4.0, 'lulus': True},
            {'huruf': 'A-', 'bobot': 3.7, 'lulus': True},
            {'huruf': 'B+', 'bobot': 3.3, 'lulus': True},
            {'huruf': 'B', 'bobot': 3.0, 'lulus': True},
            {'huruf': 'B-', 'bobot': 2.7, 'lulus': True},
            {'huruf': 'C+', 'bobot': 2.3, 'lulus': True},
            {'huruf': 'C', 'bobot': 2.0, 'lulus': True},
            {'huruf': 'C-', 'bobot': 1.7, 'lulus': True},
            {'huruf': 'D+', 'bobot': 1.3, 'lulus': False},
            {'huruf': 'D', 'bobot': 1.0, 'lulus': False},
            {'huruf': 'D-', 'bobot': 0.7, 'lulus': False},
            {'huruf': 'E', 'bobot': 0.0, 'lulus': False},
            {'huruf': 'F', 'bobot': 0.0, 'lulus': False},
            {'huruf': 'T', 'bobot': 0.0, 'lulus': False},
        ],
        # Berkas akademik tidak memuat SKS per mata kuliah, jadi dipakai angka rata.
        'sks_per_matkul': 3,
    },
}

_MAX_TEXT = 100


class DataFormat:
    """Bentuk siap pakai dari dict format: pemetaan, spesifikasi sheet, dan
    tabel nilai mutu dalam struktur yang langsung dipakai kode pengolah."""

    def __init__(self, raw):
        self.raw = raw
        self.prodi = list(raw['prodi'])
        pmb, ak, nilai = raw['pmb'], raw['akademik'], raw['nilai']

        self.pmb_key = pmb['kolom_no_pendaftaran']
        self.pmb_nim = pmb['kolom_nim']
        self.pmb_prodi = pmb['kolom_prodi']
        self.pmb_mapel = pmb['kolom_mapel']
        self.biodata_rename = {m['sumber']: m['fitur'] for m in pmb['biodata']}
        self.tes_rename = {m['sumber']: m['fitur'] for m in pmb['nilai_tes']}
        self.rapor_value_cols = {m['sumber']: m['akhiran'] for m in pmb['nilai_rapor']}

        self.ak = dict(ak)
        self.label_aman = {str(v).strip().lower() for v in ak['label_aman']}

        huruf = nilai['huruf']
        # Peringkat: makin besar makin baik.
        self.grade_rank = {h['huruf']: len(huruf) - i for i, h in enumerate(huruf)}
        self.grade_points = {h['huruf']: float(h['bobot']) for h in huruf}
        self.grade_pass = {h['huruf'] for h in huruf if h['lulus']}
        self.grade_fail = {h['huruf'] for h in huruf if not h['lulus']}
        self.sks_per_matkul = int(nilai['sks_per_matkul'])

    def sheet_specs(self):
        """(kunci, label, kolom_wajib). Sheet dikenali dari kolom wajibnya.
        Urutan penting: yang lebih ketat diperiksa lebih dulu karena sheet biodata
        dan sheet nilai tes sama-sama punya kolom nomor pendaftaran."""
        ak = self.ak
        return (
            ('akademik', 'nilai mata kuliah per semester',
             (ak['kolom_nim'], ak['kolom_matkul'], ak['kolom_nilai'], ak['kolom_semester'])),
            ('nilai_tes', 'nilai tes seleksi masuk', (self.pmb_key, self.raw['pmb']['penanda_tes'])),
            ('nilai_rapor', 'nilai rapor SMA', (self.pmb_key, self.pmb_mapel)),
            ('biodata', 'biodata pendaftar', (self.pmb_key, self.raw['pmb']['penanda_biodata'])),
        )


def default_format():
    return copy.deepcopy(DEFAULT_FORMAT)


def merge_with_default(stored):
    """Format tersimpan ditimpakan ke bawaan per bagian, supaya kunci baru yang
    ditambahkan di versi aplikasi berikutnya tetap punya nilai."""
    out = default_format()
    for section, value in (stored or {}).items():
        if section not in out:
            continue
        if isinstance(out[section], dict) and isinstance(value, dict):
            out[section].update({k: v for k, v in value.items() if k in out[section]})
        else:
            out[section] = value
    return out


# ---------------------------------------------------------------------------
# Validasi
# ---------------------------------------------------------------------------

def _text(value):
    return value.strip() if isinstance(value, str) else ''


def validate_format(data):
    """Kembalikan (format_bersih, daftar_error). Semua teks di-trim. Format hanya
    disimpan bila daftar error kosong."""
    errors = []
    if not isinstance(data, dict):
        return None, ['Format harus berupa objek JSON.']
    data = merge_with_default(data)

    def need_text(section, key, label):
        val = _text(data[section].get(key))
        if not val:
            errors.append(f'{label} wajib diisi.')
        elif len(val) > _MAX_TEXT:
            errors.append(f'{label} maksimal {_MAX_TEXT} karakter.')
        data[section][key] = val
        return val

    def text_list(values, label, min_len=1):
        if not isinstance(values, list):
            errors.append(f'{label} harus berupa daftar.')
            return []
        out, seen = [], set()
        for v in values:
            v = _text(v)
            if not v:
                continue
            if v.lower() in seen:
                errors.append(f'{label}: "{v}" ditulis lebih dari sekali.')
                continue
            seen.add(v.lower())
            out.append(v)
        if len(out) < min_len:
            errors.append(f'{label} minimal berisi {min_len} nilai.')
        return out

    def pair_list(values, right, label, check_reserved):
        if not isinstance(values, list):
            errors.append(f'{label} harus berupa daftar.')
            return []
        out, kiri, kanan = [], set(), set()
        for i, m in enumerate(values, start=1):
            m = m if isinstance(m, dict) else {}
            s, r = _text(m.get('sumber')), _text(m.get(right))
            if not s and not r:
                continue
            if not s or not r:
                errors.append(f'{label} baris {i}: kedua kolom wajib diisi.')
                continue
            if s.lower() in kiri:
                errors.append(f'{label}: kolom sumber "{s}" ditulis lebih dari sekali.')
            if r.lower() in kanan:
                errors.append(f'{label}: "{r}" dipakai lebih dari sekali.')
            if check_reserved and r in RESERVED_COLS:
                errors.append(f'{label}: "{r}" adalah nama kolom sistem dan tidak boleh dipakai sebagai fitur.')
            kiri.add(s.lower())
            kanan.add(r.lower())
            out.append({'sumber': s, right: r})
        return out

    data['prodi'] = text_list(data.get('prodi'), 'Daftar Program Studi')

    for key, label in (('kolom_no_pendaftaran', 'Kolom nomor pendaftaran (PMB)'),
                       ('kolom_nim', 'Kolom NIM (PMB)'),
                       ('kolom_prodi', 'Kolom program studi (PMB)'),
                       ('penanda_biodata', 'Kolom penanda sheet biodata'),
                       ('penanda_tes', 'Kolom penanda sheet nilai tes'),
                       ('kolom_mapel', 'Kolom mata pelajaran (rapor)')):
        need_text('pmb', key, label)
    pmb = data['pmb']
    pmb['biodata'] = pair_list(pmb.get('biodata'), 'fitur', 'Kolom biodata', True)
    pmb['nilai_tes'] = pair_list(pmb.get('nilai_tes'), 'fitur', 'Kolom nilai tes', True)
    pmb['nilai_rapor'] = pair_list(pmb.get('nilai_rapor'), 'akhiran', 'Kolom nilai rapor', False)
    if pmb['penanda_biodata'] == pmb['penanda_tes']:
        errors.append('Kolom penanda sheet biodata dan nilai tes harus berbeda, '
                      'kalau tidak kedua sheet tidak bisa dibedakan.')

    for key, label in (('kolom_nim', 'Kolom NIM (akademik)'),
                       ('kolom_matkul', 'Kolom nama mata kuliah'),
                       ('kolom_nilai', 'Kolom nilai huruf'),
                       ('kolom_semester', 'Kolom semester'),
                       ('kolom_angkatan', 'Kolom angkatan'),
                       ('kolom_ipk', 'Kolom IPK per semester'),
                       ('kolom_sks_lulus', 'Kolom SKS lulus per semester'),
                       ('kolom_label', 'Kolom label sisip')):
        need_text('akademik', key, label)
    data['akademik']['label_aman'] = text_list(data['akademik'].get('label_aman'),
                                               'Nilai label "tidak sisip"')

    nilai = data['nilai']
    huruf_in = nilai.get('huruf') if isinstance(nilai.get('huruf'), list) else []
    huruf, seen = [], set()
    for i, h in enumerate(huruf_in, start=1):
        h = h if isinstance(h, dict) else {}
        kode = _text(h.get('huruf')).upper()
        if not kode:
            continue
        if kode in seen:
            errors.append(f'Nilai huruf "{kode}" ditulis lebih dari sekali.')
            continue
        bobot = h.get('bobot')
        if isinstance(bobot, str):
            try:
                bobot = float(bobot.replace(',', '.'))
            except ValueError:
                bobot = None
        if not isinstance(bobot, numbers.Number) or isinstance(bobot, bool) or not 0 <= bobot <= 10:
            errors.append(f'Bobot nilai "{kode}" harus angka 0 sampai 10.')
            bobot = 0.0
        seen.add(kode)
        huruf.append({'huruf': kode, 'bobot': round(float(bobot), 2), 'lulus': bool(h.get('lulus'))})
    if len(huruf) < 2:
        errors.append('Tabel nilai huruf minimal berisi 2 nilai.')
    elif not any(h['lulus'] for h in huruf) or all(h['lulus'] for h in huruf):
        errors.append('Tabel nilai huruf harus memuat nilai lulus dan nilai tidak lulus.')
    nilai['huruf'] = huruf

    sks = nilai.get('sks_per_matkul')
    try:
        sks = int(sks)
    except (TypeError, ValueError):
        sks = None
    if sks is None or not 1 <= sks <= 12:
        errors.append('SKS per mata kuliah harus bilangan bulat 1 sampai 12.')
        sks = DEFAULT_FORMAT['nilai']['sks_per_matkul']
    nilai['sks_per_matkul'] = sks

    return data, errors


# ---------------------------------------------------------------------------
# Penyimpanan (tabel app_settings)
# ---------------------------------------------------------------------------

def load_format_row(conn):
    """(format_lengkap, metadata) dari database; bawaan bila belum pernah disimpan."""
    row = conn.execute(
        "SELECT s.value, s.updated_at, u.name FROM app_settings s "
        "LEFT JOIN users u ON u.id = s.updated_by WHERE s.key = ?", (SETTINGS_KEY,)).fetchone()
    if not row:
        return default_format(), {'customized': False, 'updated_at': None, 'updated_by': None}
    try:
        stored = json.loads(row[0])
    except ValueError:
        stored = {}
    return merge_with_default(stored), {'customized': True, 'updated_at': row[1], 'updated_by': row[2]}


def save_format(conn, fmt, user_id, now):
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
        (SETTINGS_KEY, json.dumps(fmt, ensure_ascii=False), now, user_id))


def reset_format(conn):
    conn.execute("DELETE FROM app_settings WHERE key = ?", (SETTINGS_KEY,))
