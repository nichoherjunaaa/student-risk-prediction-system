"""Jalankan: cd backend && venv/bin/python ../docs/lampiran/verifikasi_model_tm.py ..

Bukti bahwa prediksi TIDAK SISIP untuk NIM 07818674325d3846cddaaa578e566544
berasal dari model, bukan dari kesalahan sistem.

Bagian A-B memakai kode sistem hanya untuk MENGAMBIL baris input yang dipakai
sistem; semua pemeriksaan dihitung ulang secara independen dari berkas mentah
dan artefak model (keras + joblib + numpy), tanpa memanggil kode prediksi sistem.
"""
import glob
import json
import os
import sqlite3
import sys

import joblib
import numpy as np
import pandas as pd

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
from tensorflow import keras  # noqa: E402

REPO = sys.argv[1]
BACKEND = os.path.join(REPO, 'backend')
NIM = '07818674325d3846cddaaa578e566544'
PMB = os.path.join(REPO, '20260605_Data_PMB.xlsx')
AKD = os.path.join(REPO, 'Data_akademik_te_tm_mat.xlsx')
BASE = os.path.join(BACKEND, 'saved_models', 'Model_2DCNN_teknik_mesin_20260908_104752')

sys.path.insert(0, BACKEND)
from sisip.preprocessing import build_prediction_table  # noqa: E402
from sisip.settings_store import current_format  # noqa: E402

line = lambda t: print('\n' + '=' * 78 + '\n' + t + '\n' + '=' * 78)

# --- artefak model, dimuat langsung -----------------------------------------
model = keras.models.load_model(BASE + '.keras')
scaler = joblib.load(BASE + '_scaler.pkl')
encoders = joblib.load(BASE + '_encoders.pkl')
le_y = joblib.load(BASE + '_ley.pkl')
cfg = joblib.load(BASE + '_config.pkl')
FEATS = list(scaler.feature_names_in_)


def infer(rows):
    """Langkah cnn_tabular_2d_v2.py apa adanya: encode -> scale -> pad -> reshape -> predict."""
    X = rows[FEATS].copy()
    for col, le in encoders.items():
        X[col] = X[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
        X[col] = le.transform(X[col])
    X = X.apply(pd.to_numeric, errors='coerce').fillna(0)
    Xs = scaler.transform(X)
    if cfg['pad_size'] > 0:
        Xs = np.pad(Xs, ((0, 0), (0, cfg['pad_size'])), mode='constant')
    p = model.predict(Xs.reshape(-1, cfg['height'], cfg['width'], 1), verbose=0).ravel()
    return p, le_y.inverse_transform((p > 0.5).astype(int))


# --- tabel input yang dipakai sistem (angkatan 2023, s.d. semester 3) --------
fmt = current_format()
tabel = build_prediction_table(PMB, AKD, prodi='Teknik Mesin', max_semester=3, angkatan='2023', fmt=fmt).df
tabel['NIM'] = tabel['NIM'].astype(str)
row = tabel[tabel['NIM'] == NIM].reset_index(drop=True)

raw = pd.concat(pd.read_excel(AKD, sheet_name=None).values(), ignore_index=True)
raw['NIM'] = raw['NIM'].astype(str)
mhs = raw[raw['NIM'] == NIM]

# =============================================================================
line('BUKTI 1. Label asli mahasiswa di berkas akademik (kunci jawaban)')
print('Label:', mhs['Sisip Program'].dropna().unique().tolist())
print(mhs[['Semester', 'IPS', 'IPK Per Semester', 'SKS Lulus Per Semester']]
      .drop_duplicates().sort_values('Semester').to_string(index=False))

# =============================================================================
line('BUKTI 2. Input ke model = data mentah (nilai mata kuliah s.d. semester 3)')
lingkup = mhs[pd.to_numeric(mhs['Semester'], errors='coerce') <= 3].copy()
# Sama seperti sistem: nama mata kuliah di berkas mentah kadang berspasi di akhir
# ('Pendidikan Agama '), dan nilai kosong (mata kuliah 0 SKS) berarti tanpa nilai.
lingkup['Nama Mtk'] = lingkup['Nama Mtk'].astype(str).str.strip()
lingkup = lingkup[lingkup['Nilai'].notna()]
lingkup['Nilai'] = lingkup['Nilai'].astype(str).str.strip().str.upper()
rank = fmt.grade_rank
terbaik = (lingkup.assign(r=lingkup['Nilai'].map(rank))
                  .sort_values('r', na_position='first')
                  .groupby('Nama Mtk')['Nilai'].last())
matkul_fitur = [f for f in FEATS if f in set(raw['Nama Mtk'].astype(str).str.strip())]
cocok = beda = 0
for f in matkul_fitur:
    harap = terbaik.get(f, '-')
    dapat = str(row.at[0, f]) if f in row.columns else '-'
    if dapat in ('nan', 'None'):
        dapat = '-'
    if harap == dapat:
        cocok += 1
    else:
        beda += 1
        print(f'  BEDA {f}: mentah={harap} sistem={dapat}')
print(f'Fitur mata kuliah: {len(matkul_fitur)} | cocok dengan berkas mentah: {cocok} | beda: {beda}')
contoh = [f for f in matkul_fitur if f in terbaik.index][:8]
print('Contoh (mentah = sistem):', {f: f'{terbaik[f]} = {row.at[0, f]}' for f in contoh})

# =============================================================================
line('BUKTI 3. Model tidak punya fitur IPK / SKS sama sekali')
ipk_sks = [f for f in FEATS if f.upper().startswith(('IPK', 'IPS', 'TOTAL SKS', 'SKS'))]
print(f'Jumlah fitur model: {len(FEATS)} | fitur IPK/SKS: {ipk_sks or "TIDAK ADA"}')
print(f'Fitur mata kuliah: {len(matkul_fitur)} | fitur lain (PMB/tes/rapor): {len(FEATS) - len(matkul_fitur)}')
print('Sama dengan skrip acuan cnn_tabular_2d_v2.py baris 42 & 61:')
print("  train_df.drop(['NIM','Nomor PMB','Angkatan','IPK 1','IPK 2','IPK 3','Total SKS 3'], axis=1)")
print(f'Ukuran data latih model (scaler.n_samples_seen_): {int(scaler.n_samples_seen_)} mahasiswa')

# =============================================================================
line('BUKTI 4. Inferensi independen (tanpa kode prediksi sistem) = hasil sistem')
p, lbl = infer(row)
print(f'Output sigmoid model: {p[0]:.4f}  (kelas 1 = {le_y.classes_[1]}, ambang 0.5) -> {lbl[0]}')
conn = sqlite3.connect(os.path.join(BACKEND, 'sisip_database.db'))
tersimpan = dict(conn.execute('SELECT nim, prediction FROM predictions WHERE batch_id = 124').fetchall())
print(f'Hasil tersimpan sistem (batch 124) untuk NIM ini: {tersimpan.get(NIM)}')
p_all, lbl_all = infer(tabel)
sama = sum(tersimpan.get(n) == l for n, l in zip(tabel['NIM'], lbl_all))
print(f'Seluruh batch 124: {sama}/{len(tabel)} prediksi independen identik dengan yang disimpan sistem')

# =============================================================================
line('BUKTI 5. Uji kontrafaktual: bagaimana model bereaksi bila nilai diubah')
for nama, nilai in [('semua mata kuliah = E', 'E'), ('semua mata kuliah = A', 'A')]:
    alt = row.copy()
    for f in matkul_fitur:
        alt.at[0, f] = nilai
    print(f'  {nama:<26} -> output {infer(alt)[0][0]:.4f} -> {infer(alt)[1][0]}')
print('  (IPK tidak bisa diuji: bukan input model, mengubahnya tidak berpengaruh apa pun.)')

# =============================================================================
line('BUKTI 6. Kinerja model terhadap label asli (semua angkatan berlabel)')
semua = []
for ang in ['2020', '2021', '2022', '2023']:
    try:
        t = build_prediction_table(PMB, AKD, prodi='Teknik Mesin', max_semester=3, angkatan=ang, fmt=fmt).df
    except Exception as e:  # angkatan tanpa data
        print(ang, 'dilewati:', e)
        continue
    t['NIM'] = t['NIM'].astype(str)
    pr, lb = infer(t)
    lab = raw.dropna(subset=['Sisip Program']).groupby('NIM')['Sisip Program'].first()
    asli = t['NIM'].map(lab).map(lambda s: None if pd.isna(s) else ('SISIP' if str(s).startswith('Sisip') else 'TIDAK SISIP'))
    df = pd.DataFrame({'angkatan': ang, 'asli': asli, 'pred': lb, 'ipk3': t.get('IPK 3')}).dropna(subset=['asli'])
    semua.append(df)
semua = pd.concat(semua, ignore_index=True)
for ang, g in semua.groupby('angkatan'):
    s = g[g.asli == 'SISIP']
    print(f'  Angkatan {ang}: {len(g):3d} mhs, sisip asli {len(s):2d}, tertangkap model {int((s.pred == "SISIP").sum()):2d}')
s = semua[semua.asli == 'SISIP']
print(f'  TOTAL: recall kelas SISIP = {int((s.pred == "SISIP").sum())}/{len(s)} '
      f'({(s.pred == "SISIP").mean():.0%}), akurasi keseluruhan = {(semua.asli == semua.pred).mean():.0%}')
print('\nTabel silang (baris = label asli, kolom = prediksi model):')
print(pd.crosstab(semua.asli, semua.pred).to_string())
