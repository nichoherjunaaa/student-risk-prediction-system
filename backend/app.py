"""Titik masuk server: `gunicorn app:app` (lihat Dockerfile) atau `python app.py`.

Seluruh kode backend ada di paket sisip/; berkas ini hanya membuat aplikasinya."""
from sisip import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
