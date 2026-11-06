# flin LinkedIn Ads für Claude Desktop auf dem Mac

## Installation

1. Die Datei **flin-linkedin-ads-mcp-macos.mcpb** aus dem
   [aktuellen GitHub-Release](https://github.com/flin-agency/flin-linkedin-ads-mcp/releases/latest)
   herunterladen und mit Claude Desktop öffnen. Alternativ in Claude unter
   **Einstellungen → Erweiterungen → Erweiterte Einstellungen → Erweiterung installieren**
   auswählen. Die Bezeichnungen können je nach Claude-Version abweichen.
2. Client-ID und Client-Secret der eigenen, für LinkedIn Ads freigeschalteten App in die
   Einstellungsfelder eintragen. Das Secret-Feld ist als sensibel markiert; keine Zugangsdaten
   in den Chat schreiben.
3. In der LinkedIn Developer App muss unter **Auth** exakt
   `http://localhost:9876/callback` als Rückleitungsadresse registriert sein.
4. In einem neuen Chat schreiben: **„Verbinde mich mit LinkedIn Ads.“** Den von
   `linkedin_login` zurückgegebenen Link auf demselben Mac öffnen und anmelden.
5. Danach: **„Zeige mir meine LinkedIn-Werbekonten.“** Das prüft den tatsächlichen Zugriff.

Eine aktuelle Claude-Desktop-Version mit Unterstützung für MCPB 0.4 und die verwaltete
UV-Laufzeit ist erforderlich. Python muss nicht manuell installiert werden. Beim ersten
Start ist Internetzugang für die Laufzeit und die Python-Abhängigkeiten erforderlich.
Das Paket ist für Apple Silicon und Intel vorgesehen; der lokale Start wurde auf Apple
Silicon geprüft. Ein separater Intel-Mac und der Login in einem realen Werbekonto wurden
für dieses Release nicht getestet.

Die App benötigt `r_ads` und `r_ads_reporting`. Das eigene LinkedIn-Konto braucht Zugriff
auf die Werbekonten. Die Ad Library setzt zusätzlich das freigeschaltete Produkt
**LinkedIn Ad Library** voraus. Eine bestehende manuelle Installation dieses MCP vorher
deaktivieren, um doppelte Tools und einen belegten Callback-Port zu vermeiden.

## Sicherheit und Updates

Das Paket enthält den geprüften Servercode der Version **0.3.1** und eine `uv.lock`-Datei
mit festen Abhängigkeitsversionen und Paket-Hashes. Beim Start wird `uv run --locked`
verwendet. Es wird keine beliebige neueste Serverversion von PyPI nachgeladen. Updates
werden durch die Installation einer neuen MCPB-Datei vorgenommen; Sicherheitsupdates
müssen deshalb aktiv eingespielt werden.

Der Server verändert keine LinkedIn-Anzeigen, Kampagnen oder Budgets. Er liest Daten und
kann ausgewählte Medien lokal speichern. Login und Token-Erneuerung schreiben lokale
Zugangsdaten. Die Anmeldung öffnet kurzzeitig einen HTTP-Callback ausschliesslich auf
`127.0.0.1`, geschützt durch einen zufälligen, einmaligen OAuth-State.

Persönliche Tokens liegen in `~/.config/flin-linkedin-ads-mcp/tokens.json` mit Dateirechten
`0600`. Diese Datei ist **nicht verschlüsselt**. Medien liegen standardmässig unter
`~/.cache/flin-linkedin-ads-mcp/media` und werden nicht automatisch gelöscht. Der Server
ist für einen einzelnen lokalen Benutzer vorgesehen, nicht als gemeinsamer Remote-Dienst.

Ausgewählte Werbekontodaten werden als Tool-Antwort an Claude übergeben. Anzeigeninhalte
und API-Antworten sind externe Daten und dürfen nicht als Anweisungen behandelt werden.
Das Paket enthält keine persönlichen Zugangsdaten oder Werbekontodaten und ist nicht
codesigniert. `SHA256SUMS` im Release ermöglicht die Prüfung auf unveränderte Downloads:

```sh
shasum -a 256 -c SHA256SUMS
```

## Beispiele

- „Zeige mir die Kampagnenleistung der letzten 30 Tage.“
- „Zeige mir meine Anzeigen inklusive Bildern.“
- „Suche in der LinkedIn Ad Library nach Anzeigen von Microsoft in Deutschland.“

## Paket reproduzierbar bauen

Aus dem Repository-Hauptverzeichnis:

```sh
uv sync --locked --extra dev
uv run python scripts/build_desktop_extension.py
npx --yes @anthropic-ai/mcpb@2.1.2 validate desktop-extension/manifest.json
uv run python scripts/smoke_desktop_extension.py
```

Der Builder verwendet eine ausdrückliche Dateiliste und kopiert den Servercode aus `src`.
Lokale Konfiguration, Tokens, Entwicklungsumgebungen und Build-Caches werden nicht gepackt.

Referenzen:
- [MCPB-Format und UV-Laufzeit](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
- [Lokale MCP-Server in Claude Desktop](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [LinkedIn-Datenschutzerklärung](https://www.linkedin.com/legal/privacy-policy)
