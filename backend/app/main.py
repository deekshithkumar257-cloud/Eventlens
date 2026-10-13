"""EventLens FastAPI application.

Run from the backend/ directory:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import database as db
from .detection import run_detection
from .log_parser import MAX_REJECTION_DETAILS, FileError, ParseResult, parse_file, parse_json
from .models import NormalizedEvent
from .schemas import (
    AlertDetail,
    AlertListOut,
    AlertSummary,
    EventListOut,
    EventOut,
    HealthOut,
    ImportResultOut,
    StatsOut,
    TimelineItem,
    TimelineOut,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

APP_VERSION = "0.1.0"
DEFAULT_MAX_UPLOAD_MB = 5
DEFAULT_SAMPLE_PATH = db.REPO_ROOT / "data" / "sample_logs.json"
ALLOWED_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def max_upload_bytes() -> int:
    try:
        mb = float(os.getenv("EVENTLENS_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB))
    except ValueError:
        mb = DEFAULT_MAX_UPLOAD_MB
    return int(max(mb, 0.001) * 1024 * 1024)


def sample_path() -> Path:
    raw = os.getenv("EVENTLENS_SAMPLE_PATH", "").strip()
    return Path(raw).expanduser().resolve() if raw else DEFAULT_SAMPLE_PATH


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="EventLens API",
    version=APP_VERSION,
    description=(
        "Cybersecurity incident correlation API. Works on synthetic data only. "
        "Alerts are investigation leads that require human review, not confirmed attacks."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---- Consistent error responses ------------------------------------------------
def _error(status: int, code: str, message: str, details: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _error(exc.status_code, f"http_{exc.status_code}", message)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", []) if part not in ("body", "query", "path"))
        details.append(f"{location or 'request'}: {err.get('msg', 'invalid value')}")
    return _error(422, "validation_error", "The request contains invalid parameters.", details)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_out(event: NormalizedEvent) -> EventOut:
    return EventOut.model_validate(event.model_dump())


# ---- Health -------------------------------------------------------------------
@app.get("/health", response_model=HealthOut, tags=["system"])
def health() -> HealthOut:
    """API health status, including a simple database connectivity check."""
    try:
        with db.transaction() as conn:
            conn.execute("SELECT 1").fetchone()
        database_status = "ok"
    except Exception:  # noqa: BLE001 - report, do not leak internals
        database_status = "unavailable"
    return HealthOut(
        status="ok" if database_status == "ok" else "degraded",
        service="EventLens API",
        version=APP_VERSION,
        database=database_status,
    )


# ---- Events ---------------------------------------------------------------------
@app.get("/events", response_model=EventListOut, tags=["events"])
def list_events(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    event_type: str | None = None,
    user: str | None = None,
    source_ip: str | None = None,
    severity: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> EventListOut:
    """Normalized events, newest first, with optional filters and pagination."""
    with db.transaction() as conn:
        events, total = db.list_events(
            conn, limit=limit, offset=offset, event_type=event_type, user=user,
            source_ip=source_ip, severity=severity, query=q,
        )
    return EventListOut(items=[_event_out(e) for e in events], total=total, limit=limit, offset=offset)


# ---- Alerts ---------------------------------------------------------------------
@app.get("/alerts", response_model=AlertListOut, tags=["alerts"])
def list_alerts(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    priority: Annotated[str | None, Query(pattern="^(High|Medium|Low)$")] = None,
    rule_id: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> AlertListOut:
    """Persisted alerts, highest priority first."""
    with db.transaction() as conn:
        items, total = db.list_alerts(
            conn, limit=limit, offset=offset, priority=priority, rule_id=rule_id, query=q,
        )
    return AlertListOut(
        items=[AlertSummary(**item) for item in items], total=total, limit=limit, offset=offset,
    )


def _require_alert(conn, alert_id: str) -> dict[str, Any]:
    alert = db.get_alert(conn, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' was not found")
    return alert


@app.get("/alerts/{alert_id}", response_model=AlertDetail, tags=["alerts"])
def get_alert(alert_id: str) -> AlertDetail:
    """One alert with its explanation, evidence factors and supporting events."""
    with db.transaction() as conn:
        alert = _require_alert(conn, alert_id)
        evidence = db.get_alert_evidence(conn, alert_id)
    return AlertDetail(
        **{k: alert[k] for k in AlertSummary.model_fields},
        summary=alert["summary"],
        observed=alert["observed"],
        uncertain=alert["uncertain"],
        next_step=alert["next_step"],
        evidence_factors=alert["evidence_factors"],
        supporting_event_ids=[item["event"].event_id for item in evidence],
        evidence=[
            {"position": i["position"], "role": i["role"], "reason": i["reason"], "event": _event_out(i["event"])}
            for i in evidence
        ],
    )


@app.get("/alerts/{alert_id}/timeline", response_model=TimelineOut, tags=["alerts"])
def get_alert_timeline(alert_id: str) -> TimelineOut:
    """Supporting events of one alert in chronological order."""
    with db.transaction() as conn:
        _require_alert(conn, alert_id)
        evidence = db.get_alert_evidence(conn, alert_id)
    items = sorted(evidence, key=lambda i: (i["event"].timestamp, i["event"].event_id))
    return TimelineOut(
        alert_id=alert_id,
        items=[
            TimelineItem(position=i + 1, role=item["role"], reason=item["reason"], event=_event_out(item["event"]))
            for i, item in enumerate(items)
        ],
    )


# ---- Import -------------------------------------------------------------------
def _run_import(file_name: str, source_format: str, parsed: ParseResult) -> ImportResultOut:
    """Store parsed events, then rebuild alerts, all in one transaction."""
    import_id = "imp_" + uuid.uuid4().hex[:12]
    imported_at = _now()
    with db.transaction() as conn:
        inserted, duplicates = db.insert_events(conn, parsed.events, import_id)
        db.record_import(
            conn,
            import_id=import_id,
            file_name=file_name,
            source_format=source_format,
            total_records=parsed.total_records,
            inserted=inserted,
            duplicates=duplicates,
            rejected=len(parsed.rejected),
            imported_at=imported_at,
        )
        alerts = run_detection(db.fetch_all_events(conn))
        new_alerts, total_alerts = db.replace_alerts(conn, alerts, created_at=imported_at)

    return ImportResultOut(
        import_id=import_id,
        file_name=file_name,
        source_format=source_format,
        total_records=parsed.total_records,
        inserted_events=inserted,
        duplicate_events=duplicates,
        rejected_records=len(parsed.rejected),
        rejected_details=[
            {"row": r.row, "reason": r.reason} for r in parsed.rejected[:MAX_REJECTION_DETAILS]
        ],
        new_alerts=new_alerts,
        total_alerts=total_alerts,
        imported_at=imported_at,
    )


def _ensure_some_valid(parsed: ParseResult) -> None:
    if parsed.total_records and not parsed.events:
        preview = "; ".join(f"row {r.row}: {r.reason}" for r in parsed.rejected[:3])
        raise HTTPException(
            status_code=422,
            detail=f"No valid records were found. {preview}",
        )


@app.post("/logs/upload", response_model=ImportResultOut, tags=["logs"])
async def upload_logs(file: Annotated[UploadFile, File(description=".csv or .json log file")]) -> ImportResultOut:
    """Validate, normalize, store and run detection on an uploaded CSV or JSON file.

    Whole-file problems (wrong type, too large, malformed JSON, missing CSV columns)
    return 4xx. Individual malformed rows are skipped and listed in `rejected_details`.
    The uploaded content is processed in memory and is not written to disk.
    """
    file_name = (file.filename or "upload").strip() or "upload"
    limit = max_upload_bytes()
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File is larger than the {limit // (1024 * 1024)} MB upload limit")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if not file_name.lower().endswith((".csv", ".json")):
        raise HTTPException(status_code=415, detail="Unsupported file type. Upload a .csv or .json file")
    try:
        source_format, parsed = parse_file(file_name, data)
    except FileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _ensure_some_valid(parsed)
    return _run_import(file_name, source_format, parsed)


@app.post("/logs/sample", response_model=ImportResultOut, tags=["logs"])
def load_sample_logs() -> ImportResultOut:
    """Load the bundled synthetic sample dataset (data/sample_logs.json). Safe to repeat."""
    path = sample_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sample dataset was not found on the server")
    try:
        parsed = parse_json(path.read_bytes())
    except FileError as exc:
        raise HTTPException(status_code=500, detail=f"Sample dataset is invalid: {exc}") from exc
    return _run_import(path.name, "json", parsed)


# ---- Stats --------------------------------------------------------------------
@app.get("/stats", response_model=StatsOut, tags=["stats"])
def get_stats() -> StatsOut:
    """Actual counts derived from stored events and alerts (used by the dashboard)."""
    with db.transaction() as conn:
        return StatsOut(**db.compute_stats(conn))
