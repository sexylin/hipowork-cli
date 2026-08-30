# hipowork-cli

HiPo Work 客户端命令行工具集 — 面向求职者和招聘方的纯 Python 脚本集，
直接对接 https://api.hipowork.com 后端 REST API（底层与 MCP 工具同一套接口），
无需浏览器、无需配置 API Key，用 OAuth 授权后即可在终端完成简历导入、岗位发布、
候选人匹配、市场分析等操作。

## 为什么是脚本集（环境适配说明）

- **Python 3.10+**：脚本使用 PEP 604 联合类型（`str | None`），低于 3.10 会给出明确报错。
  macOS 自带 `/usr/bin/python3` 是 3.9，请用 `python3.13` / `python3.12` / Homebrew Python。
- **依赖按需拆分**：核心（`requirements.txt`: mcp / httpx）和简历 PDF 提取
  （`requirements-resume.txt`: pymupdf）分开，不需要简历提取的可以不装后者。
- **从任意目录运行**：仓库根目录的 `hipo.py` 会自动处理 `scripts/` 的导入路径，
  不会出现 `ModuleNotFoundError`。也可以直接运行 `scripts/` 下的独立脚本。
- **跨平台**：仅用标准库 + 上述依赖；`webbrowser` 在无 GUI 环境会自动降级为
  打印授权 URL 手动粘贴。token 文件 `~/.hipo_mcp_tokens.json` 各平台一致，
  macOS/Linux 自动 0600 权限。
- **凭据安全**：token、config、`.env`、`.pem`/`.key` 已被 `.gitignore` 排除，
  绝不提交。授权完成后 token 只存在本机 `~/.hipo_mcp_tokens.json`。

## 快速开始

```bash
# 1. 建虚拟环境并装依赖（Python 3.10+）
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt            # 核心
.venv/bin/pip install -r requirements-resume.txt     # 可选：PDF 简历提取

# 2. 统一入口（推荐，从任意目录可跑）
.venv/bin/python hipo.py authorize --role candidate   # 求职者授权
# .venv/bin/python hipo.py authorize --role employer # 招聘方授权

# 3. 看授权状态 / 刷新 / 多账户
.venv/bin/python hipo.py status
.venv/bin/python hipo.py refresh

# 4. 用起来
.venv/bin/python hipo.py match-jobs                       # 求职者匹配岗位
.venv/bin/python hipo.py resume-import --json examples/resume.example.json  # 导入简历
.venv/bin/python hipo.py publish-job --json examples/job.example.json       # 招聘方发布岗位
.venv/bin/python hipo.py search "成都 Python 后端"
```

> 提示：也可以直接运行 `scripts/hipo_*.py`（等价）。授权流程需要浏览器完成
> 邮箱验证码登录；授权完成后 token 自动刷新，无需再手动处理。

## 命令速查

### 认证与令牌
| 命令 | 说明 |
|---|---|
| `hipo.py authorize --role candidate/employer [--email x]` | OAuth 授权（PKCE + 邮箱验证码） |
| `hipo.py status` | 查看当前 token：角色/scope/过期时间 |
| `hipo.py refresh` | 强制刷新 access_token |
| `hipo.py token-sync [--refresh]` | 导出 token 到浏览器 localStorage（4 个 base64） |
| `hipo.py accounts list/current/switch/delete` | 多账户管理（多邮箱多角色分开存） |

### 求职者
| 命令 | 说明 |
|---|---|
| `hipo.py match-jobs [--json]` | 根据我的简历匹配岗位 |
| `hipo.py resume-extract <file.pdf> [--out x.txt]` | 提取简历文本（PDF/DOCX/TXT） |
| `hipo.py resume-validate <resume.json>` | 导入前校验 JSON 结构 |
| `hipo.py resume-import --json <resume.json>` | 校验后导入简历（推荐） |
| `hipo.py resume-import --text <resume.txt>` | 走平台 AI 服务解析后导入 |

### 招聘方
| 命令 | 说明 |
|---|---|
| `hipo.py publish-job --title x --text "..." [--json file]` | 发布岗位 |
| `hipo.py search "自然语言描述" [--max n]` | 自然语言搜索候选人 |
| `hipo.py match-candidates --text "..." / --json cond.json / --job <id>` | 结构化匹配候选人 |
| `hipo.py market --keyword python [--industry tech]` | 人才市场分析 |
| `hipo.py stats` | 平台统计 |

### 运维诊断
| 命令 | 说明 |
|---|---|
| `hipo.py healthcheck` | 检查 API / MCP / OAuth metadata / Embedding 连通性 |
| `hipo.py e2e` | 端到端冒烟：token → REST /auth/me → MCP 会话 → 工具调用 |

任意命令加 `--help` 查看详细参数；大部分命令支持 `--json` 输出原始 JSON 便于脚本消费。

## 简历导入两种方式

1. **推荐：`--json`** — 用你自己的 LLM / Agent 把简历解析为结构化 JSON
   （参考 `examples/resume.example.json`），本地校验通过后导入。不依赖平台 AI 服务。
   ```bash
   .venv/bin/python hipo.py resume-import --json my_resume.json
   ```
2. **`--text`** — 传入简历纯文本，由平台后端 AI 服务解析（需要后端配置了
   AI_SERVICE_URL；否则会提示改用 `--json`）。
   ```bash
   .venv/bin/python hipo.py resume-extract resume.pdf --out resume.txt
   .venv/bin/python hipo.py resume-import --text resume.txt
   ```

`hipo_resume_validate.py` 会提前发现常见问题：`duration_months` 缺失
（会导致经验年限不累计、岗位匹配经验分拿不到）、字段超长、类型错误、
数量超限等，规则与后端 `POST /agent/import-resume` 的白名单/上限一致。

## 目录结构

```text
hipo.py                      # 统一入口（推荐）
scripts/
  hipo_auth.py               # 共享认证库：token 仓库/刷新/API 客户端
  hipo_authorize.py          # OAuth 授权 + 本地回调 + 统一成功页
  hipo_token_status.py       # token 状态
  hipo_token_refresh.py      # 强制刷新
  hipo_token_sync.py         # token → 浏览器 localStorage
  hipo_accounts.py           # 多账户管理
  hipo_mcp_client.py         # 业务封装：匹配/发布/搜索/统计/导入等
  hipo_match_jobs.py         # 求职者匹配岗位
  hipo_publish_job.py        # 发布岗位
  hipo_search_candidates.py  # 搜索候选人
  hipo_match_candidates.py   # 结构化匹配候选人
  hipo_market.py             # 市场分析
  hipo_stats.py              # 平台统计
  hipo_resume_extract.py     # 简历文本提取
  hipo_resume_validate.py    # 简历 JSON 校验
  hipo_resume_import.py      # 简历导入
  hipo_healthcheck.py        # 服务连通性检查
  hipo_e2e.py                # 端到端冒烟
templates/
  success.html               # 统一授权成功页（深色玻璃拟态）
examples/
  resume.example.json        # 结构化简历示例
  job.example.json           # 结构化岗位示例
```

## 相关服务地址

```text
API:   https://api.hipowork.com        (docs: /docs)
MCP:   https://mcp.hipowork.com/mcp
官网:  https://hipowork.com
```
