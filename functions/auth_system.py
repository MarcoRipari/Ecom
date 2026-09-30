import streamlit as st
import os

supabase_url = None
supabase_key = None
service_role_key = None
supabase = None
supabase_admin = None

try:
    supabase_url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    supabase_key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    service_role_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if supabase_url and supabase_key:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        if service_role_key:
            supabase_admin = create_client(supabase_url, service_role_key)
        else:
            supabase_admin = supabase
except Exception:
    pass

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

def login(identificativo: str, password: str) -> bool:
    if not supabase:
        st.error("❌ Client Supabase non configurato.")
        return False
    try:
        identificativo = (identificativo or "").strip()
        password = password or ""
        if not identificativo or not password:
            st.error("❌ Inserisci username/email e password.")
            return False

        if "@" in identificativo:
            email = identificativo
        else:
            try:
                res_profile = supabase.table("profiles").select("*").ilike("username", identificativo).execute()
            except Exception as e:
                st.error(_messaggio_errore_italiano(e))
                return False

            if not res_profile.data:
                st.error("❌ Username non trovato.")
                return False

            user_id = res_profile.data[0]["user_id"]
            try:
                res_user = supabase_admin.auth.admin.get_user_by_id(user_id)
                email = res_user.user.email if res_user and res_user.user else None
            except Exception as e:
                st.error(_messaggio_errore_italiano(e))
                return False

            if not email:
                st.error("❌ Nessuna email associata a questo username.")
                return False

        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        if not res or not res.user:
            st.error("❌ Username/email o password errati.")
            return False

        try:
            res_profile2 = supabase.table("profiles").select("*").eq("user_id", res.user.id).execute()
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        if not res_profile2.data:
            st.error("❌ Accesso riuscito ma profilo utente non trovato. Contatta un amministratore.")
            return False

        profilo = res_profile2.data[0]
        st.session_state.user = {
            "email": email,
            "username": profilo.get("username", ""),
            "nome": profilo.get("nome", ""),
            "cognome": profilo.get("cognome", ""),
            "role": profilo.get("role", "guest"),
        }
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False

def login_password(email: str, password: str) -> bool:
    if not supabase:
        return False
    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if res.user is not None:
            profile = supabase.table("profiles").select("*").eq("user_id", res.user.id).single().execute()
            if profile.data is None:
                st.error("❌ Profilo utente non trovato")
                return False
            st.session_state.user = {
                "data": res.user,
                "email": res.user.email,
                "nome": profile.data["nome"],
                "cognome": profile.data["cognome"],
                "username": profile.data["username"],
                "role": profile.data["role"]
            }
            return True
        else:
            st.error("❌ Email o password errati")
            return False
    except Exception as e:
        st.error(f"Errore login: {e}")
        return False

def logout():
    if "user" in st.session_state:
        if supabase:
            try:
                supabase.auth.sign_out()
            except Exception as e:
                st.warning(f"⚠️ Disconnessione dal server non riuscita ({e}), ma la sessione locale è stata comunque chiusa.")
        st.session_state.user = None
        st.rerun()

def register_user(email: str, password: str, **param) -> bool:
    if not supabase or not supabase_admin:
        st.error("❌ Client Supabase non configurato.")
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

        try:
            esistente = supabase.table("profiles").select("username").ilike("username", param["username"]).execute()
            if esistente.data:
                st.error(f"❌ Esiste già un utente con lo username '{param['username']}'.")
                return False
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        try:
            res = supabase_admin.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        if not res or not res.user:
            st.error("❌ Errore nella creazione dell'utente.")
            return False

        user_id = res.user.id
        profile = {
            "user_id": user_id,
            "nome": param.get("nome", None),
            "cognome": param.get("cognome", None),
            "username": param.get("username", None),
            "role": param.get("role", None)
        }

        try:
            supabase_admin.table("profiles").insert(profile).execute()
        except Exception as e:
            st.error(
                f"⚠️ Utente creato in autenticazione, ma il salvataggio del profilo è fallito: "
                f"{_messaggio_errore_italiano(e)} Contatta un amministratore per completare la registrazione."
            )
            return False

        st.success(f"✅ Utente {param.get('username', email)} creato correttamente")
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False
