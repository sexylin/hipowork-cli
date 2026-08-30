"""HiPo Work 服务连通性检查（API / MCP / Embedding / OAuth metadata）。

只做连通性 + 基本响应校验，不做业务写操作。

用法：
  python3 hipo_healthcheck.py
  python3 hipo_healthcheck.py --timeout 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from hipo_auth import (
    DEFAULT_API_BASE,
    DEFAULT_MCP_URL,
    TokenStore,
    require_py310,
)

ENDPOINTS = [
    ("后端 API /health", "GET", f"{DEFAULT_API_BASE.replace('/api/v1', '')}/health", None),
    ("后端 API /auth/me", "GET", f"{DEFAULT_API_BASE}/auth/me", "token"),
    ("MCP 端点", "GET", f"{DEFAULT_MCP_URL}", None),
    ("OAuth authorization server metadata",
     "GET", "https://mcp.hipowork.com/.well-known/oauth-authorization-server", None),
    ("OAuth protected resource metadata",
     "GET", "https://mcp.hipowork.com/.well-known/oauth-protected-resource/mcp", None),
    # Embedding 服务无公网反代，仅服务器本机可达；从客户端探测通常失败，仅作提示
    ("Embedding 服务 /health (仅服务器本机)", "GET", "http://127.0.0.1:8002/health", None),
]

# 失败不阻断退出码的检查项（客户端机器上探测不到属正常）
NON_BLOCKING = {"Embedding 服务 /health (仅服务器本机)"}


def _request(method: str, url: str, token: str | None, timeout: int) -> tuple[int, str, str]:
    req = urllib.request.Request(url, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")[:500], ""
    except urllib.error.HTTPError as exc:
        return exc.code, "", exc.read().decode(errors="replace")[:300]
    except urllib.error.URLError as exc:
        return 0, "", str(exc.reason or exc)
    except Exception as exc:  # pragma: no cover
        return 0, "", str(exc)


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="HiPo Work 服务连通性检查")
    parser.add_argument("--timeout", type=int, default=8, help="单请求超时（秒）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    store = TokenStore()
    token = ""
    try:
        if store.exists():
            from hipo_mcp_client import get_access_token
            token = get_access_token(store)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️  token 仓库读取失败（仍继续检查公开端点）: {exc}", file=sys.stderr)

    results = []
    for name, method, url, need in ENDPOINTS:
        t0 = time.time()
        status, body, err = _request(method, url, token if need == "token" else None, args.timeout)
        elapsed = time.time() - t0
        # 连通性判定：拿到任何 HTTP 状态码（含 401/404）都算服务可达；
        # 只有网络错误/超时（status=0）才算不可达。带 token 的检查再叠加鉴权判定。
        reachable = bool(status)
        auth_ok = status == 200
        ok = reachable and (need != "token" or auth_ok)
        note = ""
        if reachable and not auth_ok and need == "token":
            note = f"（服务可达，鉴权{'通过' if status == 200 else '未通过: HTTP ' + str(status)}）"
        if not reachable and err:
            note = f"  {err[:120]}"
        results.append({"name": name, "ok": ok, "status": status,
                        "ms": int(elapsed * 1000), "detail": (err or body)[:160], "note": note})
        if args.json:
            continue
        mark = "✅" if ok else ("🟡" if reachable else "❌")
        print(f"{mark} {name}  [{status or 'ERR'}] {int(elapsed * 1000)}ms{note}")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        ok_count = sum(1 for r in results if r["ok"])
        print(f"\n{ok_count}/{len(results)} 项正常")
        if token:
            print("（已携带本地 OAuth token 检查 /auth/me）")
        else:
            print("（未找到本地 token，/auth/me 预计返回 401，可先运行 hipo authorize）")
    blocking_fail = []
    for r in results:
        if r["ok"] or r["name"] in NON_BLOCKING:
            continue
        # 无本地 token 时 /auth/me 的 401 属预期，非阻断；有 token 仍失败才算真问题
        if r["name"] == "后端 API /auth/me" and not token:
            continue
        blocking_fail.append(r)
    return 0 if not blocking_fail else 1


if __name__ == "__main__":
    sys.exit(main())