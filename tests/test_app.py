"""Route tests with scrape_jobs replaced by a fake. No network."""

import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main, runner


@pytest.fixture
def client(monkeypatch):
    runner._cache.clear()

    def fake(**kwargs):
        df = pd.DataFrame([
            {"site": "indeed", "job_url": "javascript:alert(1)", "title": "<script>x</script>",
             "company": "Evil", "description": None},
            {"site": "indeed", "job_url": "https://ok.example/1", "title": '=HYPERLINK("x")',
             "company": "Acme", "min_amount": 100000.0, "currency": "USD", "interval": "yearly",
             "description": "Line one\nLine two"},
        ])
        df.attrs = {"errors": {"linkedin": "blocked by LinkedIn"},
                    "warnings": {"indeed": ["job_type ignored"]}}
        return df

    monkeypatch.setattr(runner, "scrape_jobs", fake)
    yield TestClient(main.app)
    runner._cache.clear()


def test_form_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'name="search_term"' in r.text and "More options" in r.text
    assert "linkedin_fetch_description" not in r.text and "proxies" not in r.text


def test_validation_400(client):
    r = client.get("/?search_term=&results_wanted=abc")
    assert r.status_code == 400
    assert "Enter a search term." in r.text and "abc" in r.text


def test_search_render_and_export(client):
    r = client.get("/?search_term=dev&site_name=indeed&site_name=linkedin")
    assert r.status_code == 200
    assert "2 jobs from indeed, linkedin" in r.text
    assert "javascript:" not in r.text
    assert "<script>x</script>" not in r.text and "&lt;script&gt;" in r.text
    assert 'href="https://ok.example/1"' in r.text
    assert "USD 100,000+ / yearly" in r.text
    assert "linkedin: blocked by LinkedIn Wait about a minute" in r.text
    assert "indeed: job_type ignored" in r.text
    assert "No description from this board" in r.text

    again = client.get("/?search_term=dev&site_name=indeed&site_name=linkedin")
    assert "Cached result from" in again.text

    key = re.search(r"/export\.csv\?key=([0-9a-f]{64})", again.text).group(1)
    csv = client.get(f"/export.csv?key={key}")
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.headers["content-disposition"].startswith('attachment; filename="jobs-')
    assert "'=HYPERLINK" in csv.content.decode("utf-8-sig")


def test_export_expired(client):
    r = client.get("/export.csv?key=nope")
    assert r.status_code == 404 and "Results expired" in r.text
