# Hilfe und Updates

## Verbindung prüfen

1. `connection_status` ohne Argumente aufrufen: `data.server_version` ist die laufende
   Serverversion; `configuration_status` ist `configured` oder `incomplete`.
2. `auth_status=unknown` bedeutet nur, dass lokal ein möglicherweise nutzbarer Token liegt.
   `unauthenticated` bedeutet fehlender, lokal abgelaufener oder bereits zurückgewiesener
   Token. Das Tool startet keinen Browser, erneuert keinen Token, fragt kein Werbekonto ab
   und schreibt keine Daten. `live_access` bleibt deshalb immer `not_checked`.
3. Die konkrete Hilfe steht in `next_step`. Für den echten Zugriffstest `list_ad_accounts`
   aufrufen. Auch nach diesem Test bleibt ein späterer lokaler Statusaufruf `not_checked`;
   alte Erfolge werden nicht als aktuelle Verifikation ausgegeben.

App-Client-ID und -Secret aus dem Passwortmanager gehören zusammen. Sie sind getrennt von
der persönlichen LinkedIn-Anmeldung mit `linkedin_login`. Die App muss die Redirect URL
`http://localhost:9876/callback` und die Leserechte `r_ads` / `r_ads_reporting` erlauben.
Bei 401 neu anmelden; bei 403 App-Freischaltung und persönliche Werbekontorolle prüfen.
Für die Ad Library braucht die App zusätzlich das gleichnamige Produkt.

## Versionen und Neustarts

Die Version unter Claudes Erweiterungen ist die **Starter-/Erweiterungsversion**.
`connection_status` zeigt die **Serverversion aus der laufenden Python-Installation**.
Der Starter lädt bei einem vollständigen Claude-Neustart neue stabile 0.x-Serverversionen
von PyPI; ein laufendes Gespräch bleibt auf seiner gestarteten Version. App-Felder und
Token-Datei werden durch normale Serverupdates nicht ersetzt.

Für die neuen Starter-Einstellungen ist einmalig das aktuelle MCPB zu importieren; die
Extension-ID und Feldnamen bleiben gleich. Nicht zuerst deinstallieren oder Tokens löschen.
Danach die vorhandenen Felder kontrollieren. Wer den Starter ab 0.3.2 verwendet, erhält den
neuen Serverstatus auch durch einen normalen Neustart. Ein neuer Starter kann bei Änderungen
an UI, Laufzeit oder der Kompatibilitätsgrenze erneut einen Import erfordern.

Die aktuelle Grenze ist `>=0.3.3,<1` ohne Vorabversionen. Innerhalb 0.x hält dieses Projekt
stdio-Einstiegspunkt, OAuth-App-Felder, Tokenformat und vorhandene Tool-Eingaben kompatibel.
Sie ist keine pauschale Kompatibilitätsgarantie für beliebige künftige Versionssprünge.

## Wenn Updates oder PyPI vorübergehend nicht erreichbar sind

Der normale Start prüft PyPI und garantiert keinen automatischen Offline-Fallback. Eine
bereits laufende Sitzung weiterverwenden und später neu starten; vorhandene Caches und
Einstellungen nicht löschen. Beim ersten Start sind Internet und eine installierte Laufzeit
nötig. Kurz nach einem Release kann der Paketindex noch verzögert aktualisiert sein.

Administratoren können eine **bereits vollständig installierte** Erweiterung mit ihrer
vorhandenen Umgebung über folgenden manuellen stdio-Start weiterverwenden:

```sh
uv run --no-config --directory /PFAD/ZUR/INSTALLIERTEN/ERWEITERUNG --offline --no-sync server/main.py
```

Dabei dieselben App-Einstellungen und gegebenenfalls `LINKEDIN_TOKEN_FILE` beibehalten.
Dieser Fallback aktualisiert nichts und repariert keine fehlenden Pakete; die Netzwerk-
Abfragen an LinkedIn benötigen weiterhin Internet. Nach der Störung zum normalen Starter
zurückwechseln. Eine feste Python-Version lässt sich für Entwickler auch gezielt aus einem
früheren GitHub-Release installieren; ein älteres MCPB ab 0.3.2 allein pinnt den Server nicht.

## Hilfe anfordern

Im [Repository](https://github.com/flin-agency/flin-linkedin-ads-mcp/issues) nur macOS-/Claude-
Version, Starterversion, die fünf Felder von `connection_status` und eine bereinigte
Fehlerbeschreibung nennen. Keine Client-Secrets, Tokens, vollständigen Login-Links,
Kundennamen, Werbekonto-IDs oder rohen API-Antworten in öffentliche Issues kopieren.
Bei belegtem Login-Port doppelte MCP-Installationen deaktivieren. Bei fehlenden Tools
Claude vollständig neu starten und in den Erweiterungseinstellungen die Pflichtfelder prüfen.
