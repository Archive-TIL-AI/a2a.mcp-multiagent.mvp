from typing import Any, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_naver import ChatClovaX
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from dotenv import load_dotenv
import os

load_dotenv()
# print(os.getenv("OPENAI_API_KEY"))

# 1. 그래프 상태 정의 - 워크플로 전체 공유되는 데이터 구조
class EmotionBotState(BaseModel):
    user_message: str = Field(default="", description="사용자 메시지")
    emotion: str = Field(default="", description="감정 분석 결과")
    response: str = Field(default="", description="봇 응답 메시지")

# 2. LLM 초기화
class EmotionOut(BaseModel):
    emotion: Literal["positive", "negative", "neutral"]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=4)
llm_naver = ChatClovaX(
    model="HCX-007",  # 기본 모델; 튜닝 모델은 "ft:{튜닝 Task ID}" 형태
    temperature=0.5,
    max_tokens=None,
    timeout=None,
    max_retries=2
)

# 3) 구조화 출력 래핑
s_llm = llm.with_structured_output(EmotionOut)

# 3. LLM 기반 감정 분석 노드 - 첫번째 단계
def analyze_emotion(state: EmotionBotState) -> dict:
    """사용자 메시지에서 감정 분석"""
    user_message = state.user_message
    print(f"llm 감정 분석 중 ... 메시지: {user_message}")

    messages = [
        SystemMessage(
            content=(
                "당신은 감정 분석 전문가입니다. "
                "사용자 메시지의 감정을 'positive' | 'negative' | 'neutral' 중 하나로 판단하세요. "
                "설명 금지. 한 단어만."
            )
        ),
        HumanMessage(content=user_message),
    ]

    # 1차: 구조화 출력 시도
    # try:
    #     out: EmotionOut = s_llm.invoke(messages)
    #     emotion = out.emotion
    #     print(f"[구조화] 감정 분석 완료: {emotion}")
    #     return {"emotion": emotion}
    # except Exception as e:
    #     print(f"[구조화 실패] {e} → raw 호출로 폴백")

    # 2차: raw 호출 + 간단 정규화
    # resp = llm.invoke(messages)
    resp = llm_naver.invoke(messages)
    print(f"[raw] 응답 메타: {getattr(resp, 'response_metadata', {})}")
    text = (resp.content or "").strip().lower()

    # 빈 응답/length 종료 방어 재시도
    finish = getattr(resp, "response_metadata", {}).get("finish_reason")
    if not text or finish == "length":
        print("[raw] 빈 응답/length 종료 감지 → 토큰 여유로 재시도")
        retry_llm = ChatOpenAI(model="gpt-5-mini", temperature=0, max_tokens=64)
        resp = retry_llm.invoke(messages)
        text = (resp.content or "").strip().lower()

    # 매우 간단한 정규화
    t = text.strip("'\"` ").rstrip(".")
    if t.startswith("pos") or t in ("positive", "긍정", "긍정적"):
        emotion = "positive"
    elif t.startswith("neg") or t in ("negative", "부정", "부정적"):
        emotion = "negative"
    elif t.startswith("neu") or t in ("neutral", "중립", "중립적"):
        emotion = "neutral"
    else:
        emotion = "neutral"

    print(f"[raw] 감정 분석 완료: {emotion}")
    return {"emotion": emotion}

def generate_positive_response(state: EmotionBotState) -> dict[str, Any]:
    """긍정적인 감정에 대한 응답 생성"""
    print("긍정적인 응답 생성 중 ...")
    response = "좋은 소식이네요! 계속해서 긍정적인 마음을 유지하세요!"
    print(f"생성된 응답: {response}")
    return {"response": response}

def generate_negative_response(state: EmotionBotState) -> dict[str, Any]:
    """부정적인 감정에 대한 응답 생성"""
    print("부정적인 응답 생성 중 ...")
    response = "힘든 시간을 보내고 있군요. 필요하면 언제든지 이야기해 주세요."
    print(f"생성된 응답: {response}")
    return {"response": response}

def generate_neutral_response(state: EmotionBotState) -> dict[str, Any]:
    """중립적인 감정에 대한 응답 생성"""
    print("중립적인 응답 생성 중 ...")
    response = "그렇군요. 더 이야기하고 싶은 것이 있나요?"
    print(f"생성된 응답: {response}")
    return {"response": response}

def route_by_emotion(state: EmotionBotState) -> Literal["positive_response", "negative_response", "neutral_response"]:
    """감정에 따라 다음 노드 결정"""
    emotion = state.emotion
    print(f"감정에 따른 라우팅 중 ... 감정: {emotion}")
    if emotion == "positive":
        return "positive_response"
    elif emotion == "negative":
        return "negative_response"
    else:
        return "neutral_response"

# 그래프 생성 함수 - 전체 워크플로 구성
def create_emotion_bot_graph():
    workflow = StateGraph(EmotionBotState)

    # 노드 추가 - 각 처리 단계 그래프 등록
    workflow.add_node("analyze_emotion", analyze_emotion)
    workflow.add_node("positive_response", generate_positive_response)
    workflow.add_node("negative_response", generate_negative_response)
    workflow.add_node("neutral_response", generate_neutral_response)

    # 시작점 설정
    workflow.add_edge(START, "analyze_emotion")

    # 조건부 라우팅 에지 추가
    workflow.add_conditional_edges("analyze_emotion",
                                   route_by_emotion,
                                   {
                                        "positive_response": "positive_response",
                                        "negative_response": "negative_response",
                                        "neutral_response": "neutral_response"
                                   }
                               )

    # 종료 에지 추가
    workflow.add_edge("positive_response", END)
    workflow.add_edge("negative_response", END)
    workflow.add_edge("neutral_response", END)

    return workflow.compile()

def main():
    print("Emotion Bot with Conditional Routing Example")
    app = create_emotion_bot_graph()

    test_case = [
        "오늘 정말 기분이 좋아요!",  # 긍정적인 메시지
        "요즘 너무 힘들어요.",    # 부정적인 메시지
        "그냥 그렇네요."         # 중립적인 메시지
    ]

    for i, message in enumerate(test_case, 1):
        print(f"\n--- 테스트 케이스 {i}: '{message}' ---")
        initial_state = EmotionBotState(user_message=message)
        print(f"초기 상태: {initial_state}")
        print("그래프 실행 중 ...")

        # 그래프 실행
        final_state = app.invoke(initial_state)
        print(f"최종 상태: {final_state}")
        print(f"봇 응답: {final_state['response']}")

    # 그래프 시각화
    mermaid_png = app.get_graph().draw_mermaid_png()
    with open("emotion_bot_graph.png", "wb") as f:
        f.write(mermaid_png)
    print("그래프 다이어그램이 'emotion_bot_graph.png'로 저장되었습니다.")

if __name__ == "__main__":
    main()
