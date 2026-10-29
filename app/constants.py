BOARDS = [
    ("indeed", "country set under More options"),
    ("linkedin", "global"),
    ("zip_recruiter", "US/Canada only"),
    ("glassdoor", "limited country list"),
    ("bayt", "Middle East focus; location should name a country it covers"),
    ("bdjobs", "Bangladesh"),
    ("naukri", "India"),
    ("hellowork", "France, French search terms work best"),
]
BOARD_NAMES = [name for name, _ in BOARDS]
DEFAULT_BOARDS = ["indeed", "linkedin"]

JOB_TYPES = [
    "fulltime",
    "parttime",
    "contract",
    "temporary",
    "internship",
    "perdiem",
    "other",
    "volunteer",
]

# (name accepted by jobspy's Country enum, has Glassdoor support)
_GLASSDOOR = {
    "Argentina", "Australia", "Austria", "Belgium", "Brazil", "Canada", "France",
    "Germany", "Hong Kong", "India", "Ireland", "Italy", "Malaysia", "Mexico",
    "Netherlands", "New Zealand", "Singapore", "Spain", "Switzerland", "UK", "USA",
    "Vietnam",
}
_COUNTRY_NAMES = [
    "Argentina", "Australia", "Austria", "Bahrain", "Belgium", "Brazil", "Canada",
    "Chile", "China", "Colombia", "Costa Rica", "Czech Republic", "Denmark",
    "Ecuador", "Egypt", "Finland", "France", "Germany", "Greece", "Hong Kong",
    "Hungary", "India", "Indonesia", "Ireland", "Israel", "Italy", "Japan",
    "Kuwait", "Luxembourg", "Malaysia", "Mexico", "Morocco", "Netherlands",
    "New Zealand", "Nigeria", "Norway", "Oman", "Pakistan", "Panama", "Peru",
    "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Saudi Arabia",
    "Singapore", "South Africa", "South Korea", "Spain", "Sweden", "Switzerland",
    "Taiwan", "Thailand", "Turkey", "Ukraine", "United Arab Emirates", "UK", "USA",
    "Uruguay", "Venezuela", "Vietnam",
]
COUNTRIES = [(name, name in _GLASSDOOR) for name in _COUNTRY_NAMES]
COUNTRY_NAMES = set(_COUNTRY_NAMES)

MAX_RESULTS = 200
CACHE_TTL = 900
CACHE_MAX = 16

DEFAULTS = {"results_wanted": "20", "hours_old": "168"}
MORE_OPTIONS = [
    "country_indeed",
    "distance",
    "easy_apply",
    "enforce_annual_salary",
    "linkedin_company_ids",
    "offset",
    "user_agent",
]
