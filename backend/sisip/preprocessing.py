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
bisa diproses tanpa perubahan kode. Nama kolom berkas mentah diatur lewat
DataFormat (data_format.py), bukan ditulis di modul ini.
"""

import csv
import io
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .constants import IDENTITY_COLS, LABEL_AMAN, LABEL_COL, LABEL_RISIKO
from .data_format import DataFormat, default_format


class PreprocessError(Exception):
    """Kesalahan yang pesannya memang ditujukan untuk pengguna akhir."""


# ---------------------------------------------------------------------------
# Nama kolom internal. Nama kolom di berkas mentah bisa diatur admin (lihat
# data_format.py); begitu sheet dikenali, kolomnya langsung diganti ke nama
# internal di bawah ini, jadi sisa modul tidak bergantung pada format berkas.
# ---------------------------------------------------------------------------

PMB_KEY = 'Nomor Pendaftaran'
PMB_NIM_KEY = 'Nomor Mahasiswa'
PRODI_COL = 'Prodi'
MAPEL_COL = 'Mata Pelajaran'
AK_NIM, AK_MATKUL, AK_NILAI, AK_SEMESTER, AK_ANGKATAN = 'NIM', 'Nama Mtk', 'Nilai', 'Semester', 'Angkatan'
AK_IPK, AK_SKS, AK_LABEL = 'IPK Per Semester', 'SKS Lulus Per Semester', 'Sisip Program'

MISSING_CATEGORICAL = '-'
MAX_SEMESTER_LIMIT = 8


def _source_rename(fmt, key):
    """Pemetaan kolom berkas mentah -> nama internal untuk satu jenis sheet."""
    ak = fmt.ak
    if key == 'akademik':
        return {ak['kolom_nim']: AK_NIM, ak['kolom_matkul']: AK_MATKUL, ak['kolom_nilai']: AK_NILAI,
                ak['kolom_semester']: AK_SEMESTER, ak['kolom_angkatan']: AK_ANGKATAN,
                ak['kolom_ipk']: AK_IPK, ak['kolom_sks_lulus']: AK_SKS, ak['kolom_label']: AK_LABEL}
    rename = {fmt.pmb_key: PMB_KEY}
    if key == 'biodata':
        rename.update({fmt.pmb_nim: PMB_NIM_KEY, fmt.pmb_prodi: PRODI_COL})
    elif key == 'nilai_rapor':
        rename[fmt.pmb_mapel] = MAPEL_COL
    return rename


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

def _file_name(file_obj):
    if isinstance(file_obj, (str, os.PathLike)):
        return str(file_obj)
    return getattr(file_obj, 'filename', None) or getattr(file_obj, 'name', None) or ''


def _read_csv(file_obj, origin):
    """Satu CSV = satu tabel. Pemisah (',' ';' tab '|') dan encoding dikenali
    otomatis; semua sel dibaca sebagai teks supaya NIM/nomor pendaftaran tidak
    berubah jadi angka (nol di depan hilang, 1.23e+09). Kolom angka diubah
    belakangan lewat _to_num, yang juga menerima desimal koma."""
    raw = file_obj.read() if hasattr(file_obj, 'read') else open(file_obj, 'rb').read()
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        sep = csv.Sniffer().sniff(text[:65536], delimiters=',;\t|').delimiter
    except csv.Error:
        sep = ','
    try:
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=True)
    except Exception as err:
        raise PreprocessError(f"Berkas {origin} tidak dapat dibaca sebagai CSV: {err}")
    # Isi sel tidak di-trim: Excel juga tidak, dan model terlatih menyimpan
    # kategori apa adanya (mis. 'Kota Serang ' dengan spasi di ujung).
    return df


def _load_tables(file_obj, origin, nrows=None):
    """[(nama_tabel, DataFrame)] dari berkas Excel (satu tabel per sheet) atau CSV."""
    name = _file_name(file_obj)
    if name.lower().endswith('.csv'):
        df = _read_csv(file_obj, origin)
        return [(os.path.basename(name) or 'CSV', df.head(nrows) if nrows else df)]
    try:
        book = pd.ExcelFile(file_obj)
    except Exception as err:
        raise PreprocessError(f"Berkas {origin} tidak dapat dibaca sebagai Excel maupun CSV: {err}")
    return [(sheet, pd.read_excel(book, sheet_name=sheet, nrows=nrows)) for sheet in book.sheet_names]


def _detect_roles(fmt, colset):
    """Jenis tabel yang cocok. Sheet Excel biasanya satu jenis, tetapi satu CSV
    PMB bisa memuat biodata sekaligus nilai tes, jadi semua jenis PMB yang
    kolom wajibnya lengkap ikut dipakai. Tabel akademik selalu berdiri sendiri."""
    roles = [k for k, _, req in fmt.sheet_specs() if colset.issuperset(req)]
    return ['akademik'] if 'akademik' in roles else roles


def _to_num(series):
    """pd.to_numeric yang juga menerima desimal koma dari CSV ('3,25')."""
    if not pd.api.types.is_numeric_dtype(series):
        series = series.astype(str).str.strip().str.replace(',', '.', regex=False)
    return pd.to_numeric(series, errors='coerce')


def _read_sheets(file_obj, origin, fmt):
    """Baca semua tabel lalu kelompokkan menurut peran yang terdeteksi. Kolom
    tiap tabel langsung diganti ke nama internal."""
    found = {}
    for _, df in _load_tables(file_obj, origin):
        df.columns = [str(c).strip() for c in df.columns]
        cols = set(df.columns)
        if df.empty:
            continue
        for key in _detect_roles(fmt, cols):
            rename = {src: dst for src, dst in _source_rename(fmt, key).items() if src in cols}
            # Kolom yang kebetulan sudah bernama internal tapi bukan sumbernya dibuang
            # dulu, supaya tidak terjadi dua kolom bernama sama.
            part = df.drop(columns=[c for c in rename.values() if c in cols and c not in rename])
            found.setdefault(key, []).append(part.rename(columns=rename))
    return found


def _concat(frames):
    if not frames:
        return None
    return frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)


def _require(sheets, key, origin, fmt):
    df = _concat(sheets.get(key))
    if df is None:
        label, required = next((lbl, req) for k, lbl, req in fmt.sheet_specs() if k == key)
        raise PreprocessError(
            f"Berkas {origin} tidak memuat sheet {label}. Sheet tersebut dikenali "
            f"dari kolom wajib: {', '.join(required)}. Nama kolom ini bisa disesuaikan "
            "di menu Format Data."
        )
    return df


def _clean_key(series):
    return series.astype(str).str.strip()


def _expected_columns(fmt, key):
    """Semua kolom berkas mentah yang dipakai untuk satu jenis sheet (wajib
    maupun opsional), dipakai fitur Cek Berkas."""
    ak = fmt.ak
    if key == 'akademik':
        return [ak[k] for k in ('kolom_nim', 'kolom_matkul', 'kolom_nilai', 'kolom_semester',
                                'kolom_angkatan', 'kolom_ipk', 'kolom_sks_lulus', 'kolom_label')]
    if key == 'biodata':
        return [fmt.pmb_key, fmt.pmb_nim, fmt.pmb_prodi] + list(fmt.biodata_rename)
    if key == 'nilai_tes':
        return [fmt.pmb_key] + list(fmt.tes_rename)
    return [fmt.pmb_key, fmt.pmb_mapel] + list(fmt.rapor_value_cols)


def inspect_workbook(file_obj, fmt):
    """Laporan per sheet: jenis yang dikenali dan kolom yang tidak ditemukan.
    Untuk sheet yang tidak dikenali, sebutkan jenis terdekat dan kolom wajib
    yang kurang, supaya admin tahu nama kolom mana yang perlu disesuaikan."""
    specs = fmt.sheet_specs()
    laporan = []
    for sheet, df in _load_tables(file_obj, 'yang dicek', nrows=5):
        cols = [str(c).strip() for c in df.columns]
        colset = set(cols)
        item = {'sheet': sheet, 'kolom': cols}
        roles = _detect_roles(fmt, colset)
        if roles:
            expected = [c for k in roles for c in _expected_columns(fmt, k)]
            item.update({
                'jenis': roles[0],
                'jenis_semua': roles,
                'label': ' + '.join(lbl for k, lbl, _ in specs if k in roles),
                'kolom_tidak_ada': list(dict.fromkeys(c for c in expected if c not in colset)),
            })
        else:
            # Jenis terdekat = yang paling banyak kolom harapannya ada di sheet ini.
            def kecocokan(spec):
                harapan = _expected_columns(fmt, spec[0])
                return sum(c in colset for c in harapan) / len(harapan)
            k, lbl, req = max(specs, key=kecocokan)
            item.update({
                'jenis': None,
                'terdekat': lbl,
                'kolom_wajib_tidak_ada': [c for c in req if c not in colset],
            })
        laporan.append(item)
    return laporan


# ---------------------------------------------------------------------------
# Pengolahan tiap sumber
# ---------------------------------------------------------------------------

def _prodi_unik(biodata):
    return sorted(str(v).strip() for v in biodata[PRODI_COL].dropna().unique())


def _resolve_prodi(biodata, prodi, nim_akademik, fmt):
    """Tentukan program studi yang diproses dan saring biodata ke prodi itu.

    Berkas PMB umumnya berisi semua program studi sekaligus, sedangkan berkas
    akademik disiapkan per program studi. Karena itu, saat prodi tidak dipilih,
    penentuannya tidak diambil dari seluruh isi berkas PMB, melainkan dari
    mahasiswa yang benar-benar muncul di berkas akademik — di situlah program
    studi yang sedang diproses sebetulnya ditentukan."""
    if PRODI_COL not in biodata.columns:
        if not prodi:
            raise PreprocessError(f"Berkas PMB tidak punya kolom '{fmt.pmb_prodi}', jadi Program "
                                  "Studi harus dipilih di halaman ini.")
        biodata = biodata.copy()
        biodata[PRODI_COL] = prodi
        return biodata, prodi

    if prodi:
        cocok = biodata[biodata[PRODI_COL].astype(str).str.contains(str(prodi), case=False,
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
            f"NIM dicocokkan dengan kolom '{fmt.pmb_nim}' di berkas PMB."
        )

    kandidat = _prodi_unik(milik_berkas)
    if len(kandidat) == 1:
        return milik_berkas.reset_index(drop=True), kandidat[0]

    raise PreprocessError(
        "Berkas akademik memuat mahasiswa dari lebih dari satu Program Studi "
        f"({', '.join(kandidat)}). Pilih salah satu di halaman ini, karena hasil "
        "preprocessing dipakai untuk melatih model per program studi."
    )


def _biodata_table(biodata, fmt):
    kolom = {k: v for k, v in fmt.biodata_rename.items() if k in biodata.columns}
    keep = [PMB_KEY, PMB_NIM_KEY, PRODI_COL] + list(kolom)
    out = biodata[[c for c in keep if c in biodata.columns]].copy()
    out = out.rename(columns=kolom)
    out['NIM'] = _clean_key(out[PMB_NIM_KEY])
    out[PMB_KEY] = _clean_key(out[PMB_KEY])
    return out.drop(columns=[PMB_NIM_KEY]).drop_duplicates(subset=['NIM'], keep='first')


def _tes_table(tes, fmt):
    if tes is None:
        return None
    kolom = {k: v for k, v in fmt.tes_rename.items() if k in tes.columns}
    out = tes[[PMB_KEY] + list(kolom)].rename(columns=kolom).copy()
    out[PMB_KEY] = _clean_key(out[PMB_KEY])
    for c in kolom.values():
        out[c] = _to_num(out[c])
    return out.groupby(PMB_KEY, as_index=False).mean(numeric_only=True)


def _rapor_table(rapor, fmt):
    """Ubah nilai rapor dari format panjang menjadi kolom `<Mapel>_<akhiran>`."""
    if rapor is None:
        return None
    value_cols = [c for c in fmt.rapor_value_cols if c in rapor.columns]
    if not value_cols:
        return None

    long = rapor[[PMB_KEY, MAPEL_COL] + value_cols].melt(
        id_vars=[PMB_KEY, MAPEL_COL], var_name='_semester', value_name='_nilai')
    long[PMB_KEY] = _clean_key(long[PMB_KEY])
    long['_kolom'] = (long[MAPEL_COL].astype(str).str.strip() + '_'
                      + long['_semester'].map(fmt.rapor_value_cols))
    long['_nilai'] = _to_num(long['_nilai'])
    long = long.dropna(subset=['_nilai'])
    if long.empty:
        return None

    wide = long.pivot_table(index=PMB_KEY, columns='_kolom', values='_nilai', aggfunc='mean')
    wide.columns.name = None
    return wide.reset_index()


def _best_attempt(akademik, fmt):
    """Satu baris per (mahasiswa, mata kuliah), memakai nilai terbaik dari
    pengulangan yang ada. Nilai di luar tabel nilai mutu dianggap terburuk."""
    df = akademik.copy()
    df[AK_MATKUL] = df[AK_MATKUL].astype(str).str.strip()
    df[AK_NILAI] = df[AK_NILAI].astype(str).str.strip().str.upper()
    df['_peringkat'] = df[AK_NILAI].map(fmt.grade_rank)
    df = df.sort_values('_peringkat', na_position='first')
    return df.groupby([AK_NIM, AK_MATKUL], as_index=False).last()


def _akademik_tables(akademik, max_semester, nim_prodi, fmt):
    """Kembalikan (rekap per mahasiswa, matriks nilai mata kuliah, semester
    terakhir yang tercatat per mahasiswa).

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
            f"dicocokkan dengan kolom '{fmt.pmb_nim}' di berkas PMB."
        )
    df['Semester'] = _to_num(df['Semester'])
    df = df[df['Semester'].notna()]

    lingkup = df[df['Semester'] <= max_semester]
    if lingkup.empty:
        raise PreprocessError(f"Tidak ada baris akademik sampai semester {max_semester}.")

    nilai = _best_attempt(lingkup, fmt)
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
                rekap[f'IPK {smt}'] = _to_num(ipk[smt])

    if 'SKS Lulus Per Semester' in df.columns:
        sks = (lingkup.drop_duplicates(subset=['NIM', 'Semester'])
                      .pivot(index='NIM', columns='Semester', values='SKS Lulus Per Semester'))
        tersedia = [s for s in sks.columns if s <= max_semester]
        if tersedia:
            rekap[f'Total SKS {max_semester}'] = _to_num(sks[max(tersedia)])

    if AK_LABEL in df.columns:
        mentah = df.dropna(subset=[AK_LABEL]).groupby('NIM')[AK_LABEL].first()
        rekap[LABEL_COL] = mentah.reindex(rekap.index).map(
            lambda v: LABEL_AMAN if str(v).strip().lower() in fmt.label_aman else LABEL_RISIKO
        ).where(mentah.reindex(rekap.index).notna())

    terakhir = df.groupby('NIM')['Semester'].max()
    return rekap.reset_index(), matriks.reset_index(), terakhir


# ---------------------------------------------------------------------------
# Alur utama
# ---------------------------------------------------------------------------

def _check_semester(max_semester):
    try:
        max_semester = int(max_semester)
    except (TypeError, ValueError):
        raise PreprocessError("Batas semester harus berupa angka.")
    if not 1 <= max_semester <= MAX_SEMESTER_LIMIT:
        raise PreprocessError(f"Batas semester harus antara 1 dan {MAX_SEMESTER_LIMIT}.")
    return max_semester


def _merged_table(pmb_file, akademik_file, prodi, max_semester, fmt):
    """Gabungan PMB + akademik satu baris per mahasiswa, sebelum urusan label.
    Dipakai bersama oleh mode latih (TRAIN_SEM*) dan mode prediksi (TEST_SEM*)
    supaya kedua tabel dibentuk dengan cara yang persis sama."""
    sheet_pmb = _read_sheets(pmb_file, 'PMB', fmt)
    sheet_akademik = _read_sheets(akademik_file, 'akademik', fmt)

    biodata = _require(sheet_pmb, 'biodata', 'PMB', fmt)
    akademik = _require(sheet_akademik, 'akademik', 'akademik', fmt)
    tes = _concat(sheet_pmb.get('nilai_tes'))
    rapor = _concat(sheet_pmb.get('nilai_rapor'))

    nim_akademik = set(_clean_key(akademik['NIM']))
    biodata, prodi_label = _resolve_prodi(biodata, prodi, nim_akademik, fmt)
    biodata = _biodata_table(biodata, fmt)

    rekap, matriks, terakhir = _akademik_tables(akademik, max_semester, set(biodata['NIM']), fmt)
    jumlah_matkul = len(matriks.columns) - 1

    df = rekap.merge(matriks, on='NIM', how='left').merge(biodata, on='NIM', how='inner')
    for tabel in (_tes_table(tes, fmt), _rapor_table(rapor, fmt)):
        if tabel is not None:
            df = df.merge(tabel, on=PMB_KEY, how='left')

    df = df.rename(columns={PMB_KEY: 'Nomor PMB'})
    df['Prodi'] = prodi_label
    sumber = {'PMB': sorted(sheet_pmb.keys()), 'akademik': sorted(sheet_akademik.keys())}
    return df, prodi_label, jumlah_matkul, terakhir, sumber


def _split_columns(df):
    laporan_cols = [c for c in df.columns
                    if c.startswith('IPK ') or c.startswith('Total SKS ')]
    kandidat = [c for c in df.columns
                if c not in IDENTITY_COLS + laporan_cols + [LABEL_COL]]
    return laporan_cols, kandidat


def build_training_table(pmb_file, akademik_file, prodi=None, max_semester=3, fmt=None):
    """Tabel latih setara sheet TRAIN_SEM<n>. `fmt` adalah DataFormat; tanpa
    itu dipakai format bawaan."""
    fmt = fmt or DataFormat(default_format())
    max_semester = _check_semester(max_semester)
    df, prodi_label, jumlah_matkul, _, sumber = _merged_table(
        pmb_file, akademik_file, prodi, max_semester, fmt)

    if LABEL_COL not in df.columns:
        raise PreprocessError(
            f"Berkas akademik tidak memuat kolom '{fmt.ak['kolom_label']}' sebagai target, "
            "sehingga data latih tidak bisa dibentuk."
        )
    tanpa_label = int(df[LABEL_COL].isna().sum())
    df = df[df[LABEL_COL].notna()]
    if df.empty:
        raise PreprocessError(
            f"Tidak ada mahasiswa dengan kolom '{fmt.ak['kolom_label']}' terisi, jadi tidak ada "
            "baris berlabel yang bisa dilatih."
        )

    df = _fill_missing(df)
    laporan_cols, kandidat = _split_columns(df)
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
            'sumber_terdeteksi': sumber,
        },
    )


def _norm_angkatan(v):
    s = str(v).strip()
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else s
    except ValueError:
        return s


def build_prediction_table(pmb_file, akademik_file, prodi, max_semester, angkatan=None, fmt=None):
    """Tabel uji setara sheet TEST_SEM<n> di cnn_tabular_2d_v2.py: dibentuk
    persis seperti tabel latih, tetapi tanpa syarat label (mahasiswa yang
    diprediksi memang belum punya label) dan tanpa membuang kolom seragam,
    karena susunan kolomnya nanti disamakan dengan fitur model.

    Nilai mata kuliah diambil sampai `max_semester`, yang harus sama dengan
    batas semester data latih model."""
    fmt = fmt or DataFormat(default_format())
    max_semester = _check_semester(max_semester)
    df, prodi_label, _, terakhir, sumber = _merged_table(
        pmb_file, akademik_file, prodi, max_semester, fmt)

    tersedia = sorted({_norm_angkatan(a) for a in df['Angkatan'].dropna().unique()})
    if angkatan not in (None, ''):
        df = df[df['Angkatan'].map(_norm_angkatan) == _norm_angkatan(angkatan)]
        if df.empty:
            raise PreprocessError(
                f"Tidak ada mahasiswa {prodi_label} angkatan {angkatan} di berkas. "
                f"Angkatan yang tersedia: {', '.join(tersedia) or '-'}."
            )

    df = df.drop(columns=[LABEL_COL], errors='ignore')
    df = _fill_missing(df)
    laporan_cols, kandidat = _split_columns(df)
    df = df[IDENTITY_COLS + kandidat + laporan_cols].reset_index(drop=True)

    # Mahasiswa yang datanya belum sampai batas semester model tetap
    # diprediksi (seperti angkatan termuda di TEST_SEM3 notebook), tetapi
    # dilaporkan supaya hasilnya dibaca dengan hati-hati.
    smt = df['NIM'].map(terakhir)
    belum_lengkap = df.loc[smt.isna() | (smt < max_semester), 'NIM'].astype(str).tolist()

    return PreprocessResult(
        df=df,
        prodi=prodi_label,
        max_semester=max_semester,
        feature_cols=kandidat,
        report={
            'mahasiswa': len(df),
            'angkatan_tersedia': tersedia,
            'belum_lengkap': belum_lengkap,
            'sumber_terdeteksi': sumber,
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
