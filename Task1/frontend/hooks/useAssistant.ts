"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, streamChat } from "@/lib/api";
import type { QuizQuestion, Source, Turn } from "@/lib/types";

const SOURCE_POLL_MS = 1200;

export interface Notice {
  kind: "error" | "info";
  text: string;
}

let turnCounter = 0;
const nextId = (prefix: string) => `${prefix}-${++turnCounter}`;

export function useAssistant() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [starting, setStarting] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [quiz, setQuiz] = useState<QuizQuestion[] | null>(null);
  const [quizLoading, setQuizLoading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  // Guards against React's development double-mount creating two sessions.
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    api
      .createSession()
      .then((session) => setSessionId(session.session_id))
      .catch((error: unknown) => setNotice({ kind: "error", text: describe(error) }))
      .finally(() => setStarting(false));

    // Surface a missing API key up front rather than letting the first upload fail.
    api
      .health()
      .then((health) => {
        if (!health.openai_key_configured) {
          setNotice({
            kind: "error",
            text: "The backend has no OPENAI_API_KEY set, so sources cannot be indexed. Add it to backend/.env and restart the server.",
          });
        }
      })
      .catch(() => {
        /* createSession already reports an unreachable backend */
      });
  }, []);

  // While anything is indexing, poll so status, chunk counts and summaries land live.
  useEffect(() => {
    if (!sessionId || !sources.some((source) => source.status === "processing")) return;

    const timer = setInterval(() => {
      api
        .listSources(sessionId)
        .then(setSources)
        .catch(() => {
          /* a dropped poll is not worth interrupting the user over */
        });
    }, SOURCE_POLL_MS);

    return () => clearInterval(timer);
  }, [sessionId, sources]);

  const addSource = useCallback(
    async (input: { url?: string; file?: File }) => {
      if (!sessionId) return;
      setNotice(null);
      try {
        const source = input.file
          ? await api.addFileSource(sessionId, input.file)
          : await api.addUrlSource(sessionId, input.url!.trim());
        setSources((previous) => [...previous, source]);
      } catch (error: unknown) {
        setNotice({ kind: "error", text: describe(error) });
      }
    },
    [sessionId],
  );

  const ask = useCallback(
    async (message: string) => {
      const question = message.trim();
      if (!sessionId || !question || streaming) return;

      const answerId = nextId("a");
      setNotice(null);
      setTurns((previous) => [
        ...previous,
        { role: "user", id: nextId("q"), text: question },
        {
          role: "assistant",
          id: answerId,
          text: "",
          citations: [],
          streaming: true,
          stage: "retrieving",
          outOfScope: false,
        },
      ]);

      const patch = (changes: Partial<Extract<Turn, { role: "assistant" }>>) =>
        setTurns((previous) =>
          previous.map((turn) =>
            turn.id === answerId && turn.role === "assistant" ? { ...turn, ...changes } : turn,
          ),
        );

      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);

      try {
        for await (const frame of streamChat(sessionId, question, controller.signal)) {
          switch (frame.event) {
            case "status":
              patch({ stage: frame.data.stage });
              break;
            case "token":
              setTurns((previous) =>
                previous.map((turn) =>
                  turn.id === answerId && turn.role === "assistant"
                    ? { ...turn, text: turn.text + frame.data.text }
                    : turn,
                ),
              );
              break;
            case "citations":
              patch({ citations: frame.data.citations });
              break;
            case "done":
              patch({ stage: "done", outOfScope: Boolean(frame.data.out_of_scope) });
              break;
            case "error":
              patch({ error: frame.data.detail });
              break;
          }
        }
        patch({ streaming: false, stage: "done" });
      } catch (error: unknown) {
        if (controller.signal.aborted) {
          patch({ streaming: false, stage: "done" });
        } else {
          patch({ streaming: false, stage: "done", error: describe(error) });
        }
      } finally {
        abortRef.current = null;
        setStreaming(false);
        // Message count and any late summaries are refreshed once the turn ends.
        api.listSources(sessionId).then(setSources).catch(() => {});
      }
    },
    [sessionId, streaming],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const startQuiz = useCallback(
    async (count = 5) => {
      if (!sessionId) return;
      setQuizLoading(true);
      setNotice(null);
      try {
        const { questions } = await api.generateQuiz(sessionId, count);
        setQuiz(questions);
      } catch (error: unknown) {
        setNotice({ kind: "error", text: describe(error) });
      } finally {
        setQuizLoading(false);
      }
    },
    [sessionId],
  );

  const closeQuiz = useCallback(() => setQuiz(null), []);

  const readySources = sources.filter((source) => source.status === "ready");

  return {
    sessionId,
    sources,
    readySources,
    turns,
    notice,
    starting,
    streaming,
    quiz,
    quizLoading,
    addSource,
    ask,
    stop,
    startQuiz,
    closeQuiz,
    dismissNotice: useCallback(() => setNotice(null), []),
  };
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
