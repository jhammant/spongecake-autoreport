"""HTTP client for the Mac-side chronos-bridge."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import requests

log = logging.getLogger(__name__)


def forecast(prices: pd.Series, horizon_days: int, cfg=None):
    from . import Forecast

    if not cfg or not cfg.chronos_bridge_url:
        raise RuntimeError("CHRONOS_BRIDGE_URL not set")
    url = cfg.chronos_bridge_url.rstrip("/") + "/forecast"
    headers = {}
    if cfg.chronos_bridge_token:
        headers["Authorization"] = f"Bearer {cfg.chronos_bridge_token}"

    resp = requests.post(
        url,
        json={
            "prices": [float(x) for x in prices.dropna().tolist()],
            "horizon": horizon_days,
            "num_samples": 100,
            "model": cfg.chronos_model,
        },
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()

    samples = (
        np.asarray(payload["forecast_samples"]) if payload.get("forecast_samples") else None
    )
    last = float(prices.iloc[-1])
    if samples is not None:
        median = np.percentile(samples, 50, axis=0)
        p5 = np.percentile(samples, 5, axis=0)
        p95 = np.percentile(samples, 95, axis=0)
    else:
        median = np.full(horizon_days, last * (1 + payload["median"]))
        p5 = np.full(horizon_days, last * (1 + payload["downside_5pct"]))
        p95 = np.full(horizon_days, last * (1 + payload["upside_95pct"]))

    return Forecast(
        method="chronos-remote",
        horizon_days=horizon_days,
        median=median,
        p5=p5,
        p95=p95,
        expected_return_pct=float(payload["expected_return"] * 100),
        samples=samples,
    )
