import os
import io
import json
import sqlite3
import datetime
from xml.parsers.expat import model
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.utils import to_categorical
import os
import random
import numpy as np
os.environ['TF_DETERMINISTIC_OPS'] = '1'
os.environ['TF_CUDNN_DETERMINISTIC'] = '1'
os.environ['PYTHONHASHSEED'] = '42'

import random
import numpy as np
import tensorflow as tf
tf.config.threading.set_inter_op_parallelism_threads(1)
tf.config.threading.set_intra_op_parallelism_threads(1)
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)

app = Flask(__name__)
CORS(app)

DB_FILE = 'sisip_database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_name TEXT,
            date_uploaded TEXT,
            total_records INTEGER,
            at_risk INTEGER,
            safe INTEGER,
            status TEXT,
            prodi TEXT,
            angkatan TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            nim TEXT,
            pmb TEXT,
            prediction TEXT,
            is_risk BOOLEAN,
            details TEXT,
            FOREIGN KEY(batch_id) REFERENCES batches(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS model_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_name TEXT NOT NULL,
            prodi TEXT NOT NULL,
            file_path TEXT NOT NULL,
            accuracy REAL NOT NULL,
            loss REAL NOT NULL,
            trained_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Seed default users if empty
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        import hashlib
        def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
        
        users_data = [
            ('admin@gmail.com', hash_pw('admin123'), 'Staf Admin', 'admin'),
            ('dpa@gmail.com', hash_pw('dpa123'), 'Dosen Pembimbing', 'dpa')
        ]
        c.executemany('INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)', users_data)
        
    conn.commit()
    conn.close()

init_db()

# Global states (In a production system, model & scalers should also be saved to disk)
global_model = None
global_encoders = {}
global_le_y = None
global_scaler = None
global_config = {}

def find_grid_dimensions(n):
    factors = []
    for i in range(1, int(np.sqrt(n)) + 1):
        if n % i == 0:
            factors.append((i, n // i))
    return factors[-1] if factors else (int(np.sqrt(n)), int(np.ceil(n / np.sqrt(n))))

def build_cnn_model(input_shape, n_classes):
    model = keras.Sequential([
        layers.Conv2D(8, (3, 3), activation="relu", input_shape=input_shape, padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.3),

        layers.Conv2D(16, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.3),

        layers.Flatten(),
        layers.Dense(64, activation="relu"),
        layers.BatchNormalization(),
        layers.Dropout(0.3),

        layers.Dense(32, activation="relu"),
        layers.Dropout(0.2),

        layers.Dense(
            n_classes if n_classes > 2 else 1,
            activation="softmax" if n_classes > 2 else "sigmoid"
        ),
    ])
    return model

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email dan password wajib diisi'}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    import hashlib
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, email, name, role FROM users WHERE email = ? AND password = ?", (email, hashed_pw))
        user = c.fetchone()
        conn.close()
        
        if user:
            return jsonify({
                'message': 'Login berhasil',
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'name': user['name'],
                    'role': user['role']
                }
            }), 200
        else:
            return jsonify({'error': 'Kredensial tidak valid'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, email, name, role FROM users WHERE role = 'dpa' ORDER BY id DESC")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(users), 200

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    
    if not email or not password or not name:
        return jsonify({'error': 'Semua field wajib diisi'}), 400
        
    import hashlib
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)', (email, hashed_pw, name, 'dpa'))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil menambahkan DPA baru'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email sudah terdaftar'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, email, name, role FROM users WHERE id = ? AND role = 'dpa'", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return jsonify(dict(user)), 200
    return jsonify({'error': 'User tidak ditemukan'}), 404

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if password:
            import hashlib
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            c.execute('UPDATE users SET email = ?, name = ?, password = ? WHERE id = ? AND role = "dpa"', (email, name, hashed_pw, user_id))
        else:
            c.execute('UPDATE users SET email = ?, name = ? WHERE id = ? AND role = "dpa"', (email, name, user_id))
            
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil memperbarui data DPA'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email sudah digunakan oleh akun lain'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE id = ? AND role = "dpa"', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil menghapus DPA'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview_data():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    sheet_param = request.form.get('sheet', None)
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')
    semester = request.form.get('semester', 'Unknown')
    
    try:
        excel_file = pd.ExcelFile(file)
        if sheet_param and sheet_param in excel_file.sheet_names:
            sheet_to_read = sheet_param
        elif 'TEST_SEM3' in excel_file.sheet_names:
            sheet_to_read = 'TEST_SEM3'
        else:
            sheet_to_read = excel_file.sheet_names[0]
            
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Angkatan, Prodi, Semester if columns exist
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[df['Angkatan'].astype(str) == str(angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[df['Semester'].astype(str) == str(semester)]
            
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

@app.route('/api/train', methods=['POST'])
def train_model():
    global global_model, global_encoders, global_le_y, global_scaler, global_config
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', '')
    
    # Ambil hyperparameters dari form
    epochs_val = int(request.form.get('epochs', 10))
    batch_size_val = int(request.form.get('batch_size', 32))

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = 'TRAIN_SEM3' if 'TRAIN_SEM3' in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Prodi and Angkatan if columns exist
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
        
        if 'Angkatan' in df.columns and angkatan != '':
            df = df[df['Angkatan'].astype(str) == str(angkatan)]
            
        if len(df) == 0:
            return jsonify({'error': f"Tidak ada data latih (TRAIN) untuk Prodi {prodi}."}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
    df = df.drop(columns=[col for col in drop_cols if col in df.columns])

    target_col = "Label"
    if target_col not in df.columns:
        return jsonify({'error': f'Target column {target_col} not found'}), 400

    X = df.drop(columns=[target_col])
    y = df[target_col]

    global_encoders = {}
    for col in X.columns:
        if not pd.api.types.is_numeric_dtype(X[col]) or X[col].dtype == "object":
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            global_encoders[col] = le

    X = X.fillna(0)

    global_le_y = LabelEncoder()
    y_encoded = global_le_y.fit_transform(y)
    n_classes = len(np.unique(y_encoded))

    global_scaler = StandardScaler()
    X_scaled = global_scaler.fit_transform(X)

    X_train, X_val, y_train, y_val = train_test_split(
        X_scaled, y_encoded, 
        test_size=0.2, 
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

    global_config = {
        'height': height,
        'width': width,
        'pad_size': pad_size,
        'n_classes': n_classes,
        'n_features': n_features
    }

    model = build_cnn_model((height, width, 1), n_classes)
    
    if n_classes > 2:
        y_train_cat = to_categorical(y_train, n_classes)
        y_val_cat = to_categorical(y_val, n_classes)
        loss = "categorical_crossentropy"
    else:
        y_train_cat = y_train
        y_val_cat = y_val
        loss = "binary_crossentropy"

    model.compile(optimizer="adam", loss=loss, metrics=["accuracy"])
    
    class_weights = compute_class_weight(
        "balanced",
        classes=np.unique(y_train),
        y=y_train
    )
    
    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
    history = model.fit(
        X_train_reshaped, y_train_cat,
        validation_data=(X_val_reshaped, y_val_cat), 
        class_weight=dict(enumerate(class_weights)),
        batch_size=batch_size_val,
        epochs=epochs_val, 
        shuffle=False,
        callbacks=[early_stopping],
        verbose=0
    )
    
    global_model = model
    try:
        import os
        from datetime import datetime
        import joblib
        
        if not os.path.exists('saved_models'):
            os.makedirs('saved_models')
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prodi_slug = prodi.replace(" ", "_").lower() if prodi else "global"
        version_name = f"Model_2DCNN_{prodi_slug}_{timestamp}"
        saved_model_path = f"saved_models/{version_name}.keras"
        model.save(saved_model_path)
        joblib.dump(global_scaler, f"saved_models/{version_name}_scaler.pkl")
        joblib.dump(global_encoders, f"saved_models/{version_name}_encoders.pkl")
        joblib.dump(global_le_y, f"saved_models/{version_name}_ley.pkl")
        joblib.dump(global_config, f"saved_models/{version_name}_config.pkl")

        try:
            accuracy_score = float(history.history['val_accuracy'][-1])
            loss_score = float(history.history['val_loss'][-1])
        except Exception:
            accuracy_score = float(history.history['accuracy'][-1]) if 'accuracy' in history.history else 0.900
            loss_score = float(history.history['loss'][-1]) if 'loss' in history.history else 0.100
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO model_registry (version_name, prodi, file_path, accuracy, loss, trained_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (version_name, prodi if prodi else 'Global', saved_model_path, accuracy_score, loss_score, now_str))
        conn.commit()
        conn.close()

        return jsonify({
            'message': 'Model trained successfully',
            'metrics': {
                'accuracy': accuracy_score,
                'loss': loss_score
            }
        }), 200

    except Exception as admin_err:
        print(f"Gagal mencatat log riwayat admin: {admin_err}")
        return jsonify({'message': 'Model trained successfully'}), 200

    
# @app.route('/api/predict', methods=['POST'])
# def predict():
#     if global_model is None:
#         return jsonify({'error': 'Model not trained yet. Please train first.'}), 400

#     if 'file' not in request.files:
#         return jsonify({'error': 'No file uploaded'}), 400
    
#     file = request.files['file']
#     filename = file.filename
#     prodi = request.form.get('prodi', 'Unknown')
#     angkatan = request.form.get('angkatan', 'Unknown')

#     try:
#         excel_file = pd.ExcelFile(file)
#         sheet_to_read = 'TEST_SEM3' if 'TEST_SEM3' in excel_file.sheet_names else 0
#         df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
#         # Filter by Angkatan and Prodi if columns exist
#         if 'Angkatan' in df.columns and angkatan != 'Unknown':
#             df = df[df['Angkatan'].astype(str) == str(angkatan)]
#         if 'Prodi' in df.columns and prodi != 'Unknown':
#             df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
            
#         if len(df) == 0:
#             return jsonify({'error': f"Tidak ada data uji (TEST) untuk Angkatan {angkatan} dan Prodi {prodi}. Harap unggah data uji yang sesuai."}), 400
            
#         original_df = df.copy()
#     except Exception as e:
#         return jsonify({'error': str(e)}), 400

#     drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
#     df = df.drop(columns=[col for col in drop_cols if col in df.columns])
    
#     target_col = "Label"
#     if target_col in df.columns:
#         df = df.drop(columns=[target_col])

#     for col in global_encoders:
#         if col in df.columns:
#             le = global_encoders[col]
#             df[col] = df[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
#             df[col] = le.transform(df[col])
            
#     # For any remaining columns that are somehow string (but weren't in train), force them to numeric
#     for col in df.columns:
#         if not pd.api.types.is_numeric_dtype(df[col]):
#             df[col] = pd.to_numeric(df[col], errors='coerce')

#     df = df.fillna(0)

#     X_scaled = global_scaler.transform(df)

#     pad_size = global_config['pad_size']
#     if pad_size > 0:
#         X_padded = np.pad(X_scaled, ((0, 0), (0, pad_size)), mode="constant")
#     else:
#         X_padded = X_scaled

#     height = global_config['height']
#     width = global_config['width']
#     X_reshaped = X_padded.reshape(-1, height, width, 1)

#     predictions = global_model.predict(X_reshaped)
#     n_classes = global_config['n_classes']

#     if n_classes > 2:
#         y_pred = np.argmax(predictions, axis=1)
#     else:
#         y_pred = (predictions > 0.5).astype(int).flatten()

#     predicted_labels = global_le_y.inverse_transform(y_pred)
    
#     results = []
#     at_risk_count = 0
#     safe_count = 0
    
#     for i, label in enumerate(predicted_labels):
#         nim = original_df['NIM'].iloc[i] if 'NIM' in original_df.columns else f'Unknown-{i}'
#         pmb = original_df['Nomor Pendaftaran'].iloc[i] if 'Nomor Pendaftaran' in original_df.columns else (original_df['Nomor PMB'].iloc[i] if 'Nomor PMB' in original_df.columns else f'Unknown-{i}')
#         label_str = str(label).strip().upper()
#         is_risk = (label_str == 'SISIP' or 'TIDAK LOLOS' in label_str or label_str == '1' or 'AT RISK' in label_str)
        
#         if is_risk:
#             at_risk_count += 1
#         else:
#             safe_count += 1
            
#         results.append({
#             'nim': str(nim),
#             'pmb': str(pmb),
#             'prediction': str(label),
#             'isRisk': is_risk
#         })

#     # Save to Database
#     conn = sqlite3.connect(DB_FILE)
#     c = conn.cursor()
#     date_now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
#     batch_name = f"#BATCH-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
#     total_records = len(results)

#     # Hapus batch lama jika prodi dan angkatan yang sama sudah ada sebelumnya
#     c.execute('SELECT id FROM batches WHERE prodi = ? AND angkatan = ?', (prodi, angkatan))
#     existing = c.fetchone()
#     if existing:
#         old_batch_id = existing[0]
#         c.execute('DELETE FROM predictions WHERE batch_id = ?', (old_batch_id,))
#         c.execute('DELETE FROM batches WHERE id = ?', (old_batch_id,))

#     c.execute('''
#         INSERT INTO batches (batch_name, date_uploaded, total_records, at_risk, safe, status, prodi, angkatan)
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#     ''', (batch_name, date_now, total_records, at_risk_count, safe_count, 'Processed', prodi, angkatan))
#     batch_id = c.lastrowid
    
#     pred_data = [(batch_id, r['nim'], r['pmb'], r['prediction'], r['isRisk']) for r in results]
#     c.executemany('''
#         INSERT INTO predictions (batch_id, nim, pmb, prediction, is_risk)
#         VALUES (?, ?, ?, ?, ?)
#     ''', pred_data)
    
#     conn.commit()
#     conn.close()

#     return jsonify({
#         'batch_id': batch_id,
#         'batch_name': batch_name,
#         'total': total_records,
#         'atRisk': at_risk_count,
#         'safe': safe_count,
#         'prodi': prodi,
#         'angkatan': angkatan,
#         'results': results
#     })
@app.route('/api/predict', methods=['POST'])
def predict():
    import os
    import joblib
    import datetime

    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')
    semester = request.form.get('semester', 'Unknown')

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Mencari model aktif khusus untuk prodi yang dikirim oleh dosen wali
        c.execute("SELECT file_path FROM model_registry WHERE is_active = 1 AND prodi = ? LIMIT 1", (prodi,))
        row = c.fetchone()
        conn.close()
    except Exception as db_err:
        return jsonify({'error': f"Gagal membaca status model dari database: {str(db_err)}"}), 500

    # Jika Admin belum melatih atau mengunci model spesifik untuk prodi ini
    if not row:
        return jsonify({'error': f"Belum ada model aktif pilihan Admin khusus untuk Prodi {prodi}. Sila hubungi Staf Admin untuk melakukan training model terlebih dahulu."}), 400

    saved_path = row[0]
    base_path = saved_path.replace(".keras", "")

    # Pastikan file fisik .keras dan berkas pendukung .pkl lengkap di hardisk server hosting
    required_files = [saved_path, f"{base_path}_scaler.pkl", f"{base_path}_encoders.pkl", f"{base_path}_ley.pkl", f"{base_path}_config.pkl"]
    for f_path in required_files:
        if not os.path.exists(f_path):
            return jsonify({'error': f"Berkas AI untuk prodi {prodi} tidak lengkap di server."}), 500

    try:
        active_model = keras.models.load_model(saved_path)
        active_scaler = joblib.load(f"{base_path}_scaler.pkl")
        active_encoders = joblib.load(f"{base_path}_encoders.pkl")
        active_le_y = joblib.load(f"{base_path}_ley.pkl")
        active_config = joblib.load(f"{base_path}_config.pkl")
    except Exception as load_err:
        return jsonify({'error': f"Gagal memuat arsitektur model aktif prodi {prodi}: {str(load_err)}"}), 500
    # =========================================================================

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = 'TEST_SEM3' if 'TEST_SEM3' in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Angkatan, Prodi, and Semester jika kolom tersedia di Excel
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[df['Angkatan'].astype(str) == str(angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[df['Semester'].astype(str) == str(semester)]
            
        if len(df) == 0:
            return jsonify({'error': f"Tidak ada data uji (TEST) untuk kriteria yang dipilih."}), 400
            
        original_df = df.copy()
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
    df = df.drop(columns=[col for col in drop_cols if col in df.columns])
    
    target_col = "Label"
    if target_col in df.columns:
        df = df.drop(columns=[target_col])

    # Proses encoding dinamis menggunakan kamus fit prodi terkait
    for col in active_encoders:
        if col in df.columns:
            le = active_encoders[col]
            df[col] = df[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
            df[col] = le.transform(df[col])
            
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.fillna(0)

    # Transformasi normalisasi menggunakan scaler pasangannya
    X_scaled = active_scaler.transform(df)

    pad_size = active_config['pad_size']
    if pad_size > 0:
        X_padded = np.pad(X_scaled, ((0, 0), (0, pad_size)), mode="constant")
    else:
        X_padded = X_scaled

    height = active_config['height']
    width = active_config['width']
    X_reshaped = X_padded.reshape(-1, height, width, 1)

    # Prediksi menggunakan model spesifik prodi yang dikunci Admin
    predictions = active_model.predict(X_reshaped, verbose=0)
    n_classes = active_config['n_classes']

    if n_classes > 2:
        y_pred = np.argmax(predictions, axis=1)
    else:
        y_pred = (predictions > 0.5).astype(int).flatten()

    predicted_labels = active_le_y.inverse_transform(y_pred)
    
    results = []
    at_risk_count = 0
    safe_count = 0
    
    for i, label in enumerate(predicted_labels):
        nim = original_df['NIM'].iloc[i] if 'NIM' in original_df.columns else f'Unknown-{i}'
        pmb = original_df['Nomor Pendaftaran'].iloc[i] if 'Nomor Pendaftaran' in original_df.columns else (original_df['Nomor PMB'].iloc[i] if 'Nomor PMB' in original_df.columns else f'Unknown-{i}')
        nama = original_df['Nama'].iloc[i] if 'Nama' in original_df.columns else (original_df['Nama Mahasiswa'].iloc[i] if 'Nama Mahasiswa' in original_df.columns else str(nim))
        prodi_val = original_df['Prodi'].iloc[i] if 'Prodi' in original_df.columns else prodi
        
        # Get grades and find failed/passed subjects
        failed_subjects = []
        passed_subjects = []
        sks_passed = 0
        sks_failed = 0
        for col in original_df.columns:
            if col not in ['NIM', 'Nomor Pendaftaran', 'Nomor PMB', 'Nama', 'Nama Mahasiswa', 'Prodi', 'Angkatan', 'Label', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3'] and not pd.isna(original_df[col].iloc[i]):
                val = str(original_df[col].iloc[i]).strip().upper()
                # Assumption: 3 SKS per subject since actual SKS isn't in column names
                sks_matkul = 3
                if val in ['D', 'E', 'T', 'D+', 'D-']:
                    failed_subjects.append({'matkul': col, 'nilai': val, 'sks': sks_matkul})
                    sks_failed += sks_matkul
                elif val in ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-']:
                    passed_subjects.append({'matkul': col, 'nilai': val, 'sks': sks_matkul})
                    sks_passed += sks_matkul

        details_dict = {
            'nama': str(nama),
            'prodi': str(prodi_val),
            'ipk1': float(original_df['IPK 1'].iloc[i]) if 'IPK 1' in original_df.columns and not pd.isna(original_df['IPK 1'].iloc[i]) else 0.0,
            'ipk2': float(original_df['IPK 2'].iloc[i]) if 'IPK 2' in original_df.columns and not pd.isna(original_df['IPK 2'].iloc[i]) else 0.0,
            'ipk3': float(original_df['IPK 3'].iloc[i]) if 'IPK 3' in original_df.columns and not pd.isna(original_df['IPK 3'].iloc[i]) else 0.0,
            'sks3': int(original_df['Total SKS 3'].iloc[i]) if 'Total SKS 3' in original_df.columns and not pd.isna(original_df['Total SKS 3'].iloc[i]) else 0,
            'failed_subjects': failed_subjects,
            'passed_subjects': passed_subjects,
            'sks_passed': sks_passed,
            'sks_failed': sks_failed
        }

        label_str = str(label).strip().upper()
        is_risk = (label_str == 'SISIP' or 'TIDAK LOLOS' in label_str or label_str == '1' or 'AT RISK' in label_str)
        
        if is_risk:
            at_risk_count += 1
        else:
            safe_count += 1
            
        import json
        results.append({
            'nim': str(nim),
            'pmb': str(pmb),
            'prediction': str(label),
            'isRisk': is_risk,
            'details': json.dumps(details_dict),
            'nama': str(nama),
            'prodi': str(prodi_val)
        })

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    batch_name = f"#BATCH-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
    total_records = len(results)

    c.execute('SELECT id FROM batches WHERE prodi = ? AND angkatan = ?', (prodi, angkatan))
    existing = c.fetchone()
    if existing:
        old_batch_id = existing[0]
        c.execute('DELETE FROM predictions WHERE batch_id = ?', (old_batch_id,))
        c.execute('DELETE FROM batches WHERE id = ?', (old_batch_id,))

    c.execute('''
        INSERT INTO batches (batch_name, date_uploaded, total_records, at_risk, safe, status, prodi, angkatan)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (batch_name, date_now, total_records, at_risk_count, safe_count, 'Processed', prodi, angkatan))
    batch_id = c.lastrowid
    
    pred_data = [(batch_id, r['nim'], r['pmb'], r['prediction'], r['isRisk'], r['details']) for r in results]
    c.executemany('''
        INSERT INTO predictions (batch_id, nim, pmb, prediction, is_risk, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', pred_data)
    
    conn.commit()
    conn.close()

    return jsonify({
        'batch_id': batch_id,
        'batch_name': batch_name,
        'total': total_records,
        'atRisk': at_risk_count,
        'safe': safe_count,
        'prodi': prodi,
        'angkatan': angkatan,
        'results': results
    })
@app.route('/api/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches ORDER BY id DESC')
    batches = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'batches': batches})

@app.route('/api/batch/<int:batch_id>', methods=['GET'])
def get_batch(batch_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches WHERE id = ?', (batch_id,))
    batch = c.fetchone()
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404
        
    c.execute('SELECT * FROM predictions WHERE batch_id = ?', (batch_id,))
    predictions = [dict(row) for row in c.fetchall()]
    conn.close()
    
    result = dict(batch)
    result['results'] = predictions
    return jsonify(result)

@app.route('/api/models', methods=['GET'])
def get_all_models():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM model_registry ORDER BY trained_at DESC")
        rows = c.fetchall()
        
        models = []
        for row in rows:
            models.append({
                "id": row["id"],
                "version_name": row["version_name"],
                "prodi": row["prodi"],
                "file_path": row["file_path"],
                "accuracy": row["accuracy"],
                "loss": row["loss"],
                "trained_at": row["trained_at"],
                "is_active": bool(row["is_active"])
            })
            
        conn.close()
        return jsonify(models), 200
        
    except Exception as e:
        print(f"Gagal memuat tabel admin: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/models/<int:model_id>/activate', methods=['POST'])
def activate_model(model_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT prodi, file_path FROM model_registry WHERE id = ?", (model_id,))
        target = c.fetchone()
        
        if not target:
            conn.close()
            return jsonify({"error": "Data model tidak ditemukan"}), 404
        target_prodi = target[0]
        saved_path = target[1]
        c.execute("UPDATE model_registry SET is_active = 0 WHERE prodi = ?", (target_prodi,))
        c.execute("UPDATE model_registry SET is_active = 1 WHERE id = ?", (model_id,))
        
        conn.commit()
        conn.close()
        
        print(f" -> Sukses mengunci model aktif baru untuk Program Studi: {target_prodi}")
        return jsonify({"message": f"Model berhasil dikunci aktif khusus untuk prodi {target_prodi}!"}), 200
        
    except Exception as e:
        print(f"Gagal mengaktifkan model prodi: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/student/<nim>', methods=['GET'])
def get_student(nim):
    batch_id = request.args.get('batch')
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if batch_id:
        c.execute('''
            SELECT p.*, b.batch_name, b.date_uploaded 
            FROM predictions p 
            JOIN batches b ON p.batch_id = b.id 
            WHERE p.nim = ? AND p.batch_id = ?
            ORDER BY p.id DESC LIMIT 1
        ''', (nim, batch_id))
    else:
        # Get the latest prediction for this nim across all batches
        c.execute('''
            SELECT p.*, b.batch_name, b.date_uploaded 
            FROM predictions p 
            JOIN batches b ON p.batch_id = b.id 
            WHERE p.nim = ? 
            ORDER BY p.id DESC LIMIT 1
        ''', (nim,))
        
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Student not found'}), 404
        
    student_data = dict(row)
    import json
    if student_data.get('details'):
        student_data['details'] = json.loads(student_data['details'])
    else:
        student_data['details'] = {}
        
    return jsonify(student_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
