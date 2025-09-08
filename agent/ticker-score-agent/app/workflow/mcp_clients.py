from __future__ import annotations
import json
from typing import Any, Dict
from contextlib import asynccontextmanager

from app.settings import settings
from langchain_mcp_adapters.client import MultiServerMCPClient


@asynccontextmanager
async def open_mcp_client() -> MultiServerMCPClient:
    """mcp_config.json 로드 후 MultiServerMCPClient 반환"""
    with open(settings.mcp_config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    servers_cfg = cfg.get("servers") or cfg.get("mcpServers") or {}
    if not servers_cfg:
        raise RuntimeError("No MCP servers found in config")

    client = MultiServerMCPClient(servers_cfg)
    await client.get_tools()  # 연결 확인
    try:
        yield client
    finally:
        if hasattr(client, "close"):
            await client.close()

async def call_tool(client: MultiServerMCPClient, name: str, args: dict):
    """
    MCP 툴 호출 공통 함수.
    name: 'yahoo:get_stock_info' 같은 풀네임 또는 'price' 같은 단일 툴 이름
    """
    tools = await client.get_tools()
    # 이름이 정확히 일치하는 툴 찾기
    for t in tools:
        if getattr(t, "name", None) == name:
            return await t.ainvoke(args)
    raise RuntimeError(f"Tool not found: {name}, available={[t.name for t in tools]}")


# ----------------------------
# Stock Information
# ----------------------------
async def get_historical_stock_prices(client, ticker: str, period="1mo", interval="1d"):
    return await call_tool(client, "get_historical_stock_prices", {
        "ticker": ticker,
        "period": period,       # e.g. "1mo", "6mo", "1y"
        "interval": interval    # e.g. "1d", "1wk", "1mo"
    })

async def get_stock_info(client, ticker: str):
    return await call_tool(client, "get_stock_info", {"ticker": ticker})

async def get_yahoo_finance_news(client, ticker: str, limit: int = 5):
    return await call_tool(client, "get_yahoo_finance_news", {
        "ticker": ticker
    })

async def get_stock_actions(client, ticker: str):
    return await call_tool(client, "get_stock_actions", {"ticker": ticker})

# ----------------------------
# Financial Statements
# ----------------------------
async def get_financial_statement(client, ticker: str, statement_type="income", period="annual"):
    return await call_tool(client, "get_financial_statement", {
        "ticker": ticker,
        "statement_type": statement_type,  # "income" | "balance" | "cashflow"
        "period": period                   # "annual" | "quarterly"
    })

async def get_holder_info(client, ticker: str, holder_type="major"):
    return await call_tool(client, "get_holder_info", {
        "ticker": ticker,
        "holder_type": holder_type  # "major" | "institutional" | "mutual" | "insider"
    })

# ----------------------------
# Options Data
# ----------------------------
async def get_option_expiration_dates(client, ticker: str):
    return await call_tool(client, "get_option_expiration_dates", {"ticker": ticker})

async def get_option_chain(client, ticker: str, expiration: str, option_type="calls"):
    return await call_tool(client, "get_option_chain", {
        "ticker": ticker,
        "expiration": expiration,  # "2025-01-17" 같은 만기일
        "option_type": option_type # "calls" | "puts"
    })

# ----------------------------
# Analyst Information
# ----------------------------
async def get_recommendations(client, ticker: str):
    return await call_tool(client, "get_recommendations", {"ticker": ticker})
