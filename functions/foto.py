import streamlit as st
import pandas as pd
from .utils import normalize_bool

def load_df_foto(force_reload=False):
    if not force_reload and "df_foto" in st.session_state:
        return st.session_state.df_foto

    sheet_id = None
    try:
        sheet_id = st.secrets.get("FOTO_GSHEET_ID")
    except Exception:
        sheet_id = None

    if not sheet_id:
        # Fallback to local SQLite or empty frame if Google Sheet secrets are not configured
        from core.app_db import get_connection
        conn = get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM foto_skus", conn)
        except Exception:
            df = pd.DataFrame()
        conn.close()

        if df.empty:
            columns = ["CANALE", "SKU", "COLLEZIONE", "DESCRIZIONE", "SCATTARE", "CONSEGNATA", "RISCATTARE", "FOTOGRAFO", "DISP", "DISP 027", "DISP 012", "X", "Y", "COR", "LAT", "COD", "VAR", "COL", "TG PIC", "TG CAMP", "UBI"]
            df = pd.DataFrame(columns=columns)
        else:
            for c in ["SCATTARE", "CONSEGNATA", "RISCATTARE", "DISP", "DISP 027", "DISP 012"]:
                if c in df.columns:
                    df[c] = normalize_bool(df[c])
        st.session_state.df_foto = df
        return df

    try:
        from .gsheet import get_sheet
        sheet = get_sheet(sheet_id, "LISTA")
        values = sheet.get_all_values()
        df = pd.DataFrame(values[1:], columns=values[0]) if len(values) > 1 else pd.DataFrame()

        for c in ["SCATTARE", "CONSEGNATA", "RISCATTARE", "DISP", "DISP 027", "DISP 012"]:
            if c in df.columns:
                df[c] = normalize_bool(df[c])

        if "X" in df.columns:
            df["X"] = pd.to_numeric(df["X"], errors="coerce").astype("Int64")
        if "Y" in df.columns:
            df["Y"] = pd.to_numeric(df["Y"], errors="coerce").astype("Int64")

        st.session_state.df_foto = df
        return df
    except Exception:
        columns = ["CANALE", "SKU", "COLLEZIONE", "DESCRIZIONE", "SCATTARE", "CONSEGNATA", "RISCATTARE", "FOTOGRAFO", "DISP", "DISP 027", "DISP 012", "X", "Y", "COR", "LAT", "COD", "VAR", "COL", "TG PIC", "TG CAMP", "UBI"]
        df = pd.DataFrame(columns=columns)
        st.session_state.df_foto = df
        return df

def count_da_scattare(type="totale"):
    df = load_df_foto()
    if df.empty:
        return 0
    scattare = len(df[df.get("SCATTARE") == True]) if "SCATTARE" in df.columns else 0
    riscattare = len(df[df.get("RISCATTARE") == True]) if "RISCATTARE" in df.columns else 0
    consegnate = len(df[(df.get("CONSEGNATA") == True) & (df.get("SCATTARE") == True)]) if "CONSEGNATA" in df.columns and "SCATTARE" in df.columns else 0
    disponibili = len(df[df.get("DISP") == True]) if "DISP" in df.columns else 0

    if type == "mancanti":
        return (scattare + riscattare) - consegnate
    elif type == "riscattare":
        return riscattare
    elif type == "totale":
        return scattare
    elif type == "consegnate":
        return consegnate
    elif type == "disponibili":
        return disponibili
    return 0

def get_da_riscattare():
    df = load_df_foto()
    if df.empty or "RISCATTARE" not in df.columns:
        return pd.DataFrame()
    return df[df["RISCATTARE"] == True]

def mostra_riscattare(sku_input):
    df = load_df_foto()
    if df.empty or "SKU" not in df.columns:
        st.warning("Nessun dato SKU disponibile.")
        return
    sku_norm = sku_input.strip().upper()
    match = df[df["SKU"] == sku_norm]
    if match.empty:
        st.warning("❌ SKU non trovata.")
    else:
        row = match.iloc[0]
        st.markdown(f"**SKU**: {row['SKU']} — {row.get('DESCRIZIONE', '')}")
