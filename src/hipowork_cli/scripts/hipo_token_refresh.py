"""强制刷新本地 token 仓库中的 access_token（用 refresh_token 轮换）。

用法：
  python3 hipo_token_refresh.py
  python3 hipo_token_refresh.py --file /path/to/tokens.json
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, ensure_valid_token, require_py310


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="刷新 HiPo Work access_token")
    parser.add_argument("--file", default=None, help="token 仓库文件路径（默认 ~/.hipo_mcp_tokens.json）")
    args = parser.parse_args()

    store = TokenStore(args.file)
    if not store.exists():
        print("❌ 未找到 token 仓库，请先运行 hipo_authorize.py 完成授权。")
        return 1

    try:
        tokens = ensure_valid_token(store, force=True)
        print("✅ token 已刷新并写回仓库。")
        print(f"   scope: {tokens.get('scope', '?')}")
        return 0
    except ValueError as exc:
        print(f"❌ {exc}")
        return 1
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
