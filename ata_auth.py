import requests
from bs4 import BeautifulSoup
import streamlit as st

LOGIN_URL = "https://atamartialarts.com/login"

@st.cache_resource
def get_myata_session():
    session = requests.Session()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": LOGIN_URL,
    }

    # STEP 1 — GET LOGIN PAGE
    resp = session.get(LOGIN_URL, headers=headers, allow_redirects=True)

    print("LOGIN GET status:", resp.status_code)
    print("LOGIN GET length:", len(resp.text))

    if resp.status_code != 200:
        st.error(f"MyATA login page returned status {resp.status_code}.")
        return session

    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})

    if not csrf_input:
        st.error("Could not find CSRF token on ATA login page.")
        return session

    csrf = csrf_input.get("value")

    # STEP 2 — POST LOGIN
    payload = {
        "username": st.secrets["MYATA_USER"],
        "password": st.secrets["MYATA_PASS"],
        "csrfmiddlewaretoken": csrf,
    }

    login_resp = session.post(LOGIN_URL, data=payload, headers=headers, allow_redirects=True)

    print("LOGIN POST status:", login_resp.status_code)
    print("LOGIN POST length:", len(login_resp.text))

    if login_resp.status_code != 200:
        st.error(f"MyATA login POST returned status {login_resp.status_code}.")
        return session

    # STEP 3 — Detect login failure
    text = login_resp.text.lower()
    if "sign in" in text or "login" in text:
        st.error("ATA login failed — check username/password in st.secrets.")
        return session

    return session

