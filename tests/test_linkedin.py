from urllib.parse import parse_qs, urlparse

import pytest

from app.config import Settings
from app.sources import linkedin as li

SEARCH_HTML = """
<ul>
  <li data-occludable-job-id="4012345678">
    <div class="job-card-container">
      <a class="job-card-container__link job-card-list__title--link" href="/jobs/view/4012345678/">
        <strong>AI Engineer AI Engineer</strong></a>
      <div class="artdeco-entity-lockup__subtitle"><span>Shopify</span></div>
      <ul class="job-card-container__metadata-wrapper"><li>Canada (Remote)</li></ul>
    </div>
  </li>
  <li data-occludable-job-id="4012345679">
    <a class="job-card-list__title" href="/jobs/view/4012345679/">LLM Engineer</a>
    <div class="artdeco-entity-lockup__subtitle">Cohere</div>
    <ul class="job-card-container__metadata-wrapper"><li>Toronto, ON (Hybrid)</li></ul>
  </li>
  <li data-occludable-job-id="4012345678"></li>
</ul>"""

JOB_HTML = """
<div class="job-details-jobs-unified-top-card__job-title"><h1>Applied AI Engineer</h1></div>
<div class="job-details-jobs-unified-top-card__company-name"><a href="#">Wealthsimple</a></div>
<div class="job-details-jobs-unified-top-card__primary-description-container"><span>Canada · 3 days ago</span></div>
<span>3 days ago</span>
<div class="job-details-fit-level-preferences"><button>Remote</button><button>Full-time</button></div>
<div class="jobs-description__content"><p>Build RAG systems with Python.</p><ul><li>LangGraph</li></ul></div>
"""


def test_search_cards_parsed_and_deduped():
    jobs = li.parse_search_results(SEARCH_HTML)
    assert [j.job_id for j in jobs] == ["4012345678", "4012345679"]
    assert jobs[0].title == "AI Engineer", "doubled screen-reader title is collapsed"
    assert jobs[0].company == "Shopify" and jobs[0].location == "Canada (Remote)"
    assert jobs[1].url == "https://www.linkedin.com/jobs/view/4012345679/"


def test_search_falls_back_to_ids_when_markup_changes():
    html = '<a href="/jobs/view/4099999999/?refId=x">x</a> <div data-job-id="4088888888"></div>'
    assert {j.job_id for j in li.parse_search_results(html)} == {"4099999999", "4088888888"}


def test_job_page_parsed():
    j = li.parse_job_page(JOB_HTML, "https://www.linkedin.com/jobs/view/4012345678/?trk=abc")
    assert (j.job_id, j.title, j.company) == ("4012345678", "Applied AI Engineer", "Wealthsimple")
    assert "Build RAG systems" in j.description and "LangGraph" in j.description
    assert j.workplace == "Remote" and j.posted == "3 days ago"


@pytest.mark.parametrize("url,jid", [
    ("https://www.linkedin.com/jobs/view/4012345678/", "4012345678"),
    ("https://www.linkedin.com/jobs/view/ai-engineer-at-shopify-4012345678?trk=x", "4012345678"),
    ("https://www.linkedin.com/jobs/search/?currentJobId=4012345678&keywords=ai", "4012345678"),
    ("4012345678", "4012345678"),
    ("https://www.linkedin.com/company/shopify/", None),
])
def test_extract_job_id(url, jid):
    assert li.extract_job_id(url) == jid


def test_search_url_filters():
    q = parse_qs(urlparse(li.search_url("AI Engineer", geo_id="101174742", posted_within_hours=24,
                                        remote_only=True)).query)
    assert q == {"keywords": ["AI Engineer"], "geoId": ["101174742"], "f_TPR": ["r86400"], "f_WT": ["2"]}


class FakeDriver:
    def __init__(self, accept_cookie=True):
        self.current_url = "about:blank"
        self.cookies, self.accept = [], accept_cookie

    def get(self, url):
        signed_in = self.accept and any(c["name"] == "li_at" for c in self.cookies)
        self.current_url = url if (signed_in or "login" in url or url.rstrip("/").endswith("linkedin.com")) \
            else "https://www.linkedin.com/authwall"

    def add_cookie(self, c):
        self.cookies.append(c)

    def quit(self):
        pass


def _browser(monkeypatch, driver, **settings):
    monkeypatch.setattr(li.LinkedInBrowser, "_make_driver", lambda self: driver)
    monkeypatch.setattr(li.LinkedInBrowser, "_pause", lambda self, *a: None)
    return li.LinkedInBrowser(Settings(linkedin_li_at="abc", **settings))


def test_cookie_sign_in(monkeypatch):
    d = FakeDriver()
    with _browser(monkeypatch, d):
        assert d.cookies[0]["name"] == "li_at" and d.cookies[0]["domain"] == ".linkedin.com"
        assert d.current_url.endswith("/feed/")


def test_expired_cookie_without_password_explains(monkeypatch):
    with pytest.raises(li.LinkedInError, match="LINKEDIN_LI_AT"):
        with _browser(monkeypatch, FakeDriver(accept_cookie=False)):
            pass
    # The lock was released despite the failure.
    assert li._browser_lock.acquire(timeout=0.1)
    li._browser_lock.release()
