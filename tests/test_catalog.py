"""Locks the catalog contract and the operator wizard."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "agent-wizardry"
VALIDATE_PATH = SKILL / "scripts" / "validate_catalog.py"
WIZARD_PATH = SKILL / "references" / "wizard.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_catalog = load_module("validate_catalog", VALIDATE_PATH)
wizard = load_module("wizard_runner", WIZARD_PATH)


class ValidateTests(unittest.TestCase):
    def test_shipped_catalogs(self) -> None:
        catalogs = [
            ROOT / "wizard" / "catalog.json",
            ROOT / "examples" / "cli-project" / "wizard" / "catalog.json",
            ROOT / "examples" / "web-project" / "wizard" / "catalog.json",
        ]
        for catalog in catalogs:
            data = json.loads(catalog.read_text(encoding="utf-8"))
            root = catalog.parent.parent
            errors = validate_catalog.validate(data, root, catalog)
            self.assertEqual(errors, [], msg=f"{catalog}: {errors}")

    def test_duplicate_id_and_destructive_confirm(self) -> None:
        root = self.make_project()
        data = self.catalog(
            [
                self.task("wipe", danger="destructive", confirm=False),
                self.task("wipe"),
            ]
        )
        errors = validate_catalog.validate(data, root)
        self.assertTrue(any("duplicate" in error for error in errors))
        self.assertTrue(any("confirm" in error for error in errors))

    def test_web_task_cannot_run(self) -> None:
        root = self.make_project()
        task = self.task("import-doc", kind="app", surface=["web"])
        task["run"] = {"argv": ["echo", "nope"]}
        task["href"] = "/import"
        errors = validate_catalog.validate(self.catalog([task]), root)
        self.assertTrue(any("web tasks never include a run command" in error for error in errors))

    def test_shell_pipeline_is_rejected(self) -> None:
        root = self.make_project()
        task = self.task("pipe")
        task["run"] = {"argv": ["bash", "-lc", "echo hi && echo there"]}
        errors = validate_catalog.validate(self.catalog([task]), root)
        self.assertTrue(any("script file" in error for error in errors))

    def test_select_requires_real_choices(self) -> None:
        root = self.make_project()
        task = self.task("choose")
        task["inputs"] = [
            {
                "name": "--env",
                "prompt": "Environment",
                "type": "select",
                "choices": [],
            }
        ]
        errors = validate_catalog.validate(self.catalog([task]), root)
        self.assertTrue(any("choices" in error for error in errors))

    def test_missing_source(self) -> None:
        root = self.make_project()
        task = self.task("missing")
        task["source"] = "no-such-file.sh"
        errors = validate_catalog.validate(self.catalog([task]), root)
        self.assertTrue(any("does not exist" in error for error in errors))

    def test_write_web_subset(self) -> None:
        catalog = ROOT / "examples" / "web-project" / "wizard" / "catalog.json"
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "catalog.web.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_PATH),
                    str(catalog),
                    "--write-web",
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.is_file())
            checked = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_PATH),
                    str(catalog),
                    "--check-web",
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            published = json.loads(target.read_text(encoding="utf-8"))
            self.assertNotIn("run", json.dumps(published))
            self.assertEqual(published["tasks"][0]["id"], "import-first-document")
            self.assertEqual(published["placements"][0]["id"], "empty-workspace")
            self.assertEqual(published["placements"][0]["tasks"], ["import-first-document"])

    def test_placements_only_name_web_tasks(self) -> None:
        root = self.make_project()
        web = self.task("import-doc", kind="app", surface=["web"])
        other = self.task("share-doc", kind="app", surface=["web"])
        cli = self.task("deploy")
        data = self.catalog([web, other, cli])
        data["placements"] = [
            {
                "id": "empty",
                "title": "Empty workspace",
                "where": "Empty workspace",
                "context": "Nothing has been imported.",
                "tasks": ["import-doc"],
            },
            {
                "id": "empty",
                "title": "Also empty",
                "where": "Header",
                "context": "The person is in the header.",
                "tasks": ["deploy", "import-doc"],
            },
        ]
        errors = validate_catalog.validate(data, root)
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("deploy" in error and "web" in error for error in errors))
        self.assertTrue(any("share-doc" in error for error in errors))

    def test_valid_placement_reaches_the_web_subset(self) -> None:
        root = self.make_project()
        web = self.task("import-doc", kind="app", surface=["web"])
        data = self.catalog([web])
        data["placements"] = [
            {
                "id": "empty",
                "title": "Empty workspace",
                "where": "Empty workspace",
                "context": "Nothing has been imported.",
                "tasks": ["import-doc"],
            }
        ]
        self.assertEqual(validate_catalog.validate(data, root), [])
        published = validate_catalog.web_view(data)
        self.assertEqual(published["placements"][0]["id"], "empty")
        self.assertEqual(published["tasks"][0]["id"], "import-doc")
        self.assertNotIn("run", json.dumps(published))

    def test_operator_catalog_refuses_a_web_file(self) -> None:
        catalog = ROOT / "examples" / "cli-project" / "wizard" / "catalog.json"
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "catalog.web.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_PATH),
                    str(catalog),
                    "--write-web",
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No web tasks", result.stderr)
            self.assertFalse(target.exists())

    def make_project(self) -> Path:
        raw = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", raw], check=False))
        root = Path(raw)
        (root / "README.md").write_text("sample\n", encoding="utf-8")
        return root

    def task(
        self,
        task_id: str,
        danger: str = "safe",
        kind: str = "script",
        surface: list[str] | None = None,
        confirm: bool | None = None,
    ) -> dict:
        task = {
            "id": task_id,
            "title": task_id,
            "summary": "Does the sample thing.",
            "kind": kind,
            "source": "README.md",
            "danger": danger,
            "surface": surface or ["cli"],
        }
        if confirm is not None:
            task["confirm"] = confirm
        elif danger in {"writes", "destructive"}:
            task["confirm"] = True
        if kind in {"script", "npm", "make", "just", "task", "workflow", "compose"}:
            task["run"] = {"argv": ["python", "-c", "print('ok')"], "cwd": "."}
        else:
            task["steps"] = ["Read the sample."]
        return task

    def catalog(self, tasks: list[dict]) -> dict:
        return {
            "version": 1,
            "project": {"name": "Sample", "summary": "A sample project."},
            "tasks": tasks,
        }


class WizardTests(unittest.TestCase):
    def test_root_wizard_is_the_template(self) -> None:
        self.assertEqual((ROOT / "wizard.py").resolve(), WIZARD_PATH.resolve())

    def test_assemble_argv(self) -> None:
        task = {
            "run": {"argv": ["sh", "sample-script.sh"]},
            "inputs": [
                {"id": "env", "name": "--env", "type": "select"},
                {"id": "dry-run", "name": "--dry-run", "type": "confirm"},
                {"id": "note", "name": "note", "positional": True, "type": "string"},
            ],
        }
        argv = wizard.assemble_argv(
            task, {"env": "staging", "dry-run": True, "note": "hello"}
        )
        self.assertEqual(
            argv, ["sh", "sample-script.sh", "--env", "staging", "--dry-run", "hello"]
        )
        skipped = wizard.assemble_argv(
            task, {"env": "staging", "dry-run": False, "note": ""}
        )
        self.assertEqual(skipped, ["sh", "sample-script.sh", "--env", "staging"])

    def test_menu_shows_what_a_task_does(self) -> None:
        task = {
            "id": "open",
            "title": "Start the local server",
            "summary": "Starts the page on this computer. This is the way to get going.",
            "kind": "script",
            "danger": "safe",
            "surface": ["cli"],
            "run": {"argv": ["python3", "webapp.py"], "cwd": "."},
        }
        frame = wizard.menu_frame(
            "Sample",
            "A sample project.",
            "The lighter text says what each choice does.",
            wizard.tasks_as_items([task]),
            0,
            80,
            24,
            False,
        )
        self.assertIn("Start the local server", frame)
        self.assertIn("Starts the page on this computer.", frame)
        self.assertIn("safe ·", frame)
        self.assertIn("↑↓ move", frame)

    def test_list_and_briefing(self) -> None:
        listed = self.run_wizard("--list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("run-tests\tsafe\tcli\tRun the catalog tests", listed.stdout)
        self.assertIn("install-skill", listed.stdout)
        briefing = self.run_wizard("--briefing")
        self.assertEqual(briefing.returncode, 0, briefing.stderr)
        self.assertIn("Agent Wizardry", briefing.stdout)
        self.assertIn("Agent Skills format", briefing.stdout)

    def test_finds_repo_catalog(self) -> None:
        previous = os.environ.pop("WIZARD_CATALOG", None)
        try:
            found = wizard.find_catalog(None)
        finally:
            if previous is not None:
                os.environ["WIZARD_CATALOG"] = previous
        self.assertEqual(found, (ROOT / "wizard" / "catalog.json").resolve())

    def test_destructive_task_does_not_run_until_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            wizard_dir = root / "wizard"
            wizard_dir.mkdir()
            marker = root / "ran"
            code = (
                "from pathlib import Path; "
                f"Path(r'{marker}').write_text('x', encoding='utf-8')"
            )
            catalog = {
                "version": 1,
                "project": {"name": "T", "summary": "T"},
                "tasks": [
                    {
                        "id": "boom",
                        "title": "Boom",
                        "summary": "Creates a marker file.",
                        "kind": "script",
                        "source": "ignored",
                        "danger": "destructive",
                        "confirm": True,
                        "surface": ["cli"],
                        "run": {
                            "argv": [sys.executable, "-c", code],
                            "cwd": ".",
                        },
                    }
                ],
            }
            catalog_path = wizard_dir / "catalog.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            refused = self.run_wizard(
                "--catalog",
                str(catalog_path),
                "--task",
                "boom",
                "--yes",
                cwd=root,
            )
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("Destructive task", refused.stderr)
            self.assertFalse(marker.exists())
            allowed = self.run_wizard(
                "--catalog",
                str(catalog_path),
                "--task",
                "boom",
                "--yes",
                "--confirm-task",
                "boom",
                cwd=root,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "x")

    def test_manual_task_prints_steps(self) -> None:
        result = self.run_wizard("--task", "install-skill", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("~/.claude/skills", result.stdout)
        self.assertIn("~/.copilot/skills", result.stdout)
        self.assertIn("~/.cursor/skills", result.stdout)
        self.assertIn("~/.grok/skills", result.stdout)
        self.assertIn("Nothing was run.", result.stdout)

    def test_safe_task_needs_yes_when_not_a_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            marker = root / "ran"
            catalog_path = self.write_catalog(
                root,
                danger="safe",
                marker=marker,
            )
            refused = self.run_wizard(
                "--catalog", str(catalog_path), "--task", "mark", cwd=root
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("Pass --yes", refused.stderr)
            self.assertFalse(marker.exists())
            allowed = self.run_wizard(
                "--catalog",
                str(catalog_path),
                "--task",
                "mark",
                "--yes",
                cwd=root,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertTrue(marker.exists())

    def write_catalog(self, root: Path, danger: str, marker: Path) -> Path:
        wizard_dir = root / "wizard"
        wizard_dir.mkdir()
        code = (
            "from pathlib import Path; "
            f"Path(r'{marker}').write_text('x', encoding='utf-8')"
        )
        catalog = {
            "version": 1,
            "project": {"name": "T", "summary": "T"},
            "tasks": [
                {
                    "id": "mark",
                    "title": "Mark",
                    "summary": "Creates a marker file.",
                    "kind": "script",
                    "source": "ignored",
                    "danger": danger,
                    "confirm": danger != "safe",
                    "surface": ["cli"],
                    "run": {"argv": [sys.executable, "-c", code], "cwd": "."},
                }
            ],
        }
        path = wizard_dir / "catalog.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        return path

    def run_wizard(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "wizard.py"), *args],
            cwd=cwd or ROOT,
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=20,
        )


if __name__ == "__main__":
    unittest.main()
