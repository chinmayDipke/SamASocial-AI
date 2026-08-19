"use client";

import { SourceCard } from "@/components/SourceCard";
import type { Source, Turn } from "@/lib/types";

interface Props {
  sources: Source[];
  readyCount: number;
  quizLoading: boolean;
  turns: Turn[];
  onJumpToTurn: (id: string) => void;
  onQuiz: () => void;
}

export function Shelf({
  sources,
  readyCount,
  quizLoading,
  turns,
  onJumpToTurn,
  onQuiz,
}: Props) {
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="label text-quiet">on the shelf</h2>
        <span className="label text-quieter">{sources.length ? `${readyCount} ready` : "empty"}</span>
      </div>

      {sources.length === 0 ? (
        <p className="hint mt-1 text-quieter">
          Paste a link or attach a file in the box below. Anything you add is the only thing the
          assistant may answer from.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {sources.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </ul>
      )}

      <ChatHistory turns={turns} onJump={onJumpToTurn} />

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
 * The questions asked in this session, newest last, as a jump list.
 *
 * Sessions live in memory, so this is deliberately the current conversation
 * rather than a cross-session archive — it is a way back to an earlier answer,
 * which is what you actually want while studying.
 */
function ChatHistory({
  turns,
  onJump,
}: {
  turns: Turn[];
  onJump: (id: string) => void;
}) {
  const questions = turns.filter((turn) => turn.role === "user");
  if (questions.length === 0) return null;

  return (
    <div className="mt-4 flex min-h-0 flex-col border-t border-line-soft pt-3">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="label text-quiet">this chat</h2>
        <span className="label text-quieter">
          {questions.length === 1 ? "1 question" : `${questions.length} questions`}
        </span>
      </div>

      <ol className="flex flex-col gap-0.5 overflow-y-auto">
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
    </div>
  );
}
