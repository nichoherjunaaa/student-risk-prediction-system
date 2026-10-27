"""Autentikasi: hash password, token login, dan dekorator hak akses."""
import functools
import re

from flask import jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import SECRET_KEY, TOKEN_MAX_AGE
from .db import connect

NIP_RE = re.compile(r'^[A-Z0-9]{5,20}$')
token_serializer = URLSafeTimedSerializer(SECRET_KEY, salt='sisip-auth')


def norm_nip(value):
    """NIP sering ditulis berspasi, bertitik, atau berstrip; pemisah itu dibuang.
    Huruf disimpan kapital supaya login tidak peka huruf besar/kecil. Simbol lain
    tidak dibuang diam-diam, supaya validasi menolaknya."""
    return re.sub(r'[\s.\-]', '', str(value or '')).upper()


def make_token(user):
    return token_serializer.dumps({'uid': user['id'], 'nip': user['nip'], 'role': user['role']})


def current_user():
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        token = auth[7:].strip()
    else:
        token = request.args.get('token', '')
    if not token:
        return None
    try:
        payload = token_serializer.loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    # Token stateless tetap sah sampai kedaluwarsa, jadi status akun dicek ulang
    # ke database: akun yang sudah dihapus (soft delete) langsung kehilangan akses,
    # dan perubahan role oleh admin berlaku tanpa menunggu login ulang.
    conn = connect()
    row = conn.execute('SELECT nip, name, role, prodi FROM users WHERE id = ? AND deleted_at IS NULL',
                       (payload.get('uid'),)).fetchone()
    conn.close()
    if not row:
        return None
    payload['nip'], payload['name'], payload['role'], payload['prodi'] = row
    return payload


def require_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({'error': 'Sesi tidak valid atau telah berakhir. Silakan login ulang.'}), 401
        request.user = user
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({'error': 'Sesi tidak valid atau telah berakhir. Silakan login ulang.'}), 401
            if user.get('role') not in roles:
                return jsonify({'error': 'Anda tidak memiliki hak akses untuk tindakan ini.'}), 403
            request.user = user
            return fn(*args, **kwargs)
        return wrapper
    return deco


def scoped_prodi(requested=None):
    """Prodi yang berlaku untuk permintaan ini. User yang terikat prodi selalu
    memakai prodinya sendiri, apa pun yang dikirim form/URL, supaya batasan
    tidak bisa diakali dari sisi browser."""
    return request.user.get('prodi') or requested
