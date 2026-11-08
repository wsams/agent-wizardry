/**
 * Product wizard panel.
 *
 * Reference product wizard for a React app. Copy these files only when the
 * app is already React. Otherwise reimplement this behavior in the app's UI
 * framework. Pass the web catalog, never the full catalog.
 *
 * Fit the markup to the host design system when the app has one.
 */
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./wizard.css";

export type WizardChoice = {
  value: string;
  label: string;
  help?: string;
};

export type WizardInput = {
  id?: string;
  name: string;
  prompt: string;
  help?: string;
  type?: "string" | "select" | "confirm" | "path" | "multiline";
  required?: boolean;
  default?: string | boolean;
  choices?: WizardChoice[];
};

export type WizardTask = {
  id: string;
  title: string;
  summary: string;
  details?: string;
  danger?: "safe" | "writes" | "destructive";
  prerequisites?: string[];
  steps?: string[];
  href?: string;
  surface?: string[];
  inputs?: WizardInput[];
  run?: unknown;
};

export type WizardPlacement = {
  id: string;
  title: string;
  where: string;
  context: string;
  tasks: string[];
};

export type WizardCatalog = {
  project: { name: string; summary: string };
  briefing?: { title: string; body: string }[];
  placements?: WizardPlacement[];
  tasks: WizardTask[];
};

export type WizardAnswers = Record<string, string | boolean>;

/** The wizard mark. There is no hat-only emoji. */
export const WIZARD_MARK = "🧙";

type WizardButtonProps = {
  catalog: WizardCatalog;
  /** Placement id. Required when the catalog has placements. */
  placement?: string;
  onContinue?: (task: WizardTask, answers: WizardAnswers) => void;
};

function inputKey(input: WizardInput): string {
  return input.id || input.name;
}

function productTasks(catalog: WizardCatalog): WizardTask[] {
  return catalog.tasks.filter(
    (task) => (task.surface ?? []).includes("web") && task.run == null,
  );
}

function tasksForPlacement(catalog: WizardCatalog, placementId?: string): WizardTask[] {
  const web = productTasks(catalog);
  const placements = catalog.placements ?? [];
  if (placements.length === 0) {
    return placementId ? [] : web;
  }
  const placement = placements.find((item) => item.id === placementId);
  if (!placement) {
    return [];
  }
  const order = new Map(placement.tasks.map((id, index) => [id, index]));
  return web
    .filter((task) => order.has(task.id))
    .sort((left, right) => (order.get(left.id) ?? 0) - (order.get(right.id) ?? 0));
}

export function WizardButton({ catalog, placement: placementId, onContinue }: WizardButtonProps) {
  const placement = catalog.placements?.find((item) => item.id === placementId) ?? null;
  const tasks = tasksForPlacement(catalog, placementId);
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<WizardAnswers>({});
  const task = tasks.find((item) => item.id === taskId) ?? null;

  useEffect(() => {
    if (!open) {
      return;
    }
    dialogRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, taskId]);

  if (tasks.length === 0) {
    return null;
  }

  function close() {
    setOpen(false);
    setTaskId(null);
  }

  function openTask(next: WizardTask) {
    const initial: WizardAnswers = {};
    for (const input of next.inputs ?? []) {
      if (input.default != null) {
        initial[inputKey(input)] = input.default;
      }
    }
    setAnswers(initial);
    setTaskId(next.id);
  }

  function setAnswer(key: string, value: string | boolean) {
    setAnswers((current) => ({ ...current, [key]: value }));
  }

  function continueTask() {
    if (!task) {
      return;
    }
    onContinue?.(task, answers);
    if (task.href) {
      window.location.assign(task.href);
      return;
    }
    setTaskId(null);
  }

  const primaryLabel = task?.href ? "Open this" : onContinue ? "Continue" : "Done";
  const homeTitle = placement?.title ?? catalog.project.name;
  const label = placement ? `Wizard: ${placement.title}` : "Wizard";

  return (
    <div className="aw-wizard">
      <button
        type="button"
        className="aw-wizard-button"
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          setTaskId(null);
          setOpen(true);
        }}
      >
        <span aria-hidden="true">{WIZARD_MARK}</span>
      </button>
      {open
        ? createPortal(
            <div className="aw-backdrop" onClick={close}>
              <div
                className="aw-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                tabIndex={-1}
                ref={dialogRef}
                onClick={(event) => event.stopPropagation()}
              >
                <div className="aw-dialog-head">
                  <h2 id={titleId}>{task ? task.title : homeTitle}</h2>
                  <button type="button" className="aw-close" onClick={close}>
                    Close
                  </button>
                </div>
                {task ? (
                  <TaskView
                    task={task}
                    answers={answers}
                    onAnswer={setAnswer}
                    onBack={() => setTaskId(null)}
                    onContinue={continueTask}
                    primaryLabel={primaryLabel}
                  />
                ) : (
                  <Home
                    catalog={catalog}
                    tasks={tasks}
                    context={placement?.context}
                    onOpen={openTask}
                  />
                )}
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}

function Home({
  catalog,
  tasks,
  context,
  onOpen,
}: {
  catalog: WizardCatalog;
  tasks: WizardTask[];
  context?: string;
  onOpen: (task: WizardTask) => void;
}) {
  return (
    <>
      <p className="aw-summary">{context ?? catalog.project.summary}</p>
      {context
        ? null
        : (catalog.briefing ?? []).map((section) => (
            <section className="aw-briefing" key={section.title}>
              <h3>{section.title}</h3>
              <p>{section.body}</p>
            </section>
          ))}
      <ul className="aw-tasks">
        {tasks.map((task) => (
          <li key={task.id}>
            <button type="button" className="aw-task" onClick={() => onOpen(task)}>
              <span className="aw-task-title">
                {task.title}
                <DangerBadge danger={task.danger} />
              </span>
              <span className="aw-muted">{task.summary}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

function TaskView({
  task,
  answers,
  onAnswer,
  onBack,
  onContinue,
  primaryLabel,
}: {
  task: WizardTask;
  answers: WizardAnswers;
  onAnswer: (key: string, value: string | boolean) => void;
  onBack: () => void;
  onContinue: () => void;
  primaryLabel: string;
}) {
  return (
    <>
      <p className="aw-summary">{task.summary}</p>
      {task.details ? <p>{task.details}</p> : null}
      {task.prerequisites?.length ? (
        <>
          <h3>Before you start</h3>
          <ul className="aw-prereq">
            {task.prerequisites.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {(task.inputs ?? []).map((input) => (
        <InputField
          key={inputKey(input)}
          input={input}
          value={answers[inputKey(input)]}
          onAnswer={onAnswer}
        />
      ))}
      {task.steps?.length ? (
        <>
          <h3>Steps</h3>
          <ol className="aw-steps">
            {task.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </>
      ) : null}
      <div className="aw-actions">
        <button type="button" className="aw-back" onClick={onBack}>
          All tasks
        </button>
        <button type="button" className="aw-action" onClick={onContinue}>
          {primaryLabel}
        </button>
      </div>
    </>
  );
}

function InputField({
  input,
  value,
  onAnswer,
}: {
  input: WizardInput;
  value: string | boolean | undefined;
  onAnswer: (key: string, value: string | boolean) => void;
}) {
  const key = inputKey(input);
  if (input.type === "select" && input.choices?.length) {
    return (
      <fieldset className="aw-field">
        <legend>{input.prompt}</legend>
        {input.help ? <p className="aw-muted">{input.help}</p> : null}
        <div className="aw-tasks" role="radiogroup" aria-label={input.prompt}>
          {input.choices.map((choice) => (
            <button
              type="button"
              key={choice.value}
              className="aw-choice"
              role="radio"
              aria-checked={value === choice.value}
              onClick={() => onAnswer(key, choice.value)}
            >
              <span className="aw-choice-label">{choice.label}</span>
              {choice.help ? <span className="aw-muted">{choice.help}</span> : null}
            </button>
          ))}
        </div>
      </fieldset>
    );
  }
  if (input.type === "confirm") {
    return (
      <label className="aw-field">
        <input
          type="checkbox"
          checked={value === true}
          onChange={(event) => onAnswer(key, event.target.checked)}
        />{" "}
        {input.prompt}
        {input.help ? <span className="aw-muted"> {input.help}</span> : null}
      </label>
    );
  }
  return (
    <label className="aw-field">
      {input.prompt}
      {input.help ? <p className="aw-muted">{input.help}</p> : null}
      <input
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onAnswer(key, event.target.value)}
      />
    </label>
  );
}

function DangerBadge({ danger }: { danger?: WizardTask["danger"] }) {
  if (!danger || danger === "safe") {
    return null;
  }
  return <span className={`aw-badge aw-badge-${danger}`}>{danger}</span>;
}
