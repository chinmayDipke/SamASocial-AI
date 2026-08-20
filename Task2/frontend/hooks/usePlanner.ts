"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, streamChat } from "@/lib/api";
import { describePlanChange } from "@/lib/plan";
import type { ChatMessage, CoursePlan, Intake, SessionInfo, Stage, Turn } from "@/lib/types";

/*
  One hook owns the whole planning session: the transcript, the intake slots,
  the plan, and the queue that pushes a mentor's inline edits back to the
  server. Components below it are pure renderers of what this returns.

  The interesting problem here is not streaming -- it is that two writers share
  one plan. The assistant rewrites it on a refine, and the mentor rewrites
  fields by hand, and neither may silently overwrite the other. See `flushEdits`
  for how that is resolved.
*/

const SESSION_KEY = "course-planner.session";
const SAVE_DEBOUNCE_MS = 400;

const EMPTY_INTAKE: Intake = { subject: null, audience: null, duration: null, goals: [] };

export interface Notice {
  /** Uppercase mono strip label, e.g. `COULDN'T DRAFT`. */
  label: string;
  text: string;
  /** What the banner's one button offers, if anything. */
  action: "retry" | "fresh" | null;
}

export type UploadState =
  | { status: "idle" }
  | { status: "uploading"; filename: string }
  | { status: "done"; filename: string }
  | { status: "failed"; filename: string; message: string };

let turnCounter = 0;
const nextId = (prefix: string) => `${prefix}-${++turnCounter}`;

export function usePlanner() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [intake, setIntake] = useState<Intake>(EMPTY_INTAKE);
  const [plan, setPlan] = useState<CoursePlan | null>(null);
  const [starting, setStarting] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [stage, setStage] = useState<Stage | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [upload, setUpload] = useState<UploadState>({ status: "idle" });
  const [maxUploadMb, setMaxUploadMb] = useState(10);
  /** Field paths with a PUT in flight; drives the `SAVING` suffix. */
  const [savingPaths, setSavingPaths] = useState<string[]>([]);
  /** Field paths whose last save failed, keyed to the message shown under them. */
  const [editErrors, setEditErrors] = useState<Record<string, string>>({});

  const abortRef = useRef<AbortController | null>(null);
  // Guards `send` against re-entry. The `streaming` state is a render behind, so
  // two Enters in one tick both read `false` and open two streams over one session.
  const streamingRef = useRef(false);
  // Guards against React's development double-mount creating two sessions.
  const startedRef = useRef(false);
  const sessionIdRef = useRef<string | null>(null);
  // The plan the debounced save will send: state is too late by a keystroke.
  const planRef = useRef<CoursePlan | null>(null);
  // What a failed save rolls back to -- the plan as it was when this batch opened.
  const baselineRef = useRef<CoursePlan | null>(null);
  const pendingPathsRef = useRef<Set<string>>(new Set());
  // Bumped by every edit, so a save can tell whether it is still the newest one.
  const editSeqRef = useRef(0);
  const saveTimerRef = useRef<number | null>(null);
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());
  // The last thing the mentor said, so the error banner can offer a real retry.
  const lastMessageRef = useRef<string | null>(null);

  const applySession = useCallback((session: SessionInfo) => {
    sessionIdRef.current = session.id;
    planRef.current = session.plan;
    baselineRef.current = session.plan;
    pendingPathsRef.current.clear();
    setSessionId(session.id);
    setTurns(turnsFromHistory(session.messages));
    setIntake(session.intake);
    setPlan(session.plan);
    setSavingPaths([]);
    setEditErrors({});
    if (typeof window !== "undefined") window.localStorage.setItem(SESSION_KEY, session.id);
  }, []);

  /*
    Resume where the mentor left off.

    The session id is the only thing kept in localStorage -- the plan itself is
    re-read from the server, so a stale tab can never resurrect an old draft
    over a newer one. An expired id 404s, and that is not an error worth showing:
    it just means a fresh session.
  */
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const stored = window.localStorage.getItem(SESSION_KEY);

    const start = async () => {
      if (stored) {
        try {
          applySession(await api.getSession(stored));
          return;
        } catch (error: unknown) {
          if (!(error instanceof ApiError) || error.status !== 404) {
            setNotice({ label: "CAN'T RESUME", text: describe(error), action: "fresh" });
            return;
          }
          window.localStorage.removeItem(SESSION_KEY);
        }
      }
      try {
        applySession(await api.createSession());
      } catch (error: unknown) {
        setNotice({ label: "NO SESSION", text: describe(error), action: "retry" });
      }
    };

    start().finally(() => setStarting(false));

    // Surface a missing API key up front rather than letting the first turn fail.
    api
      .health()
      .then((health) => {
        setMaxUploadMb(health.max_upload_mb);
        if (!health.llm_key_configured) {
          setNotice({
            label: "NO MODEL KEY",
            text: "The backend has no LLM_API_KEY set, so it cannot draft a plan. Add it to backend/.env and restart the server.",
            action: null,
          });
        }
      })
      .catch(() => {
        /* an unreachable backend is already reported by the session call */
      });
  }, [applySession]);

  /** Take a plan the server sent us as the new truth for both render and save. */
  const adoptPlan = useCallback((next: CoursePlan) => {
    planRef.current = next;
    setPlan(next);
    if (pendingPathsRef.current.size === 0) baselineRef.current = next;
  }, []);

  /**
   * Abandon any edit that has not reached the server yet, and say why on the line.
   *
   * A refinement is computed from the plan the *server* holds, so an edit still
   * sitting in the debounce timer was not part of it. Sending it afterwards would
   * push a document built on the pre-refinement plan over the top of the refined
   * one -- trading the whole refinement for one field. The edit is dropped
   * instead, and the field it touched says so rather than looking saved.
   */
  const dropPendingEdits = useCallback((reason: string) => {
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const paths = [...pendingPathsRef.current];
    if (paths.length === 0) return;
    // Also retires a save already in flight: its echo is stale now, so `runSave`
    // must not adopt whatever comes back from it.
    editSeqRef.current += 1;
    pendingPathsRef.current.clear();
    setSavingPaths([]);
    setEditErrors((previous) => {
      const next = { ...previous };
      for (const path of paths) next[path] = reason;
      return next;
    });
  }, []);

  /**
   * Carry the server's version forward onto text it has not seen.
   *
   * When something is typed while a save is in flight, the echo's *text* is stale
   * -- but its version is not: what is on screen is a descendant of what the
   * server just stored. Without this the next save would quote the older version
   * and be refused as a conflict it is not.
   */
  const adoptVersion = useCallback((version: number) => {
    const current = planRef.current;
    if (!current || current.version >= version) return;
    planRef.current = { ...current, version };
    setPlan(planRef.current);
    if (baselineRef.current) {
      baselineRef.current = { ...baselineRef.current, version };
    }
  }, []);

  const runSave = useCallback(async () => {
    const id = sessionIdRef.current;
    const pending = planRef.current;
    if (!id || !pending || pendingPathsRef.current.size === 0) return;

    const seq = editSeqRef.current;
    const paths = [...pendingPathsRef.current];
    const rollback = baselineRef.current;

    try {
      const saved = await api.savePlan(id, pending);
      /*
        Adopt the server's copy only if nothing was typed while it was in
        flight. Otherwise the echo is already stale and would yank a
        half-finished field back to its old value; the newer edit has its own
        save queued behind this one.
      */
      if (editSeqRef.current === seq) {
        adoptPlan(saved);
        baselineRef.current = saved;
        pendingPathsRef.current.clear();
        setSavingPaths([]);
      } else {
        adoptVersion(saved.version);
      }
    } catch (error: unknown) {
      const overtaken = error instanceof ApiError && error.status === 409 ? planFrom(error) : null;
      if (overtaken) {
        // The plan was rewritten while this edit was being typed, so the server
        // refused it and sent back what it now holds. Show that: rolling back
        // instead would put a plan two versions old on screen.
        adoptPlan(overtaken);
        baselineRef.current = overtaken;
      } else if (rollback && editSeqRef.current === seq) {
        // Roll back only if this save is still the newest thing that happened. A
        // plan frame or a later keystroke has already replaced what it would undo,
        // and undoing it anyway would throw away the newer document.
        planRef.current = rollback;
        setPlan(rollback);
      }
      const message = describe(error);
      setEditErrors((previous) => {
        const next = { ...previous };
        for (const path of paths) next[path] = message;
        return next;
      });
      pendingPathsRef.current.clear();
      setSavingPaths([]);
      if (error instanceof ApiError && error.status === 404) setNotice(expiredSession());
    }
  }, [adoptPlan, adoptVersion]);

  /** Saves run one at a time: two concurrent PUTs would race over `version`. */
  const queueSave = useCallback(() => {
    saveChainRef.current = saveChainRef.current.then(runSave, runSave);
    return saveChainRef.current;
  }, [runSave]);

  /**
   * Push any debounced edit out now and wait for it to land.
   *
   * This is the correctness guarantee of the whole feature, so do not reorder
   * it: the backend refines from the plan *it* holds, so an edit still sitting
   * in the debounce timer when a chat turn starts would be silently overwritten
   * by the refined plan that comes back. Flushing first means the model always
   * refines the mentor-edited plan.
   */
  const flushEdits = useCallback(async () => {
    if (saveTimerRef.current !== null) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
      queueSave();
    }
    await saveChainRef.current;
  }, [queueSave]);

  /**
   * Commit one inline edit: optimistic locally, debounced to the server.
   *
   * `path` is only an identity for the field, so the `SAVING` suffix and a
   * failure message land on the line the mentor actually touched.
   */
  const editField = useCallback(
    (path: string, produce: (plan: CoursePlan) => CoursePlan) => {
      const current = planRef.current;
      if (!current) return;

      if (pendingPathsRef.current.size === 0) baselineRef.current = current;

      const next = produce(current);
      planRef.current = next;
      setPlan(next);
      editSeqRef.current += 1;
      pendingPathsRef.current.add(path);
      setSavingPaths([...pendingPathsRef.current]);
      setEditErrors((previous) => {
        if (!(path in previous)) return previous;
        const remaining = { ...previous };
        delete remaining[path];
        return remaining;
      });

      if (saveTimerRef.current !== null) window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = window.setTimeout(() => {
        saveTimerRef.current = null;
        queueSave();
      }, SAVE_DEBOUNCE_MS);
    },
    [queueSave],
  );

  const send = useCallback(
    async (message: string) => {
      const text = message.trim();
      const id = sessionIdRef.current;
      if (!id || !text || streamingRef.current) return;
      streamingRef.current = true;

      lastMessageRef.current = text;
      const answerId = nextId("a");
      setNotice(null);
      setTurns((previous) => [
        ...previous,
        { role: "user", id: nextId("q"), text, at: null },
        {
          role: "assistant",
          id: answerId,
          text: "",
          at: null,
          streaming: true,
          stage: "thinking",
          note: null,
          error: null,
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
      setStage("thinking");

      try {
        // See `flushEdits`: the mentor's pending edits have to reach the server
        // before the model reads the plan, or the refine will overwrite them.
        await flushEdits();
        // Read after the flush, so a field the mentor just edited is not reported
        // back to them as something the assistant changed.
        const planBefore = planRef.current;

        for await (const frame of streamChat(id, text, controller.signal)) {
          switch (frame.event) {
            case "status":
              setStage(frame.data.stage);
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
            case "intake":
              setIntake(frame.data.intake);
              break;
            case "plan":
              dropPendingEdits(
                "The assistant rewrote this line while you were editing it, so your " +
                  "change was not saved. Make it again on the new text.",
              );
              adoptPlan(frame.data.plan);
              patch({ note: describePlanChange(planBefore, frame.data.plan) });
              break;
            case "done":
              patch({ stage: "done" });
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
          setNotice(
            error instanceof ApiError && error.status === 404
              ? expiredSession()
              : { label: "TURN FAILED", text: describe(error), action: "retry" },
          );
        }
      } finally {
        abortRef.current = null;
        streamingRef.current = false;
        setStreaming(false);
        setStage(null);
      }
    },
    [adoptPlan, dropPendingEdits, flushEdits],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  /** Abandon an expired or broken session and open a new one. */
  const startFresh = useCallback(async () => {
    abortRef.current?.abort();
    const abandoned = sessionIdRef.current;
    sessionIdRef.current = null;
    setSessionId(null);
    if (typeof window !== "undefined") window.localStorage.removeItem(SESSION_KEY);
    setNotice(null);
    setUpload({ status: "idle" });
    lastMessageRef.current = null;
    setStarting(true);
    // Free the abandoned session on the server now rather than at its TTL, and do
    // not wait for it: cleanup must never be what stands between the mentor and a
    // working session, and the store evicts it on its own if this never lands.
    if (abandoned) void api.deleteSession(abandoned).catch(() => undefined);
    try {
      applySession(await api.createSession());
    } catch (error: unknown) {
      setNotice({ label: "NO SESSION", text: describe(error), action: "retry" });
    } finally {
      setStarting(false);
    }
  }, [applySession]);

  /*
    Retry repeats whatever actually failed, which is not always the message: if
    the session itself never opened there is nothing to send to, so the retry is
    opening one. A button that silently does nothing is worse than no button.
  */
  const retry = useCallback(() => {
    const last = lastMessageRef.current;
    setNotice(null);
    if (!sessionIdRef.current) {
      void startFresh();
      return;
    }
    if (last) void send(last);
  }, [send, startFresh]);

  /*
    Leaving the page must not strand work. The debounce timer is fired rather
    than merely cleared -- an edit typed a second before navigating away is still
    an edit the mentor made -- and the stream is aborted so its request does not
    outlive the component that was reading it.
  */
  useEffect(
    () => () => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
        void queueSave();
      }
      abortRef.current?.abort();
    },
    [queueSave],
  );

  const uploadSyllabus = useCallback(
    async (file: File) => {
      const id = sessionIdRef.current;
      if (!id) return;

      const rejection = checkFile(file, maxUploadMb);
      if (rejection) {
        setUpload({ status: "failed", filename: file.name, message: rejection });
        return;
      }

      setUpload({ status: "uploading", filename: file.name });
      try {
        applySession(await api.uploadSyllabus(id, file));
        setUpload({ status: "done", filename: file.name });
      } catch (error: unknown) {
        setUpload({ status: "failed", filename: file.name, message: describeUpload(error) });
        if (error instanceof ApiError && error.status === 404) setNotice(expiredSession());
      }
    },
    [applySession, maxUploadMb],
  );

  return {
    sessionId,
    turns,
    intake,
    plan,
    starting,
    streaming,
    stage,
    notice,
    upload,
    maxUploadMb,
    savingPaths,
    editErrors,
    send,
    stop,
    retry,
    startFresh,
    editField,
    uploadSyllabus,
    dismissUpload: useCallback(() => setUpload({ status: "idle" }), []),
    dismissNotice: useCallback(() => setNotice(null), []),
  };
}

function turnsFromHistory(messages: ChatMessage[]): Turn[] {
  return messages.map((message, index) =>
    message.role === "user"
      ? { role: "user", id: `h${index}`, text: message.content, at: message.created_at }
      : {
          role: "assistant",
          id: `h${index}`,
          text: message.content,
          at: message.created_at,
          streaming: false,
          stage: "done",
          note: null,
          error: null,
        },
  );
}

/** The plan a 409 carries: what the server holds now, so a lost edit can be shown. */
function planFrom(error: ApiError): CoursePlan | null {
  const body = error.body;
  if (body && typeof body === "object" && "plan" in body) {
    return (body as { plan: CoursePlan }).plan;
  }
  return null;
}

function expiredSession(): Notice {
  return {
    label: "SESSION EXPIRED",
    text: "This planning session timed out on the server, so its plan is gone. Starting fresh keeps the conversation you can see but begins a new plan.",
    action: "fresh",
  };
}

/**
 * Reject a file before it is uploaded.
 *
 * Type and size are knowable here, so they are answered here -- a mentor should
 * not wait for a round trip to be told they picked a .docx.
 */
function checkFile(file: File, maxMb: number): string | null {
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  if (!isPdf) {
    return `${file.name} is not a PDF. Export the syllabus as a PDF, or paste its outline into the conversation instead.`;
  }
  const mb = file.size / (1024 * 1024);
  if (mb > maxMb) {
    return `${file.name} is ${mb.toFixed(1)} MB and the limit is ${maxMb} MB. Drop just the outline pages, or split the file.`;
  }
  if (file.size === 0) {
    return `${file.name} is empty. Check the export finished, then drop it again.`;
  }
  return null;
}

function describeUpload(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 413) {
      return "That PDF is larger than the server accepts. Drop just the outline pages, or split the file.";
    }
    // A scanned syllabus is the one failure a mentor can act on but not diagnose.
    if (/text/i.test(error.message)) {
      return `${error.message} If those pages are scans, paste the outline into the conversation instead.`;
    }
    return error.message;
  }
  return describe(error);
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  // Nothing thrown in this app reaches here, but a message a mentor can act on
  // beats a shrug if something ever does.
  return "The planning service did not answer as expected. Try again, and start a fresh session if it keeps happening.";
}
