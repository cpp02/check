# Handelsnaam & Domeinchecker — online website

Dit is een kant-en-klare **Streamlit-website** voor het controleren van tientallen Nederlandse namen tegelijk. De app controleert `.nl`-domeinen bij SIDN RDAP; een KVK-zoekcontrole is optioneel en vereist een eigen KVK API-sleutel. BOIP/merknaamonderzoek blijft handmatig.

## Publiceren als online website (zonder eigen server)

1. Maak een (bij voorkeur **privé**) repository op https://github.com/new, bijvoorbeeld `handelsnaamchecker`.
2. Upload **de bestanden in deze map** naar de hoofdmap van die repository, inclusief `app.py`, `requirements.txt` en `.streamlit/config.toml` (de laatste is verborgen op sommige computers). Upload nooit een bestand `secrets.toml` met een echte sleutel.
3. Open https://share.streamlit.io/ en meld je aan met GitHub.
4. Kies **Create app** > **Yup, I have an app** en selecteer de repository, branch `main`, en als main file `app.py`.
5. Druk op **Deploy**. Je krijgt een eigen URL met `.streamlit.app`. Kies de gewenste zichtbaarheid in de app-instellingen. Controleer de actuele beperkingen van gratis/private apps bij Streamlit.
6. Optioneel: voeg bij **Advanced settings > Secrets** de KVK API-sleutel toe als:

   ```toml
   KVK_API_KEY = "jouw-echte-sleutel"
   ```

   Een sleutel kan ook tijdelijk worden ingevuld in de sidebar, maar centraal via Secrets is makkelijker voor meerdere medewerkers.

Meer informatie: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Lokaal testen

Python 3.10 of nieuwer:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Wat deze tool wel en niet doet

- **Domein**: RDAP-status `200` = geregistreerd; `404` = geen registratie gevonden. Dat laatste is **geen garantie** dat registratie mogelijk is. Controleer bij een registrar voordat je registreert.
- **Handelsnaam**: via optionele KVK Zoek API toont de tool mogelijke overeenkomsten, geen definitieve juridische vrijgave. Sterk vergelijkbare namen moeten apart worden onderzocht.
- **Merken**: de officiële KVK/BOIP Naamchecker en BOIP-merkenregister zijn via links te bereiken, maar worden **niet** automatisch uitgelezen.
- **Privacy**: namen worden bij controles verstuurd naar SIDN (en bij ingeschakelde KVK-check naar KVK). Streamlit Cloud draait de app op externe servers. Zet voor intern gebruik de app privé en deel geen gevoelige sleutels.
- **Volumes**: maximaal 200 namen per ronde en beperkte gelijktijdigheid om API-limieten te beperken.

Bronnen: https://www.sidn.nl/en/rdap · https://developers.kvk.nl/ · https://www.kvk.nl/starten/naamchecker/
