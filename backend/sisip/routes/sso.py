"""Masuk dari SIA tanpa login (SSO). Kontrak dengan SIA: docs/INTEGRASI-SSO-SIA.md.

SIA membuat link /sso/sia?id=<NIP>&ts=<ts>&nonce=<nonce>&sig=<sig> dengan
sig = HMAC_SHA256(SIA_SSO_SECRET, "v1|id|ts|nonce"). Frontend meneruskan
parameternya ke POST /api/sso/sia; endpoint ini memeriksa sig, umur link, dan
nonce sekali pakai, lalu mengembalikan token seperti /api/login."""
import hashlib
import hmac
import re
import sqlite3
import time
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..auth import make_token, norm_nip
from ..config import SIA_SSO_MAX_SKEW, SIA_SSO_SECRET
from ..db import connect

bp = Blueprint('sso', __name__)

_HEX32 = re.compile(r'^[0-9a-f]{32}$')
_HEX64 = re.compile(r'^[0-9a-f]{64}$')
_TS = re.compile(r'^\d{1,12}$')

# Satu pesan untuk semua penolakan, supaya dari luar tidak bisa dibedakan
# "sig salah" dan "NIP tidak terdaftar". Alasan rincinya hanya di sso_audit.
_DITOLAK = 'Akses dari SIA tidak valid atau sudah kedaluwarsa.'


def sign(secret, sia_id, ts, nonce):
    msg = f'v1|{sia_id}|{ts}|{nonce}'
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


def _audit(c, sia_id, result, user_id=None):
    ip = request.headers.get('X-Real-IP') or request.remote_addr
    c.execute('INSERT INTO sso_audit (at, sia_id, user_id, result, ip) VALUES (?, ?, ?, ?, ?)',
              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sia_id, user_id, result, ip))


@bp.route('/api/sso/sia', methods=['POST'])
def sso_sia():
    if not SIA_SSO_SECRET:
        return jsonify({'error': 'Not found'}), 404

    data = request.get_json(silent=True) or {}
    sia_id = str(data.get('id') or '')
    ts = str(data.get('ts') or '')
    nonce = str(data.get('nonce') or '')
    sig = str(data.get('sig') or '')

    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        def tolak(result, status=401, user_id=None):
            _audit(c, sia_id[:254], result, user_id)
            conn.commit()
            return jsonify({'error': _DITOLAK}), status

        if not (sia_id and len(sia_id) <= 254 and _TS.match(ts)
                and _HEX32.match(nonce) and _HEX64.match(sig)):
            return tolak('bad_request', 400)

        # sig dihitung dari id persis seperti yang dikirim SIA, sebelum
        # dinormalisasi; normalisasi hanya untuk mencari akun.
        if not hmac.compare_digest(sign(SIA_SSO_SECRET, sia_id, ts, nonce), sig):
            return tolak('bad_sig')

        now = int(time.time())
        if abs(now - int(ts)) > SIA_SSO_MAX_SKEW:
            return tolak('expired')

        c.execute('DELETE FROM sso_nonce WHERE expires_at < ?', (now,))
        try:
            c.execute('INSERT INTO sso_nonce (nonce, expires_at) VALUES (?, ?)',
                      (nonce, int(ts) + SIA_SSO_MAX_SKEW))
        except sqlite3.IntegrityError:
            return tolak('replay')

        c.execute("SELECT id, nip, name, role, prodi FROM users WHERE nip = ? AND deleted_at IS NULL",
                  (norm_nip(sia_id),))
        user = c.fetchone()
        if not user:
            return tolak('unknown_user')
        # Admin tetap wajib lewat halaman login Sisip.
        if user['role'] == 'admin':
            return tolak('role_blocked', 403, user['id'])

        u = {'id': user['id'], 'nip': user['nip'], 'name': user['name'], 'role': user['role'],
             'prodi': user['prodi']}
        _audit(c, sia_id, 'ok', user['id'])
        conn.commit()
        return jsonify({'message': 'Login berhasil', 'user': u, 'token': make_token(u)}), 200
    finally:
        conn.close()
