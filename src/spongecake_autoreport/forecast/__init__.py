"""Forecast router: mc | chronos-local | chronos-remote.

Falls back to MC silently on import or HTTP failure; the caller's report caption
records which mode actually produced the numbers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import monte_carlo

log = logging.getLogger(__name__)


@dataclass
class Forecast:
    method: str  # "mc" | "chronos-local" | "chronos-remote"
    horizon_days: int
    median: np.ndarray  # length = horizon
    p5: np.ndarray
    p95: np.ndarray
    expected_return_pct: float
    note: str = ""  # e.g. "MC (chronos-remote unreachable)"
    samples: np.ndarray | None = field(default=None, repr=False)


def forecast(prices: pd.Series, horizon_days: int = 30, mode: str = "mc",
             cfg=None) -> Forecast:
    """Resolve a forecast for a price series.

    `mode` picks the source. On any failure we fall through to Monte Carlo
    and mark the `.note` field so the report caption can show the user that
    a fallback happened.
    """
    series = prices.dropna().astype(float)
    if mode == "chronos-local":
        try:
            from . import chronos_local
            return chronos_local.forecast(series, horizon_days, cfg)
        except Exception as exc:
            log.warning("chronos-local failed; falling back to MC: %s", exc)
            f = monte_carlo.forecast(series, horizon_days)
            f.note = f"MC (chronos-local unavailable: {exc})"
            return f

    if mode == "chronos-remote":
        try:
            from . import chronos_client
            return chronos_client.forecast(series, horizon_days, cfg)
        except Exception as exc:
            log.warning("chronos-remote failed; falling back to MC: %s", exc)
            f = monte_carlo.forecast(series, horizon_days)
            f.note = f"MC (chronos-remote unreachable: {exc})"
            return f

    return monte_carlo.forecast(series, horizon_days)
