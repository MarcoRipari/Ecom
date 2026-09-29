import os
import streamlit as st

supabase = None
supabase_admin = None

def get_supabase_clients():
    global supabase, supabase_admin
    if supabase is not None:
        return supabase, supabase_admin

    url = None
    key = None
    service_key = None

    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        service_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
    except Exception:
        pass

    if not url:
        url = os.environ.get("SUPABASE_URL")
    if not key:
        key = os.environ.get("SUPABASE_KEY")
    if not service_key:
        service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if url and key:
        try:
            from supabase import create_client
            supabase = create_client(url, key)
            if service_key:
                supabase_admin = create_client(url, service_key)
            else:
                supabase_admin = supabase
        except Exception:
            supabase = None
            supabase_admin = None

    return supabase, supabase_admin

def _messaggio_errore_italiano(e: Exception) -> str:
    testo = str(e).lower()
    if "invalid login credentials" in testo or "invalid_credentials" in testo:
        return "❌ Username/email o password errati."
    if "email not confirmed" in testo:
        return "❌ Email non confermata. Contatta un amministratore."
    if "user already registered" in testo or "already been registered" in testo:
        return "❌ Esiste già un utente registrato con questa email."
    if "password" in testo and ("short" in testo or "weak" in testo or "6 characters" in testo):
        return "❌ La password è troppo corta (minimo 6 caratteri)."
    if "rate limit" in testo or "429" in testo:
        return "❌ Troppi tentativi in poco tempo. Riprova tra qualche minuto."
    if "network" in testo or "timeout" in testo or "connection" in testo:
        return "❌ Errore di connessione al server. Riprova."
    if "jwt" in testo or "expired" in testo:
        return "❌ Sessione scaduta. Effettua di nuovo l'accesso."
    return f"❌ Si è verificato un errore imprevisto: {e}"

def login(identificativo: str, password: str) -> str | bool:
    identificativo = (identificativo or "").strip()
    password = password or ""
    if not identificativo or not password:
        st.error("❌ Inserisci username/email e password.")
        return False

    client, admin = get_supabase_clients()

    if not client:
        if (identificativo in ["admin", "admin@ecom.it"]) and password == "admin":
            st.session_state.user = {
                "email": "admin@ecom.it",
                "username": "admin",
                "nome": "Admin",
                "cognome": "User",
                "role": "admin",
                "mfa_verified": True
            }
            return True
        elif (identificativo in ["dipendente", "dipendente@ecom.it"]) and password == "dipendente":
            st.session_state.user = {
                "email": "dipendente@ecom.it",
                "username": "dipendente",
                "nome": "Mario",
                "cognome": "Rossi",
                "role": "dipendente",
                "mfa_verified": True
            }
            return True
        else:
            st.error("❌ Credenziali errate.")
            return False

    try:
        if "@" in identificativo:
            email = identificativo
        else:
            res_profile = client.table("profiles").select("*").ilike("username", identificativo).execute()
            if not res_profile.data:
                st.error("❌ Username non trovato.")
                return False
            user_id = res_profile.data[0]["user_id"]
            res_user = admin.auth.admin.get_user_by_id(user_id) if admin else None
            email = res_user.user.email if res_user and res_user.user else None
            if not email:
                st.error("❌ Nessuna email associata a questo username.")
                return False

        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if not res or not res.user:
            st.error("❌ Username/email o password errati.")
            return False

        res_profile2 = client.table("profiles").select("*").eq("user_id", res.user.id).execute()
        if not res_profile2.data:
            st.error("❌ Profilo utente non trovato.")
            return False

        profilo = res_profile2.data[0]
        
        user_data = {
            "id": res.user.id,
            "email": email,
            "username": profilo.get("username", ""),
            "nome": profilo.get("nome", ""),
            "cognome": profilo.get("cognome", ""),
            "role": profilo.get("role", "guest"),
        }

        # Controllo dei fattori 2FA registrati su Supabase Auth
        factors_res = client.auth.mfa.list_factors()
        verified_factors = [f for f in getattr(factors_res, 'totp', []) if getattr(f, 'status', '') == 'verified']

        if verified_factors:
            st.session_state.mfa_pending_user = user_data
            st.session_state.mfa_factor_id = verified_factors[0].id
            return "MFA_REQUIRED"

        st.session_state.user = user_data
        st.session_state.user["mfa_verified"] = True
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False

def verify_2fa_code(otp_code: str) -> bool:
    pending_user = st.session_state.get("mfa_pending_user")
    factor_id = st.session_state.get("mfa_factor_id")
    
    if not pending_user or not factor_id:
        st.error("❌ Nessuna sessione di login in attesa di 2FA.")
        return False

    otp_code = (otp_code or "").strip()
    if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
        st.error("❌ Inserisci un codice OTP valido a 6 cifre.")
        return False

    client, _ = get_supabase_clients()
    if client:
        try:
            challenge_res = client.auth.mfa.challenge({"factor_id": factor_id})
            challenge_id = challenge_res.id

            verify_res = client.auth.mfa.verify({
                "factor_id": factor_id,
                "challenge_id": challenge_id,
                "code": otp_code
            })

            if verify_res and getattr(verify_res, "access_token", None):
                st.session_state.user = pending_user
                st.session_state.user["mfa_verified"] = True
                
                if "mfa_pending_user" in st.session_state:
                    del st.session_state["mfa_pending_user"]
                if "mfa_factor_id" in st.session_state:
                    del st.session_state["mfa_factor_id"]
                return True
            else:
                st.error("❌ Codice 2FA errato o scaduto.")
                return False

        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

    # Fallback solo se Supabase non è configurato (ambiente dev offline)
    if pending_user.get("username") in ["admin", "dipendente"] and otp_code == "123456":
        st.session_state.user = pending_user
        st.session_state.user["mfa_verified"] = True
        del st.session_state["mfa_pending_user"]
        return True

    st.error("❌ Codice 2FA non valido.")
    return False

def register_user(email: str, password: str, **param) -> bool:
    client, admin = get_supabase_clients()
    if not admin:
        st.error("❌ Client Supabase Admin non configurato per la registrazione.")
        return False

    try:
        email = (email or "").strip()
        password = password or ""
        if not email or "@" not in email:
            st.error("❌ Inserisci un'email valida.")
            return False
        if len(password) < 6:
            st.error("❌ La password deve essere di almeno 6 caratteri.")
            return False
        if not param.get("username"):
            st.error("❌ Lo username è obbligatorio.")
            return False

        esistente = client.table("profiles").select("username").ilike("username", param["username"]).execute()
        if esistente.data:
            st.error(f"❌ Esiste già un utente con lo username '{param['username']}'.")
            return False

        res = admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })

        if not res or not res.user:
            st.error("❌ Errore nella creazione dell'utente.")
            return False

        user_id = res.user.id
        profile = {
            "user_id": user_id,
            "nome": param.get("nome", ""),
            "cognome": param.get("cognome", ""),
            "username": param.get("username", ""),
            "role": param.get("role", "guest"),
        }

        admin.table("profiles").insert(profile).execute()
        st.success(f"✅ Utente {param.get('username', email)} creato correttamente.")
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False

def logout():
    if "user" in st.session_state:
        client, _ = get_supabase_clients()
        if client:
            try:
                client.auth.sign_out()
            except Exception:
                pass
        st.session_state.user = None
        if "mfa_pending_user" in st.session_state:
            del st.session_state["mfa_pending_user"]
        if "mfa_factor_id" in st.session_state:
            del st.session_state["mfa_factor_id"]
        st.rerun()
