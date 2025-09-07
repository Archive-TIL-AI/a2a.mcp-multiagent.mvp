import asyncio, uuid, httpx, json
from a2a.client.card_resolver import A2ACardResolver
from a2a.client.client_factory import ClientFactory
from a2a.client.client import ClientConfig
from a2a.types import Role, Message

BASE_URL = "http://127.0.0.1:8000"

def build_user_msg(text: str) -> Message:
    fields = getattr(Message, "model_fields", {})
    kw = {"role": Role.user, "parts": [{"type": "text", "text": text}]}
    if "messageId" in fields: kw["messageId"] = str(uuid.uuid4())
    if "message_id" in fields: kw["message_id"] = str(uuid.uuid4())
    return Message(**kw)

def pick_text_from_parts(parts):
    """
    parts가 dict 또는 Pydantic 모델(Part/TextPart)인 두 경우 모두 지원.
    - dict: {"kind": "text", "text": "..."}
    - model: Part(root=TextPart(kind="text", text="..."))
    """
    texts = []
    for p in parts or []:
        # 1) dict 형태
        if isinstance(p, dict):
            kind = p.get("kind") or p.get("type")
            if kind == "text" and "text" in p:
                texts.append(p["text"])
            continue

        # 2) Pydantic 모델 형태 (Part -> root -> TextPart)
        #    안전하게 getattr로 탐색
        root = getattr(p, "root", None)
        if root is not None:
            kind = getattr(root, "kind", None)
            text = getattr(root, "text", None)
            if kind == "text" and text:
                texts.append(text)
                continue

        # 3) 혹시 모델이 바로 TextPart인 경우 (root 없이)
        kind = getattr(p, "kind", None)
        text = getattr(p, "text", None)
        if kind == "text" and text:
            texts.append(text)

    return " ".join(texts) if texts else None


def pretty(o):
    try:
        if hasattr(o, "model_dump"):
            return json.dumps(o.model_dump(), ensure_ascii=False, indent=2)
        if isinstance(o, dict):
            return json.dumps(o, ensure_ascii=False, indent=2)
        return str(o)
    except Exception:
        return repr(o)

async def main():
    async with httpx.AsyncClient(timeout=10.0) as http:
        # 1) agent-card 로드
        resolver = A2ACardResolver(httpx_client=http, base_url=BASE_URL)
        card = await resolver.get_agent_card()

        # 2) 클라이언트 생성
        client = ClientFactory(ClientConfig(streaming=True)).create(card)

        # 3) 메시지 전송
        user_msg = build_user_msg("ping")
        async for ev in client.send_message(user_msg):
            # 튜플 형태면 풀기
            payload = ev[1] if isinstance(ev, tuple) and len(ev) >= 2 else ev
            ev_type = ev[0] if isinstance(ev, tuple) and len(ev) >= 1 else type(payload).__name__

            print("—— 이벤트 수신 ——")
            print("type :", ev_type)
            print("payload:", pretty(payload))

            # (A) payload 자체가 Message 형태
            if hasattr(payload, "parts") or (isinstance(payload, dict) and "parts" in payload):
                text = pick_text_from_parts(getattr(payload, "parts", []))
                if text:
                    print("🎉 [final]", text)

            # (B) Status 이벤트 안에 최종 메시지가 포함된 경우
            status = getattr(payload, "status", None) or (payload.get("status") if isinstance(payload, dict) else None)
            if status:
                msg = getattr(status, "message", None) or (status.get("message") if isinstance(status, dict) else None)
                if msg:
                    parts = getattr(msg, "parts", None) or (msg.get("parts") if isinstance(msg, dict) else None)
                    text = pick_text_from_parts(parts)
                    if text:
                        print("🎉 [final]", text)

        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
