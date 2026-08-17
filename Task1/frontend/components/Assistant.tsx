"use client";

import { useState } from "react";

import { Composer } from "@/components/Composer";
import { Conversation } from "@/components/Conversation";
import { QuizPanel } from "@/components/QuizPanel";
import { Shelf } from "@/components/Shelf";
import { useAssistant } from "@/hooks/useAssistant";

export function Assistant() {
  const assistant = useAssistant();
  const [shelfOpen, setShelfOpen] = useState(false);

  const hasReadySource = assistant.readySources.length > 0;
  const indexing = assistant.sources.some((source) => source.status === "processing");

  const placeholder = hasReadySource
    ? "Ask about your material"
    : indexing
      ? "Reading your source…"
      : "Add a source to start asking";

  const ask = (message: string) => {
    setShelfOpen(false);
    void assistant.ask(message);
  };

  return (
    <div className="flex h-dvh flex-col bg-ink-950">
      <header className="flex items-center justify-between gap-3 border-b border-line-soft px-4 py-3">
        <div className="flex items-baseline gap-2.5">
          <span className="font-display text-[15px] text-bright">Study Assistant</span>
          <span className="label hidden text-quieter sm:inline">answers only from what you load</span>
        </div>

        <button
          type="button"
          onClick={() => setShelfOpen((open) => !open)}
          aria-expanded={shelfOpen}
          className="control rounded-md border border-line px-3 py-1.5 text-quiet transition-colors hover:text-bright lg:hidden"
        >
          Sources ({assistant.sources.length})
        </button>
      </header>

      {assistant.notice && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 border-b border-bad/30 bg-bad/10 px-4 py-2.5"
        >
          <p className="text-[13px] leading-[1.5] text-bad">{assistant.notice.text}</p>
          <button
            type="button"
            onClick={assistant.dismissNotice}
            className="control shrink-0 text-bad/80 hover:text-bad"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid min-h-0 flex-1 lg:grid-cols-[19rem_1fr]">
        <aside
          className={`min-h-0 border-line-soft bg-ink-900 lg:block lg:border-r ${
            shelfOpen
              ? "absolute inset-x-0 top-[57px] bottom-0 z-10 block border-b"
              : "hidden"
          }`}
        >
          <Shelf
            sources={assistant.sources}
            readyCount={assistant.readySources.length}
            disabled={assistant.starting || !assistant.sessionId}
            quizLoading={assistant.quizLoading}
            onAdd={(input) => void assistant.addSource(input)}
            onQuiz={() => void assistant.startQuiz()}
          />
        </aside>

        <main className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <Conversation
              turns={assistant.turns}
              hasSources={hasReadySource}
              onSuggestion={ask}
            />
          </div>

          <Composer
            disabled={!hasReadySource || assistant.starting}
            streaming={assistant.streaming}
            placeholder={placeholder}
            onSend={ask}
            onStop={assistant.stop}
          />
        </main>
      </div>

      {assistant.quiz && (
        <QuizPanel questions={assistant.quiz} onClose={assistant.closeQuiz} />
      )}
    </div>
  );
}
