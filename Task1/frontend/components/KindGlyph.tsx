import type { SourceKind } from "@/lib/types";

/** Small line glyphs per source kind: a page, a deck, a play head, a browser bar. */
export function KindGlyph({ kind, className = "" }: { kind: SourceKind; className?: string }) {
  const common = {
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.25,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: `h-4 w-4 ${className}`,
    "aria-hidden": true,
  };

  switch (kind) {
    case "pdf":
      return (
        <svg {...common}>
          <path d="M4 1.75h5L12.25 5v9.25H4z" />
          <path d="M9 1.75V5h3.25M6 8.5h4M6 11h3" />
        </svg>
      );
    case "pptx":
      return (
        <svg {...common}>
          <rect x="2" y="3" width="12" height="8.5" rx="1" />
          <path d="M8 11.5v2.75M5.5 14.25h5" />
        </svg>
      );
    case "youtube":
      return (
        <svg {...common}>
          <rect x="1.75" y="3.25" width="12.5" height="9.5" rx="2.5" />
          <path d="M7 6.5l3 1.75L7 10z" />
        </svg>
      );
    case "web":
      return (
        <svg {...common}>
          <rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.5" />
          <path d="M1.75 6h12.5M4 4.4h.01M6 4.4h.01" />
        </svg>
      );
  }
}
