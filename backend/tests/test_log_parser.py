"""Normalization, validation and malformed-input tests."""

import pytest

from app import log_parser
from app.log_parser import FileError, RecordError, normalize_record, parse_csv, parse_json, parse_timestamp


def _base(**overrides):
    record = {"timestamp": "2026-10-12T08:00:00Z", "event_type": "login_success", "user": "alice.morgan"}
    record.update(overrides)
    return record


def test_successful_normalization_maps_all_canonical_fields():
    event = normalize_record({
        "timestamp": "2026-10-12T08:00:00Z",
        "event_type": "login_failure",
        "source": "auth-service",
        "user": "alice.morgan",
        "source_ip": "203.0.113.9",
        "source_host": "WS-FIN-014",
        "destination_host": "SRV-AUTH-01",
        "destination_ip": "10.20.5.10",
        "port": "443",
        "protocol": "HTTPS",
        "severity": "Medium",
    })
    assert event.event_type == "login_failure"
    assert event.timestamp == "2026-10-12T08:00:00Z"
    assert event.source_ip == "203.0.113.9"
    assert event.port == 443
    assert event.protocol == "https"
    assert event.severity == "medium"
    assert event.event_id.startswith("evt_")


def test_raw_record_is_preserved_verbatim():
    record = _base(extra_field="kept", source_ip="10.0.0.5")
    event = normalize_record(record)
    assert event.raw == record


def test_missing_optional_fields_become_none_and_default_severity():
    event = normalize_record(_base())
    assert event.source is None
    assert event.source_ip is None
    assert event.port is None
    assert event.destination_host is None
    assert event.severity == "info"


def test_blank_strings_are_treated_as_missing():
    event = normalize_record(_base(source_ip="   ", user="", port=""))
    assert event.source_ip is None
    assert event.user is None
    assert event.port is None


def test_field_aliases_are_accepted():
    event = normalize_record({"@timestamp": "2026-10-12T08:00:00Z", "action": "login_failed",
                              "src_ip": "10.1.2.3", "username": "bob.chen"})
    assert event.event_type == "login_failure"
    assert event.source_ip == "10.1.2.3"
    assert event.user == "bob.chen"


@pytest.mark.parametrize("value, expected", [
    ("2026-10-12T10:00:00+02:00", "2026-10-12T08:00:00Z"),
    ("2026-10-12T08:00:00Z", "2026-10-12T08:00:00Z"),
    ("2026-10-12 08:00:00", "2026-10-12T08:00:00Z"),  # naive treated as UTC
    ("2026-10-12T08:00:00.123456Z", "2026-10-12T08:00:00Z"),  # sub-seconds dropped
    (1791792000, "2026-10-12T08:00:00Z"),  # epoch seconds (1791792000 = 2026-10-12T08:00:00Z)
])
def test_timestamps_normalize_to_utc_iso(value, expected):
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["not-a-date", "2026-13-45T00:00:00Z", "", None, True, "20261012"])
def test_invalid_timestamps_are_rejected(value):
    with pytest.raises(RecordError):
        parse_timestamp(value)


@pytest.mark.parametrize("record, fragment", [
    ({"event_type": "login_success"}, "timestamp"),
    ({"timestamp": "2026-10-12T08:00:00Z"}, "event_type"),
    (_base(timestamp="garbage"), "timestamp"),
    (_base(event_type="port_scan_alert"), "unsupported event_type"),
    (_base(source_ip="999.1.1.1"), "not a valid IPv4"),
    (_base(port="70000"), "outside the range"),
    (_base(port="https"), "not an integer"),
    (_base(severity="extreme"), "severity"),
    (_base(user={"nested": "object"}), "single text value"),
    (_base(user="x" * 600), "longer than"),
    (["not", "an", "object"], "must be a JSON object"),
])
def test_malformed_records_raise_readable_errors(record, fragment):
    with pytest.raises(RecordError) as exc:
        normalize_record(record)
    assert fragment in str(exc.value)


def test_event_id_is_deterministic_and_content_based():
    a = normalize_record(_base())
    b = normalize_record(_base())
    c = normalize_record(_base(user="someone.else"))
    assert a.event_id == b.event_id
    assert a.event_id != c.event_id


def test_untrusted_log_content_is_stored_as_plain_data():
    payload = "alice; rm -rf / $(whoami) <script>alert(1)</script>"
    event = normalize_record(_base(user=payload))
    assert event.user == payload
    assert event.raw["user"] == payload


def test_json_array_and_wrapped_object_are_both_accepted():
    array = b'[{"timestamp": "2026-10-12T08:00:00Z", "event_type": "login_success", "user": "a"}]'
    wrapped = b'{"events": [{"timestamp": "2026-10-12T08:00:00Z", "event_type": "login_success", "user": "a"}]}'
    assert len(parse_json(array).events) == 1
    assert len(parse_json(wrapped).events) == 1


def test_json_partial_failure_keeps_valid_rows_and_reports_bad_rows():
    data = b'''[
        {"timestamp": "2026-10-12T08:00:00Z", "event_type": "login_success", "user": "a"},
        {"timestamp": "bad", "event_type": "login_success", "user": "b"},
        {"timestamp": "2026-10-12T08:01:00Z", "event_type": "login_failure", "user": "c"}
    ]'''
    result = parse_json(data)
    assert result.total_records == 3
    assert len(result.events) == 2
    assert [r.row for r in result.rejected] == [2]


@pytest.mark.parametrize("data, fragment", [
    (b"{not json", "invalid JSON"),
    (b'"just a string"', "must be an array"),
    (b"[]", "contains no events"),
    (b"\xff\xfe\x00bad", "not valid UTF-8"),
])
def test_malformed_json_files_are_rejected(data, fragment):
    with pytest.raises(FileError) as exc:
        parse_json(data)
    assert fragment in str(exc.value)


def test_csv_normalizes_rows_and_skips_blank_lines():
    data = (
        b"timestamp,event_type,user,source_ip,severity\r\n"
        b"2026-10-12T08:00:00Z,login_success,alice,10.0.0.5,\r\n"
        b"\r\n"
        b"2026-10-12T08:01:00Z,login_failure,bob,10.0.0.6,low\r\n"
    )
    result = parse_csv(data)
    assert result.total_records == 2
    assert [e.severity for e in result.events] == ["info", "low"]
    assert result.events[0].source_ip == "10.0.0.5"


def test_csv_bad_rows_are_reported_with_line_numbers():
    data = (
        b"timestamp,event_type,user\n"
        b"2026-10-12T08:00:00Z,login_success,alice\n"
        b"oops,login_success,bob\n"
        b"2026-10-12T08:02:00Z,login_success,carol,extra\n"
    )
    result = parse_csv(data)
    assert len(result.events) == 1
    assert [r.row for r in result.rejected] == [3, 4]


@pytest.mark.parametrize("data, fragment", [
    (b"", "empty"),
    (b"user,ip\nalice,10.0.0.1\n", "missing required column"),
    (b"timestamp,event_type\n", "no data rows"),
    (b"timestamp,timestamp,event_type\n2026-10-12T08:00:00Z,x,y\n", "duplicate column"),
])
def test_malformed_csv_files_are_rejected(data, fragment):
    with pytest.raises(FileError) as exc:
        parse_csv(data)
    assert fragment in str(exc.value)


def test_csv_with_utf8_bom_is_accepted():
    data = "\ufefftimestamp,event_type\n2026-10-12T08:00:00Z,login_success\n".encode("utf-8")
    assert len(parse_csv(data).events) == 1


def test_record_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(log_parser, "MAX_RECORDS", 2)
    data = b"timestamp,event_type\n" + b"2026-10-12T08:00:00Z,login_success\n" * 3
    with pytest.raises(FileError):
        parse_csv(data)
