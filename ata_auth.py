import requests
from bs4 import BeautifulSoup
import streamlit as st

LOGIN_URL = "https://atamartialarts.com/login"

@st.cache_resource
def get_myata_session():
    session = requests.Session()

    # ATA now requires full browser headers
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": LOGIN_URL,
        "Origin": "https://atamartialarts.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
    }

    ###############################################
    # STEP 1 — GET LOGIN PAGE
    ###############################################
    resp = session.get(LOGIN_URL, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract ASP.NET Core anti-forgery tokens
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    ufprt = soup.find("input", {"name": "ufprt"})

    if not token or not ufprt:
        st.error("ATA login page missing required anti-forgery tokens.")
        return session

    token_value = token.get("value")
    ufprt_value = ufprt.get("value")

    ###############################################
    # STEP 2 — Build login payload (unchanged)
    ###############################################
    payload = {
        "loginModel.Username": st.secrets["MYATA_USER"],
        "loginModel.Password": st.secrets["MYATA_PASS"],
        "loginModel.RememberMe": "false",
        "loginModel.RedirectUrl": "",
        "__RequestVerificationToken": token_value,
        "ufprt": ufprt_value,
    }

    ###############################################
    # STEP 3 — POST LOGIN
    ###############################################
    login_resp = session.post(LOGIN_URL, data=payload, headers=headers)

    if "Sign In" in login_resp.text or "Password" in login_resp.text:
        st.error("ATA login failed — check username/password.")
        return session

    return session
