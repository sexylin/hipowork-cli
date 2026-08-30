"""求职者：根据我的简历匹配岗位（对应 MCP 工具 match_jobs_for_me）。

用法：
  python3 hipo_match_jobs.py
  python3 hipo_match_jobs.py --json
  python3 hipo_match_jobs.py --account <account_id>
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import require_py310
from hipo_mcp_client import HipiError, check_role, match_jobs_for_me, print_json


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="求职者：根据我的简历匹配岗位")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--account", default=None, help="账户 ID（默认账户）")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    from hipo_auth import TokenStore
    store = TokenStore(args.file)

    try:
        role = check_role(store, args.account)
        if role and role != "candidate":
            print(f"⚠️  当前账户角色是 {role}，岗位匹配是求职者(candidate)功能，可能返回空结果。", file=sys.stderr)

        data = match_jobs_for_me(store, args.account, raw=args.json)
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(data)
        return 0

    print(f"\n📋 为你匹配到 {data.get('total_matches', 0)} 个岗位（今日还可投递 {data.get('daily_remaining', 0)} 次）\n")
    results = data.get("results") or []
    if not results:
        print("  暂无匹配岗位。可先导入简历（hipo_resume_import.py），或稍后再试。")
        return 0
    from hipo_mcp_client import print_job_result
    for r in results:
        print_job_result(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
