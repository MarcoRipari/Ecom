import streamlit as st
import datetime as dt
from core import app_db, db as report_db
from functions.ferie_db import get_dipendenti, get_ferie_storico, calcola_riepilogo_ferie_annuale, formatta_giorni_ore, tema_colori

ALL_WIDGETS = [
    {"id": "widget_ferie", "name": "🌴 Le mie Ferie & Residuo", "roles": ["admin", "dipendente"]},
    {"id": "widget_ecom_bi", "name": "📊 Metriche & Copertura E-Commerce BI", "roles": ["admin", "logistica", "customer care", "guest"]},
    {"id": "widget_giacenze", "name": "📦 Stato Giacenze e Magazzino", "roles": ["admin", "logistica", "customer care"]},
    {"id": "widget_foto", "name": "📸 Avanzamento Catalogo Foto SKUs", "roles": ["admin", "logistica", "customer care"]},
    {"id": "widget_quick_links", "name": "🚀 Collegamenti Rapidi", "roles": ["admin", "logistica", "customer care", "dipendente", "guest"]}
]

def get_default_widgets_for_role(role):
    role = (role or "guest").lower()
    return [w["id"] for w in ALL_WIDGETS if role in w["roles"]]

@st.dialog("⚙️ Personalizza Dashboard")
def customize_dashboard_dialog(username, role):
    st.write(f"Personalizza i widget visualizzati nella tua homepage (Utente: **{username}**):")

    current_enabled = app_db.get_user_dashboard_widgets(username)
    if current_enabled is None:
        current_enabled = get_default_widgets_for_role(role)

    available_widgets = [w for w in ALL_WIDGETS if role.lower() in w["roles"]]

    selected_ids = []
    for widget in available_widgets:
        is_checked = widget["id"] in current_enabled
        enabled = st.toggle(widget["name"], value=is_checked, key=f"toggle_{widget['id']}")
        if enabled:
            selected_ids.append(widget["id"])

    if st.button("💾 Salva Configurazione", type="primary", use_container_width=True):
        app_db.save_user_dashboard_widgets(username, selected_ids)
        st.success("✅ Configurazione salvata!")
        st.rerun()

def render_user_dashboard():
    user = st.session_state.get("user", {}) or {}
    username = user.get("username", "guest")
    nome = user.get("nome", username)
    role = user.get("role", "guest")

    col_title, col_opt = st.columns([4, 1])
    with col_title:
        st.title(f"👋 Benvenuto, {nome}!")
        st.caption(f"Dashboard personale personalizzata — Ruolo: **{role.upper()}**")
    with col_opt:
        if st.button("⚙️ Personalizza", use_container_width=True):
            customize_dashboard_dialog(username, role)

    # Load configured widgets
    active_widget_ids = app_db.get_user_dashboard_widgets(username)
    if active_widget_ids is None:
        active_widget_ids = get_default_widgets_for_role(role)

    st.divider()

    # Widget 1: Le Mie Ferie
    if "widget_ferie" in active_widget_ids and role in ["admin", "dipendente"]:
        st.subheader("🌴 Le mie Ferie")
        df_dip = get_dipendenti()
        df_storico = get_ferie_storico()
        full_name = f"{(user.get('nome') or '').strip()} {(user.get('cognome') or '').strip()}".strip()
        riga = df_dip[df_dip['NOME'] == full_name] if full_name else df_dip.head(1)

        if not riga.empty:
            info_dip = riga.iloc[0]
            anno_curr = dt.datetime.now().year
            riepilogo = calcola_riepilogo_ferie_annuale(df_storico, info_dip.NOME, info_dip.TOTALE)
            dati_anno = riepilogo[anno_curr]
            t = tema_colori()

            c1, c2, c3 = st.columns(3)
            c1.metric("Totale Disponibile", formatta_giorni_ore(dati_anno["disponibili"]))
            c2.metric("Godute / Usate", formatta_giorni_ore(dati_anno["usati"]))
            c3.metric("Residuo Attuale", formatta_giorni_ore(dati_anno["residuo"]))
        else:
            st.info("Profilo ferie non associato direttamente a un dipendente.")
        st.divider()

    # Widget 2: Metriche E-Commerce BI
    if "widget_ecom_bi" in active_widget_ids and role in ["admin", "logistica", "customer care", "guest"]:
        st.subheader("📊 Stato Database E-Commerce BI")
        try:
            conn = report_db.connect()
            stats = report_db.get_stats(conn)
            conn.close()
            if stats["righe_totali"] > 0:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Righe nel DB", f"{stats['righe_totali']:,}".replace(",", "."))
                c2.metric("Spediti", f"{stats['spediti']:,}".replace(",", "."))
                c3.metric("Resi", f"{stats['resi']:,}".replace(",", "."))
                c4.metric("Rimborsi Extra", f"{stats['standalone']:,}".replace(",", "."))
                st.caption(f"Copertura dati nel DB: dal **{stats['data_min']}** al **{stats['data_max']}**")
            else:
                st.info("ℹ️ Il database E-Commerce BI è vuoto. Vai alla pagina 'Carica Dati BI' per importare un dataset.")
        except Exception as e:
            st.warning(f"Database E-Commerce BI non ancora popolato: {e}")
        st.divider()

    # Widget 3: Stato Giacenze
    if "widget_giacenze" in active_widget_ids and role in ["admin", "logistica", "customer care"]:
        st.subheader("📦 Stato Giacenze Magazzino")
        conn_app = app_db.get_connection()
        cur = conn_app.cursor()
        cur.execute("SELECT COUNT(*) as count, SUM(quantita) as total_qty FROM giacenze")
        row_g = cur.fetchone()
        conn_app.close()

        c1, c2 = st.columns(2)
        c1.metric("SKU in Magazzino", f"{row_g['count'] or 0:,}".replace(",", "."))
        c2.metric("Pezzi Totali Giacenza", f"{row_g['total_qty'] or 0:,}".replace(",", "."))
        st.divider()

    # Widget 4: Quick Links
    if "widget_quick_links" in active_widget_ids:
        st.subheader("🚀 Collegamenti Rapidi")
        q1, q2, q3 = st.columns(3)
        if q1.button("📊 Vai a Dashboard BI", use_container_width=True):
            st.session_state.selected_page = "Dashboard BI"
            st.rerun()
        if q2.button("🌴 Le Mie Ferie", use_container_width=True):
            st.session_state.selected_page = "Le Mie Ferie"
            st.rerun()
        if q3.button("📦 Importa Giacenze", use_container_width=True):
            st.session_state.selected_page = "Importa Giacenze"
            st.rerun()
