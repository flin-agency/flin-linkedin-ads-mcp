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
- Keine Schreiboperationen in `v0.1.x`

## Scope `v0.1.x` (strict read-only)

- Kein Create/Update/Delete
- Kein Pause/Resume
- Kein generischer Proxy-Endpunkt
- Kein eingebauter OAuth-Refresh-Flow im MCP selbst

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
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202603",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

Danach Claude neu starten.

### Variante B: Via `uvx` (wenn Paket publiziert ist)

```json
{
  "mcpServers": {
    "flin-linkedin-ads-mcp": {
      "command": "uvx",
      "args": ["--refresh", "flin-linkedin-ads-mcp"],
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "AQX...",
        "LINKEDIN_API_VERSION": "202603",
        "LINKEDIN_RESTLI_PROTOCOL_VERSION": "2.0.0"
      }
    }
  }
}
```

## 2-Minuten Smoke Test in Claude

Nach dem Restart in Claude diese Calls testen:

1. `list_ad_accounts`
2. `list_campaigns`
3. `get_insights` mit `pivot=campaign`

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

- `imageUrl` wird bevorzugt direkt aus dem Creative-`content` extrahiert.
- Falls dort keine Bild-URL enthalten ist und eine `content.reference` auf `urn:li:adDirectSponsoredContent:*` zeigt, versucht der MCP zusätzlich eine Auflösung über `adDirectSponsoredContents/{urn}`.
- Falls dort keine Bild-URL enthalten ist und eine Share-Referenz vorhanden ist, versucht der MCP zusätzlich eine Auflösung über die referenzierte Share/Post-Entity.
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

- `share_urn` (Pflicht, Format `urn:li:share:<id>`)
- `include_raw` (optional, `true` gibt zusätzlich das rohe API-Payload zurück)

Response enthält u. a.:

- `share_urn`, `source_endpoint` (`shares` oder `posts`)
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

## LinkedIn Access Token generieren (Schritt für Schritt)

Voraussetzung:
- LinkedIn Developer App vorhanden
- Marketing API Zugriff für die App freigeschaltet
- Scope `r_ads` für Entities (Accounts/Campaigns/Creatives)
- Scope `r_ads_reporting` für `get_insights`
- Die Ad Accounts sind in der Developer App unter `Products -> View Ad Accounts` gemappt
- Der authentifizierte User hat eine Ad-Account-Rolle (mind. `VIEWER`)

### 1) App in LinkedIn Developer Portal vorbereiten

- In der App unter `Auth`:
  - `Client ID` und `Client Secret` notieren
  - Redirect URL hinzufügen, z. B. `http://localhost:9876/callback`
- In der App sicherstellen, dass die Marketing/Ads Berechtigungen aktiviert sind (`r_ads` + `r_ads_reporting`)

### 2) Authorization Code holen

Im Browser öffnen (Werte ersetzen, `redirect_uri` URL-encoden).

Für diesen MCP müssen im Scope mindestens enthalten sein:

- `r_ads` (Accounts/Campaigns/Creatives)
- `r_ads_reporting` (`get_insights`)

Optional (nur wenn deine App dafür freigeschaltet ist):

- `offline_access` (für Refresh-Token-Flow)

Empfohlene URL für den MCP (ohne Refresh-Token):

```text
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=DEIN_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A9876%2Fcallback&scope=r_ads%20r_ads_reporting&state=dein_csrf_state
```

Variante mit optionalem `offline_access`:

```text
https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=DEIN_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost%3A9876%2Fcallback&scope=r_ads%20r_ads_reporting%20offline_access&state=dein_csrf_state
```

Nach Login/Consent leitet LinkedIn auf deine Redirect-URL zurück:

```text
http://localhost:9876/callback?code=AUTH_CODE&state=dein_csrf_state
```

Den `code` aus der URL kopieren.

### 3) Authorization Code gegen Access Token tauschen

```bash
curl -X POST 'https://www.linkedin.com/oauth/v2/accessToken' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=authorization_code' \
  --data-urlencode 'code=AUTH_CODE' \
  --data-urlencode 'redirect_uri=http://localhost:9876/callback' \
  --data-urlencode 'client_id=DEIN_CLIENT_ID' \
  --data-urlencode 'client_secret=DEIN_CLIENT_SECRET'
```

Beispiel-Response:

```json
{
  "access_token": "AQX...",
  "expires_in": 5183999
}
```

`access_token` als `LINKEDIN_ACCESS_TOKEN` in die Claude MCP Config übernehmen.

Wichtig: Bei diesem MCP erfolgt Authentifizierung über `env` in der MCP Config.
Es gibt hier keinen eingebauten OAuth-Refresh-Flow im Server selbst.
Wenn der Token abläuft, musst du einen neuen Token erzeugen und in der Config ersetzen.

### 4) Ablauf / Erneuerung

- Access Tokens laufen typischerweise nach ca. 60 Tagen ab.
- Dann OAuth-Flow erneut durchführen.
- Falls deine App für programmatic refresh tokens freigeschaltet ist, kannst du stattdessen per Refresh Token erneuern.

### 5) 401/403 schnell diagnostizieren

Token gegen Ads-Account-Endpunkt testen:

```bash
curl -i 'https://api.linkedin.com/rest/adAccounts?q=search&pageSize=1' \
  -H 'Authorization: Bearer DEIN_ACCESS_TOKEN' \
  -H 'Linkedin-Version: 202603' \
  -H 'X-Restli-Protocol-Version: 2.0.0'
```

Interpretation:

- `401 Unauthorized`: Token abgelaufen, widerrufen oder falscher Scope-Set wurde neu konsentiert
- `403 Forbidden`: Token ist gültig, aber Scope/Rolle/App-Mapping fehlt
- `200 OK`: Auth grundsätzlich korrekt

## Environment Variablen

Pflicht:

- `LINKEDIN_ACCESS_TOKEN`

Optional:

- `LINKEDIN_API_VERSION` (Default: `202603`)
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
- Token nur über MCP `env` in Claude oder über lokale Shell-Umgebung setzen
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
