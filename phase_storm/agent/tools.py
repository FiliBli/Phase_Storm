"""
Tool implementations called by the Claude agent.
Each function returns a plain dict that gets serialised as the tool result.
"""
import json
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf

from ..db.database import get_session
from ..db.models import Company, Pie, Position


def get_portfolio_summary() -> dict:
    """Return all current positions grouped by pie."""
    db = get_session()
    try:
        positions = db.query(Position).all()
        pies: dict[str, list] = {}
        standalone = []

        for pos in positions:
            entry = {
                "ticker": pos.ticker,
                "name": pos.company.name if pos.company else pos.ticker,
                "quantity": round(pos.quantity, 4),
                "avg_price": round(pos.avg_price, 4),
                "current_price": round(pos.current_price, 4),
                "total_value": round(pos.total_value, 2),
                "ppl": round(pos.ppl, 2),
                "ppl_pct": round(pos.ppl_pct, 2),
                "currency": pos.currency,
            }
            if pos.pie:
                pies.setdefault(pos.pie.name, []).append(entry)
            else:
                standalone.append(entry)

        total_value = sum(p.total_value or 0 for p in positions)
        total_ppl = sum(p.ppl or 0 for p in positions)

        return {
            "total_value": round(total_value, 2),
            "total_ppl": round(total_ppl, 2),
            "positions_by_pie": pies,
            "standalone_positions": standalone,
            "last_sync": str(positions[0].last_updated) if positions else None,
        }
    finally:
        db.close()


def get_pie_details(pie_name: str) -> dict:
    """Return positions inside a specific pie (partial name match)."""
    db = get_session()
    try:
        pie = (
            db.query(Pie)
            .filter(Pie.name.ilike(f"%{pie_name}%"))
            .first()
        )
        if not pie:
            return {"error": f"No pie found matching '{pie_name}'"}

        positions = [
            {
                "ticker": p.ticker,
                "name": p.company.name if p.company else p.ticker,
                "quantity": round(p.quantity, 4),
                "avg_price": round(p.avg_price, 4),
                "current_price": round(p.current_price, 4),
                "total_value": round(p.total_value, 2),
                "ppl": round(p.ppl, 2),
                "ppl_pct": round(p.ppl_pct, 2),
            }
            for p in pie.positions
        ]
        return {
            "name": pie.name,
            "total_value": round(pie.total_value or 0, 2),
            "result": round(pie.result or 0, 2),
            "result_pct": round((pie.result_pct or 0) * 100, 2),
            "positions": positions,
        }
    finally:
        db.close()


def get_company_info(ticker: str) -> dict:
    """Fetch company fundamentals from Yahoo Finance and update DB."""
    db = get_session()
    try:
        company = db.query(Company).filter_by(ticker=ticker.upper()).first()

        # Refresh from yfinance if stale (>1 day) or missing description
        refresh = (
            company is None
            or not company.description
            or (
                company.last_updated
                and company.last_updated < datetime.utcnow() - timedelta(days=1)
            )
        )

        if refresh:
            yfdata = yf.Ticker(ticker).info
            if company is None:
                company = Company(ticker=ticker.upper())
                db.add(company)
            company.name = yfdata.get("longName") or yfdata.get("shortName", ticker)
            company.sector = yfdata.get("sector")
            company.industry = yfdata.get("industry")
            company.country = yfdata.get("country")
            company.description = yfdata.get("longBusinessSummary")
            company.market_cap = yfdata.get("marketCap")
            company.last_updated = datetime.utcnow()
            db.commit()

        return {
            "ticker": company.ticker,
            "name": company.name,
            "sector": company.sector,
            "industry": company.industry,
            "country": company.country,
            "market_cap": company.market_cap,
            "description": company.description,
        }
    finally:
        db.close()


def get_price_history(ticker: str, period: str = "3mo") -> dict:
    """Return recent price history. period: 1mo, 3mo, 6mo, 1y, 2y."""
    valid = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}
    if period not in valid:
        period = "3mo"
    hist = yf.Ticker(ticker).history(period=period)
    if hist.empty:
        return {"error": f"No price data for {ticker}"}
    latest = hist.tail(1)
    high = round(float(hist["High"].max()), 4)
    low = round(float(hist["Low"].min()), 4)
    current = round(float(latest["Close"].iloc[0]), 4)
    start_price = round(float(hist["Close"].iloc[0]), 4)
    change_pct = round((current - start_price) / start_price * 100, 2)
    return {
        "ticker": ticker,
        "period": period,
        "current_price": current,
        "period_high": high,
        "period_low": low,
        "period_change_pct": change_pct,
    }


def search_company_news(ticker: str, company_name: Optional[str] = None) -> dict:
    """Fetch recent news headlines for a ticker via Yahoo Finance."""
    label = company_name or ticker
    yfobj = yf.Ticker(ticker)
    raw_news = yfobj.news or []
    articles = []
    for item in raw_news[:10]:
        content = item.get("content", {})
        title = content.get("title", item.get("title", ""))
        summary = content.get("summary", item.get("summary", ""))
        pub = content.get("pubDate", item.get("providerPublishTime", ""))
        url = ""
        canonical = content.get("canonicalUrl", {})
        if isinstance(canonical, dict):
            url = canonical.get("url", "")
        articles.append({"title": title, "summary": summary, "published": str(pub), "url": url})
    return {"ticker": ticker, "company": label, "articles": articles}
