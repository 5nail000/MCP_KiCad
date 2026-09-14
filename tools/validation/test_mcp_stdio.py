"""One-shot MCP stdio smoke test (initialize + tools/list)."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _run() -> int:
    root = _repo_root()
    params = StdioServerParameters(
        command=str(root / ".venv" / "Scripts" / "python.exe"),
        args=["-m", "kicad_ai.mcp.server"],
        env={**os.environ, "KICAD_AI_WORKSPACE": str(root)},
        cwd=str(root),
    )
    started = time.time()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            elapsed = round(time.time() - started, 2)
            tools = await session.list_tools()
            count = len(tools.tools)
            print(f"OK initialize in {elapsed}s")
            print(f"OK tools/list: {count} tools")
            return 0 if count > 0 else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
