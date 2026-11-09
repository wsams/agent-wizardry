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
import select
import shlex
import shutil
import subprocess
import sys
import termios
import tty
from pathlib import Path

RUNNER_VERSION = 2

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

DANGER_COLOR = {"safe": "38;5;150", "writes": "38;5;222", "destructive": "38;5;210"}
SHELLS = {"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"}
SHELL_FLAGS = {"-c", "-lc", "/c"}
GUIDED = {"manual", "app"}
ACCENT = "38;5;213"
FAINT = "2;38;5;246"
QUIET = "38;5;243"
BODY = "38;5;252"
BAR_DIM = "38;5;240"


def paint(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def wrap(text: str, width: int) -> list[str]:
    width = max(16, width)
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def term_width() -> int:
    return max(48, shutil.get_terminal_size(fallback=(80, 24)).columns)


def lead(text: str) -> str:
    """The first sentence, so a long project summary does not crowd the menu."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    stop = cleaned.find(". ")
    if stop != -1:
        return cleaned[: stop + 1]
    return cleaned


def task_hint(task: dict) -> str:
    """A short line under the summary: what kind of effect, and the command."""
    danger = str(task.get("danger") or "safe")
    run = task.get("run") if isinstance(task.get("run"), dict) else {}
    argv = run.get("argv") if isinstance(run, dict) else None
    if isinstance(argv, list) and argv:
        return f"{danger} · {shlex.join(str(part) for part in argv)}"
    if task.get("kind") in GUIDED:
        return f"{danger} · explains the steps, and does not run a command"
    return danger


def menu_item(value: str, title: str, detail: str = "", meta: str = "") -> dict:
    return {"value": value, "title": title, "detail": detail.strip(), "meta": meta.strip()}


def tasks_as_items(tasks: list[dict]) -> list[dict]:
    return [
        menu_item(
            str(task.get("id") or ""),
            str(task.get("title") or task.get("id") or "Task"),
            str(task.get("summary") or ""),
            task_hint(task),
        )
        for task in tasks
    ]


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


def item_rows(item: dict, selected: bool, width: int, color: bool) -> list[str]:
    """One menu row: a bar, the name, then lighter lines for what it does."""
    inner = max(20, width - 8)

    def tone(text: str, code: str) -> str:
        if not color:
            return text
        return f"\033[{code}m{text}\033[0m"

    bar = tone("┃", ACCENT if selected else BAR_DIM)
    mark = tone("›", ACCENT + ";1") if selected else " "
    title = tone(item["title"], "1" if selected else BODY)
    rows = [f"  {bar} {mark} {title}"]
    for line in wrap(item.get("detail") or "", inner):
        rows.append(f"  {bar}   {tone(line, FAINT)}")
    meta = item.get("meta") or ""
    if meta:
        rows.append(f"  {bar}   {tone(meta, QUIET)}")
    rows.append(f"  {bar}")
    return rows


def menu_frame(heading: str, summary: str, intro: str, items: list[dict], selected: int, width: int, height: int, color: bool) -> str:
    def tone(text: str, code: str) -> str:
        if not color:
            return text
        return f"\033[{code}m{text}\033[0m"

    bar = tone("┃", ACCENT)
    blocks = [item_rows(item, index == selected, width, color) for index, item in enumerate(items)]
    header = [f"  {bar} {tone(heading, '1')}"]
    for line in wrap(lead(summary), max(20, width - 6)):
        header.append(f"  {bar} {tone(line, FAINT)}")
    if intro:
        header.append(f"  {bar}")
        for line in wrap(intro, max(20, width - 6)):
            header.append(f"  {bar} {tone(line, FAINT)}")
    header.append(f"  {bar}")
    footer = [
        f"  {bar}",
        f"  {bar} {tone('↑↓ move    enter choose    q leave', QUIET)}",
    ]
    room = max(6, height - len(header) - len(footer) - 1)
    heights = [len(block) for block in blocks]
    start = 0
    while selected > start and sum(heights[start:selected + 1]) > room:
        start += 1
    end = start
    used = 0
    while end < len(blocks) and used + heights[end] <= room:
        used += heights[end]
        end += 1
    if selected >= end:
        end = selected + 1
        start = end
        used = 0
        while start > 0 and used + heights[start - 1] <= room:
            start -= 1
            used += heights[start]
    body: list[str] = []
    if start > 0:
        body.append(f"  {bar} {tone(f'{start} more above', QUIET)}")
    for block in blocks[start:end]:
        body.extend(block)
    if end < len(blocks):
        body.append(f"  {bar} {tone(f'{len(blocks) - end} more below', QUIET)}")
    return "\n".join(header + body + footer) + "\n"


def prompt_menu_plain(heading: str, items: list[dict]) -> str:
    print(f"\n{heading}")
    print("The lighter line under a name is what that choice does.\n")
    for index, item in enumerate(items, start=1):
        print(f"  {index}  {item['title']}")
        if item.get("detail"):
            print(f"     {item['detail']}")
        if item.get("meta"):
            print(f"     {item['meta']}")
        print()
    while True:
        raw = input("Choose a number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return str(items[int(raw) - 1]["value"])
        print(f"Enter a number from 1 to {len(items)}.")


def screen_text(frame: str) -> str:
    """Raw mode does not turn a newline into a carriage return, so each line would start where the last one ended."""
    return "\033[H\033[J" + frame.replace("\n", "\r\n")


def read_key(fd: int) -> str:
    data = os.read(fd, 1)
    if not data:
        return ""
    char = data.decode("utf-8", "replace")
    if char != "\x1b":
        return char
    if select.select([fd], [], [], 0.03)[0]:
        return char + os.read(fd, 8).decode("utf-8", "replace")
    return char


def prompt_menu(heading: str, summary: str, intro: str, items: list[dict]) -> str:
    if not items:
        raise SystemExit("There is nothing to choose.")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return prompt_menu_plain(heading, items)
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    selected = 0
    sys.stdout.write("\033[?1049h\033[?25l")
    sys.stdout.flush()
    try:
        tty.setcbreak(fd)
        while True:
            size = shutil.get_terminal_size(fallback=(80, 24))
            frame = menu_frame(
                heading,
                summary,
                intro,
                items,
                selected,
                size.columns,
                size.lines,
                True,
            )
            sys.stdout.write(screen_text(frame))
            sys.stdout.flush()
            key = read_key(fd)
            if key in {"\x03", "q", "Q"}:
                raise KeyboardInterrupt
            if key in {"\x1b[A", "\x1bOA", "k"}:
                selected = (selected - 1) % len(items)
            elif key in {"\x1b[B", "\x1bOB", "j"}:
                selected = (selected + 1) % len(items)
            elif key in {"\r", "\n"}:
                return str(items[selected]["value"])
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()


def prompt_select(message: str, choices: list[dict]) -> str:
    items = [
        menu_item(
            str(choice["value"]),
            str(choice.get("title") or choice.get("label") or choice["value"]),
            str(choice.get("detail") or choice.get("help") or ""),
            str(choice.get("meta") or ""),
        )
        for choice in choices
    ]
    return prompt_menu(message, "", "The lighter text is there so you can tell the choices apart.", items)


def prompt_confirm(message: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{paint('┃', ACCENT)} {message} [{hint}] ").strip().lower()
        if raw == "":
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Answer y or n.")


def prompt_text(message: str, default: str | None, help_text: str = "") -> str:
    if help_text and sys.stdout.isatty():
        print(paint(help_text, FAINT))
    suffix = f" [{default}]" if default not in (None, "") else ""
    raw = input(f"{paint('┃', ACCENT)} {message}{suffix} ")
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
                {
                    "value": choice["value"],
                    "title": str(choice.get("label") or choice["value"]),
                    "detail": str(choice.get("help") or ""),
                }
                for choice in spec.get("choices") or []
            ]
            answers[key] = prompt_select(prompt, choices)
            continue
        if ask:
            while True:
                raw = prompt_text(prompt, default, str(spec.get("help") or ""))
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
    print("\n" + paint("┃", ACCENT) + " " + paint(shlex.join(argv), "1"))
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
    title = str(task.get("title", task.get("id", "Task")))
    bar = paint("┃", ACCENT)
    print(f"\n{bar} {paint(title, '1')}")
    print(
        f"{bar} {kind}  {paint(danger, DANGER_COLOR.get(danger, '0'))}  {task.get('source', '')}"
    )
    summary = task.get("summary")
    if summary:
        print(bar)
        for line in wrap(str(summary), term_width() - 4):
            print(f"{bar} {line}")
    if task.get("details"):
        print(bar)
        for line in wrap(str(task["details"]), term_width() - 4):
            print(f"{bar} {paint(line, FAINT)}")
    prerequisites = task.get("prerequisites") or []
    if prerequisites:
        print(f"{bar}\n{bar} Before you start")
        for item in prerequisites:
            print(f"{bar}   · {item}")


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
    name = str(project.get("name", "Wizard"))
    summary = str(project.get("summary") or "")
    if not sys.stdout.isatty():
        print(name)
        if summary:
            print(summary)
        for section in catalog.get("briefing") or []:
            if not isinstance(section, dict):
                continue
            print(f"\n{section.get('title', '')}")
            print(section.get("body", ""))
        return
    bar = paint("┃", ACCENT)
    print(f"\n{bar} {paint(name, '1')}")
    for line in wrap(summary, term_width() - 4):
        print(f"{bar} {paint(line, FAINT)}")
    for section in catalog.get("briefing") or []:
        if not isinstance(section, dict):
            continue
        print(f"{bar}\n{bar} {paint(str(section.get('title', '')), '1')}")
        for line in wrap(str(section.get("body") or ""), term_width() - 4):
            print(f"{bar} {paint(line, FAINT)}")


def choose_and_run(catalog: dict, args: argparse.Namespace, catalog_path: Path) -> int:
    tasks = [
        task
        for task in catalog["tasks"]
        if isinstance(task, dict) and "cli" in (task.get("surface") or [])
    ]
    if not tasks:
        raise SystemExit("This catalog has no operator tasks.")
    project = catalog.get("project") or {}
    print_briefing(catalog)
    picked = prompt_menu(
        str(project.get("name") or "Wizard"),
        str(project.get("summary") or ""),
        "The lighter text under each name says what that choice does. Nothing runs until you pick one and confirm.",
        tasks_as_items(tasks),
    )
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
