"use client";

import { ChevronRight, Plus } from "lucide-react";
import { useState } from "react";

import { LessonRow } from "@/components/LessonRow";
import { Button } from "@/components/ui/button";
import { EditableText } from "@/components/ui/editable-text";
import {
  type PlanEditor,
  mapModule,
  moduleNumeral,
  moduleSummary,
  removeListEntry,
  setListEntry,
} from "@/lib/plan";
import type { Module } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  A module is a rule-separated `<section>` with a hanging numeral, not a card:
  no background, no border box, no radius. The rule above it and the number
  beside it are the container, which is how a printed syllabus does it and why
  the outline stays readable at four levels of content without nesting.

  The numeral doubles as the collapse control. It has to be *something* on
  hover, and a chevron in the margin costs no layout -- while a collapsed module
  keeps its summary line, so folding never hides what the module is.
*/

interface Props {
  module: Module;
  index: number;
  editor: PlanEditor;
}

export function ModuleSection({ module, index, editor }: Props) {
  const [open, setOpen] = useState(true);
  const titlePath = `${module.id}.title`;
  const numeral = moduleNumeral(index);

  return (
    <section
      aria-labelledby={`${module.id}-title`}
      className="line-in grid grid-cols-1 gap-x-4 border-t border-rule-strong pt-8 pb-8 first:border-t-0 first:pt-6 sm:grid-cols-[36px_minmax(0,1fr)] lg:grid-cols-[56px_minmax(0,1fr)]"
      style={{ animationDelay: `${Math.min(index, 6) * 40}ms` }}
    >
      <div className="pt-[0.35rem] text-left sm:text-right">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`${module.id}-body`}
          aria-label={`${open ? "Collapse" : "Expand"} module ${index + 1}, ${module.title}`}
          onClick={() => setOpen((previous) => !previous)}
          className="numeral group/num cursor-pointer text-ink-faint transition-colors duration-100 hover:text-ink-quiet"
        >
          <span className="group-hover/num:hidden group-focus-visible/num:hidden">{numeral}</span>
          <ChevronRight
            size={16}
            strokeWidth={1.5}
            aria-hidden
            className={cn(
              "hidden group-hover/num:inline group-focus-visible/num:inline",
              open && "rotate-90",
            )}
          />
        </button>
      </div>

      <div className="min-w-0">
        <h2 id={`${module.id}-title`}>
          <EditableText
            value={module.title}
            label={`Module ${index + 1} title: ${module.title}`}
            placeholder="Untitled module"
            className="plan-title module-title text-ink"
            saving={editor.saving(titlePath)}
            error={editor.error(titlePath)}
            onCommit={(title) =>
              editor.commit(titlePath, (plan) =>
                mapModule(plan, module.id, (current) => ({ ...current, title })),
              )
            }
          />
        </h2>

        <p className="datum mt-1 text-ink-quiet">{moduleSummary(module)}</p>

        <div id={`${module.id}-body`} hidden={!open}>
          <div className="group/objectives mt-4">
            <span className="label text-ink-quiet">Objectives</span>
            <ul className="mt-4 space-y-3">
              {module.objectives.map((objective, position) => {
                const path = `${module.id}.objectives.${position}`;
                return (
                  <li key={path} className="body flex max-w-[72ch] gap-2 text-ink-soft">
                    {/* An objective is not a task, so it takes a dot and never a tick. */}
                    <span aria-hidden className="text-rule-firm">
                      ·
                    </span>
                    <EditableText
                      value={objective}
                      label={`Objective ${position + 1} of module ${index + 1}`}
                      placeholder="Empty objective"
                      multiline
                      allowEmpty
                      className="body text-ink-soft"
                      saving={editor.saving(path)}
                      error={editor.error(path)}
                      onCommit={(value) =>
                        editor.commit(path, (plan) =>
                          mapModule(plan, module.id, (current) => ({
                            ...current,
                            objectives: setListEntry(current.objectives, position, value),
                          })),
                        )
                      }
                    />
                  </li>
                );
              })}
            </ul>
            <Button
              variant="quiet"
              aria-label={`Add an objective to module ${index + 1}`}
              className="mt-2 gap-1 opacity-0 group-hover/objectives:opacity-100 focus-visible:opacity-100"
              onClick={() =>
                editor.commit(`${module.id}.objectives`, (plan) =>
                  mapModule(plan, module.id, (current) => ({
                    ...current,
                    objectives: [...current.objectives, ""],
                  })),
                )
              }
            >
              <Plus size={14} strokeWidth={1.5} aria-hidden />
              Objective
            </Button>
          </div>

          <div className="group/assumes mt-3 flex flex-wrap items-center gap-2">
            <span className="label text-ink-quiet">Assumes</span>
            {module.prerequisites.map((prerequisite, position) => {
              const path = `${module.id}.prerequisites.${position}`;
              return (
                // Dashed, because the border style carries the meaning: this
                // topic is assumed, not taught here.
                <span
                  key={path}
                  className="group/tag datum inline-flex items-center gap-1 rounded-[3px] border border-dashed border-rule-firm px-2 py-[3px] text-ink-soft transition-colors duration-100 hover:border-ink-quiet hover:text-ink"
                >
                  <EditableText
                    value={prerequisite}
                    label={`Prerequisite ${position + 1} of module ${index + 1}`}
                    placeholder="Empty"
                    allowEmpty
                    className="datum"
                    saving={editor.saving(path)}
                    error={editor.error(path)}
                    onCommit={(value) =>
                      editor.commit(path, (plan) =>
                        mapModule(plan, module.id, (current) => ({
                          ...current,
                          prerequisites: setListEntry(current.prerequisites, position, value),
                        })),
                      )
                    }
                  />
                  <button
                    type="button"
                    aria-label={`Remove prerequisite ${prerequisite}`}
                    onClick={() =>
                      editor.commit(path, (plan) =>
                        mapModule(plan, module.id, (current) => ({
                          ...current,
                          prerequisites: removeListEntry(current.prerequisites, position),
                        })),
                      )
                    }
                    className="cursor-pointer text-ink-quiet opacity-0 transition-opacity duration-100 group-hover/tag:opacity-100 hover:text-danger focus-visible:opacity-100"
                  >
                    ×
                  </button>
                </span>
              );
            })}
            <Button
              variant="quiet"
              aria-label={`Add a prerequisite to module ${index + 1}`}
              className="gap-1 opacity-0 group-hover/assumes:opacity-100 focus-visible:opacity-100"
              onClick={() =>
                editor.commit(`${module.id}.prerequisites`, (plan) =>
                  mapModule(plan, module.id, (current) => ({
                    ...current,
                    prerequisites: [...current.prerequisites, ""],
                  })),
                )
              }
            >
              <Plus size={14} strokeWidth={1.5} aria-hidden />
              Prerequisite
            </Button>
          </div>

          {module.lessons.length > 0 ? (
            <ol
              aria-label={`Lessons in module ${index + 1}`}
              className="mt-4 border-l border-rule pl-4"
            >
              {module.lessons.map((lesson, position) => (
                <LessonRow
                  key={lesson.id}
                  lesson={lesson}
                  moduleId={module.id}
                  moduleIndex={index}
                  lessonIndex={position}
                  editor={editor}
                />
              ))}
            </ol>
          ) : null}

          {/* Dedented out of the lesson spine: the assessment closes the module,
              so it must not read as one more lesson. */}
          {module.assessment ? (
            <div className="mt-6">
              <span className="label text-ink-quiet">Assessment</span>
              <div className="mt-2">
                <EditableText
                  value={module.assessment.title}
                  label={`Assessment title for module ${index + 1}`}
                  placeholder="Untitled assessment"
                  className="plan-title assessment-title text-ink"
                  saving={editor.saving(`${module.id}.assessment.title`)}
                  error={editor.error(`${module.id}.assessment.title`)}
                  onCommit={(title) =>
                    editor.commit(`${module.id}.assessment.title`, (plan) =>
                      mapModule(plan, module.id, (current) => ({
                        ...current,
                        assessment: current.assessment ? { ...current.assessment, title } : null,
                      })),
                    )
                  }
                />
                <p className="datum mt-1 text-ink-quiet">{module.assessment.kind}</p>
                <EditableText
                  value={module.assessment.description}
                  label={`Assessment brief for module ${index + 1}`}
                  placeholder="No brief yet"
                  multiline
                  allowEmpty
                  className="body mt-2 max-w-[72ch] text-ink-soft"
                  saving={editor.saving(`${module.id}.assessment.description`)}
                  error={editor.error(`${module.id}.assessment.description`)}
                  onCommit={(description) =>
                    editor.commit(`${module.id}.assessment.description`, (plan) =>
                      mapModule(plan, module.id, (current) => ({
                        ...current,
                        assessment: current.assessment
                          ? { ...current.assessment, description }
                          : null,
                      })),
                    )
                  }
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
