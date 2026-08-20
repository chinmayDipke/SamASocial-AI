"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ModuleSection } from "@/components/ModuleSection";
import { Button } from "@/components/ui/button";
import { EditableText } from "@/components/ui/editable-text";
import { api } from "@/lib/api";
import {
  type PlanEditor,
  moduleNumeral,
  planSummary,
  setListEntry,
  withPlanFields,
} from "@/lib/plan";
import type { CoursePlan, Stage } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  The right-hand column: a toolbar, then one sheet of paper carrying the plan.

  The toolbar is where discoverability lives. `CLICK ANY LINE TO EDIT` sits
  there permanently, which buys every field on the sheet the right to have no
  chrome at all -- no pencils, no hover buttons, no "edit mode". It is also why
  the toolbar is a separate export: below `lg` the tab switch and the error
  strip slot in underneath it, above the sheet.
*/

const HINT_MS = 2400;

export function PlanToolbar({
  plan,
  sessionId,
}: {
  plan: CoursePlan | null;
  sessionId: string | null;
}) {
  return (
    <div className="flex h-[52px] shrink-0 items-center gap-4 border-b border-rule-strong bg-desk px-5 lg:px-8">
      <span className="plan-title module-title min-w-0 flex-1 truncate text-ink">
        {plan ? plan.title : "Course Planner"}
      </span>
      {plan ? (
        <span className="datum hidden shrink-0 text-ink-quiet md:inline">{planSummary(plan)}</span>
      ) : null}
      <span className="datum hidden shrink-0 text-ink-quiet xl:inline">Click any line to edit</span>
      <Actions plan={plan} sessionId={sessionId} />
    </div>
  );
}

export function PlanSheet({
  plan,
  stage,
  editor,
  className,
}: {
  plan: CoursePlan | null;
  stage: Stage | null;
  editor: PlanEditor;
  className?: string;
}) {
  const drafting = stage === "drafting" || stage === "refining";

  return (
    <div className={cn("min-h-0 flex-1 overflow-y-auto", className)}>
      <div className="mx-auto max-w-[880px] border-rule bg-paper px-5 pt-12 pb-16 lg:px-8 2xl:rounded-b-[4px] 2xl:border-x 2xl:border-b 2xl:px-10">
        {plan ? <Written plan={plan} editor={editor} /> : <EmptySheet />}
        {drafting ? <DraftingSkeleton nextIndex={plan ? plan.modules.length : 0} /> : null}
      </div>
    </div>
  );
}

function Written({ plan, editor }: { plan: CoursePlan; editor: PlanEditor }) {
  return (
    <>
      <header className="grid grid-cols-1 gap-x-4 sm:grid-cols-[36px_minmax(0,1fr)] lg:grid-cols-[56px_minmax(0,1fr)]">
        <div />
        <div className="min-w-0">
          <h1>
            <EditableText
              value={plan.title}
              label={`Course title: ${plan.title}`}
              placeholder="Untitled course"
              className="plan-title course-title text-ink"
              saving={editor.saving("title")}
              error={editor.error("title")}
              onCommit={(title) =>
                editor.commit("title", (current) => withPlanFields(current, { title }))
              }
            />
          </h1>

          <p className="datum mt-2 text-ink-quiet">
            {[plan.subject, plan.audience, plan.duration].filter(Boolean).join(" · ")}
          </p>

          <div className="group/outcomes mt-6">
            <span className="label text-ink-quiet">Outcomes</span>
            <ul className="mt-4 space-y-3">
              {plan.outcomes.map((outcome, position) => {
                const path = `outcomes.${position}`;
                return (
                  <li key={path} className="body flex max-w-[72ch] gap-2 text-ink-soft">
                    <span aria-hidden className="text-rule-firm">
                      ·
                    </span>
                    <EditableText
                      value={outcome}
                      label={`Course outcome ${position + 1}`}
                      placeholder="Empty outcome"
                      multiline
                      allowEmpty
                      className="body text-ink-soft"
                      saving={editor.saving(path)}
                      error={editor.error(path)}
                      onCommit={(value) =>
                        editor.commit(path, (current) =>
                          withPlanFields(current, {
                            outcomes: setListEntry(current.outcomes, position, value),
                          }),
                        )
                      }
                    />
                  </li>
                );
              })}
            </ul>
            <Button
              variant="quiet"
              aria-label="Add a course outcome"
              className="mt-2 gap-1 opacity-0 group-hover/outcomes:opacity-100 focus-visible:opacity-100"
              onClick={() =>
                editor.commit("outcomes", (current) =>
                  withPlanFields(current, { outcomes: [...current.outcomes, ""] }),
                )
              }
            >
              <Plus size={14} strokeWidth={1.5} aria-hidden />
              Outcome
            </Button>
          </div>
        </div>
      </header>

      <div className="mt-8">
        {plan.modules.map((module, index) => (
          <ModuleSection key={module.id} module={module} index={index} editor={editor} />
        ))}
      </div>
    </>
  );
}

/*
  Left-aligned at the content-column origin, because a centred hero with an icon
  in a circle is the loudest tell of a generated page. The two dashed ghost rows
  below say what is coming: ruled paper waiting for a line.
*/
function EmptySheet() {
  return (
    <>
      <div className="grid grid-cols-1 gap-x-4 pt-12 sm:grid-cols-[36px_minmax(0,1fr)] lg:grid-cols-[56px_minmax(0,1fr)]">
        <div className="numeral pt-[0.35rem] text-left text-ink-faint sm:text-right">M —</div>
        <div className="max-w-[46ch]">
          <h1 className="plan-title module-title text-ink">Nothing planned yet.</h1>
          <p className="body mt-2 text-ink-soft">
            Answer the four questions on the left and the plan builds itself here, module by
            module. Every line is editable.
          </p>
          <p className="datum mt-4 text-ink-quiet">Click any line to edit</p>
        </div>
      </div>

      <div className="mt-12">
        {[0, 1].map((index) => (
          <div
            key={index}
            className="mt-8 grid grid-cols-1 gap-x-4 sm:grid-cols-[36px_minmax(0,1fr)] lg:grid-cols-[56px_minmax(0,1fr)]"
          >
            <div className="numeral pt-[0.35rem] text-left text-rule-strong sm:text-right">
              {moduleNumeral(index)}
            </div>
            <div className="h-6 border-b border-dashed border-rule" />
          </div>
        ))}
      </div>
    </>
  );
}

/*
  The structure arrives before the text, which is what is actually happening:
  the numeral is already known, so it is shown for real, and the lines still
  being written are drawn left to right rather than pulsed as grey blocks.
*/
function DraftingSkeleton({ nextIndex }: { nextIndex: number }) {
  const lines = [
    { width: "62%", delay: "0s", top: "" },
    { width: "38%", delay: ".12s", top: "mt-4" },
    { width: "52%", delay: ".24s", top: "mt-3" },
  ];

  return (
    <section
      aria-hidden
      className="grid grid-cols-1 gap-x-4 border-t border-rule-strong pt-8 pb-8 sm:grid-cols-[36px_minmax(0,1fr)] lg:grid-cols-[56px_minmax(0,1fr)]"
    >
      <div className="numeral pt-[0.35rem] text-left text-ink-faint sm:text-right">
        {moduleNumeral(nextIndex)}
      </div>
      <div>
        {lines.map((line) => (
          <div
            key={line.width}
            className={cn("rule-draw h-px bg-rule", line.top)}
            style={{ width: line.width, animationDelay: line.delay }}
          />
        ))}
      </div>
    </section>
  );
}

/**
 * Export and copy.
 *
 * The download is a real fetch of the export endpoint rather than a bare link,
 * so a failure lands in this toolbar as a message instead of navigating the app
 * away to a JSON error page.
 */
function Actions({ plan, sessionId }: { plan: CoursePlan | null; sessionId: string | null }) {
  const [hint, setHint] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  useEffect(() => {
    if (!hint) return;
    const timer = window.setTimeout(() => setHint(null), HINT_MS);
    return () => window.clearTimeout(timer);
  }, [hint]);

  const download = useCallback(async () => {
    if (!sessionId) return;
    try {
      const { blob, filename } = await api.exportPlan(sessionId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      // Two browser rules, both easy to trip: Firefox ignores a programmatic click
      // on an anchor that is not in the document, and revoking the URL in the same
      // tick cancels the download it just started.
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setHint({ tone: "ok", text: `Saved ${filename}` });
    } catch (error: unknown) {
      setHint({ tone: "bad", text: error instanceof Error ? error.message : "Export failed." });
    }
  }, [sessionId]);

  const copy = useCallback(async () => {
    if (!plan) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(plan, null, 2));
      setHint({ tone: "ok", text: "Copied as JSON" });
    } catch {
      setHint({
        tone: "bad",
        text: "The browser blocked the clipboard. Use Export JSON instead.",
      });
    }
  }, [plan]);

  return (
    <div className="flex shrink-0 items-center gap-2">
      {hint ? (
        <span className={cn("datum", hint.tone === "ok" ? "text-ink-quiet" : "text-danger")}>
          {hint.text}
        </span>
      ) : null}
      <Button variant="quiet" onClick={copy} disabled={!plan}>
        Copy
      </Button>
      <Button variant="secondary" onClick={download} disabled={!plan || !sessionId}>
        <span className="label">Export JSON</span>
      </Button>
    </div>
  );
}
