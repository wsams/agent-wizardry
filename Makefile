.PHONY: test validate

test:
	python -m unittest discover -s tests -v

validate:
	python .agents/skills/agent-wizardry/scripts/validate_catalog.py wizard/catalog.json
	python .agents/skills/agent-wizardry/scripts/validate_catalog.py examples/cli-project/wizard/catalog.json
	python .agents/skills/agent-wizardry/scripts/validate_catalog.py examples/web-project/wizard/catalog.json
