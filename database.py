"""
database.py - Data ingestion and validation layer
Financial Data Validation & Reporting Tool

Responsibilities:
  - Load CSV files into SQLite (one table per company/ticker)
  - Validate schema: required columns, date format, numeric types
  - Detect and report data quality issues (nulls, duplicates, gaps)
  - Expose query helpers used by the analysis and reporting modules
"""

import sqlite3
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = Path(__file__).parent / "finans.db"

REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "name"}
COLUMN_MAP = {
    "date":  "Date",
    "open":  "Open",
    "high":  "High",
    "low":   "Low",
    "close": "Close",
    "name":  "Ticker",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# -- Custom exceptions --

class SchemaError(Exception):
    """Raised when the CSV is missing required columns."""

class EmptyDataError(Exception):
    """Raised when the filtered dataset contains no rows."""

class DateRangeError(Exception):
    """Raised for invalid date range inputs."""


# -- CSV ingestion --

def load_csv(csv_path: str) -> pd.DataFrame:
    """Read a CSV file and normalise column names to lowercase."""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise SchemaError(f"Missing required columns: {sorted(missing)}")
    return df


def validate_dataframe(df: pd.DataFrame) -> dict:
    """
    Run data quality checks and return a validation report.

    Returns:
        dict with keys: null_counts, duplicate_dates, negative_prices, coverage_pct
    """
    report = {}

    # Null / missing values per column
    report["null_counts"] = df[["open", "high", "low", "close"]].isnull().sum().to_dict()

    # Duplicate date-ticker combinations
    dupes = df.duplicated(subset=["date", "name"], keep=False)
    report["duplicate_rows"] = int(dupes.sum())

    # Negative or zero prices (data integrity check)
    price_cols = ["open", "high", "low", "close"]
    neg = (df[price_cols] <= 0).any(axis=1).sum()
    report["negative_or_zero_prices"] = int(neg)

    # Coverage: expected trading days vs actual records (per ticker)
    df["date"] = pd.to_datetime(df["date"])
    coverage = {}
    for ticker, grp in df.groupby("name"):
        min_d, max_d = grp["date"].min(), grp["date"].max()
        total_days = (max_d - min_d).days + 1
        # Rough trading day estimate: ~5/7 of calendar days
        expected_trading = max(1, round(total_days * 5 / 7))
        actual = len(grp)
        coverage[ticker] = round(actual / expected_trading * 100, 1)
    report["coverage_pct_by_ticker"] = coverage

    return report


def import_to_db(
    csv_path: str,
    progress_callback=None,
) -> tuple[list[str], dict]:
    """
    Load CSV data into SQLite.  Creates/replaces one table per ticker.

    Args:
        csv_path:          Path to the CSV file.
        progress_callback: Optional callable(pct: float) for UI progress bars.

    Returns:
        (list_of_tickers, validation_report)
    """
    df = load_csv(csv_path)
    validation = validate_dataframe(df)

    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

    tickers = sorted(df["Ticker"].unique())
    total = len(tickers)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for i, ticker in enumerate(tickers, 1):
        subset = df[df["Ticker"] == ticker][["Date", "Open", "High", "Low", "Close"]]
        cur.execute(f'DROP TABLE IF EXISTS "{ticker}"')
        cur.execute(f"""
            CREATE TABLE "{ticker}" (
                Date  TEXT    NOT NULL,
                Open  REAL    NOT NULL,
                High  REAL    NOT NULL,
                Low   REAL    NOT NULL,
                Close REAL    NOT NULL
            )
        """)
        subset.to_sql(ticker, conn, if_exists="append", index=False)

        if progress_callback:
            progress_callback(i / total * 100)

    conn.commit()
    conn.close()
    log.info("Imported %d tickers from %s", total, csv_path)
    return tickers, validation


# -- Query helpers --

def get_all_tickers() -> list[str]:
    """Return all ticker names stored in the database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tables = [
        r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    conn.close()
    return tables


def _detect_column_schema(conn: sqlite3.Connection, ticker: str) -> dict:
    """
    Auto-detect whether the table uses English or Turkish column names.
    Returns a mapping: {standard_name -> actual_column_name}
    """
    cur = conn.cursor()
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{ticker}")').fetchall()]
    col_set = set(cols)

    # English schema (created by this tool's importer)
    if {"Date", "Open", "High", "Low", "Close"}.issubset(col_set):
        return {"Date": "Date", "Open": "Open", "High": "High",
                "Low": "Low", "Close": "Close"}

    # Turkish schema (legacy / existing databases)
    if {"Tarih", "Acilis", "Yuksek", "Dusuk", "Kapanis"}.issubset(col_set):
        return {"Date": "Tarih", "Open": "Acilis", "High": "Yuksek",
                "Low": "Dusuk", "Close": "Kapanis"}

    raise SchemaError(
        f"Unrecognised column schema in table '{ticker}'. "
        f"Found: {sorted(cols)}"
    )


def fetch_ticker_data(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Query price data for a single ticker within an optional date range.
    Handles both English and Turkish column name schemas automatically.

    Args:
        ticker:     Table name / ticker symbol.
        start_date: ISO format string "YYYY-MM-DD" (inclusive).
        end_date:   ISO format string "YYYY-MM-DD" (inclusive).

    Returns:
        DataFrame with normalised English columns [Date, Open, High, Low, Close].

    Raises:
        DateRangeError: if dates are invalid or start > end.
        EmptyDataError: if the query returns no rows.
    """
    if start_date and end_date:
        try:
            s = datetime.strptime(start_date, "%Y-%m-%d")
            e = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise DateRangeError("Dates must be in YYYY-MM-DD format.")
        if s > e:
            raise DateRangeError("Start date cannot be after end date.")

    conn = sqlite3.connect(DB_PATH)
    schema = _detect_column_schema(conn, ticker)

    d, o, h, l, c = (schema[k] for k in ("Date", "Open", "High", "Low", "Close"))

    if start_date and end_date:
        query = f"""
            SELECT "{d}" AS Date, "{o}" AS Open, "{h}" AS High,
                   "{l}" AS Low,  "{c}" AS Close
            FROM   "{ticker}"
            WHERE  "{d}" BETWEEN ? AND ?
            ORDER  BY "{d}"
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
    else:
        query = f"""
            SELECT "{d}" AS Date, "{o}" AS Open, "{h}" AS High,
                   "{l}" AS Low,  "{c}" AS Close
            FROM   "{ticker}"
            ORDER  BY "{d}"
        """
        df = pd.read_sql_query(query, conn)

    conn.close()
    df["Date"] = pd.to_datetime(df["Date"])

    if df.empty:
        raise EmptyDataError(
            f"No data found for '{ticker}' "
            f"between {start_date} and {end_date}."
        )
    return df


def get_summary_stats(ticker: str, price_col: str) -> dict:
    """
    Return descriptive statistics and data quality metrics for a ticker+column.
    Automatically resolves column names for both English and Turkish schemas.
    """
    conn = sqlite3.connect(DB_PATH)
    schema = _detect_column_schema(conn, ticker)

    # Map standard English price_col name to actual DB column
    col_map_reverse = {
        "Open": schema["Open"], "High": schema["High"],
        "Low": schema["Low"],   "Close": schema["Close"],
    }
    actual_price_col = col_map_reverse.get(price_col, price_col)
    date_col = schema["Date"]

    query = f"""
        SELECT
            COUNT(*)                             AS total_records,
            MIN("{date_col}")                    AS first_date,
            MAX("{date_col}")                    AS last_date,
            ROUND(MIN("{actual_price_col}"), 4)  AS min_price,
            ROUND(MAX("{actual_price_col}"), 4)  AS max_price,
            ROUND(AVG("{actual_price_col}"), 4)  AS avg_price,
            SUM(CASE WHEN "{actual_price_col}" IS NULL THEN 1 ELSE 0 END) AS null_count
        FROM "{ticker}"
    """
    row = pd.read_sql_query(query, conn).iloc[0]
    conn.close()
    return row.to_dict()


def detect_missing_trading_days(ticker: str) -> list[str]:
    """
    Identify weekday gaps in the date sequence (potential missing data).

    Returns list of ISO date strings where data is absent but a weekday exists.
    """
    conn = sqlite3.connect(DB_PATH)
    schema = _detect_column_schema(conn, ticker)
    date_col = schema["Date"]
    dates = pd.read_sql_query(
        f'SELECT "{date_col}" AS Date FROM "{ticker}" ORDER BY "{date_col}"', conn
    )["Date"].tolist()
    conn.close()

    if len(dates) < 2:
        return []

    existing = set(dates)
    start = datetime.strptime(dates[0], "%Y-%m-%d")
    end   = datetime.strptime(dates[-1], "%Y-%m-%d")

    missing = []
    current = start + timedelta(days=1)
    while current < end:
        if current.weekday() < 5:  # Mon-Fri
            ds = current.strftime("%Y-%m-%d")
            if ds not in existing:
                missing.append(ds)
        current += timedelta(days=1)

    return missing
