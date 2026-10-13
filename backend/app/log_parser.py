"""Parse and normalize JSON / CSV log input into NormalizedEvent objects.

Safety notes:
- Log content is treated strictly as data. Nothing is executed, evaluated,
  interpolated into commands, or fetched from URLs found in a log.
- Every value is type-checked and length-limited before it is accepted.
- The original record is preserved verbatim in `raw` for investigators.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .models import NormalizedEvent

# ---- Limits -----------------------------------------------------------------
MAX_RECORDS = 10_000  # maximum records accepted in one upload / sample load
MAX_FIELD_LENGTH = 512  # maximum characters in any single text field
MAX_REJECTION_DETAILS = 50  # rejected rows echoed back in API responses

VALID_SEVERITIES = ("info", "low", "medium", "high", "critical")
DEFAULT_SEVERITY = "info"

# ---- Canonical event types ----------------------------------------------------
LOGIN_SUCCESS = "login_success"
LOGIN_FAILURE = "login_failure"
NETWORK_CONNECTION = "network_connection"

EVENT_TYPE_ALIASES: dict[str, str] = {
    "login_success": LOGIN_SUCCESS,
    "successful_login": LOGIN_SUCCESS,
    "login_succeeded": LOGIN_SUCCESS,
    "logon_success": LOGIN_SUCCESS,
    "auth_success": LOGIN_SUCCESS,
    "login_failure": LOGIN_FAILURE,
    "login_failed": LOGIN_FAILURE,
    "failed_login": LOGIN_FAILURE,
    "logon_failure": LOGIN_FAILURE,
    "auth_failure": LOGIN_FAILURE,
    "network_connection": NETWORK_CONNECTION,
    "network_connect": NETWORK_CONNECTION,
    "connection": NETWORK_CONNECTION,
    "network_flow": NETWORK_CONNECTION,
}

# Accepted input field names (case-insensitive) mapped to canonical field names.
# The first name in each tuple is the canonical name.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "time", "event_time", "@timestamp", "datetime"),
    "event_type": ("event_type", "event", "action", "type"),
    "event_id": ("event_id",),
    "source": ("source", "log_source", "sensor"),
    "user": ("user", "username", "account", "user_name"),
    "source_ip": ("source_ip", "src_ip", "client_ip", "ip"),
    "source_host": ("source_host", "src_host", "hostname", "host"),
    "destination_host": ("destination_host", "dest_host", "dst_host"),
    "destination_ip": ("destination_ip", "dest_ip", "dst_ip"),
    "port": ("port", "destination_port", "dest_port", "dst_port"),
    "protocol": ("protocol", "proto"),
    "severity": ("severity", "level"),
}
REQUIRED_FIELDS = ("timestamp", "event_type")
TEXT_FIELDS = ("source", "user", "source_host", "destination_host", "protocol", "event_id")


class FileError(ValueError):
    """The whole file cannot be processed (bad format, too large, missing columns...)."""


class RecordError(ValueError):
    """A single record is malformed and is skipped (reported back to the user)."""


@dataclass
class RejectedRecord:
    row: int
    reason: str


@dataclass
class ParseResult:
    events: list[NormalizedEvent] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    total_records: int = 0


# ---- Field-level helpers ------------------------------------------------------
# Epoch values outside this window are almost certainly not timestamps
# (e.g. "20261012" would otherwise silently parse as a 1970 date).
_EPOCH_MIN = 946_684_800  # 2000-01-01T00:00:00Z
_EPOCH_MAX = 4_102_444_800  # 2100-01-01T00:00:00Z


def _from_epoch(value: Any) -> datetime:
    seconds = float(value)
    if not _EPOCH_MIN <= seconds < _EPOCH_MAX:
        raise RecordError(f"epoch timestamp '{value}' is outside the accepted 2000-2100 range")
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def parse_timestamp(value: Any) -> str:
    """Return a UTC ISO-8601 string (seconds precision, trailing Z).

    Accepts ISO-8601 (with Z or an offset), "YYYY-MM-DD HH:MM:SS", and Unix
    epoch seconds. Naive timestamps are assumed to already be UTC.
    """
    if isinstance(value, bool) or value is None:
        raise RecordError("timestamp is missing or not a date/time")
    try:
        if isinstance(value, (int, float)):
            dt = _from_epoch(value)
        else:
            text = str(value).strip()
            if not text:
                raise RecordError("timestamp is empty")
            if text.replace(".", "", 1).isdigit():
                dt = _from_epoch(text)
            else:
                dt = datetime.fromisoformat(text)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
    except RecordError:
        raise
    except (ValueError, OverflowError, OSError) as exc:
        raise RecordError(
            f"timestamp '{value}' is not a valid ISO-8601 date/time or epoch value"
        ) from exc
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        raise RecordError(f"{name} must be a single text value")
    text = str(value).strip()
    if not text:
        return None
    if len(text) > MAX_FIELD_LENGTH:
        raise RecordError(f"{name} is longer than {MAX_FIELD_LENGTH} characters")
    return text


def _clean_ip(name: str, value: Any) -> str | None:
    text = _clean_text(name, value)
    if text is None:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError as exc:
        raise RecordError(f"{name} '{text}' is not a valid IPv4 or IPv6 address") from exc


def _clean_port(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise RecordError("port must be an integer between 0 and 65535")
    try:
        port = int(str(value).strip())
    except ValueError as exc:
        raise RecordError(f"port '{value}' is not an integer") from exc
    if not 0 <= port <= 65535:
        raise RecordError(f"port {port} is outside the range 0-65535")
    return port


def _clean_severity(value: Any) -> str:
    text = _clean_text("severity", value)
    if text is None:
        return DEFAULT_SEVERITY
    text = text.lower()
    if text not in VALID_SEVERITIES:
        raise RecordError(
            f"severity '{text}' is not one of: {', '.join(VALID_SEVERITIES)}"
        )
    return text


def _clean_event_type(value: Any) -> str:
    text = _clean_text("event_type", value)
    if text is None:
        raise RecordError("event_type is missing")
    key = text.lower().replace("-", "_").replace(" ", "_")
    if key not in EVENT_TYPE_ALIASES:
        supported = ", ".join(sorted(set(EVENT_TYPE_ALIASES.values())))
        raise RecordError(f"unsupported event_type '{text}' (supported: {supported})")
    return EVENT_TYPE_ALIASES[key]


def _make_event_id(fields: dict[str, Any]) -> str:
    """Deterministic ID from normalized content, so re-importing is idempotent."""
    canonical = json.dumps(
        [fields.get(k) for k in (
            "timestamp", "source", "event_type", "user", "source_ip", "source_host",
            "destination_host", "destination_ip", "port", "protocol", "severity", "event_id",
        )],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "evt_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _canonical_keys(record: dict[str, Any]) -> dict[str, Any]:
    """Map alias field names onto canonical names (case-insensitive)."""
    lowered = {}
    for key, value in record.items():
        if isinstance(key, str):
            lowered.setdefault(key.strip().lower(), value)
    mapped: dict[str, Any] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lowered and lowered[alias] not in (None, ""):
                mapped[canonical] = lowered[alias]
                break
    return mapped


def normalize_record(record: Any) -> NormalizedEvent:
    """Normalize one record (a dict). Raises RecordError with a human-readable reason."""
    if not isinstance(record, dict):
        raise RecordError("record must be a JSON object / CSV row")
    mapped = _canonical_keys(record)
    for required in REQUIRED_FIELDS:
        if required not in mapped:
            raise RecordError(f"required field '{required}' is missing")

    normalized: dict[str, Any] = {
        "timestamp": parse_timestamp(mapped["timestamp"]),
        "event_type": _clean_event_type(mapped["event_type"]),
        "source": _clean_text("source", mapped.get("source")),
        "user": _clean_text("user", mapped.get("user")),
        "source_ip": _clean_ip("source_ip", mapped.get("source_ip")),
        "source_host": _clean_text("source_host", mapped.get("source_host")),
        "destination_host": _clean_text("destination_host", mapped.get("destination_host")),
        "destination_ip": _clean_ip("destination_ip", mapped.get("destination_ip")),
        "port": _clean_port(mapped.get("port")),
        "protocol": _clean_text("protocol", mapped.get("protocol")),
        "severity": _clean_severity(mapped.get("severity")),
    }
    provided_id = _clean_text("event_id", mapped.get("event_id"))
    normalized["event_id"] = _make_event_id({**normalized, "event_id": provided_id})

    if normalized["protocol"]:
        normalized["protocol"] = normalized["protocol"].lower()

    return NormalizedEvent(**normalized, raw=_raw_copy(record))


def _raw_copy(record: dict[str, Any]) -> dict[str, Any]:
    """Preserve the original record as JSON-safe data for later inspection."""
    safe: dict[str, Any] = {}
    for key, value in record.items():
        if key is None:
            continue
        safe[str(key)] = value if isinstance(value, (str, int, float, bool, list, dict)) or value is None else str(value)
    return safe


# ---- Format entry points ------------------------------------------------------
def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileError("file is not valid UTF-8 text") from exc


def parse_json(data: bytes) -> ParseResult:
    """Parse a JSON array of event objects, or an object with an 'events' array."""
    text = _decode(data)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        records = payload["events"]
    elif isinstance(payload, list):
        records = payload
    else:
        raise FileError(
            "JSON must be an array of event objects or an object with an 'events' array"
        )
    if len(records) == 0:
        raise FileError("JSON file contains no events")
    if len(records) > MAX_RECORDS:
        raise FileError(f"file contains {len(records)} records; the limit is {MAX_RECORDS}")

    result = ParseResult(total_records=len(records))
    for index, record in enumerate(records, start=1):
        try:
            result.events.append(normalize_record(record))
        except RecordError as exc:
            result.rejected.append(RejectedRecord(row=index, reason=str(exc)))
    return result


def parse_csv(data: bytes) -> ParseResult:
    """Parse a CSV file with a header row. Rows are numbered by file line (header = line 1)."""
    text = _decode(data)
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header_row = next(reader)
    except StopIteration as exc:
        raise FileError("CSV file is empty") from exc
    except csv.Error as exc:
        raise FileError(f"CSV header could not be read: {exc}") from exc

    headers = [h.strip().lower() for h in header_row]
    if not any(headers):
        raise FileError("CSV header row is empty")
    if len(set(headers)) != len(headers):
        raise FileError("CSV header contains duplicate column names")
    present = set()
    for canonical, aliases in FIELD_ALIASES.items():
        if any(alias in headers for alias in aliases):
            present.add(canonical)
    missing = [f for f in REQUIRED_FIELDS if f not in present]
    if missing:
        raise FileError(f"CSV is missing required column(s): {', '.join(missing)}")

    result = ParseResult()
    for values in reader:
        line_no = reader.line_num
        if not any(v.strip() for v in values):
            continue  # skip fully blank lines silently
        result.total_records += 1
        if result.total_records > MAX_RECORDS:
            raise FileError(f"file contains more than {MAX_RECORDS} records; the limit is {MAX_RECORDS}")
        if len(values) > len(headers):
            result.rejected.append(RejectedRecord(
                row=line_no,
                reason=f"row has {len(values)} values but the header defines {len(headers)} columns",
            ))
            continue
        record = {headers[i]: values[i] for i in range(len(values))}
        try:
            result.events.append(normalize_record(record))
        except RecordError as exc:
            result.rejected.append(RejectedRecord(row=line_no, reason=str(exc)))

    if result.total_records == 0:
        raise FileError("CSV file contains a header but no data rows")
    return result


def parse_file(file_name: str, data: bytes) -> tuple[str, ParseResult]:
    """Choose the parser from the file extension. Returns (format_name, result)."""
    lowered = file_name.lower()
    if lowered.endswith(".json"):
        return "json", parse_json(data)
    if lowered.endswith(".csv"):
        return "csv", parse_csv(data)
    raise FileError("unsupported file type; upload a .csv or .json file")
