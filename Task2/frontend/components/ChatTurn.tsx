"use client";

import { STAGE_LABEL, type Turn } from "@/lib/types";

/*
  No bubbles, no avatars, no alternating alignment. Both speakers are flush-left
  blocks 24px apart; only the mentor's turns carry the 2px accent margin rule,
  because their words are the source material the plan is built from.

  A turn that changed the plan says so in one mono line -- `ADDED MODULE 03` --
  rather than firing a toast at the corner of the screen.
*/

export function ChatTurn({ turn }: { turn: Turn }) {
  const time = turn.at ? formatTime(turn.at) : null;

  if (turn.role === "user") {
    return (
      <article className="group relative -ml-[2px] border-l-2 border-accent pl-3">
        <span className="label mb-1 block text-accent">You</span>
        <Paragraphs text={turn.text} className="body max-w-[62ch] text-ink" />
        {time ? <Timestamp time={time} /> : null}
      </article>
    );
  }

  const waiting = turn.streaming && turn.text === "";

  return (
    <article className="group relative pl-3">
      <span className="label mb-1 block text-ink-quiet">Assistant</span>

      {waiting ? (
        <p className="datum text-ink-quiet">
          {turn.stage === "done" ? "Working" : STAGE_LABEL[turn.stage]}
          <span className="caret" aria-hidden />
        </p>
      ) : (
        <Paragraphs
          text={turn.text}
          className="body-lg max-w-[62ch] text-ink-soft"
          caret={turn.streaming}
        />
      )}

      {turn.note ? <p className="datum mt-2 text-ink-quiet">{turn.note}</p> : null}
      {turn.error ? <p className="body mt-2 max-w-[62ch] text-danger">{turn.error}</p> : null}
      {time ? <Timestamp time={time} /> : null}
    </article>
  );
}

/** Timestamps are answerable but not worth the ink until asked for. */
function Timestamp({ time }: { time: string }) {
  return (
    <span className="datum absolute top-0 right-0 text-ink-faint opacity-0 transition-opacity duration-100 group-hover:opacity-100">
      {time}
    </span>
  );
}

function Paragraphs({
  text,
  className,
  caret = false,
}: {
  text: string;
  className: string;
  caret?: boolean;
}) {
  const paragraphs = text.split(/\n{2,}/);
  return (
    <div className={`message-body ${className}`}>
      {paragraphs.map((paragraph, index) => (
        <p key={index}>
          {paragraph}
          {/* The caret is the only thing that moves while tokens arrive. */}
          {caret && index === paragraphs.length - 1 ? (
            <span className="caret" aria-hidden />
          ) : null}
        </p>
      ))}
    </div>
  );
}

function formatTime(iso: string): string | null {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return null;
  return at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
