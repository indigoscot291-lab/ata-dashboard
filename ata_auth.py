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
    resp = session.get(LOGIN_URL, headers=headers)
    st.write("===== DEBUG: LOGIN PAGE FIRST 2000 CHARS =====")
    st.write(resp.text[:2000])

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract ASP.NET Core anti-forgery tokens
    token = soup.find("input", {"name": "__RequestVerificationToken"})
    ufprt = soup.find("input", {"name": "ufprt"})

    # DEBUG: token extraction
    st.write("===== DEBUG: TOKEN FOUND? =====", bool(token))
    st.write("===== DEBUG: UFPRT FOUND? =====", bool(ufprt))

    if not token or not ufprt:
        st.write("===== DEBUG: TOKEN FAILURE — RETURNING EARLY =====")
        st.error("ATA login page missing required anti-forgery tokens.")
        return session

    token_value = token.get("value")
    ufprt_value = ufprt.get("value")

    # STEP 2 — Build login payload
    payload = {
        "loginModel.Username": st.secrets["MYATA_USER"],
        "loginModel.Password": st.secrets["MYATA_PASS"],
        "loginModel.RememberMe": "false",
        "loginModel.RedirectUrl": "",
        "__RequestVerificationToken": token_value,
        "ufprt": ufprt_value,
    }

    # STEP 3 — POST LOGIN
    login_resp = session.post(LOGIN_URL, data=payload, headers=headers)

    # DEBUG: login response
    st.write("===== DEBUG: LOGIN RESPONSE LENGTH =====", len(login_resp.text))
    st.write("===== DEBUG: LOGIN RESPONSE FIRST 300 CHARS =====")
    st.write(login_resp.text[:300])

    if "Sign In" in login_resp.text or "Password" in login_resp.text:
        st.write("===== DEBUG: LOGIN FAILURE — RETURNING EARLY =====")
        st.error("ATA login failed — check username/password.")
        return session

    ###############################################
    # DEBUG BLOCK — TEST PROTECTED PAGE
    ###############################################

    test_url = "https://atamartialarts.com/myata/tournament-standings/worlds-standings/?code=W01D"

    debug_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://atamartialarts.com/myata/",
        "Origin": "https://atamartialarts.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-User": "?1",
    }

    test_resp = session.get(test_url, headers=debug_headers, allow_redirects=True)

    st.write("===== DEBUG: COOKIES AFTER LOGIN =====")
    cookie_dump = []
    for c in session.cookies:
        cookie_dump.append(f"{c.name} | {c.value} | {c.domain} | {c.path}")
    st.write(cookie_dump)

    st.write("===== DEBUG: STATUS FOR PROTECTED PAGE =====")
    st.write(test_resp.status_code)

    st.write("===== DEBUG: FIRST 500 CHARS OF PROTECTED PAGE =====")
    st.write(test_resp.text[:500])

    ###############################################
    # END DEBUG BLOCK
    ###############################################

    return session
