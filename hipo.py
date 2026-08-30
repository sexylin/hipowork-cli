"""HiPo Work CLI 统一入口。

把 scripts/ 下的所有命令收敛为一个命令，自动处理模块导入路径，
避免直接双击脚本或从其他目录调用时的 import 失败。

用法（从仓库根目录或任意目录）：
  python3 hipo.py authorize --role candidate
  python3 hipo.py status
  python3 hipo.py refresh
  python3 hipo.py accounts list
  python3 hipo.py match-jobs --json
  python3 hipo.py publish-job --title "..." --text "..."
  python3 hipo.py search "成都 Python 后端"
  python3 hipo.py match-candidates --text "..."
  python3 hipo.py market --keyword python
  python3 hipo.py stats
  python3 hipo.py resume-extract resume.pdf --out resume.txt
  python3 hipo.py resume-validate resume.json
  python3 hipo.py resume-import --json resume.json
  python3 hipo.py healthcheck
  python3 hipo.py e2e
  python3 hipo.py token-sync [--refresh]

等价于直接运行 scripts/ 下的脚本；统一入口会自动转发参数。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# 命令名 → 对应脚本文件（不含 .py）
COMMANDS = {
    "authorize": "hipo_authorize",
    "status": "hipo_token_status",
    "refresh": "hipo_token_refresh",
    "token-sync": "hipo_token_sync",
    "accounts": "hipo_accounts",
    "match-jobs": "hipo_match_jobs",
    "publish-job": "hipo_publish_job",
    "search": "hipo_search_candidates",
    "match-candidates": "hipo_match_candidates",
    "market": "hipo_market",
    "stats": "hipo_stats",
    "resume-extract": "hipo_resume_extract",
    "resume-validate": "hipo_resume_validate",
    "resume-import": "hipo_resume_import",
    "healthcheck": "hipo_healthcheck",
    "e2e": "hipo_e2e",
}

# 各命令的一句话说明（help 输出用）
HELP = {
    "authorize": "OAuth 授权（打开浏览器完成邮箱验证码登录）",
    "status": "查看 token 状态（角色/scope/过期）",
    "refresh": "强制刷新 token",
    "token-sync": "导出 token 到浏览器 localStorage（4 个 base64）",
    "accounts": "多账户管理（list/switch/delete）",
    "match-jobs": "求职者：匹配岗位",
    "publish-job": "招聘方：发布岗位",
    "search": "招聘方：自然语言搜索候选人",
    "match-candidates": "招聘方：结构化/自然语言匹配候选人",
    "market": "招聘方：人才市场分析",
    "stats": "平台统计",
    "resume-extract": "简历文本提取（PDF/DOCX/TXT）",
    "resume-validate": "简历 JSON 结构校验",
    "resume-import": "简历导入（校验 + 写入）",
    "healthcheck": "服务连通性检查（API/MCP/Embedding）",
    "e2e": "端到端冒烟测试",
}

# 需要前置授权的命令（帮助提示用）
AUTH_REQUIRED = {
    "status", "refresh", "token-sync", "accounts", "match-jobs", "publish-job",
    "search", "match-candidates", "market", "stats", "resume-import", "e2e",
}


def _print_help() -> None:
    print("HiPo Work CLI — 统一入口")
    print("用法: python3 hipo.py <command> [args...]\n")
    print("认证与令牌:")
    for k in ("authorize", "status", "refresh", "token-sync", "accounts"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n招聘方:")
    for k in ("publish-job", "search", "match-candidates", "market", "stats"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n求职者:")
    for k in ("match-jobs", "resume-extract", "resume-validate", "resume-import"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n运维:")
    for k in ("healthcheck", "e2e"):
        print(f"  {k:<16} {HELP[k]}")
    print("\n任何命令都可用 --help 查看详细参数，例如:")
    print("  python3 hipo.py publish-job --help")
    print("\n也可以直接运行 scripts/ 下的独立脚本（等价）。")


def main() -> int:
    # 允许从任意目录运行：把 scripts/ 加进 PYTHONPATH
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SCRIPTS_DIR) + (os.pathsep + pythonpath if pythonpath else "")

    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        _print_help()
        return 0

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"❌ 未知命令: {cmd}\n", file=sys.stderr)
        _print_help()
        return 2

    script = SCRIPTS_DIR / f"{COMMANDS[cmd]}.py"
    if not script.exists():
        print(f"❌ 脚本缺失: {script}", file=sys.stderr)
        return 2

    # 转发剩余参数；子进程继承 PYTHONPATH，保证 scripts 内部互相 import 正常
    return subprocess.call([sys.executable, str(script), *args[1:]], env=env)


if __name__ == "__main__":
    sys.exit(main())