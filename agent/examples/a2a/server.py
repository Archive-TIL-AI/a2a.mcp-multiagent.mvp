import uvicorn
from fastapi import FastAPI

# a2a SDK
import a2a
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.events.in_memory_queue_manager import InMemoryQueueManager
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.tasks.task_updater import TaskUpdater

# 타입/헬퍼
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentProvider
from a2a.types import Message, Role
from a2a.utils.message import new_agent_text_message


# ──────────────────────────────
# Skill 정의 (버전별 필드 대응)
# ──────────────────────────────
def build_skill_echo() -> AgentSkill:
    fields = getattr(AgentSkill, "model_fields", {})
    kw = dict(id="echo", name="Echo", description="Return 'pong'")
    if "tags" in fields: kw["tags"] = ["echo"]
    if "input_modes" in fields: kw["input_modes"] = ["text"]
    if "output_modes" in fields: kw["output_modes"] = ["text"]
    if "examples" in fields: kw["examples"] = []
    return AgentSkill(**kw)


# ──────────────────────────────
# Executor: 입력 무시하고 pong 반환
# ──────────────────────────────
class EchoExecutor(AgentExecutor):
    async def execute(self, context, event_queue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()

        try:
            # 헬퍼가 있으면 그대로 사용
            reply = new_agent_text_message(
                text="pong",
                context_id=context.context_id,
                task_id=context.task_id,
            )
        except Exception:
            # 헬퍼 불가 → 수동 생성
            import uuid
            fields = getattr(Message, "model_fields", {})

            # 키 이름 결정
            id_key   = "messageId"  if "messageId"  in fields else ("message_id"  if "message_id"  in fields else None)
            ctx_key  = "contextId"  if "contextId"  in fields else ("context_id"  if "context_id"  in fields else None)
            task_key = "taskId"     if "taskId"     in fields else ("task_id"     if "task_id"     in fields else None)

            # 공통 필드
            msg_kwargs = {
                "role": Role.agent,
                "parts": [{"type": "text", "text": "pong"}],
            }
            if id_key:   msg_kwargs[id_key]   = str(uuid.uuid4())
            if ctx_key:  msg_kwargs[ctx_key]  = context.context_id
            if task_key: msg_kwargs[task_key] = context.task_id

            reply = Message(**msg_kwargs)

        await updater.complete(message=reply)

    async def cancel(self, context, event_queue):
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.cancel()


# ──────────────────────────────
# AgentCard 정의 (필수 필드 대응)
# ──────────────────────────────
def build_agent_card() -> AgentCard:
    fields = getattr(AgentCard, "model_fields", {})
    kw = dict(
        name="Echo Agent",
        description="Minimal a2a-sdk echo agent that replies 'pong'",
        provider=AgentProvider(organization="Example", url="https://example.org"),
        url="http://localhost:8000/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=True),
        skills=[build_skill_echo()],
    )
    if "defaultInputModes" in fields: kw["defaultInputModes"] = ["text"]
    if "default_input_modes" in fields: kw["default_input_modes"] = ["text"]
    if "defaultOutputModes" in fields: kw["defaultOutputModes"] = ["text"]
    if "default_output_modes" in fields: kw["default_output_modes"] = ["text"]
    return AgentCard(**kw)


# ──────────────────────────────
# 서버 조립
# ──────────────────────────────
agent_card = build_agent_card()
task_store = InMemoryTaskStore()
queue_manager = InMemoryQueueManager()
executor = EchoExecutor()
handler = DefaultRequestHandler(agent_executor=executor, task_store=task_store, queue_manager=queue_manager)

a2a_app = A2AFastAPIApplication(agent_card=agent_card, http_handler=handler)
app: FastAPI = a2a_app.build()

print("a2a version:", getattr(a2a, "__version__", "unknown"))

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
