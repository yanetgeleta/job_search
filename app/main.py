import inspect
import logging
import time
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jobspy import scrape_jobs

from .constants import BOARDS, COUNTRIES, JOB_TYPES, MAX_RESULTS
from .params import form_fields, form_values, parse
from .results import diagnostics
from .export import to_csv_bytes
from .runner import Busy, cache_get, run

log = logging.getLogger("uvicorn.error")
BASE = Path(__file__).parent

SUPPORTED = set(inspect.signature(scrape_jobs).parameters)
log.info("jobspy %s params: %s", version("python-jobspy"), sorted(SUPPORTED))

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def _refresh_url(qp) -> str:
    items = [(k, v) for k, v in qp.multi_items() if k != "refresh"]
    return "/?" + urlencode(items + [("refresh", "1")])


def base_context(request: Request) -> dict:
    return {
        "form": form_values(request.query_params),
        "fields": form_fields(SUPPORTED),
        "boards": BOARDS,
        "countries": COUNTRIES,
        "job_types": JOB_TYPES,
        "max_results": MAX_RESULTS,
        "errors": [],
        "notices": [],
        "outcome": None,
        "diagnostics": [],
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    qp = request.query_params
    ctx = base_context(request)
    if "search_term" in qp:
        kwargs, errors, notices = parse(qp, SUPPORTED)
        ctx.update(errors=errors, notices=notices)
        if not errors:
            try:
                outcome = run(kwargs, refresh=qp.get("refresh") == "1", supported=SUPPORTED)
                ctx.update(
                    outcome=outcome,
                    diagnostics=diagnostics(outcome),
                    cached_at=time.strftime("%H:%M", time.localtime(outcome.created)),
                    refresh_url=_refresh_url(qp),
                )
            except Busy:
                ctx["errors"] = ["A search is already running. Wait for it to finish."]
            except Exception as e:
                ctx["errors"] = [f"Search failed: {e}"]
    return templates.TemplateResponse(
        request, "index.html", ctx, status_code=400 if ctx["errors"] else 200
    )


@app.get("/export.csv")
def export(key: str = ""):
    outcome = cache_get(key) if key else None
    if outcome is None:
        return PlainTextResponse("Results expired. Run the search again.", status_code=404)
    filename = time.strftime("jobs-%Y%m%d-%H%M.csv", time.localtime(outcome.created))
    return Response(
        to_csv_bytes(outcome.df),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
