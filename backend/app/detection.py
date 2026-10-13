"""Transparent, rule-based detection (no AI / ML).

Core principle: "Evidence first, score second."
A rule match is an investigation lead, not proof of an attack. Every alert
states what was observed, what remains uncertain, and what to check next.

All thresholds live in the constants below so they are easy to change.
Detection is deterministic: the same events always produce the same alerts
with the same IDs.
"""

from __future__ import annotations

import bisect
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from .log_parser import LOGIN_FAILURE, LOGIN_SUCCESS
from .models import DetectedAlert, EvidenceLink, NormalizedEvent

# ---- Tunable thresholds -------------------------------------------------------
FAILED_LOGIN_THRESHOLD = 5  # Rule 1 and Rule 2: minimum failed attempts
FAILED_LOGIN_WINDOW_SECONDS = 600  # ten-minute window (inclusive at both ends)
HIGH_PRIORITY_FAILURE_COUNT = 10  # Rule 1 escalates to High at this many failures

# ---- Rule identifiers and names ----------------------------------------------
RULE_REPEATED_FAILURES = "R1_REPEATED_FAILED_LOGINS"
RULE_REPEATED_FAILURES_NAME = "Repeated failed logins"
RULE_SUCCESS_AFTER_FAILURES = "R2_SUCCESS_AFTER_FAILURES"
RULE_SUCCESS_AFTER_FAILURES_NAME = "Successful login after failures"

PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"
PRIORITY_ORDER = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 1, PRIORITY_LOW: 2}

UNCERTAINTY_GENERAL = (
    "The logs alone do not establish whether the activity was authorized or malicious."
)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _fmt_seconds(seconds: float) -> str:
    seconds = int(round(seconds))
    minutes, secs = divmod(seconds, 60)
    if minutes and secs:
        return f"{minutes}m {secs}s"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _alert_id(fingerprint: str) -> str:
    return "alrt_" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]


def _sorted_events(events: list[NormalizedEvent]) -> list[NormalizedEvent]:
    return sorted(events, key=lambda e: (e.timestamp, e.event_id))


# ---- Rule 1: repeated failed logins -------------------------------------------
def _sliding_clusters(events: list[NormalizedEvent], times: list[datetime]) -> list[list[int]]:
    """Greedy, non-overlapping clusters of >= threshold failures inside the window.

    Returns lists of indexes into `events`. Scans left to right; once a cluster
    is emitted, scanning resumes after its last event so one burst is reported once.
    """
    window = FAILED_LOGIN_WINDOW_SECONDS
    clusters: list[list[int]] = []
    n = len(events)
    i = 0
    j = 0
    while i < n:
        j = max(j, i)
        while j + 1 < n and (times[j + 1] - times[i]).total_seconds() <= window:
            j += 1
        if j - i + 1 >= FAILED_LOGIN_THRESHOLD:
            clusters.append(list(range(i, j + 1)))
            i = j + 1
        else:
            i += 1
    return clusters


def _build_repeated_failure_alert(
    entity_type: str, entity_value: str, cluster: list[NormalizedEvent], times: list[datetime]
) -> DetectedAlert:
    count = len(cluster)
    first, last = cluster[0], cluster[-1]
    observed_seconds = (times[-1] - times[0]).total_seconds()
    ips = sorted({e.source_ip for e in cluster if e.source_ip})
    users = sorted({e.user for e in cluster if e.user})
    hosts = [e.source_host for e in cluster if e.source_host]
    window_minutes = FAILED_LOGIN_WINDOW_SECONDS // 60

    if entity_type == "user":
        entity_desc = f"account '{entity_value}'"
        title = f"Repeated failed logins for account {entity_value}"
        affected_user = entity_value
        affected_ip = ips[0] if len(ips) == 1 else None
    else:
        entity_desc = f"source IP {entity_value}"
        title = f"Repeated failed logins from source IP {entity_value}"
        affected_user = users[0] if len(users) == 1 else None
        affected_ip = entity_value

    priority = PRIORITY_HIGH if count >= HIGH_PRIORITY_FAILURE_COUNT else PRIORITY_MEDIUM
    account_note = (
        f"across {len(users)} accounts ({', '.join(users)})" if entity_type == "source_ip" and users
        else f"from {len(ips)} source IP(s)" if entity_type == "user" and ips
        else ""
    )
    summary = (
        f"{count} failed login events for {entity_desc} occurred within "
        f"{_fmt_seconds(observed_seconds)} (rule threshold: {FAILED_LOGIN_THRESHOLD} within "
        f"{window_minutes} minutes)."
    )
    observed = (
        f"{count} failed login attempts for {entity_desc} {account_note}".rstrip()
        + f" were recorded between {first.timestamp} and {last.timestamp}."
    )
    uncertain = (
        UNCERTAINTY_GENERAL
        + " The failures may come from a mistyped password, an expired credential, a"
        " misconfigured service, or a deliberate guessing attempt; the logs do not say which."
    )
    next_step = (
        "Confirm with the account owner or service owner whether these failures were expected. "
        "Check whether the source IP is a known system and review other activity for this entity."
    )
    factors = [
        {"factor": "Failed login count", "value": str(count)},
        {"factor": "Rule threshold", "value": f"{FAILED_LOGIN_THRESHOLD} or more within {window_minutes} minutes"},
        {"factor": "Observed time span", "value": _fmt_seconds(observed_seconds)},
        {"factor": "Distinct source IPs", "value": str(len(ips))},
        {"factor": "Distinct accounts", "value": str(len(users))},
    ]
    if priority == PRIORITY_HIGH:
        factors.append({"factor": "Priority escalation", "value": f"{count} failures reached the High threshold of {HIGH_PRIORITY_FAILURE_COUNT}"})

    evidence = [
        EvidenceLink(
            event_id=e.event_id,
            position=idx,
            role="failed_login",
            reason=(
                f"Failed login {idx} of {count} for {entity_desc}"
                f" inside the {window_minutes}-minute window."
            ),
        )
        for idx, e in enumerate(cluster, start=1)
    ]
    fingerprint = RULE_REPEATED_FAILURES + "|" + ",".join(sorted(e.event_id for e in cluster))
    return DetectedAlert(
        alert_id=_alert_id(fingerprint),
        fingerprint=fingerprint,
        rule_id=RULE_REPEATED_FAILURES,
        rule_name=RULE_REPEATED_FAILURES_NAME,
        priority=priority,
        title=title,
        summary=summary,
        observed=observed,
        uncertain=uncertain,
        next_step=next_step,
        entity_type=entity_type,
        entity_value=entity_value,
        affected_user=affected_user,
        affected_source_ip=affected_ip,
        affected_host=hosts[0] if hosts else None,
        first_seen=first.timestamp,
        last_seen=last.timestamp,
        evidence_factors=factors,
        evidence=evidence,
    )


def detect_repeated_failures(ordered: list[NormalizedEvent]) -> list[DetectedAlert]:
    failures = [e for e in ordered if e.event_type == LOGIN_FAILURE]
    alerts: list[DetectedAlert] = []
    for entity_type in ("user", "source_ip"):
        groups: dict[str, list[NormalizedEvent]] = defaultdict(list)
        for event in failures:
            key = event.user if entity_type == "user" else event.source_ip
            if key:
                groups[key].append(event)
        for key in sorted(groups):
            group = groups[key]
            times = [_parse(e.timestamp) for e in group]
            for indexes in _sliding_clusters(group, times):
                cluster = [group[i] for i in indexes]
                cluster_times = [times[i] for i in indexes]
                alerts.append(_build_repeated_failure_alert(entity_type, key, cluster, cluster_times))
    return alerts


# ---- Rule 2: successful login after failures ------------------------------------
def detect_success_after_failures(ordered: list[NormalizedEvent]) -> list[DetectedAlert]:
    """Failures from a source IP shortly before a successful login from that same IP.

    Each failed attempt is used as evidence at most once, so a single burst of
    failures produces one alert even if the same IP logs in several times.
    """
    window = FAILED_LOGIN_WINDOW_SECONDS
    failures_by_ip: dict[str, list[NormalizedEvent]] = defaultdict(list)
    for event in ordered:
        if event.event_type == LOGIN_FAILURE and event.source_ip:
            failures_by_ip[event.source_ip].append(event)
    failure_times = {ip: [_parse(e.timestamp) for e in evs] for ip, evs in failures_by_ip.items()}

    consumed: set[str] = set()
    alerts: list[DetectedAlert] = []
    successes = [e for e in ordered if e.event_type == LOGIN_SUCCESS and e.source_ip]
    for success in successes:
        ip = success.source_ip
        if ip not in failures_by_ip:
            continue
        success_time = _parse(success.timestamp)
        times = failure_times[ip]
        lo = bisect.bisect_left(times, success_time.timestamp() - window, key=lambda t: t.timestamp())
        hi = bisect.bisect_right(times, success_time.timestamp(), key=lambda t: t.timestamp())
        candidates = [
            (failures_by_ip[ip][k], times[k])
            for k in range(lo, hi)
            if failures_by_ip[ip][k].event_id not in consumed
        ]
        if len(candidates) < FAILED_LOGIN_THRESHOLD:
            continue
        consumed.update(f.event_id for f, _ in candidates)
        alerts.append(_build_success_after_failures_alert(ip, success, success_time, candidates))
    return alerts


def _build_success_after_failures_alert(
    ip: str,
    success: NormalizedEvent,
    success_time: datetime,
    candidates: list[tuple[NormalizedEvent, datetime]],
) -> DetectedAlert:
    failures = [f for f, _ in candidates]
    count = len(failures)
    first_time = candidates[0][1]
    last_failure_time = candidates[-1][1]
    targeted_users = sorted({f.user for f in failures if f.user})
    same_account = bool(success.user) and targeted_users == [success.user]
    window_minutes = FAILED_LOGIN_WINDOW_SECONDS // 60
    success_account = success.user or "an unspecified account"

    if same_account:
        account_text = f"account '{success.user}'"
    elif targeted_users:
        account_text = f"{len(targeted_users)} account(s) ({', '.join(targeted_users)})"
    else:
        account_text = "no recorded account"

    gap = (success_time - last_failure_time).total_seconds()
    summary = (
        f"Possible credential compromise requiring validation: {count} failed login attempts "
        f"from source IP {ip} were followed by a successful login from the same IP "
        f"{_fmt_seconds(gap)} after the last failure."
    )
    observed = (
        "Multiple failed login attempts were followed by a successful login from the same source IP. "
        f"{count} failed attempts for {account_text} were recorded from {ip} between "
        f"{failures[0].timestamp} and {failures[-1].timestamp}; a successful login from {ip} "
        f"for {success_account} followed at {success.timestamp}."
    )
    uncertain = (
        UNCERTAINTY_GENERAL
        + " A legitimate user may have mistyped a password several times before succeeding, "
        "or the successful login may have been made by someone other than the account owner."
    )
    next_step = (
        "Verify the login with the account owner. Review related activity for this account and "
        "source IP, including any logins or network connections after the successful login."
    )
    factors = [
        {"factor": "Failed attempts before success", "value": str(count)},
        {"factor": "Rule window", "value": f"{window_minutes} minutes before the successful login"},
        {"factor": "Same source IP", "value": "Yes (rule condition)"},
        {"factor": "Failed attempts span", "value": _fmt_seconds((last_failure_time - first_time).total_seconds())},
        {"factor": "Gap from last failure to success", "value": _fmt_seconds(gap)},
        {
            "factor": "Same account as failures",
            "value": "Yes" if same_account else f"No: failures targeted {', '.join(targeted_users) or 'no recorded account'}",
        },
    ]

    evidence = [
        EvidenceLink(
            event_id=f.event_id,
            position=0,  # filled in after sorting below
            role="failed_login",
            reason=(
                f"Failed login attempt {idx} of {count} from {ip}"
                + (f" for account '{f.user}'" if f.user else "")
                + f", {_fmt_seconds((success_time - t).total_seconds())} before the successful login."
            ),
        )
        for idx, (f, t) in enumerate(candidates, start=1)
    ]
    evidence.append(
        EvidenceLink(
            event_id=success.event_id,
            position=0,
            role="successful_login",
            reason=(
                f"Successful login from {ip}"
                + (f" for account '{success.user}'" if success.user else "")
                + f" after {count} failed attempts within the {window_minutes}-minute window."
            ),
        )
    )
    all_events = failures + [success]
    evidence = _chronological(evidence, all_events)

    fingerprint = RULE_SUCCESS_AFTER_FAILURES + "|" + ",".join(sorted(e.event_id for e in all_events))
    return DetectedAlert(
        alert_id=_alert_id(fingerprint),
        fingerprint=fingerprint,
        rule_id=RULE_SUCCESS_AFTER_FAILURES,
        rule_name=RULE_SUCCESS_AFTER_FAILURES_NAME,
        priority=PRIORITY_HIGH,
        title="Possible credential compromise requiring validation",
        summary=summary,
        observed=observed,
        uncertain=uncertain,
        next_step=next_step,
        entity_type="source_ip",
        entity_value=ip,
        affected_user=success.user or (targeted_users[0] if len(targeted_users) == 1 else None),
        affected_source_ip=ip,
        affected_host=success.source_host or next((f.source_host for f in failures if f.source_host), None),
        first_seen=failures[0].timestamp,
        last_seen=success.timestamp,
        evidence_factors=factors,
        evidence=evidence,
    )


def _chronological(links: list[EvidenceLink], events: list[NormalizedEvent]) -> list[EvidenceLink]:
    """Order evidence by event timestamp and assign 1-based positions."""
    by_id = {e.event_id: e for e in events}
    ordered = sorted(links, key=lambda link: (by_id[link.event_id].timestamp, link.event_id))
    return [link.model_copy(update={"position": i}) for i, link in enumerate(ordered, start=1)]


# ---- Public entry point ------------------------------------------------------
def run_detection(events: list[NormalizedEvent]) -> list[DetectedAlert]:
    """Run every rule over the full event set. Duplicate fingerprints are merged."""
    ordered = _sorted_events(events)
    raw_alerts = detect_repeated_failures(ordered) + detect_success_after_failures(ordered)

    unique: dict[str, DetectedAlert] = {}
    for alert in raw_alerts:
        # Same evidence set from user-based and IP-based grouping -> keep the first one.
        unique.setdefault(alert.fingerprint, alert)

    return sorted(
        unique.values(),
        key=lambda a: (PRIORITY_ORDER[a.priority], a.first_seen, a.alert_id),
    )
