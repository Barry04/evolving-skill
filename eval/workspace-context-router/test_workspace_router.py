import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "skill" / "workspace-context-router" / "scripts" / "workspace_router.py"


class WorkspaceRouterCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.order = self.workspace / "order-service"
        self.audit = self.workspace / "audit-service"

        for path in (
            self.order / "modules" / "payment",
            self.order / "modules" / "shared",
            self.audit / "modules" / "event-consumer",
            self.audit / "modules" / "shared",
        ):
            path.mkdir(parents=True)

        (self.order / "AGENTS.md").write_text("# Order\n", encoding="utf-8")
        (self.order / "modules" / "payment" / "AGENTS.md").write_text(
            "# Payment\n", encoding="utf-8"
        )
        (self.audit / "AGENTS.md").write_text("# Audit\n", encoding="utf-8")
        (self.order / "package.json").write_text(
            json.dumps({"name": "order-service", "version": "2.4.0"}),
            encoding="utf-8",
        )
        (self.workspace / "package.json").write_text(
            json.dumps({"name": "workspace-tools", "private": True}), encoding="utf-8"
        )
        skill_entry = self.order / "skill" / "demo" / "SKILL.md"
        skill_entry.parent.mkdir(parents=True)
        skill_entry.write_text("---\nname: demo\ndescription: test\n---\n", encoding="utf-8")

        self._init_git(self.order, "feature/refund-audit")
        self._init_git(self.audit, "main")

        manifest = {
            "version": 1,
            "workspace": {"name": "test"},
            "projects": {
                "order-service": {
                    "root": self.order.as_posix(),
                    "aliases": ["订单"],
                    "revision": {
                        "branch": "release/2026.07",
                        "version": "2.4.0",
                        "version_file": "package.json",
                    },
                    "context": {"entrypoints": ["AGENTS.md"]},
                    "modules": {
                        "payment": {
                            "path": "modules/payment",
                            "aliases": ["支付"],
                            "context": {"entrypoints": ["AGENTS.md"]},
                        },
                        "shared": {"path": "modules/shared", "aliases": ["共享"]},
                    },
                },
                "audit-service": {
                    "root": self.audit.as_posix(),
                    "aliases": ["审计"],
                    "context": {"entrypoints": ["AGENTS.md"]},
                    "modules": {
                        "event-consumer": {
                            "path": "modules/event-consumer",
                            "aliases": ["审计消费"],
                        },
                        "shared": {"path": "modules/shared", "aliases": ["共享"]},
                    },
                },
            },
            "capabilities": {
                "refund": {
                    "aliases": ["退款"],
                    "targets": [
                        {"ref": "order-service/payment", "role": "owner"},
                        {"ref": "audit-service/event-consumer", "role": "participant"},
                    ],
                }
            },
        }
        self.manifest = self.workspace / ".agent-workspace" / "workspace.yaml"
        self.manifest.parent.mkdir()
        self.manifest.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_git(self, root: Path, branch: str):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "router@test"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Router Test"], check=True)
        (root / ".router-test").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", ".router-test"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "-B", branch], check=True)

    def _run(self, *args: str, cwd: Path | None = None):
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(cwd or self.workspace),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def test_resolves_module_and_reports_revision_mismatch(self):
        result, payload = self._run(
            "resolve", "--manifest", str(self.manifest), "--query", "订单支付"
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("resolved", payload["resolution"])
        self.assertEqual("order-service/payment", payload["selection"]["ref"])
        self.assertEqual("mismatch", payload["revision"]["status"]["branch"])
        self.assertEqual("confirm_before_changes", payload["revision"]["action"])
        self.assertFalse(payload["policy"]["automatic_git_checkout"])

    def test_capability_returns_candidates_not_mandatory_changes(self):
        result, payload = self._run(
            "resolve", "--manifest", str(self.manifest), "--query", "退款"
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("capability", payload["selection"]["kind"])
        self.assertEqual(2, len(payload["impact_candidates"]))
        self.assertTrue(
            all(item["impact"] == "candidate_only" for item in payload["impact_candidates"])
        )
        self.assertTrue(payload["policy"]["impact_candidates_require_code_verification"])

    def test_same_module_alias_is_ambiguous_without_project_context(self):
        result, payload = self._run(
            "resolve", "--manifest", str(self.manifest), "--query", "共享"
        )
        self.assertEqual(3, result.returncode)
        self.assertEqual("ambiguous", payload["resolution"])
        refs = {payload["candidates"][0]["ref"], payload["ambiguous_with"][0]["ref"]}
        self.assertEqual({"order-service/shared", "audit-service/shared"}, refs)

    def test_keyword_only_match_requires_confirmation(self):
        data = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        data["projects"]["order-service"]["keywords"] = ["孤立关键词"]
        manifest = self.workspace / "keyword-only.yaml"
        manifest.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        result, payload = self._run(
            "resolve", "--manifest", str(manifest), "--query", "孤立关键词"
        )
        self.assertEqual(3, result.returncode)
        self.assertEqual("needs_confirmation", payload["resolution"])
        self.assertIsNone(payload["selection"])
        self.assertEqual("order-service", payload["confirmation_candidate"]["ref"])

    def test_resolve_rejects_unresolved_project_root(self):
        data = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        data["projects"]["order-service"]["root"] = "${ROUTER_TEST_MISSING_ROOT}/order"
        manifest = self.workspace / "missing-root.yaml"
        manifest.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        result, payload = self._run(
            "resolve", "--manifest", str(manifest), "--query", "订单"
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual("invalid_target", payload["resolution"])
        self.assertEqual("target_path_invalid", payload["error"]["code"])

    def test_manifest_auto_discovery_from_nested_directory(self):
        result, payload = self._run(
            "resolve", "--query", "订单支付", cwd=self.order / "modules" / "payment"
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("ancestor", payload["manifest_source"])
        self.assertEqual(str(self.manifest.resolve()), payload["manifest_path"])

    def test_validate_rejects_parent_traversal(self):
        data = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        data["projects"]["order-service"]["modules"]["payment"]["path"] = "../outside"
        unsafe = self.workspace / "unsafe.yaml"
        unsafe.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        result, payload = self._run("validate", "--manifest", str(unsafe))
        self.assertEqual(1, result.returncode)
        self.assertFalse(payload["valid"])
        self.assertIn("unsafe_relative_path", {item["code"] for item in payload["errors"]})

    def test_validate_reports_non_string_role(self):
        data = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        data["capabilities"]["refund"]["targets"][0]["role"] = ["owner"]
        invalid = self.workspace / "invalid-role.yaml"
        invalid.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        result, payload = self._run("validate", "--manifest", str(invalid))
        self.assertEqual(1, result.returncode)
        self.assertEqual("invalid", payload["status"])
        self.assertIn("invalid_role", {item["code"] for item in payload["errors"]})

    def test_validate_requires_version_file_to_be_a_file(self):
        data = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))
        data["projects"]["order-service"]["revision"]["version_file"] = "."
        invalid = self.workspace / "version-directory.yaml"
        invalid.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        result, payload = self._run(
            "validate", "--manifest", str(invalid), "--check-paths"
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("path_not_found", {item["code"] for item in payload["errors"]})

    def test_discover_is_preview_only_by_default(self):
        output = self.workspace / "discovered.yaml"
        result, payload = self._run("discover", "--root", str(self.workspace), "--max-depth", "2")
        self.assertEqual(0, result.returncode)
        self.assertEqual("preview", payload["mode"])
        self.assertTrue(payload["review_required"])
        self.assertFalse(output.exists())
        self.assertFalse(payload["policy"]["automatic_manifest_merge"])
        self.assertEqual(
            {"audit-service", "order-service"}, set(payload["candidate"]["projects"])
        )
        self.assertEqual(
            ["skill/demo/SKILL.md"],
            payload["candidate"]["projects"]["order-service"]["context"]["skills"],
        )


if __name__ == "__main__":
    unittest.main()
