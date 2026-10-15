"""Structured content -> HTML (Jinja, locked layout) -> PDF (Gotenberg or WeasyPrint)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from app.config import Settings
from app.schemas import (
    CertStatus,
    MasterResume,
    TailoredBullet,
    TailoredContent,
    TailoredSection,
)

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=False,
)
_env.globals["fonts_css"] = Markup((_TEMPLATES / "assets" / "fonts.css").read_text())
_env.globals["icons"] = json.loads((_TEMPLATES / "assets" / "icons.json").read_text())

_LINK_ICONS = {"linkedin.com": "linkedin", "github.com": "github", "github.io": "github",
               "youtube.com": "youtube", "youtu.be": "youtube"}


def _link_icon(url: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    for domain, name in _LINK_ICONS.items():
        if host == domain or host.endswith("." + domain) or host.endswith(domain):
            return name
    return "blog"


def _rich(text: str) -> Markup:
    """Escape, then allow **bold** (the only markup bullets may carry)."""
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(escape(text))))


def _cert_when(c) -> str:
    if c.status == CertStatus.in_progress:
        return f"In Progress, target {c.date}" if c.date else "In Progress"
    if c.status == CertStatus.expired:
        return f"{c.date}, expired" if c.date else "expired"
    return c.date or ""


_env.filters.update(
    phone_href=lambda p: "+1" + re.sub(r"\D", "", p) if len(re.sub(r"\D", "", p)) == 10 else re.sub(r"[^\d+]", "", p),
    link_icon=_link_icon,
    rich=_rich,
    cert_when=_cert_when,
)


class RenderError(RuntimeError):
    pass


def untailored(master: MasterResume) -> TailoredContent:
    """The master resume as-is, for previewing the base layout."""

    def sec(source_id, bullets):
        return TailoredSection(
            source_id=source_id,
            bullets=[TailoredBullet(source_ids=[b.id], text=b.text) for b in bullets if b.in_base],
        )

    return TailoredContent(
        headline=master.headline or "",
        summary=master.summary or "",
        experience=[sec(r.id, r.bullets) for r in master.experience],
        projects=[sec(p.id, p.bullets) for p in master.projects],
        skills=master.skills,
    )


def to_html(
    master: MasterResume,
    content: TailoredContent,
    *,
    show_expired_certs: bool = False,
) -> str:
    roles = {r.id: r for r in master.experience}
    projects = {p.id: p for p in master.projects}
    certs = [
        c for c in master.certifications if show_expired_certs or c.status != CertStatus.expired
    ]
    return _env.get_template("resume.html.j2").render(
        contact=master.contact,
        headline=content.headline,
        summary=content.summary,
        experience=[
            {"role": roles[s.source_id], "bullets": s.bullets} for s in content.experience if s.source_id in roles
        ],
        projects=[
            {"project": projects[s.source_id], "bullets": s.bullets}
            for s in content.projects
            if s.source_id in projects
        ],
        education=master.education,
        skills=content.skills,
        certifications=certs,
        layout=master.layout,
    )


async def to_pdf(html: str, settings: Settings) -> bytes:
    if settings.pdf_engine == "weasyprint":
        try:
            from weasyprint import HTML
        except ImportError as e:  # pragma: no cover
            raise RenderError("PDF_ENGINE=weasyprint but weasyprint isn't installed") from e
        return HTML(string=html).write_pdf()

    # Gotenberg's Chromium route: the file must be called index.html.
    url = settings.gotenberg_url.rstrip("/") + "/forms/chromium/convert/html"
    data = {
        "preferCssPageSize": "true",
        "printBackground": "true",
        "skipNetworkIdleEvent": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(url, files={"files": ("index.html", html.encode(), "text/html")}, data=data)
    except httpx.HTTPError as e:
        raise RenderError(f"Gotenberg unreachable at {settings.gotenberg_url}: {e}") from e
    if resp.status_code != 200:
        raise RenderError(f"Gotenberg returned {resp.status_code}: {resp.text[:300]}")
    return resp.content


def page_count(pdf: bytes) -> int:
    from io import BytesIO

    from pypdf import PdfReader

    return len(PdfReader(BytesIO(pdf)).pages)


def _trim_once(content: TailoredContent) -> str | None:
    """Remove the least important line. Returns a description, or None if nothing sensible is left to cut."""
    exp, proj = content.experience, content.projects
    # 1. Keep at most two projects.
    if len(proj) > 2:
        return f"project '{proj.pop().source_id}'"
    # 2. Oldest role down to one bullet, then the middle roles down to two.
    for floor in (1, 2):
        for sec in reversed(exp[1:]):
            if len(sec.bullets) > floor:
                sec.bullets.pop()
                return f"a bullet from '{sec.source_id}'"
    # 3. Projects down to one bullet each, then down to one project.
    for sec in reversed(proj):
        if len(sec.bullets) > 1:
            sec.bullets.pop()
            return f"a bullet from '{sec.source_id}'"
    if len(proj) > 1:
        return f"project '{proj.pop().source_id}'"
    # 4. Most recent role down to three bullets.
    if exp and len(exp[0].bullets) > 3:
        exp[0].bullets.pop()
        return f"a bullet from '{exp[0].source_id}'"
    return None


async def fit_one_page(
    master: MasterResume,
    content: TailoredContent,
    settings: Settings,
    *,
    show_expired_certs: bool = False,
    max_trims: int = 8,
) -> tuple[TailoredContent, str, list[str]]:
    """Render; while the PDF runs past one page, trim the least important line. Returns (content, html, trimmed)."""
    content = content.model_copy(deep=True)
    trimmed: list[str] = []
    html = to_html(master, content, show_expired_certs=show_expired_certs)
    for _ in range(max_trims):
        if page_count(await to_pdf(html, settings)) <= master.layout.max_pages:
            break
        what = _trim_once(content)
        if what is None:
            break
        trimmed.append(what)
        html = to_html(master, content, show_expired_certs=show_expired_certs)
    return content, html, trimmed
