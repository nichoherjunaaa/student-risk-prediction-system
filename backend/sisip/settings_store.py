"""Akses format data yang sedang berlaku (bawaan atau versi simpanan admin)."""
from .data_format import DataFormat, load_format_row
from .db import connect


def current_format():
    conn = connect()
    try:
        raw, _ = load_format_row(conn)
    finally:
        conn.close()
    return DataFormat(raw)
