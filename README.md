# flin-linkedin-ads-mcp

`flin-linkedin-ads-mcp` ist ein strikt read-only MCP Server für LinkedIn Ads.
Er ist dafür gebaut, direkt in Claude über MCP eingebunden und getestet zu werden.

## Features

- Read-only Zugriff auf LinkedIn Ads Daten
- Ad Accounts lesen
- Campaign Groups lesen
- Campaigns lesen
- Creatives lesen
- Share-Content lesen (`get_share_content`, best effort für Bild-URLs)
- Insights/Analytics lesen
- Company Intelligence lesen (`/accountIntelligence`, private API Access nötig)
- Öffentliche Anzeigen in der LinkedIn Ad Library suchen (`search_ad_library`)
- Als Markenpartnerschaft gekennzeichnete Beiträge suchen (`search_brand_partnerships`)
- Direkter LinkedIn-Login und Reconnect über `linkedin_login`
- Automatische Token-Erneuerung, falls LinkedIn einen Refresh-Token ausstellt
- Keine Schreiboperationen an Werbekonten oder Kampagnen in `v0.x`

## Neu in `v0.2.0`

- Ad-Library-Suche und Markenpartnerschafts-Suche mit Filtern und Seitennavigation.
- Anzeigenbilder über Creative-Metadaten ab API-Version `202610`, auch ohne Posts-Zugriff.
- Aktuelle Posts-/Images-Abfragen statt des alten Share-Endpunkts.
- API-Version `202610` als neuer Standard und verständliche Hinweise bei inaktiven Versionen.

Bestehende Installationen mit explizitem `LINKEDIN_API_VERSION` müssen diesen Wert auf
`202610` setzen, um die neue Bildauflösung zu nutzen. Anschliessend den MCP-Client neu starten.
Die Ad Library benötigt eine separate Produktfreischaltung der LinkedIn App. Die Bildadressen
bleiben externe URLs; eine Sperre externer Bilder im Dashboard wird dadurch nicht aufgehoben.

## Scope `v0.x` (strict read-only)

- Kein Create/Update/Delete
- Kein Pause/Resume
- Kein generischer Proxy-Endpunkt
- Authentifizierungs-Tools speichern ausschliesslich lokale Zugangsdaten; Ads-Daten bleiben read-only

## Direkt in Claude testen

### Variante A: Lokal aus diesem Repo (empfohlen zum Entwickeln)

In Claude:
1. `Settings` öffnen
2. `Developer` öffnen
3. MCP Config bearbeiten
4. Diesen Server eintragen:

```json
{
  "mcpServers": {
    "flin-linkedin-ads-mcp-local": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/nicolasg/Antigravity/flin-linkedin-ads-mcp",
        "flin-linkedin-ads-mcp"
      ],
      "env": {
        "LINKEDIN_CLIENT_ID": "DEINE_APP_CLIENT_ID",
        "LINKEDIN_CLIENT_SECRET": "DEIN_APP_CLIENT_SECRET",
        "LINKEDIN_REDIRECT_URI": "http://localhost:9876/callback",
        "LINKEDIN_API_VERSION": "202610",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

In der LinkedIn Developer App unter **Auth** zuerst exakt `http://localhost:9876/callback`
als Redirect URL eintragen. Danach Claude neu starten und `linkedin_login` aufrufen.
Den zurückgegebenen Link auf demselben Computer im Browser öffnen und bei LinkedIn anmelden.
Anschliessend `linkedin_login_status` und `list_ad_accounts` aufrufen.
Die App braucht die Berechtigungen `r_ads` und `r_ads_reporting`.

Ein bereits vorhandener `LINKEDIN_ACCESS_TOKEN` funktioniert weiterhin. Nach einem Login
hat der gespeicherte OAuth-Token Vorrang vor einem alten Token aus der Konfiguration.

### Variante B: Via `uvx` (wenn Paket publiziert ist)

```json
{
  "mcpServers": {
    "flin-linkedin-ads-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-ads-mcp"],
      "env": {
        "LINKEDIN_CLIENT_ID": "DEINE_APP_CLIENT_ID",
        "LINKEDIN_CLIENT_SECRET": "DEIN_APP_CLIENT_SECRET",
        "LINKEDIN_REDIRECT_URI": "http://localhost:9876/callback",
        "LINKEDIN_API_VERSION": "202610",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

## 2-Minuten Smoke Test in Claude

Nach dem Restart in Claude diese Calls testen:

1. `linkedin_login` und den zurückgegebenen Link öffnen
2. `linkedin_login_status` (nach erfolgreichem Login: `token_available`)
3. `list_ad_accounts`
4. `list_campaigns`
5. `get_insights` mit `pivot=campaign`

Wenn `list_campaigns` eine Auswahl zurückgibt, den Call mit einem vorgeschlagenen `ad_account_id` wiederholen.

Hinweis zu `get_insights`:

- Der MCP nutzt den LinkedIn `analytics` Finder mit Single-Pivot.
- Implementierung ist auf die Dokumentation `view=li-lms-2026-03` ausgerichtet.
- `date_from` ist Pflicht (LinkedIn `adAnalytics` erwartet `dateRange`).
- Unterstützte `fields` folgen der Metrics-Tabelle aus der offiziellen Reporting-Schema-Doku (max. 20 Felder pro Request).
- Der Server nutzt intern `pivot.value` / `timeGranularity.value` und hat zusätzlich einen Fallback auf Legacy-Parameternamen für bessere API-Kompatibilität.
- Neuere Video/Event-Felder sind enthalten, z. B. `videoWatchTime`, `averageVideoWatchTime`, `eventViews`, `eventWatchTime`, `averageEventWatchTime`.

Beispiel für einen stabilen Test-Call:

```json
{
  "ad_account_id": "508834004",
  "date_from": "2025-08-01",
  "date_to": "2025-12-31",
  "fields": [
    "impressions",
    "clicks",
    "costInLocalCurrency",
    "dateRange"
  ],
  "pivot": "account",
  "time_granularity": "MONTHLY"
}
```

## LinkedIn Ad Library

Voraussetzung ist das freigeschaltete Produkt **LinkedIn Ad Library** auf der App,
die den verwendeten Mitgliedstoken ausgestellt hat. Ein vorhandener gültiger
OAuth-Mitgliedstoken kann weiterverwendet werden; es ist **kein zusätzlicher OAuth-Scope**
erforderlich. Beide Tools funktionieren ohne `ad_account_id` und ohne Zugriff auf
das Werbekonto des gesuchten Unternehmens. Der bestehende Ads-Login bleibt unverändert.

### `search_ad_library`

Sucht über `GET /rest/adLibrary?q=criteria` nach öffentlichen Anzeigen, auch anderer Unternehmen.

- `keyword`: Suchbegriffe im Anzeigeninhalt; mehrere Wörter werden mit UND verknüpft.
- `advertiser`: Name des werbenden Unternehmens.
- `payer_name`: Name der zahlenden Person oder Organisation.
- `countries`: zweistellige Ländercodes, z. B. `["CH", "DE", "AT"]`.
- `date_from` und `date_to`: gemeinsam im Format `YYYY-MM-DD`; Start inklusive,
  **Ende exklusiv**. Ohne diese Angaben nutzt LinkedIn nur **heute minus 2 Tage bis
  heute minus 1 Tag**, nicht das gesamte Archiv.
- `included_targeting_categories` / `excluded_targeting_categories`: Targeting-Kategorien,
  z. B. `["COMPANY", "JOB"]`; die verfügbaren Werte stehen im Tool-Schema.
- `impressions_from` und `impressions_to`: gemeinsam als Impression-Bereich;
  `1000000` bis `0` steht für die offene oberste Klasse ab einer Million.
- `sort_order`: `ASCENDING` oder `DESCENDING`, sortiert nach Erstellungszeit der Anzeige.
- `page_start`: Offset ab `0`; `page_size`: `1` bis `25`, Standard `25`.

Beispiel für `search_ad_library`:

```json
{
  "advertiser": "Microsoft",
  "countries": ["DE", "AT"],
  "date_from": "2026-10-01",
  "date_to": "2026-10-29",
  "page_size": 25
}
```

Die Antwort behält die API-Felder unverändert bei: `adUrl`, `details` mit Inserent,
Anzeigenformat, verfügbaren Targeting- und Impression-Daten sowie `isRestricted` und
`restrictionDetails`. Umfang und Verfügbarkeit hängen von der Anzeige und Region ab;
zusätzliche Transparenzdaten betreffen insbesondere EU-Anzeigen. Die API liefert
Vorschaulinks, keine heruntergeladenen Anzeigenbilder oder vollständigen Anzeigentexte
und keine Klick-, Kosten- oder Conversion-Berichte. Redaktionen bei eingeschränkten
Anzeigen bleiben erhalten. Anzeigen bleiben üblicherweise ein Jahr nach ihrer letzten
Impression in der Bibliothek.

### `search_brand_partnerships`

Sucht über `GET /rest/paidEndorsementPosts?q=searchCriteria` nach organischen Beiträgen,
die Creators als Markenpartnerschaft gekennzeichnet haben. Die Antwort enthält `postUrl`.

- `keyword`: Pflicht; mehrere Wörter werden mit UND verknüpft.
- `date_range`: optional `PAST_24H`, `PAST_WEEK` oder `PAST_MONTH`; ohne Filter sind
  verfügbare Beiträge bis maximal ein Jahr nach Veröffentlichung durchsuchbar.
- `page_start` und `page_size`: wie bei der Anzeigensuche; der MCP begrenzt beide Tools
  auf höchstens 25 Ergebnisse pro Aufruf.

```json
{
  "keyword": "technology",
  "date_range": "PAST_MONTH",
  "page_size": 10
}
```

### Weitere Seiten und Zugriffsfehler

Beide Tools liefern `paging.next_start`, `paging.has_next` und, sofern von LinkedIn
geliefert, `paging.total`. Für die nächste Seite dieselben Filter mit
`page_start=paging.next_start` erneut aufrufen. `paging.next_after` enthält denselben
Offset als String zur Kompatibilität mit dem bestehenden Antwortformat. Fehlen die
Paging-Angaben, kann eine volle Seite einen abschliessenden leeren Aufruf erfordern.

Bei `403` / `ACCESS_DENIED` prüfen, ob die MCP-Zugangsdaten zur **freigeschalteten App**
gehören und das Produkt im Developer Portal aktiv ist. Ein gültiger Token oder der
Status `token_available` allein bestätigt den Ad-Library-Zugriff nicht. Bei Bedarf
über `linkedin_login` neu verbinden und die Suche wiederholen; eine fehlende
Produktfreischaltung wird durch einen neuen Login nicht behoben.

Offizielle Referenzen:
[Zugang und Authentifizierung](https://www.linkedin.com/ad-library/api),
[Anzeigen-Schema](https://www.linkedin.com/ad-library/api/ads),
[Markenpartnerschaften-Schema](https://www.linkedin.com/ad-library/api/paid-endorsement-posts).

## `get_insights` Parameter (2026-03)

Wichtigste Parameter:

- `pivot`: z. B. `account`, `campaign_group`, `campaign`, `creative`, `member_company_size`, `member_industry`, `member_seniority`, `member_job_title`, `member_job_function`, `member_country_v2`, `member_region_v2`, `member_company`, `member_county`, `share`, `company`, `conversion`
- `time_granularity`: `DAILY`, `MONTHLY`, `ALL`, `YEARLY`
- `fields`: Liste aus der offiziellen Metrics-Tabelle, maximal 20 Einträge, case-sensitive
  - Kompatibilitätsfelder: `pivotValue` → `pivotValues`, `clickThroughRate` (berechnet als `clicks / impressions`), `costPerClick` (berechnet als `costInLocalCurrency / clicks`)
- `date_from`: `YYYY-MM-DD` (Pflicht)
- `date_to`: optional, `YYYY-MM-DD`

Facets/Filter:

- `ad_account_id` (ein Konto) oder `account_ids` (mehrere Konten)
- optional zusätzlich: `campaign_ids`, `campaign_group_ids`, `creative_ids`, `share_ids`, `company_ids`
- optional: `campaign_type`, `objective_type`
- optional Sortierung: `sort_by_field` + `sort_order` (müssen zusammen angegeben werden)

Kompatibilität:

- `entity_ids` bleibt für Backward-Kompatibilität erhalten (z. B. bei `pivot=campaign`).

## `list_creatives` / `get_creative` Bild-URL (optional)

Für Creative-Calls kann optional das Derived-Field `imageUrl` in `fields` angefordert werden.

- Ab API-Version `202610` wird `imageUrl` bevorzugt aus `metadata.assetURL` der einzelnen Creative-Abfrage gelesen. Dafür ist kein Zugriff auf die Posts-API nötig.
- `get_creative` fordert das Metadatum im selben Aufruf an; `list_creatives` macht nur bei angefordertem `imageUrl` oder `metadata` eine zusätzliche Abfrage je Creative (doppelte IDs werden pro Seite zwischengespeichert). Ohne diese Felder bleibt es bei einer Listenabfrage.
- `metadata` kann zusätzlich in `fields` angefordert werden und enthält je nach Format u. a. `adHeadline`, `adIntroductionText`, `adFormat`, `assetURL` und `landingPage`. Auf älteren API-Versionen wird eine ausdrückliche Anfrage nach `metadata` mit einem Konfigurationshinweis abgelehnt.
- Fehlt eine Bildadresse in den Metadaten, wird der Creative-`content` geprüft.
- Falls dort keine Bild-URL enthalten ist und eine `content.reference` auf `urn:li:adDirectSponsoredContent:*` zeigt, versucht der MCP zusätzlich eine Auflösung über `adDirectSponsoredContents/{urn}`.
- Falls dort keine Bild-URL enthalten ist und eine Share-/UGC-Post-Referenz vorhanden ist, versucht der MCP zusätzlich eine Auflösung über die aktuelle Posts-API und bei Bild-URNs über die Images-API. Auch verschachtelte Referenzen in `standardUpdateAd` und `videoAd` werden erkannt.
- Wenn keine Bild-URL auflösbar ist, ist `imageUrl` `null`.

Beispiel:

```json
{
  "ad_account_id": "508834004",
  "id": "urn:li:sponsoredCreative:935973186",
  "fields": ["id", "name", "imageUrl"]
}
```

## `list_account_intelligence` (202603)

Neues Tool:

- `list_account_intelligence`

Dieser Endpunkt nutzt `GET /rest/accountIntelligence?q=account` und ist laut LinkedIn private API (zusätzliche Freischaltung erforderlich).

Wichtige Parameter:

- `ad_account_id` (oder Auto-Resolve bei genau einem Account)
- `lookback_window`: `LAST_7_DAYS`, `LAST_30_DAYS`, `LAST_60_DAYS`, `LAST_90_DAYS`
- optional: `ad_segment_ids`, `campaign_id`
- optional: `skip_company_decoration`
- optional: `page_start`, `page_size` (max. 1000)

Wichtige Response-Felder:

- `companyName`, `engagementLevel`
- `paidImpressions`, `paidClicks`, `paidEngagements`, `paidLeads`
- `paidQualifiedLeads`, `conversions` (ab API-Version `202603`)
- `organicImpressions`, `organicEngagements`

Beispiel:

```json
{
  "ad_account_id": "508834004",
  "lookback_window": "LAST_30_DAYS",
  "page_size": 100
}
```

## `get_share_content` (best effort)

Neues Tool:

- `get_share_content`

Wichtige Parameter:

- `share_urn` (Pflicht, Format `urn:li:share:<id>` oder `urn:li:ugcPost:<id>`)
- `include_raw` (optional, `true` gibt zusätzlich das rohe API-Payload zurück)

Response enthält u. a.:

- `share_urn`, `source_endpoint` (`posts`)
- `post_url` (LinkedIn Feed URL)
- `text`
- `image_url` (erstes gefundenes Bild oder `null`)
- `image_urls`, `thumbnail_urls`

Beispiel:

```json
{
  "share_urn": "urn:li:share:7379073146093568000",
  "include_raw": false
}
```

## Anzeigenbilder und Dashboard-Einbettung

Für Anzeigenbilder bevorzugt `get_creative` / `list_creatives` mit `fields: ["id", "imageUrl", "metadata"]`
und `LINKEDIN_API_VERSION=202610` verwenden. Eine explizit auf `202603` oder älter gesetzte
MCP-Konfiguration überschreibt weiterhin den neuen Default: dort den Wert ändern und den
Server neu starten. Ein Paket-Update allein ändert diese Konfiguration nicht.

`get_share_content` verwendet die aktuelle Posts-API. Der alte `/shares`-Endpunkt wird
nicht mehr aufgerufen. Ein `403` an `/posts` oder `/images` bedeutet fehlende Berechtigungen
für diese APIs, auch wenn die Ads-Abfragen funktionieren. Der Connector fordert dafür keine
zusätzlichen Schreibberechtigungen an. Der Creative-Metadatenweg funktioniert unabhängig
vom Posts-Zugriff. Ein `426` enthält nun einen Hinweis auf die konfigurierte Version und
gegebenenfalls die nötige Endpoint-Migration, statt wie ein Login-Fehler behandelt zu werden.

Die Bildadressen sind externe, möglicherweise zeitlich begrenzte LinkedIn-URLs. Wenn ein
Dashboard externe Bilder blockiert, löst eine funktionierende URL diese Einschränkung
nicht: Für eine Einbettung müssen die ausgewählten Bilder über den vom Dashboard erlaubten
Import-/Asset-Workflow bereitgestellt werden. Der Connector exportiert oder lädt mit diesen
Tools keine Bilddateien herunter und verändert keine Dashboard-Sicherheitsregeln.
LinkedIn-Vorschaulinks bleiben eine mögliche Alternative. Eine `assetURL` kann je nach
Anzeigenformat auch ein anderes Medium sein; erkennbare Video-/PDF-URLs werden nicht als
`imageUrl` ausgegeben.

Referenzen: [Creative-Metadaten](https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads/account-structure/create-and-manage-creatives?view=li-lms-2026-10),
[Posts-API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api),
[Images-API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api).

## Troubleshooting `get_insights`

Bei `ILLEGAL_ARGUMENT` oder `RESOURCE_NOT_FOUND` bitte prüfen:

1. Feldnamen sind exakt korrekt (`clicks` statt `click`, `impressions` statt `impression`).
2. Maximal 20 `fields`.
3. Mindestens ein gültiger Facet-Filter (`ad_account_id`/`account_ids` oder andere Facets).
4. IDs im korrekten Format (Account/Campaign/Campaign Group/Creative numerisch oder URN; `share_ids` und `company_ids` als URN).
5. Datum im Format `YYYY-MM-DD`.
6. `date_from` ist gesetzt (ohne `dateRange` antwortet LinkedIn oft mit `ILLEGAL_ARGUMENT`).
7. `pivot` ist einer der dokumentierten Werte (siehe oben).

Schneller API-Gegencheck (ohne MCP) für das Token:

```bash
curl -i 'https://api.linkedin.com/rest/adAccounts?q=search&pageSize=1' \
  -H 'Authorization: Bearer DEIN_ACCESS_TOKEN' \
  -H 'Linkedin-Version: 202603' \
  -H 'X-Restli-Protocol-Version: 2.0.0'
```

## Direkt anmelden und neu verbinden

Die Anmeldung ist für einen **lokalen stdio-MCP-Server mit einem Benutzer** vorgesehen.
Browser und Server müssen auf demselben Computer laufen. Dies ist keine OAuth-Anmeldung
für einen gemeinsam genutzten Remote-/HTTP-Connector.

Einmalige Einrichtung:

1. In der LinkedIn Developer App den Marketing-/Advertising-Zugang mit `r_ads` und
   `r_ads_reporting` freischalten. Der anmeldende Benutzer braucht Zugriff auf das Werbekonto.
2. Unter **Auth** die Redirect URL `http://localhost:9876/callback` registrieren.
3. `LINKEDIN_CLIENT_ID` und `LINKEDIN_CLIENT_SECRET` in der MCP-Konfiguration hinterlegen
   (siehe Beispiel oben). Secrets gehören nicht in den Chat.
4. MCP-Client einmal neu starten, damit er die neue Konfiguration und Tools lädt.

Danach reicht im Chat die Bitte **„LinkedIn Ads neu verbinden“**:

- `linkedin_login` liefert `authorization_url`. Den Link im lokalen Browser öffnen.
- Der Server nimmt die Rückleitung automatisch entgegen und speichert den Token.
- `linkedin_login_status` zeigt den lokalen Status; `token_available` bestätigt noch
  keine Kontoberechtigungen. Mit `list_ad_accounts` den echten API-Zugriff prüfen.
- Anschliessend den ursprünglichen Call wiederholen, zum Beispiel
  `get_ad_account` mit `{"id":"509614236"}`. Kein weiterer Neustart und kein Token-Kopieren nötig.

Login-Links gelten zehn Minuten. Ein erneuter Aufruf während eines offenen Logins
liefert denselben Link. Abbruch, Ablauf oder ein Fehler lässt sich über den Status abfragen;
anschliessend kann ein neuer Login gestartet werden. Bei einem belegten Callback-Port
entweder den anderen Server schliessen oder `LINKEDIN_REDIRECT_URI` auf einen freien Port
ändern und dieselbe URL in der LinkedIn App registrieren.

### Token-Speicherung und Erneuerung

Standard: `~/.config/flin-linkedin-ads-mcp/tokens.json` (über `LINKEDIN_TOKEN_FILE` änderbar).
Die Datei enthält sensible Zugangsdaten, wird atomar mit Dateirechten `0600` geschrieben
und sollte ausserhalb des Repositories bleiben. Sie ist keine verschlüsselte Schlüsselablage.
Für getrennte Benutzer/Verbindungen jeweils eine eigene Datei und einen eigenen Callback-Port
verwenden. Ein gespeicherter Token wird nur für die zugehörige Client ID geladen.

Ein gespeicherter Login hat Vorrang vor `LINKEDIN_ACCESS_TOKEN`. Die Tokens werden beim
Serverstart geladen und nach erfolgreichem Login sofort im laufenden Server verwendet.
Token, Client Secret und Authorization Code erscheinen nicht in den Auth-Tool-Antworten
oder Callback-Logs. `linkedin_login_status` gibt nur Status und Ablaufzeitpunkte zurück.

Falls LinkedIn einen Refresh-Token ausstellt, erneuert der Server den Access-Token kurz
vor Ablauf bei der nächsten API-Abfrage sowie einmal nach einer 401-Antwort.
Abgelaufene/widerrufene Refresh-Tokens führen zurück zu `linkedin_login`.
Programmatic Refresh hängt von der Freischaltung der LinkedIn App ab;
`offline_access` wird nicht angefordert. Siehe
[LinkedIn Programmatic Refresh Tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).

### 401/403 diagnostizieren

- `401` / `EXPIRED_ACCESS_TOKEN`: `linkedin_login` aufrufen und den Link öffnen.
- Login meldet fehlende Konfiguration: Client ID und Client Secret einmalig hinterlegen.
- `403`: App-Berechtigungen und Rolle des angemeldeten Benutzers im Werbekonto prüfen.
- Der Server kann auch ohne Token starten, damit die Login-/Status-Tools verfügbar sind.

## Environment Variablen

Für direkten Login:

- `LINKEDIN_CLIENT_ID` und `LINKEDIN_CLIENT_SECRET` (immer zusammen setzen)
- `LINKEDIN_REDIRECT_URI` (Default: `http://localhost:9876/callback`; HTTP, `localhost` oder
  `127.0.0.1`, expliziter Port und Pfad; muss exakt in der App registriert sein)
- `LINKEDIN_TOKEN_FILE` (Default: `~/.config/flin-linkedin-ads-mcp/tokens.json`)

Alternativ bleibt `LINKEDIN_ACCESS_TOKEN` als fest hinterlegter Token unterstützt.
Ohne OAuth-App-Konfiguration kann dieser Token nicht automatisch erneuert werden.

Weitere Optionen:

- `LINKEDIN_API_VERSION` (Default: `202610`)
- `LINKEDIN_RESTLI_PROTOCOL_VERSION` (Default: `2.0.0`)
- `LINKEDIN_TIMEOUT_SECONDS` (Default: `30`)
- `LINKEDIN_MAX_RETRIES` (Default: `3`)

## Lokale Entwicklung

```bash
cd /Users/nicolasg/Antigravity/flin-linkedin-ads-mcp
python -m pip install -e ".[dev]"
pytest -q
ruff check .
mypy src
```

## Sicherheit (wichtig)

- Niemals `LINKEDIN_ACCESS_TOKEN` oder OAuth Secrets ins Repo committen
- `.env` ist bereits in `.gitignore`
- App-Zugangsdaten nur über MCP `env` oder lokale Shell-Umgebung setzen; OAuth-Tokens werden lokal gespeichert
- Vor jedem Push prüfen:

```bash
git status
git diff -- .env
```

Wenn eine Datei mit Secrets auftaucht: Commit abbrechen und Secrets rotieren.

## GitHub Actions & Release (PyPI-ready)

Dieses Repo enthält:

- CI Workflow: `.github/workflows/ci.yml`
- Release Workflow: `.github/workflows/release.yml`

Der Release-Workflow macht bei `v*` Tags:

1. Lint + Typecheck + Tests
2. Build + `twine check`
3. Trusted Publishing zu PyPI
4. GitHub Release mit `dist/*` Artefakten

Node-20-Deprecation-Warnungen sind abgefangen durch:

- aktuelle Actions-Majors (`checkout@v6`, `setup-python@v6`)
- `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` in beiden Workflows

### PyPI Trusted Publisher einmalig einrichten

- PyPI Project: `flin-linkedin-ads-mcp`
- Owner: `flin-agency`
- Repository: `flin-linkedin-ads-mcp`
- Workflow: `release.yml`
- Environment: `pypi`

### Release auslösen

```bash
git add -A
git commit -m "release: v0.1.0"
git tag v0.1.0
git push origin main --tags
```

## Offizielle Referenzen

- LinkedIn OAuth Overview:
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication
- Authorization Code Flow (native clients):
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow-native
- Reporting (Ad Analytics):
  - https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/ads-reporting?view=li-lms-2026-03
- Reporting Schema (Metrics + Query Parameters):
  - https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/ads-reporting-schema?view=li-lms-2026-03
- Company Intelligence API:
  - https://learn.microsoft.com/en-us/linkedin/marketing/account-intel/account-intel-api?view=li-lms-2026-03
- Programmatic Refresh Tokens:
  - https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens
