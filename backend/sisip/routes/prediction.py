"""Template prediksi, pratinjau berkas, dan prediksi batch."""
import io
import json
from collections import OrderedDict

import joblib
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request, send_file

from ..auth import require_role, scoped_prodi
from ..config import PREDIKSI_ROLES
from ..constants import LABEL_COL, TEMPLATE_IDENTITY_COLS, TEST_SHEET
from ..db import connect
from ..ml import active_model_info
from ..predictor import (PredictError, align_features, build_results, coverage_error,
                         load_active_model, run_model, save_batch)
from ..preprocessing import MAX_SEMESTER_LIMIT, PreprocessError, build_prediction_table
from ..settings_store import current_format
from ..utils import match_series, norm_str
from .files import file_info, latest_file

bp = Blueprint('prediction', __name__)


TEMPLATE_DEFAULT_ANGKATAN = 2023
TEMPLATE_DEFAULT_SEMESTER = 3

_SAMPLE_NAMES = [
    "Ahmad Fauzi Ramadhan", "Siti Nur Aisyah", "Budi Santoso", "Dewi Lestari",
    "Muhammad Rizky Pratama", "Putri Ayu Wulandari", "Andi Setiawan", "Rina Marlina",
]


def _build_sample_rows(cols, feature_cols, encoders, scaler, prodi_label, angkatan, semester, fmt):
    """Contoh data siap-pakai untuk template, diturunkan dari statistik model itu
    sendiri (scaler.mean_ / scaler.scale_) supaya nilainya berada di rentang yang
    memang pernah dilihat model.

    Menebak rentang sendiri (mis. nilai tes 0-100) berbahaya: pada dataset ini
    kolom nilai tes ternyata berskala 0-10, sehingga angka karangan 35-90 menjadi
    +16..+28 sigma dan mendorong SEMUA prediksi ke satu kelas. Setiap baris digeser
    k*sigma dari rata-rata: k negatif = profil kuat, k positif = profil lemah."""
    means = getattr(scaler, 'mean_', None)
    scales = getattr(scaler, 'scale_', None)
    feat_index = {c: i for i, c in enumerate(feature_cols)}

    profil_k = [-1.2, -0.8, -0.4, 0.0, 0.6, 1.0, 1.4, 1.8]

    rows = []
    for idx, nama in enumerate(_SAMPLE_NAMES, start=1):
        k = profil_k[(idx - 1) % len(profil_k)]
        row = {}
        for col in cols:
            if col == 'NIM':
                row[col] = f"{angkatan}{idx:06d}"
            elif col == 'Nomor PMB':
                row[col] = f"PMB-{angkatan}-{idx:04d}"
            elif col == 'Nama':
                row[col] = nama
            elif col == 'Prodi':
                row[col] = prodi_label
            elif col == 'Angkatan':
                row[col] = angkatan
            elif col == 'Semester':
                row[col] = semester
            elif col.startswith('IPK') or col.startswith('Total SKS'):
                row[col] = None
            elif col in feat_index and means is not None and scales is not None:
                i = feat_index[col]
                target = float(means[i]) + k * float(scales[i])
                if col in encoders:
                    classes = list(encoders[col].classes_)
                    if not classes:
                        row[col] = ''
                    else:
                        j = int(round(min(max(target, 0), len(classes) - 1)))
                        row[col] = str(classes[j])
                else:
                    row[col] = round(max(target, 0.0), 2)
            elif col in encoders:
                classes = list(encoders[col].classes_)
                row[col] = str(classes[idx % len(classes)]) if classes else ''
            else:
                row[col] = 0

        _isi_rekap_akademik(row, fmt)
        rows.append(row)
    return rows


def _isi_rekap_akademik(row, fmt):
    """Hitung kolom IPK/Total SKS contoh dari huruf mutu di baris yang sama.

    Sebelumnya kolom ini diisi angka acak berdasarkan 'profil kuat/lemah',
    terpisah dari huruf mutu yang dihasilkan dari statistik model. Akibatnya
    satu baris bisa menampilkan IPK 1.63 padahal nilai mata kuliahnya mayoritas
    A/B — pembaca lalu menyimpulkan prediksinya keliru, padahal justru angka
    IPK-nya yang mengada-ada. Sekarang keduanya berasal dari sumber yang sama."""
    points = fmt.grade_points
    huruf = [str(v).strip().upper() for v in row.values() if str(v).strip().upper() in points]
    ipk = round(sum(points[g] for g in huruf) / len(huruf), 2) if huruf else 0
    sks_lulus = sum(fmt.sks_per_matkul for g in huruf if g not in fmt.grade_fail)
    for col in row:
        if row[col] is None:
            row[col] = sks_lulus if col.startswith('Total SKS') else ipk


class _TemplateError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _load_template_model(prodi_param, default_prodi):
    """Muat artefak model aktif untuk membangun template (fitur, encoder, scaler,
    kelas label). Jatuh ke model aktif prodi lain bila prodi yang diminta belum
    punya, supaya tombol unduh template selalu berfungsi."""
    base, resolved_prodi = active_model_info(prodi_param or default_prodi)
    if not base:
        base, resolved_prodi = active_model_info(None)
    if not base:
        raise _TemplateError("Belum ada model aktif sama sekali. Latih dan aktifkan "
                             "model terlebih dahulu dari tabel di bawah.")

    try:
        scaler = joblib.load(f"{base}_scaler.pkl")
        encoders = joblib.load(f"{base}_encoders.pkl")
    except Exception as load_err:
        raise _TemplateError(f"Gagal membaca kolom dari model aktif: {load_err}", 500)

    feature_cols = [str(c) for c in getattr(scaler, 'feature_names_in_', [])]
    if not feature_cols:
        raise _TemplateError("Model aktif tidak menyimpan nama kolom fitur, template "
                             "tidak dapat dibuat. Lakukan training ulang.")

    prodi_label = prodi_param or resolved_prodi or default_prodi
    model_prodi_label = resolved_prodi or prodi_label
    return {
        'feature_cols': feature_cols, 'encoders': encoders, 'scaler': scaler,
        'prodi_label': prodi_label, 'model_prodi_label': model_prodi_label,
    }


def _template_xlsx_response(df, sheet_name, download_name):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=download_name,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@bp.route('/api/template/predict', methods=['GET'])
@bp.route('/api/template', methods=['GET'])
@require_role(*PREDIKSI_ROLES)
def download_predict_template():
    """Excel template for batch prediction upload, already filled with usable example
    data. Feature columns are taken from the active model's scaler so the header
    matches exactly what that model expects; falls back to a default prodi/model so
    the button always works even before Program Studi is chosen on the page."""
    prodi_param = scoped_prodi(request.args.get('prodi') or None)
    angkatan_param = request.args.get('angkatan') or TEMPLATE_DEFAULT_ANGKATAN
    semester_param = request.args.get('semester') or TEMPLATE_DEFAULT_SEMESTER

    fmt = current_format()
    try:
        m = _load_template_model(prodi_param, fmt.prodi[0])
    except _TemplateError as err:
        return jsonify({'error': str(err)}), err.status

    cols = TEMPLATE_IDENTITY_COLS + [c for c in m['feature_cols'] if c not in TEMPLATE_IDENTITY_COLS]
    rows = _build_sample_rows(cols, m['feature_cols'], m['encoders'], m['scaler'],
                              m['prodi_label'], angkatan_param, semester_param, fmt)
    df = pd.DataFrame(rows, columns=cols)

    return _template_xlsx_response(
        df, TEST_SHEET,
        f'template_prediksi_{m["model_prodi_label"].lower().replace(" ", "_")}.xlsx')

@bp.route('/api/preview', methods=['POST'])
@require_role(*PREDIKSI_ROLES)
def preview_data():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    sheet_param = request.form.get('sheet', None)
    prodi = scoped_prodi(request.form.get('prodi', 'Unknown'))
    angkatan = request.form.get('angkatan', 'Unknown')
    semester = request.form.get('semester', 'Unknown')
    
    try:
        excel_file = pd.ExcelFile(file)
        if sheet_param and sheet_param in excel_file.sheet_names:
            sheet_to_read = sheet_param
        elif TEST_SHEET in excel_file.sheet_names:
            sheet_to_read = TEST_SHEET
        else:
            sheet_to_read = excel_file.sheet_names[0]
            
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Angkatan, Prodi, Semester if columns exist (dinormalkan agar
        # konsisten dengan /api/predict, lihat match_series)
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[match_series(df['Angkatan'], angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[match_series(df['Semester'], semester)]

        # Convert first 10 rows to dict for preview
        preview_data = df.head(10).replace({np.nan: None}).to_dict(orient='records')
        columns = df.columns.tolist()
        return jsonify({
            'columns': columns,
            'data': preview_data,
            'total_rows': len(df)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@bp.route('/api/predict', methods=['POST'])
@require_role(*PREDIKSI_ROLES)
def predict():
    """Prediksi dari berkas template (sheet TEST_SEM3) yang diunggah dosen."""
    # Dosen yang terikat prodi selalu memprediksi untuk prodinya sendiri.
    prodi = scoped_prodi(request.form.get('prodi', 'Unknown'))
    angkatan = request.form.get('angkatan', 'Unknown')
    semester = request.form.get('semester', 'Unknown')

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']

    try:
        am = load_active_model(prodi)
    except PredictError as err:
        return jsonify({'error': str(err)}), err.status

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = TEST_SHEET if TEST_SHEET in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        df_before_filter = df

        # Filter by Angkatan, Prodi, and Semester jika kolom tersedia di Excel.
        # match_series menormalkan tipe (mis. '2024' vs '2024.0') agar tidak
        # meleset gara-gara sel kosong di kolom lain membuat kolom ini jadi float.
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[match_series(df['Angkatan'], angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[match_series(df['Semester'], semester)]

        if len(df) == 0:
            # Jelaskan persis bagian mana yang tidak cocok, dibanding isi berkas,
            # supaya bukan lagi pesan generik "tidak ada data uji".
            reasons = []
            if 'Prodi' in df_before_filter.columns and prodi not in ('Unknown', ''):
                file_vals = sorted(set(str(v) for v in df_before_filter['Prodi'].dropna().unique()))
                if file_vals and not any(str(prodi).lower() in v.lower() for v in file_vals):
                    reasons.append(f"Program Studi tidak sesuai — berkas berisi: {', '.join(file_vals)}, "
                                   f"sedangkan yang dipilih di halaman ini: {prodi}.")
            if 'Angkatan' in df_before_filter.columns and angkatan not in ('Unknown', ''):
                file_vals = sorted(set(norm_str(v) for v in df_before_filter['Angkatan'].dropna().unique()))
                if file_vals and norm_str(angkatan) not in file_vals:
                    reasons.append(f"Angkatan tidak sesuai — berkas berisi: {', '.join(file_vals)}, "
                                   f"sedangkan yang dipilih: {angkatan}.")
            if 'Semester' in df_before_filter.columns and semester not in ('Unknown', ''):
                file_vals = sorted(set(norm_str(v) for v in df_before_filter['Semester'].dropna().unique()))
                if file_vals and norm_str(semester) not in file_vals:
                    reasons.append(f"Semester tidak sesuai — berkas berisi: {', '.join(file_vals)}, "
                                   f"sedangkan yang dipilih: {semester}.")
            if not reasons:
                reasons.append("Tidak ada baris yang cocok dengan kombinasi Program Studi/Angkatan/"
                                "Semester yang dipilih di halaman ini.")
            return jsonify({'error': "Berkas tidak sesuai dengan pilihan Program Studi/Angkatan/Semester. "
                                     + " ".join(reasons)}), 400

        original_df = df.copy()
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    # Susun kolom persis seperti saat model dilatih. Kolom identitas (Nama, Prodi,
    # Semester, NIM, IPK, dst.) hanya dipakai untuk laporan dan harus dibuang di sini,
    # kalau tidak scaler menolak berkas dengan ValueError. Berkas template wajib
    # memuat semua kolom fitur, karena kolom yang hilang di sini berarti template
    # yang dipakai bukan untuk model ini.
    if am.feature_cols:
        missing = [c for c in am.feature_cols if c not in df.columns]
        if missing:
            preview = ', '.join(missing[:10]) + ('...' if len(missing) > 10 else '')
            return jsonify({'error': f"Berkas tidak cocok dengan model aktif prodi {prodi}. "
                                     f"{len(missing)} kolom tidak ditemukan: {preview}. "
                                     "Silakan unduh ulang Template Excel untuk prodi ini."}), 400
        df = df.reindex(columns=am.feature_cols)
    else:
        drop_cols = TEMPLATE_IDENTITY_COLS + [LABEL_COL]
        df = df.drop(columns=[col for col in drop_cols if col in df.columns])

    return _predict_and_save(df, original_df, am, prodi, angkatan, semester)


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
# Prediksi tanpa template: tabel uji dibentuk langsung dari berkas PMB &
# akademik di Berkas Mahasiswa (diunggah BAPSI), dengan pengolahan yang sama
# seperti tabel latih. Hasilnya setara sheet TEST_SEM<n> di cnn_tabular_2d_v2.py.
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
    """Yang akan dipakai prediksi tanpa template: berkas terbaru, model aktif,
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
