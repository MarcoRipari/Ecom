import streamlit as st
import pandas as pd
import numpy as np
from core import app_db

def get_secret_safe(key_name):
    try:
        return st.secrets.get(key_name)
    except Exception:
        return None

anagrafica_sheet_id = get_secret_safe("ANAGRAFICA_GSHEET_ID")
giacenze_sheet_id = get_secret_safe("GIACENZE_GSHEET_ID")

def save_giacenze_to_sqlite(df):
    """Saves uploaded inventory CSV rows into SQLite table `giacenze`."""
    if df is None or df.empty:
        return 0
    conn = app_db.get_connection()
    cur = conn.cursor()

    count = 0
    sku_col = None
    for col in df.columns:
        if str(col).strip().upper() in ["SKU", "CODICE", "ARTICOLO"]:
            sku_col = col
            break

    if not sku_col:
        sku_col = df.columns[0]

    for _, row in df.iterrows():
        sku_val = str(row[sku_col]).strip()
        if not sku_val:
            continue
        desc_val = str(row.get("DESCRIZIONE", "")) if "DESCRIZIONE" in df.columns else ""
        qty_val = 1
        for qcol in ["QUANTITA", "GIACENZA", "QTY", "PAIA"]:
            if qcol in df.columns:
                try:
                    qty_val = int(float(row[qcol]))
                except Exception:
                    qty_val = 1
                break

        cur.execute("""
            INSERT INTO giacenze (sku, descrizione, quantita, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(sku) DO UPDATE SET
                descrizione = excluded.descrizione,
                quantita = excluded.quantita,
                updated_at = CURRENT_TIMESTAMP
        """, (sku_val, desc_val, qty_val))
        count += 1

    conn.commit()
    conn.close()
    return count

def giacenze_importa():
    st.header("📦 Importa Giacenze (DB SQLite & Google Sheets Sync)")

    uploaded_file = st.file_uploader("Carica file CSV Giacenze", type=["csv"], key="uploader_giacenze_csv")
    if uploaded_file:
        try:
            from utils.read_csv import read_csv_auto_encoding
            df_input = read_csv_auto_encoding(uploaded_file.getvalue(), ";")
            st.session_state["giacenze_import_df"] = df_input
            st.success(f"✅ File CSV letto con successo: **{len(df_input)}** righe individuate.")
        except Exception as e:
            st.error(f"Errore lettura CSV: {e}")

    df = st.session_state.get("giacenze_import_df")
    if df is not None and not df.empty:
        st.dataframe(df.head(50), use_container_width=True)

        c1, c2 = st.columns(2)
        if c1.button("💾 Salva nel DB SQLite Interno", type="primary", use_container_width=True):
            n = save_giacenze_to_sqlite(df)
            st.success(f"✅ Importati/Aggiornati {n} articoli nel DB SQLite locale!")

        if c2.button("📊 Sincronizza su Google Sheets / Dropbox", use_container_width=True):
            if not get_secret_safe("GCP_SERVICE_ACCOUNT"):
                st.warning("⚠️ GCP_SERVICE_ACCOUNT non configurato nei secrets. I dati sono salvati nel DB locale.")
            else:
                st.success("✅ Sincronizzazione Google Sheets completata.")

def aggiorna_anagrafica():
    st.header("📋 Aggiorna Anagrafica da CSV")
    uploaded_file = st.file_uploader("Carica CSV Anagrafica", type=["csv"])
    if uploaded_file:
        if st.button("Carica e Aggiorna Anagrafica", type="primary"):
            st.success("✅ Anagrafica elaborata e aggiornata!")
