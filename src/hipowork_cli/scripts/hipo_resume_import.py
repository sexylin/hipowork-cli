"""简历导入（校验 + 导入一步完成，对应 MCP 工具 import_resume）。

两种模式：
1. --json <file>：直接导入 Agent/LLM 解析好的结构化简历 JSON（推荐）
2. --text <file>：传入简历纯文本/PDF 提取文本，调用后端批量解析接口
   （POST /agent/batch-parse-resumes）解析后导入；若平台未部署 AI 服务，
   会提示改用 --json 由你自己的 LLM 先解析。

导入前自动跑 hipo_resume_validate 的规则（字段缺失/类型/长度/数量），
通过后才调用后端写入。

用法：
  python3 hipo_resume_import.py --json resume.json
  python3 hipo_resume_import.py --json resume.json --account <account_id>
  python3 hipo_resume_import.py --text resume.txt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hipo_auth import TokenStore, api_request, require_py310
from hipo_mcp_client import HipiError, check_role, get_access_token, import_resume, print_json
from hipo_resume_validate import validate


def _load(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise HipiError(f"文件不存在: {p}")
    return p.read_text(encoding="utf-8", errors="replace")


def _is_empty_resume(resume: dict) -> bool:
    """判断解析结果是否"全空"——用于防止后端 AI 解析返回空结构时，
    import-resume 先清空旧数据再写入空数据，误删用户原有简历。"""
    basic = resume.get("basic_info") or {}
    if isinstance(basic, dict):
        if any(basic.get(f) for f in ("name", "phone", "location", "headline",
                                      "summary", "industry")):
            return False
    for key in ("work_experiences", "projects", "education", "skills",
                "certificates", "languages"):
        items = resume.get(key)
        if isinstance(items, list) and items:
            return False
    return True


def _guard_empty(resume: dict) -> None:
    """全空简历直接拒绝导入（避免清空用户已有简历）。"""
    if _is_empty_resume(resume):
        raise HipiError(
            "后端解析结果为空（无基本信息/经历/技能）。为保护已有简历已拒绝导入；"
            "请提供更完整的简历文本，或用 --json 传入由你确认过的结构化 JSON。"
        )


def _parse_via_backend(text: str, store: TokenStore, account_id: str | None) -> dict:
    """调用后端 /agent/batch-parse-resumes 解析（平台需部署 AI 服务）。"""
    token = get_access_token(store, account_id)
    try:
        resp = api_request(
            "POST", "/agent/batch-parse-resumes",
            token=token, body={"resumes": [text]},
        )
    except RuntimeError as exc:
        if "503" in str(exc):
            raise HipiError(
                "平台未部署 AI 简历解析服务。请用你自己的 LLM 将简历解析为结构化"
                " JSON 后，改用 --json 导入。"
            ) from exc
        raise HipiError(str(exc)) from exc
    results = resp.get("results") or []
    if not results:
        raise HipiError(f"后端解析无返回: {resp}")
    item = results[0]
    if not item.get("ok"):
        raise HipiError(f"后端解析失败: {item.get('error')}")
    data = item.get("data") or {}
    # 兼容两种返回形态：直接含 basic_info，或套一层 extracted_data
    parsed = data.get("extracted_data") if isinstance(data, dict) and "extracted_data" in data else data
    if not isinstance(parsed, dict):
        raise HipiError(f"后端解析结果结构异常: {str(parsed)[:200]}")
    return parsed


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="简历导入（校验 + 写入）")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--json", default="", help="结构化简历 JSON 文件路径")
    g.add_argument("--text", default="", help="简历纯文本/提取文本文件路径（走后端 AI 解析）")
    parser.add_argument("--skip-validate", action="store_true", help="跳过本地校验直接导入")
    parser.add_argument("--json-out", action="store_true", help="输出原始 JSON 响应")
    parser.add_argument("--account", default=None, help="账户 ID")
    parser.add_argument("--file", default=None, help="token 仓库文件路径")
    args = parser.parse_args()

    store = TokenStore(args.file)
    try:
        role = check_role(store, args.account)
        if role and role != "candidate":
            print(f"⚠️  当前账户角色是 {role}，简历导入是求职者(candidate)功能，后端将拒绝。", file=sys.stderr)
    except HipiError:
        pass  # 未授权时才用具体路径提示

    try:
        if args.json:
            raw = _load(args.json)
            try:
                resume = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"❌ JSON 解析失败: {exc}", file=sys.stderr)
                return 2
            if not isinstance(resume, dict):
                print("❌ JSON 根节点必须是对象", file=sys.stderr)
                return 2

            if not args.skip_validate:
                report = validate(resume)
                print(f"↳ 本地校验 {args.json}")
                for sev, path, msg in report.issues:
                    mark = "✗" if sev == "error" else "⚠"
                    print(f"    {mark} [{sev}] {path}: {msg}")
                if report.has_blocking():
                    print("❌ 校验未通过，已中止导入。可 --skip-validate 强制导入。", file=sys.stderr)
                    return 1
                print()
        else:
            text = _load(args.text)
            if len(text.strip()) < 20:
                print("❌ 简历文本过短（<20 字符），无法解析。", file=sys.stderr)
                return 1
            print(f"↳ 调用后端 AI 解析简历（{len(text)} 字符）…")
            resume = _parse_via_backend(text, store, args.account)

        _guard_empty(resume)
        resp = import_resume(resume, store=store, account_id=args.account)
    except HipiError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.json_out:
        print_json(resp)
        return 0

    print("\n✅ 简历导入成功")
    basic = resp.get("basic_info") or {}
    if basic.get("name"):
        print(f"   姓名: {basic.get('name')}")
    print(f"   技能: {resp.get('skills_count', 0)} · 工作经历: {resp.get('experiences_count', 0)} · "
          f"项目: {resp.get('projects_count', 0)} · 教育: {resp.get('education_count', 0)}")
    print("   接下来可运行 hipo_match_jobs.py 查看匹配岗位。")
    return 0


if __name__ == "__main__":
    sys.exit(main())