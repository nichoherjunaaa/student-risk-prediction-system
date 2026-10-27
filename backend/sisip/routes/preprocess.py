"""Preprocessing berkas PMB + akademik menjadi data latih."""
import json
import os
import re
import time
import uuid

import pandas as pd
from flask import Blueprint, jsonify, request, send_file

from ..auth import require_role
from ..config import PREPROCESS_DIR, PREPROCESS_TTL
from ..constants import TRAIN_SHEET_PREFIX
from ..preprocessing import PreprocessError, build_training_table, preview_records
from ..settings_store import current_format
from ..utils import slug
from .files import stored_file_path

bp = Blueprint('preprocess', __name__)


_JOB_ID_RE = re.compile(r'^[0-9a-f]{32}$')


def _prune_preprocess_dir():
    """Buang hasil preprocessing lama supaya folder kerja tidak menggelembung.

    Folder dibuat ulang di sini, bukan hanya sekali saat impor: folder kerja bisa
    hilang saat server sedang jalan (dibersihkan manual, volume di-remount), dan
    dulu itu membuat endpoint gagal dengan 500 HTML — bukan pesan JSON."""
    os.makedirs(PREPROCESS_DIR, exist_ok=True)
    batas = time.time() - PREPROCESS_TTL
    for name in os.listdir(PREPROCESS_DIR):
        path = os.path.join(PREPROCESS_DIR, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < batas:
                os.remove(path)
        except OSError:
            pass


@bp.route('/api/preprocess', methods=['POST'])
@require_role('admin')
def run_preprocess():
    """Gabungkan berkas PMB dan berkas akademik (Excel atau CSV) menjadi satu
    tabel latih berlabel, setara sheet TRAIN_SEM<n> di cnn_tabular_2d_v2.py,
    siap diunggah di Master Model.

    Peran tiap sheet/tabel dikenali dari susunan kolomnya, jadi berkas dengan
    satu sheet, banyak sheet, maupun CSV sama-sama diterima."""
    # Tiap berkas boleh diunggah langsung atau dipilih dari Berkas Mahasiswa
    # (diunggah BAPSI) lewat id-nya.
    berkas = {}
    for key, judul in (('pmb', 'PMB'), ('akademik', 'akademik')):
        berkas[key] = request.files.get(f'file_{key}')
        file_id = request.form.get(f'file_{key}_id')
        if not berkas[key] and file_id:
            berkas[key] = stored_file_path(file_id)
            if not berkas[key]:
                return jsonify({'error': f'Berkas {judul} yang dipilih tidak ditemukan atau sudah dihapus.'}), 400
    berkas_pmb, berkas_akademik = berkas['pmb'], berkas['akademik']
    if not berkas_pmb or not berkas_akademik:
        return jsonify({'error': 'Berkas PMB dan berkas akademik wajib diunggah keduanya.'}), 400

    try:
        hasil = build_training_table(
            berkas_pmb, berkas_akademik,
            prodi=request.form.get('prodi') or None,
            max_semester=request.form.get('semester', 3),
            fmt=current_format(),
        )
    except PreprocessError as err:
        return jsonify({'error': str(err)}), 400
    except Exception as err:
        return jsonify({'error': f'Gagal memproses berkas: {err}'}), 400

    job_id = uuid.uuid4().hex
    sheet_name = f'{TRAIN_SHEET_PREFIX}{hasil.max_semester}'
    nama_berkas = f'data_latih_{slug(hasil.prodi)}_sem{hasil.max_semester}.xlsx'

    # Penulisan berkas ikut ditangani: kegagalan menulis (folder hilang, disk
    # penuh, batas kolom Excel) harus tetap membalas JSON, bukan halaman 500.
    try:
        _prune_preprocess_dir()
        with pd.ExcelWriter(os.path.join(PREPROCESS_DIR, f'{job_id}.xlsx'),
                            engine='openpyxl') as writer:
            hasil.df.to_excel(writer, index=False, sheet_name=sheet_name)
        with open(os.path.join(PREPROCESS_DIR, f'{job_id}.json'), 'w', encoding='utf-8') as fp:
            json.dump({'filename': nama_berkas, 'prodi': hasil.prodi,
                       'sheet': sheet_name, 'report': hasil.report}, fp)
    except Exception as err:
        return jsonify({'error': 'Data berhasil diproses tetapi gagal disimpan di server: '
                                 f'{err}'}), 500

    return jsonify({
        'job_id': job_id,
        'filename': nama_berkas,
        'download_url': f'/api/preprocess/{job_id}/download',
        'sheet': sheet_name,
        'prodi': hasil.prodi,
        'semester': hasil.max_semester,
        'columns': list(hasil.df.columns),
        'preview': preview_records(hasil.df, 8),
        'report': hasil.report,
    }), 200


@bp.route('/api/preprocess/<job_id>/download', methods=['GET'])
@require_role('admin')
def download_preprocess_result(job_id):
    if not _JOB_ID_RE.match(job_id or ''):
        return jsonify({'error': 'Kode hasil preprocessing tidak valid.'}), 400

    path = os.path.join(PREPROCESS_DIR, f'{job_id}.xlsx')
    if not os.path.exists(path):
        return jsonify({'error': 'Hasil preprocessing sudah kedaluwarsa. '
                                 'Silakan jalankan ulang prosesnya.'}), 404

    nama_berkas = 'data_latih.xlsx'
    try:
        with open(os.path.join(PREPROCESS_DIR, f'{job_id}.json'), encoding='utf-8') as fp:
            nama_berkas = json.load(fp).get('filename', nama_berkas)
    except (OSError, ValueError):
        pass

    return send_file(
        path,
        as_attachment=True,
        download_name=nama_berkas,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
