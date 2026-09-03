"""Verifikasi menyeluruh fitur utama: TRAINING -> REGISTRI -> AKTIVASI -> PREDIKSI.

Membuktikan bahwa model machine learning benar-benar terpakai (bukan aturan
if-else tersembunyi) dan bahwa pipeline pelatihan sama persis dengan pipeline
prediksi, dengan cara:

  1. memecah TRAIN_SEM3 (604 baris berlabel) menjadi 80% latih / 20% uji tahan,
  2. melatih model baru lewat POST /api/train (bukan memanggil Keras langsung),
  3. mengaktifkannya lewat POST /api/models/<id>/activate,
  4. memprediksi 20% data tahan lewat POST /api/predict,
  5. membandingkan hasil prediksi dengan label sebenarnya.

Semua dikerjakan di database + folder model sementara; data asli tidak tersentuh.

    cd backend && venv/bin/python verify_model_integration.py
"""
import io
import os
import sys
import json
import shutil
import sqlite3
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, '..', 'DATA MAHASISWA 20-24.xlsx')

_tmp = tempfile.mkdtemp(prefix='sisip-verify-')
os.environ['SISIP_DB_FILE'] = os.path.join(_tmp, 'verify.db')
os.environ['SISIP_MODEL_DIR'] = os.path.join(_tmp, 'models')
os.environ['SISIP_SECRET_KEY'] = 'verify-secret'
os.environ['SISIP_SEED_DEMO_USERS'] = '1'
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
os.makedirs(os.environ['SISIP_MODEL_DIR'], exist_ok=True)
os.chdir(HERE)

import numpy as np                      # noqa: E402
import pandas as pd                     # noqa: E402
import joblib                           # noqa: E402
import app as A                         # noqa: E402

client = A.app.test_client()
PRODI = 'Informatika'


def sheet_bytes(df, name):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, index=False, sheet_name=name)
    buf.seek(0)
    return buf


def main():
    token = client.post('/api/login', json={'email': 'admin@gmail.com',
                                            'password': 'admin123'}).get_json()['token']
    H = {'Authorization': f'Bearer {token}'}

    print("=" * 74)
    print(" 1. SIAPKAN DATA: pecah TRAIN_SEM3 jadi 80% latih / 20% uji tahan")
    print("=" * 74)
    full = pd.read_excel(pd.ExcelFile(DATASET), sheet_name='TRAIN_SEM3')
    rng = np.random.RandomState(7)
    hold_idx = []
    for label, grp in full.groupby('Label'):           # stratified split
        n = max(1, int(round(len(grp) * 0.2)))
        hold_idx += list(rng.choice(grp.index, size=n, replace=False))
    holdout = full.loc[sorted(hold_idx)].copy()
    trainset = full.drop(index=hold_idx).copy()
    truth = holdout['Label'].astype(str).str.strip().str.upper().tolist()
    holdout_nolabel = holdout.drop(columns=['Label'])
    print(f"   latih  : {len(trainset):4d} baris  {dict(trainset['Label'].value_counts())}")
    print(f"   tahan  : {len(holdout):4d} baris  {dict(holdout['Label'].value_counts())}")

    print("\n" + "=" * 74)
    print(" 2. TRAINING lewat POST /api/train")
    print("=" * 74)
    r = client.post('/api/train', headers=H, content_type='multipart/form-data', data={
        'file': (sheet_bytes(trainset, 'TRAIN_SEM3'), 'train.xlsx'),
        'prodi': PRODI, 'angkatan': '', 'epochs': '30', 'batch_size': '32',
        'learning_rate': '0.001', 'dropout_rate': '0.3', 'val_split': '0.2',
    })
    assert r.status_code == 200, r.data[:400]
    metrics = r.get_json().get('metrics', {})
    print(f"   status  : 200  akurasi_val={metrics.get('accuracy'):.4f}  loss_val={metrics.get('loss'):.4f}")

    conn = sqlite3.connect(os.environ['SISIP_DB_FILE'])
    mid, vname, macc = conn.execute(
        "SELECT id, version_name, accuracy FROM model_registry ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    print(f"   registri: id={mid}  {vname}  accuracy={macc:.4f}")

    base = os.path.join(os.environ['SISIP_MODEL_DIR'], vname)
    for suffix in ['.keras', '_scaler.pkl', '_encoders.pkl', '_ley.pkl', '_config.pkl']:
        assert os.path.exists(base + suffix), f"artefak hilang: {suffix}"
    print("   artefak : .keras + scaler/encoders/ley/config  -> lengkap")

    scaler = joblib.load(base + '_scaler.pkl')
    cfg = joblib.load(base + '_config.pkl')
    ley = joblib.load(base + '_ley.pkl')
    feats = [str(c) for c in scaler.feature_names_in_]
    print(f"   fitur   : {len(feats)}  grid CNN {cfg['height']}x{cfg['width']} "
          f"(pad {cfg['pad_size']})  kelas={list(ley.classes_)}")

    print("\n" + "=" * 74)
    print(" 3. AKTIVASI lewat POST /api/models/<id>/activate")
    print("=" * 74)
    r = client.post(f'/api/models/{mid}/activate', headers=H)
    assert r.status_code == 200, r.data[:300]
    conn = sqlite3.connect(os.environ['SISIP_DB_FILE'])
    act = conn.execute("SELECT version_name FROM model_registry WHERE is_active=1 AND prodi=?",
                       (PRODI,)).fetchone()
    conn.close()
    print(f"   aktif   : {act[0]}  (== model baru: {act[0] == vname})")

    print("\n" + "=" * 74)
    print(" 4. PREDIKSI 20% data tahan lewat POST /api/predict")
    print("=" * 74)
    r = client.post('/api/predict', headers=H, content_type='multipart/form-data', data={
        'file': (sheet_bytes(holdout_nolabel, 'TEST_SEM3'), 'hold.xlsx'),
        'prodi': PRODI, 'angkatan': '', 'semester': '3',
    })
    assert r.status_code == 200, r.data[:400]
    body = r.get_json()
    preds = [str(x['prediction']).strip().upper() for x in body['results']]
    print(f"   status  : 200  total={body['total']}  SISIP={body['atRisk']}  TIDAK SISIP={body['safe']}")
    assert len(preds) == len(truth), f"jumlah hasil {len(preds)} != {len(truth)}"

    print("\n" + "=" * 74)
    print(" 5. HASIL vs LABEL SEBENARNYA (data yang belum pernah dilihat model)")
    print("=" * 74)
    tp = sum(1 for p, t in zip(preds, truth) if p == 'SISIP' and t == 'SISIP')
    fn = sum(1 for p, t in zip(preds, truth) if p != 'SISIP' and t == 'SISIP')
    fp = sum(1 for p, t in zip(preds, truth) if p == 'SISIP' and t != 'SISIP')
    tn = sum(1 for p, t in zip(preds, truth) if p != 'SISIP' and t != 'SISIP')
    acc = (tp + tn) / len(truth)
    recall = tp / (tp + fn) if (tp + fn) else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    print(f"   Akurasi                      : {acc:.4f}  ({tp + tn}/{len(truth)})")
    print(f"   SISIP terdeteksi (recall)    : {recall:.4f}  ({tp}/{tp + fn})")
    print(f"   Ketepatan tuduhan (precision): {prec:.4f}  ({tp}/{tp + fp if tp + fp else 0})")
    print(f"   Matriks: TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    baseline = max(truth.count('SISIP'), truth.count('TIDAK SISIP')) / len(truth)
    print(f"   Baseline tebak-kelas-mayoritas: {baseline:.4f}")
    print(f"   -> model {'MENGUNGGULI' if acc > baseline else 'TIDAK mengungguli'} tebakan buta")

    print("\n" + "=" * 74)
    print(" 6. FITUR MANA YANG DIPAKAI MODEL")
    print("=" * 74)
    for c in ['IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3', 'NIM', 'Nama', 'Prodi', 'Semester', 'Angkatan']:
        print(f"   {c:14s} -> {'DIPAKAI' if c in feats else 'TIDAK dipakai (hanya untuk laporan)'}")

    enc = joblib.load(base + '_encoders.pkl')
    konstan = [c for c in feats if c in enc and len(enc[c].classes_) == 1]
    print(f"\n   Fitur kategorikal dengan 1 nilai saja (nol informasi): {len(konstan)} dari {len(feats)}")

    print("\n" + "=" * 74)
    print(" 7. SENSITIVITAS: apa yang benar-benar menggerakkan hasil?")
    print("=" * 74)
    from tensorflow import keras
    model = keras.models.load_model(base + '.keras')

    def prob(df):
        d = df.reindex(columns=feats).copy()
        for c in enc:
            if c in d.columns:
                known = set(str(x) for x in enc[c].classes_)
                d[c] = d[c].astype(str).map(lambda s: s if s in known else str(enc[c].classes_[0]))
                d[c] = enc[c].transform(d[c])
        for c in d.columns:
            if not pd.api.types.is_numeric_dtype(d[c]):
                d[c] = pd.to_numeric(d[c], errors='coerce')
        X = scaler.transform(d.fillna(0))
        if cfg['pad_size'] > 0:
            X = np.pad(X, ((0, 0), (0, cfg['pad_size'])), mode='constant')
        return float(model.predict(X.reshape(-1, cfg['height'], cfg['width'], 1), verbose=0).flatten()[0])

    row = holdout_nolabel.iloc[[0]].copy()
    multi = [c for c in feats if c in enc and len(enc[c].classes_) > 1
             and set(str(x) for x in enc[c].classes_) <= {'A', 'A-', 'B', 'B+', 'B-', 'C', 'C+',
                                                          'C-', 'D', 'D+', 'D-', 'E', 'F', 'T', 'nan'}]
    skenario = []
    for nama, ipk, sks in [("IPK 2.14/1.88/2.25, SKS 30", [2.14, 1.88, 2.25], 30),
                           ("IPK 2.15/1.75/2.00, SKS 20", [2.15, 1.75, 2.00], 20),
                           ("IPK 4.00/4.00/4.00, SKS 144", [4.0, 4.0, 4.0], 144)]:
        v = row.copy()
        for col, val in zip(['IPK 1', 'IPK 2', 'IPK 3'], ipk):
            if col in v.columns:
                v[col] = val
        if 'Total SKS 3' in v.columns:
            v['Total SKS 3'] = sks
        skenario.append((nama, v))
    worst = row.copy()
    for c in multi:
        worst[c] = 'E'
    skenario.append((f"semua {len(multi)} nilai matkul -> E", worst))
    best = row.copy()
    for c in multi:
        best[c] = 'A'
    skenario.append((f"semua {len(multi)} nilai matkul -> A", best))

    print(f"   {'SKENARIO (baris yang sama persis)':44s} {'P(TIDAK SISIP)':>15s}  HASIL")
    print("   " + "-" * 70)
    for nama, v in skenario:
        p = prob(v)
        print(f"   {nama:44s} {p:15.6f}  {ley.classes_[int(p > 0.5)]}")


try:
    main()
    print("\nSEMUA TAHAP TERINTEGRASI DAN BERJALAN.")
    code = 0
except AssertionError as e:
    print(f"\nGAGAL: {e}")
    code = 1
finally:
    shutil.rmtree(_tmp, ignore_errors=True)
sys.exit(code)
