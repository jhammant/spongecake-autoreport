# Spongecake Autoreport

Daily research report for an LSE-stock watchlist: technical charts, indicators,
30-day forecasts, balance/income tables, LLM commentary, and a diff against
yesterday — rendered as both a PDF and an interactive HTML page.

This is a fork of [chris-j-akers/spongecake-autoreport][upstream]
(last upstream commit June 2022) modernized for 2026:
- the `pandas_datareader` Yahoo backend (dead since Yahoo killed the endpoint)
  is replaced with `yfinance`;
- Investors-Chronicle scraping (rotted) is replaced with `yfinance` fundamentals;
- the package is restructured under `src/spongecake_autoreport/` with a
  `spongecake-report` console entry, `pyproject.toml`, and a smoke test;
- the report grew an indicator suite (RSI, Bollinger, ATR, OBV…),
  signal extraction, a composite trend score, per-strategy backtests,
  Plotly interactive HTML, day-over-day diff, Discord/Pushover notifiers,
  and a viewer Flask app.
- Forecasting can run as Monte Carlo locally, Chronos locally (on-host), or
  routed to a Mac-side bridge over tailscale.

[upstream]: https://github.com/chris-j-akers/spongecake-autoreport

## Quick start (local Mac)

```bash
# Clone your fork
git clone git@github.com:jhammant/spongecake-autoreport.git
cd spongecake-autoreport

# System libs (WeasyPrint runtime)
brew install cairo pango gdk-pixbuf libffi

# Python env (uv recommended; pip works too)
uv venv
uv pip install -e ".[dev]"

# Edit watchlist.yaml as needed, then:
spongecake-report --watchlist watchlist.yaml --tickers GAW --output ./reports
```

The report directory is `./reports/<YYYY-MM-DD>/` with `report.pdf`,
`index.html`, per-stock `.html` files, and `signals.json`.

## Configuration (env vars)

Create `.env` (or set in your shell / systemd EnvironmentFile):

```bash
# Forecasting
FORECAST_MODE=mc                  # mc | chronos-local | chronos-remote
CHRONOS_MODEL=amazon/chronos-t5-tiny
CHRONOS_BRIDGE_URL=http://your-mac-tailscale:5003
CHRONOS_BRIDGE_TOKEN=...

# LLM commentary (optional — gracefully skipped if unset)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# Notifiers (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
PUSHOVER_USER_KEY=...
PUSHOVER_APP_TOKEN=...

# Viewer
VIEWER_AUTH=user:strongpass        # required when bound publicly
VIEWER_BASE_URL=https://spongecake.hammant.io
```

## CLI reference

```bash
spongecake-report \
  --watchlist watchlist.yaml \
  --output ./reports \
  --state ./state \
  --tickers GAW,FDEV \              # optional — filter to subset
  --horizon 30 \                    # forecast horizon in trading days
  --history-days 365 \              # historical window per chart
  --forecast chronos-remote \       # override FORECAST_MODE
  --notify discord,pushover \       # fire notifiers on success
  --diff                            # diff against latest prior run (default on)
```

Other entry points:

```bash
spongecake-viewer --host 127.0.0.1 --port 8090 --reports ./reports
spongecake-bridge --host 0.0.0.0 --port 5003          # Mac-side, requires [bridge,chronos]
```

## Watchlist format

`watchlist.yaml` is a YAML list. Each entry needs `tidm` + `name`. `description`
is optional — the LLM commentary fills its own.

```yaml
- tidm: GAW
  name: Games Workshop
  sector: Consumer
- tidm: FDEV
  name: Frontier Developments
  sector: Tech
  description: Optional fallback when no LLM key is set
```

A migrator from the legacy pipe-delimited format is included:

```python
from spongecake_autoreport.watchlist import migrate_pipe_file
migrate_pipe_file("watchlist", "watchlist.yaml")
```

## Forecasting modes

| Mode | Where it runs | Deps | Notes |
|------|----------------|------|-------|
| `mc` (default) | Anywhere | numpy | Bootstrap of historical log-returns. Always available. |
| `chronos-local` | Process host | `[chronos]` extra (`torch + chronos-forecasting`) | First run downloads the model. Use `chronos-t5-tiny` on cloud (4GB host). |
| `chronos-remote` | Routes to a Mac via HTTP | `requests` only on the caller | Requires `spongecake-bridge` running on the Mac (tailscale recommended). Cloud falls back to MC silently if Mac is unreachable. |

## Output

- `report.pdf` — A4, table of contents sorted by trend score, one page per stock
- `index.html` + `<TIDM>.html` — interactive Plotly charts
- `signals.json` — snapshot used to diff future runs

A run also persists state under `./state/`:
- `state/signals/<YYYY-MM-DD>.json`
- `state/commentary/<TIDM>/<YYYY-MM-DD>.json` — same-day re-runs are free

## Deployment

This repo deploys to the Hetzner cloud server (`cloud.hammant.io`) as systemd
units, alongside the existing hydra trader. See `deploy/` and `Phase 6` of the
plan at `~/.claude/plans/cool-fork-it-make-zany-cookie.md`.

## Tests

```bash
uv run pytest -q
```

Smoke tests stub yfinance — they don't hit the network.

## License

MIT (inherited from upstream).
