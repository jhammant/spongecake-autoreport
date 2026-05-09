"""Local Chronos forecast — wraps the vendored ChronosForecaster.

Imports torch + chronos lazily so the module load itself doesn't fail when the
optional `chronos` extra isn't installed.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def forecast(prices: pd.Series, horizon_days: int, cfg=None):
    from ._chronos_vendor import ChronosForecaster
    from . import Forecast

    model = (cfg.chronos_model if cfg else None) or "amazon/chronos-t5-tiny"
    fc = ChronosForecaster(
        horizon_steps=horizon_days, model_name=model, num_samples=20
    )
    result = fc.forecast_from_series(prices.to_numpy(), prediction_length=horizon_days)

    last = float(prices.iloc[-1])
    samples = result.forecast_samples  # (num_samples, horizon)
    if samples is None:
        # ChronosForecaster gave us only summary stats; synthesize a flat band.
        median = np.full(horizon_days, last * (1 + result.median))
        p5 = np.full(horizon_days, last * (1 + result.downside_5pct))
        p95 = np.full(horizon_days, last * (1 + result.upside_95pct))
    else:
        median = np.percentile(samples, 50, axis=0)
        p5 = np.percentile(samples, 5, axis=0)
        p95 = np.percentile(samples, 95, axis=0)

    return Forecast(
        method="chronos-local",
        horizon_days=horizon_days,
        median=median,
        p5=p5,
        p95=p95,
        expected_return_pct=float(result.expected_return * 100),
        samples=samples,
    )
