"""Matplotlib chart figure for a single instrument."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def technicals_figure(
    df: pd.DataFrame,
    title: str,
    figsize: tuple[float, float] = (16, 12),
    linewidth: float = 1.6,
) -> plt.Figure:
    """Stacked Price/Volume + MACD + Stochastic + RSI + Bollinger figure.

    `df` must be enriched (see indicators.enrich).
    """
    fig, axes = plt.subplots(5, 1, figsize=figsize, sharex=True)
    fig.suptitle(title, fontweight="bold", fontsize=14)

    idx_min, idx_max = df.index.min(), df.index.max()

    # 1. Price + Volume
    ax = axes[0]
    ax.plot(df.index, df["Close"], color="black", linewidth=linewidth, label="Close")
    if "SMA_20" in df:
        ax.plot(df.index, df["SMA_20"], color="tab:orange", linewidth=1, label="SMA 20")
    if "SMA_50" in df:
        ax.plot(df.index, df["SMA_50"], color="tab:blue", linewidth=1, label="SMA 50")
    ax.set_ylabel("Price (GBp)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Price / Volume", fontweight="bold", fontsize=10, loc="left")
    vol_ax = ax.twinx()
    vol_ax.bar(df.index, df["Volume"], color="lightgrey", alpha=0.6, width=1.0)
    vol_ax.set_ylabel("Volume")
    vol_ax.ticklabel_format(style="plain", axis="y")

    # 2. MACD
    ax = axes[1]
    ax.plot(df.index, df["MACD"], color="tab:blue", linewidth=linewidth, label="MACD")
    ax.plot(df.index, df["MACD_SIGNAL"], color="tab:red", linewidth=linewidth, label="Signal")
    ax.bar(df.index, df["MACD_HIST"], color="grey", alpha=0.5, width=1.0)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("MACD", fontweight="bold", fontsize=10, loc="left")

    # 3. Stochastic
    ax = axes[2]
    ax.plot(df.index, df["STO_K"], color="tab:blue", linewidth=linewidth, label="%K")
    ax.plot(df.index, df["STO_D"], color="tab:red", linewidth=linewidth, label="%D")
    ax.axhline(80, color="grey", linewidth=0.8, linestyle="--")
    ax.axhline(20, color="grey", linewidth=0.8, linestyle="--")
    ax.fill_between([idx_min, idx_max], 20, 80, color="pink", alpha=0.2)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Stochastic", fontweight="bold", fontsize=10, loc="left")

    # 4. RSI
    ax = axes[3]
    ax.plot(df.index, df["RSI"], color="tab:purple", linewidth=linewidth)
    ax.axhline(70, color="red", linewidth=0.8, linestyle="--")
    ax.axhline(30, color="green", linewidth=0.8, linestyle="--")
    ax.set_ylim(0, 100)
    ax.set_title("RSI(14)", fontweight="bold", fontsize=10, loc="left")

    # 5. Bollinger
    ax = axes[4]
    ax.plot(df.index, df["Close"], color="black", linewidth=linewidth)
    ax.plot(df.index, df["BB_UPPER"], color="tab:red", linewidth=1, alpha=0.7)
    ax.plot(df.index, df["BB_MID"], color="tab:blue", linewidth=1, alpha=0.7)
    ax.plot(df.index, df["BB_LOWER"], color="tab:green", linewidth=1, alpha=0.7)
    ax.fill_between(df.index, df["BB_LOWER"], df["BB_UPPER"], color="tab:blue", alpha=0.08)
    ax.set_title("Bollinger Bands(20, 2σ)", fontweight="bold", fontsize=10, loc="left")

    fig.tight_layout()
    return fig
