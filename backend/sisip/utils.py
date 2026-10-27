"""Fungsi kecil yang dipakai banyak modul."""
import datetime
import re


def now_iso():
    return datetime.datetime.now().isoformat(timespec='seconds')


def slug(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_') or 'prodi'


def norm_str(v):
    """Normalisasi nilai supaya '2024', '2024.0', 2024, dan ' 2024 ' dianggap sama.
    Tanpa ini, kolom Angkatan/Semester yang punya sel kosong berubah jadi float oleh
    pandas ('2024.0') dan tidak akan pernah cocok dengan pilihan dropdown ('2024')."""
    s = str(v).strip()
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return s


def match_series(series, value):
    return series.astype(str).map(norm_str) == norm_str(value)
