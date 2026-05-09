"""Tiny unleveraged backtester for indicator-driven strategies.

Phase 4 originally proposed adapting hydra's LeveragedBacktestEngine; for LSE
equities the leveraged-futures features (funding, liquidation, margin) don't
apply, so we ride a 50-line equity-only backtester that fits on one page.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    name: str
    total_return_pct: float
    buy_hold_return_pct: float
    num_trades: int
    win_rate_pct: float
    sharpe: float
    max_drawdown_pct: float


def _sharpe(returns: pd.Series) -> float:
    if returns.std() == 0 or returns.empty:
        return 0.0
    return float(np.sqrt(252) * returns.mean() / returns.std())


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min() * 100)


def _run(df: pd.DataFrame, signals: pd.Series, name: str) -> BacktestResult:
    """signals: bool series — True = hold position next bar; False = flat.

    Uses next-bar fill: a True at row t puts you in for the return from t to t+1.
    """
    rets = df["Close"].pct_change().fillna(0.0)
    pos = signals.shift(1).fillna(False).astype(bool)
    strat_rets = rets * pos
    equity = (1 + strat_rets).cumprod()

    # Count trades = number of position-onset transitions
    onsets = (pos.astype(int).diff() == 1).sum()
    wins = ((strat_rets > 0) & pos).sum()
    losses = ((strat_rets < 0) & pos).sum()
    win_rate = (wins / max(wins + losses, 1)) * 100

    return BacktestResult(
        name=name,
        total_return_pct=float((equity.iloc[-1] - 1) * 100),
        buy_hold_return_pct=float(((df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1) * 100),
        num_trades=int(onsets),
        win_rate_pct=float(win_rate),
        sharpe=_sharpe(strat_rets),
        max_drawdown_pct=_max_dd(equity),
    )


def macd_crossover(df: pd.DataFrame) -> BacktestResult:
    sig = df["MACD"] > df["MACD_SIGNAL"]
    return _run(df, sig, "MACD crossover")


def rsi_mean_reversion(df: pd.DataFrame, low: float = 30, high: float = 70) -> BacktestResult:
    rsi = df["RSI"]
    state = pd.Series(False, index=df.index)
    holding = False
    for i, v in enumerate(rsi):
        if not holding and v < low:
            holding = True
        elif holding and v > high:
            holding = False
        state.iloc[i] = holding
    return _run(df, state, "RSI mean-reversion")


def stoch_mean_reversion(df: pd.DataFrame, low: float = 20, high: float = 80) -> BacktestResult:
    k = df["STO_K"]
    state = pd.Series(False, index=df.index)
    holding = False
    for i, v in enumerate(k):
        if not holding and v < low:
            holding = True
        elif holding and v > high:
            holding = False
        state.iloc[i] = holding
    return _run(df, state, "Stochastic mean-reversion")


def run_all(df: pd.DataFrame) -> list[BacktestResult]:
    if df.empty or len(df) < 60:
        return []
    return [
        macd_crossover(df),
        rsi_mean_reversion(df),
        stoch_mean_reversion(df),
    ]
