"""Menggabungkan berkas mentah kampus menjadi satu tabel lebar siap latih.

Masukan berupa dua berkas Excel:

1. Berkas PMB  — biodata pendaftar, nilai tes seleksi, dan nilai rapor SMA.
2. Berkas akademik — nilai mata kuliah per semester (format panjang: satu baris
   per mahasiswa per mata kuliah) beserta rekap IPK/SKS dan kolom
   ``Sisip Program`` yang menjadi target.

Keluaran berupa satu baris per mahasiswa dengan kolom identitas, kolom fitur
(biodata, nilai tes, nilai rapor, nilai tiap mata kuliah), kolom pelaporan
(IPK/SKS), dan kolom ``Label``. Bentuk ini sengaja dibuat sama dengan sheet
``TRAIN_SEM*`` yang dipakai pipeline lama sehingga bisa langsung dilatih.

Sheet dikenali dari susunan kolomnya, bukan dari namanya. Berkas dengan satu
sheet per program studi maupun berkas gabungan berisi banyak sheet sama-sama
bisa diproses tanpa perubahan kode.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class PreprocessError(Exception):
    """Kesalahan yang pesannya memang ditujukan untuk pengguna akhir."""


# ---------------------------------------------------------------------------
# Konfigurasi sumber data. Menambah sumber baru cukup dengan menambah SheetSpec
# dan pemetaan nama kolomnya di bawah ini.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SheetSpec:
    key: str
    label: str
    required: tuple


# Urutan penting: spesifikasi yang lebih ketat harus diperiksa lebih dulu karena
# sheet biodata dan sheet nilai tes sama-sama punya kolom 'Nomor Pendaftaran'.
SHEET_SPECS = (
    SheetSpec('akademik', 'nilai mata kuliah per semester',
              ('NIM', 'Nama Mtk', 'Nilai', 'Semester')),
    SheetSpec('nilai_tes', 'nilai tes seleksi masuk',
              ('Nomor Pendaftaran', 'Penalaran Verbal')),
    SheetSpec('nilai_rapor', 'nilai rapor SMA',
              ('Nomor Pendaftaran', 'Mata Pelajaran')),
    SheetSpec('biodata', 'biodata pendaftar',
              ('Nomor Pendaftaran', 'Nama Sekolah')),
)

# Nama kolom keluaran mengikuti pipeline lama (sheet TRAIN_SEM3) supaya model
# lama dan baru memakai kosakata kolom yang sama.
BIODATA_RENAME = {
    'Propinsi': 'Propinsi Asal Lahir',
    'Kabupaten': 'Kabupaten Asal Lahir',
    'Propinsi Sekolah': 'Propinsi Asal Sekolah',
    'Kabupaten Sekolah': 'Kabupaten Asal Sekolah',
    'Nama Sekolah': 'Nama Sekolah',
    'Jurusan Sekolah': 'Jurusan Sekolah',
    'Status Sekolah': 'Profil Sekolah',
    'Nama Jalur': 'Jalur Pendaftaran',
}

TES_RENAME = {
    'Penalaran Verbal': 'Nilai Penalaran Verbal',
    'Kemampuan Numerik': 'Nilai Kemampuan Numerik',
    'Penalaran Mekanik': 'Nilai Penalaran Mekanik',
    'Hubungan Ruang': 'Nilai Hubungan Ruang',
    'Bahasa Inggris': 'Nilai Bahasa Inggris',
    'Rata-Rata Nilai': 'Nilai Final Rata-Rata',
}

RAPOR_VALUE_COLS = {'Kelas 2 Semester 1': '1', 'Kelas 2 Semester 2': '2'}

PMB_KEY = 'Nomor Pendaftaran'
PMB_NIM_KEY = 'Nomor Mahasiswa'

IDENTITY_COLS = ['NIM', 'Nomor PMB', 'Prodi', 'Angkatan']
LABEL_COL = 'Label'
RAW_LABEL_COL = 'Sisip Program'
LABEL_AMAN = 'TIDAK SISIP'
LABEL_RISIKO = 'SISIP'
RAW_LABEL_AMAN = 'tidak sisip program'

# Huruf mutu dari yang terburuk ke terbaik; nilai di luar daftar dianggap
# tidak dikenal dan kalah dari nilai mana pun saat memilih hasil pengulangan.
GRADE_ORDER = ('F', 'E', 'D-', 'D', 'D+', 'C-', 'C', 'C+', 'B-', 'B', 'B+', 'A-', 'A')
GRADE_RANK = {g: i for i, g in enumerate(GRADE_ORDER)}

MISSING_CATEGORICAL = '-'
MAX_SEMESTER_LIMIT = 8


@dataclass
class PreprocessResult:
    df: pd.DataFrame
    prodi: str
    max_semester: int
    feature_cols: list
    report: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pembacaan berkas
# ---------------------------------------------------------------------------

def _read_sheets(file_obj, origin):
    """Baca semua sheet lalu kelompokkan menurut peran yang terdeteksi."""
    try:
        book = pd.ExcelFile(file_obj)
    except Exception as err:
        raise PreprocessError(f"Berkas {origin} tidak dapat dibaca sebagai Excel: {err}")

    found = {}
    for sheet in book.sheet_names:
        df = pd.read_excel(book, sheet_name=sheet)
        df.columns = [str(c).strip() for c in df.columns]
        cols = set(df.columns)
        spec = next((s for s in SHEET_SPECS if cols.issuperset(s.required)), None)
        if spec is None or df.empty:
            continue
        found.setdefault(spec.key, []).append(df)
    return found


def _concat(frames):
    if not frames:
        return None
    return frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)


def _require(sheets, key, origin):
    df = _concat(sheets.get(key))
    if df is None:
        spec = next(s for s in SHEET_SPECS if s.key == key)
        raise PreprocessError(
            f"Berkas {origin} tidak memuat sheet {spec.label}. Sheet tersebut dikenali "
            f"dari kolom wajib: {', '.join(spec.required)}."
        )
    return df


def _clean_key(series):
    return series.astype(str).str.strip()


# ---------------------------------------------------------------------------
# Pengolahan tiap sumber
# ---------------------------------------------------------------------------

def _prodi_unik(biodata):
    return sorted(str(v).strip() for v in biodata['Prodi'].dropna().unique())


def _resolve_prodi(biodata, prodi, nim_akademik):
    """Tentukan program studi yang diproses dan saring biodata ke prodi itu.

    Berkas PMB umumnya berisi semua program studi sekaligus, sedangkan berkas
    akademik disiapkan per program studi. Karena itu, saat prodi tidak dipilih,
    penentuannya tidak diambil dari seluruh isi berkas PMB, melainkan dari
    mahasiswa yang benar-benar muncul di berkas akademik — di situlah program
    studi yang sedang diproses sebetulnya ditentukan."""
    if 'Prodi' not in biodata.columns:
        if not prodi:
            raise PreprocessError("Berkas PMB tidak punya kolom Prodi, jadi Program Studi "
                                  "harus dipilih di halaman ini.")
        biodata = biodata.copy()
        biodata['Prodi'] = prodi
        return biodata, prodi

    if prodi:
        cocok = biodata[biodata['Prodi'].astype(str).str.contains(str(prodi), case=False,
                                                                  na=False, regex=False)]
        if cocok.empty:
            tersedia = _prodi_unik(biodata)
            raise PreprocessError(
                f"Tidak ada data PMB untuk Program Studi {prodi}. Berkas berisi: "
                f"{', '.join(tersedia) if tersedia else 'tidak ada nilai Prodi'}."
            )
        return cocok.reset_index(drop=True), prodi

    milik_berkas = biodata[_clean_key(biodata[PMB_NIM_KEY]).isin(nim_akademik)]
    if milik_berkas.empty:
        raise PreprocessError(
            "Tidak ada satu pun NIM di berkas akademik yang ditemukan di berkas PMB. "
            "Pastikan kedua berkas berasal dari angkatan dan program studi yang sama — "
            "NIM dicocokkan dengan kolom 'Nomor Mahasiswa' di berkas PMB."
        )

    kandidat = _prodi_unik(milik_berkas)
    if len(kandidat) == 1:
        return milik_berkas.reset_index(drop=True), kandidat[0]

    raise PreprocessError(
        "Berkas akademik memuat mahasiswa dari lebih dari satu Program Studi "
        f"({', '.join(kandidat)}). Pilih salah satu di halaman ini, karena hasil "
        "preprocessing dipakai untuk melatih model per program studi."
    )


def _biodata_table(biodata):
    kolom = {k: v for k, v in BIODATA_RENAME.items() if k in biodata.columns}
    keep = [PMB_KEY, PMB_NIM_KEY, 'Prodi'] + list(kolom)
    out = biodata[[c for c in keep if c in biodata.columns]].copy()
    out = out.rename(columns=kolom)
    out['NIM'] = _clean_key(out[PMB_NIM_KEY])
    out[PMB_KEY] = _clean_key(out[PMB_KEY])
    return out.drop(columns=[PMB_NIM_KEY]).drop_duplicates(subset=['NIM'], keep='first')


def _tes_table(tes):
    if tes is None:
        return None
    kolom = {k: v for k, v in TES_RENAME.items() if k in tes.columns}
    out = tes[[PMB_KEY] + list(kolom)].rename(columns=kolom).copy()
    out[PMB_KEY] = _clean_key(out[PMB_KEY])
    for c in kolom.values():
        out[c] = pd.to_numeric(out[c], errors='coerce')
    return out.groupby(PMB_KEY, as_index=False).mean(numeric_only=True)


def _rapor_table(rapor):
    """Ubah nilai rapor dari format panjang menjadi kolom `<Mapel>_<semester>`."""
    if rapor is None:
        return None
    value_cols = [c for c in RAPOR_VALUE_COLS if c in rapor.columns]
    if not value_cols:
        return None

    long = rapor[[PMB_KEY, 'Mata Pelajaran'] + value_cols].melt(
        id_vars=[PMB_KEY, 'Mata Pelajaran'], var_name='_semester', value_name='_nilai')
    long[PMB_KEY] = _clean_key(long[PMB_KEY])
    long['_kolom'] = (long['Mata Pelajaran'].astype(str).str.strip() + '_'
                      + long['_semester'].map(RAPOR_VALUE_COLS))
    long['_nilai'] = pd.to_numeric(long['_nilai'], errors='coerce')
    long = long.dropna(subset=['_nilai'])
    if long.empty:
        return None

    wide = long.pivot_table(index=PMB_KEY, columns='_kolom', values='_nilai', aggfunc='mean')
    wide.columns.name = None
    return wide.reset_index()


def _best_attempt(akademik):
    """Satu baris per (mahasiswa, mata kuliah), memakai nilai terbaik dari
    pengulangan yang ada."""
    df = akademik.copy()
    df['Nama Mtk'] = df['Nama Mtk'].astype(str).str.strip()
    df['Nilai'] = df['Nilai'].astype(str).str.strip().str.upper()
    df['_peringkat'] = df['Nilai'].map(GRADE_RANK)
    df = df.sort_values('_peringkat', na_position='first')
    return df.groupby(['NIM', 'Nama Mtk'], as_index=False).last()


def _akademik_tables(akademik, max_semester, nim_prodi):
    """Kembalikan (rekap per mahasiswa, matriks nilai mata kuliah).

    Disaring lebih dulu ke NIM milik program studi yang diproses supaya matriks
    mata kuliah hanya berisi mata kuliah prodi tersebut, bukan gabungan semua
    prodi yang kebetulan ada di satu berkas."""
    df = akademik.copy()
    df['NIM'] = _clean_key(df['NIM'])
    df = df[df['NIM'].isin(nim_prodi)]
    if df.empty:
        raise PreprocessError(
            "Tidak ada mahasiswa yang cocok antara berkas akademik dan berkas PMB. "
            "Pastikan kedua berkas berasal dari program studi yang sama — NIM "
            "dicocokkan dengan kolom 'Nomor Mahasiswa' di berkas PMB."
        )
    df['Semester'] = pd.to_numeric(df.get('Semester'), errors='coerce')
    df = df[df['Semester'].notna()]

    lingkup = df[df['Semester'] <= max_semester]
    if lingkup.empty:
        raise PreprocessError(f"Tidak ada baris akademik sampai semester {max_semester}.")

    nilai = _best_attempt(lingkup)
    matriks = nilai.pivot(index='NIM', columns='Nama Mtk', values='Nilai')
    matriks.columns.name = None

    rekap = pd.DataFrame(index=matriks.index)
    rekap['Angkatan'] = df.groupby('NIM')['Angkatan'].first()

    # IPK kumulatif tiap semester diambil apa adanya dari berkas sumber.
    if 'IPK Per Semester' in df.columns:
        ipk = (lingkup.drop_duplicates(subset=['NIM', 'Semester'])
                      .pivot(index='NIM', columns='Semester', values='IPK Per Semester'))
        for smt in range(1, max_semester + 1):
            if smt in ipk.columns:
                rekap[f'IPK {smt}'] = pd.to_numeric(ipk[smt], errors='coerce')

    if 'SKS Lulus Per Semester' in df.columns:
        sks = (lingkup.drop_duplicates(subset=['NIM', 'Semester'])
                      .pivot(index='NIM', columns='Semester', values='SKS Lulus Per Semester'))
        tersedia = [s for s in sks.columns if s <= max_semester]
        if tersedia:
            rekap[f'Total SKS {max_semester}'] = pd.to_numeric(
                sks[max(tersedia)], errors='coerce')

    if RAW_LABEL_COL in df.columns:
        mentah = df.dropna(subset=[RAW_LABEL_COL]).groupby('NIM')[RAW_LABEL_COL].first()
        rekap[LABEL_COL] = mentah.reindex(rekap.index).map(
            lambda v: LABEL_AMAN if str(v).strip().lower() == RAW_LABEL_AMAN else LABEL_RISIKO
        ).where(mentah.reindex(rekap.index).notna())

    return rekap.reset_index(), matriks.reset_index()


# ---------------------------------------------------------------------------
# Alur utama
# ---------------------------------------------------------------------------

def build_training_table(pmb_file, akademik_file, prodi=None, max_semester=3):
    try:
        max_semester = int(max_semester)
    except (TypeError, ValueError):
        raise PreprocessError("Batas semester harus berupa angka.")
    if not 1 <= max_semester <= MAX_SEMESTER_LIMIT:
        raise PreprocessError(f"Batas semester harus antara 1 dan {MAX_SEMESTER_LIMIT}.")

    sheet_pmb = _read_sheets(pmb_file, 'PMB')
    sheet_akademik = _read_sheets(akademik_file, 'akademik')

    biodata = _require(sheet_pmb, 'biodata', 'PMB')
    akademik = _require(sheet_akademik, 'akademik', 'akademik')
    tes = _concat(sheet_pmb.get('nilai_tes'))
    rapor = _concat(sheet_pmb.get('nilai_rapor'))

    nim_akademik = set(_clean_key(akademik['NIM']))
    biodata, prodi_label = _resolve_prodi(biodata, prodi, nim_akademik)
    biodata = _biodata_table(biodata)

    rekap, matriks = _akademik_tables(akademik, max_semester, set(biodata['NIM']))
    jumlah_matkul = len(matriks.columns) - 1

    df = rekap.merge(matriks, on='NIM', how='left').merge(biodata, on='NIM', how='inner')
    for tabel in (_tes_table(tes), _rapor_table(rapor)):
        if tabel is not None:
            df = df.merge(tabel, on=PMB_KEY, how='left')

    df = df.rename(columns={PMB_KEY: 'Nomor PMB'})
    df['Prodi'] = prodi_label

    if LABEL_COL not in df.columns:
        raise PreprocessError(
            f"Berkas akademik tidak memuat kolom '{RAW_LABEL_COL}' sebagai target, "
            "sehingga data latih tidak bisa dibentuk."
        )
    tanpa_label = int(df[LABEL_COL].isna().sum())
    df = df[df[LABEL_COL].notna()]
    if df.empty:
        raise PreprocessError(
            f"Tidak ada mahasiswa dengan kolom '{RAW_LABEL_COL}' terisi, jadi tidak ada "
            "baris berlabel yang bisa dilatih."
        )

    df = _fill_missing(df)
    laporan_cols = [c for c in df.columns
                    if c.startswith('IPK ') or c.startswith('Total SKS ')]
    kandidat = [c for c in df.columns
                if c not in IDENTITY_COLS + laporan_cols + [LABEL_COL]]
    # Kolom yang isinya seragam (mis. mata kuliah yang tak seorang pun ambil)
    # tidak membawa informasi apa pun dan hanya memperbesar grid masukan CNN.
    feature_cols = [c for c in kandidat if df[c].nunique(dropna=False) > 1]
    df = df[IDENTITY_COLS + feature_cols + laporan_cols + [LABEL_COL]]

    return PreprocessResult(
        df=df.reset_index(drop=True),
        prodi=prodi_label,
        max_semester=max_semester,
        feature_cols=feature_cols,
        report={
            'mahasiswa': len(df),
            'kolom': len(df.columns),
            'jumlah_fitur': len(feature_cols),
            'jumlah_matkul': jumlah_matkul,
            'kolom_seragam_dibuang': len(kandidat) - len(feature_cols),
            'tanpa_label': tanpa_label,
            'distribusi_label': {str(k): int(v) for k, v in
                                 df[LABEL_COL].value_counts().items()},
            'angkatan': sorted(str(a) for a in df['Angkatan'].dropna().unique()),
            'sumber_terdeteksi': {
                'PMB': sorted(sheet_pmb.keys()),
                'akademik': sorted(sheet_akademik.keys()),
            },
        },
    )


def _fill_missing(df):
    """Kolom huruf mutu/kategori diisi '-' (tidak diambil), kolom angka diisi 0 —
    sama seperti berkas latih lama supaya distribusi fiturnya sebanding."""
    out = df.copy()
    for col in out.columns:
        if col == LABEL_COL:
            continue
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].fillna(0)
        else:
            out[col] = out[col].astype(object).where(out[col].notna(), MISSING_CATEGORICAL)
            out[col] = out[col].replace({'nan': MISSING_CATEGORICAL, '': MISSING_CATEGORICAL})
    return out


def preview_records(df, limit=10):
    return df.head(limit).replace({np.nan: None}).to_dict(orient='records')
