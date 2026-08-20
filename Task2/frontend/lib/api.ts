import type { CoursePlan, SessionInfo, StreamFrame } from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /**
     * The parsed error body, when the server sent one.
     *
     * Kept because one failure needs more than a sentence to recover from: a 409
     * from the plan endpoint carries the plan the server now holds, and that is
     * the only thing that lets the UI show the mentor what their edit collided
     * with instead of guessing.
     */
    readonly body: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Every call to the backend goes through here.
 *
 * Two failures look nothing alike to a user and are easy to conflate in code: a
 * backend that is not running (`fetch` rejects with a bare TypeError, which says
 * "Failed to fetch" and nothing about what to do) and a backend that answered
 * with a reason. Both become an `ApiError` carrying a sentence worth reading.
 */
async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch (error: unknown) {
    // An abort is the mentor pressing Stop, not a broken service.
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      `Cannot reach the planning service at ${BASE_URL}. Check that the backend is running.`,
      0,
    );
  }
  if (!response.ok) {
    throw await failure(response);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function failure(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    /* a non-JSON error body is still a failure worth reporting */
  }
  return new ApiError(detailOf(body, response.status), response.status, body);
}

/** The backend writes `detail` for the mentor, so it beats anything we could say. */
function detailOf(body: unknown, status: number): string {
  const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : null;
  if (typeof detail === "string") return detail;
  // FastAPI reports request-validation problems as an array of field errors.
  if (Array.isArray(detail)) return "That request was not valid.";
  return `The request failed (HTTP ${status}).`;
}

export interface Health {
  status: string;
  provider: string;
  chat_model: string;
  llm_key_configured: boolean;
  max_upload_mb: number;
  verify_links: boolean;
}

/** A plan file the browser can save, with the name the server chose for it. */
export interface PlanDownload {
  blob: Blob;
  filename: string;
}

export const api = {
  health: () => request<Health>("/api/health"),

  createSession: () => request<SessionInfo>("/api/sessions", { method: "POST" }),

  getSession: (sessionId: string) => request<SessionInfo>(`/api/sessions/${sessionId}`),

  /** Hand back an abandoned session's memory instead of waiting out its TTL. */
  deleteSession: (sessionId: string) =>
    request<void>(`/api/sessions/${sessionId}`, { method: "DELETE" }),

  /** Persist a mentor's inline edits. The server bumps `version` and echoes the plan back. */
  savePlan: (sessionId: string, plan: CoursePlan) =>
    request<CoursePlan>(`/api/sessions/${sessionId}/plan`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    }),

  uploadSyllabus: (sessionId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<SessionInfo>(`/api/sessions/${sessionId}/syllabus`, { method: "POST", body });
  },

  /**
   * Fetch the export as bytes rather than pointing an anchor at the URL.
   *
   * A bare link would navigate on any error, replacing the app with a JSON error
   * page; this way a failed export surfaces as an ApiError like everything else,
   * and the caller still gets the server's `Content-Disposition` filename.
   */
  exportPlan: async (sessionId: string): Promise<PlanDownload> => {
    const response = await send(`/api/sessions/${sessionId}/plan/export`);
    return {
      blob: await response.blob(),
      filename: filenameFrom(response.headers.get("Content-Disposition")),
    };
  },
};

function filenameFrom(disposition: string | null): string {
  const match = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match ? decodeURIComponent(match[1]) : "course-plan.json";
}

/**
 * Stream one turn of the planning conversation.
 *
 * The request carries a JSON body, which `EventSource` cannot do, so the SSE
 * frames are parsed off a `fetch` response stream instead.
 */
export async function* streamChat(
  sessionId: string,
  message: string,
  signal: AbortSignal,
): AsyncGenerator<StreamFrame> {
  const response = await send(`/api/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.body) {
    throw new ApiError(
      "The assistant accepted the message but sent nothing back. Try sending it again.",
      502,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      // Frames are separated by a blank line; the trailing partial frame stays buffered.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
      }
    }
  } catch {
    // Stop was pressed: whatever already arrived stands, and is not an error.
    if (signal.aborted) return;
    throw new ApiError(
      "The connection dropped part-way through the answer, so the reply above may be " +
        "incomplete. Send your message again.",
      0,
    );
  } finally {
    // Frees the response body if the consumer stopped reading before the end.
    void reader.cancel().catch(() => undefined);
  }
}

function parseFrame(raw: string): StreamFrame | null {
  let event = "";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!event || dataLines.length === 0) return null;

  try {
    return { event, data: JSON.parse(dataLines.join("\n")) } as StreamFrame;
  } catch {
    return null;
  }
}
