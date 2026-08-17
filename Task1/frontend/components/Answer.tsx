"use client";

import { useState } from "react";

import { KindGlyph } from "@/components/KindGlyph";
import { type Block, type Footnote, type Inline, inkFor, parseAnswer } from "@/lib/answer";
import { INK } from "@/lib/ink";
import type { Turn } from "@/lib/types";

type AssistantTurn = Extract<Turn, { role: "assistant" }>;

/**
 * An answer is rendered as a footnoted document: inline markers in the prose,
 * an apparatus underneath resolving each one to a source and a locator, and the
 * exact quoted passage one click away.
 */
export function Answer({ turn }: { turn: AssistantTurn }) {
  const [openFootnote, setOpenFootnote] = useState<number | null>(null);
  const { blocks, footnotes } = parseAnswer(turn.text, turn.citations, turn.streaming);

  const toggle = (number: number) => setOpenFootnote((current) => (current === number ? null : number));

  return (
    <article className="rise overflow-hidden rounded-[10px] border border-paper-edge bg-paper shadow-[0_1px_2px_rgba(0,0,0,0.35)]">
      <div className="px-5 pt-4 pb-1">
        {turn.stage === "retrieving" && turn.text === "" ? (
          <Searching />
        ) : (
          <div className="prose-answer">
            {blocks.map((block, index) => (
              <BlockView
                key={index}
                block={block}
                openFootnote={openFootnote}
                onToggle={toggle}
              />
            ))}
            {turn.streaming && <span className="caret" aria-hidden />}
          </div>
        )}

        {turn.error && (
          <p className="mt-3 rounded-md bg-bad/10 px-3 py-2 text-[13px] text-[#8f2020]">
            {turn.error}
          </p>
        )}
      </div>

      {footnotes.length > 0 && (
        <Apparatus footnotes={footnotes} openFootnote={openFootnote} onToggle={toggle} />
      )}

      {!turn.streaming && footnotes.length === 0 && turn.citations.length === 0 && !turn.error && (
        <p className="label border-t border-paper-edge px-5 py-2.5 text-prose-soft/70">
          {turn.outOfScope ? "outside the loaded material" : "no citation returned"}
        </p>
      )}
    </article>
  );
}

function Searching() {
  return (
    <p className="label flex items-center gap-2 py-1 text-prose-soft">
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((dot) => (
          <span
            key={dot}
            className="h-1 w-1 animate-pulse rounded-full bg-prose-soft"
            style={{ animationDelay: `${dot * 160}ms` }}
          />
        ))}
      </span>
      searching your sources
    </p>
  );
}

function BlockView({
  block,
  openFootnote,
  onToggle,
}: {
  block: Block;
  openFootnote: number | null;
  onToggle: (n: number) => void;
}) {
  const inlines = (parts: Inline[]) =>
    parts.map((part, index) => (
      <InlineView key={index} inline={part} active={openFootnote} onToggle={onToggle} />
    ));

  if (block.kind === "heading") {
    return <p className="mt-3 mb-1 font-display text-[1.05rem] font-semibold">{inlines(block.inlines)}</p>;
  }
  if (block.kind === "list") {
    const Tag = block.ordered ? "ol" : "ul";
    return (
      <Tag className={block.ordered ? "list-decimal" : "list-disc"}>
        {block.items.map((item, index) => (
          <li key={index} className="mt-1">
            {inlines(item)}
          </li>
        ))}
      </Tag>
    );
  }
  return <p>{inlines(block.inlines)}</p>;
}

function InlineView({
  inline,
  active,
  onToggle,
}: {
  inline: Inline;
  active: number | null;
  onToggle: (n: number) => void;
}) {
  switch (inline.kind) {
    case "text":
      return <>{inline.value}</>;
    case "bold":
      return <strong>{inline.value}</strong>;
    case "code":
      return <code>{inline.value}</code>;
    case "marker": {
      const { footnote } = inline;
      const ink = INK[inkFor(footnote.ref)];
      const isActive = active === footnote.number;
      return (
        <button
          type="button"
          onClick={() => onToggle(footnote.number)}
          aria-expanded={isActive}
          title={`${footnote.ref} — ${footnote.locator}`}
          className={`mx-px align-super font-mono text-[0.62em] font-medium transition-colors ${ink.text} ${
            isActive ? "underline" : "hover:underline"
          }`}
        >
          {footnote.number}
        </button>
      );
    }
  }
}

function Apparatus({
  footnotes,
  openFootnote,
  onToggle,
}: {
  footnotes: Footnote[];
  openFootnote: number | null;
  onToggle: (n: number) => void;
}) {
  return (
    <div className="border-t border-paper-edge bg-paper-edge/40 px-5 py-3">
      <ul className="flex flex-col gap-1.5">
        {footnotes.map((footnote) => {
          const ink = INK[inkFor(footnote.ref)];
          const citation = footnote.citation;
          const isOpen = openFootnote === footnote.number;

          return (
            <li key={footnote.number}>
              <button
                type="button"
                onClick={() => onToggle(footnote.number)}
                aria-expanded={isOpen}
                className="group flex w-full items-baseline gap-2 text-left"
              >
                <span className={`font-mono text-[10px] ${ink.text}`}>{footnote.number}</span>
                <span className={`label ${ink.text}`}>{footnote.ref}</span>
                <span className="font-mono text-[11px] text-prose-soft">{footnote.locator}</span>
                {citation && (
                  <span className="flex min-w-0 items-center gap-1.5 text-prose-soft/80">
                    <KindGlyph kind={citation.source_kind} className="h-3 w-3 shrink-0" />
                    <span className="truncate text-[12px] group-hover:underline">
                      {citation.source_title}
                    </span>
                  </span>
                )}
              </button>

              {isOpen && citation && (
                <blockquote
                  className={`mt-1.5 mb-1 border-l-2 pl-3 ${ink.border} font-display text-[13.5px] leading-[1.55] text-prose-soft`}
                >
                  {citation.quote.length > 520
                    ? `${citation.quote.slice(0, 520).trimEnd()}…`
                    : citation.quote}
                  {citation.url && (
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className={`label mt-1.5 block ${ink.text} hover:underline`}
                    >
                      open source ↗
                    </a>
                  )}
                </blockquote>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
