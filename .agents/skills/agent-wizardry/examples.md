# Examples

These fixtures show the catalog shape. They are not installed as this repository's wizard. This repository's own wizard is `wizard/catalog.json`.

## Operator tasks

`examples/cli-project/` is a script plus a workflow.

The script `sample-script.sh` accepts `--env staging|production` (default `staging`) and `--dry-run`. The catalog records those flags and no others. The task is `writes` because a real run prints a deploy line for the chosen environment, and `--dry-run` is the way to avoid that. The wizard still confirms before it runs.

GitHub Actions inputs become extra argv entries. `gh workflow run` takes `-f name=value`. Give each input its own id when several of them share the flag `-f`:

```json
{
  "id": "environment",
  "name": "-f",
  "prompt": "Which environment?",
  "help": "Sets the workflow_dispatch input named environment.",
  "type": "select",
  "required": true,
  "default": "environment=staging",
  "choices": [
    { "value": "environment=staging", "label": "Staging" },
    { "value": "environment=production", "label": "Production" }
  ]
}
```

The command list stays `["gh", "workflow", "run", "sample-workflow.yml"]`. The runner appends `-f` and `environment=staging`.

Product-wizard checklist for this fixture: (1) no browser UI. Stop. Operator wizard only.

## Product tasks

`examples/web-project/` is a one-page description of a docs workspace. The only cataloged action is the import flow that `README.md` describes.

Checklist: (1) yes, it is a browser UI. (2) yes, the empty workspace does not say what to do. (3) yes, the header can hold one Wizard button. (4) yes, import is a product action. Add the button. The task's `href` is `/import`. There is no `run` block.

A deploy script in that same repo would be a second task with `"surface": ["cli"]` and would be absent from `wizard/catalog.web.json`.

## This repository

Agent Wizardry has no product UI. Checklist question 1 is no. The catalog lists the tests, the validator, the test workflow, and the install steps. See `wizard/catalog.json`. This repository's tooling is Python, so the operator program here is the Python reference. A Go or Node repository would get a Go or Node program that reads a catalog of the same shape.
