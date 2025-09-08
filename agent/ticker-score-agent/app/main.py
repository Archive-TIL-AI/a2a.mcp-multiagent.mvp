from __future__ import annotations
import json
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, StreamingResponse
from app.workflow.graph import run_once, run_stream

app = FastAPI(title="Parallel MCP + CLOVA X Scoring")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
LOGGER = logging.getLogger("ticker-graph")

@app.get("/score")
async def score(ticker: str = Query(..., min_length=1)):
    result = await run_once(ticker)
    return JSONResponse({
        "ticker":    result["ticker"],
        "score":     result["score"],
        "rationale": result["rationale"]
    })

@app.get("/score/stream")
async def score_stream(ticker: str = Query(..., min_length=1)):
    async def sse():
        async for ev in run_stream(ticker):
            yield f"event: progress\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {json.dumps({'ticker': ticker}, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")

@app.get("/score/trace")
async def score_trace(ticker: str = Query(...)):
    async def sse():
        async for ev in run_with_trace(ticker):
            yield f"event: {ev['event']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
    return StreamingResponse(sse(), media_type="text/event-stream")
