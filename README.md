# Financial Data Validation & Reporting Tool

> A business analyst support tool for financial time-series data: SQL-based validation,
> anomaly detection, and stakeholder-ready PDF reporting across 500+ company stocks.

---

## Overview

This tool was built to demonstrate core **business analyst workflows** applied to a real financial dataset (S&P 500 constituents, 2013–2018, ~500 companies, 1,259 trading days each).

It answers the practical question: *before handing a dataset to a decision-maker, how do you know it's trustworthy?*

The answer is the same whether you're working on stock prices, ERP orders, CRM customer records, or inventory tables — which is what this tool is designed to show.

---

## Key Features

### 1. SQL-Backed Data Ingestion
- Loads CSV files into a **SQLite** database (one table per company / ticker)
- Schema validation before any data touches the database: checks for required columns, correct data types, and rejects malformed files with clear error messages
- Equivalent to the column-mapping and data-type verification step in any ERP/CRM integration

### 2. Data Quality Validation
All checks are run via **SQL queries** against the database, not in-memory:

| Check | SQL Pattern Used |
|---|---|
| Null / missing values | `SUM(CASE WHEN col IS NULL THEN 1 ELSE 0 END)` |
| Duplicate date-ticker rows | `GROUP BY date, ticker HAVING COUNT(*) > 1` |
| Min / Max / Avg prices | `MIN()`, `MAX()`, `AVG()` aggregates |
| Record count per period | `COUNT(*) WHERE Date BETWEEN ? AND ?` |
| Missing trading days | Date sequence gap analysis (Python + SQL) |

### 3. Anomaly Detection
- Identifies the largest single-day price movements (% change) — flags potential data quality issues or corporate events requiring investigation
- Equivalent to "tutarsızlık tespiti" in order/stock/customer data validation

### 4. Test Scenario Logging (UAT Simulation)
Every query execution logs its outcome automatically:
- ✓ PASS: expected data returned, boundary conditions handled correctly
- ✗ FAIL: captured with error type (DateRangeError, EmptyDataError, SchemaError)

This mirrors the test case tracking done in UAT processes, and the log is included directly in the PDF report.

### 5. Stakeholder PDF Reports
Automated PDF generation containing:
- Cover page with metadata
- Data validation summary (nulls, gaps, coverage)
- Price chart with moving averages and Bollinger Bands
- Statistical summary table (min/max/avg/volatility)
- Top daily movers table (anomaly detection output)
- Most recent 10 records
- QA / test scenario log

### 6. Audit Trail
Every action (import, query, validation result, chart generation, report export) is logged with a timestamp in the action log panel — equivalent to audit trail documentation in project tracking tools.

---

## Project Structure

```
financial_tool/
│
├── main.py          # GUI entry point (Tkinter)
├── database.py      # Data ingestion, SQL queries, validation
├── analysis.py      # Chart generation, rolling stats, anomaly detection
├── report.py        # PDF report builder
│
├── finans.db        # SQLite database (auto-created on first import)
├── charts/          # Generated chart images
└── reports/         # Generated PDF reports
```

---

## Requirements

```
Python 3.10+
pandas
matplotlib
fpdf2
numpy
tkinter (built-in)
sqlite3 (built-in)
```

Install dependencies:
```bash
pip install pandas matplotlib fpdf2 numpy
```

---

## How to Run

```bash
cd financial_tool
python main.py
```

**Workflow:**
1. Click **Select CSV** to load a stock data CSV file
2. Select a ticker, price type, and date range
3. Click **Validate & Query** to run SQL checks and see validation results
4. Click **Generate Chart** to render the price chart
5. Click **Export PDF Report** to produce a stakeholder-ready document

**CSV Format Expected:**
```
Date, Open, High, Low, Close, Name
2015-01-02, 110.5, 112.0, 109.8, 111.3, AAPL
```

---

## Test Scenarios Implemented

| Scenario | Expected Outcome | Covered |
|---|---|---|
| CSV missing required column | `SchemaError` raised, clear message | ✓ |
| Start date after end date | `DateRangeError` raised | ✓ |
| Date range with no data | `EmptyDataError` raised, warning shown | ✓ |
| Invalid date format | `DateRangeError` with format hint | ✓ |
| Single-day range | Returns 1 row, chart renders correctly | ✓ |
| Ticker with missing trading days | Gap list shown in UI and PDF | ✓ |
| Export PDF before chart | Informative warning, no crash | ✓ |

---

## Data

- **Source:** S&P 500 historical daily prices (2013–2018)
- **Companies:** ~500 tickers
- **Fields:** Date, Open, High, Low, Close
- **Storage:** SQLite (one table per ticker, ~1,259 rows each)
- **Total records:** ~630,000 rows

---

## Skills Demonstrated

| Skill | Where |
|---|---|
| SQL (SELECT, WHERE, GROUP BY, aggregates) | `database.py` — all query functions |
| Data validation & gap detection | `database.py` — `validate_dataframe()`, `detect_missing_trading_days()` |
| Test scenarios & UAT logging | `main.py` — action log + test pass/fail capture |
| Stakeholder reporting | `report.py` — structured PDF with sections |
| Audit trail documentation | `main.py` — timestamped action log |
| Data quality (null/duplicate detection) | `database.py` — `validate_dataframe()` |
| Analytical thinking | `analysis.py` — anomaly detection, moving averages |
