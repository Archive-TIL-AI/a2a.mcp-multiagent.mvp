from __future__ import annotations
from typing import Any, Dict, List
import logging

LOGGER = logging.getLogger("ticker-graph")

PROMPT_TEMPLATE = """\
당신은 한국어로 금융 뉴스를 요약하고 투자 관점의 점수를 산정하는 애널리스트입니다.
다음 입력을 바탕으로 1~100 사이의 점수와 짧은 한국어 근거를 생성하세요.

[컨텍스트]
- 종목: {ticker}
- 가격: last={last}, change={change}

- 뉴스(최대 5개):
{news_lines}

- 공시요약(최대 5개):
{filing_lines}

[요구사항]
- 숫자만 포함된 "score"(정수)와 "rationale"(짧은 한국어 문장 1~3개)로 JSON 출력
- 예: {{"score": 87, "rationale": "긍정적 뉴스와 안정적 가격 흐름"}}
"""

def render_prompt(ticker: str,
                  price: dict | None,
                  news: list[dict] | None,
                  filings: list[dict] | None) -> str:
    last = price.get("last") if price else None
    change = price.get("chg") or price.get("change") if price else None

    news_lines = ""
    if news:
        for n in news[:5]:
            title = n.get("title")
            senti = n.get("sentiment")
            summary = n.get("summary")
            news_lines += f"  - {title} ({senti}): {summary}\n"
    else:
        news_lines = "  - (데이터 없음)\n"

    filing_lines = ""
    if filings:
        for f in filings[:5]:
            ftype = f.get("type")
            fdate = f.get("date")
            fsum  = f.get("summary")
            filing_lines += f"  - [{ftype} {fdate}] {fsum}\n"
    else:
        filing_lines = "  - (데이터 없음)\n"

    prompt = PROMPT_TEMPLATE.format(
        ticker=ticker,
        last=last,
        change=change,
        news_lines=news_lines.rstrip(),
        filing_lines=filing_lines.rstrip()
    )

    # --- 로그/트레이스 남기기 ---
    preview = prompt if len(prompt) < 500 else prompt[:500] + "…"
    LOGGER.info("[prompt] ticker=%s, preview=%s", ticker, preview)

    return prompt
