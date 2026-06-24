"""
main.py - Financial Data Validation & Reporting Tool
Entry point and GUI application

Architecture:
  database.py   - SQLite ingestion, SQL queries, data quality checks
  analysis.py   - Chart generation, rolling stats, anomaly detection
  report.py     - PDF report builder
  main.py       - Tkinter GUI (this file)

Key BA-relevant features demonstrated:
  - SQL-backed data validation with gap detection
  - Structured test scenario logging (UAT simulation)
  - Automated PDF reports for stakeholder communication
  - Action / audit trail log with timestamps
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
from pathlib import Path
from datetime import datetime

# Local modules
sys.path.insert(0, str(Path(__file__).parent))
from database import (
    import_to_db, get_all_tickers, fetch_ticker_data,
    get_summary_stats, detect_missing_trading_days,
    SchemaError, EmptyDataError, DateRangeError,
    DB_PATH,
)
from analysis import generate_price_chart, compute_rolling_stats, get_top_movers
from report import generate_report


# -- Colour tokens --
BG_DARK   = "#0f172a"
BG_MID    = "#1e293b"
BG_CARD   = "#1a2741"
FG_TEXT   = "#e2e8f0"
FG_ACCENT = "#38bdf8"
FG_MUTED  = "#94a3b8"
FG_GREEN  = "#10b981"
FG_RED    = "#f87171"
FG_AMBER  = "#f59e0b"
BTN_BG    = "#1d4ed8"
BTN_HOV   = "#2563eb"


# -- Helper: themed label --
def lbl(parent, text, size=9, bold=False, color=FG_TEXT, **kw):
    font = ("Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(parent, text=text, bg=parent["bg"] if hasattr(parent, "__getitem__") else BG_DARK,
                    fg=color, font=font, **kw)


# -- Main application class --
class FinancialApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Financial Data Validation & Reporting Tool")
        self.root.geometry("820x740")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)

        # State
        self._tickers: list[str] = []
        self._current_chart: str | None = None
        self._test_log: list[str] = []          # UAT / test scenario log

        self._build_ui()
        self._load_existing_tickers()

    # -- UI construction --

    def _build_ui(self):
        # -- Title bar
        title_bar = tk.Frame(self.root, bg=BG_MID, height=54)
        title_bar.pack(fill="x")
        tk.Label(
            title_bar, text="  _  Financial Data Validation & Reporting Tool",
            bg=BG_MID, fg=FG_ACCENT, font=("Segoe UI", 13, "bold")
        ).pack(side="left", padx=10, pady=12)
        tk.Label(
            title_bar, text="SQL _ Analytics _ Reporting  ",
            bg=BG_MID, fg=FG_MUTED, font=("Segoe UI", 9)
        ).pack(side="right", pady=14)

        # -- Main content: left panel + right log
        body = tk.Frame(self.root, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=14, pady=10)

        left = tk.Frame(body, bg=BG_DARK)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(body, bg=BG_MID, width=230)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        self._build_import_section(left)
        self._build_query_section(left)
        self._build_validation_section(left)
        self._build_actions(left)
        self._build_action_log(right)

    # -- Section: CSV Import --
    def _build_import_section(self, parent):
        card = tk.LabelFrame(
            parent, text=" 1 _ Data Import ",
            bg=BG_CARD, fg=FG_ACCENT, font=("Segoe UI", 9, "bold"),
            bd=1, relief="flat"
        )
        card.pack(fill="x", pady=(0, 8))

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", padx=10, pady=8)

        self._csv_label = tk.Label(
            row, text="No file selected", bg=BG_CARD, fg=FG_MUTED,
            font=("Segoe UI", 8), anchor="w"
        )
        self._csv_label.pack(side="left", fill="x", expand=True)

        self._btn_csv = self._make_button(row, "_  Select CSV", self._on_import_csv)
        self._btn_csv.pack(side="right", padx=(6, 0))

        self._progress = ttk.Progressbar(card, length=600, mode="determinate")
        self._progress.pack(fill="x", padx=10, pady=(0, 8))

        s = ttk.Style()
        s.configure("TProgressbar", troughcolor=BG_DARK, background=FG_ACCENT, thickness=6)

    # -- Section: Query parameters --
    def _build_query_section(self, parent):
        card = tk.LabelFrame(
            parent, text=" 2 _ Query Parameters ",
            bg=BG_CARD, fg=FG_ACCENT, font=("Segoe UI", 9, "bold"),
            bd=1, relief="flat"
        )
        card.pack(fill="x", pady=(0, 8))

        grid = tk.Frame(card, bg=BG_CARD)
        grid.pack(fill="x", padx=10, pady=8)

        # Ticker
        tk.Label(grid, text="Ticker / Company", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w", pady=2)
        self._combo_ticker = ttk.Combobox(grid, width=22, state="readonly")
        self._combo_ticker.grid(row=1, column=0, sticky="w", padx=(0, 14))
        self._combo_ticker.bind("<<ComboboxSelected>>", self._on_ticker_change)

        # Price type
        tk.Label(grid, text="Price Type", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=1, sticky="w", pady=2)
        self._combo_price = ttk.Combobox(
            grid, values=["Open", "High", "Low", "Close"], width=12, state="readonly"
        )
        self._combo_price.set("Close")
        self._combo_price.grid(row=1, column=1, sticky="w", padx=(0, 14))

        # Date range
        tk.Label(grid, text="Start Date (YYYY-MM-DD)", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w", pady=2)
        self._entry_start = tk.Entry(grid, width=14, bg=BG_MID, fg=FG_TEXT,
                                     insertbackground=FG_TEXT, font=("Segoe UI", 9),
                                     relief="flat")
        self._entry_start.insert(0, "2015-01-01")
        self._entry_start.grid(row=1, column=2, sticky="w", padx=(0, 14))

        tk.Label(grid, text="End Date (YYYY-MM-DD)", bg=BG_CARD, fg=FG_MUTED,
                 font=("Segoe UI", 8)).grid(row=0, column=3, sticky="w", pady=2)
        self._entry_end = tk.Entry(grid, width=14, bg=BG_MID, fg=FG_TEXT,
                                   insertbackground=FG_TEXT, font=("Segoe UI", 9),
                                   relief="flat")
        self._entry_end.insert(0, "2018-01-01")
        self._entry_end.grid(row=1, column=3, sticky="w")

        # Ticker info banner
        self._lbl_ticker_info = tk.Label(
            card, text="", bg=BG_CARD, fg=FG_MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self._lbl_ticker_info.pack(fill="x", padx=10, pady=(0, 6))

    # -- Section: Validation results --
    def _build_validation_section(self, parent):
        card = tk.LabelFrame(
            parent, text=" 3 _ Data Validation Results ",
            bg=BG_CARD, fg=FG_ACCENT, font=("Segoe UI", 9, "bold"),
            bd=1, relief="flat"
        )
        card.pack(fill="x", pady=(0, 8))

        self._val_frame = tk.Frame(card, bg=BG_CARD)
        self._val_frame.pack(fill="x", padx=10, pady=8)

        # Placeholder labels
        self._kpi_vars = {}
        kpis = [
            ("Records", "-"),
            ("Null Values", "-"),
            ("Missing Days", "-"),
            ("Date Range", "-"),
        ]
        for col, (label, default) in enumerate(kpis):
            f = tk.Frame(self._val_frame, bg=BG_MID, width=120)
            f.grid(row=0, column=col, padx=4, pady=4, sticky="ew")
            tk.Label(f, text=label, bg=BG_MID, fg=FG_MUTED,
                     font=("Segoe UI", 7)).pack(pady=(5, 0))
            var = tk.StringVar(value=default)
            tk.Label(f, textvariable=var, bg=BG_MID, fg=FG_ACCENT,
                     font=("Segoe UI", 12, "bold")).pack(pady=(0, 5))
            self._kpi_vars[label] = var

        self._lbl_gap_detail = tk.Label(
            card, text="", bg=BG_CARD, fg=FG_AMBER,
            font=("Segoe UI", 8), anchor="w", wraplength=540, justify="left"
        )
        self._lbl_gap_detail.pack(fill="x", padx=10, pady=(0, 6))

    # -- Section: Action buttons --
    def _build_actions(self, parent):
        row = tk.Frame(parent, bg=BG_DARK)
        row.pack(fill="x", pady=4)

        self._btn_validate = self._make_button(
            row, "_  Validate & Query", self._on_validate, state="disabled", color="#0e7490"
        )
        self._btn_validate.pack(side="left", padx=(0, 8))

        self._btn_chart = self._make_button(
            row, "_  Generate Chart", self._on_generate_chart, state="disabled"
        )
        self._btn_chart.pack(side="left", padx=(0, 8))

        self._btn_pdf = self._make_button(
            row, "_  Export PDF Report", self._on_export_pdf, state="disabled", color="#7c3aed"
        )
        self._btn_pdf.pack(side="left", padx=(0, 8))

        self._btn_clear = self._make_button(
            row, "_  Clear Log", self._on_clear_log, color="#374151"
        )
        self._btn_clear.pack(side="right")

    # -- Section: Action log --
    def _build_action_log(self, parent):
        tk.Label(
            parent, text="  Action & Audit Log",
            bg=BG_MID, fg=FG_ACCENT, font=("Segoe UI", 9, "bold"), anchor="w"
        ).pack(fill="x", pady=(10, 4))

        self._log_box = tk.Text(
            parent, bg=BG_DARK, fg=FG_TEXT, font=("Consolas", 8),
            relief="flat", wrap="word", state="disabled", cursor="arrow"
        )
        self._log_box.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        # Tag colours
        self._log_box.tag_config("info",    foreground=FG_TEXT)
        self._log_box.tag_config("success", foreground=FG_GREEN)
        self._log_box.tag_config("warn",    foreground=FG_AMBER)
        self._log_box.tag_config("error",   foreground=FG_RED)
        self._log_box.tag_config("accent",  foreground=FG_ACCENT)
        self._log_box.tag_config("ts",      foreground=FG_MUTED)

    # -- Widget factory --
    def _make_button(self, parent, text, command, state="normal", color=BTN_BG):
        btn = tk.Button(
            parent, text=text, command=command, state=state,
            bg=color, fg="white", activebackground=BTN_HOV, activeforeground="white",
            font=("Segoe UI", 9, "bold"), relief="flat",
            padx=12, pady=6, cursor="hand2"
        )
        return btn

    # -- Logging --
    def _log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"{ts}  ", "ts")
        self._log_box.insert("end", f"{message}\n", level)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

        # Mirror to test log for PDF inclusion
        self._test_log.append(f"[{ts}] {message}")

    # -- Load tickers from existing DB --
    def _load_existing_tickers(self):
        if DB_PATH.exists():
            tickers = get_all_tickers()
            if tickers:
                self._tickers = tickers
                self._combo_ticker["values"] = tickers
                self._combo_ticker.set(tickers[0])
                self._btn_validate["state"] = "normal"
                self._log(f"Database loaded _ {len(tickers)} tickers available", "accent")

    # -- Event handlers --

    def _on_ticker_change(self, _event=None):
        ticker = self._combo_ticker.get()
        if not ticker:
            return
        try:
            stats = get_summary_stats(ticker, "Close")
            self._lbl_ticker_info.config(
                text=f"  {ticker}  _  {int(stats['total_records'])} records  "
                     f"_  {stats['first_date'][:10]} -> {stats['last_date'][:10]}"
            )
        except Exception:
            pass

    def _on_import_csv(self):
        path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        self._csv_label.config(text=Path(path).name)
        self._log(f"CSV selected: {Path(path).name}", "info")
        self._progress["value"] = 0

        def _run():
            try:
                self._log("Starting schema validation _", "info")
                tickers, validation = import_to_db(
                    path, progress_callback=self._set_progress
                )
                self._tickers = tickers
                self.root.after(0, self._after_import, tickers, validation)
            except SchemaError as e:
                self.root.after(0, self._log, f"Schema error: {e}", "error")
                self.root.after(0, messagebox.showerror, "Schema Error", str(e))
            except Exception as e:
                self.root.after(0, self._log, f"Import failed: {e}", "error")
                self.root.after(0, messagebox.showerror, "Import Error", str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _set_progress(self, pct: float):
        self.root.after(0, self._progress.__setitem__, "value", pct)
        self.root.after(0, self.root.update_idletasks)

    def _after_import(self, tickers, validation):
        self._combo_ticker["values"] = tickers
        self._combo_ticker.set(tickers[0])
        self._btn_validate["state"] = "normal"
        self._log(f"OK Imported {len(tickers)} tickers successfully", "success")

        # Log validation report
        nulls = validation.get("null_counts", {})
        total_nulls = sum(nulls.values())
        dupes = validation.get("duplicate_rows", 0)
        neg   = validation.get("negative_or_zero_prices", 0)

        self._log(f"  Null values found: {total_nulls}", "warn" if total_nulls else "success")
        self._log(f"  Duplicate rows:    {dupes}",       "warn" if dupes else "success")
        self._log(f"  Invalid prices:    {neg}",         "warn" if neg else "success")
        self._on_ticker_change()

    def _on_validate(self):
        ticker     = self._combo_ticker.get()
        price_col  = self._combo_price.get()
        start_date = self._entry_start.get().strip()
        end_date   = self._entry_end.get().strip()

        if not ticker or not price_col:
            messagebox.showwarning("Missing Input", "Please select a ticker and price type.")
            return

        self._log(f"Running validation query: {ticker} _ {price_col} _ {start_date} -> {end_date}", "accent")

        try:
            df = fetch_ticker_data(ticker, start_date, end_date)
            stats = get_summary_stats(ticker, price_col)
            missing = detect_missing_trading_days(ticker)

            # Update KPI badges
            self._kpi_vars["Records"].set(str(len(df)))
            self._kpi_vars["Null Values"].set(str(int(stats["null_count"])))
            self._kpi_vars["Missing Days"].set(str(len(missing)))
            self._kpi_vars["Date Range"].set(
                f"{str(stats['first_date'])[:7]}_{str(stats['last_date'])[:7]}"
            )

            # Gap detail
            if missing:
                shown = ", ".join(missing[:5]) + (f"  (+{len(missing)-5} more)" if len(missing) > 5 else "")
                self._lbl_gap_detail.config(
                    text=f"_  Missing trading days: {shown}", fg=FG_AMBER
                )
                self._log(f"  _  {len(missing)} missing trading day(s) detected", "warn")
            else:
                self._lbl_gap_detail.config(
                    text="OK  No missing trading days in full dataset", fg=FG_GREEN
                )
                self._log("  OK  Date sequence complete - no gaps", "success")

            self._log(
                f"  Stats: min=${stats['min_price']:.2f}  max=${stats['max_price']:.2f}"
                f"  avg=${stats['avg_price']:.2f}", "info"
            )

            # Enable downstream buttons
            self._btn_chart["state"] = "normal"
            self._btn_pdf["state"]   = "normal"

            # Log test scenario result
            self._log(f"  Test PASS: Query returned {len(df)} rows - boundary conditions OK", "success")

        except DateRangeError as e:
            self._log(f"  Test FAIL: DateRangeError - {e}", "error")
            messagebox.showerror("Date Range Error", str(e))
        except EmptyDataError as e:
            self._log(f"  Test FAIL: EmptyDataError - {e}", "warn")
            messagebox.showwarning("No Data", str(e))
        except Exception as e:
            self._log(f"  Error: {e}", "error")
            messagebox.showerror("Query Error", str(e))

    def _on_generate_chart(self):
        ticker     = self._combo_ticker.get()
        price_col  = self._combo_price.get()
        start_date = self._entry_start.get().strip()
        end_date   = self._entry_end.get().strip()

        self._log(f"Generating chart: {ticker} _ {price_col}", "accent")

        try:
            df = fetch_ticker_data(ticker, start_date, end_date)
            chart_path = generate_price_chart(df, ticker, price_col,
                                              show_ma5=True, show_ma20=True,
                                              show_bollinger=True)
            self._current_chart = chart_path
            self._log(f"  OK Chart saved -> {chart_path}", "success")
            messagebox.showinfo("Chart Saved",
                                f"Chart saved to:\n{chart_path}\n\nOpen the file to view.")
        except (DateRangeError, EmptyDataError) as e:
            self._log(f"  Chart error: {e}", "error")
            messagebox.showerror("Chart Error", str(e))
        except Exception as e:
            self._log(f"  Chart error: {e}", "error")
            messagebox.showerror("Chart Error", str(e))

    def _on_export_pdf(self):
        ticker     = self._combo_ticker.get()
        price_col  = self._combo_price.get()
        start_date = self._entry_start.get().strip()
        end_date   = self._entry_end.get().strip()

        if not self._current_chart:
            messagebox.showwarning(
                "Chart Required",
                "Please generate a chart first before exporting the PDF report."
            )
            return

        self._log(f"Generating PDF report: {ticker} _ {price_col}", "accent")

        try:
            df = fetch_ticker_data(ticker, start_date, end_date)
            pdf_path = generate_report(
                df=df,
                ticker=ticker,
                price_col=price_col,
                start_date=start_date,
                end_date=end_date,
                chart_path=self._current_chart,
                validation_log=self._test_log[-20:],  # last 20 log entries
            )
            self._log(f"  OK PDF report saved -> {pdf_path}", "success")
            messagebox.showinfo("Report Saved", f"PDF report saved to:\n{pdf_path}")
        except Exception as e:
            self._log(f"  PDF error: {e}", "error")
            messagebox.showerror("PDF Error", str(e))

    def _on_clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._test_log.clear()


# -- Entry point --
if __name__ == "__main__":
    root = tk.Tk()

    # TTK dark style
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox",
                    fieldbackground="#1e293b", background="#1e293b",
                    foreground="#e2e8f0", selectbackground="#0f172a",
                    arrowcolor="#38bdf8")
    style.configure("TProgressbar", troughcolor="#0f172a",
                    background="#38bdf8", thickness=6)

    app = FinancialApp(root)
    root.mainloop()
