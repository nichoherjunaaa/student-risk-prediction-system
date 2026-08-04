import sqlite3

def update_db():
    conn = sqlite3.connect('sisip_database.db')
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE predictions ADD COLUMN details TEXT;")
        print("Column 'details' added successfully.")
    except sqlite3.OperationalError as e:
        print("Column already exists or error:", e)
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_db()
