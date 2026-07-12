# ai-skill-repository — Agent 入口

**强规则：进入本仓库处理任何任务时，先读本文件，再从 Skill 索引中选择相关 Skill。**

仓库：<https://github.com/Barry04/ai-skill-repository>

个人 Skill 库（含多个 Skill）：**不在仓库里的经验，对 Agent 不存在。**

> 设计参考：[Harness Engineering](https://github.com/deusyu/harness-engineering) — 人类掌舵，智能体执行；约束写在仓库里，用地图指路而非堆一本手册。

## 三步

1. **任务开始** → 先读本文件；从下表选最多 **2** 个相关 Skill，读其 `SKILL.md`
2. 按 Skill 执行任务；长细节在 `references/`，脚本在 `tools/`
3. **任务收尾** → 读 **evolving-skill**；发现可复用经验 → **先问用户**，同意后写入**当前项目** `skill/`

## Skill 索引

| Skill | 路径 | 何时用 |
|-------|------|--------|
| evolving-skill | `skill/evolving-skill/SKILL.md` | **任务收尾必读**；沉淀/合并 skill；用户确认后写项目 `skill/` |
| read-wiki-via-mcp | `skill/read-wiki-via-mcp/SKILL.md` | 通过本地 Atlassian MCP 读取、创建、更新 Confluence / wiki 页面 |
| java-backend-troubleshooting | `skill/java-backend-troubleshooting/SKILL.md` | Java / Spring / MyBatis 排错 |
| linux-test-executor | `skill/linux-test-executor/SKILL.md` | 远程 Linux 测试、SSH 部署验证 |
| project-to-harness-skill | `skill/project-to-harness-skill/SKILL.md` | 任意项目 → Harness 文档 + `skills/`（资格化、登记、preview-first） |
| workspace-context-router | `skill/workspace-context-router/SKILL.md` | 多项目/多模块请求定位；按 Manifest 路由项目、模块与上下文 |
| skillopt-adapter | `skill/skillopt-adapter/SKILL.md` | SkillOpt 优化 / benchmark / regression / proposal 审查 |

新增 Skill 后更新本表。

## 文件布局

```text
AGENTS.md          ← 你在这里（地图）
README.md          ← 人类总览（中文）
README.en.md       ← English overview
UPGRADE.md         ← 新增/合并 Skill 的维护约定
eval/              ← Skill 回归评测用例（不安装）
proposals/         ← SkillOpt 候选修改预览（用户确认后才合并）
skill/
  <name>/SKILL.md  ← 每个 Skill 一份，自包含可执行规则
```

## 原则

| 原则 | 做法 |
|------|------|
| 地图非手册 | 入口保持短小；细节下沉到各 Skill |
| 渐进披露 | 先索引 → 再 `SKILL.md` → 按需 `references/` |
| 用户确认才写 | 禁止静默新建或修改 Skill |
| 收熵 | 触发词重叠则合并；过时则删 |
| 提高触发率 | `description` 必须写入中文/英文触发词、报错文本、任务说法 |

## 安装

将全部 Skill 装到本机 Codex / Cursor / Claude Skills 目录：

| 平台 | 命令 |
|------|------|
| Windows | `.\install.ps1` |
| macOS / Linux | `bash install.sh` |
