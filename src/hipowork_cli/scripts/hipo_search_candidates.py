"""招聘方：自然语言搜索候选人（对应 MCP 工具 search_candidates）。

用法：
  python3 hipo_search_candidates.py "成都 Python 后端 3 年经验"
  python3 hipo_search_candidates.py --query "..." --max 20 --json
  python3 hipo_search_candidates.py --account <account_id>
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import (
    HipiError,
    check_role,
    print_candidate_result,
    print_json,
    search_candidates,
)


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="招聘方：自然语言搜索候选人")
    parser.add_argument("query", nargs="*", default="", help="搜索描述（也可用 --query）")
    parser.add_argument("--query", dest="query_opt", default="", help="搜索描述")
    parser.add_argument("--max", type=int, default=10, help="最大返回数（默认 10）")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    query = " ".join(args.query) or args.query_opt
    if not query.strip():
        print("❌ 缺少搜索描述。例如: hipo_search_candidates.py \"成都 Python 后端\"", file=sys.stderr)
        return 2

    store = TokenStore(args.file)
    try:
        role = check_role(store, args.account)
        if role and role != "employer":
            print(f"⚠️  当前账户角色是 {role}，搜索候选人是招聘方(employer)功能。", file=sys.stderr)
        data = search_candidates(query, max_results=args.max, store=store, account_id=args.account)
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(data)
        return 0

    print(f"\n🔍 搜索: {data.get('query_summary', query)}")
    print(f"硬条件过滤后: {data.get('total_hard_filtered', '?')} 人，返回 Top {len(data.get('results') or [])}\n")
    results = data.get("results") or []
    if not results:
        print("  没有匹配候选人。可调整条件后重试。")
        return 0
    for r in results:
        print_candidate_result(r)
    ai_summary = data.get("ai_summary")
    if ai_summary:
        print(f"\n  AI 摘要: {ai_summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())