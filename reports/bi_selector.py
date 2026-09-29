import streamlit as st
import datetime as dt
from core import db, pipeline as pl, engine
from core.ui_helpers import shift_year

def render_bi_period_selector():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🗓️ Selettore Periodo BI")

    conn = db.connect()
    stats = db.get_stats(conn)

    if stats["righe_totali"] == 0:
        st.sidebar.warning("⚠️ Il DB BI è vuoto. Carica prima un dataset nella pagina 'Carica Dati BI'.")
        conn.close()
        return

    data_min = dt.date.fromisoformat(stats["data_min"])
    data_max = dt.date.fromisoformat(stats["data_max"])

    periodo_a = st.sidebar.date_input(
        "Periodo corrente",
        value=(max(data_min, shift_year(data_max, -1)), data_max),
        min_value=data_min, max_value=data_max, key="periodo_a_selector"
    )

    confronta = st.sidebar.checkbox("Confronta con un altro periodo (Y2Y)", value=True, key="confronta_selector")
    periodo_b = None
    if confronta and isinstance(periodo_a, tuple) and len(periodo_a) == 2:
        default_b = (max(data_min, shift_year(periodo_a[0], -1)), min(data_max, shift_year(periodo_a[1], -1)))
        periodo_b = st.sidebar.date_input(
            "Periodo di confronto", value=default_b,
            min_value=data_min, max_value=data_max, key="periodo_b_selector"
        )

    perimetro_label = st.sidebar.radio(
        "Perimetro logistico",
        ["TOTALE (Diretti + Logistica Esterna)", "SOLO DIRETTI", "SOLO LOGISTICA ESTERNA (ZFS/FBA/AMZ)"],
        index=0, key="perimetro_selector"
    )
    perimetro = {"TOTALE (Diretti + Logistica Esterna)": "1", "SOLO DIRETTI": "2",
                 "SOLO LOGISTICA ESTERNA (ZFS/FBA/AMZ)": "3"}[perimetro_label]

    anagrafica_file = st.sidebar.file_uploader("Anagrafica articoli (facoltativa)", type=["csv", "txt"], key="anag_file_selector")

    periodo_a_ok = isinstance(periodo_a, tuple) and len(periodo_a) == 2
    periodo_b_ok = (not confronta) or (isinstance(periodo_b, tuple) and len(periodo_b) == 2)

    if st.sidebar.button("▶️ Genera Dati Report", type="primary", use_container_width=True, disabled=not (periodo_a_ok and periodo_b_ok)):
        anagrafica = engine.load_anagrafica(anagrafica_file) if anagrafica_file else {}
        with st.spinner("Interrogazione DB BI..."):
            try:
                result = pl.build_pipeline_from_db(
                    conn,
                    periodo_current=periodo_a,
                    periodo_old=periodo_b if (confronta and periodo_b_ok) else None,
                    perimetro=perimetro,
                    anagrafica=anagrafica,
                )
                st.session_state["pipeline"] = result
                st.session_state["perimetro_label"] = perimetro_label
                st.session_state["sel_periodo_a"] = periodo_a
                st.session_state["sel_periodo_b"] = periodo_b if (confronta and periodo_b_ok) else None
                st.session_state["periodo_a_label"] = f"{periodo_a[0]} → {periodo_a[1]}"
                st.session_state["periodo_b_label"] = f"{periodo_b[0]} → {periodo_b[1]}" if (confronta and periodo_b_ok) else None
                st.success("✅ Dati report generati con successo!")
            except Exception as e:
                st.error(f"Errore durante la generazione report: {e}")
    conn.close()
