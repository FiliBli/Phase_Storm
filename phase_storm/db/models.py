from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Pie(Base):
    __tablename__ = "pies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    t212_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    icon = Column(String)
    target_currency = Column(String)
    cash = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    result = Column(Float, default=0.0)
    result_pct = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)

    positions = relationship("Position", back_populates="pie")


class Company(Base):
    __tablename__ = "companies"

    ticker = Column(String, primary_key=True)
    isin = Column(String, unique=True)
    name = Column(String)
    sector = Column(String)
    industry = Column(String)
    country = Column(String)
    description = Column(Text)
    market_cap = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

    positions = relationship("Position", back_populates="company")


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, ForeignKey("companies.ticker"), nullable=False)
    isin = Column(String)
    quantity = Column(Float)
    avg_price = Column(Float)
    current_price = Column(Float)
    total_value = Column(Float)
    ppl = Column(Float)          # profit/loss absolute
    ppl_pct = Column(Float)      # profit/loss percent
    currency = Column(String)
    pie_id = Column(Integer, ForeignKey("pies.id"), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="positions")
    pie = relationship("Pie", back_populates="positions")
