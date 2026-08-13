"""Data-intelligence layer: entities + evidence + quality for the upgraded
discovery/crawl pipeline.

This is the evidence-based, provenance-backed extension of the existing
`leads`-centric schema. `leads` remains the workspace-facing record; these
tables store the *how and where* every important value came from, plus the
entity/freshness/quality layer that lets Crawler.io self-improve over time.

Every table is global (not workspace-scoped) — like discovery_cache — because
this is public business-listing + web-published data; workspace enforcement
happens at the Lead/API layer as today.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    """A single crawled/discovered web source (page). Deduplicated by URL; used
    by source_evidence as the provenance anchor for every stored field."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("url", name="uq_sources_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    access_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    evidence: Mapped[list["SourceEvidence"]] = relationship(back_populates="source")


class SourceEvidence(Base):
    """Per-field provenance. Every important value is traceable:
    {'value', 'source_url', 'source_type', 'collected_at', 'confidence', 'status'}."""

    __tablename__ = "source_evidence"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "field_name", "field_value", name="uq_evidence_field"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="first_party")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collected")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    source: Mapped[Optional["Source"]] = relationship(back_populates="evidence")


class EmailRecord(Base):
    """A discovered email value + its verification state. Value normalized
    (lowercase/trim), deduplicated, classification stored."""

    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("value", name="uq_emails_value"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    value: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    classification: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_found", index=True
    )
    verification_meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PhoneRecord(Base):
    """A discovered phone value: raw + E.164 normalized + confidence."""

    __tablename__ = "phones"
    __table_args__ = (UniqueConstraint("e164", name="uq_phones_e164"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    raw_phone: Mapped[str] = mapped_column(String(60), nullable=False)
    e164: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    normalization: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialProfile(Base):
    """A publicly exposed official social URL (Instagram/Facebook/LinkedIn/YouTube/TikTok)."""

    __tablename__ = "social_profiles"
    __table_args__ = (UniqueConstraint("platform", "url", name="uq_social_platform_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="company")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Person(Base):
    """A discovered person (team member / doctor / leadership)."""

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("full_name", "profile_url", name="uq_people_name_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    company_links: Mapped[list["CompanyPerson"]] = relationship(back_populates="person")


class CompanyPerson(Base):
    """Link a person to a company (role-aware, provenance-backed)."""

    __tablename__ = "company_people"
    __table_args__ = (UniqueConstraint("company_id", "person_id", name="uq_company_person"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("people.id"), nullable=False, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)

    person: Mapped["Person"] = relationship(back_populates="company_links")


class CrawlJob(Base):
    """A crawl run for one entity/lead (or a discovery batch)."""

    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    search_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    pages: Mapped[list["CrawlPage"]] = relationship(back_populates="job")


class CrawlPage(Base):
    """The crawl frontier: one row per candidate page with priority/status/retry."""

    __tablename__ = "crawl_pages"
    __table_args__ = (UniqueConstraint("crawl_job_id", "url", name="uq_crawl_page_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    crawl_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("crawl_jobs.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped["CrawlJob"] = relationship(back_populates="pages")


class EnrichmentRun(Base):
    """One enrichment run for an entity; keeps a history of what enrichment did."""

    __tablename__ = "enrichment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    items_found: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class VerificationResult(Base):
    """Log of one verification check (email/phone) with per-check detail."""

    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    field_name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    field_value: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    checks: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EntityMatch(Base):
    """Entity-resolution outcome: two records resolved to the same entity."""

    __tablename__ = "entity_matches"
    __table_args__ = (UniqueConstraint("entity_type", "primary_id", "candidate_id", name="uq_entity_match_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    primary_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="deterministic")
    detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DataQualityScore(Base):
    """Field-level confidence + source count (the confidence engine output)."""

    __tablename__ = "data_quality_scores"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "field_name", name="uq_quality_field"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

class FieldHistory(Base):
    """Immutable change log for entity fields (never destroy evidence)."""

    __tablename__ = "field_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Technographic(Base):
    """A technology reliably detected on a company's website."""

    __tablename__ = "technographics"
    __table_args__ = (UniqueConstraint("company_id", "technology", name="uq_technographic"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    technology: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id"), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IntentSignal(Base):
    """An ICP relevance signal recorded about a lead (industry match, keyword hit, etc.)."""

    __tablename__ = "intent_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, default="lead")
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    signal: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VerifiedFlag(Base):
    """Lightweight marker for a Source that carried a verified field (helper for
    'verified email evidence' lookups without scanning JSON)."""

    __tablename__ = "verified_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)