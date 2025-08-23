from pathlib import Path
from shutil import which
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

# 파일 실행 방법: python mcp_stdio_request.py

# 예) agent/examples/mcp_stdio_request.py 기준으로 repo 루트를 역행
REPO_ROOT = Path(__file__).resolve().parents[2]
YF_DIR = (REPO_ROOT / "mcp-server" / "yahoo-finance-mcp").resolve()  # ← 절대경로화

UV = which("uv")  # PATH에서 uv 찾기
if not UV:
    # macOS에서 /opt/homebrew/bin 이 PATH에 없을 수 있음
    UV = "/opt/homebrew/bin/uv"  # 필요 시 하드코딩 or 에러 처리

async def main():
    env = os.environ.copy()
    # (선택) PATH 보정: IDE에서 PATH가 짧을 때
    if "/opt/homebrew/bin" not in env.get("PATH", ""):
        env["PATH"] = "/opt/homebrew/bin:" + env.get("PATH", "")

    server = StdioServerParameters(
        command=UV,
        args=["--directory", str(YF_DIR), "run", "server.py"],  # ← 여기 REL/ABS 모두 OK, 지금은 ABS
        env=env,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

            res = await session.call_tool("get_stock_info", {"ticker": "AAPL"})
            print(res.structuredContent or res.content)

asyncio.run(main())