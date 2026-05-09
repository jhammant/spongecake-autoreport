from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def fetch(tidm: str, period_days: int = 365) -> pd.DataFrame:
    """OHLCV for an LSE TIDM via yfinance.

    Returns a DataFrame indexed by Date with columns Open/High/Low/Close/Volume.
    Empty DataFrame on failure or empty response (caller decides whether to skip).
    """
    symbol = f"{tidm}.L"
    end = datetime.utcnow().date()
    start = end - timedelta(days=period_days)
    try:
        df = yf.download(
            symbol,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=False,
            actions=False,
        )
    except Exception as exc:  # yfinance occasionally raises on transient JSON errors
        log.warning("yfinance fetch failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    if df is None or df.empty:
        log.warning("yfinance returned no rows for %s", symbol)
        return pd.DataFrame()

    # yfinance returns a MultiIndex when given a single symbol in newer versions.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index.name = "Date"
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
