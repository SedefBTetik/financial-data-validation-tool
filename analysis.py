"""
analysis.py - Chart generation and statistical analysis
Financial Data Validation & Reporting Tool

Responsibilities:
  - Render price charts with moving averages, Bollinger Bands, volume context
  - Compute rolling statistics used in reports
  - Save chart images to the charts/ directory
  - Return file paths for downstream use (PDF reports, GUI display)
"""

import matplotlib
matplotlib.use("Agg")  # headless rendering - safe for both GUI and batch use

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from pathlib import Path

CHARTS_DIR = Path(__file__).parent / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

# -- Colour palette (dark professional theme) --
PALETTE = {
    "background": "#0f172a",
    "surface":    "#1e293b",
    "grid":       "#334155",
    "price":      "#38bdf8",
    "ma5":        "#f59e0b",
    "ma20":       "#10b981",
    "bb_fill":    "#334155",
    "text":       "#e2e8f0",
    "title":      "#f8fafc",
    "accent":     "#818cf8",
}


def _apply_dark_theme(fig, ax):
    fig.patch.set_facecolor(PALETTE["background"])
    ax.set_facecolor(PALETTE["surface"])
    ax.tick_params(colors=PALETTE["text"], labelsize=9)
    ax.xaxis.label.set_color(PALETTE["text"])
    ax.yaxis.label.set_color(PALETTE["text"])
    ax.title.set_color(PALETTE["title"])
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["grid"])
    ax.grid(True, color=PALETTE["grid"], linewidth=0.5, alpha=0.7, linestyle="--")


def generate_price_chart(
    df: pd.DataFrame,
    ticker: str,
    price_col: str,
    show_ma5: bool = True,
    show_ma20: bool = True,
    show_bollinger: bool = False,
) -> str:
    """
    Render a price chart with optional moving averages and Bollinger Bands.

    Args:
        df:              DataFrame from database.fetch_ticker_data()
        ticker:          Ticker symbol (used in title and filename).
        price_col:       Column to plot: Open | High | Low | Close.
        show_ma5:        Overlay 5-day simple moving average.
        show_ma20:       Overlay 20-day simple moving average.
        show_bollinger:  Overlay Bollinger Bands (20-day, _2_).

    Returns:
        Absolute path to the saved PNG file.
    """
    fig, ax = plt.subplots(figsize=(11, 5))
    _apply_dark_theme(fig, ax)

    # Price line
    ax.plot(
        df["Date"], df[price_col],
        color=PALETTE["price"], linewidth=1.5,
        label=f"{price_col} Price", zorder=3
    )

    # 5-day MA
    if show_ma5 and len(df) >= 5:
        ma5 = df[price_col].rolling(5).mean()
        ax.plot(df["Date"], ma5, color=PALETTE["ma5"], linewidth=1.2,
                linestyle="--", label="MA-5", zorder=4)

    # 20-day MA
    if show_ma20 and len(df) >= 20:
        ma20 = df[price_col].rolling(20).mean()
        ax.plot(df["Date"], ma20, color=PALETTE["ma20"], linewidth=1.2,
                linestyle="-.", label="MA-20", zorder=4)

    # Bollinger Bands
    if show_bollinger and len(df) >= 20:
        ma = df[price_col].rolling(20).mean()
        std = df[price_col].rolling(20).std()
        upper = ma + 2 * std
        lower = ma - 2 * std
        ax.fill_between(df["Date"], lower, upper,
                        alpha=0.15, color=PALETTE["accent"], label="Bollinger Bands")
        ax.plot(df["Date"], upper, color=PALETTE["accent"], linewidth=0.8, alpha=0.5)
        ax.plot(df["Date"], lower, color=PALETTE["accent"], linewidth=0.8, alpha=0.5)

    # Formatting
    ax.set_title(f"{ticker}  _  {price_col} Price", fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Price (USD)", fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
    plt.xticks(rotation=30, ha="right")

    legend = ax.legend(
        facecolor=PALETTE["surface"], edgecolor=PALETTE["grid"],
        labelcolor=PALETTE["text"], fontsize=9
    )

    # Min/max annotations
    idx_max = df[price_col].idxmax()
    idx_min = df[price_col].idxmin()
    for idx, label, color in [(idx_max, "Peak", "#f87171"), (idx_min, "Trough", "#4ade80")]:
        ax.annotate(
            f"{label}\n${df[price_col][idx]:.2f}",
            xy=(df["Date"][idx], df[price_col][idx]),
            xytext=(15, 15 if label == "Peak" else -30),
            textcoords="offset points",
            fontsize=7.5, color=color,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        )

    plt.tight_layout()
    out_path = CHARTS_DIR / f"{ticker}_{price_col}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=PALETTE["background"])
    plt.close()
    return str(out_path)


def compute_rolling_stats(df: pd.DataFrame, price_col: str) -> pd.DataFrame:
    """
    Compute rolling statistics appended to the input DataFrame.

    Adds: MA5, MA20, Volatility_20 (rolling std), Pct_Change.
    """
    df = df.copy()
    df["MA5"]           = df[price_col].rolling(5).mean().round(4)
    df["MA20"]          = df[price_col].rolling(20).mean().round(4)
    df["Volatility_20"] = df[price_col].rolling(20).std().round(4)
    df["Pct_Change"]    = df[price_col].pct_change().mul(100).round(3)
    return df


def get_top_movers(df: pd.DataFrame, price_col: str, n: int = 5) -> pd.DataFrame:
    """
    Return the n largest single-day price moves (absolute % change).

    Useful for identifying anomalies and outliers in the dataset.
    """
    df = df.copy()
    df["Pct_Change"] = df[price_col].pct_change().mul(100).round(3)
    df["Abs_Change"] = df["Pct_Change"].abs()
    return (
        df.nlargest(n, "Abs_Change")
        [["Date", price_col, "Pct_Change"]]
        .reset_index(drop=True)
    )
