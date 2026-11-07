# Sample operator project

This fixture shows how Agent Wizardry catalogs a script and a GitHub Actions workflow. It is not a product, and it has no web UI.

`sample-script.sh` prints a deploy line for `--env staging` or `--env production`. `--dry-run` prints the plan and writes nothing. The default environment is staging.

`sample-workflow.yml` is a `workflow_dispatch` workflow with one input, `environment`. It lives here as a catalog fixture. It is not installed under `.github/workflows`.
