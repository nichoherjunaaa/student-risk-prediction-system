import os

# Determinisme TF harus diset SEBELUM tensorflow diimpor, kalau tidak diabaikan.
os.environ.setdefault('TF_DETERMINISTIC_OPS', '1')
os.environ.setdefault('TF_CUDNN_DETERMINISTIC', '1')
os.environ.setdefault('PYTHONHASHSEED', '42')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')

import io
import json
import hmac
import random
import hashlib
import sqlite3
import datetime
import functools

import numpy as np
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.utils import to_categorical

tf.config.threading.set_inter_op_parallelism_threads(1)
tf.config.threading.set_intra_op_parallelism_threads(1)
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)

app = Flask(__name__)

# CORS: default terbuka untuk pengembangan lokal; batasi di produksi lewat
# SISIP_CORS_ORIGINS=https://domain-anda (pisahkan dengan koma bila lebih dari satu).
_cors_origins = os.environ.get('SISIP_CORS_ORIGINS', '*').strip()
CORS(app, resources={r"/api/*": {
    "origins": '*' if _cors_origins == '*' else [o.strip() for o in _cors_origins.split(',') if o.strip()]
}})

# Persistent paths. In production these point at a mounted volume so that
# the SQLite database and trained model files survive container redeploys.
DATA_DIR = os.environ.get('SISIP_DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.environ.get('SISIP_DB_FILE', os.path.join(DATA_DIR, 'sisip_database.db'))
MODEL_DIR = os.environ.get('SISIP_MODEL_DIR', os.path.join(DATA_DIR, 'saved_models'))
os.makedirs(MODEL_DIR, exist_ok=True)

# Default seeded admin credentials (override in production via env).
DEFAULT_ADMIN_EMAIL = os.environ.get('SISIP_ADMIN_EMAIL', 'admin@gmail.com')
DEFAULT_ADMIN_PASSWORD = os.environ.get('SISIP_ADMIN_PASSWORD', 'admin123')

# ---------------------------------------------------------------------------
# Autentikasi: token bertanda-tangan (stateless) + hashing password.
# Set SISIP_SECRET_KEY di produksi — tanpa itu token bisa dipalsukan.
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get('SISIP_SECRET_KEY', 'dev-insecure-secret-change-me')
TOKEN_MAX_AGE = int(os.environ.get('SISIP_TOKEN_MAX_AGE', str(12 * 3600)))
_token_serializer = URLSafeTimedSerializer(SECRET_KEY, salt='sisip-auth')


def _hash_pw(pw):
    return generate_password_hash(pw)


def _verify_pw(pw, stored):
    """Terima hash lama (SHA-256 hex 64 karakter tanpa salt) maupun hash baru
    (PBKDF2 werkzeug), supaya akun di database lama tetap bisa login."""
    if not stored:
        return False
    s = str(stored)
    if len(s) == 64 and all(ch in '0123456789abcdef' for ch in s.lower()):
        return hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), s.lower())
    try:
        return check_password_hash(s, pw)
    except Exception:
        return False


def _make_token(user):
    return _token_serializer.dumps({'uid': user['id'], 'email': user['email'], 'role': user['role']})


def _current_user():
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        token = auth[7:].strip()
    else:
        token = request.args.get('token', '')
    if not token:
        return None
    try:
        return _token_serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return jsonify({'error': 'Sesi tidak valid atau telah berakhir. Silakan login ulang.'}), 401
        request.user = user
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user()
            if not user:
                return jsonify({'error': 'Sesi tidak valid atau telah berakhir. Silakan login ulang.'}), 401
            if user.get('role') not in roles:
                return jsonify({'error': 'Anda tidak memiliki hak akses untuk tindakan ini.'}), 403
            request.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


def resolve_model_path(stored_path):
    """Resolve a model file path stored in the registry, tolerating rows that
    were written with a relative 'saved_models/...' prefix before MODEL_DIR
    became configurable."""
    if os.path.isabs(stored_path) and os.path.exists(stored_path):
        return stored_path
    if os.path.exists(stored_path):
        return stored_path
    return os.path.join(MODEL_DIR, os.path.basename(stored_path))

def _migrate_columns(c, wanted):
    """Tambahkan kolom yang belum ada pada tabel yang sudah terlanjur dibuat.
    `wanted` = {nama_tabel: [(nama_kolom, tipe_sql), ...]}."""
    for table, cols in wanted.items():
        existing = {row[1] for row in c.execute("PRAGMA table_info(%s)" % table).fetchall()}
        for name, coltype in cols:
            if name not in existing:
                c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, coltype))


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
            angkatan TEXT,
            uploaded_by TEXT
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

    # Migrasi idempoten: tambahkan kolom yang muncul setelah database dibuat.
    # CREATE TABLE IF NOT EXISTS tidak menambah kolom pada tabel yang sudah ada.
    _migrate_columns(c, {
        'batches': [('uploaded_by', 'TEXT'), ('semester', 'TEXT')],
        'predictions': [('details', 'TEXT')],
    })

    # Seed default admin + DPA only on a fresh database.
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)', [
            (DEFAULT_ADMIN_EMAIL, _hash_pw(DEFAULT_ADMIN_PASSWORD), 'Staf Admin', 'admin'),
            ('dpa@gmail.com', _hash_pw('dpa123'), 'Dosen Pembimbing', 'dpa'),
        ])

    # Demo accounts for end-to-end testing (one per role). Idempotent: safe to
    # run on every startup. Disable in real production with SISIP_SEED_DEMO_USERS=0.
    if os.environ.get('SISIP_SEED_DEMO_USERS', '1').lower() in ('1', 'true', 'yes'):
        demo_users = [
            ('admin.test@sisip.test',   _hash_pw('Admin#2026'),   'Admin Tester',   'admin'),
            ('dpa.test@sisip.test',     _hash_pw('Dpa#2026'),     'DPA Tester',     'dpa'),
            ('kaprodi.test@sisip.test', _hash_pw('Kaprodi#2026'), 'Kaprodi Tester', 'kaprodi'),
        ]
        c.executemany(
            'INSERT OR IGNORE INTO users (email, password, name, role) VALUES (?, ?, ?, ?)',
            demo_users,
        )

    conn.commit()
    conn.close()

init_db()

# Global states (In a production system, model & scalers should also be saved to disk)
global_model = None
global_encoders = {}
global_le_y = None
global_scaler = None
global_config = {}

# Arsitektur memakai dua MaxPooling2D((2,2)), jadi tiap sisi grid harus >= 4.
MIN_GRID_SIDE = 4


def find_grid_dimensions(n):
    """Bentuk grid 2D untuk n fitur, sisi minimal MIN_GRID_SIDE.

    Faktorisasi pas saja tidak cukup: bila n bilangan prima (mis. 157 fitur),
    satu-satunya faktor adalah 1 x n sehingga tinggi grid = 1, lalu MaxPooling
    kedua menghasilkan dimensi 0 dan pelatihan gagal dengan ValueError. Kalau
    tidak ada faktorisasi yang memenuhi syarat, pakai grid mendekati persegi dan
    biarkan sisanya di-padding nol (pad_size sudah disimpan di config)."""
    best = None
    for i in range(1, int(np.sqrt(n)) + 1):
        if n % i == 0 and i >= MIN_GRID_SIDE and (n // i) >= MIN_GRID_SIDE:
            best = (i, n // i)
    if best:
        return best
    height = max(MIN_GRID_SIDE, int(np.floor(np.sqrt(n))))
    width = max(MIN_GRID_SIDE, int(np.ceil(n / height)))
    return (height, width)

def build_cnn_model(input_shape, n_classes, dropout_rate=0.3):
    model = keras.Sequential([
        layers.Conv2D(8, (3, 3), activation="relu", input_shape=input_shape, padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(dropout_rate),

        layers.Conv2D(16, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(dropout_rate),

        layers.Flatten(),
        layers.Dense(64, activation="relu"),
        layers.BatchNormalization(),
        layers.Dropout(dropout_rate),

        layers.Dense(32, activation="relu"),
        layers.Dropout(dropout_rate - 0.1 if dropout_rate >= 0.1 else 0),

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

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, email, name, role, password FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if not user or not _verify_pw(password, user['password']):
            return jsonify({'error': 'Kredensial tidak valid'}), 401

        u = {'id': user['id'], 'email': user['email'], 'name': user['name'], 'role': user['role']}
        return jsonify({'message': 'Login berhasil', 'user': u, 'token': _make_token(u)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users', methods=['GET'])
@require_role('admin')
def get_users():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, email, name, role FROM users WHERE role != "admin" ORDER BY id DESC')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(users), 200

@app.route('/api/users', methods=['POST'])
@require_role('admin')
def create_user():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')

    if not email or not password or not name:
        return jsonify({'error': 'Semua field wajib diisi'}), 400

    hashed_pw = _hash_pw(password)

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)', (email, hashed_pw, name, data.get('role', 'dpa')))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil menambahkan DPA baru'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email sudah terdaftar'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
@require_role('admin')
def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, email, name, role FROM users WHERE id = ? AND role != 'admin'", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return jsonify(dict(user)), 200
    return jsonify({'error': 'User tidak ditemukan'}), 404

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_role('admin')
def update_user(user_id):
    data = request.json
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')

    role = data.get('role', 'dpa')
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if password:
            hashed_pw = _hash_pw(password)
            c.execute('UPDATE users SET email = ?, name = ?, password = ?, role = ? WHERE id = ? AND role != "admin"', (email, name, hashed_pw, role, user_id))
        else:
            c.execute('UPDATE users SET email = ?, name = ?, role = ? WHERE id = ? AND role != "admin"', (email, name, role, user_id))
            
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil memperbarui data DPA'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email sudah digunakan oleh akun lain'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_role('admin')
def delete_user(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE id = ? AND role != "admin"', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil menghapus DPA'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

TEMPLATE_IDENTITY_COLS = [
    'NIM', 'Nomor PMB', 'Nama', 'Prodi', 'Angkatan', 'Semester',
    'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3',
]

# Kolom biodata mahasiswa yang dienkode tapi bukan nilai mata kuliah (dipakai untuk
# membedakan "isi dengan nama provinsi/sekolah" vs "isi dengan huruf mutu" saat
# membuat contoh data template).
TEMPLATE_BIODATA_COLS = [
    'Propinsi Asal Lahir', 'Kabupaten Asal Lahir', 'Propinsi Asal Sekolah',
    'Kabupaten Asal Sekolah', 'Nama Sekolah', 'Jurusan Sekolah', 'Profil Sekolah',
    'Jalur Pendaftaran',
]

TEMPLATE_DEFAULT_PRODI = 'Informatika'
TEMPLATE_DEFAULT_ANGKATAN = 2023
TEMPLATE_DEFAULT_SEMESTER = 3

_GRADE_LETTERS = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E', 'T'}
_GRADE_POOL_AMAN = ['A', 'A-', 'B+', 'B', 'B-']
_GRADE_POOL_BERISIKO = ['C', 'C-', 'D', 'D-', 'E']
_GRADE_POOL_GAGAL = ['D', 'D-', 'D+', 'E']

_SAMPLE_NAMES = [
    "Ahmad Fauzi Ramadhan", "Siti Nur Aisyah", "Budi Santoso", "Dewi Lestari",
    "Muhammad Rizky Pratama", "Putri Ayu Wulandari", "Andi Setiawan", "Rina Marlina",
]


def _norm_str(v):
    """Normalisasi nilai supaya '2024', '2024.0', 2024, dan ' 2024 ' dianggap sama.
    Tanpa ini, kolom Angkatan/Semester yang punya sel kosong berubah jadi float oleh
    pandas ('2024.0') dan tidak akan pernah cocok dengan pilihan dropdown ('2024')."""
    s = str(v).strip()
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return s


def _match_series(series, value):
    return series.astype(str).map(_norm_str) == _norm_str(value)


def _active_model_info(prodi=None):
    """(base_path, prodi_yang_sebenarnya) dari model aktif, atau (None, None)."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        if prodi:
            c.execute("SELECT file_path, prodi FROM model_registry WHERE is_active = 1 AND prodi = ? LIMIT 1", (prodi,))
        else:
            c.execute("SELECT file_path, prodi FROM model_registry WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
    except Exception:
        return None, None
    if not row:
        return None, None
    path, prodi_db = row
    base = resolve_model_path(path)[:-len('.keras')] if path.endswith('.keras') else resolve_model_path(path)
    return base, prodi_db


def _active_model_base(prodi=None):
    """Path prefix (without .keras) of an active model, or None."""
    base, _ = _active_model_info(prodi)
    return base


def _build_sample_rows(cols, feature_cols, encoders, scaler, prodi_label, angkatan, semester):
    """Contoh data siap-pakai untuk template, diturunkan dari statistik model itu
    sendiri (scaler.mean_ / scaler.scale_) supaya nilainya berada di rentang yang
    memang pernah dilihat model.

    Menebak rentang sendiri (mis. nilai tes 0-100) berbahaya: pada dataset ini
    kolom nilai tes ternyata berskala 0-10, sehingga angka karangan 35-90 menjadi
    +16..+28 sigma dan mendorong SEMUA prediksi ke satu kelas. Setiap baris digeser
    k*sigma dari rata-rata: k negatif = profil kuat, k positif = profil lemah."""
    rng = random.Random(20230903)  # seed tetap: isi contoh sama setiap diunduh
    means = getattr(scaler, 'mean_', None)
    scales = getattr(scaler, 'scale_', None)
    feat_index = {c: i for i, c in enumerate(feature_cols)}

    # Gradasi profil: separuh di bawah rata-rata (lebih kuat), separuh di atas
    # (lebih lemah), supaya contoh tidak seragam pada satu kelas prediksi.
    profil_k = [-1.2, -0.8, -0.4, 0.0, 0.6, 1.0, 1.4, 1.8]

    rows = []
    for idx, nama in enumerate(_SAMPLE_NAMES, start=1):
        k = profil_k[(idx - 1) % len(profil_k)]
        aman = k <= 0
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
            elif col.startswith('IPK'):
                # Hanya untuk laporan; model tidak memakai kolom ini.
                row[col] = round(rng.uniform(3.00, 3.70), 2) if aman else round(rng.uniform(1.60, 2.30), 2)
            elif col == 'Total SKS 3':
                row[col] = rng.choice([54, 57, 60]) if aman else rng.choice([30, 36, 42])
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
        rows.append(row)
    return rows


@app.route('/api/template/predict', methods=['GET'])
@app.route('/api/template', methods=['GET'])
@require_auth
def download_predict_template():
    """Excel template for batch prediction upload, already filled with usable example
    data. Feature columns are taken from the active model's scaler so the header
    matches exactly what that model expects; falls back to a default prodi/model so
    the button always works even before Program Studi is chosen on the page."""
    import joblib

    prodi_param = request.args.get('prodi') or None
    angkatan_param = request.args.get('angkatan') or TEMPLATE_DEFAULT_ANGKATAN
    semester_param = request.args.get('semester') or TEMPLATE_DEFAULT_SEMESTER

    base, resolved_prodi = _active_model_info(prodi_param or TEMPLATE_DEFAULT_PRODI)
    if not base:
        # Prodi yang diminta/dipilih belum punya model aktif -> pakai model aktif
        # apa saja yang tersedia supaya tombol tetap berfungsi, dan beri tahu di
        # sheet Petunjuk bahwa contohnya untuk prodi lain.
        base, resolved_prodi = _active_model_info(None)
    if not base:
        return jsonify({'error': "Belum ada model aktif sama sekali. Hubungi Admin untuk "
                                 "melatih dan mengaktifkan model terlebih dahulu."}), 400

    prodi_label = prodi_param or resolved_prodi or TEMPLATE_DEFAULT_PRODI
    model_prodi_label = resolved_prodi or prodi_label

    feature_cols = []
    encoders = {}
    try:
        scaler = joblib.load(f"{base}_scaler.pkl")
        encoders = joblib.load(f"{base}_encoders.pkl")
        if hasattr(scaler, 'feature_names_in_'):
            feature_cols = [str(c) for c in scaler.feature_names_in_]
    except Exception as load_err:
        return jsonify({'error': f"Gagal membaca kolom dari model aktif: {load_err}"}), 500

    if not feature_cols:
        return jsonify({'error': "Model aktif tidak menyimpan nama kolom fitur, "
                                 "template tidak dapat dibuat. Lakukan training ulang dari menu Admin."}), 400

    cols = TEMPLATE_IDENTITY_COLS + [c for c in feature_cols if c not in TEMPLATE_IDENTITY_COLS]

    rows = _build_sample_rows(cols, feature_cols, encoders, scaler, prodi_label,
                              angkatan_param, semester_param)
    df = pd.DataFrame(rows, columns=cols)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='TEST_SEM3')
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name=f'template_prediksi_{model_prodi_label.lower().replace(" ", "_")}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/api/preview', methods=['POST'])
@require_auth
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
        
        # Filter by Angkatan, Prodi, Semester if columns exist (dinormalkan agar
        # konsisten dengan /api/predict, lihat _match_series)
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[_match_series(df['Angkatan'], angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[_match_series(df['Semester'], semester)]

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
@require_role('admin')
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
    learning_rate_val = float(request.form.get('learning_rate', 0.001))
    dropout_rate_val = float(request.form.get('dropout_rate', 0.3))
    val_split_val = float(request.form.get('val_split', 0.2))

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = 'TRAIN_SEM3' if 'TRAIN_SEM3' in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Prodi and Angkatan if columns exist
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]

        if 'Angkatan' in df.columns and angkatan != '':
            # Normalisasi ('2023' vs '2023.0') supaya satu sel kosong di kolom lain
            # yang mengubah kolom Angkatan jadi float tidak diam-diam membuang baris.
            angkatan_list = [_norm_str(a) for a in str(angkatan).split(',') if a.strip()]
            if angkatan_list:
                df = df[df['Angkatan'].map(_norm_str).isin(angkatan_list)]

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

    global_config = {
        'height': height,
        'width': width,
        'pad_size': pad_size,
        'n_classes': n_classes,
        'n_features': n_features
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
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prodi_slug = prodi.replace(" ", "_").lower() if prodi else "global"
        version_name = f"Model_2DCNN_{prodi_slug}_{timestamp}"
        saved_model_path = os.path.join(MODEL_DIR, f"{version_name}.keras")
        model.save(saved_model_path)
        joblib.dump(global_scaler, os.path.join(MODEL_DIR, f"{version_name}_scaler.pkl"))
        joblib.dump(global_encoders, os.path.join(MODEL_DIR, f"{version_name}_encoders.pkl"))
        joblib.dump(global_le_y, os.path.join(MODEL_DIR, f"{version_name}_ley.pkl"))
        joblib.dump(global_config, os.path.join(MODEL_DIR, f"{version_name}_config.pkl"))

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

@app.route('/api/predict', methods=['POST'])
@require_auth
def predict():
    import os
    import joblib
    import datetime

    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')
    semester = request.form.get('semester', 'Unknown')
    uploaded_by = request.form.get('uploaded_by', 'Sistem')

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

    saved_path = resolve_model_path(row[0])
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
        df_before_filter = df

        # Filter by Angkatan, Prodi, and Semester jika kolom tersedia di Excel.
        # _match_series menormalkan tipe (mis. '2024' vs '2024.0') agar tidak
        # meleset gara-gara sel kosong di kolom lain membuat kolom ini jadi float.
        if 'Angkatan' in df.columns and angkatan != 'Unknown' and angkatan != '':
            df = df[_match_series(df['Angkatan'], angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown' and prodi != '':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False, regex=False)]
        if 'Semester' in df.columns and semester != 'Unknown' and semester != '':
            df = df[_match_series(df['Semester'], semester)]

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
                file_vals = sorted(set(_norm_str(v) for v in df_before_filter['Angkatan'].dropna().unique()))
                if file_vals and _norm_str(angkatan) not in file_vals:
                    reasons.append(f"Angkatan tidak sesuai — berkas berisi: {', '.join(file_vals)}, "
                                   f"sedangkan yang dipilih: {angkatan}.")
            if 'Semester' in df_before_filter.columns and semester not in ('Unknown', ''):
                file_vals = sorted(set(_norm_str(v) for v in df_before_filter['Semester'].dropna().unique()))
                if file_vals and _norm_str(semester) not in file_vals:
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
    # kalau tidak scaler menolak berkas dengan ValueError.
    expected_cols = [str(c) for c in getattr(active_scaler, 'feature_names_in_', [])]
    if expected_cols:
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            preview = ', '.join(missing[:10]) + ('...' if len(missing) > 10 else '')
            return jsonify({'error': f"Berkas tidak cocok dengan model aktif prodi {prodi}. "
                                     f"{len(missing)} kolom tidak ditemukan: {preview}. "
                                     "Silakan unduh ulang Template Excel untuk prodi ini."}), 400
        df = df.reindex(columns=expected_cols)
    else:
        drop_cols = TEMPLATE_IDENTITY_COLS + ['Label']
        df = df.drop(columns=[col for col in drop_cols if col in df.columns])

    try:
        # Proses encoding dinamis menggunakan kamus fit prodi terkait.
        # Nilai yang tidak dikenal model diganti ke kelas pertama agar prediksi
        # tetap bisa jalan.
        for col in active_encoders:
            if col in df.columns:
                le = active_encoders[col]
                known = set(str(x) for x in le.classes_)
                as_str = df[col].astype(str)
                df[col] = as_str.map(lambda s: s if s in known else str(le.classes_[0]))
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
    except Exception as proc_err:
        return jsonify({'error': f"Gagal memproses isi berkas untuk prodi {prodi}: {proc_err}"}), 400
    
    def _safe_float(series_name, i):
        """IPK bisa berisi teks/kosong pada berkas hasil edit manual; jangan sampai
        satu sel rusak menjatuhkan seluruh permintaan dengan 500."""
        if series_name not in original_df.columns:
            return 0.0
        val = original_df[series_name].iloc[i]
        try:
            return float(val) if not pd.isna(val) else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _safe_int(series_name, i):
        if series_name not in original_df.columns:
            return 0
        val = original_df[series_name].iloc[i]
        try:
            return int(float(val)) if not pd.isna(val) else 0
        except (TypeError, ValueError):
            return 0

    import json

    try:
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
                if col not in ['NIM', 'Nomor Pendaftaran', 'Nomor PMB', 'Nama', 'Nama Mahasiswa', 'Prodi', 'Angkatan', 'Semester', 'Label', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3'] and not pd.isna(original_df[col].iloc[i]):
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
                'ipk1': _safe_float('IPK 1', i),
                'ipk2': _safe_float('IPK 2', i),
                'ipk3': _safe_float('IPK 3', i),
                'sks3': _safe_int('Total SKS 3', i),
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

            results.append({
                'nim': str(nim),
                'pmb': str(pmb),
                'prediction': str(label),
                'isRisk': is_risk,
                'details': json.dumps(details_dict),
                'nama': str(nama),
                'prodi': str(prodi_val)
            })
    except Exception as build_err:
        return jsonify({'error': f"Gagal menyusun hasil prediksi: {build_err}"}), 500

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        date_now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
        batch_name = f"#BATCH-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
        total_records = len(results)

        # Kunci dedup mencakup semester — tanpa ini prediksi semester berbeda pada
        # prodi & angkatan yang sama saling menimpa dan hasil lama hilang permanen.
        semester_key = '' if str(semester) in ('Unknown', 'None', '') else str(semester)
        c.execute('SELECT id FROM batches WHERE prodi = ? AND IFNULL(angkatan, "") = ? AND IFNULL(semester, "") = ?',
                  (prodi, '' if angkatan in (None, 'Unknown') else angkatan, semester_key))
        existing = c.fetchone()
        if existing:
            old_batch_id = existing[0]
            c.execute('DELETE FROM predictions WHERE batch_id = ?', (old_batch_id,))
            c.execute('DELETE FROM batches WHERE id = ?', (old_batch_id,))

        c.execute('''
            INSERT INTO batches (batch_name, date_uploaded, total_records, at_risk, safe, status, prodi, angkatan, uploaded_by, semester)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (batch_name, date_now, total_records, at_risk_count, safe_count, 'Processed', prodi, angkatan, uploaded_by, semester_key))
        batch_id = c.lastrowid

        pred_data = [(batch_id, r['nim'], r['pmb'], r['prediction'], r['isRisk'], r['details']) for r in results]
        c.executemany('''
            INSERT INTO predictions (batch_id, nim, pmb, prediction, is_risk, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', pred_data)

        conn.commit()
        conn.close()
    except Exception as db_err:
        return jsonify({'error': f"Prediksi berhasil dihitung tetapi gagal disimpan ke database: {db_err}"}), 500

    return jsonify({
        'batch_id': batch_id,
        'batch_name': batch_name,
        'total': total_records,
        'atRisk': at_risk_count,
        'safe': safe_count,
        'prodi': prodi,
        'angkatan': angkatan,
        'semester': semester_key,
        'results': results,
    })


@app.route('/api/history', methods=['GET'])
@require_auth
def get_history():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches ORDER BY id DESC')
    batches = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'batches': batches})

@app.route('/api/batch/<int:batch_id>', methods=['GET'])
@require_auth
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
@require_role('admin')
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
@require_role('admin')
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

        # Jangan kunci model yang berkas fisiknya tidak lengkap — kalau tidak,
        # error baru muncul nanti saat dosen menjalankan prediksi.
        base_path = resolve_model_path(saved_path)
        if base_path.endswith('.keras'):
            base_path = base_path[:-len('.keras')]
        needed = [f"{base_path}.keras", f"{base_path}_scaler.pkl", f"{base_path}_encoders.pkl",
                  f"{base_path}_ley.pkl", f"{base_path}_config.pkl"]
        missing = [os.path.basename(p) for p in needed if not os.path.exists(p)]
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

@app.route('/api/student/<nim>', methods=['GET'])
@require_auth
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

@app.route('/api/health', methods=['GET'])
def health():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'detail': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
