"use client";

import { useEffect, useRef } from "react";

import { Answer } from "@/components/Answer";
import type { Turn } from "@/lib/types";

interface Props {
  turns: Turn[];
  hasSources: boolean;
  onSuggestion: (question: string) => void;
}

const SUGGESTIONS = [
  "What are the main ideas here?",
  "Explain the hardest part in simple terms",
  "What should I revise first?",
];

export function Conversation({ turns, hasSources, onSuggestion }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const lastTurn = turns.at(-1);
  const streamingText = lastTurn?.role === "assistant" ? lastTurn.text : "";

  // Follow the answer as it streams, but never fight a user who scrolled up.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, streamingText]);

  if (turns.length === 0) {
    return <Opening hasSources={hasSources} onSuggestion={onSuggestion} />;
  }

  return (
    <div className="mx-auto flex w-full max-w-[42rem] flex-col gap-5 px-5 py-6">
      {turns.map((turn) =>
        turn.role === "user" ? (
          <Question key={turn.id} text={turn.text} />
        ) : (
          <Answer key={turn.id} turn={turn} />
        ),
      )}
      <div ref={endRef} />
    </div>
  );
}

function Question({ text }: { text: string }) {
  return (
    <div className="rise self-end max-w-[85%]">
      <p className="label mb-1 text-right text-quieter">you asked</p>
      <p className="rounded-[10px] border border-line bg-ink-850 px-3.5 py-2.5 font-mono text-[13px] leading-[1.55] text-bright">
        {text}
      </p>
    </div>
  );
}

function Opening({
  hasSources,
  onSuggestion,
}: {
  hasSources: boolean;
  onSuggestion: (question: string) => void;
}) {
  return (
    <div className="mx-auto flex h-full w-full max-w-[42rem] flex-col justify-center px-5 py-10">
      <p className="label text-quieter">grounded answers only</p>
      <h1 className="mt-3 font-display text-[2rem] leading-[1.15] text-bright">
        Ask your own material,
        <br />
        <span className="text-quiet">and see exactly where each answer came from.</span>
      </h1>
      <p className="mt-4 max-w-[30rem] text-[13.5px] leading-[1.65] text-quiet">
        Add a PDF, a slide deck, a lecture video or a web page. Every claim in an answer carries a
        footnote back to the page, slide, timestamp or section it came from. Ask about something the
        material does not cover and the assistant will say so rather than guess.
      </p>

      {hasSources ? (
        <div className="mt-7">
          <p className="label mb-2 text-quieter">try asking</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onSuggestion(suggestion)}
                className="control rounded-full border border-line px-3.5 py-1.5 text-quiet transition-colors hover:border-accent/60 hover:text-bright"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <p className="hint mt-7 text-quieter">Add a source to get started.</p>
      )}
    </div>
  );
}
