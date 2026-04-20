import os
import requests
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from ..db.models import Pie, Company, Position


class Trading212Client:
    def __init__(self):
        self.api_key = os.environ["T212_API_KEY"]
        mode = os.environ.get("T212_MODE", "live")
        if mode == "demo":
            self.base_url = "https://demo.trading212.com/api/v0"
        else:
            self.base_url = "https://live.trading212.com/api/v0"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.api_key})

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = self.session.get(f"{self.base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    def fetch_portfolio(self) -> list[dict]:
        return self._get("/equity/portfolio")

    def fetch_pies(self) -> list[dict]:
        return self._get("/equity/pies")

    def fetch_pie(self, pie_id: int) -> dict:
        return self._get(f"/equity/pies/{pie_id}")

    def sync(self, db: Session) -> dict[str, int]:
        """Sync all pies and positions from Trading212 into the DB."""
        now = datetime.utcnow()
        stats = {"pies": 0, "positions": 0, "companies": 0}

        # --- Pies ---
        raw_pies = self.fetch_pies()
        t212_pie_ids = set()
        pie_map: dict[str, int] = {}  # t212_id -> db pie.id

        for raw in raw_pies:
            t212_id = raw["id"]
            t212_pie_ids.add(t212_id)
            pie = db.query(Pie).filter_by(t212_id=t212_id).first()
            if pie is None:
                pie = Pie(t212_id=t212_id)
                db.add(pie)

            pie.name = raw.get("settings", {}).get("name", f"Pie {t212_id}")
            pie.icon = raw.get("settings", {}).get("icon")
            pie.target_currency = raw.get("settings", {}).get("targetCurrency")
            pie.cash = raw.get("cash", 0.0)
            pie.result = raw.get("result", {}).get("result", 0.0)
            pie.result_pct = raw.get("result", {}).get("resultCoef", 0.0)
            pie.last_updated = now
            db.flush()
            pie_map[t212_id] = pie.id
            stats["pies"] += 1

        # --- Pie instruments (positions inside pies) ---
        pie_ticker_map: dict[str, int] = {}  # ticker -> pie db id
        for t212_id in t212_pie_ids:
            detail = self.fetch_pie(t212_id)
            instruments = detail.get("instruments", [])
            for inst in instruments:
                ticker = inst.get("ticker", "").replace("_EQ", "")
                if ticker:
                    pie_ticker_map[ticker] = pie_map[t212_id]

            # update total value from pie detail
            pie = db.query(Pie).filter_by(t212_id=t212_id).first()
            if pie:
                pie.total_value = detail.get("result", {}).get("investedValue", 0.0)

        # --- Portfolio positions ---
        raw_positions = self.fetch_portfolio()

        # Remove stale positions
        db.query(Position).delete()

        for raw in raw_positions:
            ticker = raw.get("ticker", "").replace("_EQ", "")
            isin = raw.get("isin", "")

            # Upsert company stub
            company = db.query(Company).filter_by(ticker=ticker).first()
            if company is None:
                company = Company(ticker=ticker, isin=isin)
                db.add(company)
                company.name = raw.get("ticker", ticker)
                stats["companies"] += 1

            qty = raw.get("quantity", 0.0)
            avg = raw.get("averagePrice", 0.0)
            curr = raw.get("currentPrice", 0.0)
            ppl = raw.get("ppl", 0.0)
            total = qty * curr if curr else 0.0
            ppl_pct = (ppl / (qty * avg)) * 100 if avg and qty else 0.0

            pos = Position(
                ticker=ticker,
                isin=isin,
                quantity=qty,
                avg_price=avg,
                current_price=curr,
                total_value=total,
                ppl=ppl,
                ppl_pct=ppl_pct,
                currency=raw.get("currency", ""),
                pie_id=pie_ticker_map.get(ticker),
                last_updated=now,
            )
            db.add(pos)
            stats["positions"] += 1

        db.commit()
        return stats
