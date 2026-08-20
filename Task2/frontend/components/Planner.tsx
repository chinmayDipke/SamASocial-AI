"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Conversation } from "@/components/Conversation";
import { PlanSheet, PlanToolbar } from "@/components/PlanPanel";
import { usePlanner } from "@/hooks/usePlanner";
import type { PlanEditor } from "@/lib/plan";
import { cn } from "@/lib/utils";

/*
  The shell. Conversation on the left at a fixed width, the plan on the right
  taking the rest; each column scrolls on its own and the page never does.

  Below `lg` the two become tabs rather than a stack, because a stacked plan
  puts the artefact below the fold of a conversation that grows all session --
  the mentor would never see it again. The toolbar stays above the switch in
  both layouts, so the export actions and the edit hint never disappear.
*/

type Tab = "chat" | "plan";

const TABS: readonly Tab[] = ["chat", "plan"];
const TAB_LABEL: Record<Tab, string> = { chat: "Conversation", plan: "Plan" };

export function Planner() {
  const planner = usePlanner();
  const {
    plan,
    savingPaths,
    editErrors,
    editField,
    notice,
    retry,
    startFresh,
    dismissNotice,
  } = planner;

  const editor = useMemo<PlanEditor>(
    () => ({
      commit: editField,
      saving: (path) => savingPaths.includes(path),
      error: (path) => editErrors[path] ?? null,
    }),
    [editField, savingPaths, editErrors],
  );

  const [tab, setTab] = useState<Tab>("chat");
  // Once the mentor picks a tab we stop moving it under them.
  const chosen = useRef(false);
  const moduleCount = plan?.modules.length ?? 0;
  const planStamp = plan?.updated_at ?? "";
  const assistantTurns = planner.turns.filter((turn) => turn.role === "assistant").length;

  const tabRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ chat: null, plan: null });

  const chooseTab = (next: Tab) => {
    chosen.current = true;
    setTab(next);
  };

  /*
    Roving tabindex: the whole switch is one Tab stop and the arrows move inside
    it. That is what a screen reader promises the moment it says "tab, 1 of 2",
    and without it the promise is false.
  */
  const moveTab = (event: React.KeyboardEvent, from: number) => {
    const last = TABS.length - 1;
    let target = from;
    switch (event.key) {
      case "ArrowRight":
        target = from === last ? 0 : from + 1;
        break;
      case "ArrowLeft":
        target = from === 0 ? last : from - 1;
        break;
      case "Home":
        target = 0;
        break;
      case "End":
        target = last;
        break;
      default:
        return;
    }
    event.preventDefault();
    const next = TABS[target];
    chooseTab(next);
    tabRefs.current[next]?.focus();
  };

  // The plan is the point, so it takes over as soon as there is one to show.
  useEffect(() => {
    if (!chosen.current && moduleCount > 0) setTab("plan");
  }, [moduleCount]);

  const [waiting, setWaiting] = useState({ chat: 0, plan: 0 });
  const seenPlan = useRef("");
  const seenTurns = useRef(0);

  // Content landing in the hidden tab bumps a count on its label, not a red dot.
  useEffect(() => {
    if (tab === "plan" || planStamp === "" || planStamp === seenPlan.current) {
      seenPlan.current = planStamp;
      setWaiting((previous) => (previous.plan === 0 ? previous : { ...previous, plan: 0 }));
      return;
    }
    seenPlan.current = planStamp;
    setWaiting((previous) => ({ ...previous, plan: previous.plan + 1 }));
  }, [planStamp, tab]);

  useEffect(() => {
    if (tab === "chat" || assistantTurns === seenTurns.current) {
      seenTurns.current = assistantTurns;
      setWaiting((previous) => (previous.chat === 0 ? previous : { ...previous, chat: 0 }));
      return;
    }
    const arrived = assistantTurns - seenTurns.current;
    seenTurns.current = assistantTurns;
    if (arrived > 0) setWaiting((previous) => ({ ...previous, chat: previous.chat + arrived }));
  }, [assistantTurns, tab]);

  return (
    <main className="flex h-dvh flex-col overflow-hidden lg:grid lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[420px_minmax(0,1fr)] 2xl:grid-cols-[460px_minmax(0,1fr)]">
      <section
        id="panel-chat"
        role="tabpanel"
        aria-label="Planning conversation"
        className={cn(
          "order-2 min-h-0 flex-col border-rule-strong bg-desk-shade lg:order-none lg:flex lg:flex-1 lg:border-r",
          tab === "chat" ? "flex flex-1" : "hidden",
        )}
      >
        <Conversation
          turns={planner.turns}
          intake={planner.intake}
          starting={planner.starting}
          streaming={planner.streaming}
          stage={planner.stage}
          hasPlan={plan !== null}
          upload={planner.upload}
          maxUploadMb={planner.maxUploadMb}
          onSend={planner.send}
          onStop={planner.stop}
          onUpload={planner.uploadSyllabus}
          onDismissUpload={planner.dismissUpload}
        />
      </section>

      <section
        id="panel-plan"
        role="tabpanel"
        aria-label="Course plan"
        className={cn(
          "order-1 flex min-h-0 flex-col bg-desk lg:order-none lg:flex-1",
          tab === "plan" && "flex-1",
        )}
      >
        <PlanToolbar plan={plan} sessionId={planner.sessionId} />

        <div className="shrink-0 border-b border-rule-strong bg-desk px-5 py-2 lg:hidden">
          <div
            role="tablist"
            aria-label="Switch between the conversation and the plan"
            className="flex h-[44px] items-center gap-0.5 rounded-[5px] bg-paper-warm p-0.5"
          >
            {TABS.map((key, index) => (
              <button
                key={key}
                ref={(element) => {
                  tabRefs.current[key] = element;
                }}
                type="button"
                role="tab"
                id={`tab-${key}`}
                aria-selected={tab === key}
                aria-controls={`panel-${key}`}
                tabIndex={tab === key ? 0 : -1}
                onClick={() => chooseTab(key)}
                onKeyDown={(event) => moveTab(event, index)}
                className={cn(
                  "control h-full flex-1 rounded-[5px] transition-colors duration-100",
                  tab === key
                    ? "border border-rule-firm bg-paper text-ink"
                    : "text-ink-quiet hover:text-ink",
                )}
              >
                {TAB_LABEL[key]}
                {waiting[key] > 0 ? (
                  <span className="datum ml-2 text-ink-quiet">+{waiting[key]}</span>
                ) : null}
              </button>
            ))}
          </div>
        </div>

        {notice ? (
          <div
            role="alert"
            className="flex shrink-0 items-baseline gap-3 border-y border-danger-rule bg-danger-tint px-5 py-3 lg:px-8"
          >
            <span className="label shrink-0 text-danger">{notice.label}</span>
            <p className="body min-w-0 text-ink-soft">{notice.text}</p>
            <button
              type="button"
              onClick={
                notice.action === "retry"
                  ? retry
                  : notice.action === "fresh"
                    ? () => void startFresh()
                    : dismissNotice
              }
              className="control ml-auto shrink-0 cursor-pointer text-danger underline decoration-danger/40"
            >
              {notice.action === "retry"
                ? "Retry"
                : notice.action === "fresh"
                  ? "Start fresh"
                  : "Dismiss"}
            </button>
          </div>
        ) : null}

        <PlanSheet
          plan={plan}
          stage={planner.stage}
          editor={editor}
          className={tab === "chat" ? "hidden lg:block" : undefined}
        />
      </section>
    </main>
  );
}
