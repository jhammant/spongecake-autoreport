from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)

API = "https://api.pushover.net/1/messages.json"


def notify(*, user_key: str, app_token: str, title: str, message: str,
           viewer_url: str = "", priority: int = 0) -> bool:
    if not user_key or not app_token:
        return False
    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
        "priority": priority,
    }
    if viewer_url:
        payload["url"] = viewer_url
        payload["url_title"] = "Open report"
    try:
        r = requests.post(API, data=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:
        log.warning("Pushover notify failed: %s", exc)
        return False
