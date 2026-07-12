#!/usr/bin/env python3
"""Deterministic, reviewable workspace manifest discovery and routing CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    import yaml
except ImportError:  # Reported as JSON after argument parsing.
    yaml = None  # type: ignore[assignment]

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.11+ is recommended.
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


VERSION = 1
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
CONTEXT_KEYS = ("entrypoints", "docs", "skills")
ROLES = {"owner", "participant", "observer"}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
}
BUILD_MARKERS = (
    "pom.xml",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "pnpm-workspace.yaml",
    "Cargo.toml",
    "go.work",
    "pyproject.toml",
)


class CliFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 1,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliFailure("usage_error", message, exit_code=2)

    def print_help(self, file: Any | None = None) -> None:
        emit_json(
            {
                "status": "ok",
                "command": "help",
                "help": self.format_help(),
            },
            file=file,
        )


def emit_json(payload: Mapping[str, Any], file: Any | None = None) -> None:
    target = file or sys.stdout
    target.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def compact_text(value: str) -> str:
    return "".join(ch for ch in normalize_text(value) if ch.isalnum())


def unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = normalize_text(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def expand_env(value: str) -> tuple[str, list[str]]:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        replacement = os.environ.get(name)
        if replacement is None:
            missing.append(name)
            return match.group(0)
        return replacement

    return ENV_PATTERN.sub(replace, value), missing


def absolute_path(value: str, base: Path) -> tuple[Path | None, list[str]]:
    expanded, missing = expand_env(value)
    if missing:
        return None, missing
    candidate = Path(os.path.expanduser(expanded))
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False), []


def relative_path(value: str, base: Path) -> tuple[Path | None, list[str], str | None]:
    """Resolve a scope-relative path while preventing traversal and symlink escape."""
    violation = relative_path_syntax_violation(value)
    if violation:
        return None, [], violation
    expanded, missing = expand_env(value)
    if missing:
        return None, missing, None
    candidate = Path(os.path.expanduser(expanded))
    if candidate.is_absolute() or re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", expanded):
        return None, [], "absolute_after_expansion"
    resolved_base = base.resolve(strict=False)
    resolved = (resolved_base / candidate).resolve(strict=False)
    if not is_within(resolved, resolved_base):
        return None, [], "scope_escape"
    return resolved, [], None


def relative_path_syntax_violation(value: str) -> str | None:
    if re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", value):
        return "absolute"
    if ".." in re.split(r"[\\/]", value):
        return "parent_traversal"
    return None


def display_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def locate_manifest(explicit: str | None, start: Path) -> tuple[Path, str, list[str]]:
    searched: list[str] = []
    if explicit:
        expanded, missing = expand_env(explicit)
        if missing:
            raise CliFailure(
                "missing_environment_variable",
                "Manifest 路径包含未定义的环境变量。",
                details={"variables": sorted(set(missing)), "value": explicit},
            )
        path = Path(os.path.expanduser(expanded))
        if not path.is_absolute():
            path = start / path
        path = path.resolve(strict=False)
        if not path.is_file():
            raise CliFailure(
                "manifest_not_found",
                "显式指定的 Manifest 不存在或不是文件。",
                details={"path": display_path(path)},
            )
        return path, "argument", [display_path(path)]

    env_value = os.environ.get("AGENT_WORKSPACE_MANIFEST")
    if env_value:
        expanded, missing = expand_env(env_value)
        if missing:
            raise CliFailure(
                "missing_environment_variable",
                "AGENT_WORKSPACE_MANIFEST 包含未定义的环境变量。",
                details={"variables": sorted(set(missing)), "value": env_value},
            )
        path = Path(os.path.expanduser(expanded))
        if not path.is_absolute():
            path = start / path
        path = path.resolve(strict=False)
        searched.append(display_path(path))
        if not path.is_file():
            raise CliFailure(
                "manifest_not_found",
                "AGENT_WORKSPACE_MANIFEST 指向的文件不存在。",
                details={"path": display_path(path)},
            )
        return path, "environment", searched

    current = start.resolve(strict=False)
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        for candidate in (
            directory / ".agent-workspace" / "workspace.yaml",
            directory / "workspace.yaml",
        ):
            searched.append(display_path(candidate))
            if candidate.is_file():
                return candidate.resolve(strict=False), "ancestor", searched

    fallback = (Path.home() / ".agent-workspace" / "workspace.yaml").resolve(
        strict=False
    )
    searched.append(display_path(fallback))
    if fallback.is_file():
        return fallback, "home", searched
    raise CliFailure(
        "manifest_not_found",
        "未找到 Workspace Manifest。",
        details={"searched": searched},
    )


if yaml is not None:

    class NoDuplicateSafeLoader(yaml.SafeLoader):
        pass


    def construct_mapping(
        loader: Any, node: Any, deep: bool = False
    ) -> dict[Any, Any]:
        loader.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable mapping key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key: {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping


    NoDuplicateSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )


def require_yaml() -> None:
    if yaml is None:
        raise CliFailure(
            "dependency_missing",
            "缺少 PyYAML。请先运行 `python -m pip install PyYAML`。",
            exit_code=2,
            details={"package": "PyYAML"},
        )


def load_manifest(path: Path) -> dict[str, Any]:
    require_yaml()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise CliFailure(
            "manifest_read_failed",
            f"无法读取 Manifest：{exc}",
            details={"path": display_path(path)},
        ) from exc
    try:
        data = yaml.load(text, Loader=NoDuplicateSafeLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        details: dict[str, Any] = {"path": display_path(path)}
        if mark is not None:
            details.update({"line": mark.line + 1, "column": mark.column + 1})
        raise CliFailure(
            "manifest_parse_failed", f"Manifest YAML 解析失败：{exc}", details=details
        ) from exc
    if not isinstance(data, dict):
        raise CliFailure(
            "manifest_type_error",
            "Manifest 顶层必须是对象。",
            details={"path": display_path(path)},
        )
    return data


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def error(self, path: str, code: str, message: str) -> None:
        self.errors.append({"path": path, "code": code, "message": message})

    def warn(self, path: str, code: str, message: str) -> None:
        self.warnings.append({"path": path, "code": code, "message": message})


def validate_allowed_keys(
    value: Mapping[str, Any], allowed: set[str], path: str, report: ValidationReport
) -> None:
    for key in value:
        if key not in allowed:
            report.error(f"{path}.{key}", "unknown_field", "字段不在 v1 Schema 中。")


def validate_string_list(
    value: Any,
    path: str,
    report: ValidationReport,
    *,
    required: bool = False,
) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list):
        report.error(path, "type_error", "必须是字符串数组。")
        return []
    if not value:
        report.error(path, "empty_list", "数组不能为空。")
    result: list[str] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, str) or not item.strip():
            report.error(item_path, "type_error", "必须是非空字符串。")
            continue
        normalized = normalize_text(item)
        if normalized in seen:
            report.error(
                item_path,
                "duplicate_value",
                f"与 {path}[{seen[normalized]}] 重复（忽略大小写与 Unicode 形式）。",
            )
        else:
            seen[normalized] = index
            result.append(item)
    return result


def validate_context(
    value: Any,
    path: str,
    report: ValidationReport,
    *,
    check_paths: bool,
    base: Path | None,
) -> None:
    if not isinstance(value, dict):
        report.error(path, "type_error", "Context 必须是对象。")
        return
    validate_allowed_keys(value, set(CONTEXT_KEYS), path, report)
    present = False
    for key in CONTEXT_KEYS:
        if key not in value:
            continue
        values = validate_string_list(value[key], f"{path}.{key}", report, required=True)
        if values:
            present = True
        for index, item in enumerate(values):
            if base is None:
                violation = relative_path_syntax_violation(item)
                _, missing = expand_env(item)
                resolved = None
            else:
                resolved, missing, violation = relative_path(item, base)
            if violation:
                report.error(
                    f"{path}.{key}[{index}]",
                    "unsafe_relative_path",
                    "路径必须相对当前作用域，且不得是绝对路径、包含 .. 或经符号链接越界。",
                )
                continue
            if missing:
                method = report.error if check_paths else report.warn
                method(
                    f"{path}.{key}[{index}]",
                    "missing_environment_variable",
                    f"未定义环境变量：{', '.join(sorted(set(missing)))}。",
                )
            elif check_paths and resolved is not None and not resolved.is_file():
                report.error(
                    f"{path}.{key}[{index}]",
                    "path_not_found",
                    f"文件不存在：{display_path(resolved)}。",
                )
    if not present:
        report.error(path, "empty_context", "Context 至少需要一个非空路径数组。")


def validate_env_path(
    value: Any,
    path: str,
    report: ValidationReport,
    *,
    base: Path,
    check_paths: bool,
    expect_directory: bool,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        report.error(path, "type_error", "必须是非空路径字符串。")
        return None
    resolved, missing = absolute_path(value, base)
    if missing:
        method = report.error if check_paths else report.warn
        method(
            path,
            "missing_environment_variable",
            f"未定义环境变量：{', '.join(sorted(set(missing)))}。",
        )
        return None
    if check_paths and resolved is not None:
        valid = resolved.is_dir() if expect_directory else resolved.is_file()
        if not valid:
            expected = "目录" if expect_directory else "文件"
            report.error(
                path,
                "path_not_found",
                f"{expected}不存在：{display_path(resolved)}。",
            )
    return resolved


def validate_relative_path(
    value: Any,
    path: str,
    report: ValidationReport,
    *,
    base: Path | None,
    check_paths: bool,
    expect_directory: bool,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        report.error(path, "type_error", "必须是非空相对路径字符串。")
        return None
    if base is None:
        violation = relative_path_syntax_violation(value)
        _, missing = expand_env(value)
        resolved = None
    else:
        resolved, missing, violation = relative_path(value, base)
    if violation:
        report.error(
            path,
            "unsafe_relative_path",
            "路径必须相对当前作用域，且不得是绝对路径、包含 .. 或经符号链接越界。",
        )
        return None
    if missing:
        method = report.error if check_paths else report.warn
        method(
            path,
            "missing_environment_variable",
            f"未定义环境变量：{', '.join(sorted(set(missing)))}。",
        )
        return None
    if check_paths and resolved is not None:
        valid = resolved.is_dir() if expect_directory else resolved.is_file()
        if not valid:
            expected = "目录" if expect_directory else "文件"
            report.error(
                path,
                "path_not_found",
                f"{expected}不存在：{display_path(resolved)}。",
            )
    return resolved


def validate_manifest(
    data: Mapping[str, Any], manifest_path: Path, *, check_paths: bool
) -> ValidationReport:
    report = ValidationReport()
    base = manifest_path.parent
    validate_allowed_keys(data, {"version", "workspace", "projects", "capabilities"}, "$", report)

    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        report.error("$.version", "type_error", "version 必须是整数 1。")
    elif version != VERSION:
        report.error("$.version", "unsupported_version", f"仅支持 version: {VERSION}。")

    workspace = data.get("workspace")
    if not isinstance(workspace, dict):
        report.error("$.workspace", "type_error", "workspace 必须是对象。")
    else:
        validate_allowed_keys(workspace, {"name", "roots", "context"}, "$.workspace", report)
        if "name" in workspace and (
            not isinstance(workspace["name"], str) or not workspace["name"].strip()
        ):
            report.error("$.workspace.name", "type_error", "name 必须是非空字符串。")
        if "roots" in workspace:
            roots = validate_string_list(workspace["roots"], "$.workspace.roots", report, required=True)
            for index, root in enumerate(roots):
                validate_env_path(
                    root,
                    f"$.workspace.roots[{index}]",
                    report,
                    base=base,
                    check_paths=check_paths,
                    expect_directory=True,
                )
        if "context" in workspace:
            validate_context(
                workspace["context"],
                "$.workspace.context",
                report,
                check_paths=check_paths,
                base=base,
            )

    projects = data.get("projects")
    project_modules: dict[str, set[str]] = {}
    global_project_names: dict[str, str] = {}
    global_module_names: dict[str, list[str]] = defaultdict(list)
    resolved_project_roots: list[tuple[str, Path]] = []
    if not isinstance(projects, dict) or not projects:
        report.error("$.projects", "type_error", "projects 必须是非空对象。")
        projects = {}

    for project_id, project in projects.items():
        project_path = f"$.projects.{project_id}"
        project_id_is_string = isinstance(project_id, str)
        project_key = project_id if project_id_is_string else str(project_id)
        if (
            not project_id_is_string
            or len(project_id) > 64
            or not ID_PATTERN.fullmatch(project_id)
        ):
            report.error(project_path, "invalid_id", "project-id 必须为 1-64 位小写 ASCII ID，且不能以 .、_、- 结尾。")
        if not isinstance(project, dict):
            report.error(project_path, "type_error", "项目定义必须是对象。")
            continue
        validate_allowed_keys(
            project,
            {"root", "aliases", "keywords", "revision", "context", "modules"},
            project_path,
            report,
        )
        root = validate_env_path(
            project.get("root"),
            f"{project_path}.root",
            report,
            base=base,
            check_paths=check_paths,
            expect_directory=True,
        )
        if root is not None:
            for previous_id, previous_root in resolved_project_roots:
                if os.path.normcase(str(root)) == os.path.normcase(str(previous_root)):
                    report.error(
                        f"{project_path}.root",
                        "duplicate_project_root",
                        f"项目根目录与 {previous_id!r} 重复：{display_path(root)}。",
                    )
            resolved_project_roots.append((project_key, root))
        aliases = validate_string_list(project.get("aliases"), f"{project_path}.aliases", report)
        validate_string_list(project.get("keywords"), f"{project_path}.keywords", report)
        if project_id_is_string:
            for alias in [project_id, *aliases]:
                normalized = normalize_text(alias)
                previous = global_project_names.get(normalized)
                if previous and previous != project_id:
                    report.error(
                        f"{project_path}.aliases",
                        "duplicate_project_alias",
                        f"项目别名/ID {alias!r} 已被 {previous!r} 使用。",
                    )
                else:
                    global_project_names[normalized] = project_id

        revision = project.get("revision")
        if revision is not None:
            revision_path = f"{project_path}.revision"
            if not isinstance(revision, dict):
                report.error(revision_path, "type_error", "revision 必须是对象。")
            else:
                validate_allowed_keys(
                    revision, {"branch", "version", "version_file"}, revision_path, report
                )
                present = False
                for field in ("branch", "version", "version_file"):
                    if field not in revision:
                        continue
                    present = True
                    value = revision[field]
                    if not isinstance(value, str) or not value.strip():
                        report.error(
                            f"{revision_path}.{field}", "type_error", "必须是非空字符串。"
                        )
                if not present:
                    report.error(
                        revision_path,
                        "empty_revision",
                        "revision 至少需要 branch、version、version_file 之一。",
                    )
                if "version_file" in revision:
                    validate_relative_path(
                        revision["version_file"],
                        f"{revision_path}.version_file",
                        report,
                        base=root,
                        check_paths=check_paths,
                        expect_directory=False,
                    )

        if "context" in project:
            validate_context(
                project["context"],
                f"{project_path}.context",
                report,
                check_paths=check_paths,
                base=root,
            )

        modules = project.get("modules", {})
        if not isinstance(modules, dict):
            report.error(f"{project_path}.modules", "type_error", "modules 必须是对象。")
            modules = {}
        elif "modules" in project and not modules:
            report.error(f"{project_path}.modules", "empty_object", "modules 不能为空对象。")
        module_names: dict[str, str] = {}
        project_modules[project_key] = set()
        for module_id, module in modules.items():
            module_path = f"{project_path}.modules.{module_id}"
            module_id_is_string = isinstance(module_id, str)
            if module_id_is_string:
                project_modules[project_key].add(module_id)
            if (
                not module_id_is_string
                or len(module_id) > 64
                or not ID_PATTERN.fullmatch(module_id)
            ):
                report.error(module_path, "invalid_id", "module-id 必须为 1-64 位小写 ASCII ID，且不能以 .、_、- 结尾。")
            if not isinstance(module, dict):
                report.error(module_path, "type_error", "模块定义必须是对象。")
                continue
            validate_allowed_keys(
                module, {"path", "aliases", "keywords", "context"}, module_path, report
            )
            module_root = validate_relative_path(
                module.get("path"),
                f"{module_path}.path",
                report,
                base=root,
                check_paths=check_paths,
                expect_directory=True,
            )
            module_aliases = validate_string_list(
                module.get("aliases"), f"{module_path}.aliases", report
            )
            validate_string_list(module.get("keywords"), f"{module_path}.keywords", report)
            if module_id_is_string:
                for alias in [module_id, *module_aliases]:
                    normalized = normalize_text(alias)
                    previous = module_names.get(normalized)
                    if previous and previous != module_id:
                        report.error(
                            f"{module_path}.aliases",
                            "duplicate_module_alias",
                            f"同一项目内的模块别名/ID {alias!r} 已被 {previous!r} 使用。",
                        )
                    else:
                        module_names[normalized] = module_id
                    global_module_names[normalized].append(f"{project_key}/{module_id}")
            if "context" in module:
                validate_context(
                    module["context"],
                    f"{module_path}.context",
                    report,
                    check_paths=check_paths,
                    base=module_root,
                )

    for index, (project_id, root) in enumerate(resolved_project_roots):
        for other_id, other_root in resolved_project_roots[index + 1 :]:
            if root != other_root and (is_within(root, other_root) or is_within(other_root, root)):
                report.warn(
                    "$.projects",
                    "nested_project_roots",
                    f"项目根目录相互嵌套：{project_id!r} ({display_path(root)}) 与 {other_id!r} ({display_path(other_root)})。",
                )

    for normalized, refs in sorted(global_module_names.items()):
        unique_refs = sorted(set(refs))
        projects_for_ref = {ref.split("/", 1)[0] for ref in unique_refs}
        if len(projects_for_ref) > 1:
            report.warn(
                "$.projects",
                "cross_project_module_alias",
                f"模块名/别名 {normalized!r} 跨项目重复；无项目上下文时可能产生歧义：{', '.join(unique_refs)}。",
            )

    capabilities = data.get("capabilities", {})
    capability_names: dict[str, str] = {}
    if not isinstance(capabilities, dict):
        report.error("$.capabilities", "type_error", "capabilities 必须是对象。")
        capabilities = {}
    elif "capabilities" in data and not capabilities:
        report.error("$.capabilities", "empty_object", "capabilities 不能为空对象。")
    for capability_id, capability in capabilities.items():
        capability_path = f"$.capabilities.{capability_id}"
        capability_id_is_string = isinstance(capability_id, str)
        if (
            not capability_id_is_string
            or len(capability_id) > 64
            or not ID_PATTERN.fullmatch(capability_id)
        ):
            report.error(capability_path, "invalid_id", "capability-id 必须为 1-64 位小写 ASCII ID，且不能以 .、_、- 结尾。")
        if not isinstance(capability, dict):
            report.error(capability_path, "type_error", "Capability 定义必须是对象。")
            continue
        validate_allowed_keys(
            capability,
            {"aliases", "keywords", "targets", "context", "evidence"},
            capability_path,
            report,
        )
        aliases = validate_string_list(
            capability.get("aliases"), f"{capability_path}.aliases", report
        )
        validate_string_list(
            capability.get("keywords"), f"{capability_path}.keywords", report
        )
        validate_string_list(
            capability.get("evidence"), f"{capability_path}.evidence", report
        )
        if capability_id_is_string:
            for alias in [capability_id, *aliases]:
                normalized = normalize_text(alias)
                previous = capability_names.get(normalized)
                if previous and previous != capability_id:
                    report.error(
                        f"{capability_path}.aliases",
                        "duplicate_capability_alias",
                        f"Capability 别名/ID {alias!r} 已被 {previous!r} 使用。",
                    )
                else:
                    capability_names[normalized] = capability_id
        targets = capability.get("targets")
        if not isinstance(targets, list) or not targets:
            report.error(f"{capability_path}.targets", "type_error", "targets 必须是非空数组。")
            targets = []
        seen_targets: set[str] = set()
        for index, target in enumerate(targets):
            target_path = f"{capability_path}.targets[{index}]"
            if not isinstance(target, dict):
                report.error(target_path, "type_error", "target 必须是对象。")
                continue
            validate_allowed_keys(target, {"ref", "role", "evidence"}, target_path, report)
            ref = target.get("ref")
            if not isinstance(ref, str) or ref.count("/") != 1:
                report.error(
                    f"{target_path}.ref",
                    "invalid_ref",
                    "ref 必须是全限定的 project-id/module-id。",
                )
            else:
                project_id, module_id = ref.split("/", 1)
                if (
                    project_id not in project_modules
                    or module_id not in project_modules.get(project_id, set())
                ):
                    report.error(
                        f"{target_path}.ref",
                        "unknown_ref",
                        f"目标模块不存在：{ref}。",
                    )
                if ref in seen_targets:
                    report.error(
                        f"{target_path}.ref", "duplicate_target", f"目标重复：{ref}。"
                    )
                seen_targets.add(ref)
            role = target.get("role")
            if not isinstance(role, str) or role not in ROLES:
                report.error(
                    f"{target_path}.role",
                    "invalid_role",
                    "role 必须是 owner、participant 或 observer。",
                )
            validate_string_list(
                target.get("evidence"), f"{target_path}.evidence", report
            )
        if "context" in capability:
            validate_context(
                capability["context"],
                f"{capability_path}.context",
                report,
                check_paths=check_paths,
                base=base,
            )

    return report


def safe_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def detect_version(root: Path, explicit_file: str | None = None) -> tuple[str | None, str | None]:
    candidates = [explicit_file] if explicit_file else [
        "pom.xml",
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "gradle.properties",
    ]
    for relative in candidates:
        if not relative:
            continue
        if explicit_file:
            path, missing, violation = relative_path(relative, root)
        else:
            path, missing = absolute_path(relative, root)
            violation = None
        if violation or missing or path is None or not path.is_file():
            continue
        try:
            name = path.name.lower()
            if name == "package.json":
                value = json.loads(path.read_text(encoding="utf-8-sig")).get("version")
            elif name == "pom.xml":
                tree = ET.parse(path)
                root_node = tree.getroot()
                namespace = ""
                if root_node.tag.startswith("{"):
                    namespace = root_node.tag.split("}", 1)[0] + "}"
                node = root_node.find(f"{namespace}version")
                value = node.text.strip() if node is not None and node.text else None
            elif name in {"pyproject.toml", "cargo.toml"} and tomllib is not None:
                parsed = tomllib.loads(path.read_text(encoding="utf-8-sig"))
                if name == "cargo.toml":
                    value = parsed.get("package", {}).get("version")
                else:
                    value = parsed.get("project", {}).get("version")
                    if value is None:
                        value = parsed.get("tool", {}).get("poetry", {}).get("version")
            elif name == "gradle.properties":
                value = None
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    match = re.match(r"\s*version\s*=\s*(.+?)\s*$", line)
                    if match:
                        value = match.group(1)
                        break
            else:
                value = next(
                    (
                        line.strip()
                        for line in path.read_text(encoding="utf-8-sig").splitlines()
                        if line.strip()
                    ),
                    None,
                )
            if isinstance(value, (str, int, float)) and str(value).strip():
                try:
                    detected_relative_path = path.relative_to(root).as_posix()
                except ValueError:
                    detected_relative_path = display_path(path)
                return str(value).strip(), detected_relative_path
        except (OSError, ValueError, ET.ParseError, json.JSONDecodeError):
            continue
    return None, None


def revision_status(project: Mapping[str, Any], root: Path) -> dict[str, Any]:
    revision = project.get("revision")
    expected = revision if isinstance(revision, dict) else {}
    expected_branch = expected.get("branch") if isinstance(expected.get("branch"), str) else None
    expected_version = expected.get("version") if isinstance(expected.get("version"), str) else None
    version_file = expected.get("version_file") if isinstance(expected.get("version_file"), str) else None
    actual_branch = safe_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    actual_commit = safe_git(root, "rev-parse", "HEAD")
    if actual_branch == "HEAD":
        actual_branch = None
    actual_version, detected_file = detect_version(root, version_file)

    def comparison(expected_value: str | None, actual_value: str | None) -> str:
        if expected_value is None:
            return "not_configured"
        if actual_value is None:
            return "unknown"
        return "match" if expected_value == actual_value else "mismatch"

    branch_status = comparison(expected_branch, actual_branch)
    version_status = comparison(expected_version, actual_version)
    compared = [status for status in (branch_status, version_status) if status != "not_configured"]
    if "mismatch" in compared:
        overall = "mismatch"
    elif "unknown" in compared:
        overall = "unknown"
    elif compared:
        overall = "match"
    else:
        overall = "not_configured"
    if overall == "mismatch":
        action = "confirm_before_changes"
    elif overall == "unknown":
        action = "verify_before_changes"
    else:
        action = "report_only"
    return {
        "expected": {
            "branch": expected_branch,
            "version": expected_version,
            "version_file": version_file,
        },
        "actual": {
            "branch": actual_branch,
            "commit": actual_commit,
            "version": actual_version,
            "version_file": detected_file,
        },
        "status": {
            "branch": branch_status,
            "version": version_status,
            "overall": overall,
        },
        "action": action,
    }


def context_entries(
    context: Any, base: Path, scope: str
) -> list[dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    entries: list[dict[str, Any]] = []
    for category in CONTEXT_KEYS:
        values = context.get(category, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            resolved, missing, violation = relative_path(value, base)
            entries.append(
                {
                    "scope": scope,
                    "category": category,
                    "configured": value,
                    "path": display_path(resolved) if resolved is not None else None,
                    "exists": resolved.exists() if resolved is not None else False,
                    "missing_environment_variables": sorted(set(missing)),
                    "path_violation": violation,
                }
            )
    return entries


def term_evidence(
    query: str,
    term: str,
    field: str,
    weights: tuple[int, int, int],
) -> dict[str, Any] | None:
    query_normalized = normalize_text(query)
    term_normalized = normalize_text(term)
    query_compact = compact_text(query)
    term_compact = compact_text(term)
    if not query_compact or not term_compact:
        return None
    if query_normalized == term_normalized or query_compact == term_compact:
        match, points = "exact", weights[0]
    elif len(term_compact) >= 2 and term_compact in query_compact:
        match, points = "contained", weights[1]
    elif len(query_compact) >= 2 and query_compact in term_compact:
        match, points = "partial", weights[2]
    else:
        return None
    return {"field": field, "term": term, "match": match, "points": points}


def score_terms(
    query: str, fields: Sequence[tuple[str, Iterable[str], tuple[int, int, int]]]
) -> tuple[int, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    for field, terms, weights in fields:
        best: dict[str, Any] | None = None
        for term in terms:
            if not isinstance(term, str):
                continue
            match = term_evidence(query, term, field, weights)
            if match is not None and (best is None or match["points"] > best["points"]):
                best = match
        if best is not None:
            evidence.append(best)
    return sum(item["points"] for item in evidence), evidence


def project_root(project: Mapping[str, Any], manifest_path: Path) -> Path | None:
    value = project.get("root")
    if not isinstance(value, str):
        return None
    resolved, missing = absolute_path(value, manifest_path.parent)
    return None if missing else resolved


def route_candidates(
    data: Mapping[str, Any], manifest_path: Path, query: str, cwd: Path
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        return candidates
    workspace_context = data.get("workspace", {}).get("context") if isinstance(data.get("workspace"), dict) else None
    for project_id, project in projects.items():
        if not isinstance(project_id, str) or not isinstance(project, dict):
            continue
        root = project_root(project, manifest_path)
        project_score, project_evidence = score_terms(
            query,
            (
                ("project.id", [project_id], (120, 70, 40)),
                ("project.aliases", project.get("aliases", []), (140, 90, 45)),
                ("project.keywords", project.get("keywords", []), (60, 35, 15)),
            ),
        )
        if root is not None and is_within(cwd, root):
            project_score += 25
            project_evidence.append(
                {"field": "cwd", "term": display_path(root), "match": "within", "points": 25}
            )
        if project_score:
            contexts = context_entries(workspace_context, manifest_path.parent, "workspace")
            if root is not None:
                contexts += context_entries(project.get("context"), root, f"project:{project_id}")
            candidates.append(
                {
                    "kind": "project",
                    "ref": project_id,
                    "score": project_score,
                    "evidence": project_evidence,
                    "project_root": display_path(root) if root is not None else None,
                    "module_root": None,
                    "context": contexts,
                }
            )
        modules = project.get("modules", {})
        if not isinstance(modules, dict):
            continue
        for module_id, module in modules.items():
            if not isinstance(module_id, str) or not isinstance(module, dict):
                continue
            module_score, module_evidence = score_terms(
                query,
                (
                    ("module.id", [module_id], (150, 100, 50)),
                    ("module.path", [module.get("path", "")], (100, 60, 30)),
                    ("module.aliases", module.get("aliases", []), (180, 120, 60)),
                    ("module.keywords", module.get("keywords", []), (80, 50, 20)),
                ),
            )
            if not module_score:
                continue
            total_score = module_score + project_score
            module_root = None
            if root is not None and isinstance(module.get("path"), str):
                module_root, _, _ = relative_path(module["path"], root)
            contexts = context_entries(workspace_context, manifest_path.parent, "workspace")
            if root is not None:
                contexts += context_entries(project.get("context"), root, f"project:{project_id}")
            if module_root is not None:
                contexts += context_entries(
                    module.get("context"), module_root, f"module:{project_id}/{module_id}"
                )
            candidates.append(
                {
                    "kind": "module",
                    "ref": f"{project_id}/{module_id}",
                    "score": total_score,
                    "evidence": project_evidence + module_evidence,
                    "project_root": display_path(root) if root is not None else None,
                    "module_root": display_path(module_root) if module_root is not None else None,
                    "context": contexts,
                }
            )

    capabilities = data.get("capabilities", {})
    if isinstance(capabilities, dict):
        for capability_id, capability in capabilities.items():
            if not isinstance(capability_id, str) or not isinstance(capability, dict):
                continue
            score, evidence = score_terms(
                query,
                (
                    ("capability.id", [capability_id], (170, 110, 50)),
                    ("capability.aliases", capability.get("aliases", []), (220, 160, 80)),
                    ("capability.keywords", capability.get("keywords", []), (100, 65, 30)),
                ),
            )
            if not score:
                continue
            contexts = context_entries(workspace_context, manifest_path.parent, "workspace")
            contexts += context_entries(
                capability.get("context"), manifest_path.parent, f"capability:{capability_id}"
            )
            targets: list[dict[str, Any]] = []
            for target in capability.get("targets", []):
                if not isinstance(target, dict) or not isinstance(target.get("ref"), str):
                    continue
                ref = target["ref"]
                target_info: dict[str, Any] = {
                    "ref": ref,
                    "role": target.get("role"),
                    "evidence": target.get("evidence", []),
                    "impact": "candidate_only",
                }
                if ref.count("/") == 1:
                    target_project_id, target_module_id = ref.split("/", 1)
                    target_project = projects.get(target_project_id)
                    if isinstance(target_project, dict):
                        target_root = project_root(target_project, manifest_path)
                        target_module = target_project.get("modules", {}).get(target_module_id) if isinstance(target_project.get("modules"), dict) else None
                        target_module_root = None
                        if (
                            target_root is not None
                            and isinstance(target_module, dict)
                            and isinstance(target_module.get("path"), str)
                        ):
                            target_module_root, _, _ = relative_path(
                                target_module["path"], target_root
                            )
                        target_info["project_root"] = (
                            display_path(target_root) if target_root is not None else None
                        )
                        target_info["module_root"] = (
                            display_path(target_module_root)
                            if target_module_root is not None
                            else None
                        )
                        target_context = []
                        if target_root is not None:
                            target_context += context_entries(
                                target_project.get("context"),
                                target_root,
                                f"project:{target_project_id}",
                            )
                        if target_module_root is not None and isinstance(target_module, dict):
                            target_context += context_entries(
                                target_module.get("context"),
                                target_module_root,
                                f"module:{ref}",
                            )
                        target_info["context"] = target_context
                targets.append(target_info)
            candidates.append(
                {
                    "kind": "capability",
                    "ref": capability_id,
                    "score": score,
                    "evidence": evidence,
                    "capability_evidence": capability.get("evidence", []),
                    "impact_candidates": targets,
                    "context": contexts,
                }
            )
    candidates.sort(key=lambda item: (-item["score"], item["kind"], item["ref"]))
    return candidates


def has_strong_routing_evidence(candidate: Mapping[str, Any]) -> bool:
    evidence = candidate.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("field"), str)
        and not item["field"].endswith(".keywords")
        for item in evidence
    )


def candidate_path_issues(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def require_directory(ref: str, field: str, value: Any) -> None:
        if not isinstance(value, str) or not value:
            issues.append(
                {
                    "ref": ref,
                    "field": field,
                    "code": "path_unresolved",
                    "message": "目标目录无法展开；请检查环境变量和 Manifest。",
                }
            )
            return
        path = Path(value)
        if not path.is_dir():
            issues.append(
                {
                    "ref": ref,
                    "field": field,
                    "code": "path_not_found",
                    "message": f"目标目录不存在：{display_path(path)}。",
                }
            )

    kind = candidate.get("kind")
    ref = str(candidate.get("ref", "unknown"))
    if kind in {"project", "module"}:
        require_directory(ref, "project_root", candidate.get("project_root"))
        if kind == "module":
            require_directory(ref, "module_root", candidate.get("module_root"))
    elif kind == "capability":
        targets = candidate.get("impact_candidates", [])
        if not isinstance(targets, list) or not targets:
            issues.append(
                {
                    "ref": ref,
                    "field": "impact_candidates",
                    "code": "targets_missing",
                    "message": "Capability 没有可验证的目标模块。",
                }
            )
        for target in targets:
            if not isinstance(target, dict):
                continue
            target_ref = str(target.get("ref", "unknown"))
            require_directory(target_ref, "project_root", target.get("project_root"))
            require_directory(target_ref, "module_root", target.get("module_root"))
    return issues


def deduplicate_context(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for entry in entries:
        key = (entry.get("scope"), entry.get("category"), entry.get("path"), entry.get("configured"))
        if key not in seen:
            seen.add(key)
            result.append(dict(entry))
    return result


def resolve_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    start = Path(args.cwd or os.getcwd()).resolve(strict=False)
    manifest_path, source, searched = locate_manifest(args.manifest, start)
    data = load_manifest(manifest_path)
    validation = validate_manifest(data, manifest_path, check_paths=False)
    if validation.errors:
        return (
            {
                "status": "error",
                "command": "resolve",
                "manifest_path": display_path(manifest_path),
                "manifest_source": source,
                "error": {
                    "code": "manifest_invalid",
                    "message": "Manifest 未通过结构校验，无法路由。",
                    "details": {"errors": validation.errors, "warnings": validation.warnings},
                },
            },
            1,
        )
    query = args.query_option if args.query_option is not None else args.query
    if not isinstance(query, str) or not query.strip():
        raise CliFailure("query_required", "resolve 需要非空查询文本。", exit_code=2)
    candidates = route_candidates(data, manifest_path, query, start)
    candidates = [item for item in candidates if item["score"] >= args.min_score]
    visible = candidates[: args.limit]
    top: dict[str, Any] | None = None
    if not candidates:
        resolution_status = "not_found"
        selection = None
        ambiguous = []
        exit_code = 4
    else:
        top = candidates[0]
        ambiguous = [
            item
            for item in candidates[1:]
            if top["score"] - item["score"] <= args.ambiguity_delta
        ]
        if ambiguous:
            resolution_status = "ambiguous"
            selection = None
            exit_code = 3
        elif not has_strong_routing_evidence(top):
            resolution_status = "needs_confirmation"
            selection = None
            exit_code = 3
        else:
            resolution_status = "resolved"
            selection = top
            exit_code = 0

    if selection is not None:
        path_issues = candidate_path_issues(selection)
        if path_issues:
            return (
                {
                    "status": "error",
                    "command": "resolve",
                    "manifest_path": display_path(manifest_path),
                    "manifest_source": source,
                    "query": query,
                    "resolution": "invalid_target",
                    "selection": selection,
                    "error": {
                        "code": "target_path_invalid",
                        "message": "路由目标目录不可用，不能宣布解析成功。",
                        "details": {
                            "issues": path_issues,
                            "validation_warnings": validation.warnings,
                        },
                    },
                },
                1,
            )
    selected_context: list[dict[str, Any]] = []
    impact_candidates: list[dict[str, Any]] = []
    revision: dict[str, Any] | None = None
    if selection is not None:
        selected_context.extend(selection.get("context", []))
        if selection["kind"] == "capability":
            impact_candidates = selection.get("impact_candidates", [])
            for target in impact_candidates:
                selected_context.extend(target.get("context", []))
        project_id = None
        if selection["kind"] == "project":
            project_id = selection["ref"]
        elif selection["kind"] == "module":
            project_id = selection["ref"].split("/", 1)[0]
        if project_id:
            project = data.get("projects", {}).get(project_id)
            if isinstance(project, dict):
                root = project_root(project, manifest_path)
                if root is not None:
                    revision = revision_status(project, root)
        elif selection["kind"] == "capability":
            for target in impact_candidates:
                ref = target.get("ref")
                if not isinstance(ref, str) or ref.count("/") != 1:
                    continue
                target_project_id = ref.split("/", 1)[0]
                target_project = data.get("projects", {}).get(target_project_id)
                if isinstance(target_project, dict):
                    root = project_root(target_project, manifest_path)
                    if root is not None:
                        target["revision"] = revision_status(target_project, root)

    payload = {
        "status": "ok" if exit_code == 0 else resolution_status,
        "command": "resolve",
        "manifest_path": display_path(manifest_path),
        "manifest_source": source,
        "manifest_search": searched,
        "query": query,
        "resolution": resolution_status,
        "selection": selection,
        "ambiguous_with": ambiguous[: args.limit],
        "confirmation_candidate": top if resolution_status == "needs_confirmation" else None,
        "candidates": visible,
        "impact_candidates": impact_candidates,
        "context": deduplicate_context(selected_context),
        "revision": revision,
        "validation_warnings": validation.warnings,
        "policy": {
            "impact_candidates_require_code_verification": True,
            "automatic_git_checkout": False,
            "automatic_manifest_write": False,
            "database_index": False,
        },
    }
    return payload, exit_code


def validate_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    start = Path(args.cwd or os.getcwd()).resolve(strict=False)
    manifest_path, source, searched = locate_manifest(args.manifest, start)
    data = load_manifest(manifest_path)
    report = validate_manifest(data, manifest_path, check_paths=args.check_paths)
    valid = not report.errors
    return (
        {
            "status": "ok" if valid else "invalid",
            "command": "validate",
            "manifest_path": display_path(manifest_path),
            "manifest_source": source,
            "manifest_search": searched,
            "valid": valid,
            "path_checks": args.check_paths,
            "errors": report.errors,
            "warnings": report.warnings,
            "summary": {
                "error_count": len(report.errors),
                "warning_count": len(report.warnings),
            },
        },
        0 if valid else 1,
    )


def slugify(value: str, fallback: str = "project") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9._-]+", "-", normalized.casefold()).strip("-._")
    if not slug:
        slug = fallback
    if not slug[0].isalnum():
        slug = f"{fallback}-{slug}".strip("-")
    return slug[:63].rstrip("-._") or fallback


def has_build_marker(directory: Path) -> bool:
    if any((directory / marker).is_file() for marker in BUILD_MARKERS):
        return True
    try:
        return any(directory.glob("*.sln"))
    except OSError:
        return False


def discover_project_roots(roots: Sequence[Path], max_depth: int) -> list[Path]:
    discovered: dict[str, tuple[Path, bool]] = {}
    for root in roots:
        root = root.resolve(strict=False)
        if not root.is_dir():
            raise CliFailure(
                "root_not_found",
                "discover 根目录不存在或不是目录。",
                details={"path": display_path(root)},
            )
        queue: deque[tuple[Path, int]] = deque([(root, 0)])
        while queue:
            directory, depth = queue.popleft()
            try:
                is_git = (directory / ".git").exists()
                if is_git:
                    key = os.path.normcase(display_path(directory))
                    discovered[key] = (directory, True)
                    continue
                if has_build_marker(directory):
                    key = os.path.normcase(display_path(directory))
                    discovered[key] = (directory, False)
                if depth >= max_depth:
                    continue
                children = sorted(
                    (
                        item
                        for item in directory.iterdir()
                        if item.is_dir() and item.name not in SKIP_DIRS and not item.is_symlink()
                    ),
                    key=lambda item: normalize_text(item.name),
                )
                queue.extend((child, depth + 1) for child in children)
            except (OSError, PermissionError):
                continue

    candidates = [discovered[key] for key in sorted(discovered)]
    git_roots = [path for path, is_git in candidates if is_git]
    non_git_roots = [path for path, is_git in candidates if not is_git]
    kept_non_git: list[Path] = []
    for candidate in sorted(non_git_roots, key=lambda path: len(path.parts)):
        if any(candidate != git_root and is_within(git_root, candidate) for git_root in git_roots):
            continue
        if any(candidate != parent and is_within(candidate, parent) for parent in kept_non_git):
            continue
        kept_non_git.append(candidate)
    return sorted([*git_roots, *kept_non_git], key=lambda path: os.path.normcase(display_path(path)))


def expand_workspace_patterns(root: Path, patterns: Iterable[str]) -> list[str]:
    results: list[str] = []
    for pattern in patterns:
        if not isinstance(pattern, str) or pattern.startswith("!"):
            continue
        normalized = pattern.replace("\\", "/").strip("/")
        if not normalized:
            continue
        try:
            matches = root.glob(normalized)
            for match in matches:
                if match.is_dir() and not any(part in SKIP_DIRS for part in match.parts):
                    results.append(match.relative_to(root).as_posix())
        except (OSError, ValueError):
            continue
    return unique_strings(results)


def maven_modules(root: Path) -> list[str]:
    path = root / "pom.xml"
    if not path.is_file():
        return []
    try:
        tree = ET.parse(path)
        root_node = tree.getroot()
        namespace = ""
        if root_node.tag.startswith("{"):
            namespace = root_node.tag.split("}", 1)[0] + "}"
        modules = root_node.find(f"{namespace}modules")
        if modules is None:
            return []
        return unique_strings(
            node.text.strip().replace("\\", "/")
            for node in modules.findall(f"{namespace}module")
            if node.text and node.text.strip()
        )
    except (OSError, ET.ParseError):
        return []


def gradle_modules(root: Path) -> list[str]:
    settings = next(
        (path for path in (root / "settings.gradle", root / "settings.gradle.kts") if path.is_file()),
        None,
    )
    if settings is None:
        return []
    try:
        text = settings.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    project_dirs: dict[str, str] = {}
    for match in re.finditer(
        r"project\(\s*['\"](:[^'\"]+)['\"]\s*\)\.projectDir\s*=\s*(?:file\()?\s*['\"]([^'\"]+)['\"]",
        text,
    ):
        project_dirs[match.group(1)] = match.group(2).replace("\\", "/")
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("include"):
            continue
        names.extend(re.findall(r"['\"](:[^'\"]+)['\"]", stripped))
    paths = [project_dirs.get(name, name.lstrip(":").replace(":", "/")) for name in names]
    return unique_strings(path for path in paths if path)


def node_modules(root: Path) -> list[str]:
    patterns: list[str] = []
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8-sig"))
            workspaces = package.get("workspaces", [])
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            if isinstance(workspaces, list):
                patterns.extend(item for item in workspaces if isinstance(item, str))
        except (OSError, json.JSONDecodeError):
            pass
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file() and yaml is not None:
        try:
            parsed = yaml.safe_load(pnpm.read_text(encoding="utf-8-sig"))
            if isinstance(parsed, dict) and isinstance(parsed.get("packages"), list):
                patterns.extend(item for item in parsed["packages"] if isinstance(item, str))
        except (OSError, yaml.YAMLError):
            pass
    return expand_workspace_patterns(root, patterns)


def cargo_modules(root: Path) -> list[str]:
    path = root / "Cargo.toml"
    if not path.is_file() or tomllib is None:
        return []
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        members = parsed.get("workspace", {}).get("members", [])
        if isinstance(members, list):
            return expand_workspace_patterns(root, members)
    except (OSError, ValueError):
        pass
    return []


def go_modules(root: Path) -> list[str]:
    path = root / "go.work"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    paths: list[str] = []
    in_use = False
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if line.startswith("use ("):
            in_use = True
            continue
        if in_use and line == ")":
            in_use = False
            continue
        if in_use and line:
            paths.append(line.strip('"').removeprefix("./"))
        elif line.startswith("use "):
            paths.append(line[4:].strip().strip('"').removeprefix("./"))
    return unique_strings(paths)


def solution_modules(root: Path) -> list[str]:
    results: list[str] = []
    for solution in sorted(root.glob("*.sln")):
        try:
            text = solution.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'^Project\([^\n]+?=\s*"[^"]+",\s*"([^"]+\.(?:csproj|fsproj|vbproj))"', text, re.MULTILINE | re.IGNORECASE):
            candidate = match.group(1).replace("\\", "/")
            results.append(str(Path(candidate).parent).replace("\\", "/"))
    return unique_strings(path for path in results if path not in {"", "."})


def detect_modules(root: Path) -> list[str]:
    candidates = [
        *maven_modules(root),
        *gradle_modules(root),
        *node_modules(root),
        *cargo_modules(root),
        *go_modules(root),
        *solution_modules(root),
    ]
    valid: list[str] = []
    for relative in unique_strings(candidates):
        path = (root / relative).resolve(strict=False)
        if is_within(path, root) and path.is_dir() and path != root:
            valid.append(path.relative_to(root).as_posix())
    return valid


def build_manifests(root: Path) -> list[str]:
    found = [marker for marker in BUILD_MARKERS if (root / marker).is_file()]
    found.extend(path.name for path in sorted(root.glob("*.sln")))
    return unique_strings(found)


def keywords_for_name(name: str) -> list[str]:
    stopwords = {"app", "core", "lib", "main", "module", "service", "src"}
    words = re.split(r"[-_.\s]+", normalize_text(name))
    return unique_strings(word for word in words if len(word) >= 2 and word not in stopwords)[:8]


def portable_discovery_path(path: Path) -> str:
    workspace_home = os.environ.get("WORKSPACE_HOME")
    if workspace_home:
        home = Path(os.path.expanduser(workspace_home)).resolve(strict=False)
        try:
            relative = path.resolve(strict=False).relative_to(home)
            if str(relative) == ".":
                return "${WORKSPACE_HOME}"
            return "${WORKSPACE_HOME}/" + relative.as_posix()
        except ValueError:
            pass
    return display_path(path).replace("\\", "/")


def unique_id(base: str, used: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in used:
        suffix_text = f"-{suffix}"
        candidate = base[: 63 - len(suffix_text)].rstrip("-._") + suffix_text
        suffix += 1
    used.add(candidate)
    return candidate


def discovered_project(root: Path, project_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    project: dict[str, Any] = {"root": portable_discovery_path(root)}
    if normalize_text(root.name) != project_id:
        project["aliases"] = [root.name]
    keywords = keywords_for_name(root.name)
    if keywords:
        project["keywords"] = keywords

    context: dict[str, list[str]] = {}
    if (root / "AGENTS.md").is_file():
        context["entrypoints"] = ["AGENTS.md"]
    docs = [name for name in ("README.md", "README.en.md") if (root / name).is_file()]
    if docs:
        context["docs"] = docs
    skill_paths: list[str] = []
    for container_name in ("skill", "skills", ".agents/skills"):
        container = root / container_name
        if not container.is_dir():
            continue
        for skill_file in sorted(container.rglob("SKILL.md")):
            if skill_file.is_file() and is_within(skill_file, root):
                skill_paths.append(skill_file.relative_to(root).as_posix())
    skill_paths = unique_strings(skill_paths)
    if skill_paths:
        context["skills"] = skill_paths
    if context:
        project["context"] = context

    version, version_file = detect_version(root)
    if version is not None and version_file is not None:
        project["revision"] = {"version": version, "version_file": version_file}

    module_paths = detect_modules(root)
    if module_paths:
        used_module_ids: set[str] = set()
        modules: dict[str, Any] = {}
        for module_path in sorted(module_paths, key=normalize_text):
            module_name = Path(module_path).name
            module_id = unique_id(slugify(module_name, "module"), used_module_ids)
            module: dict[str, Any] = {"path": module_path}
            if normalize_text(module_name) != module_id:
                module["aliases"] = [module_name]
            module_keywords = keywords_for_name(module_name)
            if module_keywords:
                module["keywords"] = module_keywords
            module_root = root / module_path
            module_context: dict[str, list[str]] = {}
            if (module_root / "AGENTS.md").is_file():
                module_context["entrypoints"] = ["AGENTS.md"]
            module_docs = [name for name in ("README.md", "README.en.md") if (module_root / name).is_file()]
            if module_docs:
                module_context["docs"] = module_docs
            if module_context:
                module["context"] = module_context
            modules[module_id] = module
        project["modules"] = modules

    metadata = {
        "project_id": project_id,
        "root": display_path(root),
        "git": (root / ".git").exists(),
        "branch": safe_git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "build_manifests": build_manifests(root),
        "module_count": len(module_paths),
    }
    return project, metadata


def write_yaml_atomic(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise CliFailure(
            "output_exists",
            "输出文件已存在；只有显式传入 --force 才允许覆盖。",
            details={"path": display_path(path)},
        )
    if path.exists() and not path.is_file():
        raise CliFailure(
            "output_not_file", "输出路径存在但不是文件。", details={"path": display_path(path)}
        )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    except OSError as exc:
        raise CliFailure(
            "output_write_failed",
            f"无法写入候选文件：{exc}",
            details={"path": display_path(path)},
        ) from exc


def discover_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    require_yaml()
    root_values = args.root or [os.getcwd()]
    roots: list[Path] = []
    for value in root_values:
        expanded, missing = expand_env(value)
        if missing:
            raise CliFailure(
                "missing_environment_variable",
                "discover 根目录包含未定义环境变量。",
                details={"value": value, "variables": sorted(set(missing))},
            )
        candidate_root = Path(os.path.expanduser(expanded)).resolve(strict=False)
        if not any(
            os.path.normcase(str(existing)) == os.path.normcase(str(candidate_root))
            for existing in roots
        ):
            roots.append(candidate_root)
    project_roots = discover_project_roots(roots, args.max_depth)
    if not project_roots:
        raise CliFailure(
            "no_projects_discovered",
            "未发现 Git 仓库或受支持的构建项目；请调整 --root 或 --max-depth。",
            details={"roots": [display_path(root) for root in roots], "max_depth": args.max_depth},
        )
    used_project_ids: set[str] = set()
    projects: dict[str, Any] = {}
    discovery: list[dict[str, Any]] = []
    for root in project_roots:
        project_id = unique_id(slugify(root.name), used_project_ids)
        project, metadata = discovered_project(root, project_id)
        projects[project_id] = project
        discovery.append(metadata)
    workspace_name = roots[0].name if len(roots) == 1 else "workspace"
    candidate: dict[str, Any] = {
        "version": VERSION,
        "workspace": {
            "name": workspace_name or "workspace",
            "roots": [portable_discovery_path(root) for root in roots],
        },
        "projects": projects,
    }
    yaml_text = yaml.safe_dump(
        candidate,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=100,
    )
    output_path: Path | None = None
    if args.output:
        expanded, missing = expand_env(args.output)
        if missing:
            raise CliFailure(
                "missing_environment_variable",
                "输出路径包含未定义环境变量。",
                details={"value": args.output, "variables": sorted(set(missing))},
            )
        output_path = Path(os.path.expanduser(expanded)).resolve(strict=False)
        write_yaml_atomic(output_path, yaml_text, args.force)
    return (
        {
            "status": "ok",
            "command": "discover",
            "mode": "written" if output_path is not None else "preview",
            "output_path": display_path(output_path) if output_path is not None else None,
            "candidate": candidate,
            "candidate_yaml": yaml_text,
            "discovery": discovery,
            "summary": {
                "root_count": len(roots),
                "project_count": len(projects),
                "module_count": sum(item["module_count"] for item in discovery),
            },
            "review_required": True,
            "policy": {
                "automatic_manifest_merge": False,
                "automatic_git_checkout": False,
                "database_index": False,
            },
        },
        0,
    )


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        prog="workspace_router.py",
        description="Workspace Context Router：发现、校验并确定性解析可人工审查的 YAML Manifest。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    discover = subparsers.add_parser("discover", help="扫描 Git 仓库和常见构建清单，预览 YAML 候选。")
    discover.add_argument("--root", action="append", help="扫描根目录；可重复，默认当前目录。")
    discover.add_argument("--max-depth", type=int, default=4, help="查找项目根的最大目录深度，默认 4。")
    discover.add_argument("--output", help="显式写入 YAML 候选；省略时只输出 JSON 预览。")
    discover.add_argument("--force", action="store_true", help="允许覆盖已存在的 --output 文件。")
    discover.set_defaults(handler=discover_command)

    validate = subparsers.add_parser("validate", help="校验 Manifest Schema、别名、引用和可选路径。")
    validate.add_argument("--manifest", help="Manifest 路径；省略时按标准优先级自动发现。")
    validate.add_argument("--cwd", help="Manifest 自动发现的起始目录，默认当前目录。")
    validate.add_argument("--check-paths", action="store_true", help="同时检查项目、模块和 Context 路径。")
    validate.set_defaults(handler=validate_command)

    resolve = subparsers.add_parser("resolve", help="按 alias/keyword/Capability 确定性解析查询。")
    resolve.add_argument("query", nargs="?", help="自然语言或项目/模块查询。")
    resolve.add_argument("--query", dest="query_option", help="查询文本；用于避免位置参数转义问题。")
    resolve.add_argument("--manifest", help="Manifest 路径；省略时按标准优先级自动发现。")
    resolve.add_argument("--cwd", help="当前任务目录及 Manifest 自动发现起点，默认当前目录。")
    resolve.add_argument("--min-score", type=int, default=35, help="候选最低分，默认 35。")
    resolve.add_argument("--ambiguity-delta", type=int, default=15, help="与最高分差不超过该值视为歧义，默认 15。")
    resolve.add_argument("--limit", type=int, default=10, help="最多返回的候选数，默认 10。")
    resolve.set_defaults(handler=resolve_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        require_yaml()
        if getattr(args, "max_depth", 0) < 0:
            raise CliFailure("invalid_option", "--max-depth 不能小于 0。", exit_code=2)
        if getattr(args, "min_score", 0) < 0:
            raise CliFailure("invalid_option", "--min-score 不能小于 0。", exit_code=2)
        if getattr(args, "ambiguity_delta", 0) < 0:
            raise CliFailure("invalid_option", "--ambiguity-delta 不能小于 0。", exit_code=2)
        if getattr(args, "limit", 1) <= 0:
            raise CliFailure("invalid_option", "--limit 必须大于 0。", exit_code=2)
        if getattr(args, "force", False) and not getattr(args, "output", None):
            raise CliFailure("invalid_option", "--force 只能与 --output 一起使用。", exit_code=2)
        payload, exit_code = args.handler(args)
        emit_json(payload)
        return exit_code
    except CliFailure as exc:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.details is not None:
            error["details"] = exc.details
        emit_json({"status": "error", "command": getattr(locals().get("args"), "command", None), "error": error})
        return exc.exit_code
    except KeyboardInterrupt:
        emit_json(
            {
                "status": "error",
                "command": getattr(locals().get("args"), "command", None),
                "error": {"code": "interrupted", "message": "操作被中断。"},
            }
        )
        return 130
    except Exception as exc:  # Keep the public output contract JSON-only.
        emit_json(
            {
                "status": "error",
                "command": getattr(locals().get("args"), "command", None),
                "error": {
                    "code": "internal_error",
                    "message": "执行失败；请检查输入并使用最新版本重试。",
                    "details": {"type": type(exc).__name__, "reason": str(exc)},
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
