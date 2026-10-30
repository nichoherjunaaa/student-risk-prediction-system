"""Riwayat batch prediksi dan detail mahasiswa milik user yang login."""
import json
import sqlite3

from flask import Blueprint, jsonify, request

from ..auth import require_role

# User yang terikat prodi hanya melihat batch prodinya, termasuk batch lama
# miliknya sendiri dari sebelum prodinya ditetapkan/diubah admin.
_PRODI_FILTER = ' AND (? IS NULL OR b.prodi = ?)'


def _prodi_args():
    p = request.user.get('prodi')
    return (p, p)
from ..config import PREDIKSI_ROLES
from ..db import connect

bp = Blueprint('history', __name__)


@bp.route('/api/history', methods=['GET'])
@require_role(*PREDIKSI_ROLES)
def get_history():
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Setiap user hanya melihat batch prediksinya sendiri, termasuk admin.
    c.execute('SELECT * FROM batches b WHERE user_id = ? AND deleted_at IS NULL' + _PRODI_FILTER + ' ORDER BY id DESC',
              (request.user['uid'], *_prodi_args()))
    batches = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'batches': batches})

@bp.route('/api/batch/<int:batch_id>', methods=['GET'])
@require_role(*PREDIKSI_ROLES)
def get_batch(batch_id):
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches b WHERE id = ? AND user_id = ? AND deleted_at IS NULL' + _PRODI_FILTER,
              (batch_id, request.user['uid'], *_prodi_args()))
    batch = c.fetchone()
    if not batch:
        conn.close()
        return jsonify({'error': 'Batch not found'}), 404
        
    c.execute('SELECT * FROM predictions WHERE batch_id = ?', (batch_id,))
    predictions = [dict(row) for row in c.fetchall()]
    conn.close()
    
    result = dict(batch)
    result['results'] = predictions
    return jsonify(result)

@bp.route('/api/student/<nim>', methods=['GET'])
@require_role(*PREDIKSI_ROLES)
def get_student(nim):
    batch_id = request.args.get('batch')
    
    conn = connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if batch_id:
        c.execute('''
            SELECT p.*, b.batch_name, b.date_uploaded, b.semester AS batch_semester
            FROM predictions p 
            JOIN batches b ON p.batch_id = b.id 
            WHERE p.nim = ? AND p.batch_id = ? AND b.user_id = ? AND b.deleted_at IS NULL
        ''' + _PRODI_FILTER + ' ORDER BY p.id DESC LIMIT 1', (nim, batch_id, request.user['uid'], *_prodi_args()))
    else:
        # Prediksi terbaru untuk NIM ini dari batch milik user sendiri
        c.execute('''
            SELECT p.*, b.batch_name, b.date_uploaded, b.semester AS batch_semester
            FROM predictions p 
            JOIN batches b ON p.batch_id = b.id 
            WHERE p.nim = ? AND b.user_id = ? AND b.deleted_at IS NULL
        ''' + _PRODI_FILTER + ' ORDER BY p.id DESC LIMIT 1', (nim, request.user['uid'], *_prodi_args()))
        
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Student not found'}), 404
        
    student_data = dict(row)
    if student_data.get('details'):
        student_data['details'] = json.loads(student_data['details'])
    else:
        student_data['details'] = {}
        
    return jsonify(student_data)
