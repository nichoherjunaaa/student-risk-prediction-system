"""Inti prediksi, dipakai bersama oleh jalur template dan jalur Berkas Mahasiswa.

Langkahnya mengikuti bagian "Test data" s.d. "predictions" di
cnn_tabular_2d_v2.py, dengan objek hasil training (encoder, scaler, le_y,
dimensi grid) dimuat dari berkas model aktif, bukan dari memori notebook:

    X_test[col] = X_test[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
    X_test[col] = le.transform(X_test[col])
    X_test_scaled = scaler.transform(X_test)
    X_test_padded = np.pad(X_test_scaled, ((0, 0), (0, pad_size)), mode="constant")
    X_test_reshaped = X_test_padded.reshape(-1, height, width, 1)
    y_pred = (model.predict(X_test_reshaped) > 0.5).astype(int).flatten()
    predicted_labels = le_y.inverse_transform(y_pred)
"""
import datetime
import json

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from .constants import NON_MATKUL_COLS, is_risk_label
from .db import connect
from .ml import missing_artifacts, model_base_path
from .preprocessing import MISSING_CATEGORICAL, MISSING_GRADE


class PredictError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# Batas minimal fitur model yang harus ada di tabel hasil preprocessing. Fitur
# yang hilang wajar bila mata kuliahnya tidak diambil angkatan ini, tetapi bila
# sebagian besar hilang, model itu dilatih dari data berformat lain (mis. kode
# mata kuliah vs nama mata kuliah) dan hasilnya tidak bermakna.
MIN_FEATURE_COVERAGE = 0.8


class ActiveModel:
    """Model aktif satu prodi beserta artefak praprosesnya. Dengan
    with_network=False hanya artefak praproses yang dimuat (cukup untuk
    menyusun kolom), tanpa jaringan Keras yang berat."""

    def __init__(self, row, base_path, with_network=True):
        self.id, self.version, self.prodi, self.trained_at, self.max_semester = row
        self.model = keras.models.load_model(f"{base_path}.keras") if with_network else None
        self.scaler = joblib.load(f"{base_path}_scaler.pkl")
        self.encoders = joblib.load(f"{base_path}_encoders.pkl")
        self.le_y = joblib.load(f"{base_path}_ley.pkl")
        self.config = joblib.load(f"{base_path}_config.pkl")
        self.feature_cols = [str(c) for c in getattr(self.scaler, 'feature_names_in_', [])]
        if self.max_semester is None:
            self.max_semester = self.config.get('max_semester')
        # Isi nilai mata kuliah kosong sesuai data latih model ini. Model lama
        # (sebelum konvensi 'E') tidak mencatatnya dan dilatih dengan '-'.
        self.grade_cols = set(self.config.get('grade_cols', []))
        self.missing_grade = self.config.get('missing_grade', MISSING_CATEGORICAL)

    def missing_value(self, col):
        if col in self.grade_cols:
            return self.missing_grade
        return MISSING_CATEGORICAL if col in self.encoders else 0


def active_model_row(prodi):
    conn = connect()
    try:
        return conn.execute(
            "SELECT id, version_name, prodi, trained_at, max_semester, file_path, max_semester_source "
            "FROM model_registry "
            "WHERE is_active = 1 AND prodi = ? LIMIT 1", (prodi,)).fetchone()
    finally:
        conn.close()


def load_active_model(prodi, with_network=True):
    try:
        row = active_model_row(prodi)
    except Exception as db_err:
        raise PredictError(f"Gagal membaca status model dari database: {db_err}", 500)
    if not row:
        raise PredictError(f"Belum ada model aktif pilihan Admin khusus untuk Prodi {prodi}. "
                           "Sila hubungi Staf Admin untuk melakukan training model terlebih dahulu.")
    base_path = model_base_path(row[5])
    if missing_artifacts(base_path):
        raise PredictError(f"Berkas AI untuk prodi {prodi} tidak lengkap di server.", 500)
    try:
        am = ActiveModel(row[:5], base_path, with_network)
    except Exception as load_err:
        raise PredictError(f"Gagal memuat arsitektur model aktif prodi {prodi}: {load_err}", 500)
    # 'training' = tercatat saat dilatih, 'perkiraan' = ditebak dari data untuk model lama.
    am.max_semester_source = row[6] or 'training'
    return am


def align_features(df, am):
    """Samakan kolom dengan fitur model untuk tabel hasil preprocessing.

    Fitur yang tidak ada di tabel (mis. mata kuliah yang tak diambil satu pun
    mahasiswa angkatan ini) diisi seperti saat tabel latih dibentuk (lihat
    ActiveModel.missing_value). Kembalikan (tabel, daftar_fitur_hilang)."""
    missing = [c for c in am.feature_cols if c not in df.columns]
    out = df.reindex(columns=am.feature_cols)
    for col in missing:
        out[col] = am.missing_value(col)
    return out, missing


def coverage_error(missing, am, prodi):
    """Pesan penolakan bila terlalu banyak fitur model yang tidak ada, atau None."""
    coverage = 1 - len(missing) / max(len(am.feature_cols), 1)
    if coverage >= MIN_FEATURE_COVERAGE:
        return None
    preview = ', '.join(missing[:8]) + ('...' if len(missing) > 8 else '')
    return (f"Model aktif prodi {prodi} tidak cocok dengan berkas ini: hanya {coverage:.0%} fitur "
            f"model ditemukan ({len(missing)} kolom tidak ada, mis. {preview}). Model kemungkinan "
            "dilatih dari data berformat lain. Latih ulang model dari hasil Preprocessing Data.")


def run_model(features, am):
    """Encode -> scale -> pad -> reshape -> predict, sama dengan notebook.
    `features` sudah tersusun sesuai am.feature_cols."""
    df = features.copy()
    # Kategori yang tidak dikenal model diganti ke kelas pertama (le.classes_[0]).
    for col, le in am.encoders.items():
        if col in df.columns:
            df[col] = df[col].where(df[col].notna(), am.missing_value(col))
            known = set(str(x) for x in le.classes_)
            as_str = df[col].astype(str)
            df[col] = le.transform(as_str.map(lambda s: s if s in known else str(le.classes_[0])))

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # Training mengisi sel kosong dengan 0 sebelum scaler.fit, jadi di sini juga.
    df = df.fillna(0)

    X_scaled = am.scaler.transform(df)
    pad_size = am.config['pad_size']
    X_padded = np.pad(X_scaled, ((0, 0), (0, pad_size)), mode="constant") if pad_size > 0 else X_scaled
    X_reshaped = X_padded.reshape(-1, am.config['height'], am.config['width'], 1)

    predictions = am.model.predict(X_reshaped, verbose=0)
    if am.config['n_classes'] > 2:
        y_pred = np.argmax(predictions, axis=1)
    else:
        y_pred = (predictions > 0.5).astype(int).flatten()
    return am.le_y.inverse_transform(y_pred)


def _safe_float(df, col, i):
    """IPK bisa berisi teks/kosong pada berkas hasil edit manual; jangan sampai
    satu sel rusak menjatuhkan seluruh permintaan dengan 500."""
    if col not in df.columns:
        return 0.0
    val = df[col].iloc[i]
    try:
        return float(val) if not pd.isna(val) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(df, col, i):
    if col not in df.columns:
        return 0
    val = df[col].iloc[i]
    try:
        return int(float(val)) if not pd.isna(val) else 0
    except (TypeError, ValueError):
        return 0


def build_results(original_df, labels, prodi, fmt):
    """Hasil per mahasiswa untuk respons API dan tabel predictions."""
    sks_matkul = fmt.sks_per_matkul
    cols = original_df.columns

    def first(names, i, default):
        for n in names:
            if n in cols:
                return original_df[n].iloc[i]
        return default

    results, at_risk = [], 0
    for i, label in enumerate(labels):
        nim = first(['NIM'], i, f'Unknown-{i}')
        pmb = first(['Nomor Pendaftaran', 'Nomor PMB'], i, f'Unknown-{i}')
        nama = first(['Nama', 'Nama Mahasiswa'], i, str(nim))
        prodi_val = first(['Prodi'], i, prodi)

        failed, passed = [], []
        for col in cols:
            if col in NON_MATKUL_COLS or pd.isna(original_df[col].iloc[i]):
                continue
            val = str(original_df[col].iloc[i]).strip().upper()
            # SKS per mata kuliah tidak ada di berkas, jadi pakai angka rata
            # dari Format Data. Lulus/tidak lulus juga mengikuti tabel nilai di sana.
            if val in fmt.grade_fail:
                failed.append({'matkul': col, 'nilai': val, 'sks': sks_matkul})
            elif val in fmt.grade_pass:
                passed.append({'matkul': col, 'nilai': val, 'sks': sks_matkul})

        details = {
            'nama': str(nama),
            'prodi': str(prodi_val),
            'ipk1': _safe_float(original_df, 'IPK 1', i),
            'ipk2': _safe_float(original_df, 'IPK 2', i),
            'ipk3': _safe_float(original_df, 'IPK 3', i),
            'sks3': _safe_int(original_df, 'Total SKS 3', i),
            'failed_subjects': failed,
            'passed_subjects': passed,
            'sks_passed': sks_matkul * len(passed),
            'sks_failed': sks_matkul * len(failed),
        }
        risk = is_risk_label(label)
        at_risk += risk
        results.append({
            'nim': str(nim),
            'pmb': str(pmb),
            'prediction': str(label),
            'isRisk': risk,
            'details': json.dumps(details),
            'nama': str(nama),
            'prodi': str(prodi_val),
        })
    return results, at_risk, len(results) - at_risk


def save_batch(results, at_risk, safe, prodi, angkatan, semester, user):
    """Simpan batch + prediksi. Kunci dedup mencakup user & semester — tanpa
    user_id, prediksi user lain pada prodi/angkatan/semester yang sama ikut
    menimpa hasil milik user ini. Batch lama cukup di-soft-delete."""
    now = datetime.datetime.now()
    batch_name = f"#BATCH-{now.strftime('%y%m%d%H%M')}"
    semester_key = '' if str(semester) in ('Unknown', 'None', '') else str(semester)
    angkatan_key = '' if angkatan in (None, 'Unknown') else angkatan
    conn = connect()
    try:
        c = conn.cursor()
        c.execute('''UPDATE batches SET deleted_at = ?
                     WHERE user_id = ? AND prodi = ? AND IFNULL(angkatan, "") = ? AND IFNULL(semester, "") = ?
                       AND deleted_at IS NULL''',
                  (now.isoformat(timespec='seconds'), user['uid'], prodi, angkatan_key, semester_key))
        c.execute('''INSERT INTO batches (batch_name, date_uploaded, total_records, at_risk, safe, status,
                                          prodi, angkatan, uploaded_by, semester, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (batch_name, now.strftime("%d %b %Y, %H:%M"), len(results), at_risk, safe, 'Processed',
                   prodi, angkatan, user['name'], semester_key, user['uid']))
        batch_id = c.lastrowid
        c.executemany('INSERT INTO predictions (batch_id, nim, pmb, prediction, is_risk, details) '
                      'VALUES (?, ?, ?, ?, ?, ?)',
                      [(batch_id, r['nim'], r['pmb'], r['prediction'], r['isRisk'], r['details'])
                       for r in results])
        conn.commit()
    except Exception as db_err:
        raise PredictError(f"Prediksi berhasil dihitung tetapi gagal disimpan ke database: {db_err}", 500)
    finally:
        conn.close()
    return {
        'batch_id': batch_id,
        'batch_name': batch_name,
        'total': len(results),
        'atRisk': at_risk,
        'safe': safe,
        'prodi': prodi,
        'angkatan': angkatan,
        'semester': semester_key,
        'results': results,
    }
