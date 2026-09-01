"""HiPo Work OAuth 授权 CLI。

发起 Authorization Code + PKCE 授权流程：
  1. 启动本地回调服务器（127.0.0.1:<port>/callback）
  2. 打印授权 URL 并尝试自动打开浏览器
  3. 用户在浏览器完成邮箱验证码登录（角色由本命令 --role 指定）
  4. 浏览器跳回本地回调 → SDK 换 token → 展示统一成功页 → 落盘到 token 仓库

用法：
  python3 hipo_authorize.py --role candidate
  python3 hipo_authorize.py --role employer --email you@example.com
  python3 hipo_authorize.py --role candidate --port 9000

依赖：pip install -r requirements.txt（mcp SDK）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hipo_auth import (
    DEFAULT_CALLBACK_PORT,
    DEFAULT_MCP_URL,
    TokenStore,
    require_py310,
)

# 统一成功页模板（随仓库分发，独立 HTML）
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "success.html"

# 成功页按角色填充的文案
ROLE_HINTS = {
    "employer": {
        "primary": "发布岗位 · 匹配候选人 · 市场分析",
        "steps": [
            "让 Agent 调用 publish_job，发布第一个招聘岗位",
            "用 search_candidates / match_candidates 智能匹配候选人",
            "用 market_analysis 查看人才供需趋势",
        ],
    },
    "candidate": {
        "primary": "导入简历 · 管理求职档案",
        "steps": [
            "让 Agent 调用 import_resume，导入你的简历",
            "Agent 会解析出工作经历、项目经历、教育经历",
            "用 match_jobs_for_me 查看为你匹配的岗位",
        ],
    },
    "default": {
        "primary": "在客户端中直接向 Agent 下达任务即可",
        "steps": [
            "求职者：让 Agent 导入你的简历（import_resume）",
            "招聘方：让 Agent 发布岗位、匹配候选人",
            "回到客户端，Agent 已自动获得访问权限",
        ],
    },
}

SCOPES = "profile candidate:read candidate:write employer:read employer:write"


class CallbackServer:
    """本地回调服务器：接收浏览器跳回，捕获 code + state，返回统一成功页。"""

    def __init__(self, port: int, role: str):
        self.port = port
        self.code: str | None = None
        self.state: str | None = None
        self.received = threading.Event()
        self._server: HTTPServer | None = None
        self._role = role

    def _page_html(self) -> bytes:
        hint = ROLE_HINTS.get(self._role, ROLE_HINTS["default"])
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        steps_html = "".join(
            f'<li><span class="dot"></span><span>{s}</span></li>' for s in hint["steps"]
        )
        html = html.replace("__PRIMARY__", hint["primary"]).replace("__STEPS__", steps_html)
        return html.encode("utf-8")

    def start(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/callback":
                    qs = parse_qs(parsed.query)
                    owner = self.server.owner  # type: ignore[attr-defined]
                    owner.code = qs.get("code", [None])[0]
                    owner.state = qs.get("state", [None])[0]
                    owner.received.set()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(owner._page_html())
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *args):  # noqa: D102
                pass

        self._server = HTTPServer(("127.0.0.1", self.port), Handler)
        self._server.owner = self  # type: ignore[attr-defined]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


async def redirect_handler(url: str) -> None:
    print("\n=== 请在浏览器完成授权（邮箱验证码登录）===")
    print("授权 URL:")
    print(url)
    print()
    try:
        webbrowser.open(url)
        print("(已尝试自动打开浏览器；若未打开请手动复制上面的 URL)")
    except Exception:
        pass


async def run(port: int, role: str, email: str) -> int:
    import httpx2
    from mcp import ClientSession
    from mcp.client.auth import OAuthClientProvider
    from mcp.client.streamable_http import streamable_http_client, create_mcp_http_client
    from mcp.shared.auth import OAuthClientMetadata, AuthorizationCodeResult

    cb = CallbackServer(port, role)
    cb.start()

    async def callback_handler() -> AuthorizationCodeResult:
        print("\n等待浏览器授权回调...")
        await asyncio.to_thread(cb.received.wait, 600)
        code, state = cb.code, cb.state
        if not code:
            raise RuntimeError("回调未收到授权码（可能超时或用户取消）")
        print(f"收到回调 code={code[:12]}... state={state[:12]}...")
        return AuthorizationCodeResult(code=code, state=state)

    metadata = OAuthClientMetadata(
        client_name="hipowork-cli",
        redirect_uris=[f"http://127.0.0.1:{port}/callback"],
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope=SCOPES,
    )

    store = TokenStore()
    oauth = OAuthClientProvider(
        server_url=DEFAULT_MCP_URL,
        client_metadata=metadata,
        storage=_StorageAdapter(store),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    print(f"连接 {DEFAULT_MCP_URL} ...")
    try:
        http_client = create_mcp_http_client(auth=oauth, timeout=httpx2.Timeout(30.0, read=600.0))
        async with http_client:
            async with streamable_http_client(DEFAULT_MCP_URL, http_client=http_client) as (read, write):
                async with ClientSession(read, write) as session:
                    init = await session.initialize()
                    print("\nMCP INIT OK")
                    print("  server:", init.server_info.name, init.server_info.version)
                    tools = await session.list_tools()
                    print(f"\nTOOLS ({len(tools.tools)}):")
                    for t in tools.tools:
                        first = (t.description or "").splitlines()[0]
                        print(f"  - {t.name}: {first}")

                    # token 已在 storage 落盘；补记 email/role 到账户信息。
                    # P1-12: 角色以服务端 /auth/me 返回的真实角色为准（本地 --role
                    # 只是授权页初选，服务端可能因角色选择页/已有档案而不同）。
                    acc = store.get_account()
                    if acc is not None:
                        if email:
                            acc["email"] = email
                        try:
                            from hipo_auth import api_request, DEFAULT_API_BASE
                            me = api_request("GET", "/auth/me", token=store.tokens().get("access_token"), api_base=DEFAULT_API_BASE)
                            server_role = str(me.get("role") or "").strip()
                            if server_role:
                                acc["role"] = server_role
                            if me.get("email"):
                                acc["email"] = me["email"]
                        except Exception as exc:  # noqa: BLE001
                            # /auth/me 不可用时回退到本地角色（降级但不阻塞授权完成）
                            print(f"  ⚠️ 读取服务端角色失败，回退本地角色: {type(exc).__name__}: {str(exc)[:200]}")
                            acc["role"] = role
                        store.set_account(store.default_account(), acc)

                    # CLI/MCP 授权成功 → 桥接 Web 登录态：自动打开 /oauth/handoff，
                    # 前端从 URL fragment 的 base64url payload 解码 token 写入 localStorage
                    # 并跳转角色 profile。fragment 不发送到服务器，token 不经后端中转。
                    try:
                        import base64 as _b64
                        toks = store.tokens()
                        cinfo = store.client_info()
                        if toks.get("access_token") and toks.get("refresh_token") and cinfo.get("client_id"):
                            payload_json = json.dumps({
                                "access_token": toks["access_token"],
                                "refresh_token": toks["refresh_token"],
                                "client_id": cinfo["client_id"],
                                "expires_in": toks.get("expires_in") or 900,
                            }).encode()
                            # base64url（无填充，与前端 atob 前补 '=' 的逻辑匹配）
                            payload_b64 = _b64.urlsafe_b64encode(payload_json).rstrip(b"=").decode()
                            handoff_url = f"https://www.hipowork.com/oauth/handoff#payload={payload_b64}"
                            webbrowser.open(handoff_url)
                            print("\n🌐 已在浏览器打开 HiPo Work Web 登录态并跳转到个人中心。")
                    except Exception as exc:  # noqa: BLE001
                        print(f"  ⚠️ 打开 Web 登录态失败（不影响 CLI 授权）：{type(exc).__name__}: {str(exc)[:200]}")

                    print("\n✅ 授权完成，token 已保存到本地仓库。")
                    print("   后续可用 hipo_token_status.py / hipo_token_sync.py / hipo_mcp_client.py 复用。")
                    return 0
    except Exception as exc:
        print(f"授权失败: {type(exc).__name__}: {str(exc)[:800]}")
        return 1
    finally:
        cb.stop()


class _StorageAdapter:
    """把 TokenStore 包装成 mcp SDK 的 TokenStorage 接口（async 方法）。"""

    def __init__(self, store: TokenStore):
        self.store = store

    async def get_tokens(self):
        d = self.store.tokens()
        if not d:
            return None
        if isinstance(d, dict):
            from mcp.server.auth.provider import OAuthToken
            return OAuthToken.model_validate(d)
        return d

    async def set_tokens(self, tokens):
        if hasattr(tokens, "model_dump"):
            tokens = tokens.model_dump(mode="json")
        self.store.save_tokens(dict(tokens))
        return None

    async def get_client_info(self):
        d = self.store.client_info()
        if not d:
            return None
        if isinstance(d, dict):
            from mcp.server.auth.provider import OAuthClientInformationFull
            return OAuthClientInformationFull.model_validate(d)
        return d

    async def set_client_info(self, client_info):
        if hasattr(client_info, "model_dump"):
            client_info = client_info.model_dump(mode="json")
        self.store.save_tokens({}, dict(client_info))
        return None


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="HiPo Work OAuth 授权")
    parser.add_argument("--role", choices=["candidate", "employer"], default="candidate",
                        help="账号角色（求职者 / 招聘方）")
    parser.add_argument("--email", default="", help="关联邮箱（写入 token 仓库，便于识别账户）")
    parser.add_argument("--port", type=int, default=DEFAULT_CALLBACK_PORT, help="本地回调端口")
    args = parser.parse_args()
    return asyncio.run(run(args.port, args.role, args.email))


if __name__ == "__main__":
    sys.exit(main())
