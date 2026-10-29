"""Query string -> scrape_jobs kwargs. Pure functions, no I/O."""

from .constants import BOARD_NAMES, COUNTRY_NAMES, DEFAULT_BOARDS, DEFAULTS, JOB_TYPES, MAX_RESULTS, MORE_OPTIONS

# field -> (label, minimum, maximum)
INT_FIELDS = {
    "results_wanted": ("Results wanted", 1, MAX_RESULTS),
    "hours_old": ("Hours old", 1, None),
    "distance": ("Distance", 1, None),
    "offset": ("Offset", 0, None),
}
TEXT_FIELDS = ["location", "user_agent"]
BOOL_FIELDS = ["is_remote", "fetch_description", "easy_apply", "enforce_annual_salary"]
HIDDEN = {"linkedin_fetch_description", "google_search_term", "proxies", "ca_cert"}


def _int(raw, label, lo, hi, errors):
    try:
        value = int(raw)
    except ValueError:
        errors.append(f"{label} must be a whole number, got “{raw}”.")
        return None
    if value < lo or (hi is not None and value > hi):
        bound = f"between {lo} and {hi}" if hi is not None else f"at least {lo}"
        errors.append(f"{label} must be {bound}, got {value}.")
        return None
    return value


def parse(qp, supported: set[str]) -> tuple[dict, list[str], list[str]]:
    """Return (kwargs, errors, notices). Collects every error instead of stopping at the first."""
    get = lambda k: (qp.get(k) or "").strip()  # noqa: E731
    errors: list[str] = []
    kwargs: dict = {}

    term = get("search_term")
    if not term:
        errors.append("Enter a search term.")
    else:
        kwargs["search_term"] = term

    sites = [s.strip() for s in qp.getlist("site_name") if s.strip()]
    unknown = [s for s in sites if s not in BOARD_NAMES]
    if unknown:
        errors.append(f"Unknown board: {', '.join(unknown)}.")
    sites = [s for s in BOARD_NAMES if s in sites]  # canonical order, deduped
    if not sites:
        errors.append("Select at least one job board.")
    else:
        kwargs["site_name"] = sites

    for field, (label, lo, hi) in INT_FIELDS.items():
        raw = get(field)
        if raw:
            value = _int(raw, label, lo, hi, errors)
            if value is not None:
                kwargs[field] = value

    for field in TEXT_FIELDS:
        if get(field):
            kwargs[field] = get(field)

    job_type = get("job_type")
    if job_type:
        if job_type in JOB_TYPES:
            kwargs["job_type"] = job_type
        else:
            errors.append(f"Unknown job type “{job_type}”.")

    country = get("country_indeed")
    if country:
        if country in COUNTRY_NAMES:
            kwargs["country_indeed"] = country
        else:
            errors.append(f"Unknown country “{country}”.")

    ids_raw = get("linkedin_company_ids")
    if ids_raw:
        tokens = [t.strip() for t in ids_raw.split(",") if t.strip()]
        bad = [t for t in tokens if not t.isdigit()]
        if bad:
            errors.append(f"LinkedIn company IDs must be whole numbers separated by commas; not valid: {', '.join(bad)}.")
        elif tokens:
            kwargs["linkedin_company_ids"] = [int(t) for t in tokens]

    for field in BOOL_FIELDS:
        if get(field):
            kwargs[field] = True

    kwargs["description_format"] = "plain"
    kwargs["verbose"] = 1

    dropped = sorted(k for k in kwargs if k not in supported)
    notices = []
    if dropped:
        notices.append(f"Ignored, not supported by the installed jobspy: {', '.join(dropped)}.")
        kwargs = {k: v for k, v in kwargs.items() if k in supported}
    return kwargs, errors, notices


def form_values(qp) -> dict:
    """Raw values for prefilling the form. Defaults apply only before the first search."""
    submitted = "search_term" in qp
    values = {k: (qp.get(k) or "").strip() for k in qp.keys() if k != "site_name"}
    if submitted:
        values["site_name"] = qp.getlist("site_name")
    else:
        values = {**DEFAULTS, **values, "site_name": DEFAULT_BOARDS}
    values["more_open"] = any(values.get(k) for k in MORE_OPTIONS)
    return values


def form_fields(supported: set[str]) -> set[str]:
    """Fields the form should render for this jobspy version."""
    return supported - HIDDEN
