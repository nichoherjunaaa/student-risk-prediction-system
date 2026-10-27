"""Master Pengguna (khusus admin)."""
import datetime
import sqlite3

from flask import Blueprint, jsonify, request

from ..auth import NIP_RE, norm_nip, require_role
from ..config import PRODI_OPTIONAL_ROLES, PRODI_REQUIRED_ROLES, ROLES
from ..db import connect
from ..passwords import hash_pw
from ..settings_store import current_format

bp = Blueprint('users', __name__)


def _validate_user_payload(data, is_new):
    """Kembalikan (nilai_bersih, pesan_error)."""
    nip = norm_nip(data.get('nip'))
    name = (data.get('name') or '').strip()
    role = data.get('role') or 'dpa'
    password = data.get('password') or ''
    if not nip or not name or (is_new and not password):
        return None, 'NIP, nama, dan password wajib diisi'
    if not NIP_RE.match(nip):
        return None, 'NIP hanya boleh berisi angka (5-20 digit)'
    if role not in ROLES:
        return None, 'Peran pengguna tidak dikenal'

    prodi = (data.get('prodi') or '').strip() or None
    if role in PRODI_REQUIRED_ROLES and not prodi:
        return None, 'Program studi wajib dipilih untuk peran DPA dan Kaprodi'
    if role not in PRODI_REQUIRED_ROLES + PRODI_OPTIONAL_ROLES:
        # Admin dan BAPSI bekerja lintas prodi.
        prodi = None
    if prodi and prodi not in current_format().prodi:
        return None, f'Program studi "{prodi}" tidak ada di daftar prodi (menu Format Data)'
    return {'nip': nip, 'name': name, 'role': role, 'prodi': prodi, 'password': password}, None


@bp.route('/api/users', methods=['GET'])
@require_role('admin')
def get_users():
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, nip, name, role, prodi FROM users WHERE deleted_at IS NULL ORDER BY id DESC')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(users), 200

@bp.route('/api/users', methods=['POST'])
@require_role('admin')
def create_user():
    v, err = _validate_user_payload(request.json or {}, is_new=True)
    if err:
        return jsonify({'error': err}), 400

    # Koneksi selalu ditutup, termasuk saat INSERT gagal: transaksi yang
    # menggantung mengunci database untuk permintaan berikutnya.
    conn = connect()
    try:
        conn.execute('INSERT INTO users (nip, password, name, role, prodi) VALUES (?, ?, ?, ?, ?)',
                     (v['nip'], hash_pw(v['password']), v['name'], v['role'], v['prodi']))
        conn.commit()
        return jsonify({'message': 'Berhasil menambahkan pengguna baru'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'NIP sudah terdaftar'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@bp.route('/api/users/<int:user_id>', methods=['GET'])
@require_role('admin')
def get_user(user_id):
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, nip, name, role, prodi FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return jsonify(dict(user)), 200
    return jsonify({'error': 'User tidak ditemukan'}), 404

@bp.route('/api/users/<int:user_id>', methods=['PUT'])
@require_role('admin')
def update_user(user_id):
    v, err = _validate_user_payload(request.json or {}, is_new=False)
    if err:
        return jsonify({'error': err}), 400
    # Admin menurunkan perannya sendiri bisa membuat tidak ada lagi yang
    # memegang akses admin.
    if user_id == request.user['uid'] and v['role'] != 'admin':
        return jsonify({'error': 'Anda tidak dapat mengubah peran akun Anda sendiri'}), 400

    conn = connect()
    try:
        c = conn.cursor()
        if v['password']:
            c.execute('UPDATE users SET nip = ?, name = ?, password = ?, role = ?, prodi = ? '
                      'WHERE id = ? AND deleted_at IS NULL',
                      (v['nip'], v['name'], hash_pw(v['password']), v['role'], v['prodi'], user_id))
        else:
            c.execute('UPDATE users SET nip = ?, name = ?, role = ?, prodi = ? WHERE id = ? AND deleted_at IS NULL',
                      (v['nip'], v['name'], v['role'], v['prodi'], user_id))
        updated = c.rowcount
        conn.commit()
        if not updated:
            return jsonify({'error': 'User tidak ditemukan'}), 404
        return jsonify({'message': 'Berhasil memperbarui data pengguna'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'NIP sudah digunakan oleh akun lain'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_role('admin')
def delete_user(user_id):
    if user_id == request.user['uid']:
        return jsonify({'error': 'Anda tidak dapat menghapus akun Anda sendiri'}), 400
    try:
        conn = connect()
        c = conn.cursor()
        # Soft delete: akun dan seluruh batch prediksinya hanya ditandai, tidak
        # dihapus fisik, supaya masih bisa dipulihkan atau diaudit.
        now = datetime.datetime.now().isoformat(timespec='seconds')
        c.execute('UPDATE users SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL',
                  (now, user_id))
        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'User tidak ditemukan'}), 404
        c.execute('UPDATE batches SET deleted_at = ? WHERE user_id = ? AND deleted_at IS NULL', (now, user_id))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Berhasil menghapus pengguna'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
