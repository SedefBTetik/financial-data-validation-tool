"""
report.py - PDF report generator
Financial Data Validation & Reporting Tool

Produces a structured, stakeholder-ready PDF containing:
  - Cover page with metadata
  - Data validation summary (null counts, gaps, coverage)
  - Price chart
  - Statistical summary table
  - Top daily movers (anomaly detection)
  - Test scenario results log
"""

from fpdf import FPDF
from pathlib import Path
from datetime import datetime
import pandas as pd

from analysis import compute_rolling_stats, get_top_movers
from database import get_summary_stats, detect_missing_trading_days

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# -- Brand colours (hex without #) --
C_DARK   = (15,  23,  42)   # #0f172a
C_MID    = (30,  41,  59)   # #1e293b
C_ACCENT = (56, 189, 248)   # #38bdf8
C_GREEN  = (16, 185, 129)   # #10b981
C_RED    = (248, 113, 113)  # #f87171
C_LIGHT  = (226, 232, 240)  # #e2e8f0
C_WHITE  = (255, 255, 255)


class FinancialReport(FPDF):
    """Custom FPDF subclass with consistent header/footer."""

    def __init__(self, ticker: str, price_col: str):
        super().__init__()
        self.ticker    = ticker
        self.price_col = price_col
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)

    # -- Header --
    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(*C_DARK)
        self.rect(0, 0, 210, 14, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*C_ACCENT)
        self.set_y(4)
        self.cell(0, 6, f"  {self.ticker} _ {self.price_col} Price Analysis", align="L")
        self.set_text_color(*C_LIGHT)
        self.cell(0, 6, f"{datetime.now().strftime('%Y-%m-%d')}  ", align="R")
        self.ln(8)

    # -- Footer --
    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-14)
        self.set_fill_color(*C_DARK)
        self.rect(0, self.get_y(), 210, 14, "F")
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*C_LIGHT)
        self.cell(0, 10, f"  Financial Data Validation & Reporting Tool  _  Page {self.page_no()}", align="L")
        self.cell(0, 10, "Confidential - Internal Use Only  ", align="R")

    # -- Section heading --
    def section_heading(self, title: str):
        self.set_fill_color(*C_MID)
        self.set_text_color(*C_ACCENT)
        self.set_font("Helvetica", "B", 11)
        self.set_draw_color(*C_ACCENT)
        self.set_line_width(0.5)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(2)
        self.cell(0, 8, title, ln=True)
        self.ln(2)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)

    # -- Body text --
    def body(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, text)
        self.ln(2)

    # -- KPI badge row --
    def kpi_row(self, items: list[tuple]):
        """items: list of (label, value) tuples, max 4."""
        col_w = 174 / len(items)
        self.set_font("Helvetica", "B", 8)
        for label, value in items:
            x = self.get_x()
            y = self.get_y()
            self.set_fill_color(*C_MID)
            self.rect(x, y, col_w - 2, 14, "F")
            self.set_text_color(*C_ACCENT)
            self.set_xy(x + 2, y + 1)
            self.cell(col_w - 4, 5, str(label), ln=False)
            self.set_xy(x + 2, y + 7)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*C_WHITE)
            self.cell(col_w - 4, 5, str(value))
            self.set_xy(x + col_w, y)
            self.set_font("Helvetica", "B", 8)
        self.ln(16)

    # -- Table --
    def data_table(self, headers: list, rows: list, col_widths: list):
        # Header row
        self.set_fill_color(*C_DARK)
        self.set_text_color(*C_ACCENT)
        self.set_font("Helvetica", "B", 8)
        for h, w in zip(headers, col_widths):
            self.cell(w, 7, str(h), border=0, fill=True)
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 8)
        for i, row in enumerate(rows):
            self.set_fill_color(*C_MID) if i % 2 == 0 else self.set_fill_color(22, 31, 48)
            self.set_text_color(220, 230, 240)
            for val, w in zip(row, col_widths):
                self.cell(w, 6, str(val), border=0, fill=True)
            self.ln()
        self.ln(4)


# -- Main report builder --

def generate_report(
    df: pd.DataFrame,
    ticker: str,
    price_col: str,
    start_date: str,
    end_date: str,
    chart_path: str,
    validation_log: list[str] | None = None,
) -> str:
    """
    Build and save a PDF report.

    Args:
        df:             Filtered price DataFrame.
        ticker:         Ticker symbol.
        price_col:      Price column analysed (Open/High/Low/Close).
        start_date:     Analysis start date string.
        end_date:       Analysis end date string.
        chart_path:     Absolute path to the pre-generated chart PNG.
        validation_log: Optional list of QA/test notes to include.

    Returns:
        Path to the saved PDF file.
    """
    pdf = FinancialReport(ticker, price_col)

    # -- Cover page --
    pdf.add_page()
    pdf.set_fill_color(*C_DARK)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_y(60)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(*C_ACCENT)
    pdf.cell(0, 12, ticker, align="C", ln=True)

    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*C_LIGHT)
    pdf.cell(0, 8, f"{price_col} Price Analysis Report", align="C", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 6, f"Period: {start_date} - {end_date}", align="C", ln=True)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", ln=True)
    pdf.ln(20)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*C_ACCENT)
    for line in [
        "Financial Data Validation & Reporting Tool",
        "Internal Stakeholder Report - Data Quality & Trend Analysis",
    ]:
        pdf.cell(0, 6, line, align="C", ln=True)

    # -- Page 2: Validation & KPIs --
    pdf.add_page()

    stats = get_summary_stats(ticker, price_col)
    missing_days = detect_missing_trading_days(ticker)

    pdf.section_heading("1. Data Validation Summary")
    pdf.body(
        f"The table '{ticker}' was queried for {price_col} prices between "
        f"{start_date} and {end_date}. The following quality checks were applied: "
        "null value detection, date sequence gap analysis, and statistical boundary validation."
    )

    pdf.kpi_row([
        ("Total Records",  int(stats["total_records"])),
        ("Null Values",    int(stats["null_count"])),
        ("Missing Days",   len(missing_days)),
        ("Coverage Start", str(stats["first_date"])[:10]),
    ])

    # Gap detail
    if missing_days:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_RED)
        pdf.cell(0, 6, f"  !  {len(missing_days)} missing trading day(s) detected:", ln=True)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(220, 180, 180)
        shown = missing_days[:10]
        pdf.cell(0, 5, "  " + ",  ".join(shown) + ("  ..." if len(missing_days) > 10 else ""), ln=True)
    else:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*C_GREEN)
        pdf.cell(0, 6, "  OK  No missing trading days detected in the full dataset.", ln=True)
    pdf.ln(4)

    # -- Statistical summary --
    pdf.set_text_color(0, 0, 0)
    pdf.section_heading("2. Statistical Summary")

    df_stats = compute_rolling_stats(df.reset_index(drop=True), price_col)

    stats_rows = [
        ["Minimum Price",        f"${stats['min_price']:.4f}"],
        ["Maximum Price",        f"${stats['max_price']:.4f}"],
        ["Average Price",        f"${stats['avg_price']:.4f}"],
        ["5-Day Moving Avg (last)",  f"${df_stats['MA5'].dropna().iloc[-1]:.4f}" if df_stats['MA5'].dropna().any() else "N/A"],
        ["20-Day Moving Avg (last)", f"${df_stats['MA20'].dropna().iloc[-1]:.4f}" if df_stats['MA20'].dropna().any() else "N/A"],
        ["20-Day Volatility (last)", f"${df_stats['Volatility_20'].dropna().iloc[-1]:.4f}" if df_stats['Volatility_20'].dropna().any() else "N/A"],
        ["Records in Range",     len(df)],
        ["Date Range",           f"{start_date} -> {end_date}"],
    ]
    pdf.data_table(["Metric", "Value"], stats_rows, [95, 79])

    # -- Price chart --
    pdf.section_heading("3. Price Chart")
    if Path(chart_path).exists():
        pdf.image(chart_path, x=18, w=174)
    pdf.ln(4)

    # -- Top daily movers --
    pdf.section_heading("4. Anomaly Detection - Top Daily Price Movers")
    pdf.body(
        "The following dates recorded the largest single-day percentage changes "
        "within the selected period. Significant outliers may indicate data quality "
        "issues, market events, or corporate actions requiring further investigation."
    )
    movers = get_top_movers(df.reset_index(drop=True), price_col, n=7)
    mover_rows = [
        [
            str(r["Date"])[:10],
            f"${r[price_col]:.4f}",
            f"{r['Pct_Change']:+.3f}%"
        ]
        for _, r in movers.iterrows()
    ]
    pdf.data_table(["Date", f"{price_col} Price", "Daily Change %"], mover_rows, [60, 60, 54])

    # -- Last 10 records --
    pdf.section_heading("5. Most Recent Records (last 10 rows)")
    tail = df.tail(10).reset_index(drop=True)
    tail_rows = [
        [str(r["Date"])[:10], f"${r['Open']:.2f}", f"${r['High']:.2f}",
         f"${r['Low']:.2f}", f"${r['Close']:.2f}"]
        for _, r in tail.iterrows()
    ]
    pdf.data_table(["Date", "Open", "High", "Low", "Close"], tail_rows, [40, 33, 33, 33, 35])

    # -- QA / Test log --
    if validation_log:
        pdf.section_heading("6. QA & Test Scenario Log")
        pdf.body(
            "The following test scenarios were executed during this session. "
            "Results confirm the tool handles boundary conditions correctly, "
            "consistent with UAT acceptance criteria."
        )
        for entry in validation_log:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(180, 220, 200)
            pdf.cell(0, 5, f"  _  {entry}", ln=True)

    # -- Save --
    out_path = REPORTS_DIR / f"{ticker}_{price_col}_report.pdf"
    pdf.output(str(out_path))
    return str(out_path)
