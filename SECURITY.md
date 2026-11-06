# Sicherheitsprüfung – v0.3.1

Prüfdatum: 6. November 2026. Umfang: Python-Server, Tool-Dispatcher und Eingabeprüfung,
OAuth-Anmeldung und Token-Speicherung, API-Client, Medien-Downloads, Abhängigkeiten,
Git-Historie, Desktop-Paket und GitHub-Workflows. Dies ist eine interne Code- und
Paketprüfung, keine unabhängige Zertifizierung oder Garantie für Schwachstellenfreiheit.

## Behobene Befunde

| Befund | Änderung |
| --- | --- |
| Bekannte Schwachstellen in installierten Abhängigkeiten | Aktualisierung, insbesondere MCP 1.30.0; feste Versionen und Hashes in beiden `uv.lock`-Dateien. |
| Desktop-Launcher lud bei jedem Start neue Serverversionen | Servercode liegt jetzt im MCPB; `uv run --locked` verhindert ungeprüfte Versionssprünge. |
| Read-only nur durch Tool-Auswahl abgesichert | HTTP-Client erlaubt ausschliesslich GET ohne Request-Body; zusätzliche Regressionstests. |
| API-Weiterleitungen und Pfadnormalisierung nicht ausdrücklich gesperrt | Weiterleitungen, absolute URLs und Traversal-Pfade werden vor weiteren Requests blockiert. |
| Provider-Fehler konnten Zugangsdaten wiedergeben | Bekannte Access-/Refresh-Tokens und Client-Secrets werden aus verschachtelten Fehlern entfernt; unerwartete Fehler werden ohne sensible Tracebacks protokolliert. |
| Dekompression konnte vor der Medien-Grössenprüfung Speicher belegen | Komprimierte HTTP-Medienantworten werden abgewiesen; bereits vorhandene Dateityp-, Grössen- und CDN-Prüfungen bleiben aktiv. |
| Bewegliche GitHub-Actions-Versionen und breite Release-Rechte | Actions auf Commit-SHAs fixiert; Build, GitHub-Release und PyPI-Publishing mit getrennten Rechten. |

## Verifikation

- 182 automatisierte Tests, Lint und Typecheck erfolgreich lokal ausgeführt.
- Laufzeitabhängigkeiten aus der Desktop-Sperrdatei mit `pip-audit` geprüft: keine bekannten
  Schwachstellen im Abgleich am Prüfdatum. Das Ergebnis ist zeitabhängig; CI prüft erneut.
- Gitleaks 8.30.1 über 30 bestehende Commits: zwei Treffer ausschliesslich für den
  README-Platzhalter `DEIN_ACCESS_TOKEN`; nach enger Platzhalter-Ausnahme keine Treffer.
- Reproduzierbarer MCPB-Build mit ausdrücklicher Dateiliste; Quellcode im Archiv wird
  bytegenau gegen `src` geprüft. Kein Verpacken des ganzen Arbeitsverzeichnisses.
- Manifest mit dem offiziellen MCPB-Werkzeug 2.1.2 validiert.
- Frischer Start des entpackten MCPB auf macOS/Apple Silicon über stdio: Initialisierung,
  Liste aller 16 Tools, Login-Status ohne Zugangsdaten und Ablehnung nicht authentifizierter
  API-Zugriffe erfolgreich.
- Python-Wheel und Quelldistribution gebaut und mit `twine check` geprüft.

Die GitHub-Workflows testen zusätzlich auf Linux/Python 3.11 und 3.12 sowie macOS/Python
3.13. Der Release-Build läuft auf macOS und prüft das tatsächlich veröffentlichte Paket.

## Schutzgrenzen

- Der Server ist ein lokaler Single-User-stdio-Dienst. Er ist kein gehärteter Remote- oder
  Multi-Tenant-Server. Die Kontoberechtigungen werden von LinkedIn durchgesetzt.
- Der OAuth-Callback bindet nur an `127.0.0.1`. Zufälliger State, zehn Minuten Gültigkeit,
  einmalige Verwendung und keine Callback-URL-Logs schützen die Anmeldung.
- Token-Dateien werden atomar mit `0600` geschrieben, sind jedoch nicht verschlüsselt.
  Andere Prozesse desselben Benutzerkontos können grundsätzlich darauf zugreifen.
- Die MCPB-Konfiguration markiert das Client-Secret als sensibel. Das Paket enthält kein
  gemeinsames App-Secret. Nutzer müssen Zugangsdaten ihrer eigenen LinkedIn-App hinterlegen.
- API-Token werden nicht an Medien-CDNs weitergegeben. Medien-Downloads erlauben nur
  HTTPS unter `.licdn.com` und prüfen jedes Redirect-Ziel. Dies setzt vertrauenswürdiges
  DNS/TLS und eine vertrauenswürdige lokale Netzwerk-/Proxy-Konfiguration voraus.
- Lokale Mediendateien werden nicht automatisch gelöscht; Dateisignaturen sind keine
  vollständige Prüfung auf schädliche Inhalte. Betrachter müssen aktuell gehalten werden.
- Werbekontodaten und externe Anzeigeninhalte gelangen über Tool-Antworten an den MCP-Client.
  Externe Inhalte sind untrusted data, keine Anweisungen an den Assistenten.
- Das MCPB ist nicht codesigniert. Die veröffentlichte SHA-256-Prüfsumme dient der
  Integritätsprüfung, ersetzt aber keine Herausgeber-Signatur.
- Kein echter LinkedIn-Login, keine Live-Werbekontodaten, kein separater Intel-Mac und kein
  interaktiver Import in Claude Desktop wurden für diese Prüfung verwendet.
- Feste Versionen brauchen bewusste Sicherheitsupdates: Abhängigkeiten aktualisieren,
  erneut prüfen und eine neue MCPB-Version installieren. Bestehende Installationen
  aktualisieren sich nicht still im Hintergrund.

## Sicherheitsprobleme melden

Keine Zugangsdaten in öffentlichen Issues veröffentlichen. Für vertrauliche Meldungen
GitHubs private Sicherheitsmeldung verwenden, sofern im Repository aktiviert, andernfalls
den Repository-Verantwortlichen über einen bestehenden privaten Kontakt erreichen.
