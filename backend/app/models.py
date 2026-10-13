"""Internal domain models shared by the parser, detection engine and database layer.

These are Pydantic models so that every normalized event and every generated
alert is validated before it is stored.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedEvent(BaseModel):
    """Common event structure produced by the log parser (see docs/architecture.md)."""

    event_id: str
    timestamp: str  # UTC ISO-8601, e.g. 2026-10-12T08:00:00Z
    source: str | None = None
    event_type: str
    user: str | None = None
    source_ip: str | None = None
    source_host: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    port: int | None = None
    protocol: str | None = None
    severity: str = "info"
    raw: dict[str, Any] = Field(default_factory=dict)


class EvidenceLink(BaseModel):
    """Links one stored event to an alert, with the reason it is relevant."""

    event_id: str
    position: int
    role: str
    reason: str


class DetectedAlert(BaseModel):
    """An alert produced by a detection rule. Never a confirmed attack."""

    alert_id: str
    fingerprint: str
    rule_id: str
    rule_name: str
    priority: str  # High | Medium | Low
    title: str
    summary: str
    observed: str  # "What we observed"
    uncertain: str  # "What remains uncertain"
    next_step: str  # "Suggested next step"
    entity_type: str  # user | source_ip
    entity_value: str
    affected_user: str | None = None
    affected_source_ip: str | None = None
    affected_host: str | None = None
    first_seen: str
    last_seen: str
    evidence_factors: list[dict[str, str]] = Field(default_factory=list)
    evidence: list[EvidenceLink] = Field(default_factory=list)
