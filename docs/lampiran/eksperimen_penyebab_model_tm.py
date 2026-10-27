"""Jalankan: cd backend && venv/bin/python ../docs/lampiran/eksperimen_penyebab_model_tm.py ..

Eksperimen sebab-akibat untuk model Teknik Mesin: latih ulang dengan langkah
yang sama persis seperti backend/sisip/routes/training.py (baris 82-167), lalu
ubah SATU faktor per varian dan ukur recall kelas SISIP pada angkatan 2023
(tidak pernah dipakai latih). Tidak menyimpan model dan tidak menyentuh database.
"""
import os
import sys

os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import tensorflow as tf  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import LabelEncoder, StandardScaler  # noqa: E402
from sklearn.utils.class_weight import compute_class_weight  # noqa: E402
from tensorflow import keras  # noqa: E402

REPO = sys.argv[1]
sys.path.insert(0, os.path.join(REPO, 'backend'))
from sisip.constants import LABEL_COL, non_feature_columns  # noqa: E402
from sisip.ml import build_cnn_model, find_grid_dimensions  # noqa: E402
from sisip.preprocessing import build_training_table  # noqa: E402
from sisip.settings_store import current_format  # noqa: E402

NIM = '07818674325d3846cddaaa578e566544'
FITUR_RAPOR = ['IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']

tabel = build_training_table(os.path.join(REPO, '20260605_Data_PMB.xlsx'),
                             os.path.join(REPO, 'Data_akademik_te_tm_mat.xlsx'),
                             prodi='Teknik Mesin', max_semester=3, fmt=current_format()).df
tabel['Angkatan'] = tabel['Angkatan'].astype(str)
uji = tabel[tabel['Angkatan'] == '2023'].reset_index(drop=True)


def latih_dan_uji(angkatan, epochs, patience, shuffle, pakai_ipk, seed):
    keras.utils.set_random_seed(seed)
    df = tabel[tabel['Angkatan'].isin(angkatan)].copy()
    buang = [c for c in non_feature_columns(df.columns) if not (pakai_ipk and c in FITUR_RAPOR)]
    df = df.drop(columns=buang)                                      # training.py:82
    X, y = df.drop(columns=[LABEL_COL]), df[LABEL_COL]               # training.py:88-89
    encoders = {}
    for col in X.columns:                                            # training.py:92-96
        if not pd.api.types.is_numeric_dtype(X[col]) or X[col].dtype == 'object':
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            encoders[col] = le
    X = X.fillna(0)
    le_y = LabelEncoder()
    y_enc = le_y.fit_transform(y)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    Xtr, Xva, ytr, yva = train_test_split(Xs, y_enc, test_size=0.2, random_state=42, stratify=y_enc)
    h, w = find_grid_dimensions(Xs.shape[1])
    pad = h * w - Xs.shape[1]
    shape = lambda a: np.pad(a, ((0, 0), (0, pad))).reshape(-1, h, w, 1)
    model = build_cnn_model((h, w, 1), 2, dropout_rate=0.3)
    model.compile(optimizer=keras.optimizers.Adam(0.001), loss='binary_crossentropy', metrics=['accuracy'])
    cw = compute_class_weight('balanced', classes=np.unique(ytr), y=ytr)
    model.fit(shape(Xtr), ytr, validation_data=(shape(Xva), yva), class_weight=dict(enumerate(cw)),
              batch_size=32, epochs=epochs, shuffle=shuffle, verbose=0,
              callbacks=[keras.callbacks.EarlyStopping(monitor='val_loss', patience=patience,
                                                       restore_best_weights=True)])

    # Prediksi angkatan 2023 seperti predictor.py:115-137 (kategori asing -> classes_[0]).
    Xt = uji[X.columns].copy()
    for col, le in encoders.items():
        Xt[col] = le.transform(Xt[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0]))
    Xt = Xt.apply(pd.to_numeric, errors='coerce').fillna(0)
    p = model.predict(shape(scaler.transform(Xt)), verbose=0).ravel()
    pred = le_y.inverse_transform((p > 0.5).astype(int))
    asli = uji[LABEL_COL].values
    sisip = asli == 'SISIP'
    i = uji.index[uji['NIM'].astype(str) == NIM][0]
    return (pred[sisip] == 'SISIP').mean(), (pred == asli).mean(), pred[i], p[i]


VARIAN = [
    ('A  Replika model aktif: angkatan 2021, epochs 10, patience 5, shuffle False, tanpa IPK',
     dict(angkatan=['2021'], epochs=10, patience=5, shuffle=False, pakai_ipk=False)),
    ('B  A + data latih 2020-2022', dict(angkatan=['2020', '2021', '2022'], epochs=10, patience=5, shuffle=False, pakai_ipk=False)),
    ('B1 B + epochs 100, patience 10 (shuffle tetap False)',
     dict(angkatan=['2020', '2021', '2022'], epochs=100, patience=10, shuffle=False, pakai_ipk=False)),
    ('B2 B + shuffle True (epochs tetap 10, patience 5)',
     dict(angkatan=['2020', '2021', '2022'], epochs=10, patience=5, shuffle=True, pakai_ipk=False)),
    ('A1 A + epochs 100, patience 10, shuffle True (data tetap 2021 saja)',
     dict(angkatan=['2021'], epochs=100, patience=10, shuffle=True, pakai_ipk=False)),
    ('C  B + epochs 100, patience 10, shuffle True (= skrip acuan)',
     dict(angkatan=['2020', '2021', '2022'], epochs=100, patience=10, shuffle=True, pakai_ipk=False)),
    ('D  C + IPK 1-3 & Total SKS 3 sebagai fitur',
     dict(angkatan=['2020', '2021', '2022'], epochs=100, patience=10, shuffle=True, pakai_ipk=True)),
]

print(f'Data uji: angkatan 2023, {len(uji)} mhs, {int((uji[LABEL_COL] == "SISIP").sum())} sisip\n')
print(f'{"Varian":<92} {"Recall SISIP":>13} {"Akurasi":>8}  NIM kasus')
for nama, cfg in VARIAN:
    hasil = [latih_dan_uji(seed=s, **cfg) for s in (1, 2, 3)]
    rec = np.mean([h[0] for h in hasil])
    acc = np.mean([h[1] for h in hasil])
    nim = ', '.join(f'{h[2]} ({h[3]:.2f})' for h in hasil)
    print(f'{nama:<92} {rec:>12.0%} {acc:>8.0%}  {nim}')
