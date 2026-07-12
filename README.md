# ai-skill-repository

[English](README.en.md) · [GitHub](https://github.com/Barry04/ai-skill-repository)

面向 AI Agent 的**个人 Skill 库**——把可复用的工程经验写成 `skill/<name>/SKILL.md`，按需读取、确认后沉淀、随使用演进。

设计参考 [Harness Engineering](https://github.com/deusyu/harness-engineering)：**人类掌舵，智能体执行**；约束写在仓库里；入口是地图，不是百科全书。

> **仓库名** `ai-skill-repository` · 内含多个可全局安装的 Skill；**evolving-skill** 是演进协议，日常沉淀写在**各项目**的 `skill/` 目录。

---

## 这是什么

本仓库**不是**单一 Skill，也**不是**知识库或 RAG 平台。它是一个可版本管理的 **Skill 集合**：

- 每个 Skill 独立目录：`skill/<name>/SKILL.md`
- Agent 每次任务最多选 **2** 个高相关 Skill
- 新经验须**用户确认**后才写入（规则见 [evolving-skill](skill/evolving-skill/SKILL.md)）
- SkillOpt 只做离线评测 / 优化 proposal，不直接覆盖正式 Skill
- 运行 `install.ps1` / `install.sh` 可一次安装**全部** Skill 到 Codex / Cursor / Claude

---

## 当前 Skill 一览

### evolving-skill — 演进协议（装全局，写项目）

**何时用：** 任何项目里需要沉淀、合并、演进 Skill 时。

- **协议本身** → 安装到 `~/.codex/skills/`、`~/.cursor/skills/`、`~/.claude/skills/`（跨项目）
- **生成 / 演化的 Skill** → 写在**当前项目** `skill/<name>/`，并更新项目 `AGENTS.md`

不负责具体业务排错，而是管「怎么发现经验、怎么问用户、怎么落到项目里」。

→ [skill/evolving-skill/SKILL.md](skill/evolving-skill/SKILL.md)

---

### project-to-harness-skill — 项目 Harness 化

**何时用：** 把任意项目（新建 / 进行中 / 历史 / 开源）变成 Agent 可读结构。

只读扫描 → 知识发现 → 资格化评分 → 生成 `AGENTS.md`、`docs/harness/`、项目级 `skills/`。默认先预览，用户确认后才写入；不改业务源码与构建/部署配置。

→ [skill/project-to-harness-skill/SKILL.md](skill/project-to-harness-skill/SKILL.md)

---

### workspace-context-router — 多项目上下文路由

**何时用：** 同时维护多个仓库或模块，用户不想反复提供项目名、模块名和磁盘路径时。

以可人工审查的 `workspace.yaml` 登记项目、模块、别名和可选 revision；Router 先返回项目/模块及上下文入口，再按需读取项目 Harness。自动发现只生成候选，不使用 SQLite，不自动切换分支。

→ [skill/workspace-context-router/SKILL.md](skill/workspace-context-router/SKILL.md)

---

### java-backend-troubleshooting — Java 后端排错

**何时用：** Spring 事务不回滚、MyBatis 分页失效、Java 服务调试等。

沉淀可复用的 Java 后端排查规则，例如 `@Transactional` 代理问题、分页插件未生效等。

→ [skill/java-backend-troubleshooting/SKILL.md](skill/java-backend-troubleshooting/SKILL.md)

---

### linux-test-executor — 远程 Linux 测试

**何时用：** 在 Linux 测试机上验证部署、跑集成测试、收集日志。

支持 SSH 上传文件、执行远程命令、采集日志，附带 `tools/` 脚本（`remote_runner.py` 等）与连接配置样例。

→ [skill/linux-test-executor/SKILL.md](skill/linux-test-executor/SKILL.md)

---

### read-wiki-via-mcp — 读取 / 更新 Wiki

**何时用：** 通过本地 Atlassian MCP 读取、创建、更新 Confluence / wiki 页面。

支持 `wiki.shterm.com` / Confluence 页面读取与写入流程，包含本地 MCP 使用约束和辅助脚本。

→ [skill/read-wiki-via-mcp/SKILL.md](skill/read-wiki-via-mcp/SKILL.md)

---

### skillopt-adapter — SkillOpt 优化闭环

**何时用：** 用 SkillOpt 做 skill 优化、benchmark、regression、validation gate 或审查 `best_skill.md` 候选结果时。

SkillOpt 输出必须先进 `experiments/skillopt/` 和 `proposals/`；正式 `skill/<name>/SKILL.md` 只有在用户确认后才合并。CI 只跑确定性 regression，不调用模型。

→ [skill/skillopt-adapter/SKILL.md](skill/skillopt-adapter/SKILL.md)

---

## 它们如何配合

```text
全局（install.ps1 / install.sh 安装到 ~/.codex/skills 等）
  ├─ evolving-skill              → 演进协议
  ├─ project-to-harness-skill  → 项目 Harness 化
  ├─ workspace-context-router  → 多仓库 / 多模块上下文路由
  ├─ skillopt-adapter          → SkillOpt 优化 proposal / regression
  ├─ java-backend-troubleshooting
  ├─ linux-test-executor
  └─ read-wiki-via-mcp

目标项目（随项目 Git）
  ├─ docs/harness/ + skills/   → project-to-harness-skill 批量生成（可选）
  └─ skill/                    → evolving-skill 日常沉淀（用户确认后写入）

本仓库优化实验室（不安装到工具）
  ├─ eval/<skill>/              → regression cases + rubric
  ├─ experiments/skillopt/      → 本地 SkillOpt 运行产物
  └─ proposals/<skill>/         → 待审查候选修改
```

---

## 克隆与安装

```bash
git clone https://github.com/Barry04/ai-skill-repository.git
cd ai-skill-repository
```

安装**全部** Skill 到 Codex / Cursor / Claude：

| 平台 | 命令（在仓库根目录或解压后的包根目录执行） |
|------|------|
| Windows | `.\install.ps1` |
| macOS / Linux | `bash install.sh` |

脚本默认从**自身所在目录**读取 `skill/`，解压后直接执行即可，无需传路径。

`AGENTS.md` 留在仓库内作索引；建议将本仓库加入工作区或符号链接，便于 Agent 发现全部 Skill。

### GitHub Actions 自动打包与安装验证

推送 `skill/` 或安装脚本变更到 `master` 时，[package-and-install-skills](.github/workflows/package-and-install-skills.yml) 流水线会：

1. **分别打包** — Windows 包：`skill/` + `install.ps1`；Unix 包：`skill/` + `install.sh`（无 `scripts/` 目录）
2. **Windows** — 解压后执行 `.\install.ps1`，安装到 `%USERPROFILE%\.codex\skills`、`%USERPROFILE%\.cursor\skills` 与 `%USERPROFILE%\.claude\skills`
3. **macOS / Linux** — 解压后执行 `bash install.sh`，安装到 `~/.codex/skills`、`~/.cursor/skills` 与 `~/.claude/skills`

在 GitHub **Actions** 页下载对应平台 Artifact，解压后在包根目录执行：

| 平台 | 命令 |
|------|------|
| Windows | `.\install.ps1` |
| macOS / Linux | `bash install.sh` |

也可在 Actions 页手动 **Run workflow** 触发。

---

## 目录结构

```text
AGENTS.md              # Agent 入口（Skill 索引）
README.md              # 本文件
README.en.md
UPGRADE.md
LICENSE
install.ps1
install.sh
skill/
  evolving-skill/
  skillopt-adapter/
  project-to-harness-skill/
  workspace-context-router/    # 含 references/、scripts/、assets/、agents/
  java-backend-troubleshooting/
  linux-test-executor/         # 含 references/、tools/、assets/
  read-wiki-via-mcp/           # 含 scripts/、agents/
eval/                          # Skill regression 用例
scripts/skillopt/              # 评分、proposal 生成与审查脚本
proposals/                     # SkillOpt 候选修改
```

**渐进披露：** `AGENTS.md` → `skill/<name>/SKILL.md` → `references/` / `tools/`。

---

## 快速开始

**Agent：** 读 [AGENTS.md](AGENTS.md) → 选 Skill → 执行 → 可复用经验先问用户。

**人类：** 新增或合并 Skill 见 [UPGRADE.md](UPGRADE.md)。

**SkillOpt 回归：**

```powershell
pwsh scripts/skillopt/score-skill.ps1 -Skill java-backend-troubleshooting
```

```bash
bash scripts/skillopt/score-skill.sh --skill java-backend-troubleshooting
```

---

## 设计原则

| 原则 | 做法 |
|------|------|
| 仓库即记录系统 | 不在仓库里的，Agent 不能稳定依赖 |
| 地图非手册 | 入口短；细节在各 `SKILL.md` |
| 先预览后写入 | Harness 化与沉淀须用户批准 |
| Skill 即知识单元 | 短、可执行、触发词清晰 |
| 优化不直写 | SkillOpt 输出先进 proposal，确认后才合并 |
| 收熵 | 合并重叠，删除过时 |

## 触发率维护

Skill 触发率低时，优先检查：

1. `AGENTS.md` 是否明确要求任务开始先读索引。
2. `AGENTS.md` 是否列出该 Skill 的路径和“何时用”。
3. `SKILL.md` frontmatter `description` 是否包含中英文任务说法、常见报错、工具/框架名。
4. 触发词是否只写在正文里；只写正文通常不够。
5. 空目录或缺 `SKILL.md` 的 Skill 不会稳定触发。

---

## 许可证

[MIT](LICENSE)
