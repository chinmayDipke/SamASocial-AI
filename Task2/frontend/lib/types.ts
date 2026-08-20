/** Mirrors the Pydantic models in backend/app/schemas.py. */

export type Level = "beginner" | "intermediate" | "advanced";
export type ResourceKind = "video" | "article" | "documentation" | "exercise";
export type AssessmentKind = "quiz" | "project" | "assignment";
export type LinkStatus = "verified" | "unreachable" | "unchecked";

export interface Resource {
  id: string;
  title: string;
  kind: ResourceKind;
  url: string;
  provider: string;
  note: string;
  link_status: LinkStatus;
}

export interface Lesson {
  id: string;
  title: string;
  summary: string;
  level: Level;
  duration_minutes: number;
  resources: Resource[];
}

export interface Assessment {
  title: string;
  kind: AssessmentKind;
  description: string;
}

export interface Module {
  id: string;
  title: string;
  objectives: string[];
  prerequisites: string[];
  lessons: Lesson[];
  assessment: Assessment | null;
}

export interface CoursePlan {
  title: string;
  subject: string;
  audience: string;
  duration: string;
  outcomes: string[];
  modules: Module[];
  version: number;
  updated_at: string;
}

export interface Intake {
  subject: string | null;
  audience: string | null;
  duration: string | null;
  goals: string[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  messages: ChatMessage[];
  intake: Intake;
  plan: CoursePlan | null;
}

/** What the backend is doing right now, as reported by a `status` frame. */
export type Stage = "thinking" | "drafting" | "refining" | "checking-links";

/**
 * How each stage is worded to the mentor.
 *
 * The `status` frame carries the backend's own `detail` line, but the wording a
 * mentor reads is the UI's decision and has to be the same sentence wherever it
 * appears -- the composer and the turn in flight can both be showing it at once.
 */
export const STAGE_LABEL: Record<Stage, string> = {
  thinking: "Reading your answer",
  drafting: "Drafting the plan",
  refining: "Revising the plan",
  "checking-links": "Checking resource links",
};

/** One frame of the chat SSE stream. */
export type StreamFrame =
  | { event: "status"; data: { stage: Stage; detail?: string } }
  | { event: "token"; data: { text: string } }
  | { event: "intake"; data: { intake: Intake } }
  | { event: "plan"; data: { plan: CoursePlan } }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { detail: string } };

/**
 * A conversation turn as the UI holds it.
 *
 * Wider than `ChatMessage`, because a turn in flight carries state the
 * transcript does not keep: which stage it is in, whether tokens are still
 * arriving, and the one-line note saying what it did to the plan.
 */
export type Turn =
  | { role: "user"; id: string; text: string; at: string | null }
  | {
      role: "assistant";
      id: string;
      text: string;
      at: string | null;
      streaming: boolean;
      stage: Stage | "done";
      /** e.g. `ADDED MODULE 03` -- plain text under the turn, never a toast. */
      note: string | null;
      error: string | null;
    };
