"""招聘方：结构化条件匹配候选人（对应 MCP 工具 match_candidates）。

支持从 JSON 文件读结构化条件，或用自然语言（--text，走 /agent/match-candidates
的 query_text 分支，后端解析为结构化检索）。

用法：
  python3 hipo_match_candidates.py --json cond.json
  python3 hipo_match_candidates.py --text "成都 Python 后端，3年以上经验，高并发优先" --max 10
  python3 hipo_match_candidates.py --job <job_id>      # 等价 match_job_requirement
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import (
    HipiError,
    check_role,
    match_candidates,
    match_job_requirement,
    print_candidate_result,
    print_json,
)


def _load_json_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise HipiError(f"文件不存在: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HipiError(f"JSON 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise HipiError("JSON 根节点必须是对象")
    return data


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="招聘方：结构化/自然语言匹配候选人")
    parser.add_argument("--json", default="", help="结构化条件 JSON 文件路径")
    parser.add_argument("--text", default="", help="自然语言匹配描述")
    parser.add_argument("--job", default="", help="对已发布岗位 job_id 自动匹配")
    parser.add_argument("--max", type=int, default=10, help="最大返回数（默认 10）")
    parser.add_argument("--json-out", action="store_true", help="输出原始 JSON")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    store = TokenStore(args.file)
    try:
        role = check_role(store, args.account)
        if role and role != "employer":
            print(f"⚠️  当前账户角色是 {role}，匹配候选人是招聘方(employer)功能。", file=sys.stderr)

        if args.job:
            data = match_job_requirement(args.job, max_results=args.max, store=store, account_id=args.account)
        elif args.json:
            cond = _load_json_file(args.json)
            data = match_candidates(
                required=cond.get("required"),
                preferred=cond.get("preferred"),
                query_text=cond.get("query_text"),
                max_results=args.max,
                store=store,
                account_id=args.account,
            )
        elif args.text:
            data = match_candidates(
                query_text=args.text,
                max_results=args.max,
                store=store,
                account_id=args.account,
            )
        else:
            print("❌ 请提供 --json、--text 或 --job 之一。", file=sys.stderr)
            return 2
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        print_json(data)
        return 0

    print(f"\n🎯 匹配到 {len(data.get('results') or [])} 个候选人（过滤后 {data.get('total_hard_filtered', '?')} 人）\n")
    results = data.get("results") or []
    if not results:
        print("  没有匹配候选人。")
        return 0
    for r in results:
        print_candidate_result(r)
    ai_summary = data.get("ai_summary")
    if ai_summary:
        print(f"\n  AI 摘要: {ai_summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
