"""Per-stock LLM commentary via Anthropic SDK with prompt caching.

System prompt is marked `cache_control: ephemeral` so the high-level role +
schema description is paid-for once per 5-minute window.

Cached to disk by (tidm, run_date) so a re-run in the same day is free.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a UK equities research analyst writing one-paragraph briefings for a daily watchlist report.

Voice: terse, factual, no marketing fluff, no emojis. Use the data given to you; don't invent numbers.

For each stock you receive, return a JSON object with exactly these keys:
- headline: one short sentence summarising what the data is telling us today
- technical: 2-3 sentences from the chart and indicator signals (MACD, RSI, Stochastic, Bollinger, 52w proximity, trend score)
- fundamental: 2 sentences from balance / income / summary tables (margins, leverage, valuation, anything notable)
- flag: one of "green", "amber", "red" — your overall sense given today's signals only

Output VALID JSON ONLY. No prose, no code fences, no commentary outside the JSON."""


@dataclass
class Commentary:
    tidm: str
    headline: str
    technical: str
    fundamental: str
    flag: str  # green | amber | red

    @classmethod
    def disabled(cls, tidm: str, reason: str = "ANTHROPIC_API_KEY not set") -> "Commentary":
        return cls(
            tidm=tidm,
            headline=f"(commentary disabled — {reason})",
            technical="",
            fundamental="",
            flag="amber",
        )


def _cache_path(state_dir: Path, tidm: str, run_date: date) -> Path:
    p = state_dir / "commentary" / tidm / f"{run_date.isoformat()}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get(
    *,
    tidm: str,
    name: str,
    sector: str,
    signals: list[str],
    trend_score: float,
    summary_text: str,
    balance_text: str,
    income_text: str,
    state_dir: Path,
    cfg,
    run_date: date | None = None,
) -> Commentary:
    """Return cached commentary if present today; otherwise call Anthropic."""
    run_date = run_date or date.today()
    cache_file = _cache_path(state_dir, tidm, run_date)
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return Commentary(**data)
        except Exception:
            log.warning("commentary cache parse failed for %s; regenerating", tidm)

    if not cfg.anthropic_api_key:
        return Commentary.disabled(tidm)

    try:
        import anthropic
    except ImportError:
        return Commentary.disabled(tidm, "anthropic SDK not installed")

    user_payload = {
        "tidm": tidm,
        "name": name,
        "sector": sector,
        "trend_score": round(trend_score, 3),
        "signals": signals,
        "summary": summary_text,
        "balance": balance_text,
        "income": income_text,
    }

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    try:
        msg = client.messages.create(
            model=cfg.anthropic_model,
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        text = msg.content[0].text.strip()
        # Defensive: occasionally a model wraps JSON in ``` despite instructions.
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        data = json.loads(text)
        c = Commentary(
            tidm=tidm,
            headline=str(data.get("headline", "")),
            technical=str(data.get("technical", "")),
            fundamental=str(data.get("fundamental", "")),
            flag=str(data.get("flag", "amber")).lower(),
        )
        cache_file.write_text(json.dumps(c.__dict__))
        return c
    except Exception as exc:
        log.warning("anthropic commentary failed for %s: %s", tidm, exc)
        return Commentary.disabled(tidm, f"API error: {exc}")
