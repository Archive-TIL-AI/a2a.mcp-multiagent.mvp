# app/workflow/state.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict
from typing_extensions import Annotated
import operator

class ScoreState(TypedDict, total=False):
    ticker: str
    price: Optional[Dict[str, Any]]
    news: Optional[List[Dict[str, Any]]]
    filings: Optional[List[Dict[str, Any]]]
    score: Optional[int]
    rationale: Optional[str]
    # 병렬 합치기: 리스트 이어붙이기
    logs: Annotated[List[str], operator.add]
