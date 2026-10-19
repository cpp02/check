import csv
import io
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Handelsnaam & Domeinchecker", page_icon="🔎", layout="wide")
st.title("🔎 Handelsnaam & Domeinchecker")
st.markdown("**Controleer tot 200 namen in één keer** en exporteer de uitkomsten naar Excel/CSV.")
st.caption("Vooronderzoek voor Nederlandse handelsnamen en .nl-domeinen. Resultaten zijn geen juridische vrijgave of registratiegarantie.")

SIDN_RDAP = "https://rdap.sidn.nl/domain/"
KVK_URL = "https://api.kvk.nl/api/v2/zoeken"


def normaliseer_domein(naam: str) -> str:
    naam = naam.lower().strip()
    naam = re.sub(r"^https?://", "", naam)
    naam = naam.split("/")[0]
    if naam.endswith(".nl"):
        naam = naam[:-3]
    naam = re.sub(r"\s+", "", naam)
    try:
        naam = naam.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    if len(naam) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", naam):
        return ""
    return naam + ".nl"


def domein_check(domein: str, timeout=12) -> tuple[str, str]:
    if not domein:
        return "Ongeldig", "Geen geldige .nl-domeinnaam"
    try:
        res = requests.get(
            SIDN_RDAP + quote(domein, safe=".-"),
            headers={"Accept": "application/rdap+json", "User-Agent": "Handelsnaamchecker/1.0"},
            timeout=timeout,
        )
        if res.status_code == 200:
            return "Geregistreerd", "RDAP-record gevonden"
        if res.status_code == 404:
            return "Geen registratie gevonden", "RDAP 404; controleer beschikbaarheid nogmaals bij SIDN/registrar"
        if res.status_code == 429:
            return "Onbekend", "Limiet bereikt bij SIDN (HTTP 429)"
        return "Onbekend", f"SIDN HTTP {res.status_code}"
    except requests.RequestException as ex:
        return "Onbekend", f"Verbinding mislukt: {type(ex).__name__}"


def kvk_check(naam: str, api_key: str, timeout=12) -> tuple[str, str]:
    if not api_key:
        return "Niet gecontroleerd", "KVK API-sleutel ontbreekt"
    try:
        res = requests.get(
            KVK_URL,
            params={"naam": naam, "pagina": 1},
            headers={"apikey": api_key, "Accept": "application/json"},
            timeout=timeout,
        )
        if res.status_code == 200:
            data = res.json()
            items = data.get("resultaten", [])
            matches = [str(x.get("naam", "")) for x in items if x.get("naam")]
            if matches:
                return "Mogelijke overeenkomst(en)", "; ".join(matches[:5])
            return "Geen resultaat", "Geen resultaten voor deze zoekterm; geen juridische garantie"
        if res.status_code in (401, 403):
            return "Niet gecontroleerd", "KVK API-sleutel of toegang ongeldig"
        if res.status_code == 429:
            return "Niet gecontroleerd", "KVK API-limiet bereikt"
        return "Niet gecontroleerd", f"KVK HTTP {res.status_code}"
    except (requests.RequestException, ValueError) as ex:
        return "Niet gecontroleerd", f"KVK-fout: {type(ex).__name__}"


def zoeklinks(naam: str) -> tuple[str, str]:
    return (
        "https://www.kvk.nl/starten/naamchecker/",
        "https://www.boip.int/nl/merkenregister",
    )


def check_naam(naam: str, api_key: str, doe_kvk: bool) -> dict:
    domein = normaliseer_domein(naam)
    d_status, d_toelichting = domein_check(domein)
    k_status, k_toelichting = kvk_check(naam, api_key) if doe_kvk else ("Niet gecontroleerd", "KVK-controle uitgeschakeld")
    kvk_link, boip_link = zoeklinks(naam)
    return {
        "Handelsnaam": naam,
        "Domein": domein or "Ongeldig",
        "Domeinstatus": d_status,
        "Domeintoelichting": d_toelichting,
        "KVK-status": k_status,
        "KVK-resultaat": k_toelichting,
        "KVK/BOIP Naamchecker": kvk_link,
        "BOIP merkenregister": boip_link,
        "SIDN controle": f"https://www.sidn.nl/" if not domein else "https://www.sidn.nl/",
    }

st.info("⚠️ 'Geen registratie gevonden' is niet hetzelfde als definitief registreerbaar. Een KVK-hit is evenmin automatisch een juridisch conflict. Controleer altijd spellingvarianten en merkenrechten.")

with st.sidebar:
    st.header("Instellingen")
    try:
        configured_key = st.secrets.get("KVK_API_KEY", "")
    except (FileNotFoundError, KeyError):
        configured_key = ""
    if configured_key:
        st.success("KVK API-sleutel ingesteld op de server")
        api_key = configured_key
    else:
        api_key = st.text_input("KVK API-key (optioneel)", type="password", help="Voeg de sleutel bij voorkeur toe via Streamlit Cloud > Secrets. Niet rechtstreeks in broncode plaatsen.")
    doe_kvk = st.checkbox("KVK via API controleren", value=False)
    workers = st.slider("Parallelle domeinchecks", 1, 8, 3)
    st.markdown("[KVK API aanvragen](https://developers.kvk.nl/)  ")
    st.markdown("[Officiële KVK/BOIP Naamchecker](https://www.kvk.nl/starten/naamchecker/)  ")
    st.markdown("[SIDN domeincheck](https://www.sidn.nl/)")

raw = st.text_area("Handelsnamen (één per regel)", height=230, placeholder="Wolkwerf\nHosthaven\nDomeinsteiger")
st.caption("Voorbeeld: ‘Mijn Hosting’ wordt mijnhosting.nl. Alleen .nl wordt gecontroleerd.")
upload = st.file_uploader("Of upload een CSV/TXT met één naam per regel", type=["csv", "txt"])

if st.button("Controleer namen", type="primary"):
    names = []
    if raw.strip():
        names.extend(x.strip() for x in raw.splitlines() if x.strip())
    if upload is not None:
        content = upload.getvalue().decode("utf-8-sig", errors="replace")
        for row in csv.reader(io.StringIO(content)):
            if row and row[0].strip():
                names.append(row[0].strip())
    names = list(dict.fromkeys(names))
    if not names:
        st.warning("Voer minstens één naam in.")
    elif len(names) > 200:
        st.error("Maximaal 200 unieke namen per ronde, om onnodige API-belasting te voorkomen.")
    else:
        results = []
        progress = st.progress(0)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(check_naam, n, api_key.strip(), doe_kvk): n for n in names}
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    results.append(future.result())
                except Exception as ex:
                    results.append({"Handelsnaam": futures[future], "Domeinstatus": "Onbekend", "Domeintoelichting": type(ex).__name__})
                progress.progress(i / len(names))
        order = {n: i for i, n in enumerate(names)}
        results.sort(key=lambda row: order[row["Handelsnaam"]])
        df = pd.DataFrame(results)
        st.subheader(f"Resultaten ({len(df)} namen)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download resultaten als CSV", data=df.to_csv(index=False).encode("utf-8-sig"), file_name="handelsnaamchecker_resultaten.csv", mime="text/csv")
        st.caption("Controleer namen met 'Geen registratie gevonden' bij een registrar voordat je registreert. Handelsnaam- en merkenonderzoek blijft noodzakelijk.")
