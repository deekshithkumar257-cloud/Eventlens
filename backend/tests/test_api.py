"""API tests: upload validation, sample loading, alert/timeline endpoints, stats, persistence."""

import json

from fastapi.testclient import TestClient

from app import log_parser
from app.main import app

SAMPLE_EVENT_COUNT = 50
SAMPLE_ALERT_COUNT = 4


def _load_sample(client):
    response = client.post("/logs/sample")
    assert response.status_code == 200, response.text
    return response.json()


def _sample_csv(name):
    """Bytes of one of the bundled CSV sample files."""
    from pathlib import Path

    return (Path(__file__).resolve().parents[2] / "data" / name).read_bytes()


def _upload(client, name, content, content_type="text/plain"):
    return client.post("/logs/upload", files={"file": (name, content, content_type)})


# ---- Sample loading and idempotency ---------------------------------------------
def test_sample_load_stores_events_and_creates_expected_alerts(client):
    result = _load_sample(client)
    assert result["total_records"] == SAMPLE_EVENT_COUNT
    assert result["inserted_events"] == SAMPLE_EVENT_COUNT
    assert result["duplicate_events"] == 0
    assert result["rejected_records"] == 0
    assert result["new_alerts"] == SAMPLE_ALERT_COUNT
    assert result["total_alerts"] == SAMPLE_ALERT_COUNT


def test_loading_sample_twice_does_not_duplicate_events_or_alerts(client):
    _load_sample(client)
    second = _load_sample(client)
    assert second["inserted_events"] == 0
    assert second["duplicate_events"] == SAMPLE_EVENT_COUNT
    assert second["new_alerts"] == 0
    assert second["total_alerts"] == SAMPLE_ALERT_COUNT
    assert client.get("/events").json()["total"] == SAMPLE_EVENT_COUNT
    assert client.get("/alerts").json()["total"] == SAMPLE_ALERT_COUNT


def test_csv_exports_of_sample_are_recognized_as_duplicates_of_json_sample(client):
    """The CSV files contain the same events as the JSON sample, so their IDs match."""
    _load_sample(client)
    auth = _upload(client, "auth_logs.csv", _sample_csv("auth_logs.csv"), "text/csv")
    network = _upload(client, "network_logs.csv", _sample_csv("network_logs.csv"), "text/csv")
    assert auth.status_code == 200, auth.text
    assert network.status_code == 200, network.text
    assert auth.json()["inserted_events"] == 0
    assert auth.json()["duplicate_events"] == 40
    assert network.json()["inserted_events"] == 0
    assert network.json()["duplicate_events"] == 10
    assert client.get("/stats").json()["total_events"] == SAMPLE_EVENT_COUNT


def test_csv_upload_on_fresh_database_matches_json_sample(client):
    auth = _upload(client, "auth_logs.csv", _sample_csv("auth_logs.csv"), "text/csv")
    network = _upload(client, "network_logs.csv", _sample_csv("network_logs.csv"), "text/csv")
    assert auth.status_code == 200 and network.status_code == 200
    assert client.get("/stats").json()["total_events"] == SAMPLE_EVENT_COUNT
    assert client.get("/alerts").json()["total"] == SAMPLE_ALERT_COUNT


def test_json_upload_round_trip(client):
    """Five failures for one user from one IP form one burst.

    The user-based and IP-based views of that burst contain the same events, so
    detection reports ONE alert, not two.
    """
    records = [
        {"timestamp": f"2026-10-12T08:0{i}:00Z", "event_type": "login_failure",
         "user": "u1", "source_ip": "10.0.0.1"}
        for i in range(5)
    ]
    response = _upload(client, "failures.json", json.dumps(records).encode(), "application/json")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["inserted_events"] == 5
    assert body["rejected_records"] == 0
    assert body["new_alerts"] == 1
    assert body["total_alerts"] == 1
    alert = client.get("/alerts").json()["items"][0]
    assert alert["rule_id"] == "R1_REPEATED_FAILED_LOGINS"
    assert alert["event_count"] == 5


# ---- Upload validation -----------------------------------------------------------
def test_unsupported_file_type_is_rejected(client):
    response = _upload(client, "logs.txt", b"hello")
    assert response.status_code == 415
    assert response.json()["error"]["message"]


def test_empty_upload_is_rejected(client):
    response = _upload(client, "empty.csv", b"")
    assert response.status_code == 400


def test_malformed_json_upload_is_rejected_with_message(client):
    response = _upload(client, "bad.json", b"{not json", "application/json")
    assert response.status_code == 400
    assert "invalid JSON" in response.json()["error"]["message"]


def test_csv_missing_required_column_is_rejected(client):
    response = _upload(client, "bad.csv", b"user,ip\nalice,10.0.0.1\n", "text/csv")
    assert response.status_code == 400
    assert "missing required column" in response.json()["error"]["message"]


def test_partially_invalid_upload_imports_valid_rows_and_reports_bad_ones(client):
    content = (
        b"timestamp,event_type,user\n"
        b"2026-10-12T08:00:00Z,login_success,alice\n"
        b"not-a-time,login_success,bob\n"
    )
    response = _upload(client, "mixed.csv", content, "text/csv")
    assert response.status_code == 200
    body = response.json()
    assert body["inserted_events"] == 1
    assert body["rejected_records"] == 1
    assert body["rejected_details"][0]["row"] == 3
    assert "timestamp" in body["rejected_details"][0]["reason"]


def test_upload_where_every_row_is_invalid_returns_422(client):
    response = _upload(client, "allbad.csv", b"timestamp,event_type\nnope,login_success\n", "text/csv")
    assert response.status_code == 422
    assert "No valid records" in response.json()["error"]["message"]


def test_upload_size_limit_is_enforced(client, monkeypatch):
    monkeypatch.setenv("EVENTLENS_MAX_UPLOAD_MB", "0.001")  # about 1 KB
    response = _upload(client, "big.csv", b"timestamp,event_type\n" + b"2026-10-12T08:00:00Z,login_success\n" * 100, "text/csv")
    assert response.status_code == 413


def test_record_count_limit_is_enforced(client, monkeypatch):
    monkeypatch.setattr(log_parser, "MAX_RECORDS", 2)
    content = b"timestamp,event_type\n" + b"2026-10-12T08:00:00Z,login_success\n" * 3
    response = _upload(client, "many.csv", content, "text/csv")
    assert response.status_code == 400
    assert "limit" in response.json()["error"]["message"]


# ---- Read endpoints -------------------------------------------------------------
def test_events_endpoint_paginates_and_filters(client):
    _load_sample(client)
    page = client.get("/events", params={"limit": 10, "offset": 0}).json()
    assert page["total"] == SAMPLE_EVENT_COUNT
    assert len(page["items"]) == 10
    filtered = client.get("/events", params={"event_type": "login_failure", "limit": 500}).json()
    assert filtered["total"] > 0
    assert all(item["event_type"] == "login_failure" for item in filtered["items"])


def test_events_endpoint_validates_limit(client):
    response = client.get("/events", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_alerts_endpoint_lists_high_priority_first_and_supports_filters(client):
    _load_sample(client)
    alerts = client.get("/alerts").json()["items"]
    assert len(alerts) == SAMPLE_ALERT_COUNT
    priorities = [a["priority"] for a in alerts]
    assert priorities == sorted(priorities, key=lambda p: {"High": 0, "Medium": 1, "Low": 2}[p])
    high = client.get("/alerts", params={"priority": "High"}).json()
    assert high["total"] == 2
    search = client.get("/alerts", params={"q": "amara.singh"}).json()
    assert search["total"] >= 1
    assert all("amara.singh" in (a["title"] + a["entity_value"] + (a["affected_user"] or "")) for a in search["items"])


def test_rule_two_alert_for_sample_has_linked_evidence_and_explanation(client):
    _load_sample(client)
    alerts = client.get("/alerts", params={"priority": "High"}).json()["items"]
    rule2 = [a for a in alerts if a["rule_id"] == "R2_SUCCESS_AFTER_FAILURES"]
    assert len(rule2) == 1
    detail = client.get(f"/alerts/{rule2[0]['alert_id']}").json()
    assert detail["entity_value"] == "203.0.113.50"
    assert "Possible credential compromise" in detail["title"]
    assert detail["observed"]
    assert detail["uncertain"]
    assert detail["next_step"]
    assert detail["evidence_factors"]
    assert len(detail["supporting_event_ids"]) == 8
    roles = [item["role"] for item in detail["evidence"]]
    assert roles.count("successful_login") == 1


def test_alert_evidence_ids_match_stored_events(client):
    _load_sample(client)
    stored_ids = {e["event_id"] for e in client.get("/events", params={"limit": 500}).json()["items"]}
    for summary in client.get("/alerts").json()["items"]:
        detail = client.get(f"/alerts/{summary['alert_id']}").json()
        assert detail["supporting_event_ids"]
        for event_id in detail["supporting_event_ids"]:
            assert event_id in stored_ids
        for item in detail["evidence"]:
            assert item["event"]["event_id"] in stored_ids
            assert item["reason"]


def test_alert_timeline_is_chronological_and_matches_evidence(client):
    _load_sample(client)
    alert_id = client.get("/alerts", params={"priority": "High"}).json()["items"][0]["alert_id"]
    detail = client.get(f"/alerts/{alert_id}").json()
    timeline = client.get(f"/alerts/{alert_id}/timeline").json()
    assert timeline["alert_id"] == alert_id
    timestamps = [item["event"]["timestamp"] for item in timeline["items"]]
    assert timestamps == sorted(timestamps)
    assert {item["event"]["event_id"] for item in timeline["items"]} == set(detail["supporting_event_ids"])
    for item in timeline["items"]:
        assert item["event"]["raw"]
        assert item["reason"]


def test_unknown_alert_returns_404_in_consistent_format(client):
    for path in ("/alerts/alrt_doesnotexist", "/alerts/alrt_doesnotexist/timeline"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["message"]


def test_stats_reflect_stored_data(client):
    empty = client.get("/stats").json()
    assert empty["total_events"] == 0
    assert empty["total_alerts"] == 0
    _load_sample(client)
    stats = client.get("/stats").json()
    assert stats["total_events"] == SAMPLE_EVENT_COUNT
    assert stats["total_alerts"] == SAMPLE_ALERT_COUNT
    assert stats["high_priority_alerts"] == 2
    assert sum(stats["events_by_type"].values()) == SAMPLE_EVENT_COUNT
    assert sum(stats["alerts_by_rule"].values()) == SAMPLE_ALERT_COUNT
    assert stats["last_import_at"]


# ---- Persistence and CORS ---------------------------------------------------------
def test_data_survives_backend_restart(db_path):
    with TestClient(app) as first:
        _load_sample(first)
    with TestClient(app) as second:
        stats = second.get("/stats").json()
        assert stats["total_events"] == SAMPLE_EVENT_COUNT
        assert stats["total_alerts"] == SAMPLE_ALERT_COUNT


def test_cors_allows_only_the_local_frontend_origin(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
