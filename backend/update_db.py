"""Migrasi database manual.

Tidak lagi diperlukan untuk operasi normal: app.py menjalankan migrasi idempoten
(_migrate_columns) setiap kali start. Skrip ini disimpan sebagai pintasan bila
ingin menjalankan migrasi tanpa menyalakan server.

    cd backend && venv/bin/python update_db.py
"""
import app

if __name__ == '__main__':
    app.init_db()
    print("Skema database sudah sinkron (kolom yang kurang otomatis ditambahkan).")
