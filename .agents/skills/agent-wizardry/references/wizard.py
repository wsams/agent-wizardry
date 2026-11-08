#!/usr/bin/env python3
"""Reference operator wizard for a Python project.

This is one implementation of the Agent Wizardry operator behavior. An agent
copies it into a project that is already Python. For any other language, the
agent reimplements this behavior and keeps the task list in wizard/catalog.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

RUNNER_VERSION = 1

KIND_LABEL = {
    "script": "Script",
    "npm": "npm script",
    "make": "Make target",
    "just": "Just recipe",
    "task": "Task runner",
    "workflow": "GitHub Actions workflow",
    "compose": "Compose service",
    "manual": "Manual steps",
    "app": "In the app",
}

DANGER_COLOR = {"safe": "32", "writes": "33", "destructive": "31"}
SHELLS = {"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"}
SHELL_FLAGS = {"-c", "-lc", "/c"}
GUIDED = {"manual", "app"}


def questionary():
    try:
        import questionary as module
    except ImportError:
        return None
    return module


def paint(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def find_catalog(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SystemExit(f"Catalog not found: {path}")
        return path.resolve()
    env = os.environ.get("WIZARD_CATALOG")
    if env:
        path = Path(env)
        if not path.is_file():
            raise SystemExit(f"WIZARD_CATALOG not found: {path}")
        return path.resolve()
    start = Path(__file__).resolve().parent
    for directory in (start, *start.parents):
        candidate = directory / "wizard" / "catalog.json"
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "wizard/catalog.json not found. Run this from a project that has a wizard, "
        "or pass --catalog."
    )


def load_catalog(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: catalog must be a JSON object")
    version = data.get("version")
    if type(version) is not int or version != 1:
        raise SystemExit(f"{path}: unsupported catalog version {version!r}")
    if not isinstance(data.get("tasks"), list):
        raise SystemExit(f"{path}: tasks must be a list")
    return data


def project_root(catalog_path: Path) -> Path:
    if catalog_path.parent.name == "wizard":
        return catalog_path.parent.parent
    return catalog_path.parent


def task_map(catalog: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for task in catalog["tasks"]:
        if isinstance(task, dict) and isinstance(task.get("id"), str):
            found[task["id"]] = task
    return found


def input_id(spec: dict) -> str:
    return str(spec.get("id") or spec["name"])


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def choice_label(choice: dict) -> str:
    help_text = choice.get("help")
    if help_text:
        return f"{choice['label']} ({help_text})"
    return str(choice["label"])


def prompt_select(message: str, choices: list[dict]) -> str:
    module = questionary()
    if module is not None:
        picked = module.select(
            message,
            choices=[
                module.Choice(title=choice["label"], value=choice["value"])
                for choice in choices
            ],
        ).ask()
        if picked is None:
            raise KeyboardInterrupt
        return str(picked)
    print(f"\n{message}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}. {choice['label']}")
    while True:
        raw = input("Choose a number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return str(choices[int(raw) - 1]["value"])
        print(f"Enter a number from 1 to {len(choices)}.")


def prompt_confirm(message: str, default: bool) -> bool:
    module = questionary()
    if module is not None:
        picked = module.confirm(message, default=default).ask()
        if picked is None:
            raise KeyboardInterrupt
        return bool(picked)
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{message} [{hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Answer y or n.")


def prompt_text(message: str, default: str | None) -> str:
    module = questionary()
    if module is not None:
        picked = module.text(message, default="" if default is None else default).ask()
        if picked is None:
            raise KeyboardInterrupt
        return str(picked)
    suffix = f" [{default}]" if default not in (None, "") else ""
    raw = input(f"{message}{suffix}: ")
    if raw == "" and default is not None:
        return default
    return raw


def parse_sets(pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--set must look like id=value, got {pair!r}")
        key, value = pair.split("=", 1)
        if not key:
            raise SystemExit(f"--set must look like id=value, got {pair!r}")
        parsed[key] = value
    return parsed


def parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise SystemExit(f"Expected true or false, got {raw!r}")


def collect_inputs(task: dict, provided: dict[str, str], ask: bool) -> dict[str, object]:
    answers: dict[str, object] = {}
    for spec in task.get("inputs") or []:
        key = input_id(spec)
        prompt = str(spec.get("prompt") or key)
        kind = spec.get("type") or "string"
        required = bool(spec.get("required"))
        if ask and spec.get("help"):
            print(spec["help"])
        if key in provided:
            raw = provided[key]
            if kind == "confirm":
                answers[key] = parse_bool(raw)
            elif kind == "select":
                allowed = {choice["value"] for choice in spec.get("choices") or []}
                if raw not in allowed:
                    names = ", ".join(sorted(str(item) for item in allowed))
                    raise SystemExit(f"{key}: {raw!r} is not one of {names}")
                answers[key] = raw
            else:
                answers[key] = raw
            continue
        if kind == "confirm":
            default = bool(spec.get("default", False))
            answers[key] = prompt_confirm(prompt, default) if ask else default
            continue
        default = None if "default" not in spec else str(spec["default"])
        if ask and kind == "select":
            choices = [
                {"value": choice["value"], "label": choice_label(choice)}
                for choice in spec.get("choices") or []
            ]
            answers[key] = prompt_select(prompt, choices)
            continue
        if ask:
            while True:
                raw = prompt_text(prompt, default)
                if raw == "" and required and default in (None, ""):
                    print("This one is required.")
                    continue
                answers[key] = raw
                break
            continue
        if default not in (None, ""):
            if kind == "select":
                allowed = {choice["value"] for choice in spec.get("choices") or []}
                if default not in allowed:
                    raise SystemExit(f"{key}: default {default!r} is not a listed choice")
            answers[key] = default
            continue
        if required:
            raise SystemExit(
                f"Missing input {key}. Pass --set {key}=VALUE "
                "(or run without --task in a terminal to be asked)."
            )
        answers[key] = ""
    return answers


def assemble_argv(task: dict, answers: dict[str, object]) -> list[str]:
    argv = [str(part) for part in task["run"]["argv"]]
    for spec in task.get("inputs") or []:
        key = input_id(spec)
        value = answers.get(key, "")
        kind = spec.get("type") or "string"
        if kind == "confirm":
            if value:
                argv.append(str(spec["name"]))
            continue
        if value is None or value == "":
            continue
        text = str(value)
        if spec.get("positional"):
            argv.append(text)
        else:
            argv.extend((str(spec["name"]), text))
    return argv


def guard_shell(argv: list[str]) -> None:
    if not argv:
        raise SystemExit("This task has an empty command.")
    program = Path(argv[0]).name
    if program in SHELLS and any(part in SHELL_FLAGS for part in argv[1:]):
        raise SystemExit(
            "This command starts a shell. Put the work in a script file and "
            "catalog that file so the command stays reviewable."
        )


def resolve_cwd(root: Path, run: dict) -> Path:
    raw = run.get("cwd", ".")
    if not isinstance(raw, str) or raw == "" or Path(raw).is_absolute():
        raise SystemExit(f"cwd must be a relative path, got {raw!r}")
    path = (root / raw).resolve()
    if not path.is_relative_to(root.resolve()):
        raise SystemExit(f"cwd escapes the project: {raw}")
    return path


def confirm_run(task: dict, argv: list[str], args: argparse.Namespace) -> bool:
    danger = task.get("danger", "safe")
    print("\n" + paint("$ " + shlex.join(argv), "1"))
    if danger == "destructive":
        if args.yes and args.confirm_task == task["id"]:
            return True
        if args.yes or not is_interactive():
            raise SystemExit(
                f"Destructive task. Re-run with --yes --confirm-task {task['id']}"
            )
        return prompt_text(f"Type {task['id']} to run it", None) == task["id"]
    if args.yes:
        return True
    if not is_interactive():
        raise SystemExit("Refusing to prompt. Pass --yes to run this task.")
    return prompt_confirm("Run this command?", danger == "safe")


def show_task_context(task: dict) -> None:
    danger = str(task.get("danger", "safe"))
    kind = KIND_LABEL.get(str(task.get("kind", "")), str(task.get("kind", "")))
    print(f"\n{paint(str(task.get('title', task.get('id', 'Task'))), '1')}")
    print(
        f"{kind}  {paint(danger, DANGER_COLOR.get(danger, '0'))}  {task.get('source', '')}"
    )
    summary = task.get("summary")
    if summary:
        print(f"\n{summary}")
    if task.get("details"):
        print(f"\n{task['details']}")
    prerequisites = task.get("prerequisites") or []
    if prerequisites:
        print("\nBefore you start:")
        for item in prerequisites:
            print(f"  - {item}")


def print_steps(task: dict) -> None:
    steps = task.get("steps") or []
    if steps:
        print("\nSteps:")
        for index, step in enumerate(steps, start=1):
            print(f"  {index}. {step}")
    if task.get("href"):
        print(f"\nOpen: {task['href']}")
    danger = str(task.get("danger", "safe"))
    if danger != "safe":
        print(paint(f"\nMarked {danger}. Nothing was run.", DANGER_COLOR.get(danger, "0")))


def run_task(
    task: dict,
    args: argparse.Namespace,
    provided: dict[str, str],
    catalog_path: Path,
) -> int:
    if "cli" not in (task.get("surface") or []):
        raise SystemExit(
            f"{task.get('id')} is a product task. Open the wizard in the app."
        )
    show_task_context(task)
    if task.get("kind") in GUIDED or "run" not in task:
        print_steps(task)
        return 0
    answers = collect_inputs(task, provided, is_interactive() and not args.yes)
    argv = assemble_argv(task, answers)
    guard_shell(argv)
    cwd = resolve_cwd(project_root(catalog_path), task["run"])
    if not confirm_run(task, argv, args):
        print("Cancelled.")
        return 0
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        completed = subprocess.run(argv, cwd=cwd, check=False)
    except FileNotFoundError:
        raise SystemExit(f"Command not found: {argv[0]}") from None
    return int(completed.returncode)


def list_tasks(catalog: dict) -> str:
    lines = []
    for task in catalog["tasks"]:
        if not isinstance(task, dict):
            continue
        surfaces = ",".join(task.get("surface") or [])
        lines.append(
            f"{task.get('id', '')}\t{task.get('danger', '')}\t{surfaces}\t{task.get('title', '')}"
        )
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def print_briefing(catalog: dict) -> None:
    project = catalog.get("project") or {}
    print(paint(str(project.get("name", "Wizard")), "1"))
    if project.get("summary"):
        print(project["summary"])
    for section in catalog.get("briefing") or []:
        if not isinstance(section, dict):
            continue
        print(f"\n{paint(str(section.get('title', '')), '1')}")
        print(section.get("body", ""))


def choose_and_run(catalog: dict, args: argparse.Namespace, catalog_path: Path) -> int:
    if questionary() is None:
        print("For arrow-key prompts: pip install questionary", file=sys.stderr)
    print_briefing(catalog)
    tasks = [
        task
        for task in catalog["tasks"]
        if isinstance(task, dict) and "cli" in (task.get("surface") or [])
    ]
    if not tasks:
        raise SystemExit("This catalog has no operator tasks.")
    choices = [
        {
            "value": task["id"],
            "label": f"{task['title']}  [{task.get('danger', 'safe')}]",
        }
        for task in tasks
    ]
    picked = prompt_select("What do you want to do?", choices)
    return run_task(task_map(catalog)[picked], args, {}, catalog_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Walk through this project's wizard catalog."
    )
    parser.add_argument("--list", action="store_true", help="List tasks and exit")
    parser.add_argument(
        "--briefing", action="store_true", help="Print the project briefing and exit"
    )
    parser.add_argument("--task", help="Run one task by id")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="ID=VALUE",
        help="Provide an input. Repeat for more than one.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Run a safe or writes task without a confirmation prompt",
    )
    parser.add_argument(
        "--confirm-task",
        help="For a destructive task, pass the task id as confirmation",
    )
    parser.add_argument("--catalog", help="Catalog file instead of wizard/catalog.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog_path = find_catalog(args.catalog)
    catalog = load_catalog(catalog_path)
    if args.list:
        sys.stdout.write(list_tasks(catalog))
        return 0
    if args.briefing:
        print_briefing(catalog)
        return 0
    provided = parse_sets(args.set)
    if args.task:
        found = task_map(catalog)
        if args.task not in found:
            known = ", ".join(sorted(found)) or "(none)"
            raise SystemExit(f"Unknown task {args.task!r}. Known tasks: {known}")
        return run_task(found[args.task], args, provided, catalog_path)
    if not is_interactive():
        raise SystemExit("Pass --list, --briefing, or --task. This is not a terminal.")
    return choose_and_run(catalog, args, catalog_path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130) from None
