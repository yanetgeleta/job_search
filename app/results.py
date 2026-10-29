"""DataFrame post-processing and display helpers. Pure functions, no I/O."""

from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urlparse

import pandas as pd


@dataclass
class Outcome:
    key: str
    created: float
    elapsed: float
    records: list[dict]
    df: pd.DataFrame
    errors: dict
    warnings: dict
    counts: dict
    boards: list[str]
    from_cache: bool = False
    meta_fields: list = field(default_factory=list)


def safe_url(u) -> str | None:
    """Return u only if it is an http(s) URL with a host; blocks javascript:, data:, etc."""
    if not isinstance(u, str):
        return None
    u = u.strip()
    try:
        parsed = urlparse(u)
    except ValueError:
        return None
    return u if parsed.scheme.lower() in {"http", "https"} and parsed.netloc else None


def _amount(v) -> str | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f"{f:,.2f}".removesuffix(".00")


def format_salary(r: dict) -> str | None:
    lo, hi = _amount(r.get("min_amount")), _amount(r.get("max_amount"))
    if not lo and not hi:
        return None
    if lo and hi:
        text = lo if lo == hi else f"{lo}–{hi}"
    elif lo:
        text = f"{lo}+"
    else:
        text = f"up to {hi}"
    if r.get("currency"):
        text = f"{r['currency']} {text}"
    if r.get("interval"):
        text = f"{text} / {r['interval']}"
    return text


def _iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def clean(df: pd.DataFrame) -> list[dict]:
    """NaN/NaT/NA -> None, dates -> ISO strings."""
    obj = df.astype(object)
    obj = obj.where(obj.notna(), None)
    return [{k: _iso(v) for k, v in row.items()} for row in obj.to_dict("records")]


def _meta(r: dict) -> list[str]:
    items = [
        r.get("company"),
        r.get("location"),
        r.get("site"),
        r.get("date_posted"),
        r.get("job_type"),
        "remote" if r.get("is_remote") is True else None,
        r.get("job_level"),
        r.get("salary_text"),
    ]
    return [str(i) for i in items if i not in (None, "")]


def postprocess(df, attrs: dict, boards: list[str], key: str, elapsed: float, created: float) -> Outcome:
    attrs = attrs or {}
    errors = dict(attrs.get("errors") or {})
    warnings = dict(attrs.get("warnings") or {})
    if df is None or df.empty:
        return Outcome(key, created, elapsed, [], pd.DataFrame(), errors, warnings, {}, boards)

    if "job_url" in df.columns:
        df = df.drop_duplicates(subset="job_url")
    if "date_posted" in df.columns:
        df = df.assign(_d=pd.to_datetime(df["date_posted"], errors="coerce"))
        df = df.sort_values("_d", ascending=False, na_position="last", kind="stable").drop(columns="_d")
    df = df.reset_index(drop=True)

    records = clean(df)
    for r in records:
        r["salary_text"] = format_salary(r)
        r["href"] = safe_url(r.get("job_url"))
        r["direct_href"] = safe_url(r.get("job_url_direct"))
        r["company_href"] = safe_url(r.get("company_url"))
        r["meta"] = _meta(r)

    counts = df["site"].value_counts().to_dict() if "site" in df.columns else {}
    return Outcome(key, created, elapsed, records, df, errors, warnings, counts, boards)


RATE_HINT = "Wait about a minute before retrying this board, or configure a proxy."


def diagnostics(outcome: Outcome) -> list[str]:
    lines = []
    for board, msg in outcome.errors.items():
        line = f"{board}: {msg}"
        if "429" in str(msg) or "blocked" in str(msg).lower():
            line += f" {RATE_HINT}"
        lines.append(line)
    for board, msgs in outcome.warnings.items():
        for msg in msgs if isinstance(msgs, (list, tuple)) else [msgs]:
            lines.append(f"{board}: {msg}")
    for board in outcome.boards:
        if not outcome.counts.get(board) and board not in outcome.errors:
            lines.append(f"{board}: returned no jobs")
    return lines
