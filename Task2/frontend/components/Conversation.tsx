"use client";

import { useEffect, useRef } from "react";

import { ChatTurn } from "@/components/ChatTurn";
import { Composer } from "@/components/Composer";
import { IntakeChecklist, askingSlot } from "@/components/IntakeChecklist";
import { SyllabusDrop } from "@/components/SyllabusDrop";
import type { UploadState } from "@/hooks/usePlanner";
import type { Intake, Stage, Turn } from "@/lib/types";

/*
  The left column: who is being interviewed, what has been answered, and the
  transcript. The checklist is pinned above the scroll because it is the only
  progress indicator this app has -- the plan itself is the reward, not a
  percentage bar.
*/

interface Props {
  turns: Turn[];
  intake: Intake;
  starting: boolean;
  streaming: boolean;
  stage: Stage | null;
  hasPlan: boolean;
  upload: UploadState;
  maxUploadMb: number;
  onSend: (message: string) => void;
  onStop: () => void;
  onUpload: (file: File) => void;
  onDismissUpload: () => void;
}

export function Conversation({
  turns,
  intake,
  starting,
  streaming,
  stage,
  hasPlan,
  upload,
  maxUploadMb,
  onSend,
  onStop,
  onUpload,
  onDismissUpload,
}: Props) {
  const scroll = useRef<HTMLDivElement>(null);
  const lastTurn = turns.at(-1);
  // Follow the stream, keyed on the tail so every token nudges the view.
  const tail = lastTurn && lastTurn.role === "assistant" ? lastTurn.text.length : turns.length;

  useEffect(() => {
    const element = scroll.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [tail]);

  // The assistant asks about one slot at a time; the checklist points at which.
  const asking = streaming || (lastTurn?.role === "assistant" && !hasPlan)
    ? askingSlot(intake)
    : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col px-6 pt-5">
      <IntakeChecklist intake={intake} asking={asking} />

      <div ref={scroll} className="min-h-0 flex-1 space-y-6 overflow-y-auto pb-6">
        {turns.length === 0 ? <FirstRun starting={starting} /> : null}
        {turns.map((turn) => (
          <ChatTurn key={turn.id} turn={turn} />
        ))}
      </div>

      <div className="shrink-0 pb-3">
        <SyllabusDrop
          disabled={starting || streaming}
          state={upload}
          maxUploadMb={maxUploadMb}
          onUpload={onUpload}
          onDismiss={onDismissUpload}
        />
      </div>

      <Composer
        disabled={starting}
        streaming={streaming}
        stage={stage}
        hasPlan={hasPlan}
        onSend={onSend}
        onStop={onStop}
      />
    </div>
  );
}

/*
  What this is, and what to type. Nothing is centred, nothing is illustrated,
  and the example is a real sentence a mentor could send verbatim -- an empty
  state that only says "start chatting" wastes the one screen where the mentor
  has no idea what shape of answer is wanted.
*/
function FirstRun({ starting }: { starting: boolean }) {
  return (
    <div className="pl-3">
      <span className="label mb-1 block text-ink-quiet">Course planner</span>
      <p className="body-lg max-w-[62ch] text-ink-soft">
        Describe the course you want to teach. The assistant asks four questions —
        subject, audience, duration, goals — then drafts modules, lesson topics,
        public resources and an assessment per module. Every line of the result is
        editable on the right.
      </p>
      <p className="datum mt-4 text-ink-quiet">
        {starting
          ? "Opening a session"
          : "Try: an 8-week intro to Python for adults with no coding background, two 90-minute evening sessions a week"}
      </p>
    </div>
  );
}
