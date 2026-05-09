from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


@dataclass
class Fundamentals:
    tidm: str
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    income: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    calcs: pd.DataFrame = field(default_factory=pd.DataFrame)
    current_price: float | None = None


def _df(d: dict | None) -> pd.DataFrame:
    if not d:
        return pd.DataFrame()
    return pd.DataFrame(d)


def fetch(tidm: str) -> Fundamentals:
    """Pull fundamentals from yfinance. Best-effort: returns empty frames on failure."""
    symbol = f"{tidm}.L"
    out = Fundamentals(tidm=tidm)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        out.current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        summary_rows = []
        for label, key in [
            ("Market Cap", "marketCap"),
            ("Trailing P/E", "trailingPE"),
            ("Forward P/E", "forwardPE"),
            ("Price/Book", "priceToBook"),
            ("Dividend Yield", "dividendYield"),
            ("Beta", "beta"),
            ("52w High", "fiftyTwoWeekHigh"),
            ("52w Low", "fiftyTwoWeekLow"),
            ("Currency", "currency"),
        ]:
            v = info.get(key)
            if v is not None:
                summary_rows.append({"Summary Line Item": label, "Value": v})
        out.summary = pd.DataFrame(summary_rows)

        try:
            out.income = ticker.income_stmt.fillna("").reset_index(names=["Income Line Item"])
        except Exception:
            pass
        try:
            out.balance = ticker.balance_sheet.fillna("").reset_index(names=["Balance Line Item"])
        except Exception:
            pass

        # Derived calcs
        calc_rows = []
        if (ca := info.get("totalCurrentAssets")) and (cl := info.get("totalCurrentLiabilities")):
            calc_rows.append({"Calc Line Item": "Current Ratio", "Value": round(ca / cl, 2)})
        if (e := info.get("trailingEps")) and (p := out.current_price):
            calc_rows.append(
                {
                    "Calc Line Item": "Earnings Yield % (TTM)",
                    "Value": f"{round((e / p) * 100, 2)}%",
                }
            )
        if (rc := info.get("returnOnCapital")):
            calc_rows.append({"Calc Line Item": "ROC", "Value": f"{round(rc * 100, 2)}%"})
        if (roe := info.get("returnOnEquity")):
            calc_rows.append({"Calc Line Item": "ROE", "Value": f"{round(roe * 100, 2)}%"})
        if (de := info.get("debtToEquity")):
            calc_rows.append({"Calc Line Item": "Debt/Equity", "Value": round(de, 2)})
        if (bvps := info.get("bookValue")) and (p := out.current_price):
            calc_rows.append({"Calc Line Item": "Book Value / Share", "Value": round(bvps, 2)})
            calc_rows.append(
                {
                    "Calc Line Item": "BV/Share as % of Price",
                    "Value": f"{round((bvps / p) * 100, 2)}%",
                }
            )
        out.calcs = pd.DataFrame(calc_rows)
    except Exception as exc:
        log.warning("yfinance fundamentals failed for %s: %s", symbol, exc)
    return out
