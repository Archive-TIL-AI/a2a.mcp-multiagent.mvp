# app/workflow/trace.py
from __future__ import annotations
import json, time, functools
from typing import Any, Dict, Callable

import logging
LOGGER = logging.getLogger("ticker-graph")

def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        try:
            return json.dumps(str(obj), ensure_ascii=False)
        except Exception:
            return "<unserializable>"

def shorten(x: Any, limit: int = 400) -> str:
    s = _safe_json(x) if not isinstance(x, str) else x
    return (s[:limit] + "…") if len(s) > limit else s

def state_preview(state: Dict[str, Any]) -> Dict[str, Any]:
    """노드 입/출력 시점의 상태 요약 (가볍게 보여주기 위함)."""
    if state is None:
        return {}
    price = state.get("price") or {}
    news = state.get("news") or []
    filings = state.get("filings") or []
    logs = state.get("logs") or []
    return {
        "ticker": state.get("ticker"),
        "price": {
            "ticker": price.get("ticker"),
            "last": price.get("last"),
            "chg": price.get("chg"),
            "pct": price.get("pct"),
        } if price else None,
        "news_len": len(news),
        "filings_len": len(filings),
        "score": state.get("score"),
        "rationale_preview": (state.get("rationale")[:120] + "…") if isinstance(state.get("rationale"), str) and len(state.get("rationale")) > 120 else state.get("rationale"),
        "logs_len": len(logs),
    }

def traced(node_name: str):
    """
    노드 함수(async)에 적용하는 데코레이터.
    - 입력/출력/소요 ms 를 logs에 추가
    - trace[node_name]에 before_state/after_state 프리뷰를 함께 기록
    """
    def deco(fn: Callable[..., Any]):
        @functools.wraps(fn)
        async def wrapper(state: dict):
            t0 = time.perf_counter()

            # BEFORE PREVIEW (입력 상태)
            before = state_preview(state)
            LOGGER.info("[%-8s] START  before=%s", node_name, shorten(before, 300))

            try:
                out = await fn(state)  # 노드 본체 실행
                dt_ms = int((time.perf_counter() - t0) * 1000)

                # AFTER PREVIEW (출력 상태 = 입력+p(reset)atch 가 아니고, 노드 반환 값만 프리뷰)
                # 반환 out 자체의 핵심만 요약해서 본다.
                out_for_preview = {
                    "price": out.get("price"),
                    "news": out.get("news"),
                    "filings": out.get("filings"),
                    "score": out.get("score"),
                    "rationale": out.get("rationale"),
                    "logs": out.get("logs"),
                }
                after = state_preview(out_for_preview)

                LOGGER.info("[%-8s] END    %dms  after=%s", node_name, dt_ms, shorten(after, 300))

                # logs 는 리듀서로 합쳐지므로 증분만 넣기
                out_logs = out.get("logs", [])
                out_trace = out.get("trace", {})
                out = {**out, "logs": out_logs + [f"{node_name}: {dt_ms}ms"]}

                # response preview: 주요 필드만 축약
                resp_preview = {
                    k: shorten(v, 400)
                    for k, v in out.items()
                    if k in ("price", "news", "filings", "score", "rationale")
                }

                # trace(노드별 상세) 추가: before/after 포함
                out["trace"] = {
                    **out_trace,
                    node_name: {
                        "duration_ms": dt_ms,
                        "before_state": before,
                        "after_state": after,
                        "request": {  # 요청 요약 (필요 시 확장)
                            "ticker": state.get("ticker"),
                        },
                        "response_preview": resp_preview,
                    }
                }
                return out

            except Exception as e:
                dt_ms = int((time.perf_counter() - t0) * 1000)
                LOGGER.exception("[%-8s] ERROR  %dms  %s", node_name, dt_ms, e)
                return {
                    "logs": [f"{node_name}:ERROR {type(e).__name__} {str(e)} ({dt_ms}ms)"],
                    "trace": {
                        node_name: {
                            "duration_ms": dt_ms,
                            "error": f"{type(e).__name__}: {e}",
                            "before_state": before,
                            "request": {"ticker": state.get("ticker")},
                        }
                    }
                }
        return wrapper
    return deco


def events_to_mermaid_flow(events: list[dict]) -> str:
    """
    astream_events로 수집한 이벤트를 Flowchart로 가볍게 가시화
    """
    visited = []
    for ev in events:
        if ev.get("event") == "on_chain_end" and ev.get("name"):
            visited.append(ev["name"])
        if ev.get("event") == "on_node_end" and ev.get("name"):
            visited.append(ev["name"])

    # 중복 압축
    seq = []
    for n in visited:
        if not seq or seq[-1] != n:
            seq.append(n)

    lines = ["flowchart LR", "  START((START))", "  END((END))"]
    prev = "START"
    for n in seq:
        nid = n.replace(" ", "_")
        lines.append(f"  {prev} --> {nid}[[{n}]]")
        prev = nid
    lines.append(f"  {prev} --> END")
    return "\n".join(lines)