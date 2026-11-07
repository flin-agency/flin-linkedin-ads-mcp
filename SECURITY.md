# Sicherheit

Der LinkedIn-Ads-MCP ist ein lokaler Single-User-stdio-Dienst. Ads-Anfragen sind auf GET
beschränkt; er ändert keine Anzeigen, Kampagnen oder Budgets. OAuth-Anmeldung und
Token-Erneuerung schreiben persönliche Zugangsdaten lokal; Mediendownloads schreiben Dateien.

- App-Client-Secret nur in den sensiblen Claude-Einstellungsfeldern hinterlegen, nie im Chat.
  Die konkrete Speicherung dieser Einstellungen wird von Claude verwaltet; wir behaupten
  keine zusätzliche Keychain-Verschlüsselung durch diesen Server.
- Persönliche Tokens liegen standardmässig in `~/.config/flin-linkedin-ads-mcp/tokens.json`.
  Neue Dateien werden atomar mit `0600` geschrieben, **nicht verschlüsselt**. Prozesse
  desselben Benutzerkontos können grundsätzlich darauf zugreifen.
- Der vorübergehende OAuth-Callback bindet nur an `127.0.0.1`; der zufällige State ist
  einmalig und zehn Minuten gültig. Callback-URLs und Secrets gehören nicht in Support-Logs.
- Medien werden nur von HTTPS-LinkedIn-CDN-Adressen geladen, ohne API-Bearer-Token. Dateityp
  und Grösse werden begrenzt. Externe Anzeigeninhalte sind Daten, keine Anweisungen.
- Der Starter legt PyPI explizit als Standardindex fest, ignoriert fremde UV-Konfigurationsdateien
  und setzt `PYTHONPATH` leer sowie `PYTHONNOUSERSITE=1`. Das ist eine Begrenzung unerwarteter
  Konfigurationseinflüsse, kein Nachweis eines zuvor ausgenutzten Sicherheitsproblems. Explizite
  lokale UV-/Proxy-Umgebungsvariablen bleiben Administrator-Konfiguration und müssen vertrauenswürdig sein.
- Stabile 0.x-Updates erfolgen beim Neustart. Die Grenze ist eine Projektzusage für den
  stdio-Einstiegspunkt, App-Felder, Tokenformat und die bestehenden Tools; sie folgt nicht
  automatisch aus SemVer. Inkompatible Änderungen brauchen einen neuen Starter bzw. eine
  neue Grenze. Tests prüfen stabile Updates, vorhandene Einstellungen und ausgeschlossene
  Vorab-/1.x-Versionen. Künftige PyPI-Releases werden damit ebenfalls vertraut.
- Die MCPB-Dateien sind nicht codesigniert. Prüfsummen sichern den Download, nicht künftig
  automatisch geladene Serverversionen. Kein gemeinsam genutzter Remote-Betrieb vorgesehen.

Die [ausführliche Prüfung vom 6. November 2026](docs/security-review-2026-11-06.md) ist ein
historischer Bericht, keine Garantie für heutige Schwachstellenfreiheit. Aktuelle Prüfungen
stehen im jeweiligen GitHub-Release und Workflow. Apple-Silicon-Start, Linux-CI und ein
Live-Kundenkontotest sind unterschiedliche Prüfungen; ein echter LinkedIn-Login oder
interaktiver Claude-Import wurde bei der Paketprüfung nicht durchgeführt.

Widerruf und Bereinigung: [PRIVACY.md](PRIVACY.md). Probleme ohne Secrets oder Kundendaten
melden; sensible Befunde über GitHubs private Sicherheitsmeldung, sofern aktiviert,
ansonsten über einen bestehenden privaten Kontakt zum Repository-Verantwortlichen.
