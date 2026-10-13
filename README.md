# EventLens

**EventLens is a Cybersecurity Incident Correlation and Visualization System (Basic MVP).**
It turns synthetic security log entries into understandable, evidence-backed alerts that help a human investigate possible suspicious activity.

> **Evidence first, score second.**
> A detected pattern is an investigation lead, not proof that an attack occurred.

EventLens uses transparent, rule-based detection. It does not use artificial intelligence or machine learning.
It works on **synthetic data only**. It does not connect to real systems and does not perform any containment action (no account blocking, no host isolation).

---

## Contents

- [The problem it solves](#the-problem-it-solves)
- [Features](#features)
- [Architecture](#architecture)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Install and run: Windows PowerShell](#install-and-run-windows-powershell)
- [Install and run: macOS / Linux](#install-and-run-macos--linux)
- [Load sample logs](#load-sample-logs)
- [Upload a CSV or JSON file](#upload-a-csv-or-json-file)
- [Detection rules](#detection-rules)
- [Run the tests](#run-the-tests)
- [API documentation](#api-documentation)
- [Data handling and duplicates](#data-handling-and-duplicates)
- [Current limitations](#current-limitations)
- [Ethical and safety considerations](#ethical-and-safety-considerations)
- [Publish the repository to GitHub](#publish-the-repository-to-github)

---

## The problem it solves

Security tools produce many raw log lines. A single failed login means little. Repeated failures followed by a success from the same address can mean a password was guessed, or it can mean a user mistyped their password. EventLens makes these patterns visible and shows the exact events behind each one, so a reviewer can decide what to check next.

## Features

| Area | What is implemented |
|---|---|
| Dashboard | Events analyzed, possible alerts, high-concern alerts, medium-priority alerts, recent alerts, events-by-type and events-by-severity breakdowns. All numbers come from the database. Loading, empty and error states. |
| Alerts | List with search, priority and rule filters, pagination. Click an alert to open its detail page. |
| Alert detail | "What we observed", "What remains uncertain", "Suggested next step", evidence factors, and a vertical chronological timeline. Each event shows why it is linked and its original raw record. |
| Event Explorer | Normalized events, newest first, with search, event-type and severity filters, pagination, and expandable raw records. |
| Upload Logs | Upload a `.csv` or `.json` file. Shows accepted, duplicate and rejected counts, with the row number and reason for each rejected row. A sample-data button is also provided. |
| Normalization | Common structure: `event_id`, `timestamp`, `source`, `event_type`, `user`, `source_ip`, `source_host`, `destination_host`, `destination_ip`, `port`, `protocol`, `severity`, `raw`. Timestamps become UTC ISO-8601. |
| Detection | Rule 1: repeated failed logins. Rule 2: successful login after failures. Thresholds are constants in `backend/app/detection.py`. |
| Persistence | SQLite. Tables are created on startup. Data survives backend restarts. |

Not implemented in this MVP: user accounts or login to EventLens itself, live log streaming, real log-source connectors, background jobs, exporting reports, custom rule editing in the UI, and any response or containment action.

## Architecture

```
React + Vite + Tailwind (browser)
        │  same-origin requests to /api/*
        ▼
Vite dev / preview server  ──proxy──►  FastAPI backend (127.0.0.1:8000)
                                          ├─ log_parser.py   validate + normalize JSON/CSV
                                          ├─ detection.py    Rule 1 and Rule 2
                                          ├─ database.py     SQLite (data/eventlens.db)
                                          └─ main.py         HTTP routes, errors, CORS
```

The browser never calls the backend port directly; the Vite server forwards `/api/*`. See [docs/architecture.md](docs/architecture.md) for the data flow, rule behavior and persistence model.

## Repository structure

```
EventLens/
  README.md
  .gitignore
  docs/
    architecture.md
  data/
    sample_logs.json        synthetic demo dataset (JSON)
    auth_logs.csv           synthetic login events (CSV)
    network_logs.csv        synthetic network events (CSV)
    README.md               notes on the synthetic data
  backend/
    requirements.txt        pinned Python dependencies
    pytest.ini
    .env.example
    app/
      __init__.py
      main.py               FastAPI app and routes
      database.py           SQLite schema and queries
      models.py             internal Pydantic models
      schemas.py            API response models
      log_parser.py         JSON/CSV parsing and normalization
      detection.py          rule engine
    tests/
      conftest.py           temporary database fixtures
      test_health.py
      test_log_parser.py    normalization and malformed-input tests
      test_detection.py     rule, threshold and window-boundary tests
      test_api.py           endpoint, upload, persistence tests
  frontend/
    package.json
    vite.config.js          dev/preview server and /api proxy
    index.html
    .env.example
    src/
      main.jsx
      App.jsx
      index.css
      components/           Layout, Timeline, badges, state messages, ...
      pages/                DashboardPage, AlertsPage, AlertDetailPage, EventsPage, UploadPage
      services/             api.js (backend client), useAsync.js, format.js
```

## Prerequisites

| Tool | Version used for testing | Notes |
|---|---|---|
| Python | 3.11 (3.10+ should work) | `python --version` |
| Node.js | 22 (Vite 8 needs Node 20.19+ or 22.12+) | `node --version` |
| npm | 10 | comes with Node.js |
| Git | any recent version | needed only to clone and publish |

Windows: run the commands in **PowerShell**. If PowerShell blocks activation scripts, run this once in the same window: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

---

## Install and run: Windows PowerShell

Use two PowerShell windows, one for the backend and one for the frontend.

### 1. Clone the repository (first time only)

```powershell
git clone https://github.com/deekshithkumar257-cloud/Eventlens.git
cd Eventlens
```

### 2. Backend: install dependencies (terminal 1)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

If the `py` launcher is not installed, use `python -m venv .venv` instead of `py -3.11 -m venv .venv`.

`copy .env.example .env` is optional. The defaults work without it.

### 3. Backend: start the API (terminal 1)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this window open. The API is at <http://127.0.0.1:8000>, and the interactive docs are at <http://127.0.0.1:8000/docs>.

### 4. Frontend: install dependencies (terminal 2)

```powershell
cd frontend
npm install
```

### 5. Frontend: start the dashboard (terminal 2)

```powershell
cd frontend
npm run dev
```

Open <http://localhost:5173>. The header shows **API online** when the frontend can reach the backend.

## Install and run: macOS / Linux

### 1. Clone the repository (first time only)

```bash
git clone https://github.com/deekshithkumar257-cloud/Eventlens.git
cd Eventlens
```

### 2. Backend: install dependencies (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env   # optional
```

### 3. Backend: start the API (terminal 1)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Frontend: install and start (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

### Frontend production build (optional)

```powershell
cd frontend
npm run build      # output goes to frontend/dist (ignored by Git)
npm run preview    # serves the built app at http://localhost:4173
```

---

## Load sample logs

1. Start the backend and the frontend as above.
2. Open <http://localhost:5173>.
3. Click **Load sample logs**. The first load stores 50 events and creates 4 alerts.

You can also load the sample from the command line while the backend is running:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/logs/sample
```

```bash
curl -X POST http://127.0.0.1:8000/logs/sample
```

The sample shows:

- Normal successful logins and internal network connections.
- Six failed logins for one account with no success: **Repeated failed logins, Medium**.
- Four failures followed by a success: below the threshold, no alert.
- Seven failures from an external IP, then a success from the same IP: **Successful login after failures, High**.
- Eleven failed attempts across accounts from one IP: **Repeated failed logins from source IP, High** (escalated at 10+ failures).
- A successful login more than 10 minutes after earlier failures: no Rule 2 alert.

## Upload a CSV or JSON file

Open **Upload Logs** in the dashboard, choose a file, and click **Upload and analyze**. The same file can be sent with the command line.

**CSV** needs a header row with at least `timestamp` and `event_type`. Other columns are optional:

```csv
timestamp,event_type,user,source_ip,source_host,destination_host,destination_ip,port,protocol,severity
2026-10-12T09:40:05Z,login_failure,jordan.lee,10.20.1.60,WS-OPS-007,SRV-AUTH-01,10.20.5.10,443,https,low
```

**JSON** is either an array of event objects or an object with an `events` array:

```json
{
  "events": [
    {"timestamp": "2026-10-12T09:40:05Z", "event_type": "login_failure", "user": "jordan.lee", "source_ip": "10.20.1.60"}
  ]
}
```

Supported `event_type` values: `login_success`, `login_failure`, `network_connection`. Common aliases such as `failed_login` are also accepted. Timestamps can be ISO-8601 with or without an offset (no offset means UTC) or Unix epoch seconds between 2000 and 2100.

Limits: 5 MB per file (`EVENTLENS_MAX_UPLOAD_MB`) and 10,000 records per file.

Command-line upload:

```powershell
curl.exe -X POST -F "file=@data\auth_logs.csv" http://127.0.0.1:8000/logs/upload
```

```bash
curl -X POST -F "file=@data/auth_logs.csv" http://127.0.0.1:8000/logs/upload
```

## Detection rules

Both rules run over all stored events every time a file is imported. All thresholds are in `backend/app/detection.py`:

```python
FAILED_LOGIN_THRESHOLD = 5          # failures needed
FAILED_LOGIN_WINDOW_SECONDS = 600   # ten-minute window, inclusive at both ends
HIGH_PRIORITY_FAILURE_COUNT = 10    # Rule 1 escalates to High at this count
```

| Rule | Trigger | Review priority |
|---|---|---|
| **R1 Repeated failed logins** | 5 or more failed logins for the same account, or from the same source IP, within 10 minutes | Medium (High at 10 or more) |
| **R2 Successful login after failures** | 5 or more failed logins from a source IP, followed by a successful login from the same IP, within 10 minutes. The failures are linked as evidence. The finding is described as *possible credential compromise requiring validation*. | High |

Every alert states what was observed, what remains uncertain, and the suggested next step. No alert is labelled as a confirmed attack.

## Run the tests

From the `backend` folder with the virtual environment active:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

```bash
cd backend
source .venv/bin/activate
pytest
```

The tests use a temporary SQLite database created for each test, so the development database is never touched. They cover the health endpoint, normalization, missing optional fields, malformed records and files, both detection rules, window boundaries, evidence IDs, alert and timeline endpoints, upload limits, idempotent re-import, persistence across restarts, and CORS.

Frontend production build check:

```powershell
cd frontend
npm run build
```

## API documentation

With the backend running:

| URL | Description |
|---|---|
| <http://127.0.0.1:8000/docs> | Interactive Swagger UI (try endpoints in the browser) |
| <http://127.0.0.1:8000/redoc> | ReDoc reference |
| <http://127.0.0.1:8000/openapi.json> | OpenAPI schema |

| Method and path | Purpose |
|---|---|
| `GET /health` | API and database health |
| `GET /events` | Normalized events. Query: `limit` (1–500), `offset`, `event_type`, `user`, `source_ip`, `severity`, `q` |
| `POST /logs/upload` | Upload and process a `.csv` or `.json` file (multipart field `file`) |
| `POST /logs/sample` | Load the bundled synthetic sample |
| `GET /alerts` | Alerts, highest priority first. Query: `limit`, `offset`, `priority`, `rule_id`, `q` |
| `GET /alerts/{alert_id}` | One alert with explanation, evidence factors and linked events |
| `GET /alerts/{alert_id}/timeline` | Linked events in chronological order |
| `GET /stats` | Counts for the dashboard, all derived from stored data |

Errors use one format: `{"error": {"code": "...", "message": "...", "details": [...]}}`.

The frontend reaches the same API through `http://localhost:5173/api/...`.

## Data handling and duplicates

- **Event IDs** are deterministic. They are a hash of the normalized content (timestamp, source, type, user, IPs, hosts, port, protocol, severity, and any provided `event_id`).
- **Re-importing the same data** inserts nothing. The response reports those rows as `duplicate_events`. Two genuinely identical log lines with the same timestamp to the second are stored as one event.
- **Alerts** are rebuilt from the stored events after each import, inside the same transaction. Unchanged data therefore yields the same alert IDs and no duplicates.
- **Rejected rows** are skipped and reported with their row number (CSV line number, or JSON array position). Valid rows in the same file are still stored. A file where no row is valid is rejected with HTTP 422.
- **Uploads** are processed in memory and not saved to disk.
- **Raw evidence** is stored as text and displayed as text. Log content is never executed or rendered as HTML.

## Current limitations

- Synthetic data only. The rules are simple thresholds and have not been validated against real traffic. Expect false positives and false negatives.
- Only two rules. No correlation with network connections, no time-series scoring, no per-user baselines.
- An alert ID is derived from its evidence. If later imports change a cluster (for example, more failures join a burst), the old alert disappears and a new ID appears.
- Event timestamps are stored to the second. Sub-second precision is dropped.
- The database is a single local SQLite file. There is no authentication, no multi-user access and no role separation. Do not expose the API to a network.
- The upload parser supports CSV and JSON only. Syslog, Windows Event Log and cloud formats are not supported.
- Frontend automated tests are not included. The frontend was verified with a production build and a scripted browser walkthrough of the main workflows.
- The development servers are for local use. For a deployment, serve `frontend/dist` behind a proper web server and run the backend under a production ASGI setup.

## Ethical and safety considerations

- EventLens is for education, demonstrations and defensive review of data you are authorized to analyze.
- Use synthetic or properly authorized data only. Do not upload personal data, credentials, or logs from systems you do not own or administer.
- Alerts are leads. Verify with the account owner and the system owner before taking any action. An alert is never evidence of wrongdoing by a named person.
- EventLens does not block accounts, isolate hosts, or send traffic to any external target. Keep it that way; any response action must go through your organization's own approved process.
- The sample uses fictional names and documentation IP ranges. Do not add real credentials, API keys or real personal data to `data/` or to Git.

## Publish the repository to GitHub

The repository is already a Git repository. The steps below commit the work and push it to GitHub.

### Windows PowerShell

```powershell
cd Eventlens
git status
git add .
git commit -m "Add EventLens basic MVP"
git push -u origin HEAD
```

`HEAD` pushes whichever branch you are on. To open a pull request into `main`, use the GitHub web page or `gh pr create --base main`.

### macOS / Linux

```bash
cd Eventlens
git status
git add .
git commit -m "Add EventLens basic MVP"
git push -u origin HEAD
```

Before committing, check `git status` to confirm that `.env`, `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`, and `data/*.db` are **not** listed. The `.gitignore` excludes them.
