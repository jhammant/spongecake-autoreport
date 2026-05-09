from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Runtime config sourced from env (loaded by .env or systemd EnvironmentFile)."""

    forecast_mode: str = "mc"  # mc | chronos-local | chronos-remote
    chronos_model: str = "amazon/chronos-t5-tiny"
    chronos_bridge_url: str = ""
    chronos_bridge_token: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_cheap_model: str = "claude-haiku-4-5-20251001"

    discord_webhook_url: str = ""
    pushover_user_key: str = ""
    pushover_app_token: str = ""

    viewer_auth: str = ""  # "user:pass"
    viewer_base_url: str = ""  # e.g. https://spongecake.hammant.io

    # Pruning
    keep_reports_days: int = 30

    notifiers: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            forecast_mode=os.environ.get("FORECAST_MODE", "mc"),
            chronos_model=os.environ.get("CHRONOS_MODEL", "amazon/chronos-t5-tiny"),
            chronos_bridge_url=os.environ.get("CHRONOS_BRIDGE_URL", ""),
            chronos_bridge_token=os.environ.get("CHRONOS_BRIDGE_TOKEN", ""),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            anthropic_cheap_model=os.environ.get(
                "ANTHROPIC_CHEAP_MODEL", "claude-haiku-4-5-20251001"
            ),
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
            pushover_user_key=os.environ.get("PUSHOVER_USER_KEY", ""),
            pushover_app_token=os.environ.get("PUSHOVER_APP_TOKEN", ""),
            viewer_auth=os.environ.get("VIEWER_AUTH", ""),
            viewer_base_url=os.environ.get("VIEWER_BASE_URL", ""),
            keep_reports_days=int(os.environ.get("KEEP_REPORTS_DAYS", "30")),
        )
