"""Migrasi database manual.

Tidak lagi diperlukan untuk operasi normal: server menjalankan migrasi idempoten
(sisip.db.init_db) setiap kali start. Skrip ini disimpan sebagai pintasan bila
ingin menjalankan migrasi tanpa menyalakan server.

    cd backend && venv/bin/python update_db.py
"""
from sisip.db import init_db

if __name__ == '__main__':
    init_db()
    print("Skema database sudah sinkron (kolom yang kurang otomatis ditambahkan).")
