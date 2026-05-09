"""High-level orchestration: take a watchlist, produce a dated report dir.

Output layout:
    reports/
      YYYY-MM-DD/
        report.pdf
        index.html              (interactive)
        AAA.html                (per-stock interactive)
        BBB.html
        ...
        signals.json            (snapshot for diff)
        charts/AAA_<date>.png   (matplotlib raster fed into PDF)

State (kept across runs):
    state/
      signals/YYYY-MM-DD.json
      commentary/<TIDM>/<YYYY-MM-DD>.json
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from . import __version__
from . import backtest as bt
from . import charts as ch
from . import commentary as commentary_mod
from . import diff as diff_mod
from . import forecast as forecast_mod
from . import fundamentals as fund_mod
from . import indicators as ind
from . import prices as prices_mod
from . import signals as sig_mod
from . import watchlist as wl
from .config import Config
from .notifiers import discord_notify, pushover_notify
from .render import html as html_render
from .render import pdf as pdf_render

log = logging.getLogger(__name__)


def run_report(
    *,
    watchlist_path: Path,
    output_root: Path,
    state_root: Path,
    cfg: Config,
    tickers_filter: list[str] | None = None,
    horizon_days: int = 30,
    do_diff: bool = True,
    notify: list[str] | None = None,
    history_days: int = 365,
) -> Path:
    """Run end-to-end. Returns the dated report directory."""
    notify = notify or []
    run_dt = datetime.now(timezone.utc).astimezone()
    run_date = run_dt.date()
    date_dir = output_root / run_date.isoformat()
    charts_dir = date_dir / "charts"
    date_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    state_root.mkdir(parents=True, exist_ok=True)

    stocks = wl.load(watchlist_path)
    if tickers_filter:
        wanted = {t.upper() for t in tickers_filter}
        stocks = [s for s in stocks if s.tidm.upper() in wanted]

    log.info("running report for %d stocks; output=%s", len(stocks), date_dir)

    pages: list[dict] = []
    today_signals_payload: dict = {"date": run_date.isoformat(), "stocks": {}}

    prior = diff_mod.latest_prior(state_root, run_date) if do_diff else None
    prior_stocks = (prior or {}).get("stocks", {}) if prior else {}

    for s in stocks:
        log.info("processing %s (%s)", s.tidm, s.name)
        df = prices_mod.fetch(s.tidm, period_days=history_days)
        if df.empty:
            log.warning("skipping %s: no price data", s.tidm)
            continue

        df = ind.enrich(df)
        ssig = sig_mod.extract(s.tidm, df)
        fund = fund_mod.fetch(s.tidm)

        # Forecast
        try:
            fc = forecast_mod.forecast(
                df["Close"], horizon_days=horizon_days, mode=cfg.forecast_mode, cfg=cfg
            )
        except Exception as exc:
            log.warning("forecast failed for %s: %s", s.tidm, exc)
            from .forecast import monte_carlo as mc

            fc = mc.forecast(df["Close"], horizon_days=horizon_days)
            fc.note = f"MC (forecast failed: {exc})"

        # Render matplotlib chart for the PDF
        fig_title = f"{s.tidm} ({s.name}) — last close {df['Close'].iloc[-1]:,.2f}"
        fig = ch.technicals_figure(df, fig_title)
        chart_png = charts_dir / f"{s.tidm}.png"
        fig.savefig(chart_png, dpi=110, bbox_inches="tight")
        # Free matplotlib memory
        import matplotlib.pyplot as _plt

        _plt.close(fig)

        # Backtests
        backtests = bt.run_all(df)

        # Commentary
        com = commentary_mod.get(
            tidm=s.tidm,
            name=s.name,
            sector=s.sector,
            signals=ssig.items,
            trend_score=ssig.trend_score,
            summary_text=fund.summary.to_string(index=False) if not fund.summary.empty else "",
            balance_text=(fund.balance.iloc[:, :3].to_string(index=False)
                          if not fund.balance.empty else ""),
            income_text=(fund.income.iloc[:, :3].to_string(index=False)
                         if not fund.income.empty else ""),
            state_dir=state_root,
            cfg=cfg,
            run_date=run_date,
        )

        # Diff
        prev_stock = prior_stocks.get(s.tidm)
        cur_set = set(ssig.items)
        prev_set = set(prev_stock.get("signals", [])) if prev_stock else set()
        diff_new = sorted(cur_set - prev_set)
        diff_gone = sorted(prev_set - cur_set)

        # Track for snapshot
        today_signals_payload["stocks"][s.tidm] = {
            "name": s.name,
            "sector": s.sector,
            "trend_score": ssig.trend_score,
            "signals": ssig.items,
            "flag": com.flag,
        }

        pages.append(
            {
                "tidm": s.tidm,
                "name": s.name,
                "sector": s.sector,
                "current_price": float(df["Close"].iloc[-1]),
                "chart_path": str(chart_png),
                "df": df,
                "signals": ssig.items,
                "trend_score": ssig.trend_score,
                "forecast_note": fc.note or fc.method,
                "fc_median": fc.median,
                "fc_p5": fc.p5,
                "fc_p95": fc.p95,
                "fc_horizon": fc.horizon_days,
                "commentary": com,
                "flag": com.flag,
                "summary_df": fund.summary,
                "calcs_df": fund.calcs,
                "income_df": fund.income,
                "balance_df": fund.balance,
                "backtests": backtests,
                "diff_new": diff_new,
                "diff_gone": diff_gone,
            }
        )

    # Diff summary for TOC + notifiers
    diff_summary = None
    if do_diff and prior is not None:
        new_pairs: list[tuple[str, str]] = []
        gone_pairs: list[tuple[str, str]] = []
        for p in pages:
            for s in p.get("diff_new", []):
                new_pairs.append((p["tidm"], s))
            for s in p.get("diff_gone", []):
                gone_pairs.append((p["tidm"], s))
        diff_summary = {
            "prior_date": prior.get("date", ""),
            "new": new_pairs,
            "gone": gone_pairs,
        }

    # Persist signals snapshot
    diff_mod.snapshot(state_root, run_date, today_signals_payload)

    # Write outputs
    pdf_path = date_dir / "report.pdf"
    pdf_render.render(out_path=pdf_path, run_dt=run_dt, pages=pages, diff_summary=diff_summary)
    html_render.render(out_dir=date_dir, run_dt=run_dt, pages=pages, diff_summary=diff_summary)

    # Run metadata
    meta = {
        "version": __version__,
        "generated_at": run_dt.isoformat(),
        "stock_count": len(pages),
        "forecast_mode": cfg.forecast_mode,
        "diff_against": (prior or {}).get("date") if prior else None,
        "notifiers": notify,
    }
    (date_dir / "run.json").write_text(json.dumps(meta, indent=2))

    # Prune old
    _prune_old(output_root, cfg.keep_reports_days, current=run_date)

    # Notify
    _fire_notifiers(notify, cfg, pages, diff_summary, run_date, date_dir)

    log.info("report complete: %s", pdf_path)
    return date_dir


def _prune_old(output_root: Path, keep_days: int, current: date) -> None:
    if keep_days <= 0:
        return
    cutoff = current - timedelta(days=keep_days)
    for d in output_root.iterdir():
        if not d.is_dir():
            continue
        try:
            run_d = date.fromisoformat(d.name)
        except ValueError:
            continue
        if run_d < cutoff:
            log.info("pruning old report dir: %s", d)
            shutil.rmtree(d, ignore_errors=True)


def _fire_notifiers(notify, cfg, pages, diff_summary, run_date, date_dir):
    if not notify:
        return
    top_movers = sorted(
        ((p["tidm"], p.get("trend_score", 0.0)) for p in pages),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5]
    new_signals = (
        [(t, s) for (t, s) in (diff_summary or {}).get("new", [])][:8]
        if diff_summary
        else []
    )
    summary = f"{len(pages)} stocks · forecast={cfg.forecast_mode}"
    if diff_summary:
        summary += (
            f" · {len((diff_summary or {}).get('new', []))} new signals"
            f" / {len((diff_summary or {}).get('gone', []))} gone"
        )
    viewer_url = (
        f"{cfg.viewer_base_url.rstrip('/')}/r/{run_date.isoformat()}/index.html"
        if cfg.viewer_base_url
        else ""
    )
    title = f"Spongecake — {run_date.isoformat()}"

    if "discord" in notify and cfg.discord_webhook_url:
        discord_notify(
            webhook_url=cfg.discord_webhook_url,
            title=title,
            summary=summary,
            top_movers=top_movers,
            new_signals=new_signals,
            viewer_url=viewer_url,
        )

    if "pushover" in notify and cfg.pushover_user_key and cfg.pushover_app_token:
        priority = 1 if any(
            p.get("flag") == "red" for p in pages
        ) else 0
        pushover_notify(
            user_key=cfg.pushover_user_key,
            app_token=cfg.pushover_app_token,
            title=title,
            message=summary,
            viewer_url=viewer_url,
            priority=priority,
        )
