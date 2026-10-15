from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import tracker
from app.demo import SAMPLE_JOB
from app.deps import tailor_limit
from app.main import app
from app.sources import linkedin as li

client = TestClient(app)


def add(text=SAMPLE_JOB.text, **kw):
    r = client.post("/api/v1/jobs", json={"text": text, "title": "AI Engineer", "company": kw.pop("company", "Acme"), **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list():
    job = add(company="ListCo")
    assert job["status"] == "saved" and job["has_description"]
    assert [e["kind"] for e in job["events"]] == ["created", "status"]
    rows = client.get("/api/v1/jobs", params={"q": "ListCo"}).json()
    assert len(rows) == 1 and rows[0]["id"] == job["id"]


def test_needs_url_or_text():
    assert client.post("/api/v1/jobs", json={"title": "x"}).status_code == 422


def test_status_flow_sets_dates_and_history():
    job = add(company="FlowCo")
    r = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "applied", "notes": "Referred by Priya"}).json()
    assert r["applied_on"] == date.today().isoformat()
    assert r["follow_up_on"] == (date.today() + timedelta(days=7)).isoformat()
    r = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "screen"}).json()
    r = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "rejected"}).json()
    moves = [(e["from"], e["to"]) for e in r["events"] if e["kind"] == "status"]
    assert moves[-3:] == [("saved", "applied"), ("applied", "screen"), ("screen", "rejected")]


def test_stats_count_responses_even_after_rejection():
    s = client.get("/api/v1/stats").json()
    assert s["applied_total"] >= 1
    assert s["responded"] >= 1, "FlowCo reached a screen before being rejected"
    assert 0 < s["response_rate"] <= 1


def test_follow_up_due_filter():
    job = add(company="DueCo")
    client.patch(f"/api/v1/jobs/{job['id']}",
                 json={"status": "applied", "follow_up_on": (date.today() - timedelta(days=1)).isoformat()})
    due = client.get("/api/v1/jobs", params={"follow_up_due": True}).json()
    assert any(j["company"] == "DueCo" for j in due)


def test_tailor_saved_job_then_edit_and_download():
    tailor_limit.hits.clear()
    job = add(company="TailorCo", status="new")
    r = client.post(f"/api/v1/jobs/{job['id']}/tailor")
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert detail["has_resume"] and detail["fit_score"] == r.json()["fit"]["score"]
    assert detail["status"] == "saved", "tailoring a new job moves it to saved"
    assert detail["tailor_result"]["faithfulness"]["passed"]

    html = client.get(f"/api/v1/jobs/{job['id']}/resume").text
    edited = html.replace("Trihedral Engineering Limited", "Trihedral Engineering Ltd.")
    assert client.put(f"/api/v1/jobs/{job['id']}/resume", json={"html": edited}).status_code == 204
    assert "Trihedral Engineering Ltd." in client.get(f"/api/v1/jobs/{job['id']}/resume").text
    pdf = client.get(f"/api/v1/jobs/{job['id']}/resume.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert 'filename="Benny_Daniel_Tharigopala_TailorCo.pdf"' in pdf.headers["content-disposition"]


def test_delete():
    job = add(company="GoneCo")
    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404


class FakeBrowser:
    def __init__(self, settings):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def search(self, keywords, **kw):
        return [li.LinkedInJob(job_id="4100000001", url=li.job_url("4100000001"), title="AI Engineer",
                               company="Shopify", location="Canada (Remote)"),
                li.LinkedInJob(job_id="4100000002", url=li.job_url("4100000002"), title="ML Engineer",
                               company="Cohere", location="Toronto")]

    def job(self, url_or_id):
        jid = li.extract_job_id(url_or_id)
        return li.LinkedInJob(job_id=jid, url=li.job_url(jid), title="AI Engineer", company="Shopify",
                              location="Canada", description="Build agents with LangGraph. " * 10)


@pytest.fixture
def fake_linkedin(monkeypatch):
    monkeypatch.setattr(li, "LinkedInBrowser", FakeBrowser)


def test_linkedin_search_adds_and_dedupes(fake_linkedin):
    body = {"keywords": "AI Engineer", "location": "Canada"}
    first = client.post("/api/v1/jobs/search/linkedin", json=body).json()
    assert (first["found"], first["added"], first["already_tracked"]) == (2, 2, 0)
    assert all(j["status"] == "new" and not j["has_description"] for j in first["jobs"])
    again = client.post("/api/v1/jobs/search/linkedin", json=body).json()
    assert (again["added"], again["already_tracked"]) == (0, 2)


def test_linkedin_url_import_and_refresh(fake_linkedin):
    r = client.post("/api/v1/jobs", json={"url": "https://www.linkedin.com/jobs/view/4100000009/?trk=x"})
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["source"] == "linkedin" and job["external_id"] == "4100000009" and "LangGraph" in job["description"]
    dup = client.post("/api/v1/jobs", json={"url": "https://www.linkedin.com/jobs/view/4100000009/"})
    assert dup.status_code == 409
    searched = client.get("/api/v1/jobs", params={"q": "Cohere"}).json()[0]
    refreshed = client.post(f"/api/v1/jobs/{searched['id']}/refresh").json()
    assert refreshed["has_description"]
