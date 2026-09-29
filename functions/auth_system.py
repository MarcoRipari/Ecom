import os
import streamlit as st
from supabase import create_client, Client

supabase: Client = None
supabase_admin: Client = None

def get_supabase_clients():
    global supabase, supabase_admin
    if supabase is not None:
        return supabase, supabase_admin

    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    service_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if url and key:
        try:
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
    """Traduce le eccezioni più comuni di Supabase in messaggi leggibili in italiano."""
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
    """Effettua il login con username OPPURE email ed esegue l'AAL Check di Supabase per la 2FA."""
    client, admin = get_supabase_clients()
    if not client:
        st.error("❌ Connessione al database non disponibile.")
        return False

    try:
        identificativo = (identificativo or "").strip()
        password = password or ""
        if not identificativo or not password:
            st.error("❌ Inserisci username/email e password.")
            return False

        # 1. Risoluzione email se l'utente ha inserito lo username
        if "@" in identificativo:
            email = identificativo
        else:
            try:
                res_profile = client.table("profiles").select("user_id").ilike("username", identificativo).execute()
            except Exception as e:
                st.error(_messaggio_errore_italiano(e))
                return False

            if not res_profile.data:
                st.error("❌ Username non trovato.")
                return False

            user_id = res_profile.data[0]["user_id"]
            try:
                res_user = admin.auth.admin.get_user_by_id(user_id) if admin else None
                email = res_user.user.email if res_user and res_user.user else None
            except Exception as e:
                st.error(_messaggio_errore_italiano(e))
                return False

            if not email:
                st.error("❌ Nessuna email associata a questo username.")
                return False

        # 2. Authenticate user -> ottiene sessione AAL1
        try:
            res = client.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        if not res or not res.user:
            st.error("❌ Username/email o password errati.")
            return False

        # 3. Recupera dati del profilo utente
        try:
            res_profile2 = client.table("profiles").select("*").eq("user_id", res.user.id).execute()
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        if not res_profile2.data:
            st.error("❌ Accesso riuscito ma profilo utente non trovato.")
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

        # 4. AAL CHECK (Authenticators Assurance Level Check)
        # Recupera il livello di garanzia corrente (aal1 vs aal2) e i fattori verificati
        mfa_data = client.auth.mfa.get_authenticator_assurance_level()
        current_level = getattr(mfa_data, "current_level", "aal1")
        next_level = getattr(mfa_data, "next_level", "aal1")

        # Elenca i fattori associati all'utente corrente
        factors_res = client.auth.mfa.list_factors()
        totp_factors = [f for f in getattr(factors_res, 'totp', []) if getattr(f, 'status', '') == 'verified']

        # Se il livello richiesto è aal2 (o ci sono fattori TOTP verificati e siamo ancora a livello aal1)
        if (next_level == "aal2" or totp_factors) and current_level != "aal2":
            factor_id = totp_factors[0].id if totp_factors else getattr(mfa_data, "next_factor_id", None)
            
            if factor_id:
                st.session_state.mfa_pending_user = user_data
                st.session_state.mfa_factor_id = factor_id
                return "MFA_REQUIRED"

        # Nessuna 2FA richiesta o già verificata a livello aal2
        st.session_state.user = user_data
        st.session_state.user["mfa_verified"] = True
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False

def verify_2fa_code(otp_code: str) -> bool:
    """Valida il codice OTP a 6 cifre con Supabase MFA."""
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
    if not client:
        st.error("❌ Connessione al database non disponibile.")
        return False

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

def logout():
    """Effettua il logout pulendo sia la sessione Supabase sia la sessione Streamlit."""
    client, _ = get_supabase_clients()
    if "user" in st.session_state or "mfa_pending_user" in st.session_state:
        if client:
            try:
                client.auth.sign_out()
            except Exception as e:
                st.warning(f"⚠️ Disconnessione dal server non riuscita ({e}), ma la sessione locale è stata comunque chiusa.")
        st.session_state.user = None
        if "mfa_pending_user" in st.session_state:
            del st.session_state["mfa_pending_user"]
        if "mfa_factor_id" in st.session_state:
            del st.session_state["mfa_factor_id"]
        st.rerun()

def register_user(email: str, password: str, **param) -> bool:
    """Registra un nuovo utente creando la credenziale in Auth ed inserendo il profilo in 'profiles'."""
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

        try:
            esistente = client.table("profiles").select("username").ilike("username", param["username"]).execute()
            if esistente.data:
                st.error(f"❌ Esiste già un utente con lo username '{param['username']}' (a meno di maiuscole/minuscole).")
                return False
        except Exception as e:
            st.error(_messaggio_errore_italiano(e))
            return False

        try:
            res = admin.auth.admin.create_user({
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
            admin.table("profiles").insert(profile).execute()
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
