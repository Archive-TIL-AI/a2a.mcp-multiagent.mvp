from __future__ import annotations
from typing import Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.workflow.state import ScoreState
from app.workflow.nodes import node_yahoo, node_dart, node_score, node_finalize
from uuid import uuid4
from app.workflow.trace import events_to_mermaid_flow

# 그래프 선언 (병렬 노드 구성)
memory = MemorySaver()
builder = StateGraph(ScoreState)

builder.add_node("yahoo",    node_yahoo)
builder.add_node("dart",     node_dart)
builder.add_node("score",    node_score)
builder.add_node("finalize", node_finalize)

# START → yahoo & dart (병렬) → score → finalize → END
builder.add_edge(START, "yahoo")
builder.add_edge(START, "dart")
builder.add_edge("yahoo", "score")
builder.add_edge("dart",  "score")
builder.add_edge("score", "finalize")
builder.add_edge("finalize", END)

graph = builder.compile(checkpointer=memory)

# 실행 유틸
async def run_once(ticker: str) -> Dict[str, Any]:
    cfg = {"configurable": {"thread_id": f"score-{ticker}-{uuid4()}"}}  # ✅ 새 스레드 id
    final: ScoreState = await graph.ainvoke({"ticker": ticker}, config=cfg)
    return {
        "ticker":    ticker,
        "price":     final.get("price"),
        "news":      final.get("news"),
        "filings":   final.get("filings"),
        "score":     final.get("score"),
        "rationale": final.get("rationale"),
        "logs":      final.get("logs"),
        "trace": final.get("trace", {}),  # 🔎 노드별 request/response 미리보기
    }

async def run_stream(ticker: str):
    cfg = {"configurable": {"thread_id": f"stream-{ticker}-{uuid4()}"}}  # ✅
    async for ev in graph.astream({"ticker": ticker}, config=cfg):
        yield ev  # {"yahoo": {...}}, {"dart": {...}}, {"score": {...}}, ...

async def run_with_trace(ticker: str):
    cfg = {"configurable": {"thread_id": f"trace-{ticker}-{uuid4()}"}}
    events = []
    async for ev in graph.astream_events({"ticker": ticker}, version="v2", config=cfg):
        # ev 예: {"event":"on_node_start","name":"yahoo",...}, {"event":"on_node_end","name":"yahoo",...}
        events.append(ev)
        yield {"event": ev.get("event"), "name": ev.get("name")}  # SSE 등으로 바로 전송 가능

    # 실행 종료 후 Mermaid 텍스트 생성
    mermaid = events_to_mermaid_flow(events)
    yield {"event": "diagram", "mermaid": mermaid}
