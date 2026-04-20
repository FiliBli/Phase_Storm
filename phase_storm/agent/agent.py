import json
import os
from typing import Optional

import anthropic

from .tools import (
    get_portfolio_summary,
    get_pie_details,
    get_company_info,
    get_price_history,
    search_company_news,
)

TOOLS = [
    {
        "name": "get_portfolio_summary",
        "description": (
            "Returns all current portfolio positions grouped by pie, "
            "including total value, profit/loss, and per-position details."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_pie_details",
        "description": "Returns positions inside a specific portfolio pie by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pie_name": {
                    "type": "string",
                    "description": "Full or partial name of the pie.",
                }
            },
            "required": ["pie_name"],
        },
    },
    {
        "name": "get_company_info",
        "description": (
            "Returns company fundamentals: sector, industry, country, market cap, "
            "and business description from Yahoo Finance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_price_history",
        "description": "Returns recent price history, period high/low and % change for a ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {
                    "type": "string",
                    "enum": ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
                    "description": "Time period for price history. Default 3mo.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "search_company_news",
        "description": "Fetches recent news headlines and summaries for a stock ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "company_name": {
                    "type": "string",
                    "description": "Optional human-readable company name for context.",
                },
            },
            "required": ["ticker"],
        },
    },
]

TOOL_DISPATCH = {
    "get_portfolio_summary": lambda args: get_portfolio_summary(),
    "get_pie_details": lambda args: get_pie_details(**args),
    "get_company_info": lambda args: get_company_info(**args),
    "get_price_history": lambda args: get_price_history(**args),
    "search_company_news": lambda args: search_company_news(**args),
}

SYSTEM_PROMPT = """You are Phase Storm, an intelligent portfolio assistant.
You have access to the user's Trading212 portfolio (positions, pies, companies).
You can look up company fundamentals, price history, and recent news.

When answering:
- Be concise but informative.
- Format numbers with appropriate currency symbols and decimal places.
- Highlight significant gains, losses, or newsworthy items.
- When asked for a summary, cover portfolio totals, top performers, worst performers, and any notable news.
- Today's date is {today}.
"""


class PhaseStormAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.history: list[dict] = []

    def _run_tool(self, name: str, args: dict) -> str:
        fn = TOOL_DISPATCH.get(name)
        if fn is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = fn(args)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def chat(self, user_message: str) -> str:
        from datetime import date
        self.history.append({"role": "user", "content": user_message})
        system = SYSTEM_PROMPT.format(today=date.today().isoformat())

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=self.history,
            )

            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._run_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })

                self.history.append({"role": "assistant", "content": assistant_content})
                self.history.append({"role": "user", "content": tool_results})

            else:
                # Final text response
                text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                self.history.append({"role": "assistant", "content": response.content})
                return text

    def reset(self):
        self.history = []
