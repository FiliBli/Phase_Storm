# Phase Storm

AI-powered portfolio assistant for Trading212. Syncs positions and pies from Trading212, stores them locally, and provides a Claude-powered chat interface for research, news and summaries.

## Owner
FiliBli — solo project.

## Stack
- Python + SQLAlchemy (SQLite)
- Trading212 REST API
- Anthropic SDK (claude-sonnet-4-6)
- yfinance for market data and news
- Rich + Click for CLI

## Key concepts
- **Pies** — Trading212 portfolio groupings (e.g. "Tech Pie = 40% AAPL, 30% MSFT")
- **Positions** — individual stock holdings synced from T212
- **Companies** — enriched with fundamentals from Yahoo Finance

## Commands
```bash
phase-storm sync        # pull latest data from Trading212
phase-storm portfolio   # view positions table
phase-storm chat        # talk to the AI agent
```

## Setup
```bash
pip install -e .
cp .env.example .env    # fill in ANTHROPIC_API_KEY and T212_API_KEY
```

## Branch workflow
- `main` — stable branch
- Feature work goes on a new branch → PR → merge into main
