import type { QuizQuestion, SessionInfo, Source, StreamFrame } from "./types";

const BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Pull the backend's `detail` message through, since those are written for users. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "Cannot reach the assistant service. Check that the backend is running on " + BASE_URL,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await readDetail(response), response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "That request was not valid.";
  } catch {
    /* fall through to the generic message */
  }
  return `The request failed (HTTP ${response.status}).`;
}

export interface Health {
  status: string;
  chat_model: string;
  embed_model: string;
  openai_key_configured: boolean;
  max_upload_mb: number;
  max_sources_per_session: number;
}

export const api = {
  health: () => request<Health>("/api/health"),

  createSession: () => request<SessionInfo>("/api/sessions", { method: "POST" }),

  getSession: (sessionId: string) => request<SessionInfo>(`/api/sessions/${sessionId}`),

  listSources: (sessionId: string) => request<Source[]>(`/api/sessions/${sessionId}/sources`),

  addUrlSource: (sessionId: string, url: string) =>
    request<Source>(`/api/sessions/${sessionId}/sources/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),

  addFileSource: (sessionId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Source>(`/api/sessions/${sessionId}/sources/file`, { method: "POST", body });
  },

  generateQuiz: (sessionId: string, count = 5) =>
    request<{ questions: QuizQuestion[] }>(
      `/api/sessions/${sessionId}/quiz?count=${count}`,
      { method: "POST" },
    ),
};

/**
 * Stream one answer.
 *
 * The request carries a JSON body, which `EventSource` cannot do, so the SSE
 * frames are parsed off a `fetch` response stream instead.
 */
export async function* streamChat(
  sessionId: string,
  message: string,
  signal: AbortSignal,
): AsyncGenerator<StreamFrame> {
  const response = await fetch(`${BASE_URL}/api/sessions/${sessionId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(await readDetail(response), response.status);
  }
  if (!response.body) {
    throw new ApiError("The assistant returned an empty response.", 500);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

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

export { BASE_URL };
