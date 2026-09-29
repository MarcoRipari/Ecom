import streamlit as st
import re
import os
import importlib.util
from core import app_db, auth
from reports.bi_selector import render_bi_period_selector

st.set_page_config(
    page_title="Pannello Unificato E-Commerce & Gestione",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

app_db.init_app_db()

try:
    _user_agent = (st.context.headers.get("User-Agent", "") or "")
except Exception:
    _user_agent = ""
IS_MOBILE = bool(re.search(r"Mobi|Android|iPhone|iPad|iPod|Windows Phone", _user_agent, re.IGNORECASE))

if "user" not in st.session_state:
    st.session_state.user = None
if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Dashboard Utente"

user = st.session_state.user

if user is None:
    if st.session_state.get("mfa_pending_user"):
        st.markdown("<h2 style='text-align: center;'>🔐 Autenticazione a Due Fattori (2FA / Double Opt-In)</h2>", unsafe_allow_html=True)
        st.caption("I dati del sistema sono protetti da 2FA. Inserisci il codice OTP a 6 cifre per accedere.")
        with st.form("form_2fa", clear_on_submit=False):
            otp_code = st.text_input("Codice OTP (6 cifre)", max_chars=6)
            submit_2fa = st.form_submit_button("Verifica Codice 2FA", use_container_width=True, type="primary")
            if submit_2fa:
                if auth.verify_2fa_code(otp_code):
                    st.success("✅ Autenticazione 2FA completata con successo!")
                    st.rerun()

        if st.button("⬅ Annulla e torna al login", use_container_width=True):
            keys_to_delete = ["mfa_pending_user", "mfa_factor_id", "supabase_access_token", "supabase_refresh_token"]
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        st.stop()

    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<h2 style='text-align: center;'>🔑 Accesso al Sistema</h2>", unsafe_allow_html=True)
        st.caption("Accesso unificato E-Commerce BI e Gestione Operativa (con 2FA / Double Opt-In)")
        with st.form("login_form"):
            identificativo = st.text_input("Username o Email")
            password = st.text_input("Password", type="password")
            require_2fa = st.checkbox("Richiedi verifica 2FA / OTP", value=True)
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

with st.sidebar:
    st.markdown(f"### 👋 Ciao, {user.get('nome', user.get('username')) if user else ''}")
    st.caption(f"Ruolo: **{(user.get('role', 'utente') if user else '').upper()}** | 2FA: **Attivo**")
    if st.button("🚪 Esci (Logout)", use_container_width=True):
        auth.logout()

    st.divider()

role = (user.get("role", "guest") if user else "guest").lower()

menu_structure = []

menu_structure.append({
    "section": "📌 Principale",
    "items": [
        {"name": "Dashboard Utente", "roles": ["admin", "logistica", "customer care", "dipendente", "guest"]}
    ]
})

if role in ["admin", "logistica", "customer care", "guest"]:
    menu_structure.append({
        "section": "📊 Reports & BI",
        "items": [
            {"name": "Carica Dati BI", "script": "reports/00_Carica_Dati.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Dashboard BI", "script": "reports/01_Dashboard.py", "roles": ["admin", "logistica", "customer care", "guest"]},
            {"name": "Y2Y Generale", "script": "reports/02_Y2Y_Generale.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Y2Y Collezioni", "script": "reports/03_Y2Y_Collezioni.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Y2Y Codici", "script": "reports/04_Y2Y_Codici.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Carryover", "script": "reports/05_Carryover.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Taglie", "script": "reports/06_Taglie.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Analisi Resi", "script": "reports/07_Analisi_Resi.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Log Riconciliazione", "script": "reports/08_Log_Riconciliazione.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Sell Through", "script": "reports/09_Sell_Through.py", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Nazioni", "script": "reports/10_Nazioni.py", "roles": ["admin", "logistica", "customer care"]}
        ]
    })

if role in ["admin", "logistica", "customer care"]:
    menu_structure.append({
        "section": "📋 Catalogo & Ordini",
        "items": [
            {"name": "Aggiungi Ordini Stagione", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Genera Descrizioni", "roles": ["admin", "customer care"]},
            {"name": "Genera Traduzioni", "roles": ["admin", "customer care"]}
        ]
    })

if role in ["admin", "logistica", "customer care"]:
    menu_structure.append({
        "section": "📦 Giacenze",
        "items": [
            {"name": "Importa Giacenze", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Aggiorna Anagrafica", "roles": ["admin", "logistica", "customer care"]}
        ]
    })

if role in ["admin", "logistica", "customer care"]:
    menu_structure.append({
        "section": "📸 Foto SKUs",
        "items": [
            {"name": "Dashboard Foto", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Riscatta SKU", "roles": ["admin", "logistica", "customer care"]},
            {"name": "Aggiungi Prelevate", "roles": ["admin", "logistica", "customer care"]}
        ]
    })

if role in ["admin", "dipendente"]:
    menu_structure.append({
        "section": "🌴 Gestione Ferie",
        "items": [
            {"name": "Le Mie Ferie", "roles": ["admin", "dipendente"]},
            {"name": "Report Ferie", "roles": ["admin"]},
            {"name": "Calendario Ferie", "roles": ["admin", "dipendente"]},
            {"name": "Aggiungi Ferie / Permesso", "roles": ["admin"]},
            {"name": "Gestione Dipendenti", "roles": ["admin"]}
        ]
    })

if role == "admin":
    menu_structure.append({
        "section": "⚙️ Amministrazione",
        "items": [
            {"name": "Gestione Utenti", "roles": ["admin"]}
        ]
    })

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

bi_page_names = [item["name"] for sec in menu_structure if sec["section"] == "📊 Reports & BI" for item in sec["items"]]
if st.session_state.selected_page in bi_page_names:
    render_bi_period_selector()

page_selected = st.session_state.selected_page

if page_selected == "Dashboard Utente":
    from views.dashboard import render_user_dashboard
    render_user_dashboard()

elif page_selected == "Le Mie Ferie":
    from views.ferie import dashboard_dipendente
    dashboard_dipendente()

elif page_selected == "Report Ferie":
    from views.ferie import ferie
    ferie()

elif page_selected == "Calendario Ferie":
    from views.ferie import calendario_ferie_mensile
    calendario_ferie_mensile()

elif page_selected == "Aggiungi Ferie / Permesso":
    from views.ferie import aggiungi_ferie
    aggiungi_ferie()

elif page_selected == "Gestione Dipendenti":
    from views.ferie import gestione_dipendenti
    gestione_dipendenti()

elif page_selected == "Aggiungi Ordini Stagione":
    from views.catalogo import catalogo_import_ordini
    catalogo_import_ordini()

elif page_selected == "Genera Descrizioni":
    from views.descrizioni import genera_descrizioni
    genera_descrizioni()

elif page_selected == "Genera Traduzioni":
    from views.traduzioni import genera_traduzioni
    genera_traduzioni()

elif page_selected == "Importa Giacenze":
    from views.giacenze import giacenze_importa
    giacenze_importa()

elif page_selected == "Aggiorna Anagrafica":
    from views.giacenze import aggiorna_anagrafica
    aggiorna_anagrafica()

elif page_selected == "Dashboard Foto":
    from views.foto import foto_dashboard
    foto_dashboard()

elif page_selected == "Riscatta SKU":
    from views.foto import foto_riscattare
    foto_riscattare()

elif page_selected == "Aggiungi Prelevate":
    from views.foto import foto_aggiungi_prelevate
    foto_aggiungi_prelevate()

elif page_selected == "Gestione Utenti":
    st.subheader("⚙️ Aggiungi nuovo utente")
    with st.form("reg_user_form"):
        new_email = st.text_input("Email")
        new_pass = st.text_input("Password", type="password")
        new_name = st.text_input("Nome")
        new_surname = st.text_input("Cognome")
        new_username = st.text_input("Username")
        new_role = st.selectbox("Ruolo", ["guest", "logistica", "customer care", "admin", "dipendente"])
        mfa_opt = st.checkbox("Richiedi Autenticazione 2FA (MFA)", value=True)
        reg_btn = st.form_submit_button("Registra Utente")
        if reg_btn:
            auth.register_user(new_email, new_pass, nome=new_name, cognome=new_surname, username=new_username, role=new_role, mfa_enabled=mfa_opt)

else:
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
