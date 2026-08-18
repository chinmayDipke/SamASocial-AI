import type { SourceKind } from "./types";

/**
 * Per-source ink colours.
 *
 * The class strings are written out in full rather than composed at runtime:
 * Tailwind only generates classes it can see in the source.
 */
export const INK = {
  1: { text: "text-src-1", bg: "bg-src-1", softBg: "bg-src-1/12", border: "border-src-1" },
  2: { text: "text-src-2", bg: "bg-src-2", softBg: "bg-src-2/12", border: "border-src-2" },
  3: { text: "text-src-3", bg: "bg-src-3", softBg: "bg-src-3/12", border: "border-src-3" },
  4: { text: "text-src-4", bg: "bg-src-4", softBg: "bg-src-4/12", border: "border-src-4" },
  5: { text: "text-src-5", bg: "bg-src-5", softBg: "bg-src-5/12", border: "border-src-5" },
} as const;

export const KIND_LABEL: Record<SourceKind, string> = {
  pdf: "PDF",
  pptx: "slides",
  youtube: "video",
  web: "page",
};

/** What the locator means for each kind, used in hints and empty states. */
export const KIND_LOCATOR: Record<SourceKind, string> = {
  pdf: "page",
  pptx: "slide",
  youtube: "timestamp",
  web: "section",
};
