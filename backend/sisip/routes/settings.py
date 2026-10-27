"""Format Data: nama kolom berkas mentah, daftar prodi, dan tabel nilai mutu."""
import json

from flask import Blueprint, jsonify, request

from ..auth import require_auth, require_role
from ..data_format import (DataFormat, default_format, load_format_row, reset_format,
                           save_format, validate_format)
from ..db import connect
from ..preprocessing import PreprocessError, inspect_workbook
from ..utils import now_iso

bp = Blueprint('settings', __name__)


def _format_response(conn):
    fmt, meta = load_format_row(conn)
    return {'format': fmt, 'default': default_format(), **meta}


@bp.route('/api/prodi', methods=['GET'])
@require_auth
def list_prodi():
    """Daftar prodi untuk dropdown di semua halaman. User yang terikat prodi
    hanya mendapat prodinya sendiri, dan `locked` memberi tahu frontend untuk
    tidak menampilkan pilihan prodi."""
    locked = request.user.get('prodi')
    if locked:
        return jsonify({'prodi': [locked], 'locked': locked}), 200
    conn = connect()
    try:
        fmt, _ = load_format_row(conn)
    finally:
        conn.close()
    return jsonify({'prodi': fmt['prodi'], 'locked': None}), 200


@bp.route('/api/settings/data-format', methods=['GET'])
@require_role('admin')
def get_data_format():
    conn = connect()
    try:
        return jsonify(_format_response(conn)), 200
    finally:
        conn.close()


@bp.route('/api/settings/data-format', methods=['PUT'])
@require_role('admin')
def update_data_format():
    clean, errors = validate_format(request.json)
    if errors:
        return jsonify({'error': errors[0], 'errors': errors}), 400
    conn = connect()
    try:
        dipakai = conn.execute(
            "SELECT DISTINCT prodi FROM users WHERE deleted_at IS NULL AND prodi IS NOT NULL").fetchall()
        hilang = sorted(r[0] for r in dipakai if r[0] not in clean['prodi'])
        if hilang:
            return jsonify({'error': 'Program studi masih dipakai akun pengguna dan tidak bisa '
                                     f'dihapus: {", ".join(hilang)}. Ubah prodi akun tersebut '
                                     'di Master Pengguna terlebih dahulu.'}), 400
        save_format(conn, clean, request.user['uid'], now_iso())
        conn.commit()
        return jsonify(_format_response(conn)), 200
    finally:
        conn.close()


@bp.route('/api/settings/data-format', methods=['DELETE'])
@require_role('admin')
def reset_data_format():
    conn = connect()
    try:
        reset_format(conn)
        conn.commit()
        return jsonify(_format_response(conn)), 200
    finally:
        conn.close()


@bp.route('/api/settings/data-format/check', methods=['POST'])
@require_role('admin')
def check_file_against_format():
    """Cek sebuah berkas mentah terhadap format. Bila `format` (JSON) dikirim,
    yang dipakai adalah draf itu, jadi admin bisa mencoba sebelum menyimpan."""
    berkas = request.files.get('file')
    if not berkas:
        return jsonify({'error': 'Pilih berkas Excel yang ingin dicek.'}), 400
    if request.form.get('format'):
        try:
            draft = json.loads(request.form['format'])
        except ValueError:
            return jsonify({'error': 'Format draf tidak valid.'}), 400
        raw, errors = validate_format(draft)
        if errors:
            return jsonify({'error': errors[0], 'errors': errors}), 400
    else:
        conn = connect()
        try:
            raw, _ = load_format_row(conn)
        finally:
            conn.close()
    try:
        return jsonify({'sheets': inspect_workbook(berkas, DataFormat(raw))}), 200
    except PreprocessError as err:
        return jsonify({'error': str(err)}), 400
