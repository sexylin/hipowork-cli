"""平台统计（对应 MCP 工具 get_stats）。

用法：
  python3 hipo_stats.py
  python3 hipo_stats.py --json
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import HipiError, get_stats, print_json


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="平台统计")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    store = TokenStore(args.file)
    try:
        data = get_stats(store=store, account_id=args.account)
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(data)
        return 0

    print(f"\n📈 平台统计")
    print(f"  候选人: {data.get('total_candidates', 0)}")
    print(f"  招聘方: {data.get('total_employers', 0)}")
    print(f"  活跃岗位: {data.get('active_jobs', 0)}")

    industries = data.get("industry_distribution") or []
    if industries:
        print("\n行业分布:")
        for i in industries:
            print(f"  {i.get('industry')}: {i.get('count')} 人")

    top_skills = data.get("top_skills") or []
    if top_skills:
        print("\nTop 技能:")
        for s in top_skills[:10]:
            print(f"  {s.get('skill')}: {s.get('count')} 人")
    return 0


if __name__ == "__main__":
    sys.exit(main())