"""Arsitektur CNN tabular 2D dan registri berkas model di disk."""
import os
import random

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from .config import MODEL_DIR
from .db import connect

tf.config.threading.set_inter_op_parallelism_threads(1)
tf.config.threading.set_intra_op_parallelism_threads(1)
random.seed(42)
np.random.seed(42)
tf.random.set_seed(42)

# Satu model terdiri dari berkas .keras plus artefak praproses pendampingnya.
MODEL_ARTIFACT_SUFFIXES = ('.keras', '_scaler.pkl', '_encoders.pkl', '_ley.pkl', '_config.pkl')


def model_base_path(stored_path):
    """Path model tanpa akhiran .keras, sudah di-resolve ke MODEL_DIR."""
    path = resolve_model_path(stored_path)
    return path[:-len('.keras')] if path.endswith('.keras') else path


def missing_artifacts(base_path):
    return [os.path.basename(base_path + s) for s in MODEL_ARTIFACT_SUFFIXES
            if not os.path.exists(base_path + s)]


def resolve_model_path(stored_path):
    """Resolve a model file path stored in the registry, tolerating rows that
    were written with a relative 'saved_models/...' prefix before MODEL_DIR
    became configurable."""
    if os.path.isabs(stored_path) and os.path.exists(stored_path):
        return stored_path
    if os.path.exists(stored_path):
        return stored_path
    return os.path.join(MODEL_DIR, os.path.basename(stored_path))

MIN_GRID_SIDE = 4


def find_grid_dimensions(n):
    """Bentuk grid 2D untuk n fitur, sisi minimal MIN_GRID_SIDE.

    Faktorisasi pas saja tidak cukup: bila n bilangan prima (mis. 157 fitur),
    satu-satunya faktor adalah 1 x n sehingga tinggi grid = 1, lalu MaxPooling
    kedua menghasilkan dimensi 0 dan pelatihan gagal dengan ValueError. Kalau
    tidak ada faktorisasi yang memenuhi syarat, pakai grid mendekati persegi dan
    biarkan sisanya di-padding nol (pad_size sudah disimpan di config)."""
    best = None
    for i in range(1, int(np.sqrt(n)) + 1):
        if n % i == 0 and i >= MIN_GRID_SIDE and (n // i) >= MIN_GRID_SIDE:
            best = (i, n // i)
    if best:
        return best
    height = max(MIN_GRID_SIDE, int(np.floor(np.sqrt(n))))
    width = max(MIN_GRID_SIDE, int(np.ceil(n / height)))
    return (height, width)

def build_cnn_model(input_shape, n_classes, dropout_rate=0.3):
    model = keras.Sequential([
        layers.Conv2D(8, (3, 3), activation="relu", input_shape=input_shape, padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(dropout_rate),

        layers.Conv2D(16, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(dropout_rate),

        layers.Flatten(),
        layers.Dense(64, activation="relu"),
        layers.BatchNormalization(),
        layers.Dropout(dropout_rate),

        layers.Dense(32, activation="relu"),
        layers.Dropout(dropout_rate - 0.1 if dropout_rate >= 0.1 else 0),

        layers.Dense(
            n_classes if n_classes > 2 else 1,
            activation="softmax" if n_classes > 2 else "sigmoid"
        ),
    ])
    return model

def active_model_info(prodi=None):
    """(base_path, prodi_yang_sebenarnya) dari model aktif, atau (None, None)."""
    try:
        conn = connect()
        c = conn.cursor()
        if prodi:
            c.execute("SELECT file_path, prodi FROM model_registry WHERE is_active = 1 AND prodi = ? LIMIT 1", (prodi,))
        else:
            c.execute("SELECT file_path, prodi FROM model_registry WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
    except Exception:
        return None, None
    if not row:
        return None, None
    path, prodi_db = row
    base = resolve_model_path(path)[:-len('.keras')] if path.endswith('.keras') else resolve_model_path(path)
    return base, prodi_db
