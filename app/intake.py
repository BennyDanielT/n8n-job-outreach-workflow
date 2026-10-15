"""Turn a URL into a job posting, whatever site it's on."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from app.config import Settings
from app.jobfetch import FetchError, fetch_job
from app.schemas import JobPosting
from app.sources import linkedin


def source_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if linkedin.is_linkedin(url):
        return "linkedin"
    for name in ("greenhouse", "lever", "ashbyhq", "workday", "smartrecruiters"):
        if name in host:
            return name.replace("ashbyhq", "ashby")
    return "web"


async def fetch_posting(url: str, settings: Settings) -> tuple[JobPosting, dict]:
    """Returns (posting, extra fields for the tracker)."""
    if linkedin.is_linkedin(url):
        def go():
            with linkedin.LinkedInBrowser(settings) as b:
                return b.job(url)

        try:
            j = await asyncio.to_thread(go)
        except linkedin.LinkedInError as e:
            raise FetchError(str(e)) from e
        posting = JobPosting(title=j.title, company=j.company, location=j.location, url=j.url,
                             text=j.description or "")
        return posting, {"source": "linkedin", "external_id": j.job_id, "posted": j.posted,
                         "workplace": j.workplace, "apply_url": j.apply_url}
    posting = await fetch_job(url, settings)
    return posting, {"source": source_of(url), "external_id": url}
