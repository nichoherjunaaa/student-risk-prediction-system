"""Prediksi batch dari berkas PMB & akademik di Berkas Mahasiswa."""
import json
from collections import OrderedDict

from flask import Blueprint, jsonify, request

from ..auth import require_role, scoped_prodi
from ..config import PREDIKSI_ROLES
from ..db import connect
from ..predictor import (PredictError, align_features, build_results, coverage_error,
                         load_active_model, run_model, save_batch)
from ..preprocessing import MAX_SEMESTER_LIMIT, PreprocessError, build_prediction_table
from ..settings_store import current_format
from ..utils import norm_str
from .files import file_info, latest_file

bp = Blueprint('prediction', __name__)


def _predict_and_save(features, original_df, am, prodi, angkatan, semester, extra=None):
    try:
        labels = run_model(features, am)
    except Exception as proc_err:
        return jsonify({'error': f"Gagal memproses isi berkas untuk prodi {prodi}: {proc_err}"}), 400
    try:
        results, at_risk, safe = build_results(original_df, labels, prodi, current_format())
    except Exception as build_err:
        return jsonify({'error': f"Gagal menyusun hasil prediksi: {build_err}"}), 500
    try:
        body = save_batch(results, at_risk, safe, prodi, angkatan, semester, request.user)
    except PredictError as err:
        return jsonify({'error': str(err)}), err.status
    body.update(extra or {})
    return jsonify(body)


# ---------------------------------------------------------------------------
# Tabel uji dibentuk langsung dari berkas PMB & akademik di Berkas Mahasiswa
# (diunggah BAPSI), dengan pengolahan yang sama seperti tabel latih. Hasilnya
# setara sheet TEST_SEM<n> di cnn_tabular_2d_v2.py.
# ---------------------------------------------------------------------------

# Tabel hasil preprocessing disimpan sebentar per kombinasi berkas/prodi/
# semester/format, supaya memilih angkatan lalu memprediksi tidak membaca ulang
# Excel berukuran besar dua kali.
_TABLE_CACHE = OrderedDict()
_TABLE_CACHE_SIZE = 8


def _source_files(form):
    """Berkas PMB & akademik: pilihan eksplisit (id) atau yang terbaru."""
    chosen = {}
    for kategori in ('pmb', 'akademik'):
        file_id = form.get(f'file_{kategori}_id')
        info = file_info(file_id, kategori) if file_id else latest_file(kategori)
        judul = 'PMB' if kategori == 'pmb' else 'akademik'
        if not info and file_id:
            raise PredictError(f"Berkas {judul} yang dipilih tidak ditemukan atau sudah dihapus. "
                               "Pilih berkas lain.")
        if not info:
            raise PredictError(f"Belum ada berkas {judul} di Berkas Mahasiswa. "
                               "Minta BAPSI mengunggah berkas terbaru terlebih dahulu.")
        chosen[kategori] = info
    return chosen


def _cached_table(files, prodi, semester, fmt):
    key = (files['pmb']['id'], files['akademik']['id'], prodi, semester,
           json.dumps(fmt.raw, sort_keys=True))
    if key in _TABLE_CACHE:
        _TABLE_CACHE.move_to_end(key)
        return _TABLE_CACHE[key]
    hasil = build_prediction_table(files['pmb']['path'], files['akademik']['path'],
                                   prodi=prodi, max_semester=semester, fmt=fmt)
    _TABLE_CACHE[key] = hasil
    while len(_TABLE_CACHE) > _TABLE_CACHE_SIZE:
        _TABLE_CACHE.popitem(last=False)
    return hasil


def _model_semester(am, files, prodi, fmt):
    """Batas semester data latih model. Model baru mencatatnya saat training;
    untuk model lama diperkirakan sekali dari data lalu disimpan: semester
    terkecil yang sudah memuat sebanyak mungkin fitur model (mata kuliah
    semester berikutnya belum menjadi fitur, jadi semester lebih besar tidak
    menambah kecocokan)."""
    if am.max_semester:
        return int(am.max_semester), getattr(am, 'max_semester_source', None) or 'training'
    best, best_cov = None, -1.0
    for smt in range(1, MAX_SEMESTER_LIMIT + 1):
        try:
            tabel = _cached_table(files, prodi, smt, fmt)
        except PreprocessError:
            continue
        cols = set(tabel.df.columns)
        cov = sum(c in cols for c in am.feature_cols) / max(len(am.feature_cols), 1)
        if cov > best_cov + 1e-9:
            best, best_cov = smt, cov
    if best is None:
        raise PredictError("Batas semester model tidak dapat ditentukan dari berkas yang ada.")
    conn = connect()
    try:
        conn.execute("UPDATE model_registry SET max_semester = ?, max_semester_source = 'perkiraan' "
                     "WHERE id = ?", (best, am.id))
        conn.commit()
    finally:
        conn.close()
    return best, 'perkiraan'


def _model_info(am, semester=None, source=None):
    return {'id': am.id, 'version': am.version, 'trained_at': am.trained_at,
            'max_semester': semester, 'max_semester_source': source}


@bp.route('/api/predict/sumber', methods=['GET'])
@require_role(*PREDIKSI_ROLES)
def prediction_source():
    """Yang akan dipakai prediksi: berkas pilihan (default terbaru), model aktif,
    batas semester, dan angkatan yang tersedia untuk prodi ini."""
    prodi = scoped_prodi(request.args.get('prodi') or None)
    if not prodi:
        return jsonify({'error': 'Pilih program studi terlebih dahulu.'}), 400
    try:
        files = _source_files(request.args)
        am = load_active_model(prodi)
        fmt = current_format()
        semester, source = _model_semester(am, files, prodi, fmt)
        tabel = _cached_table(files, prodi, semester, fmt)
    except PredictError as err:
        return jsonify({'error': str(err)}), err.status
    except PreprocessError as err:
        return jsonify({'error': str(err)}), 400
    return jsonify({
        'prodi': prodi,
        'berkas': {k: {kk: v[kk] for kk in ('id', 'name', 'uploaded_at', 'uploaded_by')}
                   for k, v in files.items()},
        'model': _model_info(am, semester, source),
        'angkatan': tabel.report['angkatan_tersedia'],
    }), 200


@bp.route('/api/predict/berkas', methods=['POST'])
@require_role(*PREDIKSI_ROLES)
def predict_from_files():
    data = request.json or {}
    prodi = scoped_prodi(data.get('prodi') or None)
    angkatan = str(data.get('angkatan') or '').strip()
    if not prodi:
        return jsonify({'error': 'Pilih program studi terlebih dahulu.'}), 400
    if not angkatan:
        return jsonify({'error': 'Pilih angkatan yang akan diprediksi.'}), 400

    try:
        files = _source_files(data)
        am = load_active_model(prodi)
        if not am.feature_cols:
            raise PredictError("Model aktif tidak menyimpan nama kolom fitur. Lakukan training ulang.")
        fmt = current_format()
        semester, source = _model_semester(am, files, prodi, fmt)
        tabel = _cached_table(files, prodi, semester, fmt)
    except PredictError as err:
        return jsonify({'error': str(err)}), err.status
    except PreprocessError as err:
        return jsonify({'error': str(err)}), 400

    df = tabel.df[tabel.df['Angkatan'].map(norm_str) == norm_str(angkatan)].reset_index(drop=True)
    if df.empty:
        return jsonify({'error': f"Tidak ada mahasiswa {prodi} angkatan {angkatan} di berkas. "
                                 f"Angkatan yang tersedia: {', '.join(tabel.report['angkatan_tersedia'])}."}), 400

    features, missing = align_features(df, am)
    err = coverage_error(missing, am, prodi)
    if err:
        return jsonify({'error': err}), 400
    coverage = 1 - len(missing) / len(am.feature_cols)

    belum = set(tabel.report['belum_lengkap'])
    extra = {
        'sumber': {
            'berkas': {k: {kk: v[kk] for kk in ('id', 'name', 'uploaded_at')} for k, v in files.items()},
            'model': _model_info(am, semester, source),
            'kecocokan_fitur': round(coverage, 4),
            'fitur_diisi_kosong': len(missing),
            'belum_lengkap': [n for n in df['NIM'].astype(str) if n in belum],
        },
    }
    return _predict_and_save(features, df, am, prodi, angkatan, semester, extra)
