"""Per-stock signal extraction from an enriched OHLCV+indicators dataframe.

Output is a list of human-readable strings + a composite trend score in [-1, 1].
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StockSignals:
    tidm: str
    items: list[str]
    trend_score: float  # -1 (bearish) .. +1 (bullish)


def _crossed_recently(a: pd.Series, b: pd.Series, lookback: int = 5) -> tuple[bool, int, str]:
    """Return (crossed, days_ago, direction) over the last `lookback` rows."""
    diff = (a - b).dropna()
    if diff.size < 2:
        return False, 0, ""
    sign = np.sign(diff)
    for i in range(1, min(lookback, len(sign))):
        if sign.iloc[-i - 1] != sign.iloc[-i] and sign.iloc[-i] != 0:
            direction = "bullish" if sign.iloc[-i] > 0 else "bearish"
            return True, i, direction
    return False, 0, ""


def extract(tidm: str, df: pd.DataFrame) -> StockSignals:
    if df.empty or len(df) < 50:
        return StockSignals(tidm=tidm, items=["insufficient history"], trend_score=0.0)

    items: list[str] = []
    last = df.iloc[-1]

    # MACD cross
    crossed, days_ago, direction = _crossed_recently(df["MACD"], df["MACD_SIGNAL"])
    if crossed:
        items.append(f"MACD {direction} cross {days_ago} day{'s' if days_ago != 1 else ''} ago")

    # Stochastic
    if last["STO_K"] < 20:
        items.append(f"Stochastic oversold ({last['STO_K']:.0f})")
    elif last["STO_K"] > 80:
        items.append(f"Stochastic overbought ({last['STO_K']:.0f})")

    # RSI
    if last["RSI"] < 30:
        items.append(f"RSI oversold ({last['RSI']:.0f})")
    elif last["RSI"] > 70:
        items.append(f"RSI overbought ({last['RSI']:.0f})")

    # 52-week proximity (last ~252 trading days; use what we have)
    window = df.tail(252)
    high_52 = window["Close"].max()
    low_52 = window["Close"].min()
    last_close = float(last["Close"])
    if last_close >= 0.96 * high_52:
        items.append(f"Within {(high_52 - last_close) / high_52 * 100:.1f}% of 52w high")
    if last_close <= 1.04 * low_52:
        items.append(f"Within {(last_close - low_52) / low_52 * 100:.1f}% of 52w low")

    # Bollinger squeeze
    bbw = float(last.get("BB_WIDTH", np.nan))
    if not np.isnan(bbw) and bbw < 0.05:
        items.append(f"Bollinger squeeze (BBW {bbw:.3f})")

    # SMA trend
    if "SMA_20" in df and "SMA_50" in df:
        if last["SMA_20"] > last["SMA_50"]:
            items.append("Price above SMA(20) > SMA(50)")
        elif last["SMA_20"] < last["SMA_50"]:
            items.append("Price below SMA(20) < SMA(50)")

    if not items:
        items.append("no notable signals")

    score = trend_score(df)
    return StockSignals(tidm=tidm, items=items, trend_score=score)


def trend_score(df: pd.DataFrame) -> float:
    """Composite -1..1 score from MACD-hist, RSI distance from 50, %B, 20d return."""
    last = df.iloc[-1]
    parts: list[float] = []

    macd_hist = float(last.get("MACD_HIST", 0.0))
    if "MACD" in df:
        std = df["MACD_HIST"].std()
        if std and not np.isnan(std):
            parts.append(np.tanh(macd_hist / (2 * std)))

    rsi_val = float(last.get("RSI", 50.0))
    if not np.isnan(rsi_val):
        parts.append((rsi_val - 50) / 50)

    pctb = float(last.get("BB_PCTB", 0.5))
    if not np.isnan(pctb):
        parts.append(np.clip((pctb - 0.5) * 2, -1, 1))

    if len(df) >= 21:
        r20 = (df["Close"].iloc[-1] - df["Close"].iloc[-21]) / df["Close"].iloc[-21]
        parts.append(np.tanh(r20 * 5))

    if not parts:
        return 0.0
    return float(np.clip(sum(parts) / len(parts), -1, 1))
