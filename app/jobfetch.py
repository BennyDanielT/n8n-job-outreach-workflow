"""Fetch a public job posting by URL, safely.

- Known ATS boards (Greenhouse, Lever, Ashby) go through their public JSON APIs: clean text, no scraping.
- Anything else: fetch the page, prefer schema.org JobPosting JSON-LD, else readable page text.
- LinkedIn is never fetched here: app/sources/linkedin.py handles it with your signed-in session.
- Server-side request forgery guard: https only, public IPs only, every redirect re-checked, size capped.
  (DNS rebinding between check and connect is still possible; in Azure, run with egress restricted.)
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.schemas import JobPosting

BLOCKED_HOSTS = ("linkedin.com", "lnkd.in")
_UA = "JobCopilot/0.1 (+https://github.com/BennyDanielT)"


class FetchError(ValueError):
    pass


def _check_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https":
        raise FetchError("Only https URLs are supported")
    host = (p.hostname or "").lower()
    if not host:
        raise FetchError("URL has no host")
    if any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS):
        raise FetchError(
            "LinkedIn pages need your signed-in session; add the job from the tracker (uses LINKEDIN_LI_AT)."
        )
    try:
        infos = socket.getaddrinfo(host, p.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise FetchError(f"Can't resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("That address isn't on the public internet")


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _from_json_ld(html: str) -> JobPosting | None:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting" and item.get("description"):
                org = item.get("hiringOrganization") or {}
                loc = item.get("jobLocation") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                addr = loc.get("address", {}) if isinstance(loc, dict) else {}
                place = ", ".join(x for x in (addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")) if isinstance(x, str) and x)
                return JobPosting(
                    title=item.get("title"),
                    company=org.get("name") if isinstance(org, dict) else None,
                    location=place or None,
                    text=_html_to_text(item["description"]),
                )
    return None


def _ats_api(url: str) -> tuple[str, str] | None:
    """Return (api_url, kind) for ATS boards with public JSON APIs."""
    p = urlparse(url)
    host, parts = p.hostname or "", [x for x in p.path.split("/") if x]
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and "jobs" in parts:
        i = parts.index("jobs")
        if i >= 1 and i + 1 < len(parts):
            return f"https://boards-api.greenhouse.io/v1/boards/{parts[i - 1]}/jobs/{parts[i + 1]}", "greenhouse"
    if host == "jobs.lever.co" and len(parts) >= 2:
        return f"https://api.lever.co/v0/postings/{parts[0]}/{parts[1]}", "lever"
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}#{parts[1]}", "ashby"
    return None


async def _get(client: httpx.AsyncClient, url: str, settings: Settings) -> str:
    for _ in range(4):
        _check_url(url)
        async with client.stream("GET", url, headers={"User-Agent": _UA}) as resp:
            if resp.is_redirect:
                url = urljoin(url, resp.headers.get("location", ""))
                continue
            body = b""
            async for chunk in resp.aiter_bytes():
                body += chunk
                if len(body) > settings.fetch_max_bytes:
                    raise FetchError("Page is too large")
            if resp.status_code >= 400:
                raise FetchError(f"Site returned {resp.status_code}")
            return body.decode(resp.encoding or "utf-8", errors="replace")
    raise FetchError("Too many redirects")


async def fetch_job(url: str, settings: Settings) -> JobPosting:
    async with httpx.AsyncClient(timeout=settings.fetch_timeout_s, follow_redirects=False) as client:
        ats = _ats_api(url)
        if ats:
            api_url, kind = ats
            job_id = api_url.split("#", 1)[1] if "#" in api_url else None
            data = json.loads(await _get(client, api_url.split("#", 1)[0], settings))
            if kind == "greenhouse":
                import html as _h

                return JobPosting(
                    url=url, title=data.get("title"), company=None,
                    location=(data.get("location") or {}).get("name"),
                    text=_html_to_text(_h.unescape(data.get("content", ""))),
                )
            if kind == "lever":
                lists = "\n".join(
                    f"{l.get('text', '')}\n{_html_to_text(l.get('content', ''))}" for l in data.get("lists", [])
                )
                return JobPosting(
                    url=url, title=data.get("text"),
                    location=(data.get("categories") or {}).get("location"),
                    text=f"{data.get('descriptionPlain', '')}\n\n{lists}\n\n{data.get('additionalPlain', '')}".strip(),
                )
            if kind == "ashby":
                for job in data.get("jobs", []):
                    if job_id and job_id in (job.get("id"), job.get("jobUrl", "").rstrip("/").split("/")[-1]):
                        return JobPosting(
                            url=url, title=job.get("title"), location=job.get("location"),
                            text=job.get("descriptionPlain") or _html_to_text(job.get("descriptionHtml", "")),
                        )
                raise FetchError("Couldn't find that job on the Ashby board")

        html = await _get(client, url, settings)
        job = _from_json_ld(html)
        if job is None:
            text = _html_to_text(html)
            if len(text) < 200:
                raise FetchError("Couldn't read a job description from that page. Paste the text instead.")
            title = BeautifulSoup(html, "html.parser").title
            job = JobPosting(title=title.get_text(strip=True) if title else None, text=text[:40_000])
        job.url = url
        return job
