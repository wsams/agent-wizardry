# Agent Wizardry

A repository starts with one command. Then it grows a Makefile, a deploy script, two GitHub workflows, and a flag that only exists in the source. The person who built it can still operate it. Everyone else is guessing: you, six months later; a teammate who just cloned it; an agent asked to "just deploy it"; someone opening the product who cannot tell what to click first.

Agent Wizardry is a skill any coding agent can follow. Point an agent at a repository and it reads the scripts, workflows, and docs, then builds a wizard in the language that project already uses. The list of tasks is the same everywhere. The program that asks the questions is whatever fits the repo: Python, Go, TypeScript, PHP, a shell, or the UI framework the app already has.

When the confusing part is the product itself, the agent adds a **Wizard** button to the interface the app already ships. The button asks what you want to do and walks you through the setup the app actually supports. In the repository, the operator wizard does the same job for the scripts and workflows, in whatever language that repository is built with.

## What the agent leaves behind

```
your-repo/
├── wizard/catalog.json       # the task list, the same shape in every language
├── <the wizard program>      # written in this repo's language
├── wizard/catalog.web.json   # browser subset, and only when a product wizard exists
└── AGENTS.md                 # names the command, and tells the next agent to keep it current
```

The catalog records each task, the file it came from, the flags and their defaults, and whether running it is safe, a write, or destructive. The program the agent writes reads that catalog:

- what the task does, and the file it came from
- what has to be true before you run it
- each flag, with the help text and the default
- the exact command
- a confirmation that gets stricter as the task gets more dangerous

`safe` tasks ask with a default of yes. `writes` tasks default to no. `destructive` tasks make you type the task id. The command is the argument list from the catalog, run with no shell.

A product wizard, when the checklist calls for one, is a Wizard button in the header, built in the app's existing UI. The browser receives the web subset, not the deploy commands.

## Why it stays current

The agent also writes a section into `AGENTS.md`. The next agent, whichever product it is, loads that section: if you add, rename, or change a script, a workflow, a flag, or a user-facing flow, you update the catalog in that same change, and you keep the wizard program in the language it was written in. The wizard is part of the project, not a snapshot taken on the day it was installed.

The skill includes a Python reading of the operator behavior and a React reading of the product button, so an agent can see the interaction once. Those are references. A Go service gets a Go wizard. A Vue app gets a Vue button.

## Scope

- The catalog records work the repo or the product can already do. Flags come from the parser, the script, the workflow, or the docs. Anything that cannot be found is left out.
- The agent implements the wizard. It uses the project's language and UI, and it does not add a runtime just to host the wizard.
- The operator wizard runs on the machine where the repo is checked out.
- The product wizard explains, asks, and opens screens that already exist. Shell commands stay in the operator program.
- One catalog feeds both surfaces. The browser gets `wizard/catalog.web.json`, the tasks marked `web`.
- Deletes, deploys, and other hard-to-undo work are labeled `destructive` and require the task id before they run.
- A project with nothing to run does not get invented tasks.
- A language-model chat is wired in only when the app already has one, and that chat may only recommend catalog tasks.

The agent adds a product wizard when all four of these are true: the repo has a browser UI, a newcomer can miss the first step, there is a sensible place for one button, and the guided actions are things the product does. A library, a CLI, or a pile of scripts gets an operator wizard and no button.

## The skill format

Agent Wizardry is an [Agent Skill](https://agentskills.io/specification). A skill is a directory whose name matches the `name` in `SKILL.md`. That file holds the metadata and the instructions. `scripts/` holds commands an agent can run, and `references/` holds detail the agent reads when it needs it.

The folder installed for an agent has to be named `agent-wizardry`. This repository keeps that folder at `.agents/skills/agent-wizardry/`.

## Install

A symlink keeps every agent on this checkout. From a clone, this links the skill into the personal directory each of these agents reads:

```bash
src="$(pwd)/.agents/skills/agent-wizardry"
for dir in \
  ~/.agents/skills \
  ~/.claude/skills \
  ~/.copilot/skills \
  ~/.cursor/skills \
  ~/.grok/skills
do
  mkdir -p "$dir"
  ln -sfn "$src" "$dir/agent-wizardry"
done
```

| Agent | Personal skill directory | Project skill directory |
| --- | --- | --- |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/agent-wizardry/` | `.claude/skills/agent-wizardry/` |
| [GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) | `~/.copilot/skills/agent-wizardry/` | `.github/skills/agent-wizardry/` |
| [Cursor](https://cursor.com/docs/skills) | `~/.cursor/skills/agent-wizardry/` | `.cursor/skills/agent-wizardry/` |
| [Grok](https://docs.x.ai/build/features/skills-plugins-marketplaces) | `~/.grok/skills/agent-wizardry/` | `.grok/skills/agent-wizardry/` |
| [Codex](https://developers.openai.com/codex/skills) | `~/.agents/skills/agent-wizardry/` | `.agents/skills/agent-wizardry/` |

Copilot, Cursor, Codex, and Grok also read `~/.agents/skills/` and `.agents/skills/`. Opening this repository is enough for those four, because the skill is already at `.agents/skills/agent-wizardry/`. Claude Code reads `~/.claude/skills/` and `.claude/skills/`, so Claude needs the link from the loop above.

To install it into one other repository instead of your home directory, point that repo's project path at the same folder. For Copilot, Cursor, Codex, or Grok:

```bash
mkdir -p /path/to/other-repo/.agents/skills
ln -sfn /path/to/agent-wizardry/.agents/skills/agent-wizardry \
  /path/to/other-repo/.agents/skills/agent-wizardry
```

For Claude Code in that repository, use `.claude/skills/agent-wizardry/` as the link target's parent. Restart the agent session after installing. In Claude Code, `/reload-skills` picks up a directory created during the session.

## Use it

Open the project you want a wizard for and ask:

> Use Agent Wizardry. Build the wizard in this project's language.

For a product people get lost in:

> Use Agent Wizardry, and add a Wizard button in the app's existing UI.

The agent will tell you the command it created. In a Python repo that might be `python wizard.py`. In another repo it will be that repo's equivalent.

## This repository

This repository's tooling is Python, so its own operator wizard is the Python reference: `python wizard.py`. That is a consequence of the rule, not the rule itself.

| Path | What it is |
| --- | --- |
| `.agents/skills/agent-wizardry/SKILL.md` | The procedure any agent follows |
| `.agents/skills/agent-wizardry/catalog-spec.md` | Catalog fields, and the behavior every wizard implements |
| `.agents/skills/agent-wizardry/web-wizard.md` | When to add a Wizard button, and how to build it in the host UI |
| `.agents/skills/agent-wizardry/agents-contract.md` | The `AGENTS.md` section, copied into each project |
| `.agents/skills/agent-wizardry/references/wizard.py` | A Python implementation of the operator behavior |
| `.agents/skills/agent-wizardry/references/web/` | A React implementation of the product button |
| `.agents/skills/agent-wizardry/scripts/validate_catalog.py` | Checks a catalog against the spec |
| `examples/cli-project/` | A script and a workflow, cataloged |
| `examples/web-project/` | A product task for an empty docs workspace |
| `wizard/catalog.json` | The wizard for working on Agent Wizardry |

```bash
make test
python wizard.py
```
