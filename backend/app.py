import os
import io
import json
import sqlite3
import datetime
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.utils import to_categorical

app = Flask(__name__)
CORS(app)

DB_FILE = 'sisip_database.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_name TEXT,
            date_uploaded TEXT,
            total_records INTEGER,
            at_risk INTEGER,
            safe INTEGER,
            status TEXT,
            prodi TEXT,
            angkatan TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            nim TEXT,
            pmb TEXT,
            prediction TEXT,
            is_risk BOOLEAN,
            FOREIGN KEY(batch_id) REFERENCES batches(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Global states (In a production system, model & scalers should also be saved to disk)
global_model = None
global_encoders = {}
global_le_y = None
global_scaler = None
global_config = {}

def find_grid_dimensions(n):
    factors = []
    for i in range(1, int(np.sqrt(n)) + 1):
        if n % i == 0:
            factors.append((i, n // i))
    return factors[-1] if factors else (int(np.sqrt(n)), int(np.ceil(n / np.sqrt(n))))

def build_cnn_model(input_shape, n_classes):
    model = keras.Sequential([
        layers.Conv2D(8, (3, 3), activation="relu", input_shape=input_shape, padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.3),

        layers.Conv2D(16, (3, 3), activation="relu", padding="same"),
        layers.BatchNormalization(),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.3),

        layers.Flatten(),
        layers.Dense(64, activation="relu"),
        layers.BatchNormalization(),
        layers.Dropout(0.3),

        layers.Dense(32, activation="relu"),
        layers.Dropout(0.2),

        layers.Dense(
            n_classes if n_classes > 2 else 1,
            activation="softmax" if n_classes > 2 else "sigmoid"
        ),
    ])
    return model

@app.route('/api/preview', methods=['POST'])
def preview_data():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    sheet_param = request.form.get('sheet', None)
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')
    
    try:
        excel_file = pd.ExcelFile(file)
        if sheet_param and sheet_param in excel_file.sheet_names:
            sheet_to_read = sheet_param
        else:
            sheet_to_read = excel_file.sheet_names[0]
            
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Angkatan and Prodi if columns exist
        if 'Angkatan' in df.columns and angkatan != 'Unknown':
            df = df[df['Angkatan'].astype(str) == str(angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
            
        # Convert first 10 rows to dict for preview
        preview_data = df.head(10).replace({np.nan: None}).to_dict(orient='records')
        columns = df.columns.tolist()
        return jsonify({
            'columns': columns,
            'data': preview_data,
            'total_rows': len(df)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/train', methods=['POST'])
def train_model():
    global global_model, global_encoders, global_le_y, global_scaler, global_config
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')
    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = 'TRAIN_SEM3' if 'TRAIN_SEM3' in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Prodi if columns exist
        if 'Prodi' in df.columns and prodi != 'Unknown':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
            
        if len(df) == 0:
            return jsonify({'error': f"Tidak ada data latih (TRAIN) untuk Prodi {prodi}."}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
    df = df.drop(columns=[col for col in drop_cols if col in df.columns])

    target_col = "Label"
    if target_col not in df.columns:
        return jsonify({'error': f'Target column {target_col} not found'}), 400

    X = df.drop(columns=[target_col])
    y = df[target_col]

    global_encoders = {}
    for col in X.columns:
        if not pd.api.types.is_numeric_dtype(X[col]) or X[col].dtype == "object":
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            global_encoders[col] = le

    X = X.fillna(0)

    global_le_y = LabelEncoder()
    y_encoded = global_le_y.fit_transform(y)
    n_classes = len(np.unique(y_encoded))

    global_scaler = StandardScaler()
    X_scaled = global_scaler.fit_transform(X)

    n_features = X_scaled.shape[1]
    height, width = find_grid_dimensions(n_features)
    pad_size = height * width - n_features

    if pad_size > 0:
        X_padded = np.pad(X_scaled, ((0, 0), (0, pad_size)), mode="constant")
    else:
        X_padded = X_scaled

    X_reshaped = X_padded.reshape(-1, height, width, 1)

    global_config = {
        'height': height,
        'width': width,
        'pad_size': pad_size,
        'n_classes': n_classes,
        'n_features': n_features
    }

    model = build_cnn_model((height, width, 1), n_classes)
    
    if n_classes > 2:
        y_cat = to_categorical(y_encoded, n_classes)
        loss = "categorical_crossentropy"
    else:
        y_cat = y_encoded
        loss = "binary_crossentropy"

    model.compile(optimizer="adam", loss=loss, metrics=["accuracy"])
    
    class_weights = compute_class_weight(
        "balanced",
        classes=np.unique(y_encoded),
        y=y_encoded
    )
    
    early_stopping = keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
    
    model.fit(
        X_reshaped, y_cat,
        class_weight=dict(enumerate(class_weights)),
        batch_size=32,
        epochs=10, 
        validation_split=0.2,
        callbacks=[early_stopping],
        verbose=0
    )
    
    global_model = model
    return jsonify({'message': 'Model trained successfully'})

@app.route('/api/predict', methods=['POST'])
def predict():
    if global_model is None:
        return jsonify({'error': 'Model not trained yet. Please train first.'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    filename = file.filename
    prodi = request.form.get('prodi', 'Unknown')
    angkatan = request.form.get('angkatan', 'Unknown')

    try:
        excel_file = pd.ExcelFile(file)
        sheet_to_read = 'TEST_SEM3' if 'TEST_SEM3' in excel_file.sheet_names else 0
        df = pd.read_excel(excel_file, sheet_name=sheet_to_read)
        
        # Filter by Angkatan and Prodi if columns exist
        if 'Angkatan' in df.columns and angkatan != 'Unknown':
            df = df[df['Angkatan'].astype(str) == str(angkatan)]
        if 'Prodi' in df.columns and prodi != 'Unknown':
            df = df[df['Prodi'].astype(str).str.contains(str(prodi), case=False, na=False)]
            
        if len(df) == 0:
            return jsonify({'error': f"Tidak ada data uji (TEST) untuk Angkatan {angkatan} dan Prodi {prodi}. Harap unggah data uji yang sesuai."}), 400
            
        original_df = df.copy()
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    drop_cols = ['NIM', 'Nomor PMB', 'Angkatan', 'IPK 1', 'IPK 2', 'IPK 3', 'Total SKS 3']
    df = df.drop(columns=[col for col in drop_cols if col in df.columns])
    
    target_col = "Label"
    if target_col in df.columns:
        df = df.drop(columns=[target_col])

    for col in global_encoders:
        if col in df.columns:
            le = global_encoders[col]
            df[col] = df[col].astype(str).map(lambda s: s if s in le.classes_ else le.classes_[0])
            df[col] = le.transform(df[col])
            
    # For any remaining columns that are somehow string (but weren't in train), force them to numeric
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.fillna(0)

    X_scaled = global_scaler.transform(df)

    pad_size = global_config['pad_size']
    if pad_size > 0:
        X_padded = np.pad(X_scaled, ((0, 0), (0, pad_size)), mode="constant")
    else:
        X_padded = X_scaled

    height = global_config['height']
    width = global_config['width']
    X_reshaped = X_padded.reshape(-1, height, width, 1)

    predictions = global_model.predict(X_reshaped)
    n_classes = global_config['n_classes']

    if n_classes > 2:
        y_pred = np.argmax(predictions, axis=1)
    else:
        y_pred = (predictions > 0.5).astype(int).flatten()

    predicted_labels = global_le_y.inverse_transform(y_pred)
    
    results = []
    at_risk_count = 0
    safe_count = 0
    
    for i, label in enumerate(predicted_labels):
        nim = original_df['NIM'].iloc[i] if 'NIM' in original_df.columns else f'Unknown-{i}'
        pmb = original_df['Nomor Pendaftaran'].iloc[i] if 'Nomor Pendaftaran' in original_df.columns else (original_df['Nomor PMB'].iloc[i] if 'Nomor PMB' in original_df.columns else f'Unknown-{i}')
        label_str = str(label).strip().upper()
        is_risk = (label_str == 'SISIP' or 'TIDAK LOLOS' in label_str or label_str == '1' or 'AT RISK' in label_str)
        
        if is_risk:
            at_risk_count += 1
        else:
            safe_count += 1
            
        results.append({
            'nim': str(nim),
            'pmb': str(pmb),
            'prediction': str(label),
            'isRisk': is_risk
        })

    # Save to Database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    batch_name = f"#BATCH-{datetime.datetime.now().strftime('%y%m%d%H%M')}"
    total_records = len(results)

    # Hapus batch lama jika prodi dan angkatan yang sama sudah ada sebelumnya
    c.execute('SELECT id FROM batches WHERE prodi = ? AND angkatan = ?', (prodi, angkatan))
    existing = c.fetchone()
    if existing:
        old_batch_id = existing[0]
        c.execute('DELETE FROM predictions WHERE batch_id = ?', (old_batch_id,))
        c.execute('DELETE FROM batches WHERE id = ?', (old_batch_id,))

    c.execute('''
        INSERT INTO batches (batch_name, date_uploaded, total_records, at_risk, safe, status, prodi, angkatan)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (batch_name, date_now, total_records, at_risk_count, safe_count, 'Processed', prodi, angkatan))
    batch_id = c.lastrowid
    
    pred_data = [(batch_id, r['nim'], r['pmb'], r['prediction'], r['isRisk']) for r in results]
    c.executemany('''
        INSERT INTO predictions (batch_id, nim, pmb, prediction, is_risk)
        VALUES (?, ?, ?, ?, ?)
    ''', pred_data)
    
    conn.commit()
    conn.close()

    return jsonify({
        'batch_id': batch_id,
        'batch_name': batch_name,
        'total': total_records,
        'atRisk': at_risk_count,
        'safe': safe_count,
        'prodi': prodi,
        'angkatan': angkatan,
        'results': results
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches ORDER BY id DESC')
    batches = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'batches': batches})

@app.route('/api/batch/<int:batch_id>', methods=['GET'])
def get_batch(batch_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM batches WHERE id = ?', (batch_id,))
    batch = c.fetchone()
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404
        
    c.execute('SELECT * FROM predictions WHERE batch_id = ?', (batch_id,))
    predictions = [dict(row) for row in c.fetchall()]
    conn.close()
    
    result = dict(batch)
    result['results'] = predictions
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
