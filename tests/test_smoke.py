"""Smoke tests that don't hit the network. Mocks yfinance.

Validates the package imports cleanly, the indicator stack runs, the MC
forecaster produces sane output, signals extraction works, and the diff/cache
plumbing is wired up.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _fake_ohlcv(n: int = 250) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.015, n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    vol = rng.integers(50_000, 500_000, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_package_imports():
    import spongecake_autoreport
    from spongecake_autoreport import (
        cli, config, watchlist, prices, fundamentals, indicators,
        signals, charts, report, backtest, commentary, diff, viewer,
    )
    from spongecake_autoreport.forecast import monte_carlo  # noqa: F401
    from spongecake_autoreport.notifiers import discord, pushover  # noqa: F401
    from spongecake_autoreport.render import pdf, html  # noqa: F401
    assert spongecake_autoreport.__version__


def test_indicator_enrich_runs():
    from spongecake_autoreport import indicators as ind

    df = _fake_ohlcv()
    out = ind.enrich(df)
    for col in ["MACD", "MACD_SIGNAL", "STO_K", "RSI", "BB_UPPER", "BB_LOWER", "ATR", "OBV"]:
        assert col in out.columns
    assert not out["MACD"].iloc[-1] != out["MACD"].iloc[-1]  # not NaN-final


def test_signals_returns_items_and_score():
    from spongecake_autoreport import indicators as ind, signals as sig

    df = ind.enrich(_fake_ohlcv())
    s = sig.extract("FAKE", df)
    assert s.tidm == "FAKE"
    assert s.items
    assert -1.0 <= s.trend_score <= 1.0


def test_monte_carlo_forecast_shapes():
    from spongecake_autoreport.forecast import monte_carlo as mc

    df = _fake_ohlcv()
    fc = mc.forecast(df["Close"], horizon_days=30)
    assert fc.method == "mc"
    assert len(fc.median) == 30
    assert (fc.p5 <= fc.median).all()
    assert (fc.median <= fc.p95).all()


def test_forecast_router_falls_back_to_mc():
    from spongecake_autoreport.config import Config
    from spongecake_autoreport import forecast as f

    df = _fake_ohlcv()
    cfg = Config(forecast_mode="chronos-remote", chronos_bridge_url="http://does.not.exist:1")
    fc = f.forecast(df["Close"], horizon_days=10, mode="chronos-remote", cfg=cfg)
    assert fc.method == "mc"
    assert "unreachable" in fc.note or "MC" in fc.note


def test_watchlist_load(tmp_path: Path):
    from spongecake_autoreport import watchlist as wl

    p = tmp_path / "wl.yaml"
    p.write_text(
        "- tidm: AAA\n  name: Alpha\n  sector: Tech\n  description: x\n"
        "- tidm: BBB\n  name: Beta\n"
    )
    stocks = wl.load(p)
    assert len(stocks) == 2
    assert stocks[0].tidm == "AAA"
    assert stocks[0].yfinance_symbol == "AAA.L"


def test_watchlist_migrator(tmp_path: Path):
    from spongecake_autoreport import watchlist as wl

    pipe = tmp_path / "watchlist"
    pipe.write_text("# header\nGAW|Games Workshop|Miniatures\nFDEV|Frontier|Games\n")
    out = tmp_path / "out.yaml"
    n = wl.migrate_pipe_file(pipe, out)
    assert n == 2
    stocks = wl.load(out)
    assert {s.tidm for s in stocks} == {"GAW", "FDEV"}


def test_diff_snapshot_and_compute(tmp_path: Path):
    from spongecake_autoreport import diff

    today = {
        "date": "2026-05-09",
        "stocks": {"AAA": {"signals": ["x", "y"], "trend_score": 0.5}},
    }
    diff.snapshot(tmp_path, date(2026, 5, 9), today)
    prior = {
        "date": "2026-05-08",
        "stocks": {"AAA": {"signals": ["x"], "trend_score": 0.3}},
    }
    diff.snapshot(tmp_path, date(2026, 5, 8), prior)
    found_prior = diff.latest_prior(tmp_path, date(2026, 5, 9))
    assert found_prior["date"] == "2026-05-08"

    out = diff.compute(today, prior)
    assert out["AAA"].new_signals == ["y"]
    assert out["AAA"].gone_signals == []
    assert pytest.approx(out["AAA"].trend_score_change, rel=1e-9) == 0.2


def test_commentary_disabled_path():
    from spongecake_autoreport.commentary import Commentary, get
    from spongecake_autoreport.config import Config
    from pathlib import Path
    import tempfile

    cfg = Config()  # no API key
    with tempfile.TemporaryDirectory() as tmp:
        c = get(
            tidm="AAA",
            name="Alpha",
            sector="Tech",
            signals=["x"],
            trend_score=0.0,
            summary_text="",
            balance_text="",
            income_text="",
            state_dir=Path(tmp),
            cfg=cfg,
        )
    assert isinstance(c, Commentary)
    assert "disabled" in c.headline


def test_backtests_run():
    from spongecake_autoreport import backtest as bt, indicators as ind

    df = ind.enrich(_fake_ohlcv())
    results = bt.run_all(df)
    assert len(results) == 3
    for r in results:
        assert isinstance(r.total_return_pct, float)
        assert isinstance(r.sharpe, float)
