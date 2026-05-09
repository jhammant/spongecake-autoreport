"""Bootstrap Monte Carlo forecast over historical log returns.

No external deps beyond numpy/pandas. Always available; the default forecast
method.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def forecast(prices: pd.Series, horizon_days: int = 30, num_paths: int = 1000,
             rng_seed: int | None = None):
    from . import Forecast  # local import to avoid circular

    rng = np.random.default_rng(rng_seed)
    log_returns = np.log(prices / prices.shift(1)).dropna().to_numpy()
    if log_returns.size < 5:
        # Not enough history. Return a flat forecast.
        last = float(prices.iloc[-1])
        flat = np.full(horizon_days, last)
        return Forecast(
            method="mc",
            horizon_days=horizon_days,
            median=flat,
            p5=flat,
            p95=flat,
            expected_return_pct=0.0,
            note="MC (insufficient history)",
            samples=None,
        )

    last = float(prices.iloc[-1])
    sampled = rng.choice(log_returns, size=(num_paths, horizon_days), replace=True)
    cumulative = np.cumsum(sampled, axis=1)
    paths = last * np.exp(cumulative)  # shape: (num_paths, horizon)

    median = np.percentile(paths, 50, axis=0)
    p5 = np.percentile(paths, 5, axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    expected = (median[-1] - last) / last * 100.0

    return Forecast(
        method="mc",
        horizon_days=horizon_days,
        median=median,
        p5=p5,
        p95=p95,
        expected_return_pct=float(expected),
        samples=paths,
    )
