"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { STAGE_LABEL, type Stage } from "@/lib/types";

/*
  The one primary button on screen lives here. While the assistant is working
  the box is disabled and says which of the four stages it is in -- a disabled
  control with no stated reason is the thing that makes an app feel broken.
*/

const MAX_LINES = 6;

interface Props {
  /** True until a session exists. */
  disabled: boolean;
  streaming: boolean;
  stage: Stage | null;
  hasPlan: boolean;
  onSend: (message: string) => void;
  onStop: () => void;
}

export function Composer({ disabled, streaming, stage, hasPlan, onSend, onStop }: Props) {
  const [value, setValue] = useState("");
  const field = useRef<HTMLTextAreaElement>(null);

  // Grow with the answer, up to six lines.
  useEffect(() => {
    const element = field.current;
    if (!element) return;
    const lineHeight = 22;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, lineHeight * MAX_LINES)}px`;
  }, [value]);

  const trimmed = value.trim();
  const blocked = disabled || streaming;

  const submit = () => {
    if (!trimmed || blocked) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div className="shrink-0 border-t border-rule-strong bg-desk-shade pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <textarea
        ref={field}
        rows={1}
        value={value}
        disabled={blocked}
        aria-label="Answer the assistant, or ask for a change to the plan"
        placeholder={
          hasPlan
            ? "Ask for a change — make module 2 simpler, add a project"
            : "What do you want to teach, and to whom?"
        }
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        className="body w-full resize-none rounded-[5px] border border-rule-firm bg-paper px-3 py-2 text-ink placeholder:text-ink-faint disabled:bg-paper-warm disabled:text-ink-faint"
      />

      <div className="mt-2 flex items-baseline justify-between gap-3">
        {streaming && stage ? (
          <span className="datum min-w-0 truncate text-ink-quiet">{STAGE_LABEL[stage]}</span>
        ) : (
          <span className="datum min-w-0 truncate text-ink-quiet">
            Enter to send · Shift+Enter for a new line
          </span>
        )}

        {streaming ? (
          <Button variant="quiet" onClick={onStop}>
            Stop
          </Button>
        ) : (
          <Button variant="primary" onClick={submit} disabled={blocked || !trimmed}>
            Send
          </Button>
        )}
      </div>
    </div>
  );
}
