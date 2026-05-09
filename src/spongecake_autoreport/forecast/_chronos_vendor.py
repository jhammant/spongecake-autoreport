"""Vendored from /Users/jhammant/dev/hydra-trading/src/hydra/models/chronos/forecaster.py.

Strips hydra-specific logging/settings imports so this works inside the
spongecake-autoreport package as a self-contained module. Used by both
`chronos-local` mode on the host running the report and the optional
Mac-side `chronos_bridge.py` FastAPI service.

Requires the optional `[chronos]` extra (torch + chronos-forecasting).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import torch

from chronos import ChronosPipeline

log = logging.getLogger(__name__)


@dataclass
class ChronosForecast:
    horizon_steps: int
    expected_return: float
    downside_5pct: float
    upside_95pct: float
    median: float
    forecast_samples: Optional[np.ndarray] = None


class ChronosForecaster:
    def __init__(
        self,
        horizon_steps: int = 12,
        model_name: str = "amazon/chronos-t5-tiny",
        device: Optional[str] = None,
        num_samples: int = 20,
    ):
        self.horizon_steps = horizon_steps
        self.model_name = model_name
        self.num_samples = num_samples

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device

        self.pipeline = ChronosPipeline.from_pretrained(
            model_name,
            device_map=self.device,
            torch_dtype=torch.bfloat16 if self.device != "cpu" else torch.float32,
        )

    def forecast_from_series(
        self,
        context: np.ndarray | pd.Series | list,
        prediction_length: Optional[int] = None,
    ) -> ChronosForecast:
        if prediction_length is None:
            prediction_length = self.horizon_steps

        if isinstance(context, pd.Series):
            context = context.values
        if isinstance(context, list):
            context = np.array(context)
        context = context[~np.isnan(context)]
        if len(context) == 0:
            raise ValueError("Context series is empty after removing NaN values")

        context_tensor = torch.tensor(context, dtype=torch.float32)
        forecast = self.pipeline.predict(
            context_tensor,
            prediction_length=prediction_length,
            num_samples=self.num_samples,
        )
        forecast_samples = forecast[0].numpy()  # (num_samples, horizon)

        median = np.median(forecast_samples, axis=0)
        mean = np.mean(forecast_samples, axis=0)
        p5 = np.percentile(forecast_samples, 5, axis=0)
        p95 = np.percentile(forecast_samples, 95, axis=0)

        current = float(context[-1])
        return ChronosForecast(
            horizon_steps=prediction_length,
            expected_return=(float(mean[-1]) - current) / current,
            downside_5pct=(float(p5[-1]) - current) / current,
            upside_95pct=(float(p95[-1]) - current) / current,
            median=(float(median[-1]) - current) / current,
            forecast_samples=forecast_samples,
        )

    def forecast_from_df(
        self,
        df: pd.DataFrame,
        target_col: str = "Close",
        prediction_length: Optional[int] = None,
    ) -> ChronosForecast:
        return self.forecast_from_series(df[target_col], prediction_length)
