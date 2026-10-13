"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthOut(BaseModel):
    status: str
    service: str
    version: str
    database: str


class EventOut(BaseModel):
    event_id: str
    timestamp: str
    source: str | None = None
    event_type: str
    user: str | None = None
    source_ip: str | None = None
    source_host: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    port: int | None = None
    protocol: str | None = None
    severity: str
    raw: dict[str, Any]


class EventListOut(BaseModel):
    items: list[EventOut]
    total: int
    limit: int
    offset: int


class EvidenceFactor(BaseModel):
    factor: str
    value: str


class AlertSummary(BaseModel):
    alert_id: str
    rule_id: str
    rule_name: str
    priority: str
    title: str
    entity_type: str
    entity_value: str
    affected_user: str | None = None
    affected_source_ip: str | None = None
    affected_host: str | None = None
    first_seen: str
    last_seen: str
    event_count: int
    created_at: str


class AlertListOut(BaseModel):
    items: list[AlertSummary]
    total: int
    limit: int
    offset: int


class EvidenceItem(BaseModel):
    position: int
    role: str
    reason: str
    event: EventOut


class AlertDetail(AlertSummary):
    summary: str
    observed: str = Field(description="What we observed")
    uncertain: str = Field(description="What remains uncertain")
    next_step: str = Field(description="Suggested next investigation step")
    evidence_factors: list[EvidenceFactor]
    supporting_event_ids: list[str]
    evidence: list[EvidenceItem]


class TimelineItem(BaseModel):
    position: int
    role: str
    reason: str
    event: EventOut


class TimelineOut(BaseModel):
    alert_id: str
    items: list[TimelineItem]


class RejectedRecordOut(BaseModel):
    row: int
    reason: str


class ImportResultOut(BaseModel):
    import_id: str
    file_name: str
    source_format: str
    total_records: int
    inserted_events: int
    duplicate_events: int
    rejected_records: int
    rejected_details: list[RejectedRecordOut]
    new_alerts: int
    total_alerts: int
    imported_at: str


class StatsOut(BaseModel):
    total_events: int
    total_alerts: int
    high_priority_alerts: int
    medium_priority_alerts: int
    low_priority_alerts: int
    alerts_by_rule: dict[str, int]
    events_by_type: dict[str, int]
    events_by_severity: dict[str, int]
    last_import_at: str | None = None
