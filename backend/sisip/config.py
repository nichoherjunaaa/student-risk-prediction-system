"""Seluruh pengaturan yang dibaca dari environment, di satu tempat.

Nilai dibaca sekali saat modul diimpor, jadi skrip uji yang ingin memakai
database/folder sementara harus mengisi os.environ sebelum mengimpor `sisip`."""
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.environ.get('SISIP_DATA_DIR', _BACKEND_DIR)
DB_FILE = os.environ.get('SISIP_DB_FILE', os.path.join(DATA_DIR, 'sisip_database.db'))
MODEL_DIR = os.environ.get('SISIP_MODEL_DIR', os.path.join(DATA_DIR, 'saved_models'))

PREPROCESS_DIR = os.environ.get('SISIP_PREPROCESS_DIR', os.path.join(DATA_DIR, 'preprocessed'))
PREPROCESS_TTL = int(os.environ.get('SISIP_PREPROCESS_TTL', str(24 * 3600)))

FILES_DIR = os.environ.get('SISIP_FILES_DIR', os.path.join(DATA_DIR, 'files'))
FILE_MAX_BYTES = int(os.environ.get('SISIP_FILE_MAX_MB', '50')) * 1024 * 1024

# Dinormalisasi seperti auth.norm_nip (tanpa spasi/titik/strip, huruf kapital).
DEFAULT_ADMIN_NIP = ''.join(c for c in os.environ.get('SISIP_ADMIN_NIP', '235314122')
                            if not c.isspace() and c not in '.-').upper()
DEFAULT_ADMIN_PASSWORD = os.environ.get('SISIP_ADMIN_PASSWORD', 'change-me-strong-password')
SEED_DEMO_USERS = os.environ.get('SISIP_SEED_DEMO_USERS', '1').lower() in ('1', 'true', 'yes')

SECRET_KEY = os.environ.get('SISIP_SECRET_KEY', 'dev-insecure-secret-change-me')
TOKEN_MAX_AGE = int(os.environ.get('SISIP_TOKEN_MAX_AGE', str(12 * 3600)))

CORS_ORIGINS = os.environ.get('SISIP_CORS_ORIGINS', '*').strip()

# Kunci bersama dengan SIA untuk link masuk /sso/sia (HMAC-SHA256). Kosong = jalur
# SSO mati. Terpisah dari SECRET_KEY; lihat routes/sso.py.
SIA_SSO_SECRET = os.environ.get('SISIP_SIA_SSO_SECRET', '').strip()
# Link SSO berlaku sekian detik sejak dibuat SIA (juga toleransi selisih jam).
SIA_SSO_MAX_SKEW = 120

ROLES = ('admin', 'dpa', 'kaprodi', 'dekan', 'bapsi')
# BAPSI hanya mengelola berkas mahasiswa; menu dan API prediksi bukan untuknya.
PREDIKSI_ROLES = ('admin', 'dpa', 'kaprodi', 'dekan')
FILE_MANAGER_ROLES = ('bapsi', 'admin')
# Peran yang terikat ke satu prodi: hanya memprediksi dan melihat data prodinya.
# Dekan boleh terikat (dekan prodi) atau tidak (tingkat fakultas, semua prodi).
PRODI_REQUIRED_ROLES = ('dpa', 'kaprodi')
PRODI_OPTIONAL_ROLES = ('dekan',)


def ensure_dirs():
    for path in (MODEL_DIR, PREPROCESS_DIR, FILES_DIR):
        os.makedirs(path, exist_ok=True)
