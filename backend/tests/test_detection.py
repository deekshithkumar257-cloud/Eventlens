"""Rule tests: thresholds, time-window boundaries, evidence, and rule 2 pairing."""

from datetime import datetime, timedelta, timezone

from app.detection import (
    FAILED_LOGIN_THRESHOLD,
    FAILED_LOGIN_WINDOW_SECONDS,
    RULE_REPEATED_FAILURES,
    RULE_SUCCESS_AFTER_FAILURES,
    run_detection,
)
from app.log_parser import normalize_record

BASE = datetime(2026, 10, 12, 8, 0, 0, tzinfo=timezone.utc)
_counter = {"n": 0}


def ev(offset_seconds, event_type, user=None, ip=None, host=None):
    """Build a normalized event at BASE + offset with a unique, explicit event_id."""
    _counter["n"] += 1
    ts = (BASE + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return normalize_record({
        "event_id": f"test-{_counter['n']}",
        "timestamp": ts,
        "event_type": event_type,
        "user": user,
        "source_ip": ip,
        "source_host": "WS-TEST-001" if ip else None,
    })


def failures(offsets, user="alice.morgan", ip="10.20.1.21"):
    return [ev(o, "login_failure", user=user, ip=ip) for o in offsets]


def by_rule(alerts, rule_id):
    return [a for a in alerts if a.rule_id == rule_id]


# ---- Constants sanity ---------------------------------------------------------
def test_thresholds_match_the_specification():
    assert FAILED_LOGIN_THRESHOLD == 5
    assert FAILED_LOGIN_WINDOW_SECONDS == 600


# ---- Rule 1: repeated failed logins -------------------------------------------
def test_five_failed_logins_for_one_user_trigger_rule_one():
    alerts = run_detection(failures([0, 60, 120, 180, 240]))
    rule1 = by_rule(alerts, RULE_REPEATED_FAILURES)
    assert len(rule1) == 1
    alert = rule1[0]
    assert alert.entity_type == "user"
    assert alert.entity_value == "alice.morgan"
    assert alert.priority == "Medium"
    assert alert.first_seen == "2026-10-12T08:00:00Z"
    assert alert.last_seen == "2026-10-12T08:04:00Z"
    assert len(alert.evidence) == 5


def test_fewer_than_five_failed_logins_do_not_trigger_rule_one():
    assert by_rule(run_detection(failures([0, 60, 120, 180])), RULE_REPEATED_FAILURES) == []


def test_five_failures_from_one_source_ip_trigger_ip_based_rule_one():
    events = [ev(o, "login_failure", user=f"user{i}", ip="198.51.100.23") for i, o in enumerate([0, 30, 60, 90, 120])]
    rule1 = by_rule(run_detection(events), RULE_REPEATED_FAILURES)
    assert len(rule1) == 1
    assert rule1[0].entity_type == "source_ip"
    assert rule1[0].entity_value == "198.51.100.23"


def test_ten_or_more_failures_escalate_rule_one_to_high():
    alerts = run_detection(failures([i * 30 for i in range(10)]))
    assert by_rule(alerts, RULE_REPEATED_FAILURES)[0].priority == "High"


def test_failures_exactly_at_window_edge_trigger_inclusive_window():
    # Span of exactly 600 seconds (10 minutes) is inside the window.
    alerts = run_detection(failures([0, 150, 300, 450, 600]))
    assert len(by_rule(alerts, RULE_REPEATED_FAILURES)) == 1


def test_failures_spanning_beyond_window_do_not_trigger():
    # Span of 601 seconds: no five-event cluster fits within 600 seconds.
    alerts = run_detection(failures([0, 150, 300, 450, 601]))
    assert by_rule(alerts, RULE_REPEATED_FAILURES) == []


def test_successful_logins_do_not_count_as_failures_for_rule_one():
    events = failures([0, 60, 120, 180]) + [ev(240, "login_success", user="alice.morgan", ip="10.20.1.21")]
    assert by_rule(run_detection(events), RULE_REPEATED_FAILURES) == []


# ---- Rule 2: success after failures -------------------------------------------
def test_success_after_five_failures_from_same_ip_triggers_rule_two():
    events = failures([0, 60, 120, 180, 240, 300, 360])
    events.append(ev(420, "login_success", user="amara.singh", ip="10.20.1.21"))
    alerts = run_detection(events)
    rule2 = by_rule(alerts, RULE_SUCCESS_AFTER_FAILURES)
    assert len(rule2) == 1
    alert = rule2[0]
    assert alert.priority == "High"
    assert "Possible credential compromise" in alert.title
    assert "requiring validation" in alert.title
    roles = [link.role for link in alert.evidence]
    assert roles.count("failed_login") == 7
    assert roles.count("successful_login") == 1
    assert alert.evidence[-1].role == "successful_login"


def test_success_after_four_failures_does_not_trigger_rule_two():
    events = failures([0, 60, 120, 180])
    events.append(ev(240, "login_success", user="alice.morgan", ip="10.20.1.21"))
    assert by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES) == []


def test_success_without_preceding_failures_does_not_trigger_rule_two():
    events = [ev(0, "login_success", user="bob.chen", ip="10.20.1.34")]
    assert run_detection(events) == []


def test_success_exactly_ten_minutes_after_failures_triggers_rule_two():
    events = failures([0, 60, 120, 180, 240])
    events.append(ev(240 + 600 - 240, "login_success", user="alice.morgan", ip="10.20.1.21"))
    # first failure at 0, success at 600: first failure is exactly at window edge
    assert len(by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES)) == 1


def test_success_just_outside_ten_minutes_does_not_trigger_rule_two():
    events = failures([0, 60, 120, 180, 240])
    events.append(ev(601, "login_success", user="alice.morgan", ip="10.20.1.21"))
    # failures at 0..240 are 361..601 seconds before the success: only four are in-window
    assert by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES) == []


def test_failures_from_a_different_ip_do_not_count_for_rule_two():
    events = failures([0, 60, 120, 180, 240], ip="203.0.113.50")
    events.append(ev(300, "login_success", user="alice.morgan", ip="10.20.1.21"))
    assert by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES) == []


def test_one_failure_burst_is_used_as_evidence_only_once():
    events = failures([0, 60, 120, 180, 240])
    events.append(ev(300, "login_success", user="alice.morgan", ip="10.20.1.21"))
    events.append(ev(360, "login_success", user="alice.morgan", ip="10.20.1.21"))
    rule2 = by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES)
    assert len(rule2) == 1


def test_rule_two_reports_different_targeted_accounts_as_uncertainty():
    events = []
    for i, o in enumerate([0, 60, 120, 180, 240]):
        events.append(ev(o, "login_failure", user=f"account{i}", ip="203.0.113.50"))
    events.append(ev(300, "login_success", user="account9", ip="203.0.113.50"))
    alert = by_rule(run_detection(events), RULE_SUCCESS_AFTER_FAILURES)[0]
    factors = {f["factor"]: f["value"] for f in alert.evidence_factors}
    assert factors["Same account as failures"].startswith("No")


# ---- Evidence, determinism and wording ----------------------------------------
def test_evidence_ids_refer_only_to_input_events():
    events = failures([0, 60, 120, 180, 240])
    input_ids = {e.event_id for e in events}
    for alert in run_detection(events):
        assert {link.event_id for link in alert.evidence} <= input_ids


def test_evidence_is_chronological_with_one_based_positions():
    events = failures([0, 60, 120, 180, 240, 300, 360])
    events.append(ev(420, "login_success", user="alice.morgan", ip="10.20.1.21"))
    for alert in run_detection(events):
        assert [link.position for link in alert.evidence] == list(range(1, len(alert.evidence) + 1))
        times = [e.timestamp for e in events if e.event_id in {link.event_id for link in alert.evidence}]
        assert times == sorted(times)


def test_detection_is_deterministic_regardless_of_input_order():
    events = failures([0, 60, 120, 180, 240, 300, 360])
    events.append(ev(420, "login_success", user="alice.morgan", ip="10.20.1.21"))
    forward = [a.alert_id for a in run_detection(events)]
    backward = [a.alert_id for a in run_detection(list(reversed(events)))]
    assert forward == backward
    assert forward  # sanity: something was detected


def test_alert_wording_never_claims_a_confirmed_attack():
    events = failures([0, 60, 120, 180, 240, 300, 360])
    events.append(ev(420, "login_success", user="alice.morgan", ip="10.20.1.21"))
    for alert in run_detection(events):
        text = " ".join([alert.title, alert.summary, alert.observed, alert.uncertain]).lower()
        assert "confirmed" not in text
        assert "attack occurred" not in text
        assert "the logs alone do not establish" in alert.uncertain.lower()
        assert alert.next_step
