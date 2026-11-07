# Datenschutz

Der Server läuft lokal auf deinem Computer. Er sendet App-Client-ID, Client-Secret und
OAuth-Code bzw. Refresh-Token zur Anmeldung an LinkedIn. Die App-Zugangsdaten stammen vom
zuständigen Administrator/Passwortmanager; die anschliessende Anmeldung erfolgt mit deinem
persönlichen LinkedIn-Konto. Freigegebene Daten hängen von dessen Werbekontorechten ab.

Ads-Abfragen senden Token und Abfrageparameter an `api.linkedin.com`; angeforderte
Werbekonto-, Kampagnen-, Anzeigen- und Leistungsdaten gehen als Tool-Antwort an Claude.
Je nach Claude-Nutzung verarbeitet Anthropic diese Inhalte. Ad-Library-Inhalte sind externe
Daten. Medien kommen von `*.licdn.com`, ohne Weitergabe des API-Tokens an den CDN.
Python-/Server-Downloads und Update-Prüfungen gehen an PyPI bzw. dessen Paket-CDN; die
Laufzeitbeschaffung übernimmt Claude/UV. Der MCP enthält keine eigene Telemetrie und
sendet keine Werbedaten an flin. Netzwerk-/Proxy-Protokolle des Systems bleiben möglich.

App-Zugangsdaten stehen in Claudes Erweiterungseinstellungen. Persönliche Access-/Refresh-
Tokens liegen unverschlüsselt unter `~/.config/flin-linkedin-ads-mcp/tokens.json` mit privaten
Dateirechten (`0600` beim Schreiben). Medien liegen unter `~/.cache/flin-linkedin-ads-mcp/media`.
Beide Pfade sind durch `LINKEDIN_TOKEN_FILE` bzw. `LINKEDIN_MEDIA_DIR` anpassbar. Ein Update
verändert diese Speicherorte nicht; lokale Medien werden nicht automatisch gelöscht.

**Zugriff beenden:** Die App-Verbindung in den LinkedIn-Kontoeinstellungen bei den erlaubten
Diensten widerrufen; bei einem kompromittierten App-Secret den zuständigen Administrator
um Rotation bitten. Danach Claude vollständig beenden, die Erweiterung deaktivieren oder
entfernen, ihre App-Zugangsdaten aus den Einstellungen entfernen und die persönliche
Token-Datei sowie nicht mehr benötigte Mediendateien löschen (bei eigenen Pfaden dort).
Lokales Löschen allein widerruft keine bei LinkedIn noch gültigen Tokens. Ein neuer Login
ist nach dem Löschen erforderlich. Bereits an Claude übermittelte Inhalte werden durch
lokales Löschen nicht entfernt; dafür die jeweiligen Chat-/Datenkontrollen verwenden.

Referenzen: [LinkedIn-Datenschutz](https://www.linkedin.com/legal/privacy-policy),
[Anthropic-Datenschutz](https://www.anthropic.com/legal/privacy).
