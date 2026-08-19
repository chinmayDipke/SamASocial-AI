"use client";

import {
  BookOpenIcon,
  ListChecksIcon,
  Loader2Icon,
  ScanTextIcon,
  SparklesIcon,
  WandSparklesIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * The welcome state, adapted from the shadcn "AI assistant card" reference.
 *
 * The reference is a static mockup — a GPT-4 picker, a microphone button and
 * "Create image" chips that do nothing. Everything here is wired: each chip
 * sends a real question, and the chips are disabled until a source is indexed,
 * because the assistant genuinely cannot answer before then.
 */

interface Suggestion {
  label: string;
  question: string;
  icon: typeof ScanTextIcon;
  tone: string;
}

const SUGGESTIONS: Suggestion[] = [
  {
    label: "Summarise it",
    question: "What are the main ideas covered in this material?",
    icon: ScanTextIcon,
    tone: "text-src-1",
  },
  {
    label: "Explain simply",
    question: "Explain the hardest part in simple terms, as if I am new to this.",
    icon: SparklesIcon,
    tone: "text-src-5",
  },
  {
    label: "What to revise",
    question: "What should I revise first, and why?",
    icon: ListChecksIcon,
    tone: "text-src-2",
  },
  {
    label: "Give an example",
    question: "Give me a concrete example from the material.",
    icon: WandSparklesIcon,
    tone: "text-src-3",
  },
  {
    label: "Key terms",
    question: "Define the key terms I need to know from this material.",
    icon: BookOpenIcon,
    tone: "text-src-4",
  },
];

interface Props {
  /** Titles of the sources that are indexed and answerable. */
  sourceTitles: string[];
  /** True while any source is still being processed. */
  indexing: boolean;
  onAsk: (question: string) => void;
}

export function AiAssistantCard({ sourceTitles, indexing, onAsk }: Props) {
  const ready = sourceTitles.length > 0;

  return (
    <Card className="w-full max-w-[540px] border-line-soft bg-ink-900/60 shadow-none">
      <CardContent className="flex flex-col items-center gap-7 p-8">
        <AssistantMark />

        <div className="flex flex-col gap-2 text-center">
          <h1 className="font-display text-[1.6rem] leading-tight text-bright">
            Ask your own material
          </h1>
          <p className="mx-auto max-w-[38ch] text-[13.5px] leading-[1.6] text-quiet">
            {ready
              ? "Every claim in an answer carries a footnote back to the page, slide, timestamp or section it came from."
              : "Add a PDF, a slide deck, a lecture video or a web page. The assistant answers only from what you load, and says so when your material does not cover something."}
          </p>
        </div>

        {indexing && !ready && (
          <p className="label flex items-center gap-2 text-warn/90">
            <Loader2Icon aria-hidden className="size-3.5 animate-spin" />
            reading your source
          </p>
        )}

        {ready ? (
          <>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {SUGGESTIONS.map(({ label, question, icon: Icon, tone }) => (
                <Badge
                  key={label}
                  variant="secondary"
                  role="button"
                  tabIndex={0}
                  onClick={() => onAsk(question)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onAsk(question);
                    }
                  }}
                  title={question}
                  className={cn(
                    "h-7 min-w-7 cursor-pointer gap-1.5 rounded-md text-xs font-medium",
                    "bg-ink-800 text-quiet transition-colors hover:bg-ink-700 hover:text-bright",
                    "[&_svg]:-ms-px [&_svg]:size-3.5 [&_svg]:shrink-0",
                  )}
                >
                  <Icon aria-hidden="true" className={tone} />
                  {label}
                </Badge>
              ))}
            </div>

            <p className="label text-center text-quieter">
              answering from{" "}
              {sourceTitles.length === 1
                ? truncate(sourceTitles[0])
                : `${sourceTitles.length} sources`}
            </p>
          </>
        ) : (
          <p className="label text-quieter">paste a link below to begin</p>
        )}
      </CardContent>
    </Card>
  );
}

function truncate(value: string, max = 42) {
  return value.length > max ? `${value.slice(0, max).trimEnd()}…` : value;
}

/** The gradient mark from the reference component. */
function AssistantMark() {
  return (
    <svg
      fill="none"
      height="48"
      viewBox="0 0 48 48"
      width="48"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="mark-sheen" gradientUnits="userSpaceOnUse" x1="24" x2="26" y1="0" y2="48">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#fff" stopOpacity=".12" />
        </linearGradient>
        <linearGradient id="mark-star" gradientUnits="userSpaceOnUse" x1="24" x2="24" y1="6" y2="42">
          <stop offset="0" stopColor="#fff" stopOpacity=".9" />
          <stop offset="1" stopColor="#fff" stopOpacity=".55" />
        </linearGradient>
        <linearGradient id="mark-edge" gradientUnits="userSpaceOnUse" x1="24" x2="24" y1="0" y2="48">
          <stop offset="0" stopColor="#fff" stopOpacity=".14" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <clipPath id="mark-clip">
          <rect height="48" rx="12" width="48" />
        </clipPath>
      </defs>
      <g clipPath="url(#mark-clip)">
        <rect fill="#0A0D12" height="48" rx="12" width="48" />
        <path d="m0 0h48v48h-48z" fill="url(#mark-sheen)" />
        <path
          clipRule="evenodd"
          d="m6 24c11.4411 0 18-6.5589 18-18 0 11.4411 6.5589 18 18 18-11.4411 0-18 6.5589-18 18 0-11.4411-6.5589-18-18-18z"
          fill="url(#mark-star)"
          fillRule="evenodd"
        />
      </g>
      <rect height="46" rx="11" stroke="url(#mark-edge)" strokeWidth="2" width="46" x="1" y="1" />
    </svg>
  );
}
