"""Mac-side FastAPI service exposing chronos-t5-small over HTTP.

Phase 3: cloud (running spongecake-report) calls this bridge over tailscale
when FORECAST_MODE=chronos-remote. Bearer token mandatory.

Run via launchd (deploy/launchd/io.hammant.chronos-bridge.plist).
"""

from __future__ import annotations

import argparse
import logging
import os

import numpy as np

log = logging.getLogger(__name__)


def main() -> None:
    """Entry point — installs FastAPI app and runs uvicorn."""
    try:
        from fastapi import FastAPI, Header, HTTPException
        from pydantic import BaseModel
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "chronos-bridge requires the [bridge] extra: pip install '.[bridge,chronos]'"
        ) from exc

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5003)
    ap.add_argument(
        "--default-model", default=os.environ.get("CHRONOS_MODEL", "amazon/chronos-t5-small")
    )
    args = ap.parse_args()

    expected_token = os.environ.get("CHRONOS_BRIDGE_TOKEN", "")
    if not expected_token:
        log.warning("CHRONOS_BRIDGE_TOKEN not set — bridge will reject all requests")

    # Load model lazily on first request (avoids startup cost / failure here).
    forecaster = {"model_name": args.default_model, "instance": None}

    class ForecastRequest(BaseModel):
        prices: list[float]
        horizon: int = 30
        num_samples: int = 100
        model: str | None = None

    class ForecastResponse(BaseModel):
        horizon_steps: int
        expected_return: float
        downside_5pct: float
        upside_95pct: float
        median: float
        forecast_samples: list[list[float]] | None = None

    app = FastAPI(title="spongecake chronos bridge")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "model": forecaster["model_name"]}

    @app.post("/forecast", response_model=ForecastResponse)
    def forecast(req: ForecastRequest, authorization: str | None = Header(default=None)):
        if not expected_token:
            raise HTTPException(status_code=503, detail="bridge token not configured")
        if authorization != f"Bearer {expected_token}":
            raise HTTPException(status_code=401, detail="bad token")

        target_model = req.model or forecaster["model_name"]
        if forecaster["instance"] is None or forecaster["model_name"] != target_model:
            from .forecast._chronos_vendor import ChronosForecaster
            forecaster["instance"] = ChronosForecaster(
                horizon_steps=req.horizon, model_name=target_model, num_samples=req.num_samples
            )
            forecaster["model_name"] = target_model

        prices_arr = np.asarray(req.prices, dtype=float)
        result = forecaster["instance"].forecast_from_series(
            prices_arr, prediction_length=req.horizon
        )

        samples = result.forecast_samples
        return ForecastResponse(
            horizon_steps=result.horizon_steps,
            expected_return=float(result.expected_return),
            downside_5pct=float(result.downside_5pct),
            upside_95pct=float(result.upside_95pct),
            median=float(result.median),
            forecast_samples=samples.tolist() if samples is not None else None,
        )

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
