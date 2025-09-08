from typing import Dict, Any

from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

# 1. 워크플로우 단계 정의
class WorkflowStep:
    GREETING = "GREETING"
    PROCESSING = "PROCESSING"

# 2. 그래프 상태 정의
class GraphState(BaseModel):
    name: str = Field(default="", description="사용자 이름")
    greeting: str = Field(default="", description="생성된 인사말")
    processed_message: str = Field(default="", description="처리된 메시지")

# 3. 첫번째 노드 함수
def generate_greeting(state: GraphState) -> Dict[str, Any]:
    name = state.name or "아무개"
    greeting = f"안녕하세요, {name}님! 만나서 반갑습니다."
    print(f"[generate_greeting] Generated greeting: {greeting}")
    return {"greeting": greeting}

# 4. 두번째 노드 함수: 인사말 처리하고 최종 메시지 생성
def process_message(state: GraphState) -> Dict[str, Any]:
    greeting = state.greeting
    processed_message = f"{greeting} 오늘도 좋은 하루 보내세요!"
    print(f"[process_message] Processed message: {processed_message}")
    return {"processed_message": processed_message}

def create_hello_graph():
    workflow = StateGraph(GraphState)

    # 노드 추가
    workflow.add_node(WorkflowStep.GREETING, generate_greeting)
    workflow.add_node(WorkflowStep.PROCESSING, process_message)

    # 시작점 설정
    workflow.add_edge(START, WorkflowStep.GREETING)

    # 에지 추가(노드 간 연결)
    workflow.add_edge(WorkflowStep.GREETING, WorkflowStep.PROCESSING)
    workflow.add_edge(WorkflowStep.GREETING, END)

    # 그래프 컴파일
    app = workflow.compile()

    return app

def main():
    print("Hello, LangGraph!")
    app = create_hello_graph()

    initial_state = GraphState(name="홍길동", greeting="", processed_message="")
    print(f"Initial State: {initial_state}")
    print("Running the graph...")

    # 그래프 실행
    final_state = app.invoke(initial_state)

    print(f"Final State: {final_state}")
    print(f"Processed Message: {final_state['processed_message']}")

    # ASCII 아트 출력
    app.get_graph().print_ascii()

# Spring Boot에서는 public static void main(String[] args) 가 앱 진입점이잖아요.
# → 파이썬에서는 if __name__ == "__main__": main() 이 진입점 역할을 해요.
if __name__ == "__main__":
    main()



