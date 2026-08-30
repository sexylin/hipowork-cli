"""招聘方：人才市场分析（对应 MCP 工具 market_analysis）。

用法：
  python3 hipo_market.py --keyword python
  python3 hipo_market.py --industry tech --location 成都
  python3 hipo_market.py --keyword solidity --json
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import HipiError, check_role, market_analysis, print_json


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="招聘方：人才市场分析")
    parser.add_argument("--keyword", default="", help="技能关键词过滤")
    parser.add_argument("--industry", default="", help="行业过滤（tech/finance/medical/sales 等）")
    parser.add_argument("--location", default="", help="地点过滤")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    store = TokenStore(args.file)
    try:
        role = check_role(store, args.account)
        if role and role != "employer":
            print(f"⚠️  当前账户角色是 {role}，市场分析是招聘方(employer)功能。", file=sys.stderr)
        data = market_analysis(
            keyword=args.keyword or None,
            industry=args.industry or None,
            location=args.location or None,
            store=store,
            account_id=args.account,
        )
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(data)
        return 0

    filt = data.get("filter") or {}
    print(f"\n📊 市场分析（关键词: {filt.get('keyword') or '全部'} · "
          f"行业: {filt.get('industry') or '全部'} · 地点: {filt.get('location') or '全部'}）")
    print(f"候选人数: {data.get('candidate_count', 0)}\n")

    top_skills = data.get("top_skills") or []
    if top_skills:
        print("Top 技能:")
        for s in top_skills:
            print(f"  {s.get('skill')}: {s.get('count')} 人")

    top_locations = data.get("top_locations") or []
    if top_locations:
        print("\nTop 地点:")
        for loc in top_locations:
            print(f"  {loc.get('location')}: {loc.get('count')} 人")

    exp_dist = data.get("experience_distribution") or {}
    if exp_dist:
        print("\n经验分布:")
        for k, v in exp_dist.items():
            print(f"  {k}: {v} 人")

    insights = data.get("insights") or []
    if insights:
        print("\n洞察:")
        for i in insights:
            print(f"  · {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())