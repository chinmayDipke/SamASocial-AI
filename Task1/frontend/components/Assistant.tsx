"use client";

import { useState } from "react";

import { Composer } from "@/components/Composer";
import { Conversation } from "@/components/Conversation";
import { QuizPanel } from "@/components/QuizPanel";
import { Shelf } from "@/components/Shelf";
import { useAssistant } from "@/hooks/useAssistant";
import { describeWhen } from "@/lib/history";

export function Assistant() {
  const assistant = useAssistant();
  const [shelfOpen, setShelfOpen] = useState(false);

  const hasReadySource = assistant.readySources.length > 0;
  const indexing = assistant.sources.some((source) => source.status === "processing");

  const placeholder = hasReadySource
    ? "Ask about your material, or paste a link to add another source"
    : indexing
      ? "Reading your source…"
      : "Paste a YouTube or article link, or attach a PDF";

  const viewing = assistant.viewingChat;

  const jumpToTurn = (id: string) => {
    setShelfOpen(false);
    assistant.closeChat();
    // If a saved chat was on screen, the live turns are rendered on the next
    // frame -- scrolling before that would look for an element that isn't there.
    requestAnimationFrame(() =>
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }),
    );
  };

  const ask = (message: string) => {
    setShelfOpen(false);
    assistant.closeChat();
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
            quizLoading={assistant.quizLoading}
            turns={assistant.turns}
            chats={assistant.chats}
            currentChatId={assistant.currentChatId}
            viewingChatId={viewing?.id ?? null}
            onJumpToTurn={jumpToTurn}
            onOpenChat={(id) => {
              setShelfOpen(false);
              assistant.openChat(id);
            }}
            onNewChat={() => {
              setShelfOpen(false);
              void assistant.newChat();
            }}
            onQuiz={() => void assistant.startQuiz()}
          />
        </aside>

        <main className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <Conversation
              turns={viewing ? viewing.turns : assistant.turns}
              sourceTitles={assistant.readySources.map((source) => source.title)}
              indexing={indexing}
              onSuggestion={ask}
            />
          </div>

          {viewing ? (
            /*
              A saved transcript, not a session. The index it was answered from
              died with its server session, so asking here is not offered --
              the way back to a live chat is explicit instead.
            */
            <div className="flex items-center justify-between gap-3 border-t border-line-soft bg-ink-900 px-4 py-3">
              <p className="hint text-quieter">
                Saved chat from {describeWhen(viewing.savedAt)}. Read-only — its sources were
                released when that session ended.
              </p>
              <button
                type="button"
                onClick={assistant.closeChat}
                className="control shrink-0 rounded-md border border-line px-3 py-1.5 text-quiet transition-colors hover:border-accent/60 hover:text-bright"
              >
                Back to this chat
              </button>
            </div>
          ) : (
            <Composer
              disabled={assistant.starting || !assistant.sessionId}
              hasSource={hasReadySource}
              streaming={assistant.streaming}
              placeholder={placeholder}
              model={assistant.model}
              models={assistant.models}
              onModelChange={assistant.chooseModel}
              onSend={ask}
              onAddUrl={(url) => void assistant.addSource({ url })}
              onStop={assistant.stop}
              onAttach={(file) => void assistant.addSource({ file })}
            />
          )}
        </main>
      </div>

      {assistant.quiz && (
        <QuizPanel questions={assistant.quiz} onClose={assistant.closeQuiz} />
      )}
    </div>
  );
}
