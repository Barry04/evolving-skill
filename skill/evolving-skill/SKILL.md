---
name: evolving-skill
description: >-
  MUST use at normal conversation/task wrap-up to decide whether reusable
  experience should be saved. Trigger before final response after a bug fix,
  code change, test/deploy flow, troubleshooting session, project setup, user
  correction, or any completed workflow that produced repeatable knowledge.
  Also use when saving reusable knowledge to the current project's skill/,
  merging or evolving project skills, end-of-task skill review, or skill
  lifecycle maintenance. Use when the user mentions 沉淀、保存 skill、写入
  skill、演进 skill、合并 skill、收熵、新建 skill、更新 skill 索引、以后都这样、
  记住这个做法. Ask the user before writing; never silent save. Complements
  domain skills; always run the task-end skill review when reusable experience
  appears, even if the user did not explicitly ask to save a skill. On first use
  in a project, check AGENTS.md for the evolving-skill task-end rule and ask the
  user before adding it.
---

# Evolving Skill Harness

**evolving-skill** 是演进**协议**（全局安装）；**生成或演化的 Skill** 写在**当前项目**的 `skill/` 下。

## 何时必须读（触发）

| 时机 | 触发词 / 场景 |
|------|----------------|
| **任务收尾** | 问题已解决、流程跑通，存在可复用经验 |
| **普通对话收尾** | 准备 final 前，刚完成代码修改、排错、测试、部署、项目配置或用户纠正，且有可重复做法 |
| **用户纠正** | 「以后都这样」「不要用 X」「保存下来」 |
| **显式请求** | 沉淀、保存 skill、写入 skill/、演进、合并 skill、收熵、新建 skill |
| **Harness 化之后** | project-to-harness-skill 完成，日常增量写入 `skill/` |

> 与领域 Skill（排错、部署等）**不互斥**：领域 Skill 解决「怎么做」；本协议管「做完要不要沉淀、怎么写进项目 skill/」。**任务结束时有可复用经验，必须读本 Skill；即使用户没有主动说“保存”，也要在 final 前做一次收尾判断。**

---

## 放在哪里

| 内容 | 位置 | 说明 |
|------|------|------|
| evolving-skill 协议 | `~/.codex/skills/evolving-skill/`、`~/.cursor/skills/evolving-skill/` 或 `~/.claude/skills/evolving-skill/` | `install.ps1` / `install.sh` 安装，跨项目通用 |
| 生成 / 演化的 Skill | **当前项目根** `skill/<name>/` | 随项目 Git 版本管理 |
| 项目 Agent 索引 | **当前项目根** `AGENTS.md` | 有新 Skill 时更新索引 |

**禁止**把日常沉淀写到全局 Skill 目录或 `ai-skill-repository` 仓库——除非用户明确要求且当前工作区就是该仓库。

确定项目根：以 Agent 当前工作区根目录为准；多仓库工作区时，经验归属用户正在改动的那个项目。

---

## 使用

### 首次进入项目：检查 AGENTS.md

**在本项目第一次因 evolving-skill 被加载时**（本对话内尚未检查过则视为第一次），读取**当前项目根** `AGENTS.md`（若存在），确认是否已写入 **evolving-skill 收尾规则**。

**视为「已有规则」**（满足其一即可）：

- 正文出现 `evolving-skill`，且同句或相邻句含「任务收尾」「收尾必读」「沉淀」之一
- Skill 索引表中有 `evolving-skill` 行，且「何时用」列含「收尾」或「沉淀」

**若 `AGENTS.md` 存在但缺少上述规则**：

1. 告知用户缺什么（一步/索引缺 evolving-skill 收尾说明）
2. **先问用户**是否补全；禁止静默修改
3. 用户同意后，按下方**推荐片段**合并进现有 `AGENTS.md`（保持 ≤ 60 行；有「三步」则改第 3 步，否则在 Skill 索引前增「Agent 三步」小节）

**推荐片段**（按需合并，勿重复堆砌）：

```markdown
## 三步

1. 从下表选最多 **2** 个相关 Skill，读其 `SKILL.md`
2. 按 Skill 执行任务；长细节在 `references/`，脚本在 `tools/`
3. **任务收尾** → 读 **evolving-skill**；发现可复用经验 → **先问用户**，同意后写入**当前项目** `skill/`
```

Skill 索引行：

```markdown
| evolving-skill | `skill/evolving-skill/SKILL.md` | **任务收尾必读**；沉淀/合并 skill；用户确认后写项目 `skill/` |
```

**若尚无 `AGENTS.md`**：提示用户可先跑 project-to-harness-skill，或询问是否新建最小 `AGENTS.md`（仍须用户确认后写入）。

**若用户拒绝补全**：本会话不再追问；照常执行收尾沉淀流程。

---

### 日常流程

任务开始或方向变化时：

1. 读**当前项目** `AGENTS.md`（若有），按问题、报错、模块名匹配 `skill/`
2. 可同时参考全局已安装 Skill（如 `java-backend-troubleshooting`），但**最多共 2 个**高相关 Skill
3. 无匹配且可重复 → 记下缺口，收尾时考虑在项目 `skill/` 新建
4. 无 `AGENTS.md` / `skill/` 时，提示用户先建立项目 Skill 结构（可读项目 `AGENTS.md` 或请用户说明入口）

---

### Final 前检查点

在发送最终回复前，快速判断本轮是否产生了可复用经验：

1. 是否完成了 bug 修复、代码改动、测试 / 部署流程、排错结论、项目初始化或用户纠正？
2. 是否有下一次可复用的命令、判断顺序、踩坑根因、配置约定或工作流？
3. 若答案为是，按「保存话术」询问用户是否沉淀；若只是一次性事实、敏感信息或未验证猜测，则不询问。

这一步用于普通对话收尾，不要求用户先说“沉淀”或“保存 skill”。

---

## 演进

**核心：可复用经验提示用户保存到当前项目 `skill/`，禁止静默写入。**

### 值得保存

- 已验证的 bug 根因 + 修复
- 可重复的构建 / 测试 / 部署命令流
- 框架踩坑（Spring 事务、MyBatis 分页等）
- 用户明确纠正：「以后都这样」「不要用 X」
- 远程测试机约定（用 `<host>` `<port>` 等占位符）

### 不要保存

- 密钥、token、生产主机等敏感信息
- 长日志、未验证猜测、一次性对话偏好
- 读代码就能看出的显而易见信息

### 何时问用户

- 问题已解决或流程已跑通，且经验可复用
- 用户刚纠正了做法
- 任务收尾时，还有未问过用户的沉淀项（同类最多 **3** 条）

用户已拒绝的同一条，本会话不再追问。

### 保存话术

```text
💡 可沉淀经验：<一句话摘要>

要保存到当前项目的 skill/<建议名>/ 吗？
- 新建
- 合并到 <已有 skill>
- 暂不
```

用户同意后：

1. 写入 `<项目根>/skill/<name>/SKILL.md`（及可选 `references/`、`tools/`）
2. 更新 `<项目根>/AGENTS.md` 索引
3. 告知完整路径，例如 `my-app/skill/payment-troubleshooting/SKILL.md`

---

## Skill 格式

```text
<project-root>/skill/<skill-name>/
  SKILL.md
  references/       # 可选
  tools/            # 可选
  assets/           # 可选
```

`SKILL.md` 最小结构：

```markdown
---
name: skill-name
description: 做什么 + 什么时候用（含触发词/报错/场景）
---

# 标题

## Purpose
...

## <主题>
触发词：...
规则：...
```

`name` 与目录名一致；`description` 写清触发场景。

---

## 维护

- 触发词重叠 → **合并**进同一项目内已有 Skill
- `SKILL.md` 保持精简；大块内容放 `references/`
- 发现错误或过时 → 修正或删除
- 新增 Skill 后更新**当前项目** `AGENTS.md`
