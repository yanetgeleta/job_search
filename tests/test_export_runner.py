import io

import pandas as pd
import pytest

from app import runner
from app.constants import CACHE_MAX, CACHE_TTL
from app.export import neutralize, to_csv_bytes
from app.main import SUPPORTED

KW = {"search_term": "a", "site_name": ["indeed", "linkedin"], "verbose": 1}


@pytest.fixture(autouse=True)
def clear_cache():
    runner._cache.clear()
    yield
    runner._cache.clear()


def fake_scraper(calls=None):
    def scrape(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        df = pd.DataFrame([{"site": "indeed", "job_url": "https://a", "title": "x"}])
        df.attrs = {"errors": {"linkedin": "429 Too Many Requests"}, "warnings": {}}
        return df
    return scrape


def test_neutralize():
    for v in ["=HYPERLINK(\"x\")", "+1", "-2", "@SUM(A1)", "\tx", "\rx"]:
        assert neutralize(v) == "'" + v
    for v in ["", "ok", "a=b", 5, None, 1.5]:
        assert neutralize(v) == v


def test_csv_round_trip():
    df = pd.DataFrame([{"title": '=HYPERLINK("http://evil","x")', "company": "Acme, Inc.", "n": 3, "e": None}])
    raw = to_csv_bytes(df)
    assert raw.startswith(b"\xef\xbb\xbf")
    back = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    assert back.loc[0, "title"] == "'=HYPERLINK(\"http://evil\",\"x\")"
    assert back.loc[0, "company"] == "Acme, Inc." and back.loc[0, "n"] == 3
    assert list(back.columns) == ["title", "company", "n", "e"]


def test_partial_failure_keeps_rows_and_caches():
    calls = []
    out = runner.run(KW, refresh=False, supported=SUPPORTED, scraper=fake_scraper(calls))
    assert len(out.records) == 1 and out.errors == {"linkedin": "429 Too Many Requests"}
    assert not out.from_cache
    again = runner.run(KW, refresh=False, supported=SUPPORTED, scraper=fake_scraper(calls))
    assert again.from_cache and len(calls) == 1
    runner.run(KW, refresh=True, supported=SUPPORTED, scraper=fake_scraper(calls))
    assert len(calls) == 2


def test_cache_ttl_expiry():
    out = runner.run(KW, refresh=False, supported=SUPPORTED, scraper=fake_scraper())
    assert runner.cache_get(out.key, now=out.created + CACHE_TTL - 1) is not None
    assert runner.cache_get(out.key, now=out.created + CACHE_TTL + 1) is None
    assert out.key not in runner._cache


def test_cache_eviction():
    keys = [runner.run({**KW, "search_term": str(i)}, False, SUPPORTED, fake_scraper()).key for i in range(CACHE_MAX + 2)]
    assert len(runner._cache) == CACHE_MAX
    assert keys[0] not in runner._cache and keys[1] not in runner._cache
    assert keys[-1] in runner._cache


def test_busy_when_locked():
    assert runner._lock.acquire(blocking=False)
    try:
        with pytest.raises(runner.Busy):
            runner.run(KW, False, SUPPORTED, fake_scraper())
    finally:
        runner._lock.release()


def test_scraper_exception_not_cached_and_releases_lock():
    def boom(**_):
        raise ValueError("Invalid location")
    with pytest.raises(ValueError):
        runner.run(KW, False, SUPPORTED, boom)
    assert not runner._cache and not runner._lock.locked()


def test_env_extras_not_in_key(monkeypatch):
    monkeypatch.setenv("JOBSPY_PROXIES", "user:secret@host:8080, other:1")
    monkeypatch.setenv("JOBSPY_CA_CERT", "/tmp/ca.pem")
    calls = []
    out = runner.run(KW, False, SUPPORTED, fake_scraper(calls))
    assert calls[0]["proxies"] == ["user:secret@host:8080", "other:1"]
    assert calls[0]["ca_cert"] == "/tmp/ca.pem"
    assert out.key == runner.make_key(KW)
    assert "secret" not in repr(out)
