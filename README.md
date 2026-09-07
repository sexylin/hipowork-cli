# hipowork-cli

<div align="center">

# 让你的简历，被 AI 看到
### 让机会与人才自然相遇

[![PyPI](https://img.shields.io/pypi/v/hipowork-cli?color=blue)](https://pypi.org/project/hipowork-cli/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![OAuth 2.0](https://img.shields.io/badge/Auth-OAuth2.0-green)](https://oauth.net/2/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**官网：** [https://hipowork.com](https://hipowork.com) · [https://www.hipowork.com](https://www.hipowork.com)  
**远程 MCP 服务：** `https://mcp.hipowork.com/mcp`  
**API 服务端点：** `https://api.hipowork.com`

</div>

---

## 🌟 平台理念

在传统的招聘求职中，优秀的简历常常沉睡在静态文档或封闭的简历库中，被动等待死板的关键词匹配。

**HiPo Work** 致力于改变这一现状：
- **把简历沉淀为高精度语义资产**：通过 Agent 或客户端工具，求职者的专业技能、独立项目经验、工作职责与落地成果被全量结构化沉淀并生成向量。
- **让你的简历被 AI 工具随时检索**：不管是 Claude Code、Cursor、OpenAI CodeX、Hermes Agent 还是企业招聘 Agent，都能在秒级通过工具精准检索、评估与连接候选人。
- **让机会与人才自然相遇**：不再需要海投或盲目筛选，基于真实项目深度与核心能力，实现招聘方与求职者的双向精准触达。

---

## 🔗 相关生态与公开仓库

HiPo Work 提供了完整的 Agent 原生招聘生态，涵盖命令行工具、MCP 服务与 Web 控制台：

| 项目 / 平台 | 链接 | 说明 |
|------------|------|------|
| **官方网站** | [hipowork.com](https://hipowork.com) | 包含求职者中心、招聘方控制台、岗位发布与语义匹配演示 |
| **hipowork-cli**（本项目） | [github.com/sexylin/hipowork-cli](https://github.com/sexylin/hipowork-cli) | 客户端命令行工具集（PyPI: `pip install hipowork-cli`），提供 `hipo` 与 `hipowork-cli` 终端命令 |
| **hipo-mcp** | [github.com/sexylin/hipo-mcp](https://github.com/sexylin/hipo-mcp) | 远程 MCP 服务端，遵循 Model Context Protocol 标准，支持 OAuth 2.0 (PKCE) |
| **MCP Registry** | `io.github.sexylin/hipo-work` | MCP 官方 Registry 认证注册服务坐标 |

---

## 📦 安装

```bash
# 从 PyPI 安装（推荐，要求 Python 3.10+）
pip install hipowork-cli

# 可选：支持本地简历 PDF 文本提取依赖
pip install hipowork-cli[resume]
```

安装完成后系统提供两个完全等价的命令行入口：`hipo` 与 `hipowork-cli`。

---

## 🚀 快速开始

### 1. 登录与授权

```bash
# 求职者登录（终端将打印标准引导并在浏览器完成邮箱验证）
hipowork-cli login --role candidate     # 或: hipo login --role candidate

# 招聘方登录
hipowork-cli login --role employer
```

> **提示**：
> - 首次授权需要在浏览器完成邮箱验证码登录；如果你已经在 HiPo Work Web 端（[hipowork.com](https://hipowork.com)）登录过，授权页将直接显示**「确认授权」**，一键放行免重复输入验证码。
> - 授权完成后 Token 自动刷新与持久化，存放在本机 `~/.hipo_mcp_tokens.json`（0600 权限），无需手动维护。
> - CLI 授权成功还会自动打开 Web Handoff 页面直接进入对应的 Profile 档案页。

### 2. 状态检查与账户管理

```bash
hipo status          # 查看当前登录身份、Token 有效期与 Scope 权限
hipo refresh         # 强制轮换 Access Token
hipo accounts list   # 查看已登录的多账户（支持多邮箱、多角色随时切换）
```

### 3. 日常使用

```bash
# 求职者：根据简历智能匹配在招岗位
hipo match-jobs

# 求职者：导入结构化简历并上传本地附件
hipo resume-import --json my_resume.json --attachment my_resume.pdf

# 招聘方：发布招聘岗位
hipo publish-job --json examples/job.example.json

# 招聘方：自然语言搜索候选人
hipo search "成都 5年经验 熟悉Solidity和Go的全栈"
```

---

## 📋 命令速查表

### 认证与凭据
| 命令 | 说明 |
|---|---|
| `hipowork-cli login --role candidate/employer` | 统一登录入口（打印格式化引导并打开浏览器授权） |
| `hipo authorize --role candidate/employer` | OAuth 授权（login 别名，PKCE + 邮箱验证码） |
| `hipo status` | 查看当前 Token 状态、角色、权限与过期时间 |
| `hipo refresh` | 强制刷新 Access Token |
| `hipo token-sync [--refresh]` | 导出 Token 供浏览器前端调试使用（Base64 格式） |
| `hipo accounts list/current/switch/delete` | 多账户管理（支持多个角色与邮箱多凭据隔离存储） |

### 求职者（Candidate）
| 命令 | 说明 |
|---|---|
| `hipo match-jobs [--json]` | 根据我的简历匹配全平台岗位，输出按匹配度排序的列表及多维度评分 |
| `hipo resume-extract <file.pdf> [--out x.txt]` | 本地提取简历文本（支持 PDF、DOCX、TXT） |
| `hipo resume-validate <resume.json>` | 导入前校验 JSON 结构（包括 duration_months、projects 完整性等） |
| `hipo resume-import --json <resume.json> [--attachment file.pdf]` | **核心推荐**：直接导入本地结构化简历，支持携带原件附件存档 |
| `hipo resume-import --text <resume.txt>` | 传入简历纯文本，走平台后端 AI 服务解析后导入 |

### 招聘方（Employer）
| 命令 | 说明 |
|---|---|
| `hipo publish-job --title x --text "..." [--json file]` | 发布招聘需求（支持结构化条件与面议设置） |
| `hipo close-job <job_id>` | 关闭已发布的职位（关闭后不再被候选人检索或参与匹配） |
| `hipo search "自然语言描述" [--max n]` | 自然语言直接检索候选人人格与经历 |
| `hipo match-candidates --text "..." / --json cond.json / --job <id>` | 结构化多维度候选人匹配（支持技能硬过滤与向量语义检索） |
| `hipo market --keyword python [--industry tech]` | 技能与行业人才市场供需热度分析 |
| `hipo stats` | 平台统计概览（在招职位、人才分布等） |

### 运维与端到端诊断
| 命令 | 说明 |
|---|---|
| `hipo healthcheck` | 一键体检：检查 API / MCP / OAuth metadata / Embedding 全链路连通性 |
| `hipo e2e` | 完整端到端冒烟测试：Token 校验 → REST /auth/me → MCP 会话 → 受保护工具调用 |

> 任意命令均可添加 `--help` 查看完整参数；大部分命令支持 `--json` 输出结构化数据，方便与自动化脚本结合。

---

## 📄 简历导入的最佳实践

### 1. 推荐方式：`--json`（带独立项目经历与原始附件）
使用你本地的 LLM 或 Agent 将简历提炼为结构化 JSON（参考 `examples/resume.example.json`），重点保留：
- **`projects`**：独立作品、开源项目、商业落地专项等（作为一等公民数据独立呈现）；
- **`work_experiences`**：职责、成果、技术栈及精确的 `duration_months`（用于累计工作年限）；
- **`--attachment`**：携带本地原始 PDF/Word 附件，自动上传加密存储并供招聘方预览。

```bash
hipo resume-import --json my_resume.json --attachment my_resume.pdf
```

### 2. 文本解析方式：`--text`
如果你不想手动组织 JSON，也可以直接提取文本由后端 AI 统一解析：
```bash
hipo resume-extract my_resume.pdf --out resume.txt
hipo resume-import --text resume.txt
```

---

## 🛠️ 本地开发与源码运行

```bash
git clone git@github.com:sexylin/hipowork-cli.git
cd hipowork-cli

python3 -m venv .venv
.venv/bin/pip install -e .[resume]

# 运行完整单元测试套件
.venv/bin/python -m unittest discover -s tests
```

---

## 📄 License

本项目基于 [MIT License](LICENSE) 开源。
