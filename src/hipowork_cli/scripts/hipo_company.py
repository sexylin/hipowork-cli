"""招聘方：管理企业主体信息（创建公司、指定默认公司、查询公司列表）。

用法：
  hipo company list
  hipo company create --name "成都灵羽科技" --desc "专注 AI Agent 基础设施研发" [--default]
  hipo company set-default <company_id>
"""
import argparse
import sys

from hipo_common import HipiError, require_py310
from hipo_mcp_client import TokenStore, check_role, create_company, list_companies, print_json, set_default_company


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="招聘方：企业主体信息管理")
    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # list
    sub_list = subparsers.add_parser("list", help="查看所有企业主体")
    sub_list.add_argument("--account", default=None, help="账户 ID")
    sub_list.add_argument("--file", default=None, help="token 仓库文件路径")
    sub_list.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")

    # create
    sub_create = subparsers.add_parser("create", help="创建企业主体")
    sub_create.add_argument("--name", required=True, help="公司名称")
    sub_create.add_argument("--desc", default="", help="公司简介")
    sub_create.add_argument("--default", action="store_true", help="是否设为默认企业主体")
    sub_create.add_argument("--account", default=None, help="账户 ID")
    sub_create.add_argument("--file", default=None, help="token 仓库文件路径")
    sub_create.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")

    # set-default
    sub_default = subparsers.add_parser("set-default", help="指定默认企业主体")
    sub_default.add_argument("company_id", help="企业主体 ID")
    sub_default.add_argument("--account", default=None, help="账户 ID")
    sub_default.add_argument("--file", default=None, help="token 仓库文件路径")
    sub_default.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        return 2

    store = TokenStore(args.file)
    role = check_role(store, args.account)
    if role and role != "employer":
        print(f"⚠️  当前账户角色是 {role}，企业管理是招聘方(employer)功能。", file=sys.stderr)

    try:
        if args.subcommand == "list":
            resp = list_companies(store=store, account_id=args.account)
            if args.json_out:
                print_json(resp)
            else:
                companies = resp.get("companies", [])
                print(f"🏢 名下共 {len(companies)} 个企业主体：\n")
                for c in companies:
                    default_tag = "【默认】" if c.get("is_default") else ""
                    print(f"- {c.get('company_name')} {default_tag}")
                    print(f"  ID: {c.get('id')}")
                    if c.get("description"):
                        print(f"  简介: {c.get('description')}")
                    print()

        elif args.subcommand == "create":
            resp = create_company(
                company_name=args.name,
                description=args.desc,
                is_default=args.default,
                store=store,
                account_id=args.account,
            )
            if args.json_out:
                print_json(resp)
            else:
                c = resp.get("company", {})
                print(f"✅ 公司创建成功: {c.get('company_name')}")
                print(f"  ID: {c.get('id')}")
                print(f"  默认: {'是' if c.get('is_default') else '否'}")

        elif args.subcommand == "set-default":
            resp = set_default_company(
                company_id=args.company_id,
                store=store,
                account_id=args.account,
            )
            if args.json_out:
                print_json(resp)
            else:
                c = resp.get("company", {})
                print(f"✅ 已成功将「{c.get('company_name')}」设为默认企业主体")

        return 0
    except HipiError as exc:
        print(f"❌ 操作失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
