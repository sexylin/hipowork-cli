"""把本地 token 仓库同步到浏览器 localStorage（生成注入负载）。

场景：Agent 使用 headless 浏览器访问 hipowork.com 前端时，浏览器自身的
localStorage 不持久。本命令把本地仓库（~/.hipo_mcp_tokens.json）中的
token 转成 base64 注入负载，由 Agent 写入浏览器 localStorage 后，
下次打开页面即可直接看到登录态，无需重新走邮箱验证码。

输出（4 个 base64 值，不含明文 token）：
  AT=  access_token（base64）
  RT=  refresh_token（base64）
  CID= client_id（base64）
  EXP= expires_at 时间戳（毫秒）

注入目标（浏览器 console）：
  localStorage.setItem("access_token", AT 解码值)
  localStorage.setItem("refresh_token", RT 解码值)
  localStorage.setItem("oauth_client_id", CID 解码值)
  localStorage.setItem("oauth_expires_at", EXP)

用法：
  python3 hipo_token_sync.py               # 有效则直接输出，过期自动刷新
  python3 hipo_token_sync.py --refresh     # 强制刷新后再输出
  python3 hipo_token_sync.py --file /path/to/tokens.json
"""
from __future__ import annotations

import argparse
import base64
import sys
import time

from hipo_auth import TokenStore, ensure_valid_token, require_py310


def _b64(v: str) -> str:
    return base64.b64encode(v.encode()).decode()


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="把本地 token 同步到浏览器 localStorage（生成注入负载）")
    parser.add_argument("--refresh", action="store_true", help="强制刷新 token 后再输出")
    parser.add_argument("--file", default=None, help="token 仓库文件路径（默认 ~/.hipo_mcp_tokens.json）")
    parser.add_argument("--origin", default="https://hipowork.com", help="注入目标 origin（默认 hipowork.com）")
    args = parser.parse_args()

    store = TokenStore(args.file)
    if not store.exists():
        print("❌ 未找到 token 仓库，请先运行 hipo_authorize.py 完成授权。", file=sys.stderr)
        return 1

    try:
        tokens = ensure_valid_token(store, force=args.refresh)
    except (ValueError, RuntimeError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    client_info = store.client_info()
    if not client_info.get("client_id"):
        print("❌ 仓库中缺少 client_id，请重新运行 hipo_authorize.py 授权。", file=sys.stderr)
        return 1

    if args.refresh:
        print("✅ token 已刷新并写回仓库。")

    expires_at = str(int((time.time() + int(tokens.get("expires_in", 3600))) * 1000))
    print("\n=== 浏览器注入负载（base64）===")
    print("AT=" + _b64(tokens["access_token"]))
    print("RT=" + _b64(tokens["refresh_token"]))
    print("CID=" + _b64(client_info["client_id"]))
    print("EXP=" + expires_at)
    print(f"\n=== 注入目标 ===\norigin: {args.origin}\n"
          "keys: access_token / refresh_token / oauth_client_id / oauth_expires_at")
    return 0


if __name__ == "__main__":
    sys.exit(main())
