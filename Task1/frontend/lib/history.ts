import type { Turn } from "./types";

/**
 * Saved chats, kept in the browser.
 *
 * Backend sessions live in memory and die with the server, so the transcript is
 * archived client-side instead: a chat you had last week is still readable after
 * a restart. What is *not* restored is the retrieval index behind it -- reopening
 * a saved chat gives you the conversation, read-only, not a session you can ask
 * more questions in. That limit is deliberate and surfaced in the UI, because
 * pretending otherwise would mean answering from an index that no longer exists.
 */

const KEY = "study-assistant.chats";
const MAX_CHATS = 25;
const MAX_TURNS = 80;
const MAX_TITLE = 90;

export interface ChatRecord {
  id: string;
  title: string;
  /** ISO timestamp of the last message in the chat. */
  savedAt: string;
  turns: Turn[];
}

export function newChatId(): string {
  return `chat-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function loadChats(): ChatRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isChatRecord) : [];
  } catch {
    // Corrupt or unreadable storage must not take the app down with it.
    return [];
  }
}

/** Insert or replace one chat, newest first, and return the stored list. */
export function saveChat(turns: Turn[], id: string): ChatRecord[] {
  const firstQuestion = turns.find((turn) => turn.role === "user");
  if (!firstQuestion) return loadChats();

  const record: ChatRecord = {
    id,
    title: truncate(firstQuestion.text, MAX_TITLE),
    savedAt: new Date().toISOString(),
    // Keep the tail: the most recent exchanges are the ones worth returning to.
    turns: turns.slice(-MAX_TURNS),
  };

  const rest = loadChats().filter((chat) => chat.id !== id);
  return persist([record, ...rest].slice(0, MAX_CHATS));
}

export function deleteChat(id: string): ChatRecord[] {
  return persist(loadChats().filter((chat) => chat.id !== id));
}

export function clearChats(): ChatRecord[] {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(KEY);
    } catch {
      /* nothing useful to do */
    }
  }
  return [];
}

/**
 * Write the list, shedding the oldest chats if the browser refuses the write.
 * A full quota should cost you your oldest transcript, not the current one.
 */
function persist(chats: ChatRecord[]): ChatRecord[] {
  if (typeof window === "undefined") return chats;

  let candidate = chats;
  while (candidate.length > 0) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(candidate));
      return candidate;
    } catch {
      candidate = candidate.slice(0, -1);
    }
  }
  return [];
}

function truncate(text: string, limit: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > limit ? `${clean.slice(0, limit - 1).trimEnd()}…` : clean;
}

function isChatRecord(value: unknown): value is ChatRecord {
  if (typeof value !== "object" || value === null) return false;
  const chat = value as Partial<ChatRecord>;
  return (
    typeof chat.id === "string" &&
    typeof chat.title === "string" &&
    typeof chat.savedAt === "string" &&
    Array.isArray(chat.turns)
  );
}

/** "Today", "Yesterday", or a short date — enough to place a chat in time. */
export function describeWhen(iso: string): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const days = Math.floor((startOfToday.getTime() - then.getTime()) / 86_400_000);

  // Later than midnight today, so show the clock; one day back reads better as a word.
  if (days < 0) return then.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  if (days === 0) return "Yesterday";
  return then.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
