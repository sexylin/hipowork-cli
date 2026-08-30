"""HiPo Work 多账户管理。

token 仓库（~/.hipo_mcp_tokens.json）按多账户设计：每个邮箱/角色一条，
可列出、切换默认账户、删除账户。

用法：
  python3 hipo_accounts.py list
  python3 hipo_accounts.py current
  python3 hipo_accounts.py switch <account_id>
  python3 hipo_accounts.py delete <account_id>
  python3 hipo_accounts.py --file /path/to/tokens.json list
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hipo_auth import TokenStore, require_py310


def _short_id(account_id: str) -> str:
    return account_id if len(account_id) <= 40 else account_id[:40] + "…"


def cmd_list(store: TokenStore) -> int:
    accounts = store.accounts()
    default = store.default_account()
    if not accounts:
        print("（空）暂无账户。请先运行 hipo_authorize.py / hipo.py authorize 完成授权。")
        return 0
    print(f"token 仓库: {store.path}")
    print(f"默认账户: {default or '（未设置）'}\n")
    print(f"{'账户':<44} {'角色':<10} {'邮箱'}")
    print("-" * 88)
    for aid, acc in accounts.items():
        marker = "→" if aid == default else " "
        role = acc.get("role") or "?"
        email = acc.get("email") or "?"
        print(f"{marker} {_short_id(aid):<42} {role:<10} {email}")
    print("\n提示: 用 `switch <account_id>` 切换默认账户；用 `delete <account_id>` 删除。")
    return 0


def cmd_current(store: TokenStore) -> int:
    default = store.default_account()
    if not default:
        print("（未设置默认账户）")
        return 1
    acc = store.get_account()
    if not acc:
        print(f"默认账户 {default} 不存在于仓库。")
        return 1
    print(f"默认账户: {default}")
    print(f"  邮箱: {acc.get('email') or '?'}")
    print(f"  角色: {acc.get('role') or '?'}")
    tokens = acc.get("tokens") or {}
    print(f"  access_token: {'有' if tokens.get('access_token') else '无'}")
    print(f"  refresh_token: {'有' if tokens.get('refresh_token') else '无'}")
    return 0


def cmd_switch(store: TokenStore, account_id: str) -> int:
    if account_id not in store.accounts():
        print(f"❌ 账户 {account_id} 不存在。可运行 `list` 查看现有账户。")
        return 1
    store.set_account(account_id, store.accounts()[account_id], make_default=True)
    print(f"✅ 默认账户已切换为 {account_id}")
    return 0


def cmd_delete(store: TokenStore, account_id: str) -> int:
    if account_id not in store.accounts():
        print(f"❌ 账户 {account_id} 不存在。")
        return 1
    acc = store.accounts()[account_id]
    if input(f"确认删除账户 {account_id}（{acc.get('email') or '?'}）？[y/N] ").strip().lower() != "y":
        print("已取消。")
        return 0
    del store._data["accounts"][account_id]  # noqa: SLF001
    if store.default_account() == account_id:
        rest = list(store.accounts().keys())
        store._data["default_account"] = rest[0] if rest else ""  # noqa: SLF001
    store._save()
    print(f"✅ 已删除账户 {account_id}")
    return 0


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="HiPo Work 多账户管理")
    parser.add_argument("--file", default=None, help="token 仓库文件路径（默认 ~/.hipo_mcp_tokens.json）")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="列出所有账户")
    sub.add_parser("current", help="显示当前默认账户")
    p_switch = sub.add_parser("switch", help="切换默认账户")
    p_switch.add_argument("account_id", help="目标账户 ID（可为邮箱）")
    p_delete = sub.add_parser("delete", help="删除账户")
    p_delete.add_argument("account_id", help="要删除的账户 ID")
    args = parser.parse_args()

    store = TokenStore(args.file)
    if args.action == "list":
        return cmd_list(store)
    if args.action == "current":
        return cmd_current(store)
    if args.action == "switch":
        return cmd_switch(store, args.account_id)
    if args.action == "delete":
        return cmd_delete(store, args.account_id)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
