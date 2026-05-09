from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Stock:
    tidm: str
    name: str
    sector: str = ""
    description: str = ""

    @property
    def yfinance_symbol(self) -> str:
        return f"{self.tidm}.L"


def load(path: str | Path) -> list[Stock]:
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f) or []
    if not isinstance(raw, list):
        raise ValueError(f"watchlist {path} must be a YAML list of stocks")
    out: list[Stock] = []
    for item in raw:
        if not isinstance(item, dict) or "tidm" not in item or "name" not in item:
            raise ValueError(f"each watchlist entry needs tidm + name; got {item!r}")
        out.append(
            Stock(
                tidm=str(item["tidm"]).strip(),
                name=str(item["name"]).strip(),
                sector=str(item.get("sector", "")).strip(),
                description=str(item.get("description", "")).strip(),
            )
        )
    return out


def migrate_pipe_file(pipe_path: str | Path, out_path: str | Path) -> int:
    """Convert legacy `tidm|name|description` watchlist to YAML. Returns row count."""
    pipe_path = Path(pipe_path)
    out_path = Path(out_path)
    rows: list[dict] = []
    for line in pipe_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        rows.append(
            {
                "tidm": parts[0],
                "name": parts[1],
                "description": parts[2] if len(parts) >= 3 else "",
            }
        )
    out_path.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True))
    return len(rows)
