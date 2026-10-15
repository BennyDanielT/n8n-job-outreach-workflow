"""Application tracker API: find jobs, track every application, tailor a resume for each."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import pipeline, render
from app.config import Settings, get_settings
from app.db import APPLIED_OR_LATER, RESPONDED, Job, JobEvent, Status, utcnow
from app.deps import get_db, get_llm, get_master, tailor_limit
from app.intake import fetch_posting
from app.jobfetch import FetchError
from app.llm import LLM, LLMError
from app.schemas import Issue, JobPosting, MasterResume, TailorResult
from app.sources import linkedin

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Tracker"])


# --------------------------------------------------------------------------- models
class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str | None
    url: str | None
    apply_url: str | None
    title: str | None
    company: str | None
    location: str | None
    workplace: str | None
    posted: str | None
    status: Status
    applied_on: date | None
    follow_up_on: date | None
    contact_name: str | None
    contact_url: str | None
    notes: str | None
    fit_score: float | None
    has_description: bool
    has_resume: bool
    tailored_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, j: Job) -> "JobOut":
        d = {c: getattr(j, c) for c in cls.model_fields if hasattr(j, c)}
        return cls(**d, has_description=bool(j.description), has_resume=bool(j.resume_html))


class JobDetail(JobOut):
    description: str | None
    tailor_result: dict | None
    events: list[dict]

    @classmethod
    def of(cls, j: Job) -> "JobDetail":
        base = JobOut.of(j).model_dump()
        return cls(**base, description=j.description, tailor_result=j.tailor_result,
                   events=[{"at": e.at, "kind": e.kind, "from": e.from_status, "to": e.to_status,
                            "detail": e.detail} for e in j.events])


class JobCreate(BaseModel):
    url: str | None = Field(None, description="Posting URL. LinkedIn URLs use your signed-in session.")
    text: str | None = Field(None, description="Description text, if you'd rather paste it")
    title: str | None = None
    company: str | None = None
    location: str | None = None
    status: Status = Status.saved


class JobPatch(BaseModel):
    status: Status | None = None
    applied_on: date | None = None
    follow_up_on: date | None = None
    contact_name: str | None = None
    contact_url: str | None = None
    notes: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None


class LinkedInSearch(BaseModel):
    keywords: str = Field(..., min_length=2, examples=["AI Engineer"])
    location: str | None = Field("Canada", description="Free text, or use geo_id")
    geo_id: str | None = Field(None, description="LinkedIn geo id, e.g. 101174742 = Canada (see docs/linkedin-geocodes.md)")
    posted_within_hours: int | None = Field(168, description="24, 72, 168 or 720")
    remote_only: bool = False
    limit: int = Field(25, ge=1, le=100)
    fetch_descriptions: bool = Field(False, description="Open every job to read its description (slow)")


class SearchResult(BaseModel):
    found: int
    added: int
    already_tracked: int
    jobs: list[JobOut]


class ResumeEdit(BaseModel):
    html: str = Field(..., max_length=2_000_000)


class Stats(BaseModel):
    by_status: dict[str, int]
    applied_total: int
    applied_last_7_days: int
    responded: int
    response_rate: float
    follow_ups_due: int
    weekly_target: int = 8


# --------------------------------------------------------------------------- helpers
def _get(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def _set_status(db: Session, job: Job, new: Status, detail: str | None = None) -> None:
    if job.status == new:
        return
    db.add(JobEvent(job=job, kind="status", from_status=job.status.value, to_status=new.value, detail=detail))
    if new == Status.applied and job.applied_on is None:
        job.applied_on = date.today()
        # Default nudge: follow up a week after applying.
        job.follow_up_on = job.follow_up_on or date.today() + timedelta(days=7)
    job.status = new


def _existing(db: Session, source: str, external_id: str | None, url: str | None) -> Job | None:
    conds = []
    if external_id:
        conds.append((Job.source == source) & (Job.external_id == external_id))
    if url:
        conds.append(Job.url == url)
    return db.scalar(select(Job).where(or_(*conds))) if conds else None


# --------------------------------------------------------------------------- jobs
@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: list[Status] | None = Query(None),
    q: str | None = None,
    follow_up_due: bool = False,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status.in_(status))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like)))
    if follow_up_due:
        stmt = stmt.where(Job.follow_up_on <= date.today(), Job.status.in_([Status.applied, Status.screen,
                                                                             Status.interviewing]))
    stmt = stmt.order_by(Job.updated_at.desc()).limit(limit)
    return [JobOut.of(j) for j in db.scalars(stmt)]


@router.post("/jobs", response_model=JobDetail, status_code=201)
async def create_job(body: JobCreate, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    if not body.url and not body.text:
        raise HTTPException(422, "Give a URL or paste the description")
    extra: dict = {"source": "manual", "external_id": None}
    posting: JobPosting | None = None
    if body.url:
        if (dup := _existing(db, "linkedin" if linkedin.is_linkedin(body.url) else "web",
                             linkedin.extract_job_id(body.url) if linkedin.is_linkedin(body.url) else body.url,
                             body.url)):
            raise HTTPException(409, f"Already tracking this job (#{dup.id})")
        if not body.text:
            try:
                posting, extra = await fetch_posting(body.url, s)
            except FetchError as e:
                raise HTTPException(422, str(e)) from e
    job = Job(
        source=extra.get("source", "manual"), external_id=extra.get("external_id"),
        url=posting.url if posting and posting.url else body.url,
        apply_url=extra.get("apply_url"), posted=extra.get("posted"), workplace=extra.get("workplace"),
        title=body.title or (posting.title if posting else None),
        company=body.company or (posting.company if posting else None),
        location=body.location or (posting.location if posting else None),
        description=body.text or (posting.text if posting else None),
        status=Status.new,
    )
    db.add(job)
    db.add(JobEvent(job=job, kind="created", detail=job.source))
    _set_status(db, job, body.status)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "Already tracking this job") from e
    db.refresh(job)
    return JobDetail.of(job)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: Session = Depends(get_db)):
    return JobDetail.of(_get(db, job_id))


@router.patch("/jobs/{job_id}", response_model=JobDetail)
def update_job(job_id: int, body: JobPatch, db: Session = Depends(get_db)):
    job = _get(db, job_id)
    data = body.model_dump(exclude_unset=True)
    new_status = data.pop("status", None)
    for k, v in data.items():
        setattr(job, k, v)
    if new_status is not None:
        _set_status(db, job, Status(new_status))
    if "notes" in data:
        db.add(JobEvent(job=job, kind="edited", detail="notes"))
    db.commit()
    db.refresh(job)
    return JobDetail.of(job)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, job_id))
    db.commit()


@router.post("/jobs/{job_id}/refresh", response_model=JobDetail)
async def refresh_description(job_id: int, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    """Re-read the posting (e.g. a LinkedIn search result that has no description yet)."""
    job = _get(db, job_id)
    if not job.url:
        raise HTTPException(422, "This job has no URL")
    try:
        posting, extra = await fetch_posting(job.url, s)
    except FetchError as e:
        raise HTTPException(422, str(e)) from e
    job.description = posting.text
    job.title = job.title or posting.title
    job.company = job.company or posting.company
    job.location = job.location or posting.location
    for k in ("apply_url", "posted", "workplace"):
        if extra.get(k):
            setattr(job, k, extra[k])
    db.commit()
    db.refresh(job)
    return JobDetail.of(job)


# --------------------------------------------------------------------------- LinkedIn search
@router.post("/jobs/search/linkedin", response_model=SearchResult)
async def search_linkedin(body: LinkedInSearch, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    known = set(db.scalars(select(Job.external_id).where(Job.source == "linkedin")))

    def go() -> list[linkedin.LinkedInJob]:
        with linkedin.LinkedInBrowser(s) as b:
            found = b.search(body.keywords, location=body.location, geo_id=body.geo_id,
                             posted_within_hours=body.posted_within_hours, remote_only=body.remote_only,
                             limit=body.limit)
            if body.fetch_descriptions:
                detailed = []
                for j in found:
                    if j.job_id in known:
                        detailed.append(j)
                        continue
                    try:
                        detailed.append(b.job(j.job_id))
                    except linkedin.LinkedInError as e:
                        log.warning("linkedin job %s: %s", j.job_id, e)
                        detailed.append(j)
                found = detailed
            return found

    try:
        results = await asyncio.to_thread(go)
    except linkedin.LinkedInError as e:
        raise HTTPException(502, str(e)) from e
    except Exception as e:  # selenium/driver problems
        log.exception("linkedin search failed")
        raise HTTPException(502, f"LinkedIn search failed: {type(e).__name__}: {e}") from e

    added: list[Job] = []
    already = 0
    for r in results:
        if _existing(db, "linkedin", r.job_id, r.url):
            already += 1
            continue
        job = Job(source="linkedin", external_id=r.job_id, url=r.url, title=r.title, company=r.company,
                  location=r.location, description=r.description, posted=r.posted, workplace=r.workplace,
                  apply_url=r.apply_url, status=Status.new)
        db.add(job)
        db.add(JobEvent(job=job, kind="created", detail=f"linkedin search: {body.keywords}"))
        added.append(job)
    db.commit()
    return SearchResult(found=len(results), added=len(added), already_tracked=already,
                        jobs=[JobOut.of(j) for j in added])


class PeopleSearch(BaseModel):
    company_slug: str = Field(..., description="From the company URL, e.g. 'shopify'")
    query_params: str = Field("", description="e.g. '?facetGeoRegion=101174742' for Canada")
    min_results: int = Field(20, le=100)


@router.post("/linkedin/people", tags=["LinkedIn"])
async def linkedin_people(body: PeopleSearch, s: Settings = Depends(get_settings)):
    """People at a company, for referral outreach."""
    def go():
        with linkedin.LinkedInBrowser(s) as b:
            return b.people(body.company_slug, body.query_params, body.min_results)

    try:
        return await asyncio.to_thread(go)
    except linkedin.LinkedInError as e:
        raise HTTPException(502, str(e)) from e


# --------------------------------------------------------------------------- tailoring per job
@router.post("/jobs/{job_id}/tailor", response_model=TailorResult, dependencies=[Depends(tailor_limit)])
async def tailor_job(
    job_id: int,
    show_expired_certs: bool = False,
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
    master: MasterResume = Depends(get_master),
    s: Settings = Depends(get_settings),
):
    job = _get(db, job_id)
    if not job.description:
        if not job.url:
            raise HTTPException(422, "No description to tailor against")
        await refresh_description(job_id, db, s)
        db.refresh(job)
    if not job.description or len(job.description) < 50:
        raise HTTPException(422, "The job description is too short to tailor against")

    posting = JobPosting(title=job.title, company=job.company, location=job.location, url=job.url,
                         text=job.description[:40_000])
    try:
        out = await asyncio.to_thread(pipeline.run, llm, s, master, posting)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    try:
        tailored, html, trimmed = await render.fit_one_page(master, out["tailored"], s,
                                                            show_expired_certs=show_expired_certs)
    except render.RenderError as e:
        log.warning("page fit skipped: %s", e)
        tailored, trimmed = out["tailored"], []
        html = render.to_html(master, tailored, show_expired_certs=show_expired_certs)
    out["tailored"] = tailored
    out["faithfulness"].issues += [
        Issue(severity="warning", check="trimmed_to_fit", location="layout", message=f"Dropped {t} to fit")
        for t in trimmed
    ]
    result = TailorResult(**out, html=html)

    job.fit_score = result.fit.score
    job.resume_html = html
    job.tailored_at = datetime.now(timezone.utc)
    job.tailor_result = result.model_dump(mode="json", exclude={"html"})
    job.company = job.company or result.requirements.company
    job.title = job.title or result.requirements.role_title
    db.add(JobEvent(job=job, kind="tailored", detail=f"fit {result.fit.score}, "
                    f"{'faithful' if result.faithfulness.passed else 'needs review'}, {result.attempts} draft(s)"))
    if job.status == Status.new:
        _set_status(db, job, Status.saved, "tailored")
    db.commit()
    return result


@router.get("/jobs/{job_id}/resume", response_class=HTMLResponse)
def job_resume_html(job_id: int, db: Session = Depends(get_db)):
    job = _get(db, job_id)
    if not job.resume_html:
        raise HTTPException(404, "No tailored resume yet")
    return job.resume_html


@router.put("/jobs/{job_id}/resume", status_code=204)
def save_resume(job_id: int, body: ResumeEdit, db: Session = Depends(get_db)):
    job = _get(db, job_id)
    job.resume_html = body.html
    db.add(JobEvent(job=job, kind="edited", detail="resume"))
    db.commit()


@router.get("/jobs/{job_id}/resume.pdf")
async def job_resume_pdf(job_id: int, db: Session = Depends(get_db), s: Settings = Depends(get_settings),
                         master: MasterResume = Depends(get_master)):
    job = _get(db, job_id)
    if not job.resume_html:
        raise HTTPException(404, "No tailored resume yet")
    try:
        pdf = await render.to_pdf(job.resume_html, s)
    except render.RenderError as e:
        raise HTTPException(502, str(e)) from e
    name = "_".join(x for x in (master.contact.name, job.company) if x)
    safe = "".join(c if c.isalnum() else "_" for c in name).strip("_") or "resume"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


# --------------------------------------------------------------------------- stats
@router.get("/stats", response_model=Stats)
def stats(db: Session = Depends(get_db)):
    counts = {st.value: 0 for st in Status}
    for st, n in db.execute(select(Job.status, func.count()).group_by(Job.status)):
        counts[st.value] = n
    applied_total = sum(counts[s.value] for s in APPLIED_OR_LATER)
    week_ago = date.today() - timedelta(days=7)
    applied_week = db.scalar(select(func.count()).where(Job.applied_on >= week_ago)) or 0
    # Anything that ever reached a human conversation counts, even if it later ended in a rejection.
    responded = db.scalar(select(func.count(func.distinct(JobEvent.job_id))).where(
        JobEvent.kind == "status", JobEvent.to_status.in_([s.value for s in RESPONDED]))) or 0
    due = db.scalar(select(func.count()).where(
        Job.follow_up_on <= date.today(),
        Job.status.in_([Status.applied, Status.screen, Status.interviewing]))) or 0
    return Stats(by_status=counts, applied_total=applied_total, applied_last_7_days=applied_week,
                 responded=responded, response_rate=round(responded / applied_total, 3) if applied_total else 0.0,
                 follow_ups_due=due)
