/** Mirrors the Pydantic models in backend/app/schemas.py. */

export type SourceKind = "pdf" | "pptx" | "youtube" | "web";
export type SourceStatus = "processing" | "ready" | "failed";

export interface Source {
  id: string;
  ref: string;
  kind: SourceKind;
  title: string;
  status: SourceStatus;
  url: string | null;
  chunk_count: number;
  summary: string | null;
  error: string | null;
  created_at: string;
}

export interface Citation {
  ref: string;
  source_id: string;
  source_title: string;
  source_kind: SourceKind;
  locator: string;
  quote: string;
  url: string | null;
}

export interface SessionInfo {
  session_id: string;
  created_at: string;
  sources: Source[];
  message_count: number;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  source_ref: string;
  locator: string;
}

export type Turn =
  | { role: "user"; id: string; text: string }
  | {
      role: "assistant";
      id: string;
      text: string;
      citations: Citation[];
      streaming: boolean;
      stage: "retrieving" | "generating" | "done";
      outOfScope: boolean;
      error?: string;
    };

/** One frame of the chat SSE stream. */
export type StreamFrame =
  | { event: "status"; data: { stage: "retrieving" | "generating"; chunks?: number; query?: string } }
  | { event: "token"; data: { text: string } }
  | { event: "citations"; data: { citations: Citation[] } }
  | { event: "done"; data: { out_of_scope?: boolean } }
  | { event: "error"; data: { detail: string } };
