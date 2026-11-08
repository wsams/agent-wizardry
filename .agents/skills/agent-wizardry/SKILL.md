---
name: agent-wizardry
description: >-
  Inventories a repository's scripts, task runners, GitHub Actions workflows,
  CLI flags, and docs, then has the agent build a project wizard in that
  project's language. The wizard is backed by wizard/catalog.json, explains
  each task and its flags before running it, and adds an AGENTS.md contract
  so later agents keep it current. Adds a wizard mark (🧙) in the app's
  existing UI, once or in several sections, and each mark opens only the
  tasks for that place. Use when the user asks for a project wizard, Agent
  Wizardry, an onboarding wizard, help operating an unfamiliar repo, or a
  wizard in the UI.
---

# Agent Wizardry

You are the agent. You inventory the repository in front of you and you build the wizard in the language that repository already uses. This skill is the contract. It is not tied to one agent product, and it does not install a prebuilt wizard.

Leave a catalog, an operator wizard you wrote, and an AGENTS.md contract. Add wizard marks in the product only when [web-wizard.md](web-wizard.md) says to.

Vocabulary:

- **Catalog** — `wizard/catalog.json`, the only task list. Language-neutral.
- **Operator wizard** — the program you write. It runs catalog tasks on the machine where the repo is checked out.
- **Product wizard** — wizard marks (🧙) you add in the app's existing UI. Each mark explains the product tasks for that place and opens screens. It does not run shell commands.
- **Contract** — the `## Agent Wizardry` section in `AGENTS.md`. It names the command you actually created.

Read [catalog-spec.md](catalog-spec.md), [web-wizard.md](web-wizard.md), and [agents-contract.md](agents-contract.md) before writing files. Read [examples.md](examples.md) when the shape of a task is unclear. Read `references/wizard.py` for the operator behavior, and `references/web/` for the product behavior. Those files are references. Reimplement them. Copy one only when the project is already that language and the file fits without adding a runtime.

## Steps

1. Inventory the repo. Read sources. Do not run the tasks you find.
2. Choose the language. See below.
3. Decide the product wizard with the checklist in [web-wizard.md](web-wizard.md).
4. Write or update `wizard/catalog.json`.
5. Implement the operator wizard in the chosen language.
6. Add the product wizard, in the app's UI framework, when the checklist is all yes.
7. Merge the contract into `AGENTS.md`, with the real command filled in.
8. Validate. Do not execute catalog tasks.
9. Report, including the command you created and why that language fit.

If a catalog or a wizard program already exists, start from it. Keep task ids that are still true. Update tasks whose source changed. Remove tasks whose source is gone. Extend the existing program. Do not rewrite it in another language because a reference file was handy.

## Language

Use the language this project already runs.

- Prefer the language of the maintainer scripts, or the language the README uses to build and run the app.
- A product wizard uses the UI framework already in the app. A React app gets the React mark. A Vue, Svelte, server-rendered, or template app gets the same mark in that stack.
- When the user names a language, use that.
- Do not add a language, runtime, package manager, or UI framework to host the wizard.

Put the program where this repo already keeps commands: `cmd/wizard`, `scripts/wizard.ts`, `wizard.py`, `bin/wizard`, a Make target, or the equivalent. One entry point is enough.

## Inventory

Skip `examples/`, `node_modules/`, `vendor/`, `dist/`, `.git/`, and generated bundles.

Read what exists:

- README, docs, CONTRIBUTING, AGENTS.md
- `.env.example` for variable **names**. Never copy values from `.env`, and never write a secret, token, or private URL into the catalog.
- `package.json` scripts, `pyproject.toml` scripts, `composer.json` scripts, Cargo aliases
- Makefile, justfile, Justfile, Taskfile, mage targets
- `scripts/`, `bin/`, `cmd/`
- `.github/workflows/` — record `workflow_dispatch` inputs when they exist
- Dockerfile, Compose files, Procfile, fly.toml, render.yaml
- Argument parsers in the project's own CLIs (argparse, click, typer, cobra, clap, and the project's equivalents)
- For the product-wizard decision: routes, navigation, empty states, and getting-started docs written for a person using the running app

A task is something a person would choose on purpose: someone who cloned the repo, or someone standing in the product. Skip install hooks, pre/post scripts only other scripts call, watch modes, formatters, and generated files, unless the docs tell a human to run them. A short catalog of real tasks is the goal.

If a flag is not in the parser, the script, the workflow, or the docs, it is not an input. If you cannot tell what a script does after reading it, leave it out and name it in the report. A repo with no runnable work gets no invented tasks: say that and stop.

## Catalog

Follow [catalog-spec.md](catalog-spec.md). `scripts/validate_catalog.py` in this skill is a checker for that spec. The spec wins if you cannot run the checker.

Operator commands use `"surface": ["cli"]` and a `run.argv` list. The wizard executes that list directly, with no shell. Product guidance uses `"surface": ["web"]`, includes `steps` or `href`, and has no `run` block. `manual` steps may be on either surface. `app` tasks are product actions and include `web`.

`danger` describes the effect of following the task. `safe` does not write or delete. `writes` changes local, remote, or shared state. `destructive` deletes, overwrites, or ships something hard to undo. `writes` and `destructive` set `"confirm": true`.

## Operator behavior

The program you write loads `wizard/catalog.json` and does all of this. `references/wizard.py` is a complete Python version of the same behavior. Use a prompt library the project already accepts. Otherwise the language's standard input is enough.

- Print the project briefing, then ask what the person wants to do.
- For the chosen task, show the summary, details, source, prerequisites, and danger.
- Ask each input in order, with its help text and default.
- Build the command from `run.argv` by the input rules in [catalog-spec.md](catalog-spec.md). Execute that list with no shell.
- Show the exact command before running it.
- `safe` confirmation defaults to yes. `writes` defaults to no. `destructive` requires the person to type the task id.
- `manual` and `app` tasks print their steps and do not execute.
- A task whose surface is only `web` tells the person to open the product wizard.
- Support a non-interactive path with the flags in [catalog-spec.md](catalog-spec.md): `--list`, `--briefing`, `--task`, `--set`, `--yes`, and `--confirm-task`.

Do not paste the catalog into the program. The catalog stays the file later agents edit.

## Product wizard

Follow [web-wizard.md](web-wizard.md). Build the mark in the UI the app already has. `references/web/WizardPanel.tsx` shows the behavior in React: the mark is 🧙, and a `placement` prop limits the dialog to that place's tasks. Translate it when the app is not React.

Publish a web subset the browser can see, and point the button at that file rather than the full catalog. When Python is available:

```bash
python <skill-dir>/scripts/validate_catalog.py wizard/catalog.json --write-web wizard/catalog.web.json
```

`<skill-dir>` is the directory that contains this `SKILL.md`. When Python is not available, write the same subset by hand from the spec: `version`, `project`, `briefing`, `placements` when the catalog has them, and the tasks whose surface includes `web`.

Wire links and callbacks only to screens and handlers the app already has. Do not add an API whose job is to shell out to the repository. Do not add a language model unless the app already calls one. When it does, the catalog is the context, and the assistant may only recommend catalog tasks.

## Contract

Insert [agents-contract.md](agents-contract.md) as the `## Agent Wizardry` section. Create `AGENTS.md` when the repo has none. When it exists, replace an existing `## Agent Wizardry` section or append one. Leave every other section alone.

Replace the placeholders:

- `{{OPERATOR_WIZARD}}` — the command you implemented, such as `python wizard.py`, `node scripts/wizard.mjs`, or `go run ./cmd/wizard`
- `{{PRODUCT_WIZARD}}` — `none`, or the path of the component you added
- `{{WEB_CATALOG}}` — `none`, or `wizard/catalog.web.json`

## Validate

When Python is available:

```bash
python <skill-dir>/scripts/validate_catalog.py wizard/catalog.json
```

When a product wizard was added, also run `--check-web wizard/catalog.web.json`. Then run the wizard's list command and confirm every cataloged task appears. Fix every problem before you finish. Do not run a catalog task.

## Report

Tell the user:

- Which sources you read
- Which language you used, and why it was already the project's
- The operator tasks you wrote
- The command that starts the wizard
- Each of the four product-wizard answers, and either each placement (its id, where it sits, and its tasks) or the answer that kept the marks out
- Anything you left uncataloged because the source did not support it
