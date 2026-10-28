"""End-to-end smoke test untuk API SISIP.

Menjalankan seluruh alur lewat Flask test client, tanpa perlu menyalakan server:
autentikasi, hak akses per-role, prediksi dari Berkas Mahasiswa, dan perbaikan-perbaikan
terbaru (dedup batch per-semester, filter angkatan tahan sel kosong, metrik model
epoch terbaik).

Pakai SALINAN database aktif + folder saved_models yang ada, jadi database asli
tidak tersentuh.

    cd backend && venv/bin/python e2e_test.py
"""
import io
import json
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
os.environ['SISIP_FILES_DIR'] = os.path.join(_tmpdir, 'files')
os.environ['SISIP_ADMIN_NIP'] = '235314122'
os.environ['SISIP_ADMIN_PASSWORD'] = ADMIN_PW = 'e2e-admin-password'
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')

os.chdir(HERE)
import app as A  # noqa: E402
from sisip.auth import token_serializer  # noqa: E402
from sisip.passwords import hash_pw  # noqa: E402

# DB sementara disalin dari DB asli, yang admin utamanya sudah punya password
# sendiri (SISIP_ADMIN_PASSWORD hanya dipakai saat tabel users kosong). Samakan
# di salinan ini saja supaya password asli tidak perlu ditulis di kode.
with sqlite3.connect(_tmp_db) as _conn:
    _conn.execute('UPDATE users SET password = ? WHERE nip = ? AND deleted_at IS NULL',
                  (hash_pw(ADMIN_PW), os.environ['SISIP_ADMIN_NIP']))
from sisip.utils import norm_str  # noqa: E402

client = A.app.test_client()

# Skenario uji mengandalkan akun demo DPA/Kaprodi yang belum terikat prodi.
# Database asli boleh saja sudah mengaturnya; yang diubah hanya salinannya.
_c = sqlite3.connect(_tmp_db)
_c.execute("UPDATE users SET prodi = NULL WHERE nip LIKE '90000000000000000%'")
_c.commit()
_c.close()

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


def login(nip, password):
    r = client.post('/api/login', json={'nip': nip, 'password': password})
    if r.status_code != 200:
        return None
    return r.get_json()['token']


ADMIN_NIP = '235314122'
DPA_NIP = '900000000000000002'
KAPRODI_NIP = '900000000000000003'
BAPSI_NIP = '900000000000000004'


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

    r = client.post('/api/login', json={'nip': ADMIN_NIP, 'password': 'salah'})
    check('login password salah -> 401', r.status_code == 401, r.status_code)

    admin_tok = login(ADMIN_NIP, ADMIN_PW)
    check('login admin utama pakai NIP -> token', bool(admin_tok))

    r = client.post('/api/login', json={'email': 'admin@gmail.com', 'password': ADMIN_PW})
    check('login pakai email sudah tidak diterima -> 400', r.status_code == 400, r.status_code)

    check('NIP boleh ditulis berspasi/bertitik', bool(login('235.314 122', ADMIN_PW)))

    dpa_tok = login(DPA_NIP, 'Dpa#2026')
    check('login demo DPA (hash baru PBKDF2) -> token', bool(dpa_tok))

    r = client.post('/api/train', headers=auth(dpa_tok), data={})
    check('DPA akses /api/train -> 403', r.status_code == 403, r.status_code)

    r = client.get('/api/users', headers=auth(dpa_tok))
    check('DPA akses /api/users -> 403', r.status_code == 403, r.status_code)

    r = client.get('/api/users', headers=auth(admin_tok))
    check('admin akses /api/users -> 200', r.status_code == 200, r.status_code)

    r = client.get('/api/history', headers=auth(token_serializer.dumps({'uid': 9, 'nip': 'x', 'role': 'dpa'})[:-3] + 'xxx'))
    check('token dipalsukan -> 401', r.status_code == 401, r.status_code)

    prodi = active_prodi()
    print(f"\n=== 2. Prediksi dari Berkas Mahasiswa (prodi aktif: {prodi}) ===")
    # BAPSI mengunggah berkas PMB & akademik; prediksi selalu memakai berkas di
    # Berkas Mahasiswa. Berkas ini dihapus lagi sebelum bagian 13.
    bapsi_tok = login(BAPSI_NIP, 'Bapsi#2026')
    setup_ids = []
    for kategori, nama in (('pmb', '20260605_Data_PMB.xlsx'), ('akademik', 'Data_akademik_te_tm_mat.xlsx')):
        with open(os.path.join(HERE, '..', nama), 'rb') as f:
            r = client.post('/api/files', headers=auth(bapsi_tok), content_type='multipart/form-data',
                            data={'kategori': kategori, 'folder_id': '', 'files': (io.BytesIO(f.read()), nama)})
        setup_ids.append(r.get_json()['files'][0]['id'])
    check('BAPSI unggah berkas PMB & akademik -> 201', len(setup_ids) == 2)

    def predict(angkatan='2023', tok=dpa_tok, **extra):
        return client.post('/api/predict/berkas', headers=auth(tok),
                           json={'prodi': prodi, 'angkatan': angkatan, **extra})

    r = predict()
    check('prediksi dari berkas -> 200', r.status_code == 200, r.data[:200])
    body = r.get_json() if r.status_code == 200 else {}
    check('hasil prediksi bervariasi (bukan satu kelas)',
          body.get('atRisk', 0) > 0 and body.get('safe', 0) > 0,
          f"atRisk={body.get('atRisk')} safe={body.get('safe')}")
    check('respons menyertakan semester = batas semester model', str(body.get('semester')) == '3',
          body.get('semester'))
    check('endpoint template sudah dihapus',
          client.get(f'/api/template/predict?prodi={prodi}', headers=auth(dpa_tok)).status_code == 404
          and client.post('/api/predict', headers=auth(dpa_tok), data={}).status_code in (404, 405))

    print("\n=== 3. Dedup batch per angkatan (perbaikan #2) ===")
    def batch_ids_for(angkatan):
        conn = sqlite3.connect(_tmp_db)
        rows = conn.execute(
            "SELECT id FROM batches WHERE prodi=? AND IFNULL(angkatan,'')=? AND deleted_at IS NULL AND user_id=?",
            (prodi, str(angkatan), token_serializer.loads(dpa_tok)['uid'])).fetchall()
        conn.close()
        return [x[0] for x in rows]

    check('prediksi angkatan 2022 -> 200', predict('2022').status_code == 200)
    a23, a22 = batch_ids_for(2023), batch_ids_for(2022)
    check('batch angkatan 2023 tetap ada setelah prediksi angkatan 2022', len(a23) == 1, a23)
    check('batch angkatan 2022 dibuat terpisah', len(a22) == 1 and a22 != a23, (a23, a22))
    predict('2023')
    check('prediksi ulang angkatan 2023 menimpa, bukan menggandakan',
          batch_ids_for(2023) != a23 and len(batch_ids_for(2023)) == 1)

    print("\n=== 3b. Hasil prediksi terpisah per user + soft delete ===")
    kaprodi_tok = login(KAPRODI_NIP, 'Kaprodi#2026')
    kaprodi_uid = token_serializer.loads(kaprodi_tok)['uid']
    dpa_s3 = batch_ids_for(2023)
    r = predict(tok=kaprodi_tok, uploaded_by='Nama Palsu')
    check('prediksi kaprodi (kombinasi sama dgn DPA) -> 200', r.status_code == 200)
    kap_batch = r.get_json()['batch_id']
    check('prediksi user lain tidak menimpa batch DPA', set(dpa_s3) <= set(batch_ids_for(2023)),
          (dpa_s3, batch_ids_for(2023)))

    conn = sqlite3.connect(_tmp_db)
    owner, name = conn.execute('SELECT user_id, uploaded_by FROM batches WHERE id=?', (kap_batch,)).fetchone()
    conn.close()
    check('pemilik & uploaded_by diambil dari token, bukan form',
          owner == kaprodi_uid and name == 'Kaprodi Tester', (owner, name))

    dpa_hist = {b['id'] for b in client.get('/api/history', headers=auth(dpa_tok)).get_json()['batches']}
    kap_hist = {b['id'] for b in client.get('/api/history', headers=auth(kaprodi_tok)).get_json()['batches']}
    check('history DPA tidak memuat batch kaprodi', kap_batch not in dpa_hist and dpa_s3[0] in dpa_hist)
    check('history kaprodi hanya batch miliknya', kap_hist == {kap_batch}, kap_hist)
    check('DPA buka batch kaprodi -> 404',
          client.get(f'/api/batch/{kap_batch}', headers=auth(dpa_tok)).status_code == 404)
    check('kaprodi buka batch sendiri -> 200',
          client.get(f'/api/batch/{kap_batch}', headers=auth(kaprodi_tok)).status_code == 200)
    nim = client.get(f'/api/batch/{kap_batch}', headers=auth(kaprodi_tok)).get_json()['results'][0]['nim']
    check('DPA buka mahasiswa via batch kaprodi -> 404',
          client.get(f'/api/student/{nim}?batch={kap_batch}', headers=auth(dpa_tok)).status_code == 404)
    r = client.get(f'/api/student/{nim}', headers=auth(dpa_tok))
    check('student tanpa batch -> dari batch milik DPA sendiri',
          r.status_code == 200 and r.get_json()['batch_id'] != kap_batch, r.status_code)

    r = client.delete(f'/api/users/{kaprodi_uid}', headers=auth(admin_tok))
    check('admin hapus kaprodi -> 200', r.status_code == 200, r.status_code)
    conn = sqlite3.connect(_tmp_db)
    urow = conn.execute('SELECT deleted_at FROM users WHERE id=?', (kaprodi_uid,)).fetchone()
    brow = conn.execute('SELECT deleted_at FROM batches WHERE id=?', (kap_batch,)).fetchone()
    npred = conn.execute('SELECT COUNT(*) FROM predictions WHERE batch_id=?', (kap_batch,)).fetchone()[0]
    conn.close()
    check('user di-soft-delete (baris masih ada)', urow is not None and urow[0] is not None, urow)
    check('batch user ikut di-soft-delete, prediksi tetap tersimpan',
          brow is not None and brow[0] is not None and npred > 0, (brow, npred))
    check('token user terhapus langsung ditolak -> 401',
          client.get('/api/history', headers=auth(kaprodi_tok)).status_code == 401)
    check('user terhapus tidak bisa login', login(KAPRODI_NIP, 'Kaprodi#2026') is None)
    ulist = client.get('/api/users', headers=auth(admin_tok)).get_json()
    check('user terhapus hilang dari daftar user', all(u['id'] != kaprodi_uid for u in ulist))
    check('hapus user yang sudah terhapus -> 404',
          client.delete(f'/api/users/{kaprodi_uid}', headers=auth(admin_tok)).status_code == 404)
    r = client.post('/api/users', headers=auth(admin_tok),
                    json={'nip': KAPRODI_NIP, 'password': 'Baru#2026', 'name': 'Kaprodi Baru', 'role': 'kaprodi',
                          'prodi': prodi})
    check('NIP user terhapus bisa dipakai akun baru -> 201', r.status_code == 201, r.get_json())
    new_tok = login(KAPRODI_NIP, 'Baru#2026')
    check('akun baru tidak mewarisi batch akun lama',
          new_tok and client.get('/api/history', headers=auth(new_tok)).get_json()['batches'] == [])
    check('dpa masih melihat batch miliknya', dpa_s3[0] in
          {b['id'] for b in client.get('/api/history', headers=auth(dpa_tok)).get_json()['batches']})

    print("\n=== 4. Diagnosa angkatan tidak ada di berkas ===")
    r = predict('2099')
    check('angkatan tidak ada -> 400 dengan penjelasan',
          r.status_code == 400 and 'angkatan' in r.get_json().get('error', '').lower(), r.get_json())

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
        norm = norm_str
        want = {norm(v) for v in tr['Angkatan'].dropna().unique()}
        got = set(tr['Angkatan'].map(norm)) & want
        check('_norm_str menyamakan "2023" dan "2023.0"',
              norm(2023.0) == norm('2023') == '2023')
        check('baris angkatan valid masih cocok setelah kolom jadi float', len(got) > 0, got)

    print("\n=== 7. Metrik model = epoch val_loss terbaik (perbaikan #3) ===")
    src = open(os.path.join(HERE, 'sisip', 'routes', 'training.py')).read()
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

    print("\n=== 8b. Registri model per halaman ===")
    semua = client.get('/api/models', headers=auth(admin_tok)).get_json()
    check('tanpa ?page tetap array semua model', isinstance(semua, list) and len(semua) >= 1, type(semua))
    pg = client.get('/api/models?page=1&per_page=1', headers=auth(admin_tok)).get_json()
    check('?page=1&per_page=1 -> 1 item + total',
          len(pg['items']) == 1 and pg['total'] == len(semua) and pg['total_pages'] == len(semua), pg)
    check('halaman 1 = model terbaru', pg['items'][0]['id'] == semua[0]['id'])
    check('respons memuat kolom angkatan', 'angkatan' in pg['items'][0])
    pg = client.get('/api/models?page=999&per_page=1', headers=auth(admin_tok)).get_json()
    check('page melebihi batas -> halaman terakhir', pg['page'] == pg['total_pages'] and len(pg['items']) == 1, pg)
    pg = client.get('/api/models?page=abc&per_page=-5', headers=auth(admin_tok)).get_json()
    check('page/per_page tidak valid -> bawaan (1, 10)', pg['page'] == 1 and pg['per_page'] == 10, pg)
    pg = client.get('/api/models?page=1&per_page=5000', headers=auth(admin_tok)).get_json()
    check('per_page dibatasi 100', pg['per_page'] == 100, pg['per_page'])


    print("\n=== 9. Manajemen pengguna berbasis NIP ===")
    def new_user(**kw):
        return client.post('/api/users', headers=auth(admin_tok), json=kw)
    r = new_user(nip='19870101 201001 1 001', name='Admin Kedua', password='Adm2#2026', role='admin')
    check('admin bisa menambah akun admin lain -> 201', r.status_code == 201, r.get_json())
    check('admin kedua bisa login dgn NIP yang dinormalisasi', bool(login('198701012010011001', 'Adm2#2026')))
    r = new_user(nip='dsn-12ab345', name='Dosen Huruf', password='Dsn#2026', role='admin')
    check('NIP berisi huruf & angka -> 201, disimpan kapital',
          r.status_code == 201 and any(u['nip'] == 'DSN12AB345' for u in
                                       client.get('/api/users', headers=auth(admin_tok)).get_json()), r.get_json())
    check('login NIP huruf tidak peka huruf besar/kecil',
          bool(login('dsn12ab345', 'Dsn#2026')) and bool(login('DSN-12AB345', 'Dsn#2026')))
    check('NIP dengan simbol lain -> 400', new_user(nip='12/AB345', name='X', password='x', role='dpa').status_code == 400)
    check('peran tak dikenal -> 400', new_user(nip='55555', name='X', password='x', role='rektor').status_code == 400)
    check('NIP duplikat -> 400', new_user(nip=DPA_NIP, name='X', password='x', role='dpa').status_code == 400)
    ulist = client.get('/api/users', headers=auth(admin_tok)).get_json()
    check('daftar pengguna memuat akun admin & kolom nip',
          any(u['role'] == 'admin' for u in ulist) and all('nip' in u and 'email' not in u for u in ulist))
    admin_uid = token_serializer.loads(admin_tok)['uid']
    check('admin tidak bisa menghapus akunnya sendiri -> 400',
          client.delete(f'/api/users/{admin_uid}', headers=auth(admin_tok)).status_code == 400)
    r = client.put(f'/api/users/{admin_uid}', headers=auth(admin_tok),
                   json={'nip': ADMIN_NIP, 'name': 'Staf Admin', 'role': 'dpa'})
    check('admin tidak bisa menurunkan perannya sendiri -> 400', r.status_code == 400, r.status_code)

    print("\n=== 10. Role BAPSI & Berkas Mahasiswa ===")
    bapsi_tok = login(BAPSI_NIP, 'Bapsi#2026')
    check('login demo BAPSI -> token', bool(bapsi_tok))
    check('BAPSI akses /api/history -> 403', client.get('/api/history', headers=auth(bapsi_tok)).status_code == 403)
    check('BAPSI akses /api/predict/berkas -> 403',
          client.post('/api/predict/berkas', headers=auth(bapsi_tok), json={}).status_code == 403)
    check('DPA buat folder -> 403',
          client.post('/api/folders', headers=auth(dpa_tok), json={'name': 'x'}).status_code == 403)

    r = client.post('/api/folders', headers=auth(bapsi_tok), json={'name': '2026'})
    check('BAPSI buat folder -> 201', r.status_code == 201, r.get_json())
    f2026 = r.get_json()['id']
    r = client.post('/api/folders', headers=auth(bapsi_tok), json={'name': 'Ganjil', 'parent_id': f2026})
    check('BAPSI buat subfolder -> 201', r.status_code == 201, r.get_json())
    fganjil = r.get_json()['id']
    check('nama folder kembar di lokasi sama -> 400',
          client.post('/api/folders', headers=auth(bapsi_tok),
                      json={'name': 'ganjil', 'parent_id': f2026}).status_code == 400)

    def upload(kategori, name, data, folder=fganjil, tok=bapsi_tok):
        return client.post('/api/files', headers=auth(tok), content_type='multipart/form-data', data={
            'kategori': kategori, 'folder_id': '' if folder is None else str(folder),
            'files': (io.BytesIO(data), name)})

    pmb_path = os.path.join(HERE, '..', '20260605_Data_PMB.xlsx')
    akd_path = os.path.join(HERE, '..', 'Data_akademik_te_tm_mat.xlsx')
    pmb_bytes = open(pmb_path, 'rb').read()
    r = upload('pmb', 'PMB 2026.xlsx', pmb_bytes)
    check('BAPSI unggah berkas PMB -> 201', r.status_code == 201, r.get_json())
    pmb_id = r.get_json()['files'][0]['id']
    r = upload('akademik', 'Akademik.xlsx', open(akd_path, 'rb').read())
    akd_id = r.get_json()['files'][0]['id']
    check('PDF sebagai kategori PMB ditolak -> 400', upload('pmb', 'x.pdf', b'%PDF').status_code == 400)
    check('nama berkas dgn path traversal tidak keluar folder',
          upload('lainnya', '../../evil.csv', b'a,b').status_code == 201
          and not os.path.exists(os.path.join(os.environ['SISIP_FILES_DIR'], '..', 'evil.csv')))
    check('DPA unggah berkas -> 403', upload('lainnya', 'a.csv', b'a', tok=dpa_tok).status_code == 403)

    r = client.get(f'/api/files?folder_id={fganjil}', headers=auth(dpa_tok))
    body = r.get_json()
    check('DPA lihat isi folder -> 200, tanpa hak kelola',
          r.status_code == 200 and body['can_manage'] is False and len(body['files']) == 3, body)
    check('breadcrumb folder bertingkat', [b['name'] for b in body['breadcrumb']] == ['2026', 'Ganjil'])
    r = client.get(f'/api/files/{pmb_id}/download', headers=auth(dpa_tok))
    check('DPA unduh berkas -> isi utuh & nama asli',
          r.status_code == 200 and r.data == pmb_bytes and 'PMB 2026.xlsx' in r.headers.get('Content-Disposition', ''))
    r = client.get('/api/files?kategori=pmb', headers=auth(admin_tok)).get_json()
    check('pencarian per kategori memuat path folder',
          any(f['id'] == pmb_id and f['path'] == '2026 / Ganjil' for f in r['files']))

    r = client.post('/api/preprocess', headers=auth(admin_tok), content_type='multipart/form-data',
                    data={'file_pmb_id': str(pmb_id), 'file_akademik_id': str(akd_id), 'semester': '3',
                          'prodi': 'Teknik Mesin'})
    check('preprocessing memakai berkas tersimpan -> 200', r.status_code == 200, r.get_json())
    base_cols = r.get_json().get('columns', [])
    akd_bytes = open(akd_path, 'rb').read()

    client.patch(f'/api/files/{pmb_id}', headers=auth(bapsi_tok), json={'name': 'PMB final'})
    r = client.get(f'/api/files?folder_id={fganjil}', headers=auth(bapsi_tok)).get_json()
    check('ganti nama tanpa ekstensi -> ekstensi dipertahankan',
          any(f['name'] == 'PMB final.xlsx' for f in r['files']))
    check('pindah berkas ke folder akar -> 200',
          client.patch(f'/api/files/{akd_id}', headers=auth(bapsi_tok), json={'folder_id': None}).status_code == 200)

    check('hapus folder induk -> 200',
          client.delete(f'/api/folders/{f2026}', headers=auth(bapsi_tok)).status_code == 200)
    check('berkas di subfolder ikut terhapus',
          client.get(f'/api/files/{pmb_id}/download', headers=auth(dpa_tok)).status_code == 404)
    r = client.get('/api/files?kategori=akademik', headers=auth(bapsi_tok)).get_json()
    check('berkas yang sudah dipindah keluar tetap ada', any(f['id'] == akd_id for f in r['files']))
    check('subfolder ikut terhapus -> 404',
          client.get(f'/api/files?folder_id={fganjil}', headers=auth(bapsi_tok)).status_code == 404)


    print("\n=== 11. Format Data (pemetaan kolom berkas mentah) ===")
    check('DPA buka format data -> 403',
          client.get('/api/settings/data-format', headers=auth(dpa_tok)).status_code == 403)
    r = client.get('/api/prodi', headers=auth(dpa_tok))
    check('semua peran bisa membaca daftar prodi', r.status_code == 200 and 'Informatika' in r.get_json()['prodi'])
    r = client.get('/api/settings/data-format', headers=auth(admin_tok)).get_json()
    check('format awal = bawaan', r['customized'] is False and r['format'] == r['default'])
    fmt = r['format']

    def put_format(f):
        return client.put('/api/settings/data-format', headers=auth(admin_tok), json=f)

    import copy
    bad = copy.deepcopy(fmt)
    bad['akademik']['kolom_nim'] = '  '
    r = put_format(bad)
    check('kolom wajib kosong -> 400 + daftar error', r.status_code == 400 and r.get_json()['errors'], r.get_json())
    bad = copy.deepcopy(fmt)
    bad['pmb']['nilai_tes'].append({'sumber': 'Logika', 'fitur': 'NIM'})
    check('fitur bernama kolom sistem -> 400', put_format(bad).status_code == 400)
    bad = copy.deepcopy(fmt)
    bad['nilai']['sks_per_matkul'] = 0
    check('SKS per matkul 0 -> 400', put_format(bad).status_code == 400)

    # Simulasikan PMB mengganti nama kolom: 'Nama Sekolah' -> 'Asal Sekolah',
    # 'Nomor Mahasiswa' -> 'NIM Mahasiswa'.
    sheets = pd.read_excel(io.BytesIO(pmb_bytes), sheet_name=None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        for name, df_ in sheets.items():
            df_.rename(columns={'Nama Sekolah': 'Asal Sekolah', 'Nomor Mahasiswa': 'NIM Mahasiswa'}) \
               .to_excel(w, index=False, sheet_name=name)
    pmb_baru = buf.getvalue()

    def preprocess_upload(pmb):
        return client.post('/api/preprocess', headers=auth(admin_tok), content_type='multipart/form-data', data={
            'file_pmb': (io.BytesIO(pmb), 'pmb.xlsx'), 'file_akademik': (io.BytesIO(akd_bytes), 'akd.xlsx'),
            'semester': '3', 'prodi': 'Teknik Mesin'})

    r = preprocess_upload(pmb_baru)
    check('berkas dgn nama kolom baru ditolak format lama -> 400', r.status_code == 400, r.status_code)
    r = client.post('/api/settings/data-format/check', headers=auth(admin_tok), content_type='multipart/form-data',
                    data={'file': (io.BytesIO(pmb_baru), 'pmb.xlsx')})
    laporan = r.get_json().get('sheets', [])
    check('cek berkas menunjuk kolom yang hilang',
          any(s['jenis'] is None and 'Nama Sekolah' in s.get('kolom_wajib_tidak_ada', []) for s in laporan), laporan)

    baru = copy.deepcopy(fmt)
    baru['pmb']['penanda_biodata'] = 'Asal Sekolah'
    baru['pmb']['kolom_nim'] = 'NIM Mahasiswa'
    for m in baru['pmb']['biodata']:
        if m['sumber'] == 'Nama Sekolah':
            m['sumber'] = 'Asal Sekolah'
    baru['prodi'].append('Sistem Informasi')
    r = client.post('/api/settings/data-format/check', headers=auth(admin_tok), content_type='multipart/form-data',
                    data={'file': (io.BytesIO(pmb_baru), 'pmb.xlsx'), 'format': json.dumps(baru)})
    laporan = r.get_json().get('sheets', [])
    check('cek berkas dgn draf format -> biodata dikenali tanpa kolom hilang',
          any(s['jenis'] == 'biodata' and not s['kolom_tidak_ada'] for s in laporan), laporan)
    r = put_format(baru)
    check('simpan format baru -> 200', r.status_code == 200 and r.get_json()['customized'], r.get_json())
    r = preprocess_upload(pmb_baru)
    check('preprocessing berkas baru dgn format baru -> 200', r.status_code == 200, r.get_json())
    check('hasil preprocessing identik dgn format lama (kolom sama)',
          r.status_code == 200 and r.get_json()['columns'] == base_cols)
    check('prodi baru muncul di daftar prodi',
          'Sistem Informasi' in client.get('/api/prodi', headers=auth(dpa_tok)).get_json()['prodi'])

    r = client.delete('/api/settings/data-format', headers=auth(admin_tok)).get_json()
    check('kembalikan ke bawaan', r['customized'] is False and r['format'] == r['default'])


    print("\n=== 12. Pengguna terikat program studi ===")
    lain = next(p for p in client.get('/api/prodi', headers=auth(admin_tok)).get_json()['prodi'] if p != prodi)
    check('DPA tanpa prodi -> 400',
          new_user(nip='77777001', name='DPA X', password='Dpa#X2026', role='dpa').status_code == 400)
    check('prodi di luar daftar -> 400',
          new_user(nip='77777001', name='DPA X', password='Dpa#X2026', role='dpa', prodi='Kedokteran').status_code == 400)
    r = new_user(nip='77777001', name='DPA Prodi', password='Dpa#X2026', role='dpa', prodi=prodi)
    check('DPA dengan prodi -> 201', r.status_code == 201, r.get_json())
    r = client.post('/api/login', json={'nip': '77777001', 'password': 'Dpa#X2026'}).get_json()
    check('respons login memuat prodi', r['user']['prodi'] == prodi, r['user'])
    sp_tok = r['token']
    r = client.get('/api/prodi', headers=auth(sp_tok)).get_json()
    check('daftar prodi DPA terkunci ke prodinya', r == {'prodi': [prodi], 'locked': prodi}, r)

    r = client.post('/api/predict/berkas', headers=auth(sp_tok), json={'prodi': lain, 'angkatan': '2023'})
    check('prodi dari form diabaikan, prediksi memakai prodi akun',
          r.status_code == 200 and r.get_json()['prodi'] == prodi, r.get_json() if r.status_code != 200 else '')
    sp_batch = r.get_json().get('batch_id')
    hist = client.get('/api/history', headers=auth(sp_tok)).get_json()['batches']
    check('history hanya berisi prodi akun', hist and all(b['prodi'] == prodi for b in hist))

    sp_uid = token_serializer.loads(sp_tok)['uid']
    r = client.put(f'/api/users/{sp_uid}', headers=auth(admin_tok),
                   json={'nip': '77777001', 'name': 'DPA Prodi', 'role': 'dpa', 'prodi': lain})
    check('admin pindahkan prodi DPA -> 200', r.status_code == 200, r.get_json())
    check('batch prodi lama tidak terlihat lagi',
          client.get('/api/history', headers=auth(sp_tok)).get_json()['batches'] == []
          and client.get(f'/api/batch/{sp_batch}', headers=auth(sp_tok)).status_code == 404)
    check('berkas BAPSI tetap terlihat lintas prodi',
          client.get('/api/files', headers=auth(sp_tok)).status_code == 200)

    r = new_user(nip='77777002', name='BAPSI Dua', password='Bapsi#2026', role='bapsi', prodi=prodi)
    bapsi2 = [u for u in client.get('/api/users', headers=auth(admin_tok)).get_json() if u['nip'] == '77777002']
    check('prodi diabaikan untuk BAPSI', r.status_code == 201 and bapsi2 and bapsi2[0]['prodi'] is None)
    r = new_user(nip='77777003', name='Dekan Fakultas', password='Dekan#2026', role='dekan')
    check('dekan boleh tanpa prodi (lintas prodi)', r.status_code == 201)

    fmt_now = client.get('/api/settings/data-format', headers=auth(admin_tok)).get_json()['format']
    fmt_now['prodi'] = [p for p in fmt_now['prodi'] if p != lain]
    r = put_format(fmt_now)
    check('prodi yang masih dipakai akun tidak bisa dihapus -> 400', r.status_code == 400, r.get_json())


    print("\n=== 13. Prediksi dari Berkas Mahasiswa (setara TEST_SEM3 di cnn_tabular_2d_v2.py) ===")
    for fid in setup_ids:
        client.delete(f'/api/files/{fid}', headers=auth(bapsi_tok))
    import joblib
    import numpy as np
    from tensorflow import keras
    from sisip.ml import model_base_path

    r = client.get(f'/api/predict/sumber?prodi={prodi}', headers=auth(dpa_tok))
    check('tanpa berkas PMB di Berkas Mahasiswa -> 400 dgn penjelasan',
          r.status_code == 400 and 'PMB' in r.get_json()['error'], r.get_json())

    # BAPSI mengunggah 2 berkas CSV. PMB: satu tabel berisi biodata, nilai tes,
    # dan nilai rapor (satu baris per mahasiswa per mata pelajaran, biodata &
    # nilai tes diulang), pemisah ';' dan desimal koma. Akademik: semua prodi
    # dalam satu tabel.
    pmb_sheets = pd.read_excel(io.BytesIO(pmb_bytes), sheet_name=None)
    gabung = pmb_sheets['Sheet1'] \
        .merge(pmb_sheets['Nilai Tes'].drop(columns=['Nomor Mahasiswa']), on='Nomor Pendaftaran', how='left') \
        .merge(pmb_sheets['Nilai Rapor'].drop(columns=['Nomor Mahasiswa']), on='Nomor Pendaftaran', how='left')
    pmb_csv = gabung.to_csv(sep=';', decimal=',', index=False).encode('utf-8')
    akd_csv = pd.concat(pd.read_excel(io.BytesIO(akd_bytes), sheet_name=None).values()) \
                .to_csv(index=False).encode('utf-8')
    r1 = upload('pmb', 'PMB terbaru.csv', pmb_csv, folder=None)
    r2 = upload('akademik', 'Akademik terbaru.csv', akd_csv, folder=None)
    check('BAPSI unggah PMB & akademik berformat CSV -> 201', r1.status_code == 201 and r2.status_code == 201,
          (r1.get_json(), r2.get_json()))

    r = client.get(f'/api/predict/sumber?prodi={prodi}', headers=auth(dpa_tok))
    src = r.get_json()
    check('sumber prediksi memakai berkas terbaru',
          r.status_code == 200 and src['berkas']['pmb']['name'] == 'PMB terbaru.csv'
          and src['berkas']['akademik']['name'] == 'Akademik terbaru.csv', src)
    check('batas semester model lama diperkirakan = 3 (TRAIN_SEM3)',
          src.get('model', {}).get('max_semester') == 3 and src['model']['max_semester_source'] == 'perkiraan',
          src.get('model'))
    check('angkatan tersedia diambil dari data', '2023' in src.get('angkatan', []), src.get('angkatan'))

    r = client.post('/api/predict/berkas', headers=auth(dpa_tok), json={'prodi': prodi, 'angkatan': '2099'})
    check('angkatan tidak ada -> 400', r.status_code == 400)
    r = client.post('/api/predict/berkas', headers=auth(dpa_tok), json={'prodi': prodi, 'angkatan': '2023'})
    auto = r.get_json()
    check('prediksi dari berkas terbaru -> 200', r.status_code == 200, auto if r.status_code != 200 else '')
    check('semua fitur model terisi dari berkas', auto.get('sumber', {}).get('kecocokan_fitur') == 1.0,
          auto.get('sumber'))
    pred_auto = {x['nim']: x['prediction'] for x in auto.get('results', [])}

    # Pembanding: langkah prediksi cnn_tabular_2d_v2.py ditulis ulang apa adanya,
    # memakai encoder/scaler/model dari berkas model aktif.
    conn = sqlite3.connect(_tmp_db)
    model_path = conn.execute("SELECT file_path FROM model_registry WHERE is_active=1 AND prodi=?",
                              (prodi,)).fetchone()[0]
    conn.close()
    base = model_base_path(model_path)
    scaler = joblib.load(base + '_scaler.pkl'); encoders = joblib.load(base + '_encoders.pkl')
    le_y = joblib.load(base + '_ley.pkl'); cfg = joblib.load(base + '_config.pkl')
    model = keras.models.load_model(base + '.keras')
    from sisip.preprocessing import build_prediction_table, build_training_table
    test_df = build_prediction_table(io.BytesIO(pmb_bytes), io.BytesIO(akd_bytes), prodi=prodi,
                                     max_semester=3, angkatan='2023').df
    X_test = test_df.reindex(columns=list(scaler.feature_names_in_))
    # Tabel prediksi membiarkan nilai mata kuliah kosong; isi seperti data latih model.
    grade_cols = set(cfg.get('grade_cols', []))
    for col in encoders:
        fill = cfg.get('missing_grade', '-') if col in grade_cols else '-'
        X_test[col] = X_test[col].where(X_test[col].notna(), fill)
    for col, le in encoders.items():
        X_test[col] = X_test[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
        X_test[col] = le.transform(X_test[col])
    X_test_scaled = scaler.transform(X_test)
    pad_size = cfg['height'] * cfg['width'] - X_test_scaled.shape[1]
    X_test_padded = np.pad(X_test_scaled, ((0, 0), (0, pad_size)), mode="constant")
    X_test_reshaped = X_test_padded.reshape(-1, cfg['height'], cfg['width'], 1)
    y_pred = (model.predict(X_test_reshaped, verbose=0) > 0.5).astype(int).flatten()
    pred_notebook = dict(zip(test_df['NIM'].astype(str), le_y.inverse_transform(y_pred)))
    check('jumlah mahasiswa dari CSV = dari Excel BAPSI asli', len(pred_notebook) == len(pred_auto))
    check('hasil prediksi = langkah notebook (per NIM)',
          pred_auto == {k: str(v) for k, v in pred_notebook.items()},
          sum(pred_auto.get(k) != str(v) for k, v in pred_notebook.items()))

    print("\n=== 14. Dua CSV -> Preprocessing -> data latih -> training ===")
    r = client.post('/api/preprocess', headers=auth(admin_tok), content_type='multipart/form-data', data={
        'prodi': prodi, 'semester': '3',
        'file_pmb': (io.BytesIO(pmb_csv), 'pmb.csv'), 'file_akademik': (io.BytesIO(akd_csv), 'akd.csv')})
    pre = r.get_json()
    check('preprocessing 2 CSV -> data latih TRAIN_SEM3', r.status_code == 200 and pre['sheet'] == 'TRAIN_SEM3', pre)
    xl = build_training_table(io.BytesIO(pmb_bytes), io.BytesIO(akd_bytes), prodi=prodi, max_semester=3)
    check('data latih dari CSV = dari Excel (kolom & jumlah mahasiswa)',
          pre.get('columns') == list(xl.df.columns) and pre['report']['mahasiswa'] == len(xl.df))
    latih = client.get(pre['download_url'], headers=auth(admin_tok)).data
    r = client.post('/api/train', headers=auth(admin_tok), content_type='multipart/form-data', data={
        'file': (io.BytesIO(latih), 'data_latih.xlsx'), 'prodi': prodi, 'epochs': '2'})
    check('data latih hasil preprocessing langsung bisa dilatih -> 200', r.status_code == 200, r.get_json())
    conn = sqlite3.connect(_tmp_db)
    smt = conn.execute("SELECT max_semester, max_semester_source FROM model_registry ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    check('model baru mencatat batas semester data latih (3)', smt == (3, 'training'), smt)

    df_latih = pd.read_excel(io.BytesIO(latih), sheet_name='TRAIN_SEM3')
    semua_angkatan = sorted({norm_str(a) for a in df_latih['Angkatan'].dropna()})
    model_baru = client.get('/api/models?page=1', headers=auth(admin_tok)).get_json()['items'][0]
    check('tanpa filter: angkatan model = semua angkatan di berkas',
          model_baru['angkatan'] == ', '.join(semua_angkatan), (model_baru['angkatan'], semua_angkatan))
    r = client.post('/api/train', headers=auth(admin_tok), content_type='multipart/form-data', data={
        'file': (io.BytesIO(latih), 'data_latih.xlsx'), 'prodi': prodi, 'epochs': '2',
        'angkatan': f' {semua_angkatan[0]}.0 , 1999'})
    check('dengan filter: angkatan dicatat dari data yang tersisa (bukan isian form)',
          r.status_code == 200 and r.get_json()['metrics']['angkatan'] == semua_angkatan[0], r.get_json())

    r = client.post('/api/predict/berkas', headers=auth(admin_tok), json={'prodi': 'Matematika', 'angkatan': '2023'})
    check('model yang fiturnya tidak cocok ditolak, bukan diprediksi diam-diam',
          r.status_code == 400 and 'tidak cocok' in r.get_json()['error'], r.get_json())


try:
    run()
finally:
    shutil.rmtree(_tmpdir, ignore_errors=True)

print(f"\n{'='*48}\n  {_passed} passed, {_failed} failed\n{'='*48}")
sys.exit(1 if _failed else 0)
