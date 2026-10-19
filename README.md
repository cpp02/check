# Handelsnaam- en domeinchecker — 100% gratis

Streamlit-website voor het filteren van maximaal 200 namen per ronde, zonder betaalde API-sleutels.

## Online publiceren

1. Pak ZIP uit en upload **de bestanden uit de map** naar een GitHub-repository.
2. Maak een app via https://share.streamlit.io met `app.py` als entrypoint.
3. Voer namen in (één per regel) of upload een CSV/TXT. Start de controle.
4. Export: alle resultaten of alleen kandidaten die niet zijn afgekeurd.

Voor lokaal gebruik: `pip install -r requirements.txt` en `streamlit run app.py`.

## Wat wordt wel automatisch gecontroleerd?

- DNS-resolutie, website via HTTPS/HTTP, HTTP-code en doorverwijzingen. Reactie van webserver (behalve 404/410) = afkeuren volgens jouw filter.
- Optioneel publieke SIDN RDAP; geen account/API-key vereist, maar rate limiting is mogelijk (429). 
- Bij gevonden SIDN-registratie wordt de naam afgekeurd. Geen registratie gevonden via RDAP betekent **niet** dat registratie is gegarandeerd.
- Fouten en onbereikbaarheid krijgen een eigen status; worden niet als 'vrij' aangeduid.

## Wat wordt NIET automatisch gecontroleerd?

- Handelsregister, KVK, merkenregister of zoekmachinevermeldingen: daar is zonder geschikte toegang geen betrouwbare gratis bulk-API voor. We **scrapen geen websites** en omzeilen geen limieten.
- In de tabel/CSV staan directe zoeklinks naar Google, Bing, DuckDuckGo, KVK en BOIP om overgebleven kandidaten snel handmatig te toetsen.

**Belangrijk:** geen actieve site betekent niet dat het domein of de handelsnaam beschikbaar is. Gebruik voor definitieve selectie officiële controles en een registrar. De app registreert niets.

## Technische aandachtspunten

De HTTP-check blokkeert IP-adressen die niet publiek routeerbaar zijn en controleert opnieuw bij redirects, maar is geen volledig afgeschermde browser. Gebruik bij voorkeur een gescheiden hostingomgeving. De applicatie is syntax-getest, niet live getest vanaf jouw Streamlit-server.
