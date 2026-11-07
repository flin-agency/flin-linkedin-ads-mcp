# flin LinkedIn Ads für Claude Desktop

Für Apple Silicon (M1 oder neuer); Intel-Macs bleiben unterstützt. Aktuelles Claude Desktop
mit MCPB-0.4-/UV-Unterstützung und Internetzugang erforderlich. Python wird von Claude/UV
verwaltet und muss für die Erweiterung nicht separat installiert werden.

1. [Paket herunterladen](https://github.com/flin-agency/flin-linkedin-ads-mcp/releases/latest/download/flin-linkedin-ads-mcp.mcpb)
   und mit Claude Desktop öffnen. Alternativ unter Einstellungen → Desktop-App → Erweiterungen
   verwalten → Erweiterte Einstellungen → Erweiterung installieren auswählen.
2. Client-ID und Client-Secret der LinkedIn-App aus dem Passwortmanager in die beiden Felder
   eintragen. Zuständigen Administrator fragen, falls sie fehlen; niemals in den Chat schreiben.
3. Persönlich mit `linkedin_login` anmelden: den Link auf demselben Mac öffnen und das eigene
   LinkedIn-Konto verwenden. Dieses braucht Werbekontozugriff. Die App muss `r_ads` und
   `r_ads_reporting` sowie `http://localhost:9876/callback` als Redirect erlauben.
4. `connection_status` zeigt die laufende Serverversion und den lokalen Zustand. Danach
   `list_ad_accounts` ausführen; nur dieser erfolgreiche Aufruf bestätigt Live-Zugriff.

## Versionen und Updates

Die Starterversion ist die im Manifest/Claude angezeigte Erweiterungsversion.
`connection_status` liefert im Feld `data.server_version` die tatsächlich laufende
Serverversion. Sie kann nach einem Update neuer sein als die Starterversion.

Der Starter lädt beim vollständigen Claude-Neustart stabile Serverversionen `>=0.3.3,<1`
von PyPI. Vorabversionen sind ausgeschlossen. Innerhalb dieses Bereichs hält das Projekt
den stdio-Einstiegspunkt, App-Felder, Tokenformat und bisherige Tools kompatibel; 0.x allein
ist keine allgemeine SemVer-Garantie. Neue Versionen werden geprüft. Ein laufender Server
wird nicht mitten im Gespräch ausgetauscht. Einstellungen und Tokens werden weiterverwendet.

**Einmalig das neue MCPB importieren**, um auch die neuen Starter-Einstellungen zu erhalten.
Extension-ID und Feldnamen sind unverändert; nicht vorher deinstallieren oder Tokens löschen.
Bestehende Starter ab 0.3.2 bekommen den neuen Server samt `connection_status` bereits beim
Neustart. Spätere UI-/Starter-Änderungen können erneut einen Import benötigen.

Beim Start wird PyPI geprüft. Caches werden weiterverwendet, ein automatischer Offline-
Fallback ist aber nicht garantiert. Eine laufende Sitzung weiterverwenden oder später
neu starten. Ein Administrator kann eine bereits installierte Umgebung mit
`uv run --no-config --directory /PFAD/ZUR/ERWEITERUNG --offline --no-sync server/main.py`
weiterverwenden; App-Einstellungen unverändert übergeben. LinkedIn-Abfragen benötigen
weiterhin Netzwerk. Details: [Support](https://github.com/flin-agency/flin-linkedin-ads-mcp/blob/main/SUPPORT.md).

## Daten und Sicherheit

Persönliche Tokens: `~/.config/flin-linkedin-ads-mcp/tokens.json`, atomar mit `0600`
geschrieben, **nicht verschlüsselt**. Medien: `~/.cache/flin-linkedin-ads-mcp/media`.
Die App-Zugangsdaten verwaltet Claude in seinen Erweiterungseinstellungen. Der Server
verändert keine Ads-Daten; Login und Medienabruf schreiben lokale Dateien.

Die Pakete sind nicht codesigniert. Alle drei Downloadnamen enthalten identische Bytes:
`flin-linkedin-ads-mcp.mcpb`, der bisherige Name `flin-linkedin-ads-mcp-macos.mcpb` und der
jeweilige versionierte Name. Mit allen Dateien und `SHA256SUMS` im selben Ordner lässt sich
`shasum -a 256 -c SHA256SUMS` ausführen. Diese Prüfsumme fixiert nicht spätere PyPI-Updates.

[Datenschutz und Widerruf](https://github.com/flin-agency/flin-linkedin-ads-mcp/blob/main/PRIVACY.md) ·
[Sicherheit](https://github.com/flin-agency/flin-linkedin-ads-mcp/blob/main/SECURITY.md)

## Entwicklung

```sh
uv sync --locked --extra dev
uv run python -m build
uv run python scripts/build_desktop_extension.py
npx --yes @anthropic-ai/mcpb@2.1.2 validate desktop-extension/manifest.json
uv run python scripts/smoke_desktop_extension.py --wheel dist/*.whl --upgrade-from 0.3.2
```

Nach Veröffentlichung denselben Starttest ohne `--wheel` gegen öffentliches PyPI ausführen.
Apple-Silicon-Start, Linux-CI und ein echter Kundenkontotest sind getrennte Prüfschritte;
es wird kein Kundenlogin durch diesen Starttest ausgeführt.
