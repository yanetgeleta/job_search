import math
from datetime import date

import pandas as pd

from app.results import diagnostics, format_salary, postprocess, safe_url


def frame(rows):
    return pd.DataFrame(rows)


def test_safe_url():
    assert safe_url("https://example.com/job/1") == "https://example.com/job/1"
    assert safe_url("HTTP://example.com") == "HTTP://example.com"
    for bad in ["javascript:alert(1)", " javascript:alert(1)", "data:text/html,<b>x</b>",
                "https://", "//example.com", "/relative", "", None, float("nan"), 42]:
        assert safe_url(bad) is None, bad


def test_dedupe_sort_and_nan():
    df = frame([
        {"site": "indeed", "job_url": "https://a", "title": "old", "date_posted": date(2025, 1, 1), "min_amount": math.nan},
        {"site": "indeed", "job_url": "https://a", "title": "dup", "date_posted": date(2025, 1, 1), "min_amount": 1.0},
        {"site": "linkedin", "job_url": "https://b", "title": "none", "date_posted": None, "min_amount": None},
        {"site": "linkedin", "job_url": "https://c", "title": "new", "date_posted": date(2025, 3, 1), "min_amount": None},
    ])
    out = postprocess(df, {}, ["indeed", "linkedin"], "k", 1.0, 0.0)
    assert [r["title"] for r in out.records] == ["new", "old", "none"]
    assert out.records[0]["date_posted"] == "2025-03-01"
    assert out.records[1]["min_amount"] is None
    assert out.records[2]["date_posted"] is None
    assert out.counts == {"indeed": 1, "linkedin": 2}
    assert len(out.df) == 3


def test_absent_columns_tolerated():
    out = postprocess(frame([{"title": "x"}]), {}, ["indeed"], "k", 0.0, 0.0)
    r = out.records[0]
    assert r["href"] is None and r["salary_text"] is None and r["meta"] == []
    assert out.counts == {}


def test_empty_and_none():
    for df in (None, pd.DataFrame()):
        out = postprocess(df, {"errors": {"linkedin": "429"}}, ["linkedin"], "k", 0.0, 0.0)
        assert out.records == [] and out.errors == {"linkedin": "429"}


def test_javascript_url_renders_no_link():
    df = frame([{"site": "indeed", "job_url": "javascript:alert(1)", "title": "x",
                 "job_url_direct": "data:text/html,x", "company_url": "https://ok.example"}])
    r = postprocess(df, {}, ["indeed"], "k", 0.0, 0.0).records[0]
    assert r["href"] is None and r["direct_href"] is None
    assert r["company_href"] == "https://ok.example"


def test_format_salary():
    assert format_salary({"min_amount": 110000.0, "max_amount": 135000.0, "currency": "USD", "interval": "yearly"}) == "USD 110,000–135,000 / yearly"
    assert format_salary({"min_amount": 110000.0, "currency": "USD", "interval": "yearly"}) == "USD 110,000+ / yearly"
    assert format_salary({"max_amount": 50.5, "interval": "hourly"}) == "up to 50.50 / hourly"
    assert format_salary({"min_amount": 20, "max_amount": 20}) == "20"
    assert format_salary({"min_amount": None, "max_amount": math.nan}) is None
    assert format_salary({}) is None


def test_diagnostics():
    df = frame([{"site": "indeed", "job_url": "https://a", "title": "x"}])
    attrs = {
        "errors": {"linkedin": "HTTP 429 Too Many Requests", "glassdoor": "bad location"},
        "warnings": {"indeed": ["job_type isn't supported with hours_old, ignoring it"]},
    }
    out = postprocess(df, attrs, ["indeed", "linkedin", "glassdoor", "bayt"], "k", 0.0, 0.0)
    lines = diagnostics(out)
    assert lines[0].startswith("linkedin: HTTP 429") and "Wait about a minute" in lines[0]
    assert lines[1] == "glassdoor: bad location"
    assert lines[2] == "indeed: job_type isn't supported with hours_old, ignoring it"
    assert lines[3] == "bayt: returned no jobs"
    assert len(lines) == 4
