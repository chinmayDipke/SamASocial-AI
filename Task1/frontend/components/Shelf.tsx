"use client";

import { SourceCard } from "@/components/SourceCard";
import { type ChatRecord, describeWhen } from "@/lib/history";
import type { Source, Turn } from "@/lib/types";

interface Props {
  sources: Source[];
  readyCount: number;
  quizLoading: boolean;
  turns: Turn[];
  chats: ChatRecord[];
  currentChatId: string;
  viewingChatId: string | null;
  onJumpToTurn: (id: string) => void;
  onOpenChat: (id: string) => void;
  onNewChat: () => void;
  onQuiz: () => void;
}

export function Shelf({
  sources,
  readyCount,
  quizLoading,
  turns,
  chats,
  currentChatId,
  viewingChatId,
  onJumpToTurn,
  onOpenChat,
  onNewChat,
  onQuiz,
}: Props) {
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      {/*
        The source list only exists once there is a source. An empty panel
        headed "on the shelf — empty" was pure furniture: the welcome card in
        the middle already says what to do first.
      */}
      {sources.length > 0 && (
        <>
          <div className="flex items-baseline justify-between">
            <h2 className="label text-quiet">on the shelf</h2>
            <span className="label text-quieter">{readyCount} ready</span>
          </div>
          <ul className="flex flex-col gap-2">
            {sources.map((source) => (
              <SourceCard key={source.id} source={source} />
            ))}
          </ul>
        </>
      )}

      <ChatList
        separated={sources.length > 0}
        turns={turns}
        chats={chats}
        currentChatId={currentChatId}
        viewingChatId={viewingChatId}
        onJump={onJumpToTurn}
        onOpenChat={onOpenChat}
        onNewChat={onNewChat}
      />

      {readyCount > 0 && (
        <button
          type="button"
          onClick={onQuiz}
          disabled={quizLoading}
          className="control mt-auto rounded-md border border-line bg-ink-850 px-3 py-2.5 text-quiet transition-colors hover:border-accent/60 hover:text-bright disabled:opacity-50"
        >
          {quizLoading ? "Writing questions…" : "Quiz me on this"}
        </button>
      )}
    </div>
  );
}

/**
 * Every chat, this one first.
 *
 * The live chat expands into its questions, each a jump link to that answer.
 * Earlier chats are saved transcripts (see lib/history.ts) and open read-only,
 * because the index they were answered from died with their session.
 */
function ChatList({
  separated,
  turns,
  chats,
  currentChatId,
  viewingChatId,
  onJump,
  onOpenChat,
  onNewChat,
}: {
  /** Whether a source list sits above, and so needs a rule between. */
  separated: boolean;
  turns: Turn[];
  chats: ChatRecord[];
  currentChatId: string;
  viewingChatId: string | null;
  onJump: (id: string) => void;
  onOpenChat: (id: string) => void;
  onNewChat: () => void;
}) {
  const questions = turns.filter((turn) => turn.role === "user");
  const earlier = chats.filter((chat) => chat.id !== currentChatId);
  const hasHistory = questions.length > 0 || earlier.length > 0;

  if (!hasHistory) return null;

  const readingCurrent = viewingChatId === null;

  return (
    <div
      className={`flex min-h-0 flex-col ${
        separated ? "mt-2 border-t border-line-soft pt-3" : ""
      }`}
    >
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="label text-quiet">chats</h2>
        <button
          type="button"
          onClick={onNewChat}
          title="Start a fresh chat. The current sources are cleared with it."
          className="control text-quieter transition-colors hover:text-accent"
        >
          + New
        </button>
      </div>

      <div className="flex min-h-0 flex-col gap-0.5 overflow-y-auto">
        {questions.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => onOpenChat(currentChatId)}
              className={`flex items-baseline gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-ink-850 ${
                readingCurrent ? "text-bright" : "text-quiet"
              }`}
            >
              <span className="label text-accent">now</span>
              <span className="truncate text-[12.5px]">This chat</span>
            </button>

            <ol className="mb-1 flex flex-col gap-0.5 border-l border-line-soft pl-2">
              {questions.map((turn, index) => (
                <li key={turn.id}>
                  <button
                    type="button"
                    onClick={() => onJump(turn.id)}
                    title={turn.text}
                    className="flex w-full gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-ink-850"
                  >
                    <span className="label mt-px shrink-0 text-quieter">{index + 1}</span>
                    <span className="line-clamp-2 text-[12.5px] leading-[1.45] text-quiet">
                      {turn.text}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </>
        )}

        {earlier.map((chat) => (
          <button
            key={chat.id}
            type="button"
            onClick={() => onOpenChat(chat.id)}
            title={chat.title}
            className={`flex w-full flex-col gap-0.5 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-ink-850 ${
              viewingChatId === chat.id ? "bg-ink-850" : ""
            }`}
          >
            <span
              className={`line-clamp-2 text-[12.5px] leading-[1.45] ${
                viewingChatId === chat.id ? "text-bright" : "text-quiet"
              }`}
            >
              {chat.title}
            </span>
            <span className="label text-quieter">
              {describeWhen(chat.savedAt)} · {countQuestions(chat)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function countQuestions(chat: ChatRecord): string {
  const asked = chat.turns.filter((turn) => turn.role === "user").length;
  return asked === 1 ? "1 question" : `${asked} questions`;
}
