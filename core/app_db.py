import sqlite3
import os
import json
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app_data.db")

def get_connection(db_path=None):
    if db_path is None:
        db_path = DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_app_db(db_path=None):
    """Initializes all SQLite operational tables replacing Google Sheets."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    # Table for Employees & Holiday allowances
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dipendenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            totale_ferie INTEGER DEFAULT 26,
            mattina_inizio TEXT DEFAULT '08:30',
            mattina_fine TEXT DEFAULT '12:30',
            pomeriggio_inizio TEXT DEFAULT '14:00',
            pomeriggio_fine TEXT DEFAULT '18:00',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Holiday & Absence History
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ferie_storico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_inizio TEXT NOT NULL,
            data_fine TEXT NOT NULL,
            tipo TEXT NOT NULL,
            giorni_lavorativi REAL DEFAULT 1.0,
            dettaglio TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (nome) REFERENCES dipendenti(nome) ON DELETE CASCADE
        )
    """)

    # Table for Inventory (Giacenze)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS giacenze (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            descrizione TEXT,
            corridoio TEXT,
            scaffale TEXT,
            quantita INTEGER DEFAULT 0,
            marchio TEXT,
            stagione TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for Photo SKUs Management
    cur.execute("""
        CREATE TABLE IF NOT EXISTS foto_skus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            stato TEXT DEFAULT 'Da Riscatta',
            note TEXT,
            prelevato_da TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for User Dashboard Personalization Widgets
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_dashboard_widgets (
            username TEXT PRIMARY KEY,
            widgets_config TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# --- Helper DB functions for Ferie & Dipendenti ---

def ensure_dipendente_exists(nome, totale_ferie=26):
    """Ensures a employee record exists in dipendenti table for the logged in user or newly registered user."""
    nome = (nome or "").strip()
    if not nome:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM dipendenti WHERE LOWER(nome) = LOWER(?)", (nome,))
    row = cur.fetchone()
    if not row:
        cur.execute("""
            INSERT INTO dipendenti (nome, totale_ferie, mattina_inizio, mattina_fine, pomeriggio_inizio, pomeriggio_fine)
            VALUES (?, ?, '08:30', '12:30', '14:00', '18:00')
        """, (nome, totale_ferie))
        conn.commit()
    conn.close()
    return True

def get_dipendenti_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM dipendenti ORDER BY nome", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["id", "NOME", "TOTALE", "mattina_inizio", "mattina_fine", "pomeriggio_inizio", "pomeriggio_fine"])
    df.rename(columns={"nome": "NOME", "totale_ferie": "TOTALE"}, inplace=True)
    return df

def get_ferie_storico_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, nome as NOME, data_inizio as 'DATA INIZIO', data_fine as 'DATA FINE', tipo as TIPO, giorni_lavorativi as 'GIORNI LAVORATIVI', dettaglio as DETTAGLIO FROM ferie_storico ORDER BY data_inizio DESC", conn)
    conn.close()
    return df

def add_ferie_record(nome, data_inizio, data_fine, tipo, giorni_lavorativi=1.0, dettaglio=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ferie_storico (nome, data_inizio, data_fine, tipo, giorni_lavorativi, dettaglio)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nome, data_inizio, data_fine, tipo, giorni_lavorativi, dettaglio))
    conn.commit()
    conn.close()
    return True

def delete_or_sync_ferie_for_dipendente(nome, df_updated):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ferie_storico WHERE nome = ?", (nome,))
    for _, row in df_updated.iterrows():
        cur.execute("""
            INSERT INTO ferie_storico (nome, data_inizio, data_fine, tipo, giorni_lavorativi, dettaglio)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            nome,
            str(row.get("DATA INIZIO", "")),
            str(row.get("DATA FINE", "")),
            str(row.get("TIPO", "Ferie")),
            float(row.get("GIORNI LAVORATIVI", 1.0)),
            str(row.get("DETTAGLIO", ""))
        ))
    conn.commit()
    conn.close()
    return True

def update_dipendente_budget(nome, nuovo_totale):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE dipendenti SET totale_ferie = ? WHERE nome = ?", (nuovo_totale, nome))
    conn.commit()
    conn.close()
    return True

def update_dipendente_orario(nome, orario_dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE dipendenti SET
            mattina_inizio = ?,
            mattina_fine = ?,
            pomeriggio_inizio = ?,
            pomeriggio_fine = ?
        WHERE nome = ?
    """, (
        orario_dict.get("mattina_inizio", "08:30"),
        orario_dict.get("mattina_fine", "12:30"),
        orario_dict.get("pomeriggio_inizio", "14:00"),
        orario_dict.get("pomeriggio_fine", "18:00"),
        nome
    ))
    conn.commit()
    conn.close()
    return True

def delete_dipendente(nome):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dipendenti WHERE nome = ?", (nome,))
    cur.execute("DELETE FROM ferie_storico WHERE nome = ?", (nome,))
    conn.commit()
    conn.close()
    return True

# --- User Dashboard Preference Widget DB helpers ---

def get_user_dashboard_widgets(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT widgets_config FROM user_dashboard_widgets WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row and row["widgets_config"]:
        try:
            return json.loads(row["widgets_config"])
        except Exception:
            pass
    return None

def save_user_dashboard_widgets(username, widgets_list):
    conn = get_connection()
    cur = conn.cursor()
    config_json = json.dumps(widgets_list)
    cur.execute("""
        INSERT INTO user_dashboard_widgets (username, widgets_config, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(username) DO UPDATE SET
            widgets_config = excluded.widgets_config,
            updated_at = CURRENT_TIMESTAMP
    """, (username, config_json))
    conn.commit()
    conn.close()
    return True
