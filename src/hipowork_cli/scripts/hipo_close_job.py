"""招聘方：关闭已发布的招聘岗位（对应 MCP 工具 close_job）。

关闭后求职者无法再看到/投递该职位，也不再参与自动匹配。

用法：
  python3 hipo_close_job.py <job_id>
  python3 hipo_close_job.py <job_id> --account <account_id>
"""
from __future__ import annotations

import argparse
import sys

from hipo_auth import TokenStore, require_py310
from hipo_mcp_client import HipiError, check_role, close_job, print_json


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="招聘方：关闭已发布的招聘岗位")
    parser.add_argument("job_id", help="岗位 ID（发布时返回的 job_id）")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    parser.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")
    args = parser.parse_args()

    store = TokenStore(args.file)

    try:
        role = check_role(store, args.account)
        if role and role != "employer":
            print(f"⚠️  当前账户角色是 {role}，关闭岗位是招聘方(employer)功能，后端会拒绝。", file=sys.stderr)

        resp = close_job(args.job_id, store=store, account_id=args.account)
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        print_json(resp)
        return 0

    status = resp.get("status")
    if status == "closed":
        print(f"✅ 岗位已关闭: {resp.get('title') or args.job_id}")
        print(f"   job_id: {resp.get('id') or args.job_id}")
        print(f"   状态: {status}")
    else:
        print(f"⚠️  接口返回状态: {status}（预期 closed），请确认。", file=sys.stderr)
        print_json(resp)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
