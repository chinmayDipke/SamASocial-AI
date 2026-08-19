"use client";

import { SourceCard } from "@/components/SourceCard";
import type { Source } from "@/lib/types";

interface Props {
  sources: Source[];
  readyCount: number;
  quizLoading: boolean;
  onQuiz: () => void;
}

export function Shelf({ sources, readyCount, quizLoading, onQuiz }: Props) {
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
