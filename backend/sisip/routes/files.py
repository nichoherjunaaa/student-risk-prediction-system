"""Berkas Mahasiswa: file manager BAPSI."""
import os
import re
import sqlite3
import uuid

from flask import Blueprint, jsonify, request, send_file

from ..auth import require_auth, require_role
from ..config import FILE_MAX_BYTES, FILE_MANAGER_ROLES, FILES_DIR
from ..db import connect
from ..utils import now_iso

bp = Blueprint('files', __name__)


# ---------------------------------------------------------------------------
# Berkas Mahasiswa (file manager BAPSI)
#
# Berkas fisik disimpan di FILES_DIR dengan nama acak (<uuid><ext>); nama asli,
# folder, dan kategori hanya ada di database. Dengan begitu nama berkas dari
# pengguna tidak pernah menjadi path di disk, dan dua berkas bernama sama tidak
# saling menimpa. BAPSI dan admin boleh mengelola, semua peran boleh mengunduh.
# ---------------------------------------------------------------------------

FILE_KATEGORI = ('pmb', 'akademik', 'lainnya')
# Berkas PMB/akademik dibaca preprocessing, yang menerima Excel (.xlsx) dan CSV.
FILE_EXT = {
    'pmb': ('.xlsx', '.csv'),
    'akademik': ('.xlsx', '.csv'),
    'lainnya': ('.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip'),
}
_NAME_FORBIDDEN = re.compile(r'[\\/\x00-\x1f]')

def _clean_name(name, max_len=150):
    name = (name or '').strip()
    if not name or len(name) > max_len or _NAME_FORBIDDEN.search(name) or name in ('.', '..'):
        return None
    return name


def _upload_name(f):
    return _clean_name(os.path.basename(f.filename.replace('\\', '/')))


def stored_file_path(file_id):
    conn = connect()
    row = conn.execute('SELECT stored_name FROM files WHERE id = ? AND deleted_at IS NULL',
                       (file_id,)).fetchone()
    conn.close()
    if not row:
        return None
    path = os.path.join(FILES_DIR, row[0])
    return path if os.path.isfile(path) else None


def _file_row_info(c, row):
    """Info berkas aktif, atau None bila berkasnya / salah satu folder induknya
    sudah dihapus atau berkas fisiknya hilang."""
    if not row:
        return None
    file_id, name, stored, folder_id, uploaded_at, uploaded_by = row
    if any(b['deleted'] for b in _breadcrumb(c, folder_id)):
        return None
    path = os.path.join(FILES_DIR, stored)
    if not os.path.isfile(path):
        return None
    return {'id': file_id, 'name': name, 'path': path, 'uploaded_at': uploaded_at,
            'uploaded_by': uploaded_by}


_INFO_SELECT = ("SELECT f.id, f.original_name, f.stored_name, f.folder_id, f.uploaded_at, u.name "
                "FROM files f LEFT JOIN users u ON u.id = f.uploaded_by WHERE f.deleted_at IS NULL")


def file_info(file_id, kategori):
    """Berkas aktif pilihan pengguna, hanya bila kategorinya sesuai."""
    conn = connect()
    try:
        return _file_row_info(conn, conn.execute(_INFO_SELECT + ' AND f.id = ? AND f.kategori = ?',
                                                 (file_id, kategori)).fetchone())
    finally:
        conn.close()


def latest_file(kategori):
    """Berkas terbaru satu kategori yang masih aktif (dipakai prediksi otomatis)."""
    conn = connect()
    try:
        for row in conn.execute(_INFO_SELECT + ' AND f.kategori = ? ORDER BY f.uploaded_at DESC, f.id DESC',
                                (kategori,)).fetchall():
            info = _file_row_info(conn, row)
            if info:
                return info
        return None
    finally:
        conn.close()


def _active_folder(c, folder_id):
    """Kembalikan (id_folder, valid). None berarti folder akar."""
    if folder_id in (None, '', 'null', 'root'):
        return None, True
    try:
        folder_id = int(folder_id)
    except (TypeError, ValueError):
        return None, False
    row = c.execute('SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL', (folder_id,)).fetchone()
    return (folder_id, True) if row else (None, False)


def _breadcrumb(c, folder_id):
    trail = []
    while folder_id is not None:
        row = c.execute('SELECT id, name, parent_id, deleted_at FROM folders WHERE id = ?',
                        (folder_id,)).fetchone()
        if not row:
            break
        trail.append({'id': row[0], 'name': row[1], 'deleted': row[3] is not None})
        folder_id = row[2]
    return list(reversed(trail))


def _folder_name_taken(c, parent_id, name, exclude_id=None):
    row = c.execute("SELECT 1 FROM folders WHERE deleted_at IS NULL AND parent_id IS ? "
                    "AND lower(name) = lower(?) AND id IS NOT ?",
                    (parent_id, name, exclude_id)).fetchone()
    return row is not None


_FILE_SELECT = ("SELECT f.id, f.original_name AS name, f.kategori, f.size, f.folder_id, "
                "f.uploaded_at, u.name AS uploaded_by "
                "FROM files f LEFT JOIN users u ON u.id = f.uploaded_by "
                "WHERE f.deleted_at IS NULL")


@bp.route('/api/files', methods=['GET'])
@require_auth
def list_files():
    """Isi satu folder. Dengan ?q= atau ?kategori=, hasilnya pencarian datar di
    seluruh folder (dipakai kotak cari dan pemilih berkas di Preprocessing)."""
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    can_manage = request.user['role'] in FILE_MANAGER_ROLES
    q = (request.args.get('q') or '').strip()
    kategori = request.args.get('kategori')

    if q or kategori:
        sql, params = _FILE_SELECT, []
        if q:
            sql += ' AND f.original_name LIKE ?'
            params.append(f'%{q}%')
        if kategori:
            sql += ' AND f.kategori = ?'
            params.append(kategori)
        files = []
        for row in c.execute(sql + ' ORDER BY f.uploaded_at DESC, f.id DESC', params).fetchall():
            f = dict(row)
            trail = _breadcrumb(c, f['folder_id'])
            # Berkas di dalam folder yang sudah dihapus ikut tersembunyi.
            if any(b['deleted'] for b in trail):
                continue
            f['path'] = ' / '.join(b['name'] for b in trail)
            files.append(f)
        conn.close()
        return jsonify({'folder': None, 'breadcrumb': [], 'folders': [], 'files': files,
                        'can_manage': can_manage, 'search': True}), 200

    folder_id, ok = _active_folder(c, request.args.get('folder_id'))
    if not ok:
        conn.close()
        return jsonify({'error': 'Folder tidak ditemukan'}), 404
    folders = [dict(r) for r in c.execute(
        "SELECT d.id, d.name, d.created_at, "
        "  (SELECT COUNT(*) FROM folders x WHERE x.parent_id = d.id AND x.deleted_at IS NULL) "
        "+ (SELECT COUNT(*) FROM files y WHERE y.folder_id = d.id AND y.deleted_at IS NULL) AS item_count "
        "FROM folders d WHERE d.deleted_at IS NULL AND d.parent_id IS ? ORDER BY lower(d.name)",
        (folder_id,))]
    files = [dict(r) for r in c.execute(
        _FILE_SELECT + ' AND f.folder_id IS ? ORDER BY f.uploaded_at DESC, f.id DESC', (folder_id,))]
    trail = [{'id': b['id'], 'name': b['name']} for b in _breadcrumb(c, folder_id)]
    conn.close()
    return jsonify({'folder': trail[-1] if trail else None, 'breadcrumb': trail,
                    'folders': folders, 'files': files, 'can_manage': can_manage}), 200


@bp.route('/api/folders', methods=['POST'])
@require_role(*FILE_MANAGER_ROLES)
def create_folder():
    data = request.json or {}
    name = _clean_name(data.get('name'), 100)
    if not name:
        return jsonify({'error': 'Nama folder wajib diisi dan tidak boleh memuat / atau \\'}), 400
    conn = connect()
    c = conn.cursor()
    parent_id, ok = _active_folder(c, data.get('parent_id'))
    if not ok:
        conn.close()
        return jsonify({'error': 'Folder induk tidak ditemukan'}), 404
    if _folder_name_taken(c, parent_id, name):
        conn.close()
        return jsonify({'error': f'Folder "{name}" sudah ada di lokasi ini'}), 400
    c.execute('INSERT INTO folders (name, parent_id, created_by, created_at) VALUES (?, ?, ?, ?)',
              (name, parent_id, request.user['uid'], now_iso()))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return jsonify({'id': new_id, 'name': name}), 201


@bp.route('/api/folders/<int:folder_id>', methods=['PATCH'])
@require_role(*FILE_MANAGER_ROLES)
def rename_folder(folder_id):
    name = _clean_name((request.json or {}).get('name'), 100)
    if not name:
        return jsonify({'error': 'Nama folder wajib diisi dan tidak boleh memuat / atau \\'}), 400
    conn = connect()
    c = conn.cursor()
    row = c.execute('SELECT parent_id FROM folders WHERE id = ? AND deleted_at IS NULL', (folder_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Folder tidak ditemukan'}), 404
    if _folder_name_taken(c, row[0], name, exclude_id=folder_id):
        conn.close()
        return jsonify({'error': f'Folder "{name}" sudah ada di lokasi ini'}), 400
    c.execute('UPDATE folders SET name = ? WHERE id = ?', (name, folder_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Nama folder diperbarui'}), 200


@bp.route('/api/folders/<int:folder_id>', methods=['DELETE'])
@require_role(*FILE_MANAGER_ROLES)
def delete_folder(folder_id):
    """Soft delete folder beserta seluruh subfolder dan berkas di dalamnya."""
    conn = connect()
    c = conn.cursor()
    ids = [r[0] for r in c.execute(
        "WITH RECURSIVE pohon(id) AS ("
        "  SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL"
        "  UNION ALL"
        "  SELECT f.id FROM folders f JOIN pohon p ON f.parent_id = p.id WHERE f.deleted_at IS NULL"
        ") SELECT id FROM pohon", (folder_id,))]
    if not ids:
        conn.close()
        return jsonify({'error': 'Folder tidak ditemukan'}), 404
    now = now_iso()
    marks = ','.join('?' * len(ids))
    c.execute(f'UPDATE folders SET deleted_at = ? WHERE id IN ({marks})', [now, *ids])
    c.execute(f'UPDATE files SET deleted_at = ? WHERE deleted_at IS NULL AND folder_id IN ({marks})', [now, *ids])
    conn.commit()
    conn.close()
    return jsonify({'message': 'Folder dihapus'}), 200


@bp.route('/api/files', methods=['POST'])
@require_role(*FILE_MANAGER_ROLES)
def upload_files():
    uploads = [f for f in request.files.getlist('files') if f and f.filename]
    if not uploads:
        return jsonify({'error': 'Pilih minimal satu berkas untuk diunggah'}), 400
    kategori = request.form.get('kategori') or 'lainnya'
    if kategori not in FILE_KATEGORI:
        return jsonify({'error': 'Kategori berkas tidak dikenal'}), 400

    conn = connect()
    c = conn.cursor()
    folder_id, ok = _active_folder(c, request.form.get('folder_id'))
    if not ok:
        conn.close()
        return jsonify({'error': 'Folder tujuan tidak ditemukan'}), 404

    # Validasi semua berkas dulu, supaya unggahan banyak berkas tidak setengah jadi.
    allowed = FILE_EXT[kategori]
    for f in uploads:
        name = _upload_name(f)
        if not name or os.path.splitext(name)[1].lower() not in allowed:
            conn.close()
            return jsonify({'error': f'"{f.filename}" ditolak: kategori ini hanya menerima '
                                     f'{", ".join(allowed)}'}), 400
        f.stream.seek(0, os.SEEK_END)
        too_big = f.stream.tell() > FILE_MAX_BYTES
        f.stream.seek(0)
        if too_big:
            conn.close()
            return jsonify({'error': f'"{name}" melebihi batas {FILE_MAX_BYTES // (1024 * 1024)} MB'}), 400

    os.makedirs(FILES_DIR, exist_ok=True)
    saved, written = [], []
    try:
        for f in uploads:
            name = _upload_name(f)
            stored = uuid.uuid4().hex + os.path.splitext(name)[1].lower()
            path = os.path.join(FILES_DIR, stored)
            f.save(path)
            written.append(path)
            c.execute("INSERT INTO files (folder_id, kategori, original_name, stored_name, size, "
                      "uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (folder_id, kategori, name, stored, os.path.getsize(path), request.user['uid'], now_iso()))
            saved.append({'id': c.lastrowid, 'name': name})
        conn.commit()
    except Exception as err:
        conn.rollback()
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        return jsonify({'error': f'Gagal menyimpan berkas: {err}'}), 500
    finally:
        conn.close()
    return jsonify({'files': saved}), 201


@bp.route('/api/files/<int:file_id>', methods=['PATCH'])
@require_role(*FILE_MANAGER_ROLES)
def update_file(file_id):
    """Ganti nama, kategori, dan/atau pindah folder."""
    data = request.json or {}
    conn = connect()
    c = conn.cursor()
    row = c.execute('SELECT original_name FROM files WHERE id = ? AND deleted_at IS NULL',
                    (file_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Berkas tidak ditemukan'}), 404
    name = row[0]
    sets, params = [], []

    if 'name' in data:
        new_name = _clean_name(data.get('name'))
        if not new_name:
            conn.close()
            return jsonify({'error': 'Nama berkas tidak valid'}), 400
        # Ekstensi dipertahankan: ekstensi menentukan cara berkas dibuka dan
        # apakah berkas masih sah untuk kategorinya.
        ext = os.path.splitext(name)[1]
        if os.path.splitext(new_name)[1].lower() != ext.lower():
            new_name += ext
        sets.append('original_name = ?')
        params.append(new_name)
        name = new_name
    if 'kategori' in data:
        if data['kategori'] not in FILE_KATEGORI:
            conn.close()
            return jsonify({'error': 'Kategori berkas tidak dikenal'}), 400
        if os.path.splitext(name)[1].lower() not in FILE_EXT[data['kategori']]:
            conn.close()
            return jsonify({'error': 'Jenis berkas ini tidak bisa dipakai untuk kategori tersebut'}), 400
        sets.append('kategori = ?')
        params.append(data['kategori'])
    if 'folder_id' in data:
        folder_id, ok = _active_folder(c, data.get('folder_id'))
        if not ok:
            conn.close()
            return jsonify({'error': 'Folder tujuan tidak ditemukan'}), 404
        sets.append('folder_id = ?')
        params.append(folder_id)

    if sets:
        c.execute(f'UPDATE files SET {", ".join(sets)} WHERE id = ?', [*params, file_id])
        conn.commit()
    conn.close()
    return jsonify({'message': 'Berkas diperbarui'}), 200


@bp.route('/api/files/<int:file_id>', methods=['DELETE'])
@require_role(*FILE_MANAGER_ROLES)
def delete_file(file_id):
    conn = connect()
    c = conn.cursor()
    c.execute('UPDATE files SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL', (now_iso(), file_id))
    found = c.rowcount
    conn.commit()
    conn.close()
    if not found:
        return jsonify({'error': 'Berkas tidak ditemukan'}), 404
    return jsonify({'message': 'Berkas dihapus'}), 200


@bp.route('/api/files/<int:file_id>/download', methods=['GET'])
@require_auth
def download_file(file_id):
    conn = connect()
    row = conn.execute('SELECT original_name FROM files WHERE id = ? AND deleted_at IS NULL',
                       (file_id,)).fetchone()
    conn.close()
    path = stored_file_path(file_id)
    if not row or not path:
        return jsonify({'error': 'Berkas tidak ditemukan'}), 404
    return send_file(path, as_attachment=True, download_name=row[0])
