---
name: cross-project-requirement
description: >-
  MUST use when a feature, change, or bug fix spans multiple repositories,
  services, applications, packages, or modules and the Agent must determine
  what each project/module does before planning or implementing. Use for
  多项目需求、多模块改造、跨仓库开发、跨服务联调、项目职责梳理、模块职责地图、
  需求影响分析、调用链梳理、multi-repo workspace、cross-repository change、
  cross-project implementation、service dependency mapping、impact analysis,
  多仓库统一分支、相同分支名、multi-repo branch alignment、same branch name,
  or when the user says the Agent does not know which project or module owns a
  responsibility. Builds or validates an evidence-backed project/module map,
  routes the requirement, orders compatible changes, and defines end-to-end
  verification. Not for understanding or documenting only one repository; use
  project-to-harness-skill for that.
---

# Cross-Project Requirement

先建立“谁负责什么、谁调用谁”的证据地图，再规划或实现跨项目需求。不要按目录名、仓库名或技术栈猜职责。

详细格式：

- 工作区地图：`references/map-schema.md`
- 需求影响与实施计划：`references/requirement-plan-template.md`

## 与其他 Skill 的边界

| 场景 | 使用方式 |
|------|----------|
| 单仓库知识提取、生成 `AGENTS.md` / Harness 文档 | 使用 `project-to-harness-skill` |
| 已有多个仓库，需要理解全局职责并完成一个跨仓需求 | 使用本 Skill |
| 单仓库缺少内部模块说明，阻碍跨仓分析 | 可先对该仓使用 `project-to-harness-skill`，再回到本 Skill；每次最多加载 2 个 Skill |

本 Skill 的地图放在**协调根目录**，不复制各仓库的详细内部文档。仓库内部事实仍以该仓库代码、`AGENTS.md` 和文档为准。

## 不可违反的规则

1. **先读后改**：完成只读发现和影响分析，才能修改业务代码。
2. **证据优先**：每条职责、依赖和接口结论都给出仓库相对路径或可定位符号。
3. **标注置信度**：仅使用 `[已验证]`、`[推断]`、`[未知]`；推断不得伪装成事实。
4. **使用稳定 ID**：项目为 `<project-id>`，模块为 `<project-id>:<module-id>`；不要只写容易重名的 `common`、`api`、`service`。
5. **区分静态依赖与运行时调用**：构建依赖不等于请求链路；分别记录。
6. **契约优先**：API、消息、数据库 schema、共享模型或文件格式发生变化时，先设计兼容策略，再排序实现。
7. **未知即阻塞项**：影响范围中的关键未知必须通过搜索、测试或用户确认关闭，不得默认为“不改”。
8. **尊重仓库规则**：进入每个项目时先读该项目自己的 `AGENTS.md`；冲突时以更靠近目标文件的规则为准。
9. **不静默覆盖文档**：已有地图采用增量合并；用户只要求分析时，不写入持久文档。
10. **多项目分支对齐**：两个及以上项目需要同时开发时，修改代码前必须提示用户让各仓库使用相同的分支名，并等待确认；不得静默创建或切换分支。

## 工作流

### 0. 确定协调根和任务模式

确认工作区根、纳入范围的仓库以及需求目标。不要把 `node_modules/`、构建产物、vendor 副本或示例目录当成项目。

选择模式：

- **建图模式**：首次接入多项目工作区，产出 `docs/cross-project/` 地图。
- **需求模式**：已有地图时先校验相关条目的新鲜度，再分析和实施需求。
- **临时分析**：用户只要方案时，在回复中输出地图与计划，不落盘。

### 1. 发现项目和模块

优先使用 `rg --files`、构建清单、包管理 workspace、容器/部署清单、CI 配置和已有文档发现边界。对每个候选项目：

1. 定位仓库根、构建根、部署单元和入口。
2. 读取就近 `AGENTS.md`、README、架构文档和构建清单。
3. 从路由/控制器、服务入口、导出 API、消息生产消费端、迁移文件和配置绑定中验证职责。
4. 记录项目、模块、公开契约、数据所有权和上下游；格式见 `references/map-schema.md`。

不要为了“完整”通读所有源码。先建立宽地图，再对需求命中的链路深挖。

### 2. 建立或校验工作区地图

建图模式默认预览以下结构，经用户同意后再写入协调根：

```text
docs/cross-project/
  README.md                 # 阅读顺序与更新时间
  project-map.md            # 项目清单与职责
  dependency-map.md         # 跨项目运行时调用和静态依赖
  projects/<project-id>.md  # 该项目的模块、契约、数据与验证入口
  requirements/<id>.md      # 可选；已批准的跨项目实施计划
```

若协调根有 `AGENTS.md`，仅增加上述索引和读取顺序；不得把详细地图塞进入口文件。若协调根不是版本库，先询问地图应归属哪个仓库。

已有地图时，至少重新校验本次涉及条目的证据路径、契约和测试命令。证据不存在或与代码冲突时，以当前代码为准并标记地图过期。

### 3. 路由需求并生成影响矩阵

把需求拆成可验收行为，逐条追踪：用户/系统入口 → 调用方 → 契约 → 提供方 → 数据或外部系统 → 回传/事件消费者。

对候选模块明确分类：

| 分类 | 含义 |
|------|------|
| `CHANGE` | 有证据表明必须修改 |
| `VERIFY` | 可能受影响，只需验证或补测试 |
| `NO_CHANGE` | 已检查且有证据说明无需修改 |
| `UNKNOWN` | 缺少关键证据，必须关闭未知 |

使用 `references/requirement-plan-template.md` 输出项目/模块影响矩阵。每个 `CHANGE` 必须关联验收条件、改动点、依赖和测试；每个 `NO_CHANGE` 必须写判断依据。

### 4. 对齐多项目开发分支

当影响矩阵中至少两个不同项目包含 `CHANGE`，且任务进入代码实施阶段时，执行以下门禁：

1. 在每个待改仓库运行只读 Git 检查，记录当前分支、detached HEAD、未提交改动以及目标分支是否已存在。
2. 按各仓库规则和需求 ID 生成一个**相同的目标分支名**。优先沿用项目约定；没有约定时建议 `<type>/<requirement-id>-<short-name>`。
3. 向用户展示分支对齐表，并明确提示：“本需求会同时修改 N 个项目，建议全部使用 `<target-branch>`，是否按此分支对齐？”
4. 用户确认前，不创建、不切换、不重命名分支，也不开始修改业务代码。
5. 用户确认后，逐仓安全创建或切换；保留已有改动。未提交改动可能与切换冲突时，停止该仓操作并说明，不自动 stash、丢弃或提交。
6. 用户拒绝统一分支或仓库策略不允许同名时，记录各仓库实际分支映射和联调风险，再按用户决定继续。

这里的“相同分支”是不同 Git 仓库使用相同的**分支名称**，不是共享同一个 Git ref。若所有待改仓库已经处于相同分支，报告“已对齐”并继续，无需重复切换。

### 5. 按兼容性排序实施

默认顺序不是简单的“后端先、前端后”，而是：

1. 建立可兼容契约：新增字段/接口/事件版本，保留旧消费者可用性。
2. 修改契约提供方和数据层，并完成提供方测试。
3. 修改各消费者/调用方，并完成项目级测试。
4. 执行跨项目集成或端到端验证。
5. 所有消费者迁移后，才安排破坏性清理；清理通常是独立变更。

若无法兼容，显式列出同步发布窗口、回滚点、数据迁移和失败恢复方案。

### 6. 分波次实现并持续校正地图

按实施波次修改代码。进入每个仓库前重新检查工作树和局部规则；保留用户已有改动。每完成一个波次：

- 运行该模块最快的相关测试。
- 核对下游契约假设。
- 更新影响矩阵状态。
- 新证据推翻原结论时，先修正计划再继续。

只有用户已授权持久化文档时，才同步更新 `docs/cross-project/`。一次性需求细节进入 `requirements/<id>.md`，长期职责只进入项目/依赖地图。

### 7. 完成验证与交付

至少按四层报告验证结果：

1. **模块级**：受改模块的单元/静态检查。
2. **项目级**：各项目构建或集成测试。
3. **契约级**：API schema、消息兼容、共享模型或数据库迁移验证。
4. **链路级**：跨项目关键验收场景与失败/回滚路径。

无法运行的层级必须写清原因、剩余风险和可执行命令。最终交付按项目列出实际改动，并说明地图是否更新。

## 完成标准

- [ ] 每个相关项目和模块都有稳定 ID、职责和证据
- [ ] 运行时调用、静态依赖、数据所有权没有混写
- [ ] 影响矩阵无未解释的 `UNKNOWN`
- [ ] 两个及以上项目同时开发时，已向用户确认同名分支，或记录用户批准的分支映射
- [ ] 契约变更有兼容、发布和回滚策略
- [ ] `CHANGE` 与验收条件、代码位置和测试一一对应
- [ ] 已完成模块、项目、契约、链路四层验证，或明确记录未完成项
- [ ] 持久地图只包含长期事实，并与当前代码证据一致
