from starlette.datastructures import QueryParams

from app.main import SUPPORTED
from app.params import form_values, parse


def q(s: str) -> QueryParams:
    return QueryParams(s)


def test_minimal_valid():
    kwargs, errors, notices = parse(q("search_term=dev&site_name=indeed"), SUPPORTED)
    assert errors == [] and notices == []
    assert kwargs == {
        "search_term": "dev",
        "site_name": ["indeed"],
        "description_format": "plain",
        "verbose": 1,
    }


def test_blanks_are_omitted():
    qs = "search_term=+dev+&site_name=indeed&location=&results_wanted=&hours_old=&job_type=&country_indeed=&distance=&offset=&user_agent=&linkedin_company_ids="
    kwargs, errors, _ = parse(q(qs), SUPPORTED)
    assert errors == []
    assert set(kwargs) == {"search_term", "site_name", "description_format", "verbose"}
    assert kwargs["search_term"] == "dev"


def test_collects_all_errors():
    qs = "search_term=&results_wanted=abc&hours_old=0&offset=-1&distance=x"
    _, errors, _ = parse(q(qs), SUPPORTED)
    assert len(errors) == 6
    assert "Enter a search term." in errors
    assert "Select at least one job board." in errors
    assert any("Results wanted" in e and "abc" in e for e in errors)
    assert any("Hours old" in e for e in errors)
    assert any("Offset" in e for e in errors)
    assert any("Distance" in e for e in errors)


def test_results_wanted_range():
    _, errors, _ = parse(q("search_term=a&site_name=indeed&results_wanted=201"), SUPPORTED)
    assert errors == ["Results wanted must be between 1 and 200, got 201."]


def test_types_and_booleans():
    qs = (
        "search_term=a&site_name=linkedin&site_name=indeed&results_wanted=50&hours_old=24"
        "&offset=0&is_remote=1&fetch_description=1&easy_apply=1&job_type=internship&country_indeed=UK"
    )
    kwargs, errors, _ = parse(q(qs), SUPPORTED)
    assert errors == []
    assert kwargs["site_name"] == ["indeed", "linkedin"]  # canonical order
    assert kwargs["results_wanted"] == 50 and kwargs["hours_old"] == 24 and kwargs["offset"] == 0
    assert kwargs["is_remote"] is kwargs["fetch_description"] is kwargs["easy_apply"] is True
    assert "enforce_annual_salary" not in kwargs
    assert kwargs["job_type"] == "internship" and kwargs["country_indeed"] == "UK"


def test_company_ids():
    kwargs, errors, _ = parse(q("search_term=a&site_name=linkedin&linkedin_company_ids=1, 22 ,333"), SUPPORTED)
    assert errors == [] and kwargs["linkedin_company_ids"] == [1, 22, 333]
    _, errors, _ = parse(q("search_term=a&site_name=linkedin&linkedin_company_ids=1,abc"), SUPPORTED)
    assert errors and "abc" in errors[0]


def test_unknown_values_rejected():
    _, errors, _ = parse(q("search_term=a&site_name=google&job_type=x&country_indeed=Ethiopia"), SUPPORTED)
    assert len(errors) == 4  # unknown board, no valid board, job type, country


def test_unsupported_params_dropped():
    supported = SUPPORTED - {"fetch_description", "verbose"}
    kwargs, errors, notices = parse(q("search_term=a&site_name=indeed&fetch_description=1"), supported)
    assert errors == []
    assert "fetch_description" not in kwargs and "verbose" not in kwargs
    assert notices and "fetch_description" in notices[0] and "verbose" in notices[0]


def test_form_values_defaults_only_before_search():
    fresh = form_values(q(""))
    assert fresh["results_wanted"] == "20" and fresh["hours_old"] == "168"
    assert fresh["site_name"] == ["indeed", "linkedin"] and fresh["more_open"] is False
    submitted = form_values(q("search_term=a&site_name=bayt&results_wanted=&distance=10"))
    assert submitted["results_wanted"] == "" and submitted["site_name"] == ["bayt"]
    assert submitted["more_open"] is True
