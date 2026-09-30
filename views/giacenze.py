import streamlit as st
import pandas as pd
import logging
import time
from io import BytesIO, StringIO

from utils import read_csv_auto_encoding
from core.app_db import get_connection
from functions.gsheet import get_sheet

SHEETS_CONFIG = {
    "FOTO": "1MFwBu5qcXwD0Hti1Su9KTxl3Z9OLGtQtp1d3HJNEiY4",
    "VECCHIA STAGIONE": "13DnpAX7M9wymMR1YIH5IP28y_UaCPajBUIcoHca562U",
    "NUOVA STAGIONE": "1YbU9twZgJECIsbxhRft-7yGGuH37xzVdOkz7jJIL5aQ",
    "SELE-SALDI-26-1": "1idaTt1PcyZo4NVu7B1Nfc5zUUhLq0dFmaF-M5r1YB7A",
    "OUTLET_FW26": "1LxLWykK_cwf4eVVF61oDNM4hxUzCyIQoGLC-EP1Z8t0",
    "SELE-OUTLET-PE26": "1eR3ZOE6IzGgYP4mPnyGBfWiDof4Gpv9olOVu_G_k1dg",
    "30.06.26_Base_Dati_Retag_26/1+26/2": "12bjlbGOuiYfKrRRe0TPOhaJ64vwts3csdTMdwTMG3Rg",
    "AMAZON PRIME || SELEZIONE": "1O4SH9B6LB7JflQY8UcPcucsQJdMI7jQNRcxJquZlpog",
    "SELE-BF-FW26-2": "1b4VOxFS14xyGU9Y03Ktwl0yPz1hex0RgyF7L11gc7LA",
    "Base_Dati_RTM_26-1": "11ag7I-Z4U6EzsUUEvyGsFciKlz2gONsynwKwcUBEI1U",
    "SKU FOTO 26/2": "1JW30e-RF2WREWe96Qj-M_zVtjqbvg3ZhRgXuY2E5CqU",
}

def giacenze_importa():
    st.header("📦 Importa Giacenze")

    # --- 1. STATO PERSISTENTE ---
    if "import_logs" not in st.session_state: st.session_state.import_logs = {}
    if "import_in_corso" not in st.session_state: st.session_state.import_in_corso = False
    if "target_rimanenti" not in st.session_state: st.session_state.target_rimanenti = []
    if "current_row_index" not in st.session_state: st.session_state.current_row_index = 0
    if "file_bytes_for_upload" not in st.session_state: st.session_state.file_bytes_for_upload = None
    if "df_input" not in st.session_state: st.session_state.df_input = None

    # --- 2. CARICAMENTO FILE ---
    uploaded_file = st.file_uploader("Carica un file CSV giacenze", type="csv", key="uploader_manual")
    if uploaded_file:
        content = uploaded_file.getvalue()
        if st.session_state.file_bytes_for_upload != content:
            st.session_state.file_bytes_for_upload = content
            st.session_state.df_input = None
            st.session_state.import_logs = {}

    if st.session_state.file_bytes_for_upload and st.session_state.df_input is None:
        st.session_state.df_input = read_csv_auto_encoding(st.session_state.file_bytes_for_upload, ";")

    df_input = st.session_state.df_input

    # --- 3. INPUT UTENTE ---
    options = ["COMPLETO", "MANUALE"] + list(SHEETS_CONFIG.keys())
    sheet_selection = st.selectbox("Seleziona target:", options)
    manual_id = ""
    if sheet_selection == "COMPLETO":
        targets_finali = list(SHEETS_CONFIG.values())
    elif sheet_selection == "MANUALE":
        manual_id = st.text_input("Inserisci l'ID del foglio Google Sheet")
        targets_finali = [manual_id] if manual_id else []
    else:
        targets_finali = [SHEETS_CONFIG[sheet_selection]]

    nome_sheet_tab = st.text_input("Nome del TAB", value="GIACENZE")

    # --- 4. PULSANTI ---
    col1, col2, col3, col4 = st.columns(4)

    def start_process(tipo, selection):
        if selection == "MANUALE":
            st.session_state.import_logs = {manual_id: "⏳ In coda"}
        else:
            st.session_state.import_logs = {k: "⏳ In coda" for k in SHEETS_CONFIG.keys() if SHEETS_CONFIG[k] in targets_finali}

        st.session_state.target_rimanenti = targets_finali.copy()
        st.session_state.import_in_corso = tipo
        st.session_state.current_row_index = 0

    if col1.button("Anagrafica", use_container_width=True): start_process("ANAGRAFICA", sheet_selection)
    if col2.button("Giacenze", use_container_width=True): start_process("GIACENZE", sheet_selection)
    if col3.button("Tutto", use_container_width=True): start_process("TOTALE", sheet_selection)
    if col4.button("Salva nel DB Locale", use_container_width=True):
        if df_input is not None and not df_input.empty:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM giacenze")
            for _, r in df_input.iterrows():
                sku_val = str(r.get("SKU", r.get("sku", ""))).strip()
                if sku_val:
                    desc_val = str(r.get("DESCRIZIONE", r.get("descrizione", "")))
                    quant_val = int(pd.to_numeric(r.get("QUANTITA", r.get("quantita", 0)), errors="coerce") or 0)
                    cur.execute("""
                        INSERT OR REPLACE INTO giacenze (sku, descrizione, quantita)
                        VALUES (?, ?, ?)
                    """, (sku_val, desc_val, quant_val))
            conn.commit()
            conn.close()
            st.success("✅ Giacenze salvate nel database SQLite locale!")

    # Tabella Avanzamento
    if st.session_state.import_logs:
        st.divider()
        st.subheader("📊 Stato Avanzamento Importazione")
        st.table([{"Foglio": k, "Stato": v} for k, v in st.session_state.import_logs.items()])

    # --- 5. ESECUZIONE IMPORTAZIONE (SQLite + GSheets Sync) ---
    if st.session_state.import_in_corso and df_input is not None:
        try:
            # 1. Aggiorna sempre il DB SQLite locale
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM giacenze")
            for _, r in df_input.iterrows():
                sku_val = str(r.get("SKU", r.get("sku", ""))).strip()
                if sku_val:
                    desc_val = str(r.get("DESCRIZIONE", r.get("descrizione", "")))
                    quant_val = int(pd.to_numeric(r.get("QUANTITA", r.get("quantita", 0)), errors="coerce") or 0)
                    cur.execute("""
                        INSERT OR REPLACE INTO giacenze (sku, descrizione, quantita)
                        VALUES (?, ?, ?)
                    """, (sku_val, desc_val, quant_val))
            conn.commit()
            conn.close()

            # 2. Tenta di aggiornare i Google Sheets di destinazione se le credenziali GCP sono configurate
            for target_id in st.session_state.target_rimanenti:
                nome_leggibile = next((k for k, v in SHEETS_CONFIG.items() if v == target_id), f"ID: {target_id[:5]}")
                try:
                    sh_gia = get_sheet(target_id, nome_sheet_tab)
                    values = [df_input.columns.tolist()] + df_input.fillna("").astype(str).values.tolist()
                    sh_gia.clear()
                    sh_gia.update("A1", values, value_input_option="USER_ENTERED")
                    st.session_state.import_logs[nome_leggibile] = "✅ Completato (SQLite + GSheets)"
                except Exception as g_err:
                    st.session_state.import_logs[nome_leggibile] = "✅ Completato (SQLite)"

            st.session_state.import_in_corso = False
            st.success("✅ Importazione completata ed elaborata sul database!")
            st.balloons()
        except Exception as e:
            st.error(f"Errore durante l'importazione: {e}")
            st.session_state.import_in_corso = False

def giacenze_dashboard():
    st.title("📦 Giacenze Magazzino")
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT sku as SKU, descrizione as DESCRIZIONE, quantita as QUANTITA, updated_at as AGGIORNATO_IL FROM giacenze", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()

    if df.empty:
        st.info("Nessun dato giacenze in magazzino. Vai su 'Importa giacenze' per caricare un file CSV.")
    else:
        st.metric("Totale SKU Registrate", len(df))
        st.dataframe(df, use_container_width=True, hide_index=True)
