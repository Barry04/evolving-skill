---
name: workspace-context-router
description: >-
  MUST use to route a coding request across multiple repositories or modules
  before reading project context. Use for multi-project workspace routing,
  workspace.yaml setup or validation, repository/module discovery, project
  aliases, business capability routing, optional branch/version checks, or when
  the user repeatedly has to provide a project name, module name, or filesystem
  path. Trigger on 多项目、多仓库、多模块、项目定位、模块定位、工作区上下文、
  workspace manifest、workspace router、项目路径、分支校验、版本校验、业务能力路由.
---

# Workspace Context Router

在读取大范围代码前，将用户请求确定性地路由到项目和模块。只回答“去哪里、先读什么、为何匹配”；不要替代项目 Harness、代码搜索或变更影响分析。

## 核心约束

- 以可审查的 `workspace.yaml` 为路由事实源；禁止 SQLite、嵌入式数据库和不可读持久化索引。
- 保持 `AGENTS.md` 为轻量导航；架构、命令和工作流留在项目 `docs/harness/` 与 `skill/`。
- 不扫描整个工作区来处理每个请求；先路由，再在命中范围内使用 `rg`、LSP 或构建工具。
- 自动发现只输出 proposal；禁止静默修改 Manifest。
- `revision.branch` 和 `revision.version` 均可选，只做提示和校验；禁止自动切换分支或改版本。
- Capability 是跨项目/模块的影响候选覆盖层，不是 `Module` 的子层，也不代表所有目标都必须修改。
- 路由存在歧义、路径失效或 revision 不一致时，展示证据并让用户确认。

详细字段、优先级与示例见 [references/workspace-schema.md](references/workspace-schema.md)。创建 Manifest 时复制 [assets/workspace.example.yaml](assets/workspace.example.yaml)，机器校验契约见 [assets/workspace.schema.json](assets/workspace.schema.json)。

## 工作流

### 1. 找到 Manifest

按以下顺序使用第一个存在的文件：

1. 用户或命令显式传入的 `--manifest`
2. `AGENT_WORKSPACE_MANIFEST`
3. 当前目录向上的 `.agent-workspace/workspace.yaml` 或 `workspace.yaml`
4. `~/.agent-workspace/workspace.yaml`

找不到时，不要求用户逐个说明项目路径。先用 `discover` 生成候选预览，再请用户审核保存位置和别名。

### 2. 校验

首次使用、Manifest 变化或路径异常时运行：

```bash
python <skill-dir>/scripts/workspace_router.py validate --check-paths
```

缺少 YAML 解析依赖时，先在当前 Python 环境安装 `PyYAML>=6,<7`。不要用自制字符串解析替代 YAML 解析器。

校验失败时停止路由，报告字段路径和修复建议；不要猜测损坏的条目。

### 3. 解析请求

```bash
python <skill-dir>/scripts/workspace_router.py resolve \
  --query "给订单退款增加审计日志" \
  --cwd <current-directory>
```

按以下证据排序：当前目录所属项目、项目 ID/人工别名、模块 ID/人工别名、人工关键词、Capability 别名。只把自动候选当弱证据。

处理结果：

- `resolved`：读取返回的 context 文件，然后在目标范围工作。
- `ambiguous`：展示前几个候选、分数和匹配依据，只问一个消歧问题。
- `needs_confirmation`：只有弱关键词证据；展示候选并请求确认，不进入项目修改。
- `not_found`：运行发现流程或请用户确认一次映射，禁止全盘盲扫。

### 4. 渐进加载上下文

只读取解析结果 `context` 中 `exists=true` 的文件，顺序如下：

1. 项目根 `AGENTS.md`
2. 目标模块最近的 `AGENTS.md`
3. Manifest 明确登记且与任务相关的 context 文件
4. 项目 Harness 指向的架构、命令或 Skill

`evidence` 只用于解释和审核映射，不是自动加载清单；除非同一路径也明确登记在 `context` 且存在，否则不要读取。先说明定位结果与依据，再修改代码。不要因为 Capability 返回多个 target 就自动修改全部目标；先验证调用关系和实际影响。

### 5. 检查 revision

若项目登记了可选 revision：

- 动态读取实际 Git 分支；detached HEAD 时报告 commit。
- 按 `version_file` 或受支持的构建文件读取实际版本。
- 不一致时输出 expected/actual 并暂停修改，等待用户确认。
- 未登记或无法识别版本时，不阻断路由。

### 6. 演进映射

发现新的项目别名、模块别名、关键词或 Capability 时：

1. 记录候选值、证据来源和目标全限定 ID。
2. 生成可审查的 YAML proposal 或差异预览。
3. 询问用户是否合并。
4. 用户确认后才更新 `workspace.yaml`，再运行 `validate`。

禁止维护独立 `memory.json`、知识图数据库或与 Manifest 重复的人工索引。

## 工具

```bash
# 发现仓库/构建模块；默认只输出 YAML 预览
python <skill-dir>/scripts/workspace_router.py discover --root <workspace-root>

# 显式写入仍需用户已确认；已有文件必须再传 --force
python <skill-dir>/scripts/workspace_router.py discover \
  --root <workspace-root> --output <workspace.yaml>

# 显式 Manifest 适用于临时或多 Workspace 场景
python <skill-dir>/scripts/workspace_router.py validate \
  --manifest <workspace.yaml> --check-paths

python <skill-dir>/scripts/workspace_router.py resolve \
  --manifest <workspace.yaml> --query <request> --cwd <directory>
```

工具输出使用结构化 JSON；`discover` 的候选 Manifest 使用 YAML。Agent 应消费精简结果，不把整个 Workspace 内容塞入上下文。
