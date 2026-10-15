"""Tracker storage: jobs you've found, where each application stands, and how it got there."""

from __future__ import annotations

import enum
from collections.abc import Iterator
from datetime import date, datetime, timezone
from functools import lru_cache

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Status(str, enum.Enum):
    new = "new"                    # found, not reviewed
    saved = "saved"                # worth applying to
    applied = "applied"
    screen = "screen"              # recruiter call
    interviewing = "interviewing"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    archived = "archived"          # not interested


# Statuses that mean a human replied after you applied.
RESPONDED = {Status.screen, Status.interviewing, Status.offer}
APPLIED_OR_LATER = {Status.applied, Status.screen, Status.interviewing, Status.offer, Status.rejected,
                    Status.withdrawn}


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_job_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Multi-user later: every row gets an owner. Null = the single local user.
    owner_id: Mapped[str | None] = mapped_column(String(64), index=True)

    source: Mapped[str] = mapped_column(String(32), default="manual")   # linkedin | greenhouse | lever | web | manual
    external_id: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(1024))
    apply_url: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str | None] = mapped_column(String(300))
    company: Mapped[str | None] = mapped_column(String(300), index=True)
    location: Mapped[str | None] = mapped_column(String(300))
    workplace: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    posted: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[Status] = mapped_column(Enum(Status, native_enum=False, length=20), default=Status.new, index=True)
    applied_on: Mapped[date | None] = mapped_column(Date)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_url: Mapped[str | None] = mapped_column(String(1024))
    notes: Mapped[str | None] = mapped_column(Text)

    # Latest tailoring run
    fit_score: Mapped[float | None] = mapped_column(Float)
    tailor_result: Mapped[dict | None] = mapped_column(JSON)   # fit + faithfulness + requirements
    resume_html: Mapped[str | None] = mapped_column(Text)       # tailored, possibly hand-edited
    tailored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    events: Mapped[list["JobEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan",
                                                    order_by="JobEvent.at")


class JobEvent(Base):
    """Append-only history: status changes, tailoring runs, notes."""

    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(32))          # created | status | tailored | edited
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    detail: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="events")


@lru_cache
def _engine(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine


def session_factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=_engine(url), expire_on_commit=False)


def get_session(url: str) -> Iterator[Session]:
    with session_factory(url)() as s:
        yield s
