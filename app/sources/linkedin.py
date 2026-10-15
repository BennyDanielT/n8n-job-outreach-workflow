"""LinkedIn jobs and people via Selenium, signed in with your session cookie.

How sign-in works, in order of preference:
1. LINKEDIN_LI_AT (+ optional LINKEDIN_JSESSIONID): the cookie from a browser where you're logged in.
   No password typing, so far fewer security checkpoints.
2. LINKEDIN_EMAIL + LINKEDIN_PASSWORD: the old form login, as a fallback.

Caveats you accepted: this automates your own account, which LinkedIn's terms don't allow, and
their markup changes often. Parsing lives in pure functions over HTML (`parse_*`) so a selector fix
is one function and its test. Keep volumes low: a few searches a day, with pauses.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from app.config import Settings

log = logging.getLogger(__name__)

# One browser at a time: parallel sessions on one account is the fastest way to get flagged.
_browser_lock = threading.Lock()

JOB_ID_RE = re.compile(r"(?:/jobs/view/(?:[^/\"?]*-)?|currentJobId=|jobPosting:|data-job-id=\"|data-occludable-job-id=\")(\d{6,})")


class LinkedInError(RuntimeError):
    pass


@dataclass
class LinkedInJob:
    job_id: str
    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description: str | None = None
    posted: str | None = None
    workplace: str | None = None
    apply_url: str | None = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"


def extract_job_id(url_or_id: str) -> str | None:
    if url_or_id.isdigit():
        return url_or_id
    m = re.search(r"(?:/jobs/view/(?:[^/?]*-)?|currentJobId=)(\d{6,})", url_or_id)
    return m.group(1) if m else None


def is_linkedin(url: str) -> bool:
    return bool(re.match(r"^https?://([a-z0-9-]+\.)?linkedin\.com/", url, re.I))


# --------------------------------------------------------------------------- search URL
TIME_FILTERS = {24: "r86400", 72: "r259200", 168: "r604800", 720: "r2592000"}


def search_url(keywords: str, location: str | None = None, geo_id: str | None = None,
               posted_within_hours: int | None = 168, remote_only: bool = False, start: int = 0) -> str:
    params: dict[str, str] = {"keywords": keywords}
    if geo_id:
        params["geoId"] = geo_id
    elif location:
        params["location"] = location
    if posted_within_hours:
        # Snap to LinkedIn's preset windows.
        hours = min(TIME_FILTERS, key=lambda h: abs(h - posted_within_hours))
        params["f_TPR"] = TIME_FILTERS[hours]
    if remote_only:
        params["f_WT"] = "2"
    if start:
        params["start"] = str(start)
    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


# --------------------------------------------------------------------------- parsing (pure, tested)
def _text(node) -> str | None:
    if node is None:
        return None
    t = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return t or None


def _dedupe_title(t: str | None) -> str | None:
    # LinkedIn often renders the title twice (visible + screen-reader copy): "AI Engineer AI Engineer".
    if not t:
        return t
    half = len(t) // 2
    if len(t) % 2 == 1 and t[:half] == t[half + 1:]:
        return t[:half]
    return t


def parse_search_results(html: str) -> list[LinkedInJob]:
    """Job cards from a logged-in /jobs/search page. Falls back to any job ids in the page."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, LinkedInJob] = {}
    for card in soup.select("[data-occludable-job-id], [data-job-id]"):
        jid = card.get("data-occludable-job-id") or card.get("data-job-id")
        if not jid or not jid.isdigit() or jid in jobs:
            continue
        title = _dedupe_title(_text(card.select_one(
            "a.job-card-list__title, a.job-card-list__title--link, a.job-card-container__link, .job-card-list__title strong")))
        company = _text(card.select_one(
            ".artdeco-entity-lockup__subtitle, .job-card-container__primary-description, .job-card-container__company-name"))
        location = _text(card.select_one(
            ".job-card-container__metadata-wrapper li, .job-card-container__metadata-item, .artdeco-entity-lockup__caption"))
        jobs[jid] = LinkedInJob(job_id=jid, url=job_url(jid), title=title, company=company, location=location)
    # Markup drifts: keep any other job ids on the page, even without card details.
    for jid in dict.fromkeys(JOB_ID_RE.findall(html)):
        jobs.setdefault(jid, LinkedInJob(job_id=jid, url=job_url(jid)))
    return list(jobs.values())


def parse_job_page(html: str, url: str) -> LinkedInJob:
    """A single job view, logged in or the public (logged-out) page."""
    soup = BeautifulSoup(html, "html.parser")
    jid = extract_job_id(url) or ""
    title = _text(soup.select_one(
        ".job-details-jobs-unified-top-card__job-title h1, h1.t-24, h1.top-card-layout__title, h1"))
    company = _text(soup.select_one(
        ".job-details-jobs-unified-top-card__company-name a, .job-details-jobs-unified-top-card__company-name, "
        ".jobs-unified-top-card__company-name, a.topcard__org-name-link, .topcard__flavor"))
    location = _text(soup.select_one(
        ".job-details-jobs-unified-top-card__primary-description-container span, "
        ".job-details-jobs-unified-top-card__tertiary-description-container span, "
        ".jobs-unified-top-card__bullet, .topcard__flavor--bullet"))
    desc = soup.select_one(
        ".jobs-description__content, .jobs-description-content__text, #job-details, .show-more-less-html__markup, "
        ".description__text")
    description = desc.get_text("\n", strip=True) if desc else None
    posted = None
    m = re.search(r"(Reposted\s+)?\d+\s+(?:minute|hour|day|week|month)s?\s+ago", soup.get_text(" "))
    if m:
        posted = m.group(0)
    workplace = None
    for chip in soup.select(".job-details-fit-level-preferences button, .job-details-preferences-and-skills__pill"):
        t = _text(chip)
        if t and any(w in t for w in ("Remote", "Hybrid", "On-site")):
            workplace = t
            break
    apply = soup.select_one("a.jobs-apply-button[href], a.apply-button[href]")
    return LinkedInJob(
        job_id=jid, url=job_url(jid) if jid else url, title=_dedupe_title(title), company=company,
        location=location, description=description, posted=posted, workplace=workplace,
        apply_url=apply["href"] if apply else None,
    )


def parse_people(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for card in soup.select("li.org-people-profile-card__profile-card-spacing"):
        a = card.select_one("div.artdeco-entity-lockup__title a")
        person = {
            "name": _text(a),
            "profile_url": a["href"].split("?")[0] if a and a.has_attr("href") else None,
            "title": _text(card.select_one("div.artdeco-entity-lockup__subtitle")),
            "mutuals": _text(card.select_one("span.lt-line-clamp--multi-line")),
        }
        if person["name"] and person not in out:
            out.append(person)
    return out


# --------------------------------------------------------------------------- browser
class LinkedInBrowser:
    """A short-lived signed-in Chrome. Use as a context manager; one at a time."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.driver = None

    def __enter__(self) -> "LinkedInBrowser":
        if not _browser_lock.acquire(timeout=300):
            raise LinkedInError("Another LinkedIn task is still running")
        try:
            self.driver = self._make_driver()
            self._sign_in()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc) -> None:
        try:
            if self.driver is not None:
                self.driver.quit()
        finally:
            self.driver = None
            _browser_lock.release()

    def _make_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        o = Options()
        if self.s.linkedin_headless:
            o.add_argument("--headless=new")
        for arg in ("--window-size=1400,1000", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
                    "--lang=en-US", "--disable-blink-features=AutomationControlled"):
            o.add_argument(arg)
        if self.s.chrome_profile_dir:
            o.add_argument(f"--user-data-dir={self.s.chrome_profile_dir}")
        if self.s.chrome_binary:
            o.binary_location = self.s.chrome_binary
        return webdriver.Chrome(options=o)

    def _pause(self, lo: float = 1.5, hi: float = 3.5) -> None:
        time.sleep(random.uniform(lo, hi))

    def _signed_in(self) -> bool:
        url = self.driver.current_url
        return "linkedin.com" in url and not any(x in url for x in ("/login", "/authwall", "/checkpoint", "/uas/"))

    def _sign_in(self) -> None:
        d = self.driver
        if self.s.linkedin_li_at:
            d.get("https://www.linkedin.com/")
            d.add_cookie({"name": "li_at", "value": self.s.linkedin_li_at.strip('"'), "domain": ".linkedin.com",
                          "path": "/", "secure": True, "httpOnly": True})
            if self.s.linkedin_jsessionid:
                d.add_cookie({"name": "JSESSIONID", "value": self.s.linkedin_jsessionid.strip('"'),
                              "domain": ".linkedin.com", "path": "/", "secure": True})
            d.get("https://www.linkedin.com/feed/")
            self._pause()
            if self._signed_in():
                log.info("linkedin: signed in with li_at cookie")
                return
            log.warning("linkedin: li_at cookie rejected (expired?), trying password login")

        if self.s.linkedin_email and self.s.linkedin_password:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys

            d.get("https://www.linkedin.com/login")
            self._pause()
            d.find_element(By.ID, "username").send_keys(self.s.linkedin_email)
            pw = d.find_element(By.ID, "password")
            pw.send_keys(self.s.linkedin_password)
            pw.send_keys(Keys.RETURN)
            self._pause(3, 5)
            if self._signed_in():
                log.info("linkedin: signed in with password")
                return
            raise LinkedInError(
                "LinkedIn asked for a security check. Log in once in a normal browser, then copy a fresh li_at cookie."
            )
        raise LinkedInError("Set LINKEDIN_LI_AT (recommended) or LINKEDIN_EMAIL and LINKEDIN_PASSWORD")

    def _scroll_results(self, rounds: int = 6) -> None:
        # The results pane lazy-loads cards as it scrolls.
        for _ in range(rounds):
            self.driver.execute_script(
                "const p=document.querySelector('.jobs-search-results-list, .scaffold-layout__list > div');"
                "if(p){p.scrollBy(0,p.clientHeight)}else{window.scrollBy(0,window.innerHeight)}")
            time.sleep(random.uniform(0.6, 1.2))

    def search(self, keywords: str, *, location: str | None = None, geo_id: str | None = None,
               posted_within_hours: int | None = 168, remote_only: bool = False, limit: int = 25) -> list[LinkedInJob]:
        found: dict[str, LinkedInJob] = {}
        start = 0
        while len(found) < limit and start < 200:
            self.driver.get(search_url(keywords, location, geo_id, posted_within_hours, remote_only, start))
            self._pause()
            if not self._signed_in():
                raise LinkedInError("Signed out while searching; refresh your li_at cookie")
            self._scroll_results()
            page = parse_search_results(self.driver.page_source)
            new = [j for j in page if j.job_id not in found]
            if not new:
                break
            for j in new:
                found[j.job_id] = j
            start += 25
            self._pause(2, 4)
        return list(found.values())[:limit]

    def job(self, url_or_id: str) -> LinkedInJob:
        jid = extract_job_id(url_or_id)
        if not jid:
            raise LinkedInError(f"Not a LinkedIn job URL: {url_or_id}")
        self.driver.get(job_url(jid))
        self._pause(2.5, 4.5)
        # Expand "See more" so the whole description is in the DOM.
        try:
            from selenium.webdriver.common.by import By

            for b in self.driver.find_elements(By.CSS_SELECTOR, "button.jobs-description__footer-button, "
                                                                "button[aria-label*='see more description' i]"):
                self.driver.execute_script("arguments[0].click();", b)
                time.sleep(0.5)
        except Exception:  # noqa: BLE001 - optional nicety
            pass
        job = parse_job_page(self.driver.page_source, job_url(jid))
        if not job.description:
            raise LinkedInError("Couldn't find the job description on the page (markup may have changed)")
        return job

    def people(self, company_slug: str, query_params: str = "", min_results: int = 20,
               max_clicks: int = 10) -> list[dict]:
        from selenium.webdriver.common.by import By

        self.driver.get(f"https://www.linkedin.com/company/{company_slug}/people/{query_params}")
        self._pause(2.5, 4)
        results: list[dict] = []
        for _ in range(max_clicks):
            for p in parse_people(self.driver.page_source):
                if p not in results:
                    results.append(p)
            if len(results) >= min_results:
                break
            buttons = self.driver.find_elements(By.XPATH, "//button[contains(., 'Show more results')]")
            if not buttons:
                break
            self.driver.execute_script("arguments[0].click();", buttons[0])
            self._pause()
        return results
