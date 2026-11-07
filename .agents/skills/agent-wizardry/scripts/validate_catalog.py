#!/usr/bin/env python3
"""Validate an Agent Wizardry catalog.json.

This script is the contract. The JSON schema mirrors it for editors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
KINDS = {
    "script",
    "npm",
    "make",
    "just",
    "task",
    "workflow",
    "compose",
    "manual",
    "app",
}
EXECUTABLE = {"script", "npm", "make", "just", "task", "workflow", "compose"}
DANGERS = {"safe", "writes", "destructive"}
SURFACES = {"cli", "web"}
INPUT_TYPES = {"string", "select", "confirm", "path", "multiline"}
TOP_KEYS = {"$schema", "version", "project", "briefing", "tasks"}
PROJECT_KEYS = {"name", "summary", "docs"}
BRIEFING_KEYS = {"title", "body"}
TASK_KEYS = {
    "id",
    "title",
    "summary",
    "details",
    "kind",
    "source",
    "danger",
    "confirm",
    "prerequisites",
    "inputs",
    "surface",
    "run",
    "steps",
    "href",
}
RUN_KEYS = {"argv", "cwd"}
INPUT_KEYS = {
    "id",
    "name",
    "prompt",
    "help",
    "type",
    "required",
    "default",
    "choices",
    "positional",
}
CHOICE_KEYS = {"value", "label", "help"}
SHELLS = {"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"}
SHELL_FLAGS = {"-c", "-lc", "/c"}


def validate(data: object, root: Path, catalog_path: Path | None = None) -> list[str]:
    errors: list[str] = []

    def add(path: str, message: str) -> None:
        errors.append(f"{path}: {message}")

    if not isinstance(data, dict):
        return ["catalog: must be a JSON object"]
    unknown = set(data) - TOP_KEYS
    if unknown:
        add("catalog", f"unknown keys: {', '.join(sorted(unknown))}")
    version = data.get("version")
    if type(version) is not int or version != 1:
        add("version", "must be the integer 1")
    check_schema(data.get("$schema"), catalog_path, add)
    project = data.get("project")
    if not isinstance(project, dict):
        add("project", "must be an object")
    else:
        check_project(project, root, add)
    if "briefing" in data:
        check_briefing(data["briefing"], add)
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        add("tasks", "must be a list")
    elif len(tasks) == 0:
        add("tasks", "add at least one real task, or stop without inventing one")
    else:
        check_tasks(tasks, root, add)
    return errors


def check_schema(schema: object, catalog_path: Path | None, add) -> None:
    if schema is None:
        return
    if not isinstance(schema, str) or not schema.strip():
        add("$schema", "must be a path or URL")
        return
    if schema.startswith(("http://", "https://")) or catalog_path is None:
        return
    resolved = (catalog_path.parent / schema).resolve()
    if not resolved.is_file():
        add("$schema", f"file does not exist: {schema}")


def check_project(project: dict, root: Path, add) -> None:
    unknown = set(project) - PROJECT_KEYS
    if unknown:
        add("project", f"unknown keys: {', '.join(sorted(unknown))}")
    require_text(project.get("name"), "project.name", add)
    require_text(project.get("summary"), "project.summary", add)
    docs = project.get("docs")
    if docs is None:
        return
    if not isinstance(docs, list):
        add("project.docs", "must be a list of paths")
        return
    for index, doc in enumerate(docs):
        check_repo_file(doc, root, f"project.docs[{index}]", add)


def check_briefing(briefing: object, add) -> None:
    if not isinstance(briefing, list):
        add("briefing", "must be a list")
        return
    for index, section in enumerate(briefing):
        path = f"briefing[{index}]"
        if not isinstance(section, dict):
            add(path, "must be an object")
            continue
        unknown = set(section) - BRIEFING_KEYS
        if unknown:
            add(path, f"unknown keys: {', '.join(sorted(unknown))}")
        require_text(section.get("title"), f"{path}.title", add)
        require_text(section.get("body"), f"{path}.body", add)


def check_tasks(tasks: list, root: Path, add) -> None:
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        path = f"tasks[{index}]"
        if not isinstance(task, dict):
            add(path, "must be an object")
            continue
        unknown = set(task) - TASK_KEYS
        if unknown:
            add(path, f"unknown keys: {', '.join(sorted(unknown))}")
        task_id = task.get("id")
        if not isinstance(task_id, str) or not ID_RE.fullmatch(task_id):
            add(f"{path}.id", "must be kebab-case starting with a letter")
        elif task_id in seen:
            add(f"{path}.id", f"duplicate id {task_id!r}")
        else:
            seen.add(task_id)
        require_text(task.get("title"), f"{path}.title", add)
        require_text(task.get("summary"), f"{path}.summary", add)
        if "details" in task and not isinstance(task["details"], str):
            add(f"{path}.details", "must be a string")
        kind = task.get("kind")
        if kind not in KINDS:
            add(f"{path}.kind", f"must be one of {', '.join(sorted(KINDS))}")
        check_repo_file(task.get("source"), root, f"{path}.source", add)
        danger = task.get("danger")
        if danger not in DANGERS:
            add(f"{path}.danger", "must be safe, writes, or destructive")
        confirm = task.get("confirm", False)
        if "confirm" in task and type(confirm) is not bool:
            add(f"{path}.confirm", "must be a boolean")
        elif danger in {"writes", "destructive"} and confirm is not True:
            add(f"{path}.confirm", f"{danger} tasks set confirm to true")
        surface = task.get("surface")
        if (
            not isinstance(surface, list)
            or not surface
            or any(item not in SURFACES for item in surface)
            or len(surface) != len(set(surface))
        ):
            add(f"{path}.surface", 'must be a unique list of "cli" and "web"')
            surface = []
        check_string_list(task.get("prerequisites"), f"{path}.prerequisites", add)
        check_string_list(task.get("steps"), f"{path}.steps", add, allow_missing=True)
        if "href" in task:
            check_href(task["href"], f"{path}.href", add)
        if "inputs" in task:
            check_inputs(
                task["inputs"],
                f"{path}.inputs",
                add,
                enforce_flags=kind in EXECUTABLE or "run" in task,
            )
        check_shape(task, path, kind, surface, add)


def check_shape(task: dict, path: str, kind: object, surface: list, add) -> None:
    has_run = "run" in task
    has_guide = bool(task.get("steps")) or bool(task.get("href"))
    if kind in EXECUTABLE:
        if surface != ["cli"]:
            add(f"{path}.surface", "operator commands stay on the cli surface")
        if not has_run:
            add(f"{path}.run", "executable tasks include run.argv")
        else:
            check_run(task["run"], f"{path}.run", add)
    elif kind == "manual":
        if has_run:
            add(f"{path}.run", "manual tasks describe steps and do not run a command")
        if not has_guide:
            add(path, "manual tasks include steps or href")
    elif kind == "app":
        if "web" not in surface:
            add(f"{path}.surface", "app tasks are product actions and include web")
        if has_run:
            add(f"{path}.run", "app tasks do not run a shell command")
        if not has_guide:
            add(path, "app tasks include steps or href")
    if "web" in surface and has_run:
        add(f"{path}.run", "web tasks never include a run command")


def check_run(run: object, path: str, add) -> None:
    if not isinstance(run, dict):
        add(path, "must be an object")
        return
    unknown = set(run) - RUN_KEYS
    if unknown:
        add(path, f"unknown keys: {', '.join(sorted(unknown))}")
    argv = run.get("argv")
    if not isinstance(argv, list) or not argv or any(type(part) is not str or not part for part in argv):
        add(f"{path}.argv", "must be a list of non-empty strings")
        return
    program = Path(argv[0]).name
    if program in SHELLS and any(part in SHELL_FLAGS for part in argv[1:]):
        add(
            f"{path}.argv",
            "put the pipeline in a script file and catalog that file",
        )
    if "cwd" not in run:
        return
    cwd = run["cwd"]
    if not isinstance(cwd, str) or not cwd or Path(cwd).is_absolute() or ".." in Path(cwd).parts:
        add(f"{path}.cwd", "must be a relative path inside the project")


def check_inputs(inputs: object, path: str, add, enforce_flags: bool) -> None:
    if not isinstance(inputs, list):
        add(path, "must be a list")
        return
    seen: set[str] = set()
    for index, spec in enumerate(inputs):
        item = f"{path}[{index}]"
        if not isinstance(spec, dict):
            add(item, "must be an object")
            continue
        unknown = set(spec) - INPUT_KEYS
        if unknown:
            add(item, f"unknown keys: {', '.join(sorted(unknown))}")
        name = spec.get("name")
        if not isinstance(name, str) or not name.strip():
            add(f"{item}.name", "must be a non-empty string")
            name = ""
        require_text(spec.get("prompt"), f"{item}.prompt", add)
        if "id" in spec and (not isinstance(spec["id"], str) or not ID_RE.fullmatch(spec["id"])):
            add(f"{item}.id", "must be kebab-case starting with a letter")
        key = spec["id"] if isinstance(spec.get("id"), str) else name
        if key in seen:
            add(item, f"duplicate input id {key!r}")
        elif key:
            seen.add(key)
        kind = spec.get("type", "string")
        if kind not in INPUT_TYPES:
            add(f"{item}.type", f"must be one of {', '.join(sorted(INPUT_TYPES))}")
        positional = spec.get("positional", False)
        if "positional" in spec and type(positional) is not bool:
            add(f"{item}.positional", "must be a boolean")
        if "required" in spec and type(spec["required"]) is not bool:
            add(f"{item}.required", "must be a boolean")
        if kind == "confirm" and positional:
            add(f"{item}.positional", "confirm inputs are flags")
        if (
            enforce_flags
            and not positional
            and isinstance(name, str)
            and name
            and not name.startswith("-")
        ):
            add(f"{item}.name", "flags start with -; set positional for bare arguments")
        if "help" in spec and not isinstance(spec["help"], str):
            add(f"{item}.help", "must be a string")
        check_default(spec, kind, item, add)
        if kind == "select":
            check_choices(spec.get("choices"), spec.get("default"), item, add)
        elif "choices" in spec:
            add(f"{item}.choices", "only select inputs have choices")


def check_default(spec: dict, kind: object, item: str, add) -> None:
    if "default" not in spec:
        return
    default = spec["default"]
    if kind == "confirm":
        if type(default) is not bool:
            add(f"{item}.default", "confirm defaults are booleans")
        return
    if type(default) is not str or not default:
        add(f"{item}.default", "must be a non-empty string")


def check_choices(choices: object, default: object, item: str, add) -> None:
    if not isinstance(choices, list) or not choices:
        add(f"{item}.choices", "select inputs list at least one choice")
        return
    values: set[str] = set()
    for index, choice in enumerate(choices):
        path = f"{item}.choices[{index}]"
        if not isinstance(choice, dict):
            add(path, "must be an object")
            continue
        unknown = set(choice) - CHOICE_KEYS
        if unknown:
            add(path, f"unknown keys: {', '.join(sorted(unknown))}")
        value = choice.get("value")
        if type(value) is not str or not value:
            add(f"{path}.value", "must be a non-empty string")
        elif value in values:
            add(f"{path}.value", f"duplicate value {value!r}")
        else:
            values.add(value)
        require_text(choice.get("label"), f"{path}.label", add)
        if "help" in choice and not isinstance(choice["help"], str):
            add(f"{path}.help", "must be a string")
    if type(default) is str and default not in values:
        add(f"{item}.default", "must be one of the choice values")


def check_href(href: object, path: str, add) -> None:
    if type(href) is not str or not href:
        add(path, "must be an in-app path or http(s) URL")
        return
    if href.startswith("/") or href.startswith("https://") or href.startswith("http://"):
        return
    add(path, "must start with /, http://, or https://")


def check_string_list(value: object, path: str, add, allow_missing: bool = False) -> None:
    if value is None and allow_missing:
        return
    if value is None:
        return
    if not isinstance(value, list) or any(type(item) is not str or not item.strip() for item in value):
        add(path, "must be a list of non-empty strings")


def check_repo_file(source: object, root: Path, path: str, add) -> None:
    if type(source) is not str or not source.strip():
        add(path, "must be a file in the repo")
        return
    file_part = source.split("#", 1)[0]
    if "://" in file_part:
        add(path, "cite a file in the repo")
        return
    relative = Path(file_part)
    if relative.is_absolute() or ".." in relative.parts or not file_part:
        add(path, "must be a relative path inside the project")
        return
    if not (root / relative).is_file():
        add(path, f"file does not exist: {file_part}")


def require_text(value: object, path: str, add) -> None:
    if type(value) is not str or not value.strip():
        add(path, "must be a non-empty string")


def web_view(data: dict) -> dict:
    tasks = [
        task
        for task in data.get("tasks", [])
        if isinstance(task, dict) and "web" in (task.get("surface") or [])
    ]
    return {
        "version": data.get("version"),
        "project": data.get("project"),
        "briefing": data.get("briefing") or [],
        "tasks": tasks,
    }


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON ({exc})") from exc


def default_root(catalog: Path) -> Path:
    if catalog.parent.name == "wizard":
        return catalog.parent.parent
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an Agent Wizardry catalog.json")
    parser.add_argument("catalog", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        help="Project root for source paths. Defaults to the catalog's project.",
    )
    parser.add_argument(
        "--write-web",
        type=Path,
        help="Write the web subset to this path",
    )
    parser.add_argument(
        "--check-web",
        type=Path,
        help="Fail when this file is not the web subset of the catalog",
    )
    args = parser.parse_args(argv)
    catalog_path = args.catalog.resolve()
    data = load_json(catalog_path)
    root = (args.root or default_root(catalog_path)).resolve()
    errors = validate(data, root, catalog_path)
    if args.check_web and not errors and isinstance(data, dict):
        other_path = args.check_web
        if not other_path.is_file():
            errors.append(f"web catalog not found: {other_path}")
        elif load_json(other_path) != web_view(data):
            errors.append("web catalog does not match the web tasks in the source catalog")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.write_web:
        if not isinstance(data, dict):
            print("catalog: must be a JSON object", file=sys.stderr)
            return 1
        view = web_view(data)
        if not view["tasks"]:
            print("No web tasks. Do not publish a web catalog.", file=sys.stderr)
            return 1
        args.write_web.parent.mkdir(parents=True, exist_ok=True)
        args.write_web.write_text(json.dumps(view, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(view['tasks'])} web task(s) to {args.write_web}")
    print(f"{catalog_path}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
