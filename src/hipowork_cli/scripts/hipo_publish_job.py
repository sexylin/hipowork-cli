"""招聘方：发布招聘岗位（对应 MCP 工具 publish_job）。

支持两种方式：
1. --json <file>：传入结构化岗位 JSON 文件（含 required/preferred/salary/benefits）
2. --text "<岗位描述>"：传自然语言描述，由后端解析为结构化条件

用法：
  python3 hipo_publish_job.py --title "Python 后端" --text "成都 Python/FastAPI 后端，3年以上经验，高并发优先" --salary-min 20 --salary-max 35
  python3 hipo_publish_job.py --json job.json
  python3 hipo_publish_job.py --json job.json --account <account_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import HipiError, check_role, print_json, publish_job


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
    parser = argparse.ArgumentParser(description="招聘方：发布招聘岗位")
    parser.add_argument("--title", default="", help="岗位标题")
    parser.add_argument("--text", default="", help="自然语言岗位描述（后端自动解析为结构化条件）")
    parser.add_argument("--json", default="", help="结构化岗位 JSON 文件路径")
    parser.add_argument("--salary-min", type=int, default=None, help="月薪下限（k）")
    parser.add_argument("--salary-max", type=int, default=None, help="月薪上限（k）")
    parser.add_argument("--salary-unit", choices=["monthly", "yearly"], default=None, help="薪资单位（缺省时取 JSON 的 salary_unit，再无则 monthly）")
    parser.add_argument("--benefit", action="append", default=[], help="福利标签（可重复）")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    parser.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")
    args = parser.parse_args()

    store = TokenStore(args.file)

    if not args.title:
        print("❌ 缺少 --title 岗位标题。", file=sys.stderr)
        return 2

    job_data: dict = {"title": args.title}
    if args.json:
        extra = _load_json_file(args.json)
        job_data.update(extra)
    job_data.setdefault("required", [])
    job_data.setdefault("preferred", {})

    try:
        role = check_role(store, args.account)
        if role and role != "employer":
            print(f"⚠️  当前账户角色是 {role}，发布岗位是招聘方(employer)功能，后端会拒绝。", file=sys.stderr)

        resp = publish_job(
            title=job_data["title"],
            required=job_data.get("required") or None,
            preferred=job_data.get("preferred") or None,
            raw_text=args.text or job_data.get("raw_text", ""),
            salary_min=args.salary_min if args.salary_min is not None else job_data.get("salary_min"),
            salary_max=args.salary_max if args.salary_max is not None else job_data.get("salary_max"),
            # 修复：CLI 未显式传 --salary-unit 时回退到 JSON 的 salary_unit，再无则 monthly。
            # 此前只传 args.salary_unit（默认 monthly），JSON 里的 yearly 被静默丢弃。
            salary_unit=args.salary_unit or job_data.get("salary_unit") or "monthly",
            benefits=args.benefit or job_data.get("benefits") or None,
            store=store,
            account_id=args.account,
        )
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        print_json(resp)
        return 0

    print(f"\n✅ 岗位已发布: {resp.get('title')}")
    if resp.get("location"):
        print(f"   地点: {resp.get('location')}")
    print(f"   job_id: {resp.get('job_id')}")
    print(f"   下一步匹配: {resp.get('please_run_match', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
