"""Job Copilot API."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextvars import ContextVar
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from app import pipeline, render, tracker
from app.config import Settings, get_settings
from app.deps import get_llm, load_master, tailor_limit
from app.intake import fetch_posting
from app.jobfetch import FetchError
from app.llm import LLM, LLMError
from app.schemas import (
    FetchJobRequest,
    Issue,
    JobPosting,
    RenderPdfRequest,
    TailorRequest,
    TailorResult,
)

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


def _setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


settings = get_settings()
_setup_logging(settings.log_level)
log = logging.getLogger("job_copilot")

app = FastAPI(
    title="Job Copilot",
    version="0.2.0",
    description="Find jobs, track applications, and tailor a resume for each one without inventing anything.",
)
STATIC = Path(__file__).parent / "static"
app.include_router(tracker.router)


@app.middleware("http")
async def correlation_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id.reset(token)
    response.headers["x-request-id"] = rid
    log.info("%s %s -> %s in %dms", request.method, request.url.path, response.status_code,
             (time.perf_counter() - started) * 1000)
    return response


# ---------------------------------------------------------------- routes
@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "pdf_engine": settings.pdf_engine}


@app.get("/api/v1/sample-job", response_model=JobPosting)
async def sample_job():
    from app.demo import SAMPLE_JOB

    return SAMPLE_JOB


@app.get("/api/v1/master/preview", response_class=HTMLResponse)
async def master_preview(s: Settings = Depends(get_settings)):
    """The master resume rendered as-is, to check the layout."""
    master = load_master(s.master_resume_path)
    return render.to_html(master, render.untailored(master))


@app.post("/api/v1/jobs/fetch", response_model=JobPosting)
async def fetch(req: FetchJobRequest, s: Settings = Depends(get_settings)):
    try:
        posting, _ = await fetch_posting(str(req.url), s)
        return posting
    except FetchError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/v1/tailor", response_model=TailorResult, dependencies=[Depends(tailor_limit)])
async def tailor(req: TailorRequest, llm: LLM = Depends(get_llm), s: Settings = Depends(get_settings)):
    master = req.master_resume or load_master(s.master_resume_path)
    try:
        # The pipeline is synchronous (SDK calls); keep the event loop free.
        out = await asyncio.to_thread(pipeline.run, llm, s, master, req.job)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    try:
        tailored, html, trimmed = await render.fit_one_page(
            master, out["tailored"], s, show_expired_certs=req.show_expired_certs
        )
    except render.RenderError as e:
        # The PDF service is down: still return the content, unmeasured.
        log.warning("page fit skipped: %s", e)
        tailored, trimmed = out["tailored"], []
        html = render.to_html(master, tailored, show_expired_certs=req.show_expired_certs)
    out["tailored"] = tailored
    out["faithfulness"].issues += [
        Issue(severity="warning", check="trimmed_to_fit", location="layout", message=f"Dropped {t} to fit one page")
        for t in trimmed
    ]
    log.info("tailor run=%s fit=%d coverage=%.2f faithful=%s attempts=%d", out["run_id"], out["fit"].score,
             out["fit"].keyword_coverage, out["faithfulness"].passed, out["attempts"])
    return TailorResult(**out, html=html)


@app.post("/api/v1/render/pdf")
async def render_pdf(req: RenderPdfRequest, s: Settings = Depends(get_settings)):
    try:
        pdf = await render.to_pdf(req.html, s)
    except render.RenderError as e:
        raise HTTPException(502, str(e)) from e
    safe = "".join(c for c in req.filename if c.isalnum() or c in "-_.") or "resume.pdf"
    if not safe.endswith(".pdf"):
        safe += ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}"'})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse({"detail": "Something went wrong", "request_id": request_id.get()}, status_code=500)
