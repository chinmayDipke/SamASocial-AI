"use client";

import { useEffect, useRef } from "react";

import { Answer } from "@/components/Answer";
import { AiAssistantCard } from "@/components/ui/ai-assistant-card";
import type { Turn } from "@/lib/types";

interface Props {
  turns: Turn[];
  /** Titles of indexed sources, shown in the welcome card. */
  sourceTitles: string[];
  indexing: boolean;
  onSuggestion: (question: string) => void;
  onAddSource: (input: { url?: string; file?: File }) => void;
}

export function Conversation({
  turns,
  sourceTitles,
  indexing,
  onSuggestion,
  onAddSource,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const lastTurn = turns.at(-1);
  const streamingText = lastTurn?.role === "assistant" ? lastTurn.text : "";

  // Follow the answer as it streams, but never fight a user who scrolled up.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length, streamingText]);

  if (turns.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-5 py-10">
        <AiAssistantCard
          sourceTitles={sourceTitles}
          indexing={indexing}
          onAsk={onSuggestion}
          onAddSource={onAddSource}
        />
      </div>
    );
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
    <div className="rise max-w-[85%] self-end">
      <p className="label mb-1 text-right text-quieter">you asked</p>
      <p className="rounded-[10px] border border-line bg-ink-850 px-3.5 py-2.5 font-mono text-[13px] leading-[1.55] text-bright">
        {text}
      </p>
    </div>
  );
}
