import streamlit as st
import os
import openai

try:
    openai.api_key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
except Exception:
    openai.api_key = os.environ.get("OPENAI_API_KEY", "")

def check_openai_key():
    try:
        if not openai.api_key:
            return False
        openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=1
        )
        return True
    except Exception as e:
        msg = str(e).lower()
        return False
