import streamlit as st
import re
import os
import importlib.util
from core import app_db, auth

# Page Configuration
st.set_page_config(
    page_title="Pannello Unificato E-Commerce & Gestione",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize SQLite operational database
app_db.init_app_db()

# Mobile detection helper
try:
    _user_agent = (st.context.headers.get("User-Agent", "") or "")
except Exception:
    _user_agent = ""
IS_MOBILE = bool(re.search(r"Mobi|Android|iPhone|iPad|iPod|Windows Phone", _user_agent, re.IGNORECASE))

# Session State Initialization
if "user" not in st.session_state:
    st.session_state.user = None
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Dashboard Utente"

user = st.session_state.user

# --- LOGIN SCREEN ---
if user is None:
    # Handle pending 2FA challenge
    if st.session_state.get("mfa_pending_user"):
        st.markdown("<h2 style='text-align: center;'>🔐 Autenticazione a Due Fattori (2FA)</h2>", unsafe_allow_html=True)
        st.caption("Per accedere ai dati sensibili inserisci il codice a 6 cifre dal tuo dispositivo di autenticazione.")
        with st.form("form_2fa", clear_on_submit=False):
            otp_code = st.text_input("Codice OTP (6 cifre)", max_chars=6)
            submit_2fa = st.form_submit_button("Verifica Codice", use_container_width=True, type="primary")
            if submit_2fa:
                if auth.verify_2fa_code(otp_code):
                    st.success("✅ Autenticazione completata con successo!")
                    st.rerun()

        if st.button("⬅️ Annulla e torna al login", use_container_width=True):
            del st.session_state["mfa_pending_user"]
            st.rerun()
        st.stop()

    # Main Login Form
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<h2 style='text-align: center;'>🔑 Accesso al Sistema</h2>", unsafe_allow_html=True)
        st.caption("Accesso unificato E-Commerce BI e Gestione Operativa")
        with st.form("login_form"):
            identificativo = st.text_input("Username o Email")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Accedi", type="primary", use_container_width=True)

        if login_btn:
            res = auth.login(identificativo, password)
            if res == "MFA_REQUIRED":
                st.info("🔑 Codice 2FA richiesto. Inserisci il codice nella schermata successiva.")
                st.rerun()
            elif res is True:
                st.success("✅ Accesso effettuato!")
                st.rerun()

    st.stop()

# --- LOGGED IN APPLICATION ---

# Sidebar User Info & Logout
with st.sidebar:
    st.markdown(f"### 👋 Ciao, {user.get('nome', user.get('username')) if user else ''}")
    st.caption(f"Ruolo: **{(user.get('role', 'utente') if user else '').upper()}**")
    if st.button("🚪 Esci (Logout)", use_container_width=True):
        auth.logout()

    st.divider()

# Define Navigation Menu according to Role
role = (user.get("role", "guest") if user else "guest").lower()

# Menu structure with collapsible sections
menu_structure = []

# 1. Main Dashboard
menu_structure.append({
    "section": "📌 Principale",
    "icon": "house",
    "items": [
        {"name": "Dashboard Utente", "icon": "speedometer", "roles": ["admin", "logistica", "customer care", "dipendente", "guest"]}
    ]
})

# 2. E-Commerce BI Reports
if role in ["admin", "logistica", "customer care", "guest"]:
    menu_structure.append({
        "section": "📊 Reports & BI",
        "icon": "bar-chart",
        "items": [
            {"name": "Carica Dati BI", "icon": "upload", "script": "reports/00_Carica_Dati.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Dashboard BI", "icon": "graph-up", "script": "reports/01_Dashboard.py", "roles": ["admin", "logistica", "customer care", "guest"]},
            {"name": "Y2Y Generale", "icon": "pie-chart", "script": "reports/02_Y2Y_Generale.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Y2Y Collezioni", "icon": "diagram-3", "script": "reports/03_Y2Y_Collezioni.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Y2Y Codici", "icon": "123", "script": "reports/04_Y2Y_Codici.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Carryover", "icon": "arrow-repeat", "script": "reports/05_Carryover.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Taglie", "icon": "box-seam", "script": "reports/06_Taglie.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Analisi Resi", "icon": "arrow-return-left", "script": "reports/07_Analisi_Resi.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Log Riconciliazione", "icon": "journal-text", "script": "reports/08_Log_Riconciliazione.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Sell Through", "icon": "bag-check", "script": "reports/09_Sell_Through.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Nazioni", "icon": "globe", "script": "reports/10_Nazioni.py", "roles": ["admin", "logistica", "customer care"]}
        ]
    })

# 3. Operational Features (Catalogo, Giacenze, Foto, Ferie)
if role in ["admin", "logistica", "customer care"]:
    menu_structure.append({
        "section": "📦 Giacenze & Foto",
        "icon": "boxes",
        "items": [
            {"name": "Importa Giacenze", "icon": "cloud-upload", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Dashboard Foto", "icon": "camera", "roles": ["admin", "logistica", "customer care"]}
        ]
    })

if role in ["admin", "dipendente"]:
    menu_structure.append({
        "section": "🌴 Gestione Ferie",
        "icon": "calendar-event",
        "items": [
            {"name": "Le Mie Ferie", "icon": "person-workspace", "roles": ["admin", "dipendente"]},
            {"name": "Calendario Ferie", "icon": "calendar3", "roles": ["admin", "dipendente"]},
            {"name": "Aggiungi Ferie", "icon": "plus-circle", "roles": ["admin"]},
            {"name": "Gestione Dipendenti", "icon": "gear", "roles": ["admin"]}
        ]
    })

if role == "admin":
    menu_structure.append({
        "section": "⚙️ Amministrazione",
        "icon": "shield-lock",
        "items": [
            {"name": "Gestione Utenti", "icon": "person-plus", "roles": ["admin"]}
        ]
    })

# Render Sidebar Collapsible Navigation
with st.sidebar:
    st.markdown("### 📋 Navigation")
    for sec in menu_structure:
        with st.expander(sec["section"], expanded=True):
            for item in sec["items"]:
                if role in item.get("roles", []):
                    item_key = f"nav_{sec['section']}_{item['name']}"
                    is_active = (st.session_state.selected_page == item["name"])
                    btn_type = "primary" if is_active else "secondary"
                    if st.button(f"{item['name']}", key=item_key, use_container_width=True, type=btn_type):
                        st.session_state.selected_page = item["name"]
                        st.rerun()

# --- DYNAMIC PAGE ROUTING ---
page_selected = st.session_state.selected_page

if page_selected == "Dashboard Utente":
    from views.dashboard import render_user_dashboard
    render_user_dashboard()

elif page_selected == "Le Mie Ferie":
    from views.ferie import dashboard_dipendente
    dashboard_dipendente()

elif page_selected == "Calendario Ferie":
    from views.ferie import calendario_ferie_mensile
    calendario_ferie_mensile()

elif page_selected == "Aggiungi Ferie":
    from views.ferie import aggiungi_ferie
    aggiungi_ferie()

elif page_selected == "Gestione Dipendenti":
    from views.ferie import gestione_dipendenti
    gestione_dipendenti()

elif page_selected == "Importa Giacenze":
    from views.giacenze import giacenze_importa
    giacenze_importa()

elif page_selected == "Dashboard Foto":
    from views.foto import foto_dashboard
    foto_dashboard()

elif page_selected == "Gestione Utenti":
    st.subheader("⚙️ Aggiungi nuovo utente")
    with st.form("reg_user_form"):
        new_email = st.text_input("Email")
        new_pass = st.text_input("Password", type="password")
        new_name = st.text_input("Nome")
        new_surname = st.text_input("Cognome")
        new_username = st.text_input("Username")
        new_role = st.selectbox("Ruolo", ["guest", "logistica", "customer care", "admin", "dipendente"])
        mfa_opt = st.checkbox("Richiedi Autenticazione 2FA (MFA)", value=False)
        reg_btn = st.form_submit_button("Registra Utente")
        if reg_btn:
            auth.register_user(new_email, new_pass, nome=new_name, cognome=new_surname, username=new_username, role=new_role, mfa_enabled=mfa_opt)

else:
    # Execute Report Script dynamically if it's an EcomAnalysis report
    script_path = None
    for sec in menu_structure:
        for item in sec["items"]:
            if item["name"] == page_selected and "script" in item:
                script_path = item["script"]
                break

    if script_path and os.path.exists(script_path):
        spec = importlib.util.spec_from_file_location("report_module", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    else:
        st.info(f"Sezione '{page_selected}' pronta.")
