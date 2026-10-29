"""Single-flight scrape with a small in-memory TTL cache."""

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import replace

from jobspy import scrape_jobs

from .constants import CACHE_MAX, CACHE_TTL
from .results import Outcome, postprocess

_lock = threading.Lock()
_cache: "OrderedDict[str, Outcome]" = OrderedDict()
_cache_lock = threading.Lock()


class Busy(Exception):
    pass


def make_key(kwargs: dict) -> str:
    return hashlib.sha256(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()


def cache_get(key: str, now: float | None = None) -> Outcome | None:
    now = time.time() if now is None else now
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit.created > CACHE_TTL:
            del _cache[key]
            return None
        return hit


def cache_put(key: str, outcome: Outcome) -> None:
    with _cache_lock:
        _cache.pop(key, None)
        _cache[key] = outcome
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


def env_extras(supported: set[str]) -> dict:
    """Proxy settings from the environment only. Never logged, cached, or rendered."""
    extras = {}
    proxies = [p.strip() for p in os.environ.get("JOBSPY_PROXIES", "").split(",") if p.strip()]
    if proxies:
        extras["proxies"] = proxies
    ca_cert = os.environ.get("JOBSPY_CA_CERT", "").strip()
    if ca_cert:
        extras["ca_cert"] = ca_cert
    return {k: v for k, v in extras.items() if k in supported}


def run(kwargs: dict, refresh: bool, supported: set[str], scraper=None) -> Outcome:
    scraper = scraper or scrape_jobs
    key = make_key(kwargs)
    hit = None if refresh else cache_get(key)
    if hit:
        return replace(hit, from_cache=True)
    if not _lock.acquire(blocking=False):
        raise Busy()
    try:
        call = {**kwargs, **env_extras(supported)}
        t0 = time.time()
        df = scraper(**call)
        attrs = dict(getattr(df, "attrs", {}) or {})  # capture before any manipulation
        out = postprocess(df, attrs, kwargs["site_name"], key, time.time() - t0, t0)
        cache_put(key, out)
        return out
    finally:
        _lock.release()
