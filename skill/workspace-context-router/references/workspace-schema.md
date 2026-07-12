# Workspace Manifest 规范

本文定义 `workspace.yaml` 的字段、职责和路由语义。机器可校验版本见
`../assets/workspace.schema.json`，可复制的起始模板见
`../assets/workspace.example.yaml`。

## 目录

- [设计原则](#设计原则)
- [最小结构](#最小结构)
- [字段定义](#字段定义)
- [路径与变量](#路径与变量)
- [事实源边界](#事实源边界)
- [路由语义](#路由语义)
- [Capability 覆盖层](#capability-覆盖层)
- [Revision 校验](#revision-校验)
- [人工审核与 Proposal](#人工审核与-proposal)
- [校验规则](#校验规则)

## 设计原则

1. `workspace.yaml` 是人工批准的跨项目路由事实源，只回答“项目或模块在哪里”。
2. Manifest、候选和可选缓存都必须是 UTF-8 文本，能够直接阅读、审查和做 Git diff。
3. 禁止使用 SQLite 或其他数据库保存 Manifest、路由索引、Capability 或候选知识。
4. Router 不复制项目架构、命令、部署步骤或实现细节；它只通过 `context` 指向这些资料。
5. 自动发现只能生成 Proposal。未被人工接受的候选不得进入正式路由结果。
6. Capability 是 Project/Module 之上的多对多覆盖层，不是 Module 的子层。

## 最小结构

```yaml
version: 1
workspace: {}
projects:
  order-service:
    root: ${WORKSPACE_HOME}/order-service
```

`version`、`workspace` 和 `projects` 必填。`workspace.roots`、`modules`、
`revision`、`context` 和 `capabilities` 均为可选字段。

项目 ID、模块 ID 和 Capability ID 使用小写 ASCII 字母、数字、点、下划线或连字符，
且必须以字母或数字开头和结尾。对象键天然保证同一作用域内唯一：项目 ID 和
Capability ID 在 Manifest 内唯一，模块 ID 只在所属项目内唯一。

## 字段定义

### 顶层字段

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `version` | 是 | integer | Schema 主版本；当前固定为 `1` |
| `workspace` | 是 | object | Workspace 的扫描提示和导航上下文 |
| `projects` | 是 | map | `project-id -> Project`，至少一个项目 |
| `capabilities` | 否 | map | `capability-id -> Capability` 多对多覆盖层 |

未知字段默认视为错误，防止拼写错误被静默忽略。

### `workspace`

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `name` | 否 | string | 给人看的 Workspace 名称，不参与唯一标识 |
| `roots` | 否 | string[] | 自动发现的搜索根提示，不是项目路径事实源 |
| `context` | 否 | Context | Workspace 级导航入口 |

`roots` 不必覆盖每个项目，也不参与路由正确性判断。发现工具可以通过命令行
`--root` 接收临时扫描范围；正式项目位置始终读取 `projects.<id>.root`。

### `projects.<project-id>`

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `root` | 是 | string | 项目根目录，可包含环境变量占位符 |
| `aliases` | 否 | string[] | 经人工确认的项目别名，精确匹配信号 |
| `keywords` | 否 | string[] | 经人工确认的弱匹配词，只用于生成候选 |
| `revision` | 否 | Revision | 期望分支/版本及版本文件，只用于校验 |
| `context` | 否 | Context | 相对项目根目录的导航入口 |
| `modules` | 否 | map | `module-id -> Module`；ID 仅在本项目内唯一 |

不要在 Project 中写 Controller、DAO、部署流程或架构正文。这些内容属于项目自己的
`AGENTS.md`、构建文件、`docs/harness/` 或项目 Skill。

### `modules.<module-id>`

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `path` | 是 | string | 相对 `project.root` 的模块目录 |
| `aliases` | 否 | string[] | 经人工确认的模块别名，精确匹配信号 |
| `keywords` | 否 | string[] | 经人工确认的弱匹配词 |
| `context` | 否 | Context | 相对模块目录的导航入口 |

模块的结构事实仍以 Maven、Gradle、pnpm 等构建文件为准。Manifest 只登记路由需要的
稳定模块入口；校验器应报告 Manifest 与构建清单不一致的情况。

### `context`

`context` 只保存路径索引，不承载知识正文；对象存在时至少包含以下一项：

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `entrypoints` | 否 | string[] | `AGENTS.md` 等 Agent 入口 |
| `docs` | 否 | string[] | 架构、模块或业务文档 |
| `skills` | 否 | string[] | 与该范围相关的 Skill 入口 |

Router 应按需读取，不能因为命中项目就一次性加载所有 `docs` 和 `skills`。

### `revision`

`revision` 整段可选；存在时至少包含一项：

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `branch` | 否 | string | 期望或建议分支，不是当前分支快照 |
| `version` | 否 | string | 期望项目版本 |
| `version_file` | 否 | string | 相对项目根目录的结构化版本文件，如 `pom.xml` 或 `package.json` |

`version_file` 只指定检测来源。读取 XML、JSON、TOML 等结构化文件时必须使用对应解析器，
不得用脆弱的字符串替换读取或回写版本。

### `capabilities.<capability-id>`

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `aliases` | 否 | string[] | 经人工确认的能力别名 |
| `keywords` | 否 | string[] | 能力的弱匹配词 |
| `targets` | 是 | Target[] | 能力涉及的项目/模块引用，至少一个 |
| `context` | 否 | Context | 相对 Manifest 所在目录的能力导航入口 |
| `evidence` | 否 | string[] | 支撑能力定义和整体覆盖关系的可审查证据引用 |

### `targets[]`

| 字段 | 必填 | 类型 | 语义 |
|---|---:|---|---|
| `ref` | 是 | string | 全限定引用，固定格式为 `project-id/module-id` |
| `role` | 是 | enum | `owner`、`participant` 或 `observer` |
| `evidence` | 否 | string[] | 支撑该目标参与关系的证据引用 |

角色语义：

- `owner`：该能力的主要实现或业务归属；同一能力可以有多个 owner，但校验器应提示人工复核。
- `participant`：参与能力流程，修改时通常需要纳入影响分析候选。
- `observer`：消费事件、审计或通知等旁路参与者，默认只作为只读上下文候选。

证据可以是文档路径、构建模块、OpenAPI 操作、消息主题或稳定符号位置。证据用于人工审查，
不等于“该目标必须修改”，也不是 Router 的自动加载清单。只有同时登记在 `context` 且运行时
确认存在的路径才能进入 Agent 的上下文读取顺序。

## 路径与变量

- `project.root` 和 `workspace.roots[]` 可以是绝对路径，或包含 `${VAR}` 环境变量占位符。
- 环境变量未定义时，校验器报告错误；不得静默把未展开文本当作真实目录。
- Project 的 `context` 路径相对 `project.root`。
- Module 的 `path` 相对 `project.root`；Module 的 `context` 路径相对该模块目录。
- Workspace 和 Capability 的 `context` 路径相对 Manifest 所在目录。
- `revision.version_file` 相对 `project.root`。
- 相对路径不得通过 `..` 逃出所属范围。符号链接解析后也必须重新检查边界。
- 持久化路径使用 `/` 作为分隔符，运行时再转换为当前平台格式。

不要把某台机器的固定盘符复制到共享 Manifest。优先使用 `${WORKSPACE_HOME}` 之类的环境变量；
机器差异留在环境配置中。

## 事实源边界

Single Source of Truth 指“每类事实只有一个权威来源”，不是把所有知识塞入同一个文件。

| 事实 | 权威来源 |
|---|---|
| 项目 ID、项目根目录、人工别名、路由入口 | `workspace.yaml` |
| 当前 Git 分支和 commit | Git 工作树运行时状态 |
| 项目版本 | `version_file` 指向的项目文件或项目构建工具 |
| 模块真实结构 | Maven/Gradle/pnpm 等构建清单 |
| 架构、命令、部署和模块职责 | 项目 `AGENTS.md`、`docs/harness/` 和项目 Skill |
| 类、方法、引用关系 | 目标范围内的 `rg`、LSP、IDE 或构建工具 |
| 自动发现的未确认结果 | Proposal 文件，不是正式事实 |

Manifest 不得保存实时分支、扫描时间戳、绝对符号清单或运行结果。这类易变状态应在执行时读取。

## 路由语义

Resolver 必须返回少量结构化候选和匹配依据，而不是把整个 Manifest 注入 Agent 上下文。
推荐顺序：

1. 加载并校验 Manifest；非法 Manifest 不得参与路由。
2. 用当前目录缩小 Project 候选，但不能覆盖用户明确指定的项目。
3. 对 Project ID/alias 做精确匹配；在候选项目内对 Module ID/alias 做精确匹配。
4. 并行对 Capability ID/alias 做精确匹配，并将其 `targets` 展开为影响候选。
5. 只在没有充分精确匹配时使用 `keywords`；只有关键词命中时返回 `needs_confirmation`，不能单独断言唯一目标。
6. 合并并去重 Project/Module 与 Capability 目标，保留每条命中的来源和角色。
7. 命中唯一主目标后，先读取最窄范围的 `context.entrypoints`，再按任务需要读取文档或 Skill。
8. 多个候选仍无法区分时，向用户展示候选及依据并请求选择，不得猜测。

建议的路由结果至少包含：`project`、`module`、命中类型、命中词、Capability 角色、
实际根路径、revision 校验状态和歧义信息。Router 不自动修改任何项目文件。

## Capability 覆盖层

Capability 与 Project/Module 是多对多关系：

```text
用户意图
├── 直接命中 Project / Module
└── 命中 Capability
    ├── owner
    ├── participant
    └── observer
```

Capability 只预测需要检查的范围。Agent 必须读取代码、构建文件、调用关系或测试后，才能决定
实际修改范围。不得把所有 target 自动升级成“必须修改”，也不得因为 Capability 未登记就排除
代码证据指向的其他模块。

`ref` 必须使用 `project-id/module-id`，不能只写模块 ID，因为不同项目可以有同名模块。
JSON Schema 只能校验字符串格式；`validate` 命令还必须确认项目和模块真实存在。

## Revision 校验

Revision 是可选上下文校验，不参与项目身份、别名匹配或 Capability 展开：

- 未配置 `revision`：正常路由，显示实际分支/版本（若可检测）即可。
- 配置 `branch`：读取当前 Git 分支并比较；不一致时提示，不自动 `checkout`。
- 配置 `version`：从 `version_file` 或受支持的项目元数据读取实际版本并比较。
- 只配置 `version_file`：报告检测到的实际版本，不要求存在期望版本。
- 无法检测分支或版本：报告 `unknown` 或警告，不因缺少可选信息阻断定位。
- Router 禁止切换分支、创建分支、修改版本文件或自动回写 Manifest。

## 人工审核与 Proposal

自动扫描可以从构建文件、README、OpenAPI、Controller/Service 符号等来源提出 alias、keyword、
module 或 Capability 候选，但只能写入与正式 Manifest 分离的文本 Proposal。

每条 Proposal 至少应包含：

```yaml
kind: keyword
target: projects.order-service.modules.payment
value: 原路退回
source: openapi
evidence:
  - order-service/api/openapi.yaml#/paths/~1refunds
confidence: 0.91
last_seen: 2026-07-11
```

合并规则：

1. 生成 Proposal 时不得修改 `workspace.yaml`。
2. 人工检查候选值、证据、目标作用域和冲突后，明确接受的条目才可合并。
3. `confidence` 仅排序，不是自动批准阈值；模型推断永远需要人工确认。
4. 合并后由正式 Manifest 承担事实源职责；Proposal 不再参与路由。
5. 删除或重命名项目/模块时，先检查所有 Capability `ref`，避免悬空引用。
6. 自动刷新只能更新 Proposal 或可删除的文本缓存，不得覆盖人工字段。

证据来源优先级建议为：人工 alias > 项目文档/OpenAPI > 构建模块名 > 稳定代码符号 > 模型推断。

## 校验规则

JSON Schema 负责结构校验：必填字段、类型、未知字段、ID/`ref` 格式、枚举和数组去重。
Validator 还必须执行以下语义校验：

- 展开环境变量后，所有 `project.root` 均存在且没有意外重叠或重复。
- `module.path`、`version_file` 和各级 `context` 不越过其所属目录。
- 每个 Capability target 的 `project-id/module-id` 都指向已登记实体。
- `context` 指向的文件存在；`skills` 指向有效 Skill 入口。
- `revision.branch` 与实际分支、`revision.version` 与检测版本的差异只产生提示或警告。
- alias/keyword 在同一作用域内的冲突产生歧义报告，不由顺序静默决定胜者。
- 任何自动生成索引若存在，必须是格式化文本、可删除重建且不成为事实源。

Schema 校验通过不代表路由语义一定正确；正式使用前仍需运行 Validator 并人工审查差异。
