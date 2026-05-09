"""Technical indicators on OHLCV DataFrames.

Functions are pure: they take a price DataFrame (with at minimum a Close column,
plus High/Low/Volume where relevant) and return new columns or values.

Phase 2 ports hydra's `add_return_features` / `add_technical_indicators` from
/Users/jhammant/dev/hydra-trading/src/hydra/features/market_features.py and adds
RSI, Bollinger, ATR, OBV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Phase 1 — kept for the modernized version of the original three indicators
# (MACD, Stochastic, Price/Volume). Phase 2 layers more on top.
# ---------------------------------------------------------------------------

def macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    out = df.copy()
    fast_ema = out["Close"].ewm(span=fast, adjust=False).mean()
    slow_ema = out["Close"].ewm(span=slow, adjust=False).mean()
    out["MACD"] = fast_ema - slow_ema
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=signal, adjust=False).mean()
    out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]
    return out


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> pd.DataFrame:
    out = df.copy()
    low_min = out["Low"].rolling(k).min()
    high_max = out["High"].rolling(k).max()
    out["STO_K"] = 100 * (out["Close"] - low_min) / (high_max - low_min)
    out["STO_D"] = out["STO_K"].rolling(d).mean()
    return out


# ---------------------------------------------------------------------------
# Phase 2 — broader indicator suite
# ---------------------------------------------------------------------------

def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))
    return out


def bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    ma = out["Close"].rolling(window).mean()
    sd = out["Close"].rolling(window).std()
    out["BB_MID"] = ma
    out["BB_UPPER"] = ma + num_std * sd
    out["BB_LOWER"] = ma - num_std * sd
    out["BB_WIDTH"] = (out["BB_UPPER"] - out["BB_LOWER"]) / ma
    out["BB_PCTB"] = (out["Close"] - out["BB_LOWER"]) / (out["BB_UPPER"] - out["BB_LOWER"])
    return out


def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    high_low = out["High"] - out["Low"]
    high_close = (out["High"] - out["Close"].shift()).abs()
    low_close = (out["Low"] - out["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    out["ATR"] = tr.ewm(alpha=1 / period, adjust=False).mean()
    return out


def obv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    direction = np.sign(out["Close"].diff()).fillna(0)
    out["OBV"] = (direction * out["Volume"]).cumsum()
    return out


# Ported from hydra: /Users/jhammant/dev/hydra-trading/src/hydra/features/market_features.py
def add_return_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["log_return"] = np.log(out["Close"] / out["Close"].shift(1))
    out["price_change_pct"] = out["Close"].pct_change() * 100
    out["rolling_vol_20"] = out["log_return"].rolling(20).std() * np.sqrt(252)
    out["rolling_vol_100"] = out["log_return"].rolling(100).std() * np.sqrt(252)
    out["rolling_mean_20"] = out["Close"].rolling(20).mean()
    out["rolling_mean_100"] = out["Close"].rolling(100).mean()
    return out


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the full default indicator stack."""
    if df.empty:
        return df
    df = macd(df)
    df = stochastic(df)
    df = rsi(df)
    df = bollinger(df)
    df = atr(df)
    df = obv(df)
    df = add_return_features(df)
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()
    return df
