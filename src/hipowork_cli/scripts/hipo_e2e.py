"""HiPo Work 端到端冒烟测试：token → MCP 会话 → 工具调用全链路。

默认只做只读操作，不写数据。步骤：
1. 检查本地 token 仓库（无 token 提示先授权）
2. 与 MCP 服务建立会话（initialize + list_tools）
3. 按角色调用一个只读工具验证鉴权链路
   - employer: get_stats（平台统计）
   - candidate: match_jobs_for_me（岗位匹配）

用法：
  python3 hipo_e2e.py
  python3 hipo_e2e.py --skip-mcp   # 只验证本地 token 和 REST /auth/me
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from hipo_auth import (
    DEFAULT_MCP_URL,
    DEFAULT_API_BASE,
    TokenStore,
    api_request,
    require_py310,
)


def _check_token(store: TokenStore) -> str | None:
    from hipo_mcp_client import get_access_token
    return get_access_token(store)


async def _mcp_smoke(role: str | None) -> int:
    """通过 MCP SDK 建立会话并调用只读工具。"""
    import httpx2
    from mcp import ClientSession
    from mcp.client.auth import OAuthClientProvider
    from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client
    from mcp.shared.auth import OAuthClientMetadata

    store = TokenStore()
    token = _check_token(store)

    class _Storage:
        async def get_tokens(self):
            d = store.tokens()
            if not d:
                return None
            from mcp.server.auth.provider import OAuthToken
            return OAuthToken.model_validate(d)

        async def set_tokens(self, tokens):
            if hasattr(tokens, "model_dump"):
                tokens = tokens.model_dump(mode="json")
            store.save_tokens(dict(tokens))
            return None

        async def get_client_info(self):
            d = store.client_info()
            if not d:
                return None
            from mcp.server.auth.provider import OAuthClientInformationFull
            return OAuthClientInformationFull.model_validate(d)

        async def set_client_info(self, client_info):
            if hasattr(client_info, "model_dump"):
                client_info = client_info.model_dump(mode="json")
            store.save_tokens({}, dict(client_info))
            return None

    metadata = OAuthClientMetadata(
        client_name="hipowork-cli-e2e",
        redirect_uris=["http://127.0.0.1:8765/callback"],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope="profile candidate:read candidate:write employer:read employer:write",
    )
    oauth = OAuthClientProvider(
        server_url=DEFAULT_MCP_URL,
        client_metadata=metadata,
        storage=_Storage(),
    )
    token_was_used = False

    async with create_mcp_http_client(auth=oauth, timeout=httpx2.Timeout(30.0, read=600.0)) as http_client:
        async with streamable_http_client(DEFAULT_MCP_URL, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                print(f"  ✅ MCP INIT OK — {init.server_info.name} {init.server_info.version}")
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                print(f"  ✅ TOOLS ({len(names)}): {', '.join(names)}")

                tool_name = None
                if role == "employer":
                    tool_name = "get_stats"
                else:
                    tool_name = "match_jobs_for_me"
                if tool_name not in names:
                    print(f"  ⚠️ 工具 {tool_name} 不在列表中，跳过工具调用。")
                    return 1
                result = await session.call_tool(tool_name, {})
                print(f"  ✅ 调用 {tool_name} 成功: {str(result)[:300]}")
                return 0


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="HiPo Work 端到端冒烟测试")
    parser.add_argument("--skip-mcp", action="store_true", help="只验证 token + REST /auth/me")
    args = parser.parse_args()

    store = TokenStore()
    if not store.exists():
        print("❌ 未找到 token 仓库。请先运行 hipo authorize 完成授权。", file=sys.stderr)
        return 1

    print("== 1/3 本地 token ==")
    try:
        token = _check_token(store)
        role = store.role() or "candidate"
        print(f"  ✅ token 有效（角色: {role}, 邮箱: {store.email() or '?'}）")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ token 不可用: {exc}", file=sys.stderr)
        return 1

    print("\n== 2/3 REST /auth/me ==")
    try:
        me = api_request("GET", "/auth/me", token=token, api_base=DEFAULT_API_BASE)
        # P1-12: 以服务端真实角色为准（本地 store 角色可能因未同步而过期）
        server_role = str(me.get("role") or "").strip() or (store.role() or "candidate")
        print(f"  ✅ /auth/me OK — {me.get('email')} ({me.get('role')})")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ /auth/me 失败: {exc}", file=sys.stderr)
        return 1

    if args.skip_mcp:
        print("\n== 3/3 跳过（--skip-mcp）==")
        print("\n✅ 冒烟通过（token + REST 部分）。")
        return 0

    print("\n== 3/3 MCP 会话 ==")
    try:
        rc = asyncio.run(_mcp_smoke(server_role))
        print("\n✅ 端到端冒烟通过。")
        return rc
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ MCP 会话失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())