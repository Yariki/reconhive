"""API request/response schemas (Pydantic v2)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..db.models import JobStatus, JobType, ScopeKind, Transport


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- engagements ------------------------------------------------------------

class EngagementCreate(BaseModel):
    client_name: str
    authorization_ref: str = Field(..., description="SOW / RoE reference")
    contact: str | None = None
    starts_at: datetime
    ends_at: datetime
    notes: str | None = None


class EngagementOut(ORMModel):
    id: uuid.UUID
    client_name: str
    authorization_ref: str
    contact: str | None
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    notes: str | None


# --- scope ------------------------------------------------------------------

class ScopeEntryCreate(BaseModel):
    cidr: str = Field(..., examples=["10.0.0.0/16", "192.168.1.0/24"])
    kind: ScopeKind = ScopeKind.allow
    expires_at: datetime | None = None
    note: str | None = None


class ScopeEntryOut(ORMModel):
    id: uuid.UUID
    cidr: str
    kind: ScopeKind
    expires_at: datetime | None
    note: str | None

    @field_validator("cidr", mode="before")
    @classmethod
    def _cidr_str(cls, v):
        return str(v)


# --- jobs -------------------------------------------------------------------

class ScanJobCreate(BaseModel):
    job_type: JobType = JobType.banner_grab
    targets: list[str] = Field(..., examples=[["10.0.0.0/24"]])
    ports: list[int] | str | None = Field(
        default=None, description="Explicit ports or a spec like '1-1024'; defaults to top ports"
    )
    requested_by: str = "api"


class ScanJobOut(ORMModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    job_type: JobType
    status: JobStatus
    requested_targets: list[str]
    authorized_targets: list[str]
    rejected_targets: list[str]
    requested_by: str
    stats: dict
    error: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# --- hosts & services -------------------------------------------------------

class ServiceOut(ORMModel):
    id: uuid.UUID
    port: int
    transport: Transport
    product: str | None
    version: str | None
    extra_info: str | None
    cpe: list[str]
    banner: str | None
    tls: dict | None
    data: dict
    last_seen: datetime


class HostSummary(ORMModel):
    id: uuid.UUID
    ip: str
    hostname: str | None
    country: str | None
    city: str | None
    asn: int | None
    as_org: str | None
    os_guess: str | None
    tags: list[str]
    last_seen: datetime

    @field_validator("ip", mode="before")
    @classmethod
    def _ip_str(cls, v):
        return str(v)


class HostOut(HostSummary):
    services: list[ServiceOut] = []


class SearchResult(BaseModel):
    """One service result (Shodan-style banner), with its host summary."""
    host: HostSummary
    service: ServiceOut


# --- audit ------------------------------------------------------------------

class AuditOut(ORMModel):
    id: int
    ts: datetime
    actor: str
    action: str
    target: str | None
    verdict: str | None
    reason: str | None
    detail: dict
