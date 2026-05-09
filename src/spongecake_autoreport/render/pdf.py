"""WeasyPrint-based PDF generation. Modernized port of the original
`spongecake_report_generator.SpongecakeReportGenerator`.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd


PAGE_CSS = """
@page { size: A4; margin: 1.2cm; }
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 9px; color: #222; }
h1 { font-size: 18px; margin: 0 0 8px 0; }
h2 { font-size: 14px; margin: 0 0 4px 0; }
h3 { font-size: 11px; margin: 0 0 4px 0; }
.muted { color: #666; font-size: 8px; }
.flag-green { background: #d1f4d1; padding: 1px 6px; border-radius: 3px; }
.flag-amber { background: #fff3c2; padding: 1px 6px; border-radius: 3px; }
.flag-red { background: #fbd5d5; padding: 1px 6px; border-radius: 3px; }
table { border-collapse: collapse; font-size: 7px; margin: 4px 0 8px 0; }
th, td { border: 1px solid #bbb; padding: 2px 4px; text-align: left; }
th { background: #efefef; font-weight: bold; }
.page { page-break-after: always; }
.toc-row td { padding: 3px 6px; }
.signals { font-size: 9px; line-height: 1.4; }
.signals li { margin-bottom: 2px; }
.section { margin-bottom: 8px; }
.commentary { font-size: 9px; line-height: 1.4; padding: 6px 8px; background: #fafafa; border-left: 3px solid #4F8FF7; }
.diff-new { color: #096; font-weight: bold; }
.diff-gone { color: #966; }
img.chart { width: 100%; max-height: 400px; object-fit: contain; }
.bt-table { font-size: 8px; }
.cols { display: flex; gap: 8px; }
.col { flex: 1; }
"""


def _df_to_html(df: pd.DataFrame, max_cols: int | None = None) -> str:
    if df is None or df.empty:
        return "<p class=muted>(no data)</p>"
    if max_cols:
        df = df.iloc[:, :max_cols]
    return df.to_html(index=False, na_rep="", float_format=lambda v: f"{v:,.2f}")


def render(
    *,
    out_path: Path,
    run_dt: datetime,
    pages: list[dict],
    diff_summary: dict | None = None,
) -> Path:
    """Render the full report. `pages` is a list of dicts with keys:
        tidm, name, sector, current_price, chart_path, signals (list[str]),
        trend_score (float), forecast_note (str), commentary (Commentary),
        summary_df, calcs_df, income_df, balance_df, backtests (list of BacktestResult),
        diff_new (list[str]), diff_gone (list[str])
    """
    parts: list[str] = []
    parts.append(_toc_html(run_dt, pages, diff_summary))
    pages_sorted = sorted(pages, key=lambda p: p.get("trend_score", 0.0), reverse=True)
    for p in pages_sorted:
        parts.append(_page_html(p))

    doc = "<html><head></head><body>" + "".join(parts) + "</body></html>"

    # Defer weasyprint import: native libs (cairo, pango, gobject, etc.) only
    # need to be installed when the user actually renders a PDF. This keeps the
    # package importable on hosts without those system libs (e.g. CI smoke tests).
    from weasyprint import CSS, HTML
    from weasyprint.text.fonts import FontConfiguration

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=doc).write_pdf(
        str(out_path),
        stylesheets=[CSS(string=PAGE_CSS)],
        font_config=FontConfiguration(),
    )
    return out_path


def _flag_html(flag: str) -> str:
    flag = (flag or "amber").lower()
    cls = {"green": "flag-green", "amber": "flag-amber", "red": "flag-red"}.get(flag, "flag-amber")
    return f'<span class="{cls}">{flag.upper()}</span>'


def _toc_html(run_dt: datetime, pages: list[dict], diff_summary: dict | None) -> str:
    rows: list[str] = []
    pages_sorted = sorted(pages, key=lambda p: p.get("trend_score", 0.0), reverse=True)
    for p in pages_sorted:
        score = p.get("trend_score", 0.0)
        rows.append(
            f'<tr class="toc-row"><td>{html.escape(p["tidm"])}</td>'
            f'<td>{html.escape(p["name"])}</td>'
            f'<td>{html.escape(p.get("sector", ""))}</td>'
            f"<td>{score:+.2f}</td>"
            f"<td>{_flag_html(p.get('flag', 'amber'))}</td></tr>"
        )

    diff_block = ""
    if diff_summary:
        new_lines = "\n".join(
            f"<li><b>{html.escape(t)}</b>: {html.escape(s)}</li>"
            for t, s in diff_summary.get("new", [])[:20]
        )
        gone_lines = "\n".join(
            f"<li><b>{html.escape(t)}</b>: {html.escape(s)}</li>"
            for t, s in diff_summary.get("gone", [])[:20]
        )
        diff_block = (
            f'<div class="section"><h3>Changes since last run ({html.escape(diff_summary.get("prior_date", ""))})</h3>'
            f'<div class="cols"><div class="col"><b>NEW</b><ul>{new_lines or "<li>—</li>"}</ul></div>'
            f'<div class="col"><b>GONE</b><ul>{gone_lines or "<li>—</li>"}</ul></div></div></div>'
        )

    return (
        '<div class="page">'
        f"<h1>Spongecake Autoreport</h1>"
        f'<p class="muted">Generated {run_dt.strftime("%Y-%m-%d %H:%M %Z")} — sorted by trend score</p>'
        f"{diff_block}"
        '<table style="width:100%;">'
        "<tr><th>TIDM</th><th>Name</th><th>Sector</th><th>Trend</th><th>Flag</th></tr>"
        + "".join(rows) +
        "</table></div>"
    )


def _page_html(p: dict) -> str:
    tidm = html.escape(p["tidm"])
    name = html.escape(p["name"])
    price = p.get("current_price")
    price_str = f"{price:,.2f}" if isinstance(price, (int, float)) else "—"
    score = p.get("trend_score", 0.0)
    fc_note = html.escape(p.get("forecast_note", ""))
    diff_new = p.get("diff_new", [])
    diff_gone = p.get("diff_gone", [])
    diff_html = ""
    if diff_new or diff_gone:
        new_html = "".join(f'<li class="diff-new">[NEW] {html.escape(s)}</li>' for s in diff_new)
        gone_html = "".join(f'<li class="diff-gone">[GONE] {html.escape(s)}</li>' for s in diff_gone)
        diff_html = f'<ul class="signals">{new_html}{gone_html}</ul>'

    com = p.get("commentary")
    com_html = ""
    if com is not None:
        com_html = (
            f'<div class="commentary">'
            f"<div><b>{html.escape(com.headline)}</b> &nbsp; {_flag_html(com.flag)}</div>"
            f"<div><b>Technical:</b> {html.escape(com.technical)}</div>"
            f"<div><b>Fundamental:</b> {html.escape(com.fundamental)}</div>"
            f"</div>"
        )

    bt_html = ""
    if p.get("backtests"):
        rows = "".join(
            f"<tr><td>{html.escape(b.name)}</td>"
            f"<td>{b.total_return_pct:+.1f}%</td>"
            f"<td>{b.buy_hold_return_pct:+.1f}%</td>"
            f"<td>{b.num_trades}</td>"
            f"<td>{b.win_rate_pct:.0f}%</td>"
            f"<td>{b.sharpe:.2f}</td>"
            f"<td>{b.max_drawdown_pct:.1f}%</td></tr>"
            for b in p["backtests"]
        )
        bt_html = (
            '<h3>Strategy backtests (vs buy & hold over chart window)</h3>'
            '<table class="bt-table"><tr>'
            "<th>Strategy</th><th>Return</th><th>B&H</th><th>Trades</th>"
            "<th>Win%</th><th>Sharpe</th><th>MaxDD</th></tr>" + rows + "</table>"
        )

    signals_html = "<ul class=signals>" + "".join(
        f"<li>{html.escape(s)}</li>" for s in p.get("signals", [])
    ) + "</ul>"

    forecast_caption = ""
    if fc_note:
        forecast_caption = f'<p class="muted">Forecast: {fc_note}</p>'

    return (
        '<div class="page">'
        f"<h2>{tidm} &mdash; {name}</h2>"
        f'<p class="muted">Sector: {html.escape(p.get("sector", ""))} &nbsp;|&nbsp; '
        f"Last close: {price_str} &nbsp;|&nbsp; "
        f"Trend score: {score:+.2f}</p>"
        + (com_html or "")
        + f'<img class="chart" src="file://{p["chart_path"]}" />'
        + forecast_caption
        + '<div class="cols">'
        + f'<div class="col"><h3>Signals</h3>{signals_html}{diff_html}</div>'
        + f'<div class="col"><h3>Summary</h3>{_df_to_html(p.get("summary_df"))}'
        + f'<h3>Calcs</h3>{_df_to_html(p.get("calcs_df"))}</div>'
        + "</div>"
        + bt_html
        + f'<h3>Income</h3>{_df_to_html(p.get("income_df"), max_cols=6)}'
        + f'<h3>Balance</h3>{_df_to_html(p.get("balance_df"), max_cols=6)}'
        + "</div>"
    )
