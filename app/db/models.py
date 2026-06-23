"""ReconHive data model (PostgreSQL).

Design notes
------------
* ``engagements`` group everything under one client authorization. Nothing
  exists outside an engagement -- a host without an engagement is meaningless
  for a pentest tool, and it lets us cascade-purge data when an engagement ends.
* ``scope_entries`` are the persisted form of :class:`app.scope.guard.ScopeEntry`.
  Stored as native PostgreSQL ``CIDR`` so we *could* offload containment checks
  to SQL (``inet <<= cidr``), but the Python ScopeGuard remains the source of
  truth for decisions so the gate logic is testable in isolation.
* ``hosts`` / ``services`` are the recon results. ``services`` carries a
  ``tsvector`` for the full-text side of the search DSL and JSONB for
  semi-structured TLS / fingerprint data.
* ``audit_log`` records every authorization decision and job lifecycle event.
  Append-only by convention; this is the artifact you hand the client.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, INET, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


# --- enums ------------------------------------------------------------------

class ScopeKind(str, enum.Enum):
    allow = "allow"
    deny = "deny"


class JobStatus(str, enum.Enum):
    pending = "pending"
    authorizing = "authorizing"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobType(str, enum.Enum):
    discovery = "discovery"      # host liveness
    port_scan = "port_scan"      # open ports
    banner_grab = "banner_grab"  # service banners + fingerprint
    enrich = "enrich"            # geoip / asn / tls


class Transport(str, enum.Enum):
    tcp = "tcp"
    udp = "udp"


class AuditAction(str, enum.Enum):
    scope_decision = "scope_decision"
    job_submitted = "job_submitted"
    job_started = "job_started"
    job_finished = "job_finished"
    scope_changed = "scope_changed"


# --- engagement -------------------------------------------------------------

class Engagement(Base, TimestampMixin):
    __tablename__ = "engagements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The signed authorization reference -- SOW id, RoE document, ticket, etc.
    authorization_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    scope_entries: Mapped[list["ScopeEntryRow"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    hosts: Mapped[list["Host"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ScanJob"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        Index("ix_engagements_active", "is_active"),
    )


# --- scope entries ----------------------------------------------------------

class ScopeEntryRow(Base, TimestampMixin):
    __tablename__ = "scope_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    cidr: Mapped[str] = mapped_column(CIDR, nullable=False)
    kind: Mapped[ScopeKind] = mapped_column(
        Enum(ScopeKind, name="scope_kind"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(500))

    engagement: Mapped[Engagement] = relationship(back_populates="scope_entries")

    __table_args__ = (
        UniqueConstraint("engagement_id", "cidr", "kind", name="cidr_kind"),
        Index("ix_scope_entries_engagement", "engagement_id"),
        # GiST index makes inet containment queries (inet <<= cidr) fast.
        Index("ix_scope_entries_cidr_gist", "cidr", postgresql_using="gist"),
    )


# --- hosts ------------------------------------------------------------------

class Host(Base, TimestampMixin):
    __tablename__ = "hosts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    ip: Mapped[str] = mapped_column(INET, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255))

    # enrichment
    asn: Mapped[int | None] = mapped_column(Integer)
    as_org: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(2))   # ISO 3166-1 alpha-2
    city: Mapped[str | None] = mapped_column(String(128))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    os_guess: Mapped[str | None] = mapped_column(String(128))

    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    engagement: Mapped[Engagement] = relationship(back_populates="hosts")
    services: Mapped[list["Service"]] = relationship(
        back_populates="host", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("engagement_id", "ip", name="ip"),
        Index("ix_hosts_ip_gist", "ip", postgresql_using="gist"),
        Index("ix_hosts_country", "country"),
        Index("ix_hosts_asn", "asn"),
    )


# --- services ---------------------------------------------------------------

class Service(Base, TimestampMixin):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    host_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False
    )
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    transport: Mapped[Transport] = mapped_column(
        Enum(Transport, name="transport"), default=Transport.tcp, nullable=False
    )

    # fingerprint
    product: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str | None] = mapped_column(String(128))
    extra_info: Mapped[str | None] = mapped_column(String(255))
    cpe: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)

    banner: Mapped[str | None] = mapped_column(Text)
    tls: Mapped[dict | None] = mapped_column(JSONB)   # cert subject/issuer/SANs/expiry
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # extensible

    # full-text search target (populated by trigger or app-side)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    host: Mapped[Host] = relationship(back_populates="services")

    __table_args__ = (
        UniqueConstraint("host_id", "port", "transport", name="host_port"),
        CheckConstraint("port >= 0 AND port <= 65535", name="port_range"),
        Index("ix_services_port", "port"),
        Index("ix_services_product", "product"),
        Index("ix_services_search_gin", "search_vector", postgresql_using="gin"),
    )


# --- scan jobs --------------------------------------------------------------

class ScanJob(Base, TimestampMixin):
    __tablename__ = "scan_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, name="job_type"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.pending, nullable=False
    )

    # what was REQUESTED vs what was actually AUTHORIZED after the ScopeGuard ran
    requested_targets: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    authorized_targets: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )
    rejected_targets: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, nullable=False
    )

    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engagement: Mapped[Engagement] = relationship(back_populates="jobs")

    __table_args__ = (
        Index("ix_scan_jobs_status", "status"),
        Index("ix_scan_jobs_engagement", "engagement_id"),
    )


# --- audit log --------------------------------------------------------------

class AuditLog(Base):
    """Append-only. The compliance artifact for the engagement."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="SET NULL")
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), nullable=False
    )
    target: Mapped[str | None] = mapped_column(String(255))
    verdict: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_audit_log_ts", "ts"),
        Index("ix_audit_log_engagement", "engagement_id"),
        Index("ix_audit_log_action", "action"),
    )
