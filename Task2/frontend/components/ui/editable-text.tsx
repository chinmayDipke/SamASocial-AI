"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/*
  Every editable line on the sheet is this component. One primitive, so the
  keyboard contract, the save signal and the failure signal are identical
  whether you are renaming a course or fixing a typo in a resource title.

  Two decisions worth keeping:

  - It holds its own draft while editing, so a `plan` frame arriving mid-stream
    re-renders the sheet around the field without yanking half-typed text away.
  - Idle is a real `<button>`. It costs nothing visually (all chrome is stripped)
    and it means keyboard users reach and open every field with Tab and Enter,
    rather than needing a parallel affordance bolted on later.

  Discoverability is solved once in the toolbar -- `CLICK ANY LINE TO EDIT` --
  so no field carries a pencil icon and the sheet stays a document.
*/

interface Props {
  value: string;
  onCommit: (next: string) => void;
  /** Names the field for screen readers, e.g. `Module 2 title`. */
  label: string;
  /** Typography and colour, applied to both states so the text does not jump. */
  className?: string;
  /** Allows newlines, and switches the hint to `⇧⏎`. */
  multiline?: boolean;
  /** Committing an empty value deletes the entry rather than reverting. */
  allowEmpty?: boolean;
  /** Shown in `ink-faint` when the value is blank; never committed. */
  placeholder?: string;
  /** A PUT for this field is in flight. */
  saving?: boolean;
  /** The last save for this field failed; the value shown has been rolled back. */
  error?: string | null;
}

const FLASH_MS = 560;

export function EditableText({
  value,
  onCommit,
  label,
  className,
  multiline = false,
  allowEmpty = false,
  placeholder,
  saving = false,
  error = null,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [flashing, setFlashing] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const idleRef = useRef<HTMLButtonElement>(null);
  // Set only by Enter and Escape: a blur caused by a click elsewhere must not
  // drag focus back out of whatever was clicked.
  const restoreFocusRef = useRef(false);

  // Grow to the text, with no visible scrollbar, and start the caret at the end.
  useEffect(() => {
    const field = fieldRef.current;
    if (!editing || !field) return;
    field.style.height = "auto";
    field.style.height = `${field.scrollHeight}px`;
  }, [editing, draft]);

  useEffect(() => {
    if (editing || !restoreFocusRef.current) return;
    restoreFocusRef.current = false;
    idleRef.current?.focus();
  }, [editing]);

  useEffect(() => {
    if (!flashing) return;
    const timer = window.setTimeout(() => setFlashing(false), FLASH_MS);
    return () => window.clearTimeout(timer);
  }, [flashing]);

  const open = useCallback(() => {
    setDraft(value);
    setEditing(true);
  }, [value]);

  const commit = useCallback(() => {
    setEditing(false);
    const next = draft.trim();
    if (next === value) return;
    // A title cleared by accident reverts; a list entry cleared on purpose is a
    // delete, and the caller says which of the two this field is.
    if (next === "" && !allowEmpty) return;
    setFlashing(true);
    onCommit(next);
  }, [allowEmpty, draft, onCommit, value]);

  const cancel = useCallback(() => {
    setDraft(value);
    setEditing(false);
  }, [value]);

  if (editing) {
    return (
      <span className="block">
        <textarea
          ref={fieldRef}
          rows={1}
          autoFocus
          value={draft}
          aria-label={label}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              restoreFocusRef.current = true;
              cancel();
              return;
            }
            if (event.key === "Enter" && !(multiline && event.shiftKey)) {
              event.preventDefault();
              restoreFocusRef.current = true;
              commit();
            }
          }}
          className={cn(
            "-mx-1 block w-full resize-none overflow-hidden rounded-[4px] bg-paper px-1",
            "caret-accent outline-2 outline-accent outline-offset-[-1px]",
            "transition-[background-color,outline-color] duration-150",
            className,
          )}
        />
        <span className="datum mt-1 block text-right text-ink-quiet">
          {multiline ? "⇧⏎ NEWLINE · ⏎ SAVE · ESC CANCEL" : "⏎ SAVE · ESC CANCEL"}
        </span>
      </span>
    );
  }

  return (
    <span className="block">
      <button
        ref={idleRef}
        type="button"
        aria-label={label}
        onClick={open}
        className={cn(
          "-mx-1 block max-w-full cursor-text rounded-[4px] border border-transparent px-1 text-left",
          "whitespace-pre-wrap transition-[background-color,outline-color] duration-150",
          "hover:bg-paper-warm hover:underline hover:decoration-rule-firm hover:decoration-dotted hover:underline-offset-[4px]",
          "focus-visible:bg-paper-warm focus-visible:underline focus-visible:decoration-rule-firm focus-visible:decoration-dotted focus-visible:underline-offset-[4px]",
          saving && "uncommitted text-caution",
          flashing && "commit-flash",
          className,
        )}
      >
        {value === "" ? (
          <span className="text-ink-faint">{placeholder ?? "Empty"}</span>
        ) : (
          value
        )}
        {saving ? <span className="datum ml-2 text-caution">SAVING</span> : null}
      </button>
      {error ? <span className="caption mt-1 block text-danger">{error}</span> : null}
    </span>
  );
}
