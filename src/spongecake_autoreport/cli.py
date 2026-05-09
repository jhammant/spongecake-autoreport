"""Command-line entry: `spongecake-report`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config
from .report import run_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Spongecake LSE autoreport")
    ap.add_argument("--watchlist", default="watchlist.yaml")
    ap.add_argument("--output", default="./reports", help="reports root directory")
    ap.add_argument("--state", default="./state", help="state directory (diff + commentary cache)")
    ap.add_argument(
        "--tickers", default="",
        help="comma-separated TIDMs to process (default: full watchlist)",
    )
    ap.add_argument(
        "--horizon", type=int, default=30, help="forecast horizon in trading days"
    )
    ap.add_argument(
        "--history-days", type=int, default=365,
        help="historical price window to fetch and chart",
    )
    ap.add_argument(
        "--forecast", default=None,
        help="override FORECAST_MODE: mc | chronos-local | chronos-remote",
    )
    ap.add_argument(
        "--notify", default="",
        help="comma-separated notifiers: discord,pushover",
    )
    ap.add_argument("--diff", action="store_true", default=True, help="enable diff vs prior run")
    ap.add_argument("--no-diff", dest="diff", action="store_false")
    ap.add_argument("--cheap", action="store_true", help="use the cheaper LLM model")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    # Silence yfinance/urllib3 chatter unless verbose
    if not args.verbose:
        logging.getLogger("yfinance").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)

    cfg = Config.from_env()
    if args.forecast:
        cfg.forecast_mode = args.forecast
    if args.cheap:
        cfg.anthropic_model = cfg.anthropic_cheap_model

    notifiers = [s.strip() for s in args.notify.split(",") if s.strip()]
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    out_dir = run_report(
        watchlist_path=Path(args.watchlist),
        output_root=Path(args.output),
        state_root=Path(args.state),
        cfg=cfg,
        tickers_filter=tickers or None,
        horizon_days=args.horizon,
        history_days=args.history_days,
        do_diff=args.diff,
        notify=notifiers,
    )
    print(f"Report generated: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
