from __future__ import annotations
from app.workflow.state import ScoreState
# ✅ 간단 버전 mcp_clients 기반
from app.workflow.mcp_clients import (
    open_mcp_client,
    get_stock_info,
    get_yahoo_finance_news,
    # 선택: 필요 시 불러와 사용
    # get_historical_stock_prices,
    # get_recommendations,
)
from app.workflow.llm import llm_naver
from app.workflow.prompts import render_prompt
from app.workflow.trace import traced
import json
import re

# ── 병렬 MCP 노드: yahoo ─────────────────────────────────────────────────────
# -------------------------
# Node 1a: Yahoo (병렬)
# -------------------------
def _parse_news_blocks(s: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(s, str) or not s.strip():
        return []
    blocks = re.split(r"\n{2,}", s.strip())
    out: List[Dict[str, Any]] = []
    for b in blocks[:limit]:
        title = re.search(r"^Title:\s*(.*)$", b, re.MULTILINE)
        summary = re.search(r"^Summary:\s*(.*)$", b, re.MULTILINE)
        desc = re.search(r"^Description:\s*(.*)$", b, re.MULTILINE)
        url = re.search(r"^URL:\s*(.*)$", b, re.MULTILINE)
        out.append({
            "title": (title.group(1).strip() if title else None),
            "summary": (summary.group(1).strip() if summary else None) or (desc.group(1).strip() if desc else None),
            "sentiment": None,
            "url": (url.group(1).strip() if url else None),
        })
    return out
@traced("yahoo")
async def node_yahoo(state: "ScoreState") -> dict:
    async with open_mcp_client() as client:
        info = await get_stock_info(client, state["ticker"])
        news = await get_yahoo_finance_news(client, state["ticker"])

    # --- 가격 정규화 ---
    # --- get_stock_info: 문자열(JSON) 또는 dict 모두 처리 ---
    raw_info: Dict[str, Any] | None = None
    if isinstance(info, dict):
        raw_info = info
    elif isinstance(info, str):
        try:
            raw_info = json.loads(info)
        except Exception:
            raw_info = None  # 파싱 실패 시 None

    # 가격 정규화 (yfinance .info 키 기준)
    price = None
    if isinstance(raw_info, dict):
        last = (
                raw_info.get("currentPrice")
                or raw_info.get("regularMarketPrice")
                or raw_info.get("previousClose")  # fallback
                or raw_info.get("close")
        )
        prev_close = raw_info.get("previousClose") or raw_info.get("regularMarketPreviousClose")
        chg = raw_info.get("regularMarketChange")
        pct = raw_info.get("regularMarketChangePercent")

        # 없으면 계산해서 보완
        if chg is None and last is not None and prev_close:
            try:
                chg = float(last) - float(prev_close)
            except Exception:
                pass
        if pct is None and chg is not None and prev_close:
            try:
                pct = (float(chg) / float(prev_close)) * 100.0
            except Exception:
                pass

        price = {
            "ticker": state["ticker"],
            "last": last,
            "chg": chg,
            "pct": pct,
            # 필요하면 추가 필드도 싣기:
            # "open": raw_info.get("open"),
            # "day_high": raw_info.get("dayHigh"),
            # "day_low": raw_info.get("dayLow"),
            # "currency": raw_info.get("currency"),
        }

    # --- 뉴스 정규화 (list | dict(items) | str) ---
    norm_news: List[Dict[str, Any]] = []
    if isinstance(news, list):
        for n in news[:5]:
            norm_news.append({
                "title": n.get("title"),
                "summary": n.get("summary") or n.get("description"),
                "sentiment": n.get("sentiment"),
                "url": n.get("link") or n.get("url"),
            })
    elif isinstance(news, dict) and "items" in news:
        for n in news["items"][:5]:
            norm_news.append({
                "title": n.get("title"),
                "summary": n.get("summary") or n.get("description"),
                "sentiment": n.get("sentiment"),
                "url": n.get("link") or n.get("url"),
            })
    elif isinstance(news, str):
        norm_news = _parse_news_blocks(news, limit=5)

    return {
        "price": price,
        "news": norm_news,
        "logs": ["yahoo:ok"],
    }

@traced("dart")
async def node_dart(state: ScoreState) -> dict:
    # DART 노드 구현 (예: 공시 데이터 수집)
    # 현재는 더미 데이터 반환
    filings = [
        {"type": "사업보고서", "date": "2023-03-31", "summary": "2023년 1분기 사업보고서 제출"},
        {"type": "분기보고서", "date": "2023-06-30", "summary": "2023년 2분기 분기보고서 제출"},
    ]
    return {
        "filings": filings,
        "logs": ["dart:ok"],
    }

# ── Score 노드(Clova X 호출) ─────────────────────────────────────────────────
@traced("score")
async def node_score(state: ScoreState) -> dict:
    prompt = render_prompt(
        ticker=state["ticker"],
        price=state.get("price"),
        news=state.get("news"),
        filings=state.get("filings"),
    )

    # LangChain ChatClovaX 호출
    resp = await llm_naver.ainvoke(prompt)
    # resp.content(혹은 resp.response) 구조는 사용하는 어댑터에 맞게 확인
    text = getattr(resp, "content", None) or str(resp)

    # 모델에게 JSON을 요청했으므로 파싱 시도
    score, rationale = None, None
    try:
        data = json.loads(text)
        score = int(data.get("score"))
        rationale = data.get("rationale")
    except Exception:
        # 파싱 실패 시 보수적 폴백
        rationale = text[:200]
        score = 50

    return {"score": score, "rationale": rationale, "logs": ["score:ok"]}

# ── Finalize ─────────────────────────────────────────────────────────────────
@traced("finalize")
async def node_finalize(state: ScoreState) -> dict:
    return {"logs": ["finalize"]}
