# Job search

A local browser UI for [python-jobspy](https://github.com/speedyapply/JobSpy). Spec: `srs-sds.md`.

## Setup

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 and the pinned dependencies.

```sh
uv sync
```

## Run

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Add `--reload` while editing code. The app binds to localhost only and has no authentication, so don't change `--host` to `0.0.0.0`.

## Proxies

Proxy settings are read from the environment only. They never appear in the form, URLs, logs, or the cache.

```sh
JOBSPY_PROXIES="user:pass@host:port,host2:port" \
JOBSPY_CA_CERT=/path/to/ca.pem \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For SOCKS proxies, run `uv add "requests[socks]"`.

## Caching

Results are kept in memory for 15 minutes (16 searches at most), so reloading the page or downloading the CSV doesn't hit the boards again. Use "Search again, ignoring cache" to force a fresh scrape. The cache is cleared on restart, and CSV links stop working once a result expires.

## Tips

- Boards rate-limit aggressively. LinkedIn in particular returns 429 for about a minute after a burst. "Fetch full descriptions" adds one request per LinkedIn job and makes this more likely.
- Indeed and Glassdoor only cover the countries in "More options". LinkedIn takes a free-text location worldwide.
- Diagnostics under the result count come straight from jobspy (`df.attrs["errors"]` / `["warnings"]`), for example when a board ignores a filter.

## Tests

```sh
uv run pytest
```

The tests use fake DataFrames and make no network calls.
