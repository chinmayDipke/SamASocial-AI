"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  disabled: boolean;
  streaming: boolean;
  placeholder: string;
  onSend: (message: string) => void;
  onStop: () => void;
}

export function Composer({ disabled, streaming, placeholder, onSend, onStop }: Props) {
  const [value, setValue] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);

  // Grow with the question, up to a point.
  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 168)}px`;
  }, [value]);

  const send = () => {
    const message = value.trim();
    if (!message || disabled || streaming) return;
    onSend(message);
    setValue("");
  };

  return (
    <div className="border-t border-line-soft bg-ink-900/80 px-5 py-3.5 backdrop-blur">
      <div className="mx-auto flex w-full max-w-[42rem] items-end gap-2">
        <textarea
          ref={textarea}
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          aria-label="Ask a question about your sources"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          className="min-h-[44px] flex-1 resize-none rounded-[10px] border border-line bg-ink-950 px-3.5 py-3 text-[14px] leading-[1.5] text-bright placeholder:text-quieter focus:border-accent/70 focus:outline-none disabled:opacity-50"
        />

        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            className="control h-11 rounded-[10px] border border-line px-4 text-quiet transition-colors hover:border-bad/60 hover:text-bad"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={send}
            disabled={disabled || !value.trim()}
            className="control h-11 rounded-[10px] bg-accent px-5 text-ink-950 transition-opacity hover:opacity-90 disabled:opacity-25"
          >
            Ask
          </button>
        )}
      </div>
      <p className="hint mx-auto mt-2 w-full max-w-[42rem] text-quieter">
        Enter to send · Shift+Enter for a new line
      </p>
    </div>
  );
}
