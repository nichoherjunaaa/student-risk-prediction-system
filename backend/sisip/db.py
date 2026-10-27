"""Koneksi SQLite, pembuatan skema, dan migrasi data lama."""
import sqlite3

from .config import DB_FILE, DEFAULT_ADMIN_NIP, DEFAULT_ADMIN_PASSWORD, SEED_DEMO_USERS
from .passwords import hash_pw


def connect():
    return sqlite3.connect(DB_FILE)


def _migrate_columns(c, wanted):
    """Tambahkan kolom yang belum ada pada tabel yang sudah terlanjur dibuat.
    `wanted` = {nama_tabel: [(nama_kolom, tipe_sql), ...]}."""
    for table, cols in wanted.items():
        existing = {row[1] for row in c.execute("PRAGMA table_info(%s)" % table).fetchall()}
        for name, coltype in cols:
            if name not in existing:
                c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, coltype))


DEMO_USERS = [
    ('900000000000000001', 'Admin#2026',   'Admin Tester',   'admin'),
    ('900000000000000002', 'Dpa#2026',     'DPA Tester',     'dpa'),
    ('900000000000000003', 'Kaprodi#2026', 'Kaprodi Tester', 'kaprodi'),
    ('900000000000000004', 'Bapsi#2026',   'BAPSI Tester',   'bapsi'),
]

# Email akun bawaan versi lama -> NIP penggantinya saat migrasi.
_LEGACY_EMAIL_NIP = {
    'admin@gmail.com': DEFAULT_ADMIN_NIP,
    'admin.test@sisip.test': DEMO_USERS[0][0],
    'dpa.test@sisip.test': DEMO_USERS[1][0],
    'kaprodi.test@sisip.test': DEMO_USERS[2][0],
}


def _migrate_users_to_nip(c):
    """Database lama memakai email sebagai identitas login (kolom UNIQUE NOT NULL).
    SQLite tidak bisa membuang kolom dengan constraint, jadi tabel dibangun ulang
    tanpa email dengan id yang sama (batches.user_id tetap menunjuk akun yang benar).

    Akun bawaan diberi NIP dari _LEGACY_EMAIL_NIP; admin utama sekaligus memakai
    password SISIP_ADMIN_PASSWORD. Akun lain mendapat NIP kosong dan belum bisa
    login sampai admin mengisi NIP-nya di Master Pengguna."""
    cols = {row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()}
    if 'email' not in cols:
        return
    rows = c.execute('SELECT id, email, password, name, role, deleted_at FROM users').fetchall()
    c.execute('ALTER TABLE users RENAME TO users_lama')
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nip TEXT,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            prodi TEXT,
            deleted_at TEXT
        )
    ''')
    for uid, email, password, name, role, deleted_at in rows:
        nip = None if deleted_at else _LEGACY_EMAIL_NIP.get((email or '').strip().lower())
        if nip == DEFAULT_ADMIN_NIP:
            password = hash_pw(DEFAULT_ADMIN_PASSWORD)
        c.execute('INSERT INTO users (id, nip, password, name, role, deleted_at) VALUES (?, ?, ?, ?, ?, ?)',
                  (uid, nip, password, name, role, deleted_at))
    c.execute('DROP TABLE users_lama')


def init_db():
    conn = connect()
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
            nip TEXT,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            prodi TEXT,
            deleted_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            deleted_at TEXT,
            FOREIGN KEY(parent_id) REFERENCES folders(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER,
            kategori TEXT NOT NULL DEFAULT 'lainnya',
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            uploaded_by INTEGER,
            uploaded_at TEXT NOT NULL,
            deleted_at TEXT,
            FOREIGN KEY(folder_id) REFERENCES folders(id)
        )
    ''')

    # Pengaturan yang bisa diubah admin dari aplikasi (mis. format data), satu
    # baris per kunci dengan nilai JSON.
    c.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT,
            updated_by INTEGER
        )
    ''')

    _migrate_columns(c, {
        'batches': [('uploaded_by', 'TEXT'), ('semester', 'TEXT'),
                    ('user_id', 'INTEGER'), ('deleted_at', 'TEXT')],
        'predictions': [('details', 'TEXT')],
        # Batas semester data latih (TRAIN_SEM<n>); prediksi memotong data di
        # semester yang sama. source: 'training' (tercatat) atau 'perkiraan'.
        'model_registry': [('max_semester', 'INTEGER'), ('max_semester_source', 'TEXT'),
                           # Recall kelas SISIP pada data validasi: tertangkap / total.
                           ('recall_sisip', 'REAL'), ('val_sisip_caught', 'INTEGER'),
                           ('val_sisip_total', 'INTEGER'), ('n_train_samples', 'INTEGER')],
        'users': [('deleted_at', 'TEXT'), ('prodi', 'TEXT')],
    })
    _migrate_users_to_nip(c)
    # NIP unik hanya di antara akun aktif, supaya NIP akun yang sudah dihapus
    # (soft delete) bisa dipakai lagi oleh akun baru.
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_users_nip_aktif
                 ON users(nip) WHERE deleted_at IS NULL AND nip IS NOT NULL''')

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO users (nip, password, name, role) VALUES (?, ?, ?, ?)',
                  (DEFAULT_ADMIN_NIP, hash_pw(DEFAULT_ADMIN_PASSWORD), 'Staf Admin', 'admin'))

    if SEED_DEMO_USERS:
        # Hanya dibuat kalau NIP-nya belum pernah ada sama sekali: akun demo yang
        # sudah dihapus admin tidak muncul lagi setiap server dinyalakan ulang.
        for nip, pw, name, role in DEMO_USERS:
            c.execute('''INSERT INTO users (nip, password, name, role)
                         SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM users WHERE nip = ?)''',
                      (nip, hash_pw(pw), name, role, nip))

    # Batch dari sebelum ada kolom user_id: pasangkan ke akun yang namanya cocok
    # dengan uploaded_by, sisanya (mis. "Sistem") ke admin utama.
    c.execute('''UPDATE batches SET user_id = (
                     SELECT u.id FROM users u WHERE u.name = batches.uploaded_by ORDER BY u.id LIMIT 1)
                 WHERE user_id IS NULL''')
    c.execute('''UPDATE batches SET user_id = (
                     SELECT id FROM users WHERE role = 'admin' ORDER BY nip != ?, id LIMIT 1)
                 WHERE user_id IS NULL''', (DEFAULT_ADMIN_NIP,))

    conn.commit()
    conn.close()
