"""Diff today's signals + trend scores against the most recent prior run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class StockDiff:
    tidm: str
    new_signals: list[str]
    gone_signals: list[str]
    trend_score_change: float | None  # None if no prior


def snapshot(state_dir: Path, run_date: date, payload: dict) -> Path:
    p = state_dir / "signals" / f"{run_date.isoformat()}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))
    return p


def latest_prior(state_dir: Path, run_date: date) -> dict | None:
    base = state_dir / "signals"
    if not base.exists():
        return None
    files = sorted(base.glob("*.json"))
    files = [f for f in files if f.stem < run_date.isoformat()]
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text())
    except Exception:
        return None


def compute(today: dict, prior: dict | None) -> dict[str, StockDiff]:
    out: dict[str, StockDiff] = {}
    prior_map: dict[str, dict] = (prior or {}).get("stocks", {}) if prior else {}
    for tidm, current in today.get("stocks", {}).items():
        prev = prior_map.get(tidm)
        cur_set = set(current.get("signals", []))
        prev_set = set(prev.get("signals", [])) if prev else set()
        new_signals = sorted(cur_set - prev_set)
        gone_signals = sorted(prev_set - cur_set)
        if prev:
            change = current.get("trend_score", 0) - prev.get("trend_score", 0)
        else:
            change = None
        out[tidm] = StockDiff(
            tidm=tidm,
            new_signals=new_signals,
            gone_signals=gone_signals,
            trend_score_change=change,
        )
    return out
