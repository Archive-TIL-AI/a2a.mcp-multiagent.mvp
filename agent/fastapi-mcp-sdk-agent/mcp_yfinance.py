from __future__ import annotations

import os
import asyncio
import logging
from pathlib import Path
from shutil import which
import anyio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

# SDK (stdio_client 방식)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolRequest

# ───────── Logger ─────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("mcp")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s :: %(message)s", "%H:%M:%S"))
    logger.addHandler(h)
logger.setLevel(LOG_LEVEL)


def _resolve_uv_cmd() -> str:
    # 1) .env 지정 우선
    env_cmd = os.getenv("MCP_YF_CMD")
    if env_cmd:
        return env_cmd
    # 2) PATH 탐색
    found = which("uv")
    if found:
        return found
    # 3) macOS Homebrew 기본 경로 시도
    fallback = "/opt/homebrew/bin/uv"
    if Path(fallback).exists():
        return fallback
    raise RuntimeError("Cannot find 'uv' command. Set MCP_YF_CMD in .env or add uv to PATH.")


def _resolve_yf_dir() -> Path:
    # 1) .env 지정 우선
    env_dir = os.getenv("MCP_YF_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    # 2) 자동 추정: this_file = agent/mcp_yfinance.py → repo_root = parents[1]
    this_file = Path(__file__).resolve()
    repo_root = this_file.parents[1]  # a2a-mcp-multiagent-poc/
    guess = (repo_root / "mcp-server" / "yahoo-finance-mcp").resolve()
    return guess


class MCPProcessClient:
    """
    동작하는 패턴 기반 - context manager 방식만 사용
    """

    def __init__(self) -> None:
        self._active_context = None  # 활성 컨텍스트 매니저
        self._session = None
        self._lock = asyncio.Lock()

        self.timeout = float(os.getenv("MCP_CALL_TIMEOUT", "30"))

        self.uv_cmd = _resolve_uv_cmd()
        self.yf_dir = _resolve_yf_dir()

        # 환경변수 설정 (UV 가상환경 충돌 방지)
        self._env = os.environ.copy()
        self._env["PYTHONUNBUFFERED"] = "1"

        # UV 가상환경 충돌 방지
        if "VIRTUAL_ENV" in self._env:
            del self._env["VIRTUAL_ENV"]
        if "CONDA_DEFAULT_ENV" in self._env:
            del self._env["CONDA_DEFAULT_ENV"]

        if "/opt/homebrew/bin" not in self._env.get("PATH", ""):
            self._env["PATH"] = "/opt/homebrew/bin:" + self._env.get("PATH", "")

    def _preflight(self):
        if not self.yf_dir.is_dir():
            raise RuntimeError(f"[MCP] MCP_YF_DIR not found: {self.yf_dir}")
        server_py = self.yf_dir / "server.py"
        if not server_py.is_file():
            raise RuntimeError(f"[MCP] server.py not found at: {server_py}")

        logger.info("Preflight check passed")
        logger.info("  • uv=%s", self.uv_cmd)
        logger.info("  • yf_dir=%s", self.yf_dir)

    async def _create_session_context(self):
        """동작하는 패턴을 따라 컨텍스트 매니저 생성"""
        server = StdioServerParameters(
            command=self.uv_cmd,
            args=["--directory", str(self.yf_dir), "run", "server.py"],
            env=self._env,
        )

        # 동작하는 패턴: stdio_client를 컨텍스트 매니저로 사용
        return stdio_client(server)

    async def start(self) -> None:
        async with self._lock:
            if self._session is not None:
                logger.debug("Session already active")
                return

            self._preflight()
            logger.info("Starting MCP connection...")

            try:
                # 동작하는 패턴을 정확히 따라함
                self._active_context = await self._create_session_context()
                read, write = await self._active_context.__aenter__()

                # ClientSession을 context manager로 사용
                self._session = ClientSession(read, write)

                logger.info("Initializing session...")
                await self._session.initialize()

                logger.info("Session initialized successfully!")

                # 툴 확인
                try:
                    tools_resp = await self._session.list_tools()
                    tools = getattr(tools_resp, "tools", tools_resp)
                    tool_names = [t.name for t in tools] if tools else []
                    logger.info("Available tools: %s", tool_names)
                except Exception as e:
                    logger.warning("Tools check failed: %s", e)

            except Exception as e:
                logger.error("Failed to start MCP client: %s", e)
                await self._cleanup()
                raise

    async def _cleanup(self):
        """완전한 정리"""
        if hasattr(self, '_session_cm') and self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Session context exit warning: %s", e)
            self._session_cm = None

        self._session = None

        if self._active_context:
            try:
                await self._active_context.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Context cleanup warning: %s", e)
            self._active_context = None

    async def stop(self) -> None:
        async with self._lock:
            logger.info("Stopping MCP client...")
            await self._cleanup()
            logger.info("MCP client stopped")

    async def list_tools(self) -> Dict[str, Any]:
        if not self._session:
            await self.start()

        if not self._session:
            raise RuntimeError("Session not available")

        with anyio.fail_after(self.timeout):
            tools_resp = await self._session.list_tools()
        tools = getattr(tools_resp, "tools", tools_resp)
        return {t.name: {"description": getattr(t, "description", "")} for t in tools}

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self._session:
            await self.start()

        if not self._session:
            raise RuntimeError("Session not available")

        try:
            # MCP SDK의 call_tool 메서드는 name, arguments를 직접 받음
            with anyio.fail_after(self.timeout):
                resp = await self._session.call_tool(name, arguments)

            # 동작하는 코드와 동일한 응답 처리
            if hasattr(resp, 'content') and resp.content:
                out = []
                for c in resp.content:
                    if hasattr(c, "text") and c.text is not None:
                        out.append(c.text)
                    elif hasattr(c, "data") and c.data is not None:
                        out.append(c.data)
                    elif hasattr(c, "json") and c.json is not None:
                        out.append(c.json)
                    else:
                        out.append(str(c))
                return out if len(out) != 1 else out[0]

            return getattr(resp, 'structuredContent', None) or getattr(resp, 'content', None)

        except Exception as e:
            logger.error("call_tool(%s) failed: %s", name, e)
            raise


# 전역 인스턴스
mcp_client = MCPProcessClient()


@asynccontextmanager
async def ensure_mcp():
    """동작하는 패턴을 직접 사용하는 컨텍스트"""
    server = StdioServerParameters(
        command=mcp_client.uv_cmd,
        args=["--directory", str(mcp_client.yf_dir), "run", "server.py"],
        env=mcp_client._env,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session  # 세션 직접 반환


# 단독 테스트용
async def test_mcp():
    """단독 테스트"""
    try:
        logger.info("=== MCP 단독 테스트 시작 ===")

        # 동작하는 패턴을 정확히 따라함
        server = StdioServerParameters(
            command=mcp_client.uv_cmd,
            args=["--directory", str(mcp_client.yf_dir), "run", "server.py"],
            env=mcp_client._env,
        )

        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("Available tools:", [t.name for t in tools.tools])

                # 테스트 호출
                tool_names = [t.name for t in tools.tools]
                if "get_stock_info" in tool_names:
                    print("Calling get_stock_info...")
                    res = await session.call_tool("get_stock_info", {"ticker": "AAPL"})
                    content = res.structuredContent or res.content
                    print("AAPL result:", content)
                else:
                    print("get_stock_info tool not found")

        logger.info("=== MCP 단독 테스트 성공 ===")

    except Exception as e:
        logger.error("=== MCP 단독 테스트 실패: %s ===", e)
        # 더 자세한 에러 정보
        import traceback
        traceback.print_exc()
    finally:
        await mcp_client.stop()

if __name__ == "__main__":
    asyncio.run(test_mcp())