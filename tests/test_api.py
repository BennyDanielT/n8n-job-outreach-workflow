import os

os.environ["PDF_ENGINE"] = "weasyprint"

import pytest
from fastapi.testclient import TestClient

from app import jobfetch
from app.deps import tailor_limit
from app.main import app

client = TestClient(app)


def test_health_and_request_id():
    r = client.get("/health", headers={"x-request-id": "abc123"})
    assert r.status_code == 200 and r.headers["x-request-id"] == "abc123"


def test_index_served():
    assert "Job Copilot" in client.get("/").text


def test_tailor_end_to_end_then_pdf():
    job = client.get("/api/v1/sample-job").json()
    r = client.post("/api/v1/tailor", json={"job": job})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["faithfulness"]["passed"]
    assert "Benny Daniel Tharigopala" in body["html"]
    pdf = client.post("/api/v1/render/pdf", json={"html": body["html"], "filename": "x/../evil name"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert "/" not in pdf.headers["content-disposition"].split("filename=")[1]


def test_short_job_text_rejected():
    assert client.post("/api/v1/tailor", json={"job": {"text": "too short"}}).status_code == 422


def test_rate_limit():
    tailor_limit.hits.clear()
    job = client.get("/api/v1/sample-job").json()
    codes = [client.post("/api/v1/tailor", json={"job": job}, headers={"x-forwarded-for": "9.9.9.9"}).status_code
             for _ in range(tailor_limit.limit + 1)]
    assert codes[-1] == 429 and codes[0] == 200
    tailor_limit.hits.clear()


@pytest.mark.parametrize("url,msg", [
    ("https://www.linkedin.com/jobs/view/123", "LinkedIn"),
    ("http://example.com/job", "https"),
    ("https://localhost/job", "public internet"),
    ("https://169.254.169.254/latest/meta-data", "public internet"),
])
def test_fetch_guards(url, msg):
    with pytest.raises(jobfetch.FetchError, match=msg):
        jobfetch._check_url(url)


def test_ats_urls_map_to_public_apis():
    assert jobfetch._ats_api("https://boards.greenhouse.io/acme/jobs/42")[0] == \
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs/42"
    assert jobfetch._ats_api("https://jobs.lever.co/acme/abc-123")[0] == "https://api.lever.co/v0/postings/acme/abc-123"
    assert jobfetch._ats_api("https://example.com/careers/1") is None


def test_json_ld_extraction():
    html = """<html><head><script type="application/ld+json">
    {"@type":"JobPosting","title":"AI Engineer","hiringOrganization":{"name":"Acme"},
     "jobLocation":{"address":{"addressLocality":"Toronto","addressCountry":"CA"}},
     "description":"<p>Build LLM apps with Python and Azure OpenAI. We want evaluation experience and FastAPI.</p>"}
    </script></head><body>x</body></html>"""
    job = jobfetch._from_json_ld(html)
    assert job.title == "AI Engineer" and job.company == "Acme" and job.location == "Toronto, CA"
    assert "Azure OpenAI" in job.text and "<p>" not in job.text
