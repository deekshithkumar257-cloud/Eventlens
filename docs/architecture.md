# EventLens Architecture (Basic MVP)

EventLens turns synthetic security log entries into evidence-backed alerts that a human can review.

> **Core principle: "Evidence first, score second."**
> A rule match is an investigation lead, not proof of an attack.

## Components

```
 Browser (React + Tailwind)                 Vite dev/preview server          FastAPI backend (Python)
 ┌──────────────────────────┐   /api/*     ┌──────────────────────┐  proxy   ┌──────────────────────────┐
 │ Overview  Alerts  Events │ ───────────► │ serves the SPA and   │ ───────► │ main.py   (HTTP routes)   │
 │ Alert detail · Upload    │              │ forwards /api/* to   │          │ log_parser.py (normalize) │
 └──────────────────────────┘              │ 127.0.0.1:8000       │          │ detection.py (2 rules)    │
                                           └──────────────────────┘          │ database.py  (SQLite)     │
                                                                             └────────────┬─────────────┘
                                                                                          ▼
                                                                                 data/eventlens.db
```

- The browser only calls same-origin `/api/...`. Backend addresses never appear in browser code.
- CORS is also limited to `http://localhost:5173` and `http://127.0.0.1:5173`.

## Data flow

1. **Input** — `POST /logs/upload` (CSV or JSON) or `POST /logs/sample` (bundled synthetic data).
2. **Validation and normalization** (`log_parser.py`)
   - Field aliases are mapped to the common structure (`event_id`, `timestamp`, `source`, `event_type`, `user`, `source_ip`, `source_host`, `destination_host`, `destination_ip`, `port`, `protocol`, `severity`, `raw`).
   - Timestamps are converted to UTC ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`).
   - IPs, ports, severities and event types are checked. Malformed rows are rejected with a row number and reason; valid rows are still stored.
   - The original record is kept in `raw` and is never executed.
3. **Storage** (`database.py`) — events are inserted with `INSERT OR IGNORE` on a deterministic `event_id`, so duplicates are counted and skipped.
4. **Detection** (`detection.py`) — both rules run over *all* stored events. Alerts are rebuilt in the same transaction as the import.
5. **Presentation** — the React app reads `/stats`, `/alerts`, `/alerts/{id}`, `/alerts/{id}/timeline` and `/events`.

## Detection rules

| Rule | Trigger | Default priority | Thresholds (`detection.py`) |
|---|---|---|---|
| R1 Repeated failed logins | ≥ 5 failed logins for the same account, or from the same source IP, inside a 10-minute window | Medium (High at ≥ 10 failures) | `FAILED_LOGIN_THRESHOLD`, `FAILED_LOGIN_WINDOW_SECONDS`, `HIGH_PRIORITY_FAILURE_COUNT` |
| R2 Successful login after failures | ≥ 5 failed logins from a source IP, then a successful login from the same IP, within 10 minutes | High | same window and threshold |

Rule behaviour:

- Windows are inclusive: a span of exactly 600 seconds is inside the window, 601 seconds is outside.
- R1 groups greedily and left to right, so one burst is reported once. An identical set of evidence from the account view and the IP view produces one alert.
- R2 uses each failed attempt as evidence at most once, so a single failure burst cannot generate several alerts when the same IP logs in repeatedly.
- Detection is deterministic: the same events always produce the same alerts with the same IDs.

## Alert model

Every alert stores: ID, rule, review priority, first/last observed timestamps, affected account / IP / host, a human-readable summary, **what we observed**, **what remains uncertain**, **suggested next step**, evidence factors, and the linked supporting events (each with a reason and a position in the chronological timeline).

## Persistence and idempotency

- SQLite tables: `imports`, `events`, `alerts`, `alert_events`. They are created automatically at startup.
- Re-importing unchanged data inserts nothing and creates no new alerts.
- Alerts are a function of the stored events. If new events change a cluster, the alert's evidence and ID change and the old one is removed. This is documented as a limitation.

## Limits and safety

- Upload size and record count are capped (`EVENTLENS_MAX_UPLOAD_MB`, default 5 MB; 10,000 records).
- Uploads are processed in memory and not written to disk.
- No account blocking, host isolation, or other containment action exists. Alerts are advisory.
- No machine learning or AI is used. Every alert is explainable from the rule thresholds and the listed events.

## Repository layout

See `README.md` for the full tree. Key modules:

| Path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI routes, error shape, CORS, upload handling |
| `backend/app/log_parser.py` | JSON/CSV parsing, normalization, validation |
| `backend/app/detection.py` | Rule 1 and Rule 2, thresholds, alert explanations |
| `backend/app/database.py` | SQLite schema and queries |
| `backend/app/models.py` / `schemas.py` | Internal models / API response models |
| `frontend/src/pages/*` | Overview, Alerts, Alert detail, Event Explorer, Upload Logs |
| `frontend/src/components/*` | Layout, timeline, badges, state messages |
| `frontend/src/services/api.js` | Backend client with readable error messages |
