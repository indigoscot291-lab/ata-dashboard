import requests
from bs4 import BeautifulSoup
import streamlit as st

LOGIN_URL = "https://atamartialarts.com/myata/login/"

@st.cache_resource
def get_myata_session():
    """
    Creates and returns an authenticated MyATA session.
    Cached so we don't re-login on every Streamlit rerun.
    """
    session = requests.Session()

    # Step 1: GET login page to get CSRF + initial cookies
    resp = session.get(LOGIN_URL, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
    if not csrf_input:
        raise RuntimeError("Could not find CSRF token on MyATA login page.")

    csrf = csrf_input.get("value")

    # Step 2: POST login with credentials + CSRF
    payload = {
        "username": st.secrets["MYATA_USER"],
        "password": st.secrets["MYATA_PASS"],
        "csrfmiddlewaretoken": csrf,
    }

    headers = {
        "Referer": LOGIN_URL,
        "User-Agent": "Mozilla/5.0",
    }

    login_resp = session.post(LOGIN_URL, data=payload, headers=headers)
    login_resp.raise_for_status()

    # Optional: simple check that we are logged in
    if "Sign In" in login_resp.text and "MyATA" in login_resp.text:
        # Still seeing login page → credentials wrong or login failed
        raise RuntimeError("MyATA login appears to have failed. Check username/password in st.secrets.")

    return session
