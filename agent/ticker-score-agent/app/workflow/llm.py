from __future__ import annotations

# 예시: LangChain용 ChatClovaX (환경에 맞는 패키지 사용)
from langchain_naver import ChatClovaX

from dotenv import load_dotenv
import os

load_dotenv()

# 사용자 지정 파라미터 적용 (요청하신 설정)
# 내부에서 OPENAI_* env를 읽어 OpenAI 호환 클라이언트로 초기화됨
llm_naver = ChatClovaX(
    model="HCX-007",
    temperature=0.5,
    max_tokens=None,
    timeout=None,
    max_retries=2
)

