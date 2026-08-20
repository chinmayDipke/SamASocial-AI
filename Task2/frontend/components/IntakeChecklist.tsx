"use client";

import { Check } from "lucide-react";

import type { Intake } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  Four fixed slots in a fixed order. They never reorder as answers arrive, so a
  mentor's eye does not have to re-find them, and the count in the header
  answers "how much more of this is there" without reading the rows.

  Pending is a small unfilled square rather than a spinner or a hollow circle:
  it reads as a field on a form that has not been written in yet, which is
  exactly what it is.
*/

type SlotKey = "subject" | "audience" | "duration" | "goals";

const SLOTS: readonly { key: SlotKey; name: string }[] = [
  { key: "subject", name: "Subject" },
  { key: "audience", name: "Audience" },
  { key: "duration", name: "Duration" },
  { key: "goals", name: "Goals" },
];

function valueOf(intake: Intake, key: SlotKey): string | null {
  if (key === "goals") return intake.goals.length > 0 ? intake.goals.join(" · ") : null;
  return intake[key];
}

/** The slot the assistant is asking about now: the first one still unfilled. */
export function askingSlot(intake: Intake): string | null {
  return SLOTS.find((slot) => valueOf(intake, slot.key) === null)?.key ?? null;
}

export function IntakeChecklist({ intake, asking }: { intake: Intake; asking: string | null }) {
  const filled = SLOTS.filter((slot) => valueOf(intake, slot.key) !== null).length;

  return (
    <div className="mb-6 border-y border-rule-strong py-3">
      <div className="flex items-baseline justify-between">
        <span className="label text-ink-quiet">Intake</span>
        <span className="datum text-ink-quiet">
          {filled} / {SLOTS.length}
        </span>
      </div>

      <dl className="mt-1">
        {SLOTS.map((slot) => {
          const value = valueOf(intake, slot.key);
          const done = value !== null;
          const active = asking === slot.key;

          return (
            <div
              key={slot.key}
              className={cn(
                "grid grid-cols-[16px_84px_minmax(0,1fr)] items-baseline gap-x-2 py-1",
                // The wash is the pointer -- no colour change, no left border.
                active && "-mx-2 rounded-[3px] bg-paper-warm px-2",
              )}
            >
              <span className="flex items-baseline">
                {done ? (
                  <Check size={14} strokeWidth={1.5} className="text-accent" aria-hidden />
                ) : (
                  <span
                    aria-hidden
                    className="mt-[0.3rem] h-[9px] w-[9px] rounded-[2px] border border-rule-firm"
                  />
                )}
              </span>
              <dt
                className={cn(
                  "label",
                  done ? "text-ink-quiet" : active ? "text-ink" : "text-ink-faint",
                )}
              >
                {slot.name}
              </dt>
              <dd className={cn("body truncate", done ? "text-ink" : "text-ink-faint")}>
                {done ? value : "—"}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
