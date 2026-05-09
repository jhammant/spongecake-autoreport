"""Interactive HTML report using Plotly. Self-contained per-stock pages
plus an index.html that links them all.
"""

from __future__ import annotations

import html as html_mod
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial; margin: 24px; max-width: 1200px; color: #222; }
h1 { font-size: 22px; margin: 0 0 12px 0; }
h2 { font-size: 16px; margin: 18px 0 6px 0; }
.muted { color: #666; font-size: 12px; }
table { border-collapse: collapse; font-size: 12px; margin: 8px 0; }
td, th { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #f0f0f0; }
.flag-green { background: #d1f4d1; padding: 2px 8px; border-radius: 3px; }
.flag-amber { background: #fff3c2; padding: 2px 8px; border-radius: 3px; }
.flag-red { background: #fbd5d5; padding: 2px 8px; border-radius: 3px; }
.commentary { font-size: 13px; line-height: 1.5; padding: 10px 14px; background: #fafafa; border-left: 4px solid #4F8FF7; margin: 10px 0; }
.diff-new { color: #096; font-weight: bold; }
.diff-gone { color: #966; }
.signals { line-height: 1.6; }
"""


def _flag_html(flag: str) -> str:
    flag = (flag or "amber").lower()
    cls = {"green": "flag-green", "amber": "flag-amber", "red": "flag-red"}.get(flag, "flag-amber")
    return f'<span class="{cls}">{flag.upper()}</span>'


def _figure(df: pd.DataFrame, fc_median, fc_p5, fc_p95, fc_horizon: int, title: str) -> go.Figure:
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.42, 0.18, 0.20, 0.20],
        subplot_titles=("Price + Bollinger + Forecast", "MACD", "Stochastic", "RSI"),
        vertical_spacing=0.04,
    )

    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name="Close",
                             line=dict(color="black", width=1.4)), row=1, col=1)
    if "BB_UPPER" in df:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], mode="lines", name="BB upper",
                                 line=dict(color="rgba(200,30,30,0.5)", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], mode="lines", name="BB lower",
                                 line=dict(color="rgba(30,160,30,0.5)", width=1),
                                 fill="tonexty", fillcolor="rgba(80,140,200,0.07)"), row=1, col=1)

    if fc_median is not None and len(fc_median) > 0:
        last_idx = df.index[-1]
        fc_x = pd.date_range(last_idx, periods=fc_horizon + 1, freq="D")[1:]
        fig.add_trace(go.Scatter(x=fc_x, y=fc_median, mode="lines", name="Forecast median",
                                 line=dict(color="purple", dash="dash", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=fc_x, y=fc_p5, mode="lines", name="Forecast 5%",
                                 line=dict(color="rgba(120,80,200,0.0)")), row=1, col=1)
        fig.add_trace(go.Scatter(x=fc_x, y=fc_p95, mode="lines", name="Forecast 95%",
                                 line=dict(color="rgba(120,80,200,0.0)"),
                                 fill="tonexty", fillcolor="rgba(120,80,200,0.15)"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], mode="lines", name="MACD",
                             line=dict(color="tab:blue".replace("tab:", ""), width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_SIGNAL"], mode="lines", name="MACD signal",
                             line=dict(color="red", width=1.2)), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["STO_K"], mode="lines", name="%K",
                             line=dict(color="blue", width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["STO_D"], mode="lines", name="%D",
                             line=dict(color="red", width=1.2)), row=3, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI",
                             line=dict(color="purple", width=1.2)), row=4, col=1)

    fig.update_layout(
        height=900, margin=dict(l=40, r=20, t=60, b=40),
        title=title, showlegend=False, hovermode="x unified",
    )
    return fig


def render(
    *,
    out_dir: Path,
    run_dt: datetime,
    pages: list[dict],
    diff_summary: dict | None = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages_sorted = sorted(pages, key=lambda p: p.get("trend_score", 0.0), reverse=True)

    # Per-stock files
    for p in pages_sorted:
        tidm = p["tidm"]
        df = p["df"]
        fc_median = p.get("fc_median")
        fc_p5 = p.get("fc_p5")
        fc_p95 = p.get("fc_p95")
        fc_horizon = p.get("fc_horizon", 30)
        title = f"{tidm} — {p['name']}"
        fig = _figure(df, fc_median, fc_p5, fc_p95, fc_horizon, title)
        chart_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
        page_path = out_dir / f"{tidm}.html"
        com = p.get("commentary")
        com_html = ""
        if com is not None:
            com_html = (
                f'<div class="commentary">'
                f"<div><b>{html_mod.escape(com.headline)}</b> &nbsp; {_flag_html(com.flag)}</div>"
                f"<div><b>Technical:</b> {html_mod.escape(com.technical)}</div>"
                f"<div><b>Fundamental:</b> {html_mod.escape(com.fundamental)}</div>"
                f"</div>"
            )
        signals_html = "<ul class=signals>" + "".join(
            f"<li>{html_mod.escape(s)}</li>" for s in p.get("signals", [])
        ) + "</ul>"
        diff_html = ""
        if p.get("diff_new") or p.get("diff_gone"):
            new_html = "".join(f'<li class="diff-new">[NEW] {html_mod.escape(s)}</li>' for s in p.get("diff_new", []))
            gone_html = "".join(f'<li class="diff-gone">[GONE] {html_mod.escape(s)}</li>' for s in p.get("diff_gone", []))
            diff_html = f"<ul>{new_html}{gone_html}</ul>"

        body = f"""<html><head><meta charset="utf-8"><title>{html_mod.escape(title)}</title>
<style>{CSS}</style></head><body>
<p><a href="index.html">← back to index</a></p>
<h1>{html_mod.escape(title)}</h1>
<p class="muted">Sector: {html_mod.escape(p.get('sector',''))} | Trend: {p.get('trend_score',0):+.2f}
| Forecast: {html_mod.escape(p.get('forecast_note',''))}</p>
{com_html}
{chart_html}
<h2>Signals</h2>{signals_html}{diff_html}
</body></html>"""
        page_path.write_text(body)

    # Index
    rows = "\n".join(
        f"<tr><td>{html_mod.escape(p['tidm'])}</td>"
        f"<td><a href=\"{html_mod.escape(p['tidm'])}.html\">{html_mod.escape(p['name'])}</a></td>"
        f"<td>{html_mod.escape(p.get('sector',''))}</td>"
        f"<td>{p.get('trend_score', 0):+.2f}</td>"
        f"<td>{_flag_html(p.get('flag','amber'))}</td></tr>"
        for p in pages_sorted
    )
    index_html = f"""<html><head><meta charset="utf-8"><title>Spongecake — {run_dt:%Y-%m-%d}</title>
<style>{CSS}</style></head><body>
<h1>Spongecake Autoreport — {run_dt:%Y-%m-%d}</h1>
<p class="muted">Generated {run_dt:%H:%M %Z} — sorted by trend score</p>
<table><tr><th>TIDM</th><th>Name</th><th>Sector</th><th>Trend</th><th>Flag</th></tr>
{rows}</table>
</body></html>"""
    index_path = out_dir / "index.html"
    index_path.write_text(index_html)
    return index_path
