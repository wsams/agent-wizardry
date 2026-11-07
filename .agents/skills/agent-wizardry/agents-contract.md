## Agent Wizardry

This project ships a wizard. `wizard/catalog.json` is the map of what a person can do here. The operator wizard is a program in this project's language. Later agents keep that program and the catalog together.

- Catalog: `wizard/catalog.json`
- Operator wizard: {{OPERATOR_WIZARD}}
- Product wizard: {{PRODUCT_WIZARD}}
- Web catalog: {{WEB_CATALOG}}

When you add, rename, remove, or change a script, task-runner target, package script, GitHub Actions workflow, Compose service, documented command, CLI flag, environment variable a person must set, or a user-facing flow:

1. Update `wizard/catalog.json` in the same change. Re-read the source first. Record real flags, defaults, and paths. Leave out anything you cannot find in the repo.
2. Update the operator wizard only when its behavior no longer matches the catalog. Keep it in the language it was written in.
3. Set `danger` from the effect of the task. `safe` does not write or delete. `writes` changes local, remote, or shared state. `destructive` deletes, overwrites, or deploys in a way that is hard to undo. `writes` and `destructive` set `confirm` to true.
4. Keep operator commands on the `cli` surface. Keep product guidance on the `web` surface. A web task has steps or a link and has no `run` command.
5. Keep one catalog. When a product wizard exists, regenerate its web catalog from `wizard/catalog.json`. Do not keep a second task list in the UI.
6. Validate against the Agent Wizardry catalog spec, and fix what it reports. Use the skill's `validate_catalog.py` when it is available.
7. Leave the wizard in place. A change that adds a way to run the project also updates the wizard.
