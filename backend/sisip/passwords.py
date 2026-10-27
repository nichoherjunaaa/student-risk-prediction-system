"""Hash password. Modul terpisah supaya db (seed akun) dan auth sama-sama bisa
memakainya tanpa saling mengimpor."""
import hashlib
import hmac

from werkzeug.security import check_password_hash, generate_password_hash


def hash_pw(pw):
    return generate_password_hash(pw)


def verify_pw(pw, stored):
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
