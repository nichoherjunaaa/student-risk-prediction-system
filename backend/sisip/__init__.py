"""Backend SISIP Program.

Struktur paket:
    config.py        pengaturan dari environment
    constants.py     skema kolom internal (kontrak dengan model terlatih)
    data_format.py   format berkas mentah yang bisa diatur admin
    db.py            koneksi, skema, migrasi
    auth.py          token login & dekorator hak akses
    ml.py            arsitektur CNN & registri berkas model
    preprocessing.py penggabungan berkas PMB + akademik
    routes/          endpoint API, satu blueprint per area
"""
import os

# Harus diisi sebelum TensorFlow diimpor (oleh sisip.ml) supaya training
# deterministik.
os.environ.setdefault('TF_DETERMINISTIC_OPS', '1')
os.environ.setdefault('TF_CUDNN_DETERMINISTIC', '1')
os.environ.setdefault('PYTHONHASHSEED', '42')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402

from . import config  # noqa: E402
from .db import connect, init_db  # noqa: E402


def create_app():
    app = Flask(__name__)
    origins = config.CORS_ORIGINS
    CORS(app, resources={r"/api/*": {
        "origins": '*' if origins == '*' else [o.strip() for o in origins.split(',') if o.strip()]
    }})

    config.ensure_dirs()
    init_db()

    from .routes import BLUEPRINTS
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        """Endpoint /api/* selalu membalas JSON, termasuk saat terjadi galat yang
        tidak tertangani. Sebelumnya Flask membalas halaman HTML 500, sehingga sisi
        frontend hanya melihat pesan generik dan penyebab aslinya tak terlihat."""
        if isinstance(err, HTTPException):
            if request.path.startswith('/api/'):
                return jsonify({'error': err.description}), err.code
            return err

        app.logger.exception('Kesalahan tak tertangani pada %s', request.path)
        if request.path.startswith('/api/'):
            return jsonify({'error': f'Kesalahan internal server: {err}'}), 500
        raise err

    @app.route('/api/health', methods=['GET'])
    def health():
        try:
            conn = connect()
            conn.execute("SELECT 1")
            conn.close()
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'detail': str(e)}), 500

    return app
