"use client";

import { useState } from "react";

import { KindGlyph } from "@/components/KindGlyph";
import { inkFor } from "@/lib/answer";
import { INK, KIND_LABEL } from "@/lib/ink";
import type { Source } from "@/lib/types";

export function SourceCard({ source }: { source: Source }) {
  const [showSummary, setShowSummary] = useState(false);
  const ink = INK[inkFor(source.ref)];
  const summaryId = `summary-${source.id}`;

  return (
    <li className="rise overflow-hidden rounded-[10px] border border-line-soft bg-ink-850">
      {/* The ink bar is the source's identity; its citations carry the same colour. */}
      <div
        className={`h-[3px] ${ink.bg} ${source.status === "ready" ? "settle" : "opacity-40"}`}
      />

      <div className="p-3">
        <div className="flex items-start gap-2.5">
          <span className={`label mt-px shrink-0 font-medium ${ink.text}`}>{source.ref}</span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] leading-5 font-medium text-bright" title={source.title}>
              {source.title}
            </p>

            <div className="mt-1 flex items-center gap-2 text-quieter">
              <KindGlyph kind={source.kind} className="h-3.5 w-3.5" />
              <span className="label">{KIND_LABEL[source.kind]}</span>
              <Status source={source} />
            </div>
          </div>
        </div>

        {source.error && (
          <p className="mt-2.5 border-l-2 border-bad/60 pl-2.5 text-[12px] leading-[1.45] break-words text-bad/90">
            {source.error}
          </p>
        )}

        {source.summary && (
          <>
            <button
              type="button"
              onClick={() => setShowSummary((open) => !open)}
              aria-expanded={showSummary}
              aria-controls={summaryId}
              className="hint mt-2.5 text-quieter underline decoration-line underline-offset-2 transition-colors hover:text-quiet"
            >
              {showSummary ? "Hide summary" : "Summary"}
            </button>
            {showSummary && (
              <div
                id={summaryId}
                className="mt-2 space-y-1 border-l border-line pl-2.5 text-[12px] leading-[1.5] text-quiet"
              >
                {source.summary
                  .split("\n")
                  .map((line) => line.replace(/^[-*]\s*/, "").trim())
                  .filter(Boolean)
                  .map((line, index) => (
                    <p key={index}>{line}</p>
                  ))}
              </div>
            )}
          </>
        )}
      </div>
    </li>
  );
}

function Status({ source }: { source: Source }) {
  if (source.status === "processing") {
    return (
      <span className="label flex items-center gap-1.5 text-warn/90">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warn" />
        reading
      </span>
    );
  }
  if (source.status === "failed") {
    return <span className="label text-bad/90">could not read</span>;
  }
  return (
    <span className="label text-quieter">
      {source.chunk_count} {source.chunk_count === 1 ? "passage" : "passages"}
    </span>
  );
}
