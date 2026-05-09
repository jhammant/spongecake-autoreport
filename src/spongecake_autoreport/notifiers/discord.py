from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


def notify(*, webhook_url: str, title: str, summary: str, top_movers: list[tuple[str, float]],
           new_signals: list[tuple[str, str]], viewer_url: str = "") -> bool:
    if not webhook_url:
        return False
    movers_text = "\n".join(f"**{t}**  trend {s:+.2f}" for t, s in top_movers[:5]) or "—"
    new_text = "\n".join(f"**{t}** — {sig}" for t, sig in new_signals[:8]) or "—"

    embed = {
        "title": title,
        "description": summary,
        "color": 0x4F8FF7,
        "fields": [
            {"name": "Top movers", "value": movers_text, "inline": False},
            {"name": "New signals", "value": new_text, "inline": False},
        ],
    }
    if viewer_url:
        embed["url"] = viewer_url

    try:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("Discord notify failed: %s", exc)
        return False
