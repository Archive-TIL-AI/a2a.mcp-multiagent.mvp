import asyncio
import json
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from mcp_yfinance import ensure_mcp


# ---------- Models ----------
class ScoreRequest(BaseModel):
    ticker: str
    market: str = "US"
    lookbackDays: int = Field(3, ge=1, le=30)
    sources: list[str] = Field(default_factory=lambda: ["news"])
    returnPriceContext: bool = True
    lang: str = "ko"


# ---------- Utilities ----------
async def sse_stream(gen: AsyncGenerator[Dict[str, Any], None]) -> StreamingResponse:
    async def _inner():
        try:
            async for ev in gen:
                # JSON 직렬화 시 안전장치 추가
                try:
                    json_str = json.dumps(ev, ensure_ascii=False, default=str)
                except TypeError as e:
                    # JSON 직렬화 실패 시 문자열로 변환
                    safe_ev = {"type": "error", "message": f"JSON serialization failed: {str(e)}"}
                    json_str = json.dumps(safe_ev, ensure_ascii=False)

                yield f"data: {json_str}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(_inner(), media_type="text/event-stream")


def pick_tool(tools: Dict[str, Any], candidates: list[str]) -> str | None:
    for name in candidates:
        if name in tools:
            return name
    return None


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # MCP는 각 요청마다 독립적으로 처리
    yield


# ---------- App ----------
app = FastAPI(title="A2A Agent (FastAPI + MCP stdio, uv --directory)", lifespan=lifespan)


# ---------- Endpoints ----------
@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/mcp/tools")
async def mcp_tools():
    async with ensure_mcp() as session:
        tools_resp = await session.list_tools()
        return {t.name: {"description": getattr(t, "description", "")} for t in tools_resp.tools}


@app.post("/score")
async def score(req: ScoreRequest, request: Request):
    async def _gen():
        yield {"type": "progress", "value": 5, "message": "MCP 연결 준비"}

        async with ensure_mcp() as session:
            # 툴 목록 조회
            tools_resp = await session.list_tools()
            tools = {t.name: {"description": getattr(t, "description", "")} for t in tools_resp.tools}

            # 1) 시세 툴 선택 (우선순위)
            quote_tool = pick_tool(
                tools,
                ["get_stock_info", "quote", "get_quote"]
            )
            if quote_tool:
                try:
                    yield {"type": "progress", "value": 15, "message": f"시세 조회({quote_tool})"}
                    quote_result = await session.call_tool(quote_tool, {"ticker": req.ticker})

                    # MCP 응답을 안전하게 파싱
                    if hasattr(quote_result, 'content') and quote_result.content:
                        quote_data = []
                        for content in quote_result.content:
                            if hasattr(content, 'text'):
                                quote_data.append(content.text)
                            elif hasattr(content, 'data'):
                                quote_data.append(content.data)
                            else:
                                quote_data.append(str(content))
                        quote_data = quote_data[0] if len(quote_data) == 1 else quote_data
                    else:
                        quote_data = str(quote_result)

                    yield {"type": "quote", "data": quote_data}
                except Exception as e:
                    yield {"type": "error", "stage": "quote", "message": str(e)}
            else:
                yield {"type": "error", "stage": "quote", "message": "시세 툴을 찾지 못했습니다."}

            # 2) 뉴스 툴 선택 (있을 때만)
            news_tool = pick_tool(
                tools,
                ["get_news", "news", "search_news", "get_company_news"]
            )
            if news_tool and ("news" in req.sources):
                try:
                    yield {"type": "progress", "value": 45, "message": f"뉴스 수집({news_tool})"}
                    news_result = await session.call_tool(
                        news_tool,
                        {"ticker": req.ticker, "lookback_days": req.lookbackDays}
                    )

                    # MCP 응답을 안전하게 파싱
                    if hasattr(news_result, 'content') and news_result.content:
                        news_data = []
                        for content in news_result.content:
                            if hasattr(content, 'text'):
                                news_data.append(content.text)
                            elif hasattr(content, 'data'):
                                news_data.append(content.data)
                            else:
                                news_data.append(str(content))
                        news_data = news_data[0] if len(news_data) == 1 else news_data
                    else:
                        news_data = str(news_result)

                    if isinstance(news_data, list):
                        for item in news_data:
                            yield {"type": "news_item", "data": item}
                    else:
                        yield {"type": "news_item", "data": news_data}
                except Exception as e:
                    yield {"type": "error", "stage": "news", "message": str(e)}

            # 3) (임시) 점수
            yield {
                "type": "score",
                "signal": "HOLD",
                "score": 0.5,
                "rationale": "MVP: LLM 연동 전 기본값"
            }

        yield {"type": "done"}

    return await sse_stream(_gen())