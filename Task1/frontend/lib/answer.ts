/**
 * Turn a streamed answer into a footnoted document.
 *
 * The model cites inline as `[S1 | page 4]`. Rather than leaving those brackets
 * in the prose, they are lifted out into numbered footnote markers with an
 * apparatus underneath -- which is what a grounded answer actually is. Each
 * distinct ref+locator pair gets one number, in order of first appearance.
 */

import type { Citation } from "./types";

export interface Footnote {
  number: number;
  ref: string;
  locator: string;
  citation?: Citation;
}

export type Inline =
  | { kind: "text"; value: string }
  | { kind: "bold"; value: string }
  | { kind: "code"; value: string }
  | { kind: "marker"; footnote: Footnote };

export type Block =
  | { kind: "paragraph"; inlines: Inline[] }
  | { kind: "heading"; inlines: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "rule" };

export interface ParsedAnswer {
  blocks: Block[];
  footnotes: Footnote[];
}

// Citation, bold, or inline code -- matched in one pass so offsets stay correct.
const INLINE_RE = /\[(S\d+)\s*\|\s*([^\]\n]{1,80})\]|\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;
// A citation that is still being typed, e.g. "[S1 | pa" at the end of the stream.
const PARTIAL_MARKER_RE = /\[S?\d*\s*\|?[^\]\n]{0,80}$/;
const UNORDERED_RE = /^\s*[-*•]\s+/;
const ORDERED_RE = /^\s*\d+[.)]\s+/;
const HEADING_RE = /^\s*#{1,4}\s+/;
// A markdown horizontal rule: --- , *** or ___
const RULE_RE = /^\s*([-*_])\1{2,}\s*$/;

/** Assign one of five source inks from the source ref, so colours are stable. */
export function inkFor(ref: string): 1 | 2 | 3 | 4 | 5 {
  const index = Number.parseInt(ref.replace(/\D/g, ""), 10);
  if (!Number.isFinite(index) || index < 1) return 1;
  return (((index - 1) % 5) + 1) as 1 | 2 | 3 | 4 | 5;
}

export function parseAnswer(
  text: string,
  citations: Citation[],
  streaming = false,
): ParsedAnswer {
  // While streaming, hide a half-typed citation instead of flashing raw brackets.
  const source = streaming ? text.replace(PARTIAL_MARKER_RE, "") : text;

  const footnotes: Footnote[] = [];
  const seen = new Map<string, Footnote>();

  const footnoteFor = (ref: string, locator: string): Footnote => {
    const key = `${ref}|${locator}`;
    const existing = seen.get(key);
    if (existing) return existing;

    const footnote: Footnote = {
      number: footnotes.length + 1,
      ref,
      locator,
      citation:
        citations.find((c) => c.ref === ref && c.locator === locator) ??
        citations.find((c) => c.ref === ref),
    };
    seen.set(key, footnote);
    footnotes.push(footnote);
    return footnote;
  };

  const blocks: Block[] = [];
  const lines = source.split("\n");

  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ kind: "paragraph", inlines: tokenize(paragraph.join(" "), footnoteFor) });
    paragraph = [];
  };

  const flushList = () => {
    if (!list) return;
    blocks.push({
      kind: "list",
      ordered: list.ordered,
      items: list.items.map((item) => tokenize(item, footnoteFor)),
    });
    list = null;
  };

  for (const line of lines) {
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    if (RULE_RE.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({ kind: "rule" });
      continue;
    }

    if (HEADING_RE.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({
        kind: "heading",
        inlines: tokenize(line.replace(HEADING_RE, ""), footnoteFor),
      });
      continue;
    }

    const ordered = ORDERED_RE.test(line);
    if (ordered || UNORDERED_RE.test(line)) {
      flushParagraph();
      const item = line.replace(ordered ? ORDERED_RE : UNORDERED_RE, "");
      if (list && list.ordered === ordered) {
        list.items.push(item);
      } else {
        flushList();
        list = { ordered, items: [item] };
      }
      continue;
    }

    flushList();
    paragraph.push(line.trim());
  }

  flushParagraph();
  flushList();

  return { blocks, footnotes };
}

function tokenize(
  text: string,
  footnoteFor: (ref: string, locator: string) => Footnote,
): Inline[] {
  const inlines: Inline[] = [];
  let cursor = 0;

  for (const match of text.matchAll(INLINE_RE)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      inlines.push({ kind: "text", value: text.slice(cursor, start) });
    }

    const [full, ref, locator, bold, code] = match;
    if (ref && locator) {
      inlines.push({ kind: "marker", footnote: footnoteFor(ref, locator.trim()) });
    } else if (bold) {
      inlines.push({ kind: "bold", value: bold });
    } else if (code) {
      inlines.push({ kind: "code", value: code });
    }
    cursor = start + full.length;
  }

  if (cursor < text.length) {
    inlines.push({ kind: "text", value: text.slice(cursor) });
  }
  return inlines;
}
