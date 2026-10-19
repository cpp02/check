import csv
import io
import ipaddress
import re
import unicodedata
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, quote_plus, urljoin, urlsplit

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='Handelsnaam & Domeinchecker', page_icon='🔎', layout='wide')
st.title('🔎 Handelsnaam & Domeinchecker')
st.write('Controleer tot 200 .nl-namen met **gratis DNS- en websitecheck**, optionele **gratis SIDN RDAP-controle**, openbare zoeklinks en CSV-export. Geen betaalde API nodig.')
st.caption('Een websitecheck is een goedkope voorselectie, geen bewijs dat een domeinnaam vrij is.')

SIDN_RDAP = 'https://rdap.sidn.nl/domain/'
HEADERS = {'User-Agent': 'Handelsnaamchecker/2.0 (website prescreen)', 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}


def normaliseer_domein(naam):
    value = naam.lower().strip()
    value = re.sub(r'^https?://', '', value)
    value = value.split('/')[0].split(':')[0].rstrip('.')
    if value.endswith('.nl'):
        value = value[:-3]
    value = re.sub(r'\s+', '', value)
    try:
        value = value.encode('idna').decode('ascii')
    except UnicodeError:
        return ''
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', value):
        return ''
    return value + '.nl'


def resolve_public(host):
    try:
        addresses = {i[4][0] for i in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
        if not addresses:
            return [], 'Geen A/AAAA-adres'
        # Never make server-side HTTP requests to private/loopback/link-local destinations.
        if any(not ipaddress.ip_address(x).is_global for x in addresses):
            return sorted(addresses), 'Niet-publiek IP-adres; HTTP-check geblokkeerd'
        return sorted(addresses), ''
    except socket.gaierror:
        return [], 'Geen A/AAAA-adres gevonden'
    except OSError as e:
        return [], f'DNS-fout ({type(e).__name__})'


def website_check(domein, timeout=4):
    if not domein:
        return {'Website': 'Ongeldige naam', 'Selectie': 'Afkeuren', 'Eind-URL': '', 'HTTP': '', 'IP-adres(sen)': '', 'Website-opmerking': 'Geen geldige .nl-naam'}
    ips, reason = resolve_public(domein)
    base = {'Website': '', 'Selectie': '', 'Eind-URL': '', 'HTTP': '', 'IP-adres(sen)': ', '.join(ips), 'Website-opmerking': reason}
    if reason:
        base.update({'Website': 'Niet vastgesteld', 'Selectie': 'Verder controleren'})
        return base
    # GET with stream=True: only headers are needed; avoid downloading entire sites.
    # Resolve and validate every redirect hop; block local-network targets.
    for scheme in ('https', 'http'):
        url = f'{scheme}://{domein}/'
        for _ in range(5):
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                break
            _, bad = resolve_public(parsed.hostname)
            if bad:
                base['Website-opmerking'] = f'Doorverwijzing niet veilig/controleerbaar: {bad}'
                break
            try:
                with requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=False, stream=True) as r:
                    status = r.status_code
                    if 300 <= status < 400 and r.headers.get('Location'):
                        url = urljoin(url, r.headers['Location'])
                        continue
                    base['Eind-URL'] = url
                    base['HTTP'] = str(status)
                    if status in (404, 410):
                        base.update({'Website': 'Geen bruikbare pagina', 'Selectie': 'Verder controleren', 'Website-opmerking': 'Server antwoordt, maar pagina ontbreekt; domein kan geregistreerd zijn'})
                    else:
                        base.update({'Website': 'Website / HTTP-reactie gevonden', 'Selectie': 'Afkeuren', 'Website-opmerking': 'Een webserver geeft een HTTP-reactie; niet selecteren volgens de ingestelde filterregel'})
                    return base
            except requests.RequestException as e:
                base['Website-opmerking'] = f'Verbindingsprobleem: {type(e).__name__}'
                break
        else:
            base['Website-opmerking'] = 'Te veel doorverwijzingen'
    base.update({'Website': 'Geen website bevestigd', 'Selectie': 'Verder controleren'})
    return base


def domein_check(domein, timeout=8):
    if not domein:
        return 'Ongeldig', 'Geen geldige .nl-domeinnaam'
    try:
        r = requests.get(SIDN_RDAP + quote(domein, safe='.-'), headers={'Accept': 'application/rdap+json', 'User-Agent': 'Handelsnaamchecker/2.0'}, timeout=timeout)
        if r.status_code == 200:
            return 'Geregistreerd', 'SIDN RDAP-record gevonden'
        if r.status_code == 404:
            return 'Geen registratie gevonden', 'Bij registrar opnieuw controleren'
        if r.status_code == 429:
            return 'Onbekend', 'SIDN-limiet bereikt (429)'
        return 'Onbekend', f'SIDN HTTP {r.status_code}'
    except requests.RequestException as e:
        return 'Onbekend', type(e).__name__


def check_naam(naam, use_sidn, skip_found):
    domein = normaliseer_domein(naam)
    web = website_check(domein)
    skip = skip_found and web['Selectie'] == 'Afkeuren'
    if use_sidn and not skip:
        rdap_status, rdap_note = domein_check(domein)
    else:
        rdap_status, rdap_note = 'Overgeslagen', 'Uitgeschakeld of website gevonden'
    if rdap_status == 'Geregistreerd':
        web['Selectie'] = 'Afkeuren'
    return {
        'Handelsnaam': naam, 'Domein': domein or 'Ongeldig',
        'Selectie': web['Selectie'], 'Website': web['Website'],
        'Eind-URL': web['Eind-URL'], 'HTTP': web['HTTP'],
        'IP-adres(sen)': web['IP-adres(sen)'],
        'Website-opmerking': web['Website-opmerking'],
        'SIDN-status': rdap_status, 'SIDN-opmerking': rdap_note,
        'Handelsnaamindicatie': 'Niet automatisch gecontroleerd',
        'Zoeklink Google': 'https://www.google.com/search?q=' + quote_plus('"'+naam+'"'),
        'Zoeklink Bing': 'https://www.bing.com/search?q=' + quote_plus('"'+naam+'"'),
        'Zoeklink DuckDuckGo': 'https://duckduckgo.com/?q=' + quote_plus('"'+naam+'"'),
        'Zoeklink KVK': 'https://www.kvk.nl/zoeken/',
        'KVK/BOIP Naamchecker': 'https://www.kvk.nl/starten/naamchecker/',
        'BOIP merkenregister': 'https://www.boip.int/nl/merkenregister'
    }


st.info('**Let op:** geen website ≠ vrij domein ≠ vrije handelsnaam. De automatische controle onderzoekt DNS/HTTP en eventueel SIDN, **niet** bestaande handelsnamen of merken. Gebruik de zoeklinks en controleer de shortlist in de officiële registers.')
with st.sidebar:
    st.header('Instellingen (alles gratis)')
    use_sidn = st.checkbox('Optioneel: SIDN RDAP-check voor overgebleven namen', value=False, help='Geen sleutel nodig; de openbare dienst kan verzoeken beperken (HTTP 429).')
    skip_found = st.checkbox('Sla SIDN-check over bij gevonden website', value=True)
    workers = st.slider('Gelijktijdige websitechecks', 1, 5, 2)
    st.caption('Geen KVK-, Brave- of andere betaalde API nodig. Handelsnaam- en merkzoeklinks staan in het CSV-bestand. Zoekmachines worden niet automatisch gescrapet.')

raw = st.text_area('Handelsnamen (één per regel)', height=230, placeholder='DomeinKompas\nHostBaken\nWebHaven')
upload = st.file_uploader('Of importeer CSV/TXT met naam in eerste kolom', type=['csv', 'txt'])
if st.button('Controleer namen', type='primary'):
    names = [x.strip() for x in raw.splitlines() if x.strip()]
    if upload is not None:
        for row in csv.reader(io.StringIO(upload.getvalue().decode('utf-8-sig', errors='replace'))):
            if row and row[0].strip():
                names.append(row[0].strip())
    names = list(dict.fromkeys(names))
    if not names:
        st.warning('Voer minimaal één naam in.')
    elif len(names) > 200:
        st.error('Maximaal 200 namen per ronde.')
    else:
        rows = []
        progress = st.progress(0)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(check_naam, n, use_sidn, skip_found): n for n in names}
            for i, job in enumerate(as_completed(jobs), 1):
                try:
                    rows.append(job.result())
                except Exception as e:
                    rows.append({'Handelsnaam': jobs[job], 'Selectie': 'Nader onderzoeken', 'Website-opmerking': f'Onverwachte fout: {type(e).__name__}', 'Handelsnaamindicatie': 'Niet automatisch gecontroleerd'})
                progress.progress(i / len(names))
        order = {n: i for i, n in enumerate(names)}
        rows.sort(key=lambda r: order[r['Handelsnaam']])
        df = pd.DataFrame(rows)
        st.session_state['results'] = df

if 'results' in st.session_state:
    df = st.session_state['results']
    rejected = (df['Selectie'] == 'Afkeuren').sum()
    st.subheader(f'Resultaten: {len(df)} namen · {rejected} afgevallen · {len(df) - rejected} nader te controleren')
    st.dataframe(df, use_container_width=True, hide_index=True)
    remaining = df[df['Selectie'] != 'Afkeuren']
    st.download_button('Download alle resultaten (CSV)', df.to_csv(index=False).encode('utf-8-sig'), 'websitechecker-alle-resultaten.csv', 'text/csv')
    st.download_button('Download overgebleven namen (CSV)', remaining.to_csv(index=False).encode('utf-8-sig'), 'websitechecker-overgebleven.csv', 'text/csv')
    st.caption('Namen die overblijven zijn kandidaten voor verdere controle, niet automatisch beschikbaar voor registratie.')
