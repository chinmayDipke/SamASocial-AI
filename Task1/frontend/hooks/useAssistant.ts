"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, streamChat } from "@/lib/api";
import { type ChatRecord, loadChats, newChatId, saveChat } from "@/lib/history";
import type { ModelOption, QuizQuestion, Source, Turn } from "@/lib/types";

const SOURCE_POLL_MS = 1200;
const MODEL_STORAGE_KEY = "study-assistant.model";

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
  const [models, setModels] = useState<ModelOption[]>([]);
  // Saved transcripts from previous sessions, newest first.
  const [chats, setChats] = useState<ChatRecord[]>([]);
  // Which saved chat is being read, if any. Null means the live conversation.
  const [viewingChatId, setViewingChatId] = useState<string | null>(null);
  // The id this conversation is archived under. Held in state, not a ref, because
  // the rail renders against it.
  const [chatId, setChatId] = useState(() => newChatId());
  // The chosen model. Null means "whatever the backend defaults to".
  const [model, setModel] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  // Guards against React's development double-mount creating two sessions.
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    // localStorage is only readable in the browser, so this waits for mount.
    setChats(loadChats());

    api
      .createSession()
      .then((session) => setSessionId(session.session_id))
      .catch((error: unknown) => setNotice({ kind: "error", text: describe(error) }))
      .finally(() => setStarting(false));

    api
      .listModels()
      .then(({ models: available, default: fallback }) => {
        setModels(available);
        const remembered =
          typeof window === "undefined" ? null : window.localStorage.getItem(MODEL_STORAGE_KEY);
        const usable = remembered && available.some((option) => option.id === remembered);
        setModel(usable ? remembered : fallback);
      })
      .catch(() => {
        /* the picker simply stays empty; the backend default still answers */
      });

    // Surface a missing API key up front rather than letting the first upload fail.
    api
      .health()
      .then((health) => {
        setModel((current) => current ?? health.chat_model);
        if (!health.llm_key_configured) {
          setNotice({
            kind: "error",
            text: "The backend has no LLM_API_KEY set, so sources cannot be indexed. Add it to backend/.env and restart the server.",
          });
        }
      })
      .catch(() => {
        /* createSession already reports an unreachable backend */
      });
  }, []);

  /*
    Archive the transcript once it settles.

    Saving on every token would rewrite localStorage hundreds of times per
    answer, so this waits for the stream to finish -- and a chat interrupted by
    a closed tab still keeps every completed turn.

    The written record is deliberately not fed back into `chats`: the rail lists
    *earlier* chats and reads the live one straight from `turns`, so re-reading
    storage here would only cause a render for a list that already agrees.
  */
  useEffect(() => {
    if (streaming || turns.length === 0) return;
    saveChat(turns, chatId);
  }, [streaming, turns, chatId]);

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
        for await (const frame of streamChat(sessionId, question, controller.signal, model)) {
          switch (frame.event) {
            case "status":
              patch({ stage: frame.data.stage });
              // The backend reports which model it actually used.
              if (frame.data.model) setModel(frame.data.model);
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
        // Message count, late summaries and per-model usage all refresh here.
        api.listSources(sessionId).then(setSources).catch(() => {});
        api
          .listModels()
          .then(({ models: available }) => setModels(available))
          .catch(() => {});
      }
    },
    [sessionId, streaming, model],
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

  const chooseModel = useCallback((next: string) => {
    setModel(next);
    // Remember the choice so a reload does not silently switch models.
    if (typeof window !== "undefined") window.localStorage.setItem(MODEL_STORAGE_KEY, next);
  }, []);

  /**
   * Start a fresh conversation.
   *
   * A new backend session means a new retrieval index, so the loaded sources go
   * with it -- there is no way to keep them without keeping the old session.
   */
  const newChat = useCallback(async () => {
    abortRef.current?.abort();
    setViewingChatId(null);
    setNotice(null);
    setQuiz(null);
    setTurns([]);
    setSources([]);
    setChatId(newChatId());
    // The chat just left behind becomes an "earlier" one, so re-read the archive.
    setChats(loadChats());

    try {
      const session = await api.createSession();
      setSessionId(session.session_id);
    } catch (error: unknown) {
      setNotice({ kind: "error", text: describe(error) });
    }
  }, []);

  const openChat = useCallback(
    (id: string) => setViewingChatId(id === chatId ? null : id),
    [chatId],
  );

  const closeChat = useCallback(() => setViewingChatId(null), []);

  const viewingChat = viewingChatId
    ? (chats.find((chat) => chat.id === viewingChatId) ?? null)
    : null;

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
    model,
    models,
    chooseModel,
    chats,
    currentChatId: chatId,
    viewingChat,
    openChat,
    closeChat,
    newChat,
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
