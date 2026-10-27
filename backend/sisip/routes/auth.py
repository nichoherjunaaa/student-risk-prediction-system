"""Login."""
import sqlite3

from flask import Blueprint, jsonify, request

from ..auth import make_token, norm_nip
from ..db import connect
from ..passwords import verify_pw

bp = Blueprint('auth', __name__)


@bp.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    nip = norm_nip(data.get('nip'))
    password = data.get('password')
    if not nip or not password:
        return jsonify({'error': 'NIP dan password wajib diisi'}), 400

    try:
        conn = connect()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, nip, name, role, prodi, password FROM users WHERE nip = ? AND deleted_at IS NULL", (nip,))
        user = c.fetchone()
        conn.close()

        if not user or not verify_pw(password, user['password']):
            return jsonify({'error': 'NIP atau password salah'}), 401

        u = {'id': user['id'], 'nip': user['nip'], 'name': user['name'], 'role': user['role'],
             'prodi': user['prodi']}
        return jsonify({'message': 'Login berhasil', 'user': u, 'token': make_token(u)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
