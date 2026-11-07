# AGENTS.md

## Project

Agent Wizardry is an [Agent Skill](https://agentskills.io/specification). The skill directory is `.agents/skills/agent-wizardry/`, and its name matches the `name` field in `SKILL.md`. An agent that follows it reads a repository and builds a wizard in that repository's language.

The catalog format is language-neutral. `.agents/skills/agent-wizardry/references/wizard.py` is a Python implementation of the operator behavior, and `references/web/` is a React implementation of the product button. Agents reimplement those. They copy a reference only when the target project is already that language.

This repository's tooling is Python, so the wizard for working on Agent Wizardry is the Python reference. `wizard.py` at the repo root points at that reference. `.agents/skills/agent-wizardry/scripts/validate_catalog.py` checks catalogs. `catalog.schema.json` beside it is for editors. The checker wins if the schema drifts.

When you change the reference runner's behavior, bump `RUNNER_VERSION` in the reference `wizard.py` and update `catalog-spec.md` and `tests/` in the same change. When you change catalog rules, update the checker, the spec, and the schema together. Keep the skill directory named `agent-wizardry`.

## Agent Wizardry

This project ships a wizard. `wizard/catalog.json` is the map of what a person can do here. The operator wizard is a program in this project's language. Later agents keep that program and the catalog together.

- Catalog: `wizard/catalog.json`
- Operator wizard: `python wizard.py`
- Product wizard: none
- Web catalog: none

When you add, rename, remove, or change a script, task-runner target, package script, GitHub Actions workflow, Compose service, documented command, CLI flag, environment variable a person must set, or a user-facing flow:

1. Update `wizard/catalog.json` in the same change. Re-read the source first. Record real flags, defaults, and paths. Leave out anything you cannot find in the repo.
2. Update the operator wizard only when its behavior no longer matches the catalog. Keep it in the language it was written in.
3. Set `danger` from the effect of the task. `safe` does not write or delete. `writes` changes local, remote, or shared state. `destructive` deletes, overwrites, or deploys in a way that is hard to undo. `writes` and `destructive` set `confirm` to true.
4. Keep operator commands on the `cli` surface. Keep product guidance on the `web` surface. A web task has steps or a link and has no `run` command.
5. Keep one catalog. When a product wizard exists, regenerate its web catalog from `wizard/catalog.json`. Do not keep a second task list in the UI.
6. Validate against the Agent Wizardry catalog spec, and fix what it reports. Use the skill's `validate_catalog.py` when it is available.
7. Leave the wizard in place. A change that adds a way to run the project also updates the wizard.

## Conventions

- Run `make test` after changing the checker, the reference runner, or a catalog.
