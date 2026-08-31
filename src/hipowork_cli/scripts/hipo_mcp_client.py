"""HiPo Work CLI 统一客户端封装（MCP/API 双通道）。

所有业务命令（发验证码、匹配岗位、发布岗位、搜候选人、市场分析、平台统计、
简历导入等）统一复用本模块：先确保拿到有效 OAuth token，再直接调用
后端 REST API（Bearer 认证）。REST 与 MCP 工具底层走同一套后端接口，
不需要拉起 MCP 会话，命令更轻、更快、更易在脚本中复用。

依赖：pip install -r requirements.txt
"""
from __future__ import annotations

import json
import sys

from hipo_auth import (
    DEFAULT_API_BASE,
    DEFAULT_MCP_URL,
    TokenStore,
    api_request,
    ensure_valid_token,
    require_py310,
)


class HipiError(Exception):
    """CLI 层统一错误（带友好提示）。"""


def _req(method: str, path: str, token: str | None = None, body: dict | None = None,
         api_base: str = DEFAULT_API_BASE, timeout: int = 30) -> dict:
    """api_request 的友好包装：把底层 RuntimeError 转成 HipiError。"""
    try:
        return api_request(method, path, token=token, body=body,
                           api_base=api_base, timeout=timeout)
    except RuntimeError as exc:
        raise HipiError(str(exc)) from exc


# ============ 公开认证动作 ============


def send_code(email: str) -> dict:
    """发送邮箱验证码（公开接口，不需要 token）。"""
    return _req("POST", "/auth/send-code", token=None, body={"email": email})


def register_or_login(email: str, code: str, role: str = "candidate",
                      company_name: str | None = None) -> dict:
    """邮箱验证码注册/登录（公开接口）。"""
    body = {"email": email, "code": code, "role": role}
    if company_name:
        body["company_name"] = company_name
    return _req("POST", "/auth/register-or-login", token=None, body=body)


# ============ 认证工具 ============


def get_access_token(store: TokenStore | None = None, account_id: str | None = None,
                     force_refresh: bool = False) -> str:
    """确保拿到未过期的 access_token（过期自动刷新）。"""
    store = store or TokenStore()
    if not store.exists():
        raise HipiError("未找到 token 仓库，请先运行 hipo authorize 完成授权。")
    try:
        tokens = ensure_valid_token(store, account_id=account_id, force=force_refresh)
    except (ValueError, RuntimeError) as exc:
        raise HipiError(f"token 不可用: {exc}") from exc
    return tokens["access_token"]


# ============ 业务封装（对应 MCP 工具 / Agent 接口） ============


def check_role(store: TokenStore | None = None, account_id: str | None = None) -> str:
    """返回当前账户角色（candidate/employer/空）。"""
    store = store or TokenStore()
    return store.role(account_id) or ""


def match_jobs_for_me(store: TokenStore | None = None, account_id: str | None = None,
                      raw: bool = False) -> dict:
    """求职者：根据我的简历匹配岗位（GET /candidate/matches）。"""
    token = get_access_token(store, account_id)
    data = _req("GET", "/candidate/matches", token=token)
    return data if raw else _summarize_job_matches(data)


def publish_job(title: str, required: list | None = None, preferred: dict | None = None,
                raw_text: str = "", salary_min: int | None = None,
                salary_max: int | None = None, salary_unit: str | None = "monthly",
                benefits: list | None = None,
                store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """招聘方：发布结构化岗位（POST /agent/publish-job）。

    P1-17 薪资面议契约：salary_min 与 salary_max 均为空 → 面议 → salary_unit 传 None；
    只有提供了下限或上限时才带 unit。
    """
    token = get_access_token(store, account_id)
    # 面议统一为 None（与后端 salary_unit=NULL=面议 语义一致）
    effective_unit = salary_unit if (salary_min is not None or salary_max is not None) else None
    body = {
        "title": title,
        "raw_text": raw_text or "",
        "required": required or [],
        "preferred": preferred or {},
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_unit": effective_unit,
        "benefits": benefits or [],
    }
    return _req("POST", "/agent/publish-job", token=token, body=body)


def close_job(job_id: str,
              store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """招聘方：关闭已发布的招聘岗位（PUT /employer/requirements/{job_id}）。"""
    token = get_access_token(store, account_id)
    return _req("PUT", f"/employer/requirements/{job_id}", token=token,
                body={"status": "closed"})


def search_candidates(query: str, max_results: int = 10,
                      store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """招聘方：自然语言搜索候选人（POST /search）。"""
    token = get_access_token(store, account_id)
    return _req("POST", "/search", token=token,
                       body={"query": query, "max_results": max_results})


def match_candidates(required: list | None = None, preferred: dict | None = None,
                     query_text: str | None = None, max_results: int = 10,
                     store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """招聘方：结构化/自然语言条件匹配候选人（POST /agent/match-candidates）。"""
    token = get_access_token(store, account_id)
    body: dict = {"max_results": max_results}
    if query_text:
        body["query_text"] = query_text
    if required:
        body["required"] = required
    if preferred:
        body["preferred"] = preferred
    return _req("POST", "/agent/match-candidates", token=token, body=body)


def match_job_requirement(job_id: str, max_results: int = 10,
                          store: TokenStore | None = None,
                          account_id: str | None = None) -> dict:
    """招聘方：对已发布岗位自动匹配候选人（POST /employer/requirements/{id}/match）。"""
    token = get_access_token(store, account_id)
    return _req("POST", f"/employer/requirements/{job_id}/match", token=token,
                       body={"max_results": max_results})


def get_stats(store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """平台统计（GET /agent/stats）。"""
    token = get_access_token(store, account_id)
    return _req("GET", "/agent/stats", token=token)


def market_analysis(keyword: str | None = None, industry: str | None = None,
                    location: str | None = None,
                    store: TokenStore | None = None, account_id: str | None = None) -> dict:
    """市场分析（POST /agent/market-analysis）。"""
    token = get_access_token(store, account_id)
    body = {}
    if keyword:
        body["keyword"] = keyword
    if industry:
        body["industry"] = industry
    if location:
        body["location"] = location
    return _req("POST", "/agent/market-analysis", token=token, body=body)


def import_resume(resume_data: dict, store: TokenStore | None = None,
                  account_id: str | None = None) -> dict:
    """简历导入（POST /agent/import-resume），传入 Agent 解析好的结构化 JSON。"""
    token = get_access_token(store, account_id)
    body = {
        "basic_info": resume_data.get("basic_info", {}),
        "work_experiences": resume_data.get("work_experiences", []),
        "projects": resume_data.get("projects", []),
        "education": resume_data.get("education", []),
        "skills": resume_data.get("skills", []),
        "certificates": resume_data.get("certificates", []),
        "languages": resume_data.get("languages", []),
    }
    return _req("POST", "/agent/import-resume", token=token, body=body)


# ============ 输出美化 ============


def _summarize_job_matches(data: dict) -> dict:
    """压缩候选人视角的岗位匹配结果为终端友好的摘要（保留原始数据供 --json）。"""
    results = data.get("results", [])
    slim = []
    for r in results:
        job = r.get("job") or {}
        breakdown = r.get("score_breakdown") or {}
        slim.append({
            "rank": r.get("rank"),
            "final_score": r.get("final_score"),
            "job_id": job.get("id"),
            "title": job.get("title"),
            "location": job.get("location"),
            "salary": _salary_text(job),
            "match_reasons": r.get("match_reasons") or [],
        })
    return {
        "total_matches": data.get("total_matches"),
        "results": slim,
    }


def _salary_text(job: dict) -> str:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    unit = job.get("salary_unit") or "monthly"
    if not lo and not hi:
        return "面议"
    unit_txt = "月" if unit == "monthly" else "年"
    if lo and hi:
        return f"{lo}-{hi}k/{unit_txt}"
    return f"{lo or hi}k/{unit_txt}"


def fmt_score_breakdown(bd: dict) -> str:
    """把分数明细渲染成终端可读的多行文本。"""
    if not bd:
        return "  (无分数明细)"
    lines = []
    for k, v in bd.items():
        if isinstance(v, (int, float)):
            lines.append(f"  {k}: {v}")
        elif isinstance(v, list):
            lines.append(f"  {k}: {', '.join(str(x) for x in v[:6])}")
        elif isinstance(v, dict):
            inner = "；".join(f"{ik}={iv}" for ik, iv in list(v.items())[:6])
            lines.append(f"  {k}: {inner}")
    return "\n".join(lines) if lines else "  (无分数明细)"


def print_candidate_result(r: dict, indent: str = "  ") -> None:
    """渲染招聘方单个候选人匹配结果。"""
    cand = r.get("candidate") or {}
    name = cand.get("name") or cand.get("display_name") or "匿名候选人"
    print(f"{indent}#{r.get('rank')} [{r.get('final_score'):.1f}分] {name}")
    summary = cand.get("summary")
    if summary:
        print(f"{indent}  简介: {str(summary)[:120]}")
    reasons = r.get("match_reasons") or []
    if reasons:
        print(f"{indent}  匹配: {' | '.join(str(x) for x in reasons[:4])}")
    bd = r.get("score_breakdown")
    if bd:
        print(fmt_score_breakdown(bd).replace("\n", f"\n{indent}"))


def print_job_result(r: dict, indent: str = "  ") -> None:
    """渲染求职者单个岗位匹配结果（兼容原始结构与摘要结构）。"""
    job = r.get("job") or {}
    # 摘要结构：字段直接放顶层（_summarize_job_matches 生成）
    if not job and r.get("title"):
        job = r
    title = job.get("title") or "?"
    location = job.get("location") or ""
    # 摘要结构自带 salary 文本；原始结构用 salary_min/max 拼
    if job.get("salary") is not None:
        salary_txt = str(job["salary"])
    else:
        salary_txt = _salary_text(job)
    loc_txt = f" {location} ·" if location else " ·"
    print(f"{indent}#{r.get('rank')} [{r.get('final_score'):.1f}分] {title}{loc_txt} {salary_txt}")
    reasons = r.get("match_reasons") or []
    if reasons:
        print(f"{indent}  匹配: {' | '.join(str(x) for x in reasons[:4])}")
    bd = r.get("score_breakdown")
    if bd:
        print(fmt_score_breakdown(bd).replace("\n", f"\n{indent}"))


def print_json(data) -> None:
    """打印 JSON（默认缩进 2，ASCII 关闭以保留中文字符）。"""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    require_py310()
    print(f"HiPo Work CLI 客户端封装库。MCP: {DEFAULT_MCP_URL} / API: {DEFAULT_API_BASE}")
    print("用法：请通过 hipo.py 或独立命令脚本调用。")
    sys.exit(0)