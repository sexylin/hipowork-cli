"""简历 JSON 结构校验（导入前防御）。

字段规则与后端 POST /agent/import-resume 的白名单/长度限制对齐，
提前发现字段缺失、类型错误、超长、数量超限等问题（例如 duration_months
缺失导致经验分恒为 0 的坑）。

用法：
  python3 hipo_resume_validate.py resume.json
  python3 hipo_resume_validate.py resume.json --strict
  python3 hipo_resume_validate.py resume.json --fix 0  # 打印第 1 条工作经历修复建议

退出码：0 = 通过（仅 warning 也视为通过），1 = 有 error，2 = 文件无法解析
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from hipo_auth import require_py310

# ---- 与后端一致的规则（agent.py import-resume） ----

BASIC_FIELDS = ["name", "phone", "location", "headline", "summary", "industry"]
BASIC_MAXLEN = {"name": 100, "phone": 30, "location": 100, "headline": 200,
                "summary": 2000, "industry": 100}

WORK_FIELDS = ["company", "role", "start_date", "end_date", "duration_months",
               "industry", "responsibilities", "achievements", "tech_stack",
               "team_size", "ai_summary"]
WORK_MAXLEN = {"company": 200, "role": 200, "start_date": 7, "end_date": 7,
               "industry": 100, "ai_summary": 1000, "responsibilities": 300,
               "achievements": 300, "tech_stack": 300}
WORK_MAX_ITEMS = 20

PROJECT_FIELDS = ["name", "role", "start_date", "end_date", "description",
                  "responsibilities", "achievements", "tech_stack",
                  "project_url", "ai_summary"]
PROJECT_MAXLEN = {"name": 200, "role": 200, "start_date": 7, "end_date": 7,
                  "description": 3000, "project_url": 500, "ai_summary": 1500,
                  "responsibilities": 500, "achievements": 500, "tech_stack": 100}
PROJECT_MAX_ITEMS = 30

EDU_FIELDS = ["school", "degree", "major", "start_year", "end_year", "gpa",
              "school_type", "ai_summary"]
EDU_MAXLEN = {"school": 200, "degree": 50, "major": 200, "school_type": 50, "ai_summary": 1000}
EDU_MAX_ITEMS = 10

SKILL_FIELDS = ["name", "category", "level", "years", "context"]
SKILL_MAXLEN = {"name": 100, "category": 50, "context": 500}
SKILL_MAX_ITEMS = 50

CERT_FIELDS = ["name", "issuer", "year"]
LANG_FIELDS = ["language", "level"]

DATE_RE = re.compile(r"^\d{4}-\d{2}$")

Level = tuple[str, str, str]  # (severity, field_path, message)


class Report:
    def __init__(self) -> None:
        self.issues: list[Level] = []

    def error(self, path: str, msg: str) -> None:
        self.issues.append(("error", path, msg))

    def warn(self, path: str, msg: str) -> None:
        self.issues.append(("warning", path, msg))

    @property
    def errors(self) -> list[Level]:
        return [i for i in self.issues if i[0] == "error"]

    @property
    def warnings(self) -> list[Level]:
        return [i for i in self.issues if i[0] == "warning"]

    def has_blocking(self) -> bool:
        return bool(self.errors)


def _check_str(report: Report, obj: Any, path: str, maxlen: int) -> None:
    if obj is None:
        return
    if not isinstance(obj, str):
        report.error(path, f"应为字符串，实际 {type(obj).__name__}")
        return
    if len(obj) > maxlen:
        report.error(path, f"长度 {len(obj)} 超过后端上限 {maxlen}")


def _check_date(report: Report, obj: Any, path: str) -> None:
    if obj is None:
        return
    if not isinstance(obj, str):
        report.error(path, f"日期应为字符串 YYYY-MM，实际 {type(obj).__name__}")
        return
    if not DATE_RE.match(obj):
        report.warn(path, f"日期格式非 YYYY-MM（{obj!r}），后端仅保留前 7 字符")


def _check_int(report: Report, obj: Any, path: str, low: int | None = None, high: int | None = None) -> None:
    if obj is None:
        return
    if isinstance(obj, bool) or not isinstance(obj, int):
        report.error(path, f"应为整数，实际 {type(obj).__name__}（{obj!r}）")
        return
    if low is not None and obj < low:
        report.error(path, f"不能小于 {low}")
    if high is not None and obj > high:
        report.error(path, f"不能大于 {high}")


def _check_str_list(report: Report, obj: Any, path: str, maxlen: int, max_items: int) -> None:
    if obj is None:
        return
    if not isinstance(obj, list):
        report.error(path, f"应为字符串数组，实际 {type(obj).__name__}")
        return
    if len(obj) > max_items:
        report.warn(path, f"数组长度 {len(obj)} 超过后端上限 {max_items}，多余的会被丢弃")
    for i, item in enumerate(obj[:max_items]):
        if not isinstance(item, str):
            report.error(f"{path}[{i}]", f"应为字符串，实际 {type(item).__name__}")
        elif len(item) > maxlen:
            report.warn(f"{path}[{i}]", f"长度 {len(item)} 超过上限 {maxlen}，会被截断")


def validate(resume: dict, strict: bool = False) -> Report:
    """校验一份结构化简历。strict=True 时 warning 也视为阻断。"""
    report = Report()

    # ---- basic_info ----
    basic = resume.get("basic_info") or {}
    if not isinstance(basic, dict):
        report.error("basic_info", "应为对象")
    else:
        for f in BASIC_FIELDS:
            _check_str(report, basic.get(f), f"basic_info.{f}", BASIC_MAXLEN.get(f, 200))

    # ---- 各列表 ----
    def _check_list_section(key: str, fields: list[str], maxlen: dict, max_items: int,
                            int_fields: set[str], float_fields: set[str] | None = None) -> None:
        items = resume.get(key)
        if items is None:
            return
        if not isinstance(items, list):
            report.error(key, "应为数组")
            return
        if len(items) > max_items:
            report.warn(key, f"数量 {len(items)} 超过后端上限 {max_items}，多余的会被丢弃")
        for idx, it in enumerate(items[:max_items]):
            base = f"{key}[{idx}]"
            if not isinstance(it, dict):
                report.error(base, "应为对象")
                continue
            for f in fields:
                v = it.get(f)
                if f in int_fields:
                    _check_int(report, v, f"{base}.{f}")
                elif float_fields and f in float_fields:
                    if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                        report.error(f"{base}.{f}", "应为数字")
                elif f in ("start_date", "end_date"):
                    _check_date(report, v, f"{base}.{f}")
                elif f in ("responsibilities", "achievements", "tech_stack"):
                    _check_str_list(report, v, f"{base}.{f}", maxlen.get(f, 300), 30 if f != "tech_stack" else 50)
                else:
                    _check_str(report, v, f"{base}.{f}", maxlen.get(f, 300))

    _check_list_section("work_experiences", WORK_FIELDS, WORK_MAXLEN, WORK_MAX_ITEMS,
                        int_fields={"duration_months", "team_size"})
    _check_list_section("projects", PROJECT_FIELDS, PROJECT_MAXLEN, PROJECT_MAX_ITEMS,
                        int_fields=set())
    _check_list_section("education", EDU_FIELDS, EDU_MAXLEN, EDU_MAX_ITEMS,
                        int_fields={"start_year", "end_year"}, float_fields={"gpa"})
    _check_list_section("skills", SKILL_FIELDS, SKILL_MAXLEN, SKILL_MAX_ITEMS,
                        int_fields={"level"}, float_fields={"years"})
    _check_list_section("certificates", CERT_FIELDS, {"name": 200, "issuer": 200},
                        100, int_fields={"year"})
    _check_list_section("languages", LANG_FIELDS, {"language": 100, "level": 100},
                        50, int_fields=set())

    # ---- 关键业务校验 ----
    if not basic or not (basic.get("name") or basic.get("summary")):
        report.warn("basic_info", "建议至少提供 name 或 summary，否则简历在匹配中缺少可识别信息")

    works = resume.get("work_experiences") or []
    if isinstance(works, list):
        # duration_months 缺失提醒（直接导致后端 experience_years 不累计）
        missing_duration = [i for i, w in enumerate(works[:WORK_MAX_ITEMS])
                            if isinstance(w, dict) and "duration_months" not in w]
        if missing_duration:
            report.warn(
                "work_experiences",
                f"第 {[i + 1 for i in missing_duration]} 段工作经历缺少 duration_months，"
                "会导致经验年限(experience_years)不累计、岗位匹配经验分(0-30)拿不到",
            )

    skills = resume.get("skills") or []
    if isinstance(skills, list) and not skills:
        report.warn("skills", "无技能列表，岗位技能匹配分(0-50)将无法得分")

    return report


def _print_report(report: Report) -> None:
    for sev, path, msg in report.issues:
        mark = "✗" if sev == "error" else "⚠"
        print(f"  {mark} [{sev}] {path}: {msg}")


def main() -> int:
    require_py310()
    parser = argparse.ArgumentParser(description="简历 JSON 结构校验")
    parser.add_argument("resume", help="简历 JSON 文件路径")
    parser.add_argument("--strict", action="store_true", help="warning 也视为阻断（退出码 1）")
    args = parser.parse_args()

    path = Path(args.resume)
    if not path.exists():
        print(f"❌ 文件不存在: {path}", file=sys.stderr)
        return 2
    try:
        resume = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ JSON 解析失败: {exc}", file=sys.stderr)
        return 2
    if not isinstance(resume, dict):
        print("❌ JSON 根节点必须是对象", file=sys.stderr)
        return 2

    report = validate(resume, strict=args.strict)
    print(f"校验 {path}")
    _print_report(report)
    print()

    blocking = report.has_blocking() or (args.strict and report.warnings)
    if blocking:
        print(f"❌ 校验未通过（{len(report.errors)} 个错误"
              + (f" / {len(report.warnings)} 个 warning") + "）")
        return 1
    if report.warnings:
        print(f"✅ 校验通过（{len(report.warnings)} 个 warning，不阻断）")
        return 0
    print("✅ 校验通过，无问题。")
    return 0


if __name__ == "__main__":
    sys.exit(main())