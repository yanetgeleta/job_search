"""CSV export with spreadsheet-formula neutralization."""

import pandas as pd

FORMULA_PREFIXES = "=+-@\t\r"


def neutralize(v):
    return ("'" + v) if isinstance(v, str) and v and v[0] in FORMULA_PREFIXES else v


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    safe = df.astype(object).map(neutralize)
    return safe.to_csv(index=False).encode("utf-8-sig")
