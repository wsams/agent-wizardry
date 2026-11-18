# Catalog spec

`wizard/catalog.json` is the source of truth, and any language can read it. `scripts/validate_catalog.py` next to this file checks the spec. `catalog.schema.json` mirrors it for editors. When they disagree, the checker wins.

```json
{
  "version": 1,
  "project": {
    "name": "Display name",
    "summary": "One or two sentences from the docs.",
    "docs": ["README.md"]
  },
  "briefing": [
    { "title": "What this is", "body": "Short context the wizard prints first." }
  ],
  "tasks": []
}
```

`version` is the integer `1`. `project.name` and `project.summary` are required. `project.docs` is an optional list of files that exist in the repo. `briefing` is optional. A catalog has at least one task.

Paths in `source`, `docs`, and `run.cwd` are relative to the project root, stay inside it, and contain no `..`. A `source` may end with `#heading`. Cite a file you read. Do not cite a URL.

`$schema` is optional. A relative schema path is resolved from the catalog file.

## Tasks

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable kebab-case id. Keep it across edits. |
| `title` | yes | What the person sees in the menu. |
| `summary` | yes | When to choose this task, in one or two sentences. |
| `details` | no | Extra context: side effects, files it touches, what it does not do. |
| `kind` | yes | One of the kinds below. |
| `source` | yes | File that justifies the task. |
| `danger` | yes | `safe`, `writes`, or `destructive`. |
| `confirm` | when danger is `writes` or `destructive` | `true` for those two. Optional on `safe`. |
| `surface` | yes | `cli`, `web`, or both where the rules allow it. |
| `prerequisites` | no | Strings. What must already be true. |
| `inputs` | no | Flags and arguments, in the order they belong on the command. |
| `run` | see below | `{ "argv": ["tool", "arg"], "cwd": "." }` |
| `steps` | see below | Numbered instructions for `manual` and `app` tasks. |
| `href` | no | In-app path (`/import`) or absolute `http(s)` URL. |

Kinds:

| Kind | Surface | Run |
| --- | --- | --- |
| `script`, `npm`, `make`, `just`, `task`, `workflow`, `compose` | `["cli"]` only | `argv` required |
| `manual` | `cli`, `web`, or both | forbidden; provide `steps` or `href` |
| `app` | includes `web` | forbidden; provide `steps` or `href` |

`argv` is a list of strings executed with no shell. The program is `argv[0]`. Do not start `bash`, `sh`, `zsh`, `dash`, `cmd`, `powershell`, or `pwsh` with `-c`, `-lc`, or `/c`. Put a pipeline in a script file and catalog that file.

`cwd` defaults to `.` and is relative to the project root.

A task that includes `web` has no `run` block. The browser never receives a command.

## Danger

- `safe` — reading, tests that do not write outside a temp dir, printing help.
- `writes` — edits files, pushes, opens a pull request, starts a workflow, installs into the home directory, changes shared state.
- `destructive` — deletes, force-pushes, drops data, or deploys somewhere hard to undo.

Judge the task as a whole. A deploy that also has a dry-run flag is still `writes` or `destructive`, because the person can run it for real. Say in `details` how to avoid the write.

## Inputs

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | when `name` would repeat | Key for answers and for `--set`. Defaults to `name`. |
| `name` | yes | Flag (`--env`) or, with `positional`, the label used in help. |
| `prompt` | yes | Question the wizard asks. |
| `help` | no | What the flag does, from the source. |
| `type` | no | `string` (default), `select`, `confirm`, `path`, or `multiline`. |
| `required` | no | Default false. |
| `default` | no | Used when the person presses enter, and when `--set` is omitted. |
| `choices` | for `select` | `{ "value", "label", "help?" }`. `value` is what is passed through. |
| `positional` | no | Append the value without a flag. Not valid for `confirm`. |

On a task that runs a command, a non-positional name starts with `-`. Several inputs may share a flag such as `-f` when each has its own `id`. Product inputs, on tasks with no `run` block, use a plain name.

The runner appends flags in list order:

- `confirm` true appends `name` and nothing else. False appends nothing.
- `positional` appends the value.
- anything else appends `name` and then the value.
- empty optional values are left off.

`--set id=value` supplies an answer. Repeat the flag for more than one input. Booleans accept `true`, `false`, `yes`, `no`, `1`, and `0`.

### workflow_dispatch

Record each Actions input as a `-f` select (or string). The choice value includes the input name:

```json
{
  "id": "environment",
  "name": "-f",
  "type": "select",
  "default": "environment=staging",
  "choices": [{ "value": "environment=staging", "label": "Staging" }]
}
```

`run.argv` is `["gh", "workflow", "run", "<workflow-file>"]`.

## Placements

Omit `placements` when one mark can offer every web task. The product wizard then shows one mark, and that mark lists every web task.

Add `placements` when different parts of the product have different next steps. Each object is one mark:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Kebab-case, unique. The UI passes this id when it renders the mark. |
| `title` | yes | Heading of the dialog this mark opens. |
| `where` | yes | Where the mark sits, so a later agent can find the control. |
| `context` | yes | What the person is looking at. The dialog shows this before the tasks. |
| `tasks` | yes | Ids of tasks whose surface includes `web`, in the order to offer them. |

A task may appear in more than one placement. Every web task appears in at least one, so a product task is not written and then hidden. Operator tasks stay out of placements. The operator wizard ignores this key.

The mark is 🧙. Its accessible name is "Wizard", plus the placement title when the catalog has placements. There is no hat-only emoji. Do not use 🎩, and do not spell the word Wizard beside the mark.

Two spots that offer the same tasks reuse one placement id. A different set of tasks gets a new placement and its own mark.

## Web subset

`validate_catalog.py --write-web wizard/catalog.web.json` writes `version`, `project`, `briefing`, `placements` when that key is present, and the tasks whose surface includes `web`. `--check-web` fails when that file drifts. Edit `wizard/catalog.json`, then regenerate. Do not hand-edit the subset.

## Operator program

The agent writes this program in the project's language. `references/wizard.py` is a Python implementation of the same rules, used by this skill's own repository because that repository's tooling is Python. `RUNNER_VERSION` in that file tracks the reference. Bump it when the reference behavior changes, and update this spec and the tests in the same change.

Whatever the language, the program:

- Asks what to do. On a terminal, each choice shows its title, its summary in lighter text, and a short line for the danger and the command. Arrow keys move, Enter chooses, and `q` leaves. Nothing runs until the person confirms. When the terminal cannot draw that menu, the same title, summary, and command are printed under a number.
- Prints the task's context, asks for inputs, prints the command, and runs it after confirmation.
- `--list` prints `id`, `danger`, `surface`, and `title`, separated by tabs.
- `--briefing` prints the project briefing.
- `--task <id> --set id=value --yes` runs a `safe` or `writes` task without prompts. Repeat `--set` for more than one input.
- A `destructive` task also needs `--confirm-task <id>`.
- `manual` and `app` tasks print their steps and do not exec.
- Executes `argv` with no shell. Refuses to launch `bash`, `sh`, `zsh`, `dash`, `cmd`, `powershell`, or `pwsh` with `-c`, `-lc`, or `/c`.
