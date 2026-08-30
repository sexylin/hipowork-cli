"""查看本地 token 仓库状态。

用法：
  python3 hipo_token_status.py
  python3 hipo_token_status.py --file /path/to/tokens.json
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, print_token_summary, require_py310


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="查看 HiPo Work 本地 token 状态")
    parser.add_argument("--file", default=None, help="token 仓库文件路径（默认 ~/.hipo_mcp_tokens.json）")
    args = parser.parse_args()

    store = TokenStore(args.file)
    if not store.exists():
        print("❌ 未找到 token 仓库，请先运行 hipo_authorize.py 完成授权。")
        print(f"   仓库路径: {store.path}")
        return 1

    print(f"token 仓库: {store.path}")
    print_token_summary(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
