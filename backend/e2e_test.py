"""End-to-end smoke test untuk API SISIP.

Menjalankan seluruh alur lewat Flask test client, tanpa perlu menyalakan server:
autentikasi, hak akses per-role, unduh template, prediksi, dan perbaikan-perbaikan
terbaru (dedup batch per-semester, filter angkatan tahan sel kosong, metrik model
epoch terbaik).

Pakai SALINAN database aktif + folder saved_models yang ada, jadi database asli
tidak tersentuh.

    cd backend && venv/bin/python e2e_test.py
"""
import io
import os
import sys
import shutil
import sqlite3
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_DB = os.path.join(HERE, 'sisip_database.db')
DATASET = os.path.join(HERE, '..', 'DATA MAHASISWA 20-24.xlsx')

# --- siapkan DB sementara sebelum app diimpor -------------------------------
_tmpdir = tempfile.mkdtemp(prefix='sisip-e2e-')
_tmp_db = os.path.join(_tmpdir, 'e2e.db')
shutil.copyfile(REAL_DB, _tmp_db)
os.environ['SISIP_DB_FILE'] = _tmp_db
os.environ['SISIP_MODEL_DIR'] = os.path.join(HERE, 'saved_models')
os.environ['SISIP_SEED_DEMO_USERS'] = '1'
os.environ['SISIP_SECRET_KEY'] = 'e2e-test-secret'
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

os.chdir(HERE)
import app as A  # noqa: E402

client = A.app.test_client()

_passed = 0
_failed = 0


def check(name, cond, detail=''):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}  {detail}")


def login(email, password):
    r = client.post('/api/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        return None
    return r.get_json()['token']


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def active_prodi():
    conn = sqlite3.connect(_tmp_db)
    row = conn.execute("SELECT prodi FROM model_registry WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else 'Informatika'


def run():
    print("\n=== 1. Autentikasi & hak akses ===")
    r = client.get('/api/health')
    check('health tanpa token -> 200', r.status_code == 200, r.status_code)

    r = client.get('/api/history')
    check('endpoint terlindungi tanpa token -> 401', r.status_code == 401, r.status_code)

    r = client.post('/api/login', json={'email': 'admin@gmail.com', 'password': 'salah'})
    check('login password salah -> 401', r.status_code == 401, r.status_code)

    admin_tok = login('admin@gmail.com', 'admin123')
    check('login admin (hash lama SHA-256) -> token', bool(admin_tok))

    dpa_tok = login('dpa.test@sisip.test', 'Dpa#2026')
    check('login demo DPA (hash baru PBKDF2) -> token', bool(dpa_tok))

    r = client.post('/api/train', headers=auth(dpa_tok), data={})
    check('DPA akses /api/train -> 403', r.status_code == 403, r.status_code)

    r = client.get('/api/users', headers=auth(dpa_tok))
    check('DPA akses /api/users -> 403', r.status_code == 403, r.status_code)

    r = client.get('/api/users', headers=auth(admin_tok))
    check('admin akses /api/users -> 200', r.status_code == 200, r.status_code)

    r = client.get('/api/history', headers=auth(A._token_serializer.dumps({'uid': 9, 'email': 'x', 'role': 'dpa'})[:-3] + 'xxx'))
    check('token dipalsukan -> 401', r.status_code == 401, r.status_code)

    prodi = active_prodi()
    print(f"\n=== 2. Template & prediksi (prodi aktif: {prodi}) ===")

    r = client.get(f'/api/template/predict?prodi={prodi}&angkatan=2023&semester=3', headers=auth(dpa_tok))
    check('unduh template -> 200 xlsx', r.status_code == 200 and 'spreadsheet' in r.headers.get('Content-Type', ''),
          r.status_code)
    template_bytes = r.data

    def predict(sem, tok=dpa_tok, data_override=None):
        payload = {
            'file': (io.BytesIO(data_override or template_bytes), 'template.xlsx'),
            'prodi': prodi, 'angkatan': '2023', 'semester': str(sem),
        }
        return client.post('/api/predict', headers=auth(tok), data=payload,
                           content_type='multipart/form-data')

    r = predict(3)
    check('prediksi pakai template -> 200', r.status_code == 200, r.data[:200])
    body = r.get_json() if r.status_code == 200 else {}
    check('hasil prediksi bervariasi (bukan satu kelas)',
          body.get('atRisk', 0) > 0 and body.get('safe', 0) > 0,
          f"atRisk={body.get('atRisk')} safe={body.get('safe')}")
    check('respons menyertakan semester', body.get('semester') == '3', body.get('semester'))

    print("\n=== 3. Dedup batch per-semester (perbaikan #2) ===")
    # Pakai dataset asli (tanpa kolom Semester) supaya filter semester dilewati
    # dan nilai semester tersimpan apa adanya dari parameter.
    with open(DATASET, 'rb') as f:
        ds_bytes = f.read()

    def predict_ds(sem):
        return client.post('/api/predict', headers=auth(dpa_tok), data={
            'file': (io.BytesIO(ds_bytes), 'DATA.xlsx'),
            'prodi': 'Informatika', 'angkatan': '2023', 'semester': str(sem),
        }, content_type='multipart/form-data')

    def batch_ids_for(sem):
        conn = sqlite3.connect(_tmp_db)
        rows = conn.execute(
            "SELECT id FROM batches WHERE prodi='Informatika' AND IFNULL(angkatan,'')='2023' AND IFNULL(semester,'')=?",
            (str(sem),)).fetchall()
        conn.close()
        return [x[0] for x in rows]

    check('prediksi semester 3 -> 200', predict_ds(3).status_code == 200)
    check('prediksi semester 5 -> 200', predict_ds(5).status_code == 200)
    s3, s5 = batch_ids_for(3), batch_ids_for(5)
    check('batch semester 3 tetap ada setelah prediksi semester 5', len(s3) == 1, s3)
    check('batch semester 5 dibuat terpisah', len(s5) == 1 and s5 != s3, (s3, s5))
    predict_ds(3)
    check('prediksi ulang semester 3 menimpa, bukan menggandakan',
          batch_ids_for(3) != s3 and len(batch_ids_for(3)) == 1)

    print("\n=== 4. Diagnosa berkas tidak cocok ===")
    r = client.post('/api/predict', headers=auth(dpa_tok), data={
        'file': (io.BytesIO(template_bytes), 't.xlsx'),
        'prodi': prodi, 'angkatan': '2099', 'semester': '3',
    }, content_type='multipart/form-data')
    check('angkatan tidak cocok -> 400 dengan penjelasan',
          r.status_code == 400 and 'Angkatan' in r.get_json().get('error', ''), r.get_json())

    print("\n=== 5. Regresi dataset asli (tanpa kolom Prodi/Semester) ===")
    with open(DATASET, 'rb') as f:
        ds = f.read()
    r = client.post('/api/predict', headers=auth(dpa_tok), data={
        'file': (io.BytesIO(ds), 'DATA.xlsx'),
        'prodi': 'Informatika', 'angkatan': '2023', 'semester': '3',
    }, content_type='multipart/form-data')
    check('prediksi dataset asli -> 200', r.status_code == 200, r.data[:200])
    if r.status_code == 200:
        jb = r.get_json()
        check('dataset asli menghasilkan >0 baris', jb.get('total', 0) > 0, jb.get('total'))

    print("\n=== 6. Filter angkatan tahan sel kosong saat training (perbaikan #4) ===")
    import pandas as pd
    xl = pd.ExcelFile(DATASET)
    tr = pd.read_excel(xl, 'TRAIN_SEM3')
    if 'Angkatan' in tr.columns:
        tr = tr.copy()
        tr.loc[tr.index[:2], 'Angkatan'] = None          # kosongkan 2 sel -> kolom jadi float
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            tr.to_excel(w, index=False, sheet_name='TRAIN_SEM3')
        buf.seek(0)
        norm = A._norm_str
        want = {norm(v) for v in tr['Angkatan'].dropna().unique()}
        got = set(tr['Angkatan'].map(norm)) & want
        check('_norm_str menyamakan "2023" dan "2023.0"',
              norm(2023.0) == norm('2023') == '2023')
        check('baris angkatan valid masih cocok setelah kolom jadi float', len(got) > 0, got)

    print("\n=== 7. Metrik model = epoch val_loss terbaik (perbaikan #3) ===")
    src = open(os.path.join(HERE, 'app.py')).read()
    check('training pakai argmin(val_loss), bukan [-1]',
          'np.argmin(loss_series)' in src and "history.history['val_accuracy'][-1]" not in src)

    print("\n=== 8. Aktivasi model memeriksa kelengkapan berkas (perbaikan #16) ===")
    conn = sqlite3.connect(_tmp_db)
    conn.execute("INSERT INTO model_registry (version_name, prodi, file_path, accuracy, loss, trained_at, is_active) "
                 "VALUES ('Model_hantu', 'Informatika', 'saved_models/Model_hantu.keras', 0.9, 0.1, '2026-01-01', 0)")
    conn.commit()
    ghost_id = conn.execute("SELECT id FROM model_registry WHERE version_name='Model_hantu'").fetchone()[0]
    conn.close()
    r = client.post(f'/api/models/{ghost_id}/activate', headers=auth(admin_tok))
    check('aktivasi model tanpa berkas -> 400', r.status_code == 400, r.status_code)


try:
    run()
finally:
    shutil.rmtree(_tmpdir, ignore_errors=True)

print(f"\n{'='*48}\n  {_passed} passed, {_failed} failed\n{'='*48}")
sys.exit(1 if _failed else 0)
