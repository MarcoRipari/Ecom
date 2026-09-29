import streamlit as st
import pandas as pd
import re
from datetime import datetime

from functions.foto import load_df_foto, count_da_scattare, get_da_riscattare, mostra_riscattare
from utils.bordered_box import bordered_box

map_cod_cli = {
  "0019243.016": "ECOM",
  "0039632": "ZFS",
  "0034630": "AMAZON"
}

def foto_dashboard():
    st.title("📸 Dashboard Foto SKUs")
    df = load_df_foto()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        bordered_box("Da scattare", count_da_scattare("totale"), "📸")
    with col2:
        bordered_box("Riscattare", count_da_scattare("riscattare"), "🔁")
    with col3:
        bordered_box("Dal fotografo", count_da_scattare("consegnate"), "🧑‍🎨")
    with col4:
        bordered_box("Mancanti", count_da_scattare("mancanti"), "⏳")
    with col5:
        bordered_box("Disponibili", count_da_scattare("disponibili"), "✅")

    st.divider()

    if st.button("🔄 Aggiorna Dati Foto"):
        df = load_df_foto(force_reload=True)

    if df.empty:
        st.info("Nessuna SKU foto registrata al momento.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

def foto_riscattare():
    st.title("🔁 Riscatta SKU Foto")
    load_df_foto()
    sku_input = st.text_input("Inserisci SKU da riscattare")
    if sku_input:
        mostra_riscattare(sku_input)

def foto_aggiungi_prelevate():
    st.header("📥 Aggiungi Paia Prelevate")
    st.markdown("Inserisci la lista delle paia prelevate per aggiornare il catalogo foto:")

    text_input = st.text_area("Lista paia prelevate (copia/incolla testo)", height=300)
    if text_input:
        pattern = r"\b[0-9a-zA-Z]{7} [0-9a-zA-Z]{2} [0-9a-zA-Z]{4}\b"
        skus_raw = re.findall(pattern, text_input)
        skus_clean = [str(sku.replace(" ", "")) for sku in skus_raw]
        st.subheader(f"SKU individuate: {len(skus_clean)}")
        if st.button("💾 Registra Prelevate"):
            st.success(f"✅ Registrate {len(skus_clean)} SKU prelevate!")
