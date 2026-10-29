## What changed after reading the README

**1. Remove Google Jobs entirely (confidence ~95%).**
The FAQ says Google Jobs is currently unavailable. That deletes `google` from the site list, `google_search_term`, and my earlier fallback rule for it.

**2. Use the library's own diagnostics instead of my hard-coded filter note (~90% that `attrs` exists in the latest release, so verify with a real run).**
The README says `jobs.attrs["errors"]` and `jobs.attrs["warnings"]` carry per-board failures and ignored options. That replaces my "Indeed honors only one of hours_old / job_type / easy_apply" note. I wrote it from memory of older docs, and this README doesn't confirm it (I'd now put it at ~60% still true), so the UI shouldn't assert it. It should show whatever the library reports.

**3. Move `fetch_description` into the main form (~90%).**
LinkedIn search results don't include descriptions or job type unless this is on. Without it, most LinkedIn rows would look empty. It adds one request per job and LinkedIn returns 429s on bursts, so it defaults to off with a visible warning.

**4. Cache results and export by key, instead of re-running the search (~85%).**
All boards block aggressively, and LinkedIn's 429 lasts about a minute. A refresh or CSV click that re-scrapes would trigger exactly that. Use a small in-memory cache with a TTL.

**5. Take `proxies` and `ca_cert` out of the form (~85%).**
My earlier plan used GET query params for the whole form. Proxy credentials in a URL end up in browser history and uvicorn's access log, which contradicts "never log proxies". They move to environment variables.

**6. Country support matters for what you can actually search (~90%, from the README table).**
Indeed and Glassdoor only work for the listed countries, and Ethiopia isn't on the list. If you want Ethiopia-based listings, LinkedIn (global) is the only board that takes a plain `location`. Bayt "searches all countries unless location names one it covers", so it's worth testing but I can't confirm its coverage. For other countries, remote roles, and the Indeed/Glassdoor list, `country_indeed` must be a dropdown of exact names.

**7. Add an Indeed query-syntax hint.**
Indeed searches descriptions too, so `"engineering intern" software -tax` beats a bare "internship". A one-line hint under the search box will improve your results more than any other change here.

**8. Two security details I skipped before.**
- Scraped URLs must be scheme-checked before being used as `href`, because Jinja autoescape doesn't block `javascript:` URLs.
- CSV cells starting with `=`, `+`, `-` or `@` can run as formulas in Excel.

**9. Default `hours_old` becomes 168 (one week), not 72.**
Internship postings are sparse. This is a taste call, and it's editable in the form.

**Unchanged:** FastAPI + Jinja2 with no JS framework, plain `def` routes, default sites `indeed` + `linkedin`, no database, and the visual design rules.

**One caution on "execute it perfectly":** no spec gets there in one shot. The build order in Part 2 §14 (small phases, each verified by running the app) is what makes the result reliable.

---

# JOBSPY LOCAL SEARCH UI: SRS + SDS

# PART 1: SOFTWARE REQUIREMENTS SPECIFICATION

## 1. Introduction

**1.1 Purpose.** This defines the behavior of a local web interface for the `python-jobspy` library, so the user can search job boards from a browser form instead of the terminal.

**1.2 Scope.**
- In scope: a search form, a results list, diagnostics from the library, and CSV export.
- Out of scope: database, accounts, saved searches, scheduling, notifications, charts, dark mode, Docker, JS frameworks, Google Jobs, any external API.

**1.3 Definitions.**
- *Board*: a job site scraped by JobSpy (`indeed`, `linkedin`, and so on).
- *Search*: one call to `scrape_jobs` with parameters derived from the form.
- *Outcome*: the processed result of a Search, including records, diagnostics, and timing.
- *Key*: a hash identifying a Search's normalized form parameters.

**1.4 References.** The python-jobspy README. The installed library's `inspect.signature(scrape_jobs)` is authoritative wherever the two disagree.

## 2. Overall description

**2.1 Perspective.** A single-process Python web app that wraps `jobspy.scrape_jobs`. State is limited to an in-memory cache.

**2.2 User.** One developer, running locally. No authentication.

**2.3 Environment.** Python 3.10+, localhost only, internet access, any modern browser.

**2.4 Constraints.**
- C1. Bind to `127.0.0.1` only.
- C2. No Node toolchain, CSS framework, or CDN assets. One CSS file, at most ~15 lines of vanilla JS.
- C3. Visual design is strictly minimal (see NFR-6).
- C4. A scrape is slow (often 10 to 90 seconds) and blocking.

**2.5 Assumptions.**
- A1. `scrape_jobs` returns a pandas DataFrame, with `.attrs["errors"]` (dict: board to message) and `.attrs["warnings"]` (dict: board to list of messages) where supported.
- A2. Any board can fail or rate-limit at any time. This is normal, not exceptional.
- A3. Columns present in the DataFrame vary by board, so every column access must tolerate absence.

## 3. Functional requirements

**FR-1 Search form.**
- FR-1.1 `GET /` renders a single form with `method="get"`.
- FR-1.2 Always-visible fields:
  - `search_term` (text, required), with the hint: *Indeed searches descriptions too. Use "quotes" for exact phrases and -word to exclude. Example: "engineering intern" software -tax*
  - `location` (text)
  - `results_wanted` (number, default 20, min 1, max 200, "per board")
  - `hours_old` (number, default 168, blank allowed)
  - `job_type` (select: blank, fulltime, parttime, contract, temporary, internship, perdiem, other, volunteer)
  - `is_remote` (checkbox)
  - `fetch_description` (checkbox, only if supported by the installed version), labelled "Fetch full descriptions (slower; LinkedIn is more likely to rate-limit you)"
  - `site_name` (checkboxes; defaults indeed and linkedin). Each board carries a muted hint:
    - indeed: "country set under More options"
    - linkedin: "global"
    - zip_recruiter: "US/Canada only"
    - glassdoor: "limited country list"
    - bayt: "Middle East focus; location should name a country it covers"
    - bdjobs: "Bangladesh"
    - naukri: "India"
    - hellowork: "France, French search terms work best"
- FR-1.3 Inside a native `<details>` labelled "More options":
  - `country_indeed` (select of exact names; blank means library default)
  - `distance` (int, miles)
  - `easy_apply` (checkbox)
  - `enforce_annual_salary` (checkbox)
  - `linkedin_company_ids` (text, comma-separated ints)
  - `offset` (int, ≥0)
  - `user_agent` (text)
- FR-1.4 The form is prefilled from the current query string. The `<details>` is open if any of its fields is non-default.
- FR-1.5 Hard-coded: `description_format="plain"`, `verbose=1`.

**FR-2 Validation and parameter mapping.**
- FR-2.1 A Search is triggered when the query string contains `search_term`. With no query string, only the form is shown.
- FR-2.2 `search_term` must be non-blank, and at least one board must be selected. Never pass an empty `site_name` list, because the library treats the default as all boards.
- FR-2.3 Integer fields are cast with `int()`. Bad input produces a human-readable message naming the field. Range checks: results_wanted 1–200, hours_old ≥1, distance ≥1, offset ≥0.
- FR-2.4 Blank strings, unchecked checkboxes, and blank selects are omitted from kwargs. Never pass `""`, `None`, or `False` for optional parameters.
- FR-2.5 `linkedin_company_ids` is parsed to `list[int]`, and a non-integer token is a validation error.
- FR-2.6 Any kwarg not in the installed `scrape_jobs` signature is dropped, and a notice lists the dropped parameters.
- FR-2.7 Collect all validation errors and show them together. Do not stop at the first.

**FR-3 Execution.**
- FR-3.1 Run via a plain `def` route so the blocking call uses FastAPI's threadpool.
- FR-3.2 Only one scrape runs at a time. A concurrent request shows "A search is already running" and does not scrape.
- FR-3.3 Wrap the call in `try/except Exception` and display the message on the page, never a 500 trace.
- FR-3.4 Record elapsed seconds.
- FR-3.5 Proxies come from `JOBSPY_PROXIES` (comma-separated) and the CA certificate from `JOBSPY_CA_CERT`. If set, they are passed as `proxies` and `ca_cert`. Neither is ever shown, logged, cached, or placed in a URL.

**FR-4 Post-processing.**
- FR-4.1 Capture `attrs` immediately after the scrape, before any DataFrame manipulation.
- FR-4.2 Drop duplicate `job_url` values.
- FR-4.3 Sort by `date_posted` descending, with missing or unparseable dates last.
- FR-4.4 Convert NaN, NaT, and pandas NA to `None`, and dates to ISO strings.
- FR-4.5 Compute per-board result counts from the `site` column.

**FR-5 Results display.**
- FR-5.1 A count line, e.g. "37 jobs from indeed, linkedin, in 14.2 s".
- FR-5.2 Results are an ordered list, one row per job, with hairline separators. Line 1: title, linked to `job_url` (`target="_blank" rel="noopener noreferrer"`). Line 2, joined by " · ", omitting empty items: company, location, site, date posted, job type, "remote" (if `is_remote`), job level, salary.
- FR-5.3 Salary reads `CUR min–max / interval`, with thousands separators, shown only if min or max exists.
- FR-5.4 A native `<details>` per row ("Details") holds, when present:
  - description (`white-space: pre-wrap`)
  - skills
  - emails
  - experience_range
  - company_industry
  - company_num_employees
  - links: `job_url_direct` ("Apply link") and `company_url`
- FR-5.5 If a row has no description, show a muted note: "No description from this board. Enable 'Fetch full descriptions' to retrieve it."
- FR-5.6 Any URL used as an `href` must pass `safe_url()` (http or https scheme and a hostname). Otherwise render it as plain text or omit it.
- FR-5.7 An empty result shows a plain message suggesting a shorter query, a longer time window, fewer filters, or different boards.

**FR-6 Diagnostics.**
- FR-6.1 `attrs["errors"]` renders above the results as a plain list, `board: message`.
- FR-6.2 `attrs["warnings"]` renders the same way.
- FR-6.3 Selected boards that returned zero rows and have no error are listed as "returned no jobs".
- FR-6.4 If an error message contains `429` or "blocked", append: "Wait about a minute before retrying this board, or configure a proxy."
- FR-6.5 If the installed version provides no `attrs`, skip FR-6.1 and FR-6.2 without failing.

**FR-7 Caching.**
- FR-7.1 The cache key is the SHA-256 of canonical JSON of the form-derived kwargs (sorted keys), with proxy and CA data excluded.
- FR-7.2 TTL is 15 minutes, with at most 16 entries (evict the oldest).
- FR-7.3 A repeated identical search within the TTL is served from the cache, and the page says "Cached result from HH:MM".
- FR-7.4 A plain-text link "Search again, ignoring cache" adds `refresh=1` to the query string, which bypasses the cache and replaces the entry.
- FR-7.5 The URL is bookmarkable. Opening it after expiry re-runs the search.

**FR-8 CSV export.**
- FR-8.1 `GET /export.csv?key=<key>` returns the cached DataFrame with all columns, as `text/csv`, with the header `Content-Disposition: attachment; filename="jobs-YYYYMMDD-HHMM.csv"`.
- FR-8.2 An unknown or expired key shows "Results expired. Run the search again." with status 404.
- FR-8.3 String cells beginning with `=`, `+`, `-`, `@`, tab, or CR are prefixed with `'` to neutralize spreadsheet formulas.
- FR-8.4 Encode as UTF-8 with BOM, so Excel opens it correctly.

**FR-9 Version adaptation.**
- FR-9.1 At startup, compute `SUPPORTED = set(inspect.signature(scrape_jobs).parameters)` and log the jobspy version and the set.
- FR-9.2 The form omits fields whose parameter isn't in `SUPPORTED`.
- FR-9.3 Never expose `linkedin_fetch_description` (deprecated).

**FR-10 Minimal busy state.**
On submit, a ≤15-line vanilla JS snippet disables the submit button and changes its label to "Searching…". Nothing else is interactive.

## 4. Data requirements

The JobPost columns the UI reads, all optional because any may be absent: `site, job_url, job_url_direct, title, company, location, date_posted, job_type, interval, min_amount, max_amount, currency, is_remote, job_level, description, skills, emails, experience_range, company_industry, company_num_employees, company_url`. The CSV exports every column the DataFrame has. Nothing is persisted to disk.

## 5. External interfaces

| Route | Method | Behavior |
|---|---|---|
| `/` | GET | Form. With `search_term` present, run or fetch a cached search and render results. |
| `/export.csv` | GET | CSV of a cached Outcome by `key`. |
| `/static/style.css` | GET | Stylesheet. |

Library interface: `jobspy.scrape_jobs(**kwargs) -> pandas.DataFrame`.

## 6. Non-functional requirements

- **NFR-1 Reliability.** No code path returns a 500 for user input or board failures.
- **NFR-2 Security.** Jinja autoescape stays on, and `|safe` is never used on scraped data (FR-5.6, FR-8.3). The server binds to localhost only. No secrets in URLs or logs.
- **NFR-3 Privacy.** No persistence beyond the in-memory cache, which is lost on restart.
- **NFR-4 Performance.** Page render over a cached result is under 200 ms for 200 rows.
- **NFR-5 Maintainability.** Pure functions for parsing and post-processing, so they're testable without network access. Total code under ~500 lines.
- **NFR-6 Visual design (strict).**
  - Background `#ffffff`, text `#1f1f1c`, muted `#6b6860`, hairlines `#e5e2dc`. One accent, olive `#4a5d3a`, used for links and the primary button only.
  - No gradients, shadows, icons, emojis, pills, animations, or rounded cards. Border radius ≤2px.
  - Headings in Georgia, serif fallback. Body in `system-ui`, 16px, line-height 1.5.
  - Single column, max-width 920px, generous whitespace. Labels above fields, flat 1px-bordered inputs.
  - It should read like a well-set document, not a dashboard.

## 7. Acceptance tests

- AT-1. `uvicorn app.main:app --reload --host 127.0.0.1` starts, and `/` renders the form with no console errors.
- AT-2. `search_term=software engineer`, indeed only, returns rows, and the CSV downloads with all columns.
- AT-3. Submitting with every optional field blank doesn't crash.
- AT-4. Submitting with `search_term` blank, or with no board checked, shows a validation message and no scrape.
- AT-5. Entering `abc` in `results_wanted` shows a readable message.
- AT-6. indeed + linkedin where linkedin returns a 429 still shows Indeed rows, plus the LinkedIn error under diagnostics.
- AT-7. Repeating the same search within 15 minutes shows "Cached result" and takes under 1 s.
- AT-8. `/export.csv?key=nope` returns the "expired" message.
- AT-9. A fake job row with `job_url="javascript:alert(1)"` renders no clickable link (unit test).
- AT-10. A fake row with title `=HYPERLINK(...)` is prefixed with `'` in the CSV (unit test).
- AT-11. Selecting `job_type=internship` on a board that doesn't support it surfaces the library's warning rather than silently returning odd results.

---

# PART 2: SOFTWARE DESIGN SPECIFICATION

## 1. Architecture

```
Browser ──GET /?params──▶ FastAPI route (plain def, threadpool)
                              │
                 params.py: parse + validate ──▶ errors? render form + messages
                              │ kwargs
                 runner.py: cache lookup ──hit──▶ Outcome
                              │ miss
                 lock ─▶ scrape_jobs(**kwargs) ─▶ DataFrame (+ attrs)
                              │
                 results.py: dedupe, sort, clean, counts ─▶ Outcome ─▶ cache
                              │
                 Jinja2 template ──▶ HTML
Browser ──GET /export.csv?key──▶ export.py ──▶ CSV from cached DataFrame
```

## 2. Dependencies

`requirements.txt`: `fastapi`, `uvicorn`, `jinja2`, `python-jobspy`. After installing, run `pip freeze` and pin those four plus pandas. Add `requests[socks]` only if the user uses SOCKS proxies. No `python-multipart` is needed because everything is GET.

## 3. Layout

```
jobspy-ui/
├── app/
│   ├── main.py          # routes, startup version log
│   ├── constants.py     # boards, job types, countries, limits
│   ├── params.py        # parse/validate query → SearchParams, kwargs
│   ├── runner.py        # lock, cache, scrape call, Outcome
│   ├── results.py       # postprocess, clean values, safe_url, salary format
│   ├── export.py        # CSV with formula neutralization
│   ├── templates/index.html
│   └── static/style.css
├── tests/               # pytest on pure functions
├── requirements.txt
└── README.md
```

## 4. Module design

**constants.py**
- `BOARDS`: ordered list of `(name, hint)` pairs for the eight boards.
- `DEFAULT_BOARDS = ["indeed", "linkedin"]`.
- `JOB_TYPES`: the eight values from the README.
- `COUNTRIES`: the exact names from the README table. A name followed by `*` has Glassdoor support: Argentina*, Australia*, Austria*, Bahrain, Belgium*, Brazil*, Canada*, Chile, China, Colombia, Costa Rica, Czech Republic, Denmark, Ecuador, Egypt, Finland, France*, Germany*, Greece, Hong Kong*, Hungary, India*, Indonesia, Ireland*, Israel, Italy*, Japan, Kuwait, Luxembourg, Malaysia*, Mexico*, Morocco, Netherlands*, New Zealand*, Nigeria, Norway, Oman, Pakistan, Panama, Peru, Philippines, Poland, Portugal, Qatar, Romania, Saudi Arabia, Singapore*, South Africa, South Korea, Spain*, Sweden, Switzerland*, Taiwan, Thailand, Turkey, Ukraine, United Arab Emirates, UK*, USA*, Uruguay, Venezuela, Vietnam*. Store as `(name, glassdoor: bool)` without the asterisk, and show a note "Glassdoor supports a subset."
- Limits: `MAX_RESULTS = 200`, `CACHE_TTL = 900`, `CACHE_MAX = 16`.

**params.py**
- `parse(query_params, supported: set[str]) -> tuple[dict, list[str], list[str]]`, returning `(kwargs, errors, notices)`.
- Rules, implemented in this order:
  1. Read with `.get` and `.getlist("site_name")`. Strip all strings.
  2. Validate `search_term` and sites, then each int field, collecting errors.
  3. Build kwargs, including a key only when the value is non-blank and truthy for booleans.
  4. Add `description_format="plain"` and `verbose=1`.
  5. Drop any key not in `supported`, appending to `notices`.
- `form_values(query_params)` returns the raw values for prefilling, separate from kwargs.
- Environment-based extras (`proxies`, `ca_cert`) are added in `runner.py` after the cache key is computed, so they never enter the key.

**runner.py**

```python
_lock = threading.Lock()
_cache: "OrderedDict[str, Outcome]" = OrderedDict()


@dataclass
class Outcome:
    key: str
    created: float
    elapsed: float
    records: list[dict]
    df: "pd.DataFrame"
    errors: dict
    warnings: dict
    counts: dict
    boards: list[str]
    from_cache: bool = False


class Busy(Exception): ...


def run(kwargs: dict, refresh: bool) -> Outcome:
    key = make_key(kwargs)  # sha256 of json.dumps(kwargs, sort_keys=True)
    hit = None if refresh else cache_get(key)  # honors TTL
    if hit:
        return replace(hit, from_cache=True)
    if not _lock.acquire(blocking=False):
        raise Busy()
    try:
        call = {**kwargs, **env_extras()}  # proxies / ca_cert from env
        t0 = time.time()
        df = scrape_jobs(**call)
        attrs = dict(getattr(df, "attrs", {}) or {})  # capture BEFORE manipulation
        out = postprocess(df, attrs, kwargs["site_name"], key, time.time() - t0)
        cache_put(key, out)
        return out
    finally:
        _lock.release()
```

**results.py**
- `postprocess(df, attrs, boards, key, elapsed)`:
  - If `df` is None or empty, return an Outcome with empty records and an empty DataFrame.
  - Dedupe on `job_url` (only if the column exists).
  - Make a temp column `_d = pd.to_datetime(df["date_posted"], errors="coerce")`, sort descending with `na_position="last"` and a stable sort, then drop `_d`.
  - `records = clean(df)`: cast to object, replace missing values with `None` (`df.astype(object).where(df.notna(), None)`), stringify date and datetime values with `isoformat()`, and `to_dict("records")`.
  - Add derived keys per record: `salary_text`, `href` (via `safe_url`), `direct_href`, `company_href`, `meta` (a list of the non-empty line-2 items).
  - `counts = df["site"].value_counts().to_dict()` if the column exists.
  - `errors = attrs.get("errors", {})`, `warnings = attrs.get("warnings", {})`.
- `safe_url(u)` returns `u` only if `urlparse(u).scheme in {"http","https"}` and netloc is non-empty, else `None`.
- `format_salary(r)` returns `"USD 110,000–135,000 / yearly"`, `"USD 110,000+ / yearly"`, or `None`. Cast amounts to float safely and drop trailing `.0`.
- `diagnostics(outcome)` builds the list for FR-6, including zero-result boards and the 429 hint.

**export.py**
- `to_csv_bytes(df)` copies the DataFrame, applies `neutralize` to every string cell, and calls `to_csv(index=False)`. It encodes as `utf-8-sig`.
- `neutralize(v)` is `("'" + v) if isinstance(v, str) and v and v[0] in "=+-@\t\r" else v`. Include the `v and` guard: an empty string would otherwise pass the `in` check.

**main.py**

```python
SUPPORTED = set(inspect.signature(scrape_jobs).parameters)
log.info("jobspy %s params: %s", version, sorted(SUPPORTED))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    qp = request.query_params
    ctx = base_context(request, SUPPORTED)  # boards, countries, hints, form values
    if "search_term" in qp:
        kwargs, errors, notices = parse(qp, SUPPORTED)
        ctx.update(errors=errors, notices=notices)
        if not errors:
            try:
                outcome = run(kwargs, refresh=qp.get("refresh") == "1")
                ctx.update(outcome=outcome, diagnostics=diagnostics(outcome))
            except Busy:
                ctx["errors"] = ["A search is already running. Wait for it to finish."]
            except Exception as e:
                ctx["errors"] = [f"Search failed: {e}"]
    return templates.TemplateResponse(
        request, "index.html", ctx, status_code=400 if ctx.get("errors") else 200
    )


@app.get("/export.csv")
def export(
    key: str,
): ...  # cache lookup → Response(csv, media_type="text/csv", headers=...)
```

Do not log the query string beyond uvicorn's default access log. Never log kwargs that include proxies.

## 5. Parameter mapping

| Form field | kwarg | Type | Included when |
|---|---|---|---|
| search_term | `search_term` | str | always (required) |
| site_name (multi) | `site_name` | list[str] | always (≥1 required) |
| location | `location` | str | non-blank |
| results_wanted | `results_wanted` | int 1–200 | non-blank |
| hours_old | `hours_old` | int ≥1 | non-blank |
| job_type | `job_type` | str | non-blank |
| is_remote | `is_remote` | bool | checked |
| fetch_description | `fetch_description` | bool | checked and supported |
| country_indeed | `country_indeed` | str | non-blank |
| distance | `distance` | int ≥1 | non-blank |
| easy_apply | `easy_apply` | bool | checked |
| enforce_annual_salary | `enforce_annual_salary` | bool | checked |
| linkedin_company_ids | `linkedin_company_ids` | list[int] | non-blank |
| offset | `offset` | int ≥0 | non-blank |
| user_agent | `user_agent` | str | non-blank |
| (none) | `description_format` | `"plain"` | always |
| (none) | `verbose` | `1` | always |
| env `JOBSPY_PROXIES` | `proxies` | list[str] | env set |
| env `JOBSPY_CA_CERT` | `ca_cert` | str | env set |

Everything is filtered through `SUPPORTED` before the call.

## 6. Template design (`index.html`)

Single file, no inheritance, order top to bottom:
1. `<h1>` "Job search" (Georgia) and a one-line muted subtitle.
2. Errors and notices, as a plain list with a left hairline border. No coloured alert boxes. Use the accent or a darker neutral for emphasis, never red banners.
3. The form, with rows built from CSS grid (`repeat(auto-fit, minmax(200px, 1fr))`) for short fields. Boards are a checkbox group with muted hints. Then `<details><summary>More options</summary>…</details>`. Then the primary submit button.
4. If an outcome exists:
   - count line and elapsed time, cached notice, and "Search again, ignoring cache" link
   - diagnostics list
   - `Download CSV` text link to `/export.csv?key=…`
   - `<ol class="results">` of rows per FR-5
5. Empty-state message when there are zero records.
6. The busy-state script at the end of the body.

## 7. CSS design (`style.css`)

Tokens on `:root`: `--bg:#fff; --text:#1f1f1c; --muted:#6b6860; --line:#e5e2dc; --accent:#4a5d3a`. `body{max-width:920px;margin:0 auto;padding:3rem 1.25rem;font:16px/1.5 system-ui}`. Headings use `Georgia, serif`. Inputs, selects, and textareas have `border:1px solid var(--line); border-radius:2px; padding:.5rem; background:#fff; font:inherit; width:100%`. The primary button is `background:var(--accent); color:#fff; border:0; border-radius:2px; padding:.6rem 1.1rem`. Links use `color:var(--accent)`. Result rows have `border-top:1px solid var(--line); padding:1rem 0`, with the title in Georgia 1.1rem and the meta line muted and smaller. There is no `box-shadow`, `gradient`, `transition`, or `animation` anywhere in the file.

## 8. Error handling matrix

| Situation | Behavior |
|---|---|
| Validation failure | Form re-rendered with all messages, status 400, no scrape |
| Another scrape running | Message, no scrape |
| `scrape_jobs` raises | Message on page, status 400, no cache entry |
| One board in `attrs["errors"]` | Other boards' rows shown, plus diagnostic line |
| All boards error | Empty result message, plus all diagnostics |
| Missing column in DataFrame | Treated as empty for that field |
| `attrs` missing | Diagnostics skipped |
| Unknown CSV key | "Results expired" message, status 404 |
| Parameter not supported by installed version | Dropped, with a notice |

## 9. Security design

Autoescape stays on. `safe_url` gates every `href` that comes from scraped data, and `rel="noopener noreferrer"` goes on every external link. CSV cells are neutralized. The server binds to `127.0.0.1`, with no CORS and no cookies. Proxy and CA settings come only from the environment and never reach logs, the cache key, the cache, templates, or URLs.

## 10. Testing

Pytest, with no network access, using hand-built DataFrames:
- `params.parse`: blank handling, int errors, multi-error collection, company-id parsing, unsupported-parameter dropping.
- `results.postprocess`: dedupe, sort with missing dates, NaN to None, an absent column, salary formatting, `safe_url` rejecting `javascript:` and `data:`.
- `export.neutralize` and CSV round-trip.
- Cache: TTL expiry and eviction at 16 entries.

Live tests are manual (AT-2, AT-6, AT-7), because boards change.

## 11. Build order for the agent

Each phase ends with the app running and a check performed. Do not start the next phase until the check passes.

1. **Skeleton.** Create the venv and install the four dependencies. Print the installed jobspy version and the `scrape_jobs` signature, and report any parameter from the README that is missing. Build `/` with only `search_term`, `location` and an indeed checkbox, and show raw rows. Check: AT-1 and AT-2.
2. **Parsing and display.** Add `params.py`, the full form, and the results rows with salary and details. Check: AT-3, AT-4, AT-5.
3. **Robustness.** Add `runner.py` (lock, cache), the diagnostics from `attrs`, safe URLs, and the busy-state script. Check: AT-6, AT-7, AT-9.
4. **Export.** Add the CSV route with neutralization. Check: AT-2, AT-8, AT-10.
5. **Polish.** Apply the full CSS spec. Write the README (setup, run command, env variables for proxies, the cache caveat). Run the pytest suite.

**Agent rules:**
- Do not invent library behavior. If `attrs`, a column, or a parameter doesn't exist in the installed version, say so and degrade as specified.
- Add no dependencies beyond those listed.
- Make no network calls other than `scrape_jobs`.
- Do not add features from the out-of-scope list.
- If a live scrape fails because of rate limiting during testing, wait a minute rather than adding retries, and do not add retry loops to the app.
- After each phase, report what was run and what was observed. Do not report success without running it.