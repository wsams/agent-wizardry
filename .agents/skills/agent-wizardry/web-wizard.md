# Product wizard

The product wizard is a **Wizard** button in a web app. It asks what the person wants to do, then shows the catalog task that matches: what it does, what has to be true first, the choices and what each one means, and the steps. The primary action opens a screen the app already has, or calls a handler the app already has.

You build that button in the UI framework the app already uses. `references/web/WizardPanel.tsx` and `references/web/wizard.css` are one React rendering of the behavior. Translate them for Vue, Svelte, a server template, or whatever else the app is. Copy them only into a React app, and then fit them to that app's layout.

The operator wizard is the other surface. It is the program named in the project's Agent Wizardry contract, and it is the only surface that runs repository commands.

## Checklist

Add a product wizard only when every answer is yes.

1. **Browser UI.** This repo builds an interface a person opens in a browser.
2. **Easy to get lost.** A newcomer can miss what to do first. Evidence is a crowded nav, a multi-step setup, feature flags, an empty state with no guidance, or the user saying people get lost.
3. **A place for one control.** The header, the empty state, or both can hold a single Wizard button.
4. **Product actions.** The guided work is something the product does: create, import, connect, configure, or explain a screen. Deploy scripts, Makefiles, and GitHub workflows are operator tasks.

Record each answer in the final report. When any answer is no, skip the button and name the answer.

## What to add

1. Write the file the browser is allowed to see, `wizard/catalog.web.json`. It contains `version`, `project`, `briefing`, and the tasks whose surface includes `web`. The skill checker can write it when Python is available:

   ```bash
   python <skill-dir>/scripts/validate_catalog.py wizard/catalog.json --write-web wizard/catalog.web.json
   ```

2. Add one Wizard control to the header. When the app has an empty state, add it there too. The control loads `wizard/catalog.web.json`, never `wizard/catalog.json`.
3. Match the host design system when the app has one.
4. Ask "what do you want to do?", then show the task's summary, details, prerequisites, choices, and steps.
5. The primary action follows `href` or an existing in-app handler. Render nothing when the web catalog has no tasks. Hide any task that still has a `run` block.

Do not add a backend route whose job is to exec a repository script. Do not add a language model for the wizard unless the application already calls one. When it does, pass the web catalog as the context and restrict the assistant to tasks in that catalog.

## Security

- The browser sees the web subset: project briefing and `web` tasks.
- Web tasks have `steps` or `href` and no `run` block.
- Catalogs name environment variables. They do not contain secret values.
- Dangerous operator work stays in the operator wizard, behind its confirmation rules.
