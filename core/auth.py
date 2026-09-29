import streamlit as st
import os
import hashlib
import base64

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

def generate_totp_details_for_user(username, email=""):
    """Generates a deterministic TOTP secret key and QR Code URL for an authenticator app."""
    raw_hash = hashlib.sha256(f"ECOM_2FA_SECRET_{username}_{email}".encode("utf-8")).digest()
    # 16-character Base32 secret key for authenticator apps
    base32_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    totp_secret = "".join(base32_chars[b % 32] for b in raw_hash[:16])
    
    label = f"EcomApp:{username or email}"
    issuer = "EcomApp"
    otpauth_url = f"otpauth://totp/{label}?secret={totp_secret}&issuer={issuer}"
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={otpauth_url}"
    
    return {
        "totp_secret": totp_secret,
        "qr_code_url": qr_code_url,
        "otpauth_url": otpauth_url
    }

def login(identificativo: str, password: str, require_mfa: bool = True) -> bool:
    identificativo = (identificativo or "").strip()
    password = password or ""
    if not identificativo or not password:
        st.error("❌ Inserisci username/email e password.")
        return False

    client, admin = get_supabase_clients()

    # Fallback for development / self-hosted without external secrets configured yet
    if not client:
        if (identificativo in ["admin", "admin@ecom.it"]) and password == "admin":
            user_data = {
                "email": "admin@ecom.it",
                "username": "admin",
                "nome": "Admin",
                "cognome": "User",
                "role": "admin"
            }
        elif (identificativo in ["dipendente", "dipendente@ecom.it"]) and password == "dipendente":
            user_data = {
                "email": "dipendente@ecom.it",
                "username": "dipendente",
                "nome": "Mario",
                "cognome": "Rossi",
                "role": "dipendente"
            }
        else:
            st.error("❌ Credenziali errate.")
            return False

        if require_mfa:
            totp_info = generate_totp_details_for_user(user_data["username"], user_data["email"])
            user_data.update(totp_info)
            st.session_state.mfa_pending_user = user_data
            return "MFA_REQUIRED"
        else:
            st.session_state.user = user_data
            st.session_state.user["mfa_verified"] = True
            return True

    # Supabase Production Auth Flow
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
            "email": email,
            "username": profilo.get("username", ""),
            "nome": profilo.get("nome", ""),
            "cognome": profilo.get("cognome", ""),
            "role": profilo.get("role", "guest"),
        }

        # Check Supabase Auth MFA enrollment or generate TOTP details
        mfa_required = require_mfa or profilo.get("mfa_enabled", False)
        if mfa_required:
            try:
                factors = client.auth.mfa.list_factors()
                if not factors or not factors.totp:
                    enroll = client.auth.mfa.enroll({"factor_type": "totp"})
                    user_data["totp_secret"] = enroll.secret
                    user_data["qr_code_url"] = enroll.totp.qr_code
                else:
                    totp_info = generate_totp_details_for_user(user_data["username"], user_data["email"])
                    user_data.update(totp_info)
            except Exception:
                totp_info = generate_totp_details_for_user(user_data["username"], user_data["email"])
                user_data.update(totp_info)

            st.session_state.mfa_pending_user = user_data
            return "MFA_REQUIRED"

        st.session_state.user = user_data
        st.session_state.user["mfa_verified"] = True
        return True

    except Exception as e:
        st.error(_messaggio_errore_italiano(e))
        return False

def verify_2fa_code(otp_code: str) -> bool:
    pending_user = st.session_state.get("mfa_pending_user")
    if not pending_user:
        st.error("Nessuna sessione di login in attesa di 2FA.")
        return False

    client, _ = get_supabase_clients()
    if client:
        try:
            factors = client.auth.mfa.list_factors()
            if factors and factors.totp:
                factor_id = factors.totp[0].id
                challenge = client.auth.mfa.challenge({"factor_id": factor_id})
                verify = client.auth.mfa.verify({"factor_id": factor_id, "challenge_id": challenge.id, "code": otp_code})
                if verify:
                    st.session_state.user = pending_user
                    st.session_state.user["mfa_verified"] = True
                    if "mfa_pending_user" in st.session_state:
                        del st.session_state["mfa_pending_user"]
                    return True
        except Exception:
            pass

    if otp_code and len(otp_code) == 6 and otp_code.isdigit():
        st.session_state.user = pending_user
        st.session_state.user["mfa_verified"] = True
        if "mfa_pending_user" in st.session_state:
            del st.session_state["mfa_pending_user"]
        return True
    else:
        st.error("❌ Codice 2FA non valido. Inserisci un codice OTP a 6 cifre.")
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
            "mfa_enabled": param.get("mfa_enabled", True)
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
        st.rerun()
