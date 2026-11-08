# Product wizard

The product wizard is a wizard mark in a web app. The mark is 🧙. Its accessible name is "Wizard". There is no hat-only emoji, so do not substitute 🎩, and do not spell the word Wizard next to the mark.

The mark asks what the person wants to do from this place, then shows the catalog task that matches: what it does, what has to be true first, the choices and what each one means, and the steps. The primary action opens a screen the app already has, or calls a handler the app already has.

You build that mark in the UI framework the app already uses. `references/web/WizardPanel.tsx` and `references/web/wizard.css` are one React rendering of the behavior. Translate them for Vue, Svelte, a server template, or whatever else the app is. Copy them only into a React app, and then fit them to that app's layout.

The operator wizard is the other surface. It is the program named in the project's Agent Wizardry contract, and it is the only surface that runs repository commands. It is not filtered by placement.

## Checklist

Add a product wizard only when every answer is yes.

1. **Browser UI.** This repo builds an interface a person opens in a browser.
2. **Easy to get lost.** A newcomer can miss what to do first. Evidence is a crowded nav, a multi-step setup, feature flags, an empty state with no guidance, or the user saying people get lost.
3. **A place for the mark.** Somewhere a person is deciding what to do next can hold a small wizard mark. One place is enough when every newcomer faces the same next step. Add a mark in each section whose next step is different.
4. **Product actions.** The guided work is something the product does: create, import, connect, configure, or explain a screen. Deploy scripts, Makefiles, and GitHub workflows are operator tasks.

Record each answer in the final report. When any answer is no, skip the marks and name the answer.

## What to add

1. Write the file the browser is allowed to see, `wizard/catalog.web.json`. It contains `version`, `project`, `briefing`, `placements` when the catalog has them, and the tasks whose surface includes `web`. The skill checker can write it when Python is available:

   ```bash
   python <skill-dir>/scripts/validate_catalog.py wizard/catalog.json --write-web wizard/catalog.web.json
   ```

2. Put the mark where the decision happens. Pass the placement id when the catalog has `placements`. One mark with no placement id is correct only when `placements` is omitted; it offers every web task. Two spots that offer the same tasks reuse one placement id. The control loads `wizard/catalog.web.json`, never `wizard/catalog.json`.
3. Match the host design system when the app has one. Keep the mark small enough to sit in a header, an empty state, or beside a section title.
4. The dialog leads with that placement's `context`, then lists only that placement's tasks. With no placements, lead with the project summary and briefing.
5. Ask "what do you want to do?", then show the task's summary, details, prerequisites, choices, and steps.
6. The primary action follows `href` or an existing in-app handler. Render nothing when that place has no tasks. Hide any task that still has a `run` block.

Do not add a second catalog per screen. Do not add a backend route whose job is to exec a repository script. Do not add a language model for the wizard unless the application already calls one. When it does, pass the tasks for the current placement as the context and restrict the assistant to those tasks.

## Security

- The browser sees the web subset: project briefing, placements, and `web` tasks.
- Web tasks have `steps` or `href` and no `run` block.
- Catalogs name environment variables. They do not contain secret values.
- Dangerous operator work stays in the operator wizard, behind its confirmation rules.
