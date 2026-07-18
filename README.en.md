# ai-skill-repository

[中文](README.md) · [GitHub](https://github.com/Barry04/ai-skill-repository)

A **personal Skill library** for AI agents — reusable engineering know-how in `skill/<name>/SKILL.md`, read on demand, evolved with user confirmation.

Inspired by [Harness Engineering](https://github.com/deusyu/harness-engineering).

> **Repo name:** `ai-skill-repository` · **Contains multiple skills**; `evolving-skill` is the evolution protocol (global); day-to-day skills live in each project's `skill/`.

---

## What this is

Not a single skill, knowledge base, or RAG platform — a versioned **collection of skills**:

- One directory per skill: `skill/<name>/SKILL.md`
- At most **2** skills per task
- Saves only after user confirmation ([evolving-skill](skill/evolving-skill/SKILL.md))
- SkillOpt produces offline eval/proposal artifacts; it never overwrites formal skills directly
- `install.ps1` / `install.sh` install **all** skills to Codex / Cursor / Claude

---

## Skills in this repo

### evolving-skill — evolution protocol (global install, project writes)

- **Protocol** → `~/.codex/skills/`, `~/.cursor/skills/`, `~/.claude/skills/` (via install)
- **Generated / evolved skills** → **current project** `skill/<name>/`

→ [skill/evolving-skill/SKILL.md](skill/evolving-skill/SKILL.md)

### project-to-harness-skill — project harness generator

Turn any project (new, active, legacy, open-source) into `AGENTS.md`, `docs/harness/`, and project `skills/`. Preview-first; no app source or build/deploy changes.

→ [skill/project-to-harness-skill/SKILL.md](skill/project-to-harness-skill/SKILL.md)

### workspace-context-router — multi-project context routing

Resolve a request to the correct repository and module from a human-reviewable
`workspace.yaml`, then load only the returned project context. Discovery emits
reviewable proposals; no SQLite database or automatic branch switching.

→ [skill/workspace-context-router/SKILL.md](skill/workspace-context-router/SKILL.md)

### cross-project-requirement — cross-repository feature orchestration

Build an evidence-backed project/module responsibility map, align branch names before concurrent multi-repo development, order compatible contract changes, and verify the full path.

→ [skill/cross-project-requirement/SKILL.md](skill/cross-project-requirement/SKILL.md)

### java-backend-troubleshooting — Java backend debugging

Spring transaction rollback, MyBatis pagination, and related Java service issues.

→ [skill/java-backend-troubleshooting/SKILL.md](skill/java-backend-troubleshooting/SKILL.md)

### linux-test-executor — remote Linux testing

SSH upload, remote commands, log collection; includes `tools/` scripts.

→ [skill/linux-test-executor/SKILL.md](skill/linux-test-executor/SKILL.md)

### read-wiki-via-mcp — read / update wiki

Read, create, and update Confluence / wiki pages through the local Atlassian MCP service.

→ [skill/read-wiki-via-mcp/SKILL.md](skill/read-wiki-via-mcp/SKILL.md)

### skillopt-adapter — SkillOpt optimization loop

Use for SkillOpt-driven skill optimization, benchmark, regression, validation
gate, or `best_skill.md` proposal review. SkillOpt output goes to
`experiments/skillopt/` and `proposals/`; formal `skill/<name>/SKILL.md`
changes still require user confirmation.

→ [skill/skillopt-adapter/SKILL.md](skill/skillopt-adapter/SKILL.md)

---

## Clone & install

```bash
git clone https://github.com/Barry04/ai-skill-repository.git
cd ai-skill-repository
```

| Platform | Command (from repo root or extracted bundle root) |
|----------|---------------------------------------------------|
| Windows | `.\install.ps1` |
| macOS / Linux | `bash install.sh` |

Scripts default to `skill/` next to themselves — no path argument needed after extract.

### CI: package & install

Workflow [.github/workflows/package-and-install-skills.yml](.github/workflows/package-and-install-skills.yml) builds separate Windows (`skill/` + `install.ps1`) and Unix (`skill/` + `install.sh`) zips, then verifies installation on Windows, macOS, and Linux. Download the platform **Artifact**, extract, run the install script from that folder.

Workflow [.github/workflows/skill-regression.yml](.github/workflows/skill-regression.yml) runs deterministic skill regression checks for eval-backed skills. CI does not call model optimization.

---

## Quick start

- **Agents:** [AGENTS.md](AGENTS.md) → pick a skill → execute → ask before saving
- **Humans:** [UPGRADE.md](UPGRADE.md) for maintenance

Skill regression:

```bash
bash scripts/skillopt/score-skill.sh --skill java-backend-troubleshooting
```

## Trigger reliability

If skills rarely trigger, check `AGENTS.md` first, then strengthen each `SKILL.md` frontmatter `description` with English and Chinese task wording, common errors, tool names, framework names, and explicit "when to use" phrases. Keywords only in the body are often too late.

---

## License

[Apache License 2.0](LICENSE)
