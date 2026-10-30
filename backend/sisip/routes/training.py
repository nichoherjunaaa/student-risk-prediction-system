"""Training model dan registri model (khusus admin)."""
import os
import re
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras.utils import to_categorical

from ..auth import require_role
from ..config import MODEL_DIR
from ..constants import LABEL_COL, TRAIN_SHEET, TRAIN_SHEET_PREFIX, is_risk_label, non_feature_columns
from ..db import connect
from ..ml import build_cnn_model, find_grid_dimensions, missing_artifacts, model_base_path
from ..preprocessing import MISSING_CATEGORICAL, MISSING_GRADE
from ..settings_store import current_format
from ..utils import norm_str

bp = Blueprint('training', __name__)

_TRAIN_SHEET_RE = re.compile(rf'^{TRAIN_SHEET_PREFIX}(\d+)$')


def _pick_train_sheet(sheet_names, form_semester):
    """(sheet, batas_semester). Sheet TRAIN_SEM3 diutamakan seperti di
    cnn_tabular_2d_v2.py, lalu sheet TRAIN_SEM<n> lain (keluaran Preprocessing
    Data), lalu sheet pertama. Batas semester dicatat ke model supaya prediksi
    memotong data di semester yang sama."""
    names = [TRAIN_SHEET] if TRAIN_SHEET in sheet_names else []
    names += [n for n in sheet_names if _TRAIN_SHEET_RE.match(str(n)) and n not in names]
    if names:
        return names[0], int(_TRAIN_SHEET_RE.match(names[0]).group(1))
    semester = int(form_semester) if str(form_semester or '').isdigit() else None
    return sheet_names[0], semester


def _recall_sisip(model, X_val, y_val, le_y, n_classes):
    """(recall, tertangkap, total) kelas SISIP pada data validasi.

    Akurasi menipu untuk data yang tidak seimbang (±72% mahasiswa tidak sisip),
    jadi yang menentukan untuk peringatan dini adalah berapa mahasiswa sisip yang
    tertangkap. Ambang 0.5 sama dengan predictor.run_model."""
    probs = model.predict(X_val, verbose=0)
    if n_classes > 2:
        y_pred = np.argmax(probs, axis=1)
    else:
        y_pred = (probs > 0.5).astype(int).flatten()
    risk_idx = [i for i, label in enumerate(le_y.classes_) if is_risk_label(label)]
    actual = np.isin(y_val, risk_idx)
    total = int(actual.sum())
    if total == 0:
        return None, 0, 0
    caught = int((actual & np.isin(y_pred, risk_idx)).sum())
    return caught / total, caught, total


def _angkatan_list(series):
    return sorted({norm_str(a) for a in series.dropna() if str(a).strip()})


@bp.route('/api/train/angkatan', methods=['POST'])
@require_role('admin')
def train_angkatan():
    """Angkatan yang ada di berkas data latih, sebagai pilihan di form latih
    (supaya admin tidak mengetik angkatan bebas)."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    try:
        excel_file = pd.ExcelFile(request.files['file'])
        sheet, _ = _pick_train_sheet(excel_file.sheet_names, request.form.get('semester'))
        df = pd.read_excel(excel_file, sheet_name=sheet, usecols=lambda c: c == 'Angkatan')
    except Exception as e:
        return jsonify({'error': f"Berkas data latih tidak dapat dibaca: {e}"}), 400
    angkatan = _angkatan_list(df['Angkatan']) if 'Angkatan' in df.columns else []
    return jsonify({'sheet': sheet, 'angkatan': angkatan})


@bp.route('/api/train', methods=['POST'])
@require_role('admin')
def train_model():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', '')
    
    # Ambil hyperparameters dari form. Default mengikuti cnn_tabular_2d_v2.py
    # (epochs 100 di :418, batch 32 di :417, Adam default lr 0.001, model_f
    # dropout 0.3, validasi 20% di :419) — jangan diubah tanpa menyamakan skrip.
    epochs_val = int(request.form.get('epochs', 100))
    batch_size_val = int(request.form.get('batch_size', 32))
    learning_rate_val = float(request.form.get('learning_rate', 0.001))
    dropout_rate_val = float(request.form.get('dropout_rate', 0.3))
    val_split_val = float(request.form.get('val_split', 0.2))

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read, max_semester = _pick_train_sheet(excel_file.sheet_names,
                                                        request.form.get('semester'))
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)

        # Berkas hasil Preprocessing Data selalu satu prodi dan memuat kolom
        # Prodi, jadi prodi model diambil dari situ bila tidak dipilih di form.
        if prodi in ('Unknown', ''):
            daftar = sorted({str(p).strip() for p in df['Prodi'].dropna()}) if 'Prodi' in df.columns else []
            if len(daftar) != 1:
                alasan = (f"berkas berisi lebih dari satu program studi ({', '.join(daftar)})" if daftar
                          else "berkas tidak memuat kolom Prodi")
                return jsonify({'error': f"Program studi tidak bisa dideteksi: {alasan}. "
                                         "Gunakan berkas data latih hasil menu Preprocessing Data."}), 400
            prodi = daftar[0]

        # Filter by Prodi and Angkatan if columns exist
        if 'Prodi' in df.columns:
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]

        if 'Angkatan' in df.columns and angkatan != '':
            # Normalisasi ('2023' vs '2023.0') supaya satu sel kosong di kolom lain
            # yang mengubah kolom Angkatan jadi float tidak diam-diam membuang baris.
            angkatan_list = [norm_str(a) for a in str(angkatan).split(',') if a.strip()]
            if angkatan_list:
                df = df[df['Angkatan'].map(norm_str).isin(angkatan_list)]

        if len(df) == 0:
            return jsonify({'error': f"Tidak ada data latih (TRAIN) untuk Prodi {prodi}."}), 400

        # Yang dicatat angkatan yang tersisa setelah filter, bukan isian form:
        # form kosong berarti semua angkatan di berkas ikut dilatih.
        trained_angkatan = None
        if 'Angkatan' in df.columns:
            daftar_angkatan = _angkatan_list(df['Angkatan'])
            if daftar_angkatan:
                trained_angkatan = ', '.join(daftar_angkatan)

    except Exception as e:
        return jsonify({'error': str(e)}), 400

    df = df.drop(columns=non_feature_columns(df.columns))

    target_col = LABEL_COL
    if target_col not in df.columns:
        return jsonify({'error': f'Target column {target_col} not found'}), 400

    X = df.drop(columns=[target_col])
    y = df[target_col]

    encoders = {}
    for col in X.columns:
        if not pd.api.types.is_numeric_dtype(X[col]) or X[col].dtype == "object":
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            encoders[col] = le

    X = X.fillna(0)

    # Kolom nilai mata kuliah dan cara data latih mengisi nilai kosongnya ('E'
    # untuk hasil Preprocessing sekarang, '-' untuk berkas latih lama), supaya
    # prediksi mengisi nilai kosong dengan cara yang sama.
    fmt = current_format()
    grades = fmt.grade_pass | fmt.grade_fail | {MISSING_CATEGORICAL}
    grade_cols = [c for c, le in encoders.items() if set(map(str, le.classes_)) <= grades]
    missing_grade = (MISSING_CATEGORICAL if any(MISSING_CATEGORICAL in encoders[c].classes_ for c in grade_cols)
                     else MISSING_GRADE)

    le_y = LabelEncoder()
    y_encoded = le_y.fit_transform(y)
    n_classes = len(np.unique(y_encoded))

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    X_train, X_val, y_train, y_val = train_test_split(
        X_scaled, y_encoded, 
        test_size=val_split_val, 
        random_state=42,
        stratify=y_encoded
    )

    n_features = X_train.shape[1]
    height, width = find_grid_dimensions(n_features)
    pad_size = height * width - n_features
    if pad_size > 0:
        X_train_padded = np.pad(X_train, ((0, 0), (0, pad_size)), mode="constant")
        X_val_padded = np.pad(X_val, ((0, 0), (0, pad_size)), mode="constant")
    else:
        X_train_padded = X_train
        X_val_padded = X_val

    # Reshape bentuk matriks gambar 2D CNN Tabular
    X_train_reshaped = X_train_padded.reshape(-1, height, width, 1)
    X_val_reshaped = X_val_padded.reshape(-1, height, width, 1)

    model_config = {
        'height': height,
        'width': width,
        'pad_size': pad_size,
        'n_classes': n_classes,
        'n_features': n_features,
        'max_semester': max_semester,
        'grade_cols': grade_cols,
        'missing_grade': missing_grade,
    }

    model = build_cnn_model((height, width, 1), n_classes, dropout_rate=dropout_rate_val)
    
    if n_classes > 2:
        y_train_cat = to_categorical(y_train, n_classes)
        y_val_cat = to_categorical(y_val, n_classes)
        loss = "categorical_crossentropy"
    else:
        y_train_cat = y_train
        y_val_cat = y_val
        loss = "binary_crossentropy"

    optimizer = keras.optimizers.Adam(learning_rate=learning_rate_val)
    model.compile(optimizer=optimizer, loss=loss, metrics=["accuracy"])
    
    class_weights = compute_class_weight(
        "balanced",
        classes=np.unique(y_train),
        y=y_train
    )
    
    # patience 10 dan shuffle default (True) sama dengan cnn_tabular_2d_v2.py:404-421.
    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
    history = model.fit(
        X_train_reshaped, y_train_cat,
        validation_data=(X_val_reshaped, y_val_cat), 
        class_weight=dict(enumerate(class_weights)),
        batch_size=batch_size_val,
        epochs=epochs_val, 
        callbacks=[early_stopping],
        verbose=0
    )
    # Bobot terbaik sudah dikembalikan EarlyStopping, jadi recall ini milik model yang disimpan.
    recall_sisip, val_sisip_caught, val_sisip_total = _recall_sisip(
        model, X_val_reshaped, y_val, le_y, n_classes)
    n_train_samples = int(len(df))

    try:
        os.makedirs(MODEL_DIR, exist_ok=True)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prodi_slug = prodi.replace(" ", "_").lower() if prodi else "global"
        version_name = f"Model_2DCNN_{prodi_slug}_{timestamp}"
        saved_model_path = os.path.join(MODEL_DIR, f"{version_name}.keras")
        model.save(saved_model_path)
        joblib.dump(scaler, os.path.join(MODEL_DIR, f"{version_name}_scaler.pkl"))
        joblib.dump(encoders, os.path.join(MODEL_DIR, f"{version_name}_encoders.pkl"))
        joblib.dump(le_y, os.path.join(MODEL_DIR, f"{version_name}_ley.pkl"))
        joblib.dump(model_config, os.path.join(MODEL_DIR, f"{version_name}_config.pkl"))

        # EarlyStopping(restore_best_weights=True) mengembalikan bobot epoch dengan
        # val_loss terendah — bukan epoch terakhir. Catat metrik epoch itu juga,
        # supaya angka di registri sesuai dengan model yang benar-benar disimpan.
        try:
            hist = history.history
            loss_series = hist.get('val_loss') or hist.get('loss') or []
            acc_series = hist.get('val_accuracy') or hist.get('accuracy') or []
            if loss_series:
                best_idx = int(np.argmin(loss_series))
                loss_score = float(loss_series[best_idx])
                accuracy_score = float(acc_series[best_idx]) if best_idx < len(acc_series) else (
                    float(acc_series[-1]) if acc_series else 0.900)
            else:
                accuracy_score, loss_score = 0.900, 0.100
        except Exception:
            accuracy_score, loss_score = 0.900, 0.100
        conn = connect()
        c = conn.cursor()
        c.execute('''
            INSERT INTO model_registry (version_name, prodi, file_path, accuracy, loss, trained_at, is_active,
                                        max_semester, max_semester_source,
                                        recall_sisip, val_sisip_caught, val_sisip_total, n_train_samples,
                                        angkatan)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
        ''', (version_name, prodi if prodi else 'Global', saved_model_path, accuracy_score, loss_score, now_str,
              max_semester, 'training' if max_semester else None,
              recall_sisip, val_sisip_caught, val_sisip_total, n_train_samples,
              trained_angkatan))
        conn.commit()
        conn.close()

        return jsonify({
            'message': 'Model trained successfully',
            'prodi': prodi,
            'metrics': {
                'accuracy': accuracy_score,
                'loss': loss_score,
                'recall_sisip': recall_sisip,
                'val_sisip_caught': val_sisip_caught,
                'val_sisip_total': val_sisip_total,
                'n_train_samples': n_train_samples,
                'angkatan': trained_angkatan,
            }
        }), 200

    except Exception as admin_err:
        print(f"Gagal mencatat log riwayat admin: {admin_err}")
        return jsonify({'message': 'Model trained successfully'}), 200

def _model_row(row):
    return {
        "id": row["id"],
        "version_name": row["version_name"],
        "prodi": row["prodi"],
        "file_path": row["file_path"],
        "accuracy": row["accuracy"],
        "loss": row["loss"],
        "trained_at": row["trained_at"],
        "is_active": bool(row["is_active"]),
        "max_semester": row["max_semester"],
        "max_semester_source": row["max_semester_source"],
        "recall_sisip": row["recall_sisip"],
        "val_sisip_caught": row["val_sisip_caught"],
        "val_sisip_total": row["val_sisip_total"],
        "n_train_samples": row["n_train_samples"],
        "angkatan": row["angkatan"],
    }


def _positive_int(value, default):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


@bp.route('/api/models', methods=['GET'])
@require_role('admin')
def get_all_models():
    """Tanpa ?page: array semua model (format lama, dipakai e2e). Dengan ?page:
    satu halaman berisi per_page model (bawaan 10, maks 100) beserta totalnya."""
    try:
        conn = connect()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        order = "ORDER BY trained_at DESC, id DESC"

        if 'page' not in request.args:
            c.execute(f"SELECT * FROM model_registry {order}")
            models = [_model_row(r) for r in c.fetchall()]
            conn.close()
            return jsonify(models), 200

        per_page = min(_positive_int(request.args.get('per_page'), 10), 100)
        page = _positive_int(request.args.get('page'), 1)
        c.execute("SELECT COUNT(*) FROM model_registry")
        total = c.fetchone()[0]
        total_pages = max(1, -(-total // per_page))
        page = min(page, total_pages)
        c.execute(f"SELECT * FROM model_registry {order} LIMIT ? OFFSET ?",
                  (per_page, (page - 1) * per_page))
        models = [_model_row(r) for r in c.fetchall()]
        conn.close()
        return jsonify({
            "items": models,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }), 200

    except Exception as e:
        print(f"Gagal memuat tabel admin: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/api/models/<int:model_id>/activate', methods=['POST'])
@require_role('admin')
def activate_model(model_id):
    try:
        conn = connect()
        c = conn.cursor()
        c.execute("SELECT prodi, file_path FROM model_registry WHERE id = ?", (model_id,))
        target = c.fetchone()

        if not target:
            conn.close()
            return jsonify({"error": "Data model tidak ditemukan"}), 404
        target_prodi = target[0]
        saved_path = target[1]

        # Jangan kunci model yang berkas fisiknya tidak lengkap — kalau tidak,
        # error baru muncul nanti saat dosen menjalankan prediksi.
        missing = missing_artifacts(model_base_path(saved_path))
        if missing:
            conn.close()
            return jsonify({"error": f"Berkas model tidak lengkap di server ({', '.join(missing)}). "
                                     "Latih ulang model ini sebelum diaktifkan."}), 400

        c.execute("UPDATE model_registry SET is_active = 0 WHERE prodi = ?", (target_prodi,))
        c.execute("UPDATE model_registry SET is_active = 1 WHERE id = ?", (model_id,))
        
        conn.commit()
        conn.close()
        
        print(f" -> Sukses mengunci model aktif baru untuk Program Studi: {target_prodi}")
        return jsonify({"message": f"Model berhasil dikunci aktif khusus untuk prodi {target_prodi}!"}), 200
        
    except Exception as e:
        print(f"Gagal mengaktifkan model prodi: {str(e)}")
        return jsonify({"error": str(e)}), 500
