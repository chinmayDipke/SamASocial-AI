"use client";

import { ArrowUpIcon, LinkIcon, PaperclipIcon, SquareIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ModelPicker } from "@/components/ui/model-picker";
import { Textarea } from "@/components/ui/textarea";
import type { ModelOption } from "@/lib/types";

interface Props {
  /** True until a session exists; the box is otherwise always typable. */
  disabled: boolean;
  /** Whether any source is indexed, which decides what the hint says. */
  hasSource: boolean;
  streaming: boolean;
  placeholder: string;
  model: string | null;
  models: ModelOption[];
  onModelChange: (id: string) => void;
  onSend: (message: string) => void;
  onAddUrl: (url: string) => void;
  onStop: () => void;
  onAttach: (file: File) => void;
}

const ACCEPTED = ".pdf,.pptx";

export function Composer({
  disabled,
  hasSource,
  streaming,
  placeholder,
  model,
  models,
  onModelChange,
  onSend,
  onAddUrl,
  onStop,
  onAttach,
}: Props) {
  const [value, setValue] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  // Grow with the question, up to a point.
  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 168)}px`;
  }, [value]);

  const trimmed = value.trim();
  const isLink = looksLikeUrl(trimmed);

  const submit = () => {
    if (!trimmed || disabled || streaming) return;
    // One box, two jobs: a bare link loads a source, anything else is a question.
    if (isLink) onAddUrl(trimmed);
    else onSend(trimmed);
    setValue("");
  };

  return (
    <div className="border-t border-line-soft bg-ink-900/80 px-5 py-4 backdrop-blur">
      <div className="mx-auto w-full max-w-[42rem]">
        <div className="rounded-[10px] bg-ink-950 ring-1 ring-line focus-within:ring-accent/70">
          <Textarea
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
                submit();
              }
            }}
            className="min-h-[56px] resize-none rounded-b-none border-none bg-transparent px-3.5 py-3 text-[14px] leading-[1.5] text-bright shadow-none placeholder:text-quieter focus-visible:ring-0 focus-visible:ring-offset-0"
          />

          {/* Toolbar: everything here does something. */}
          <div className="flex items-center justify-between gap-2 rounded-b-[10px] border-t border-line-soft bg-ink-900/60 px-2 py-1.5">
            <div className="flex min-w-0 items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                onClick={() => fileInput.current?.click()}
                disabled={disabled}
                title="Add a PDF or PowerPoint file"
                className="h-7 gap-1.5 px-2 text-xs text-quiet"
              >
                <PaperclipIcon aria-hidden className="size-3.5" />
                Attach
              </Button>

              <ModelPicker
                models={models}
                value={model}
                disabled={streaming}
                onChange={onModelChange}
              />
            </div>

            {streaming ? (
              <Button
                type="button"
                variant="ghost"
                onClick={onStop}
                className="h-7 gap-1.5 px-2.5 text-xs text-quiet hover:text-bad"
              >
                <SquareIcon aria-hidden className="size-3 fill-current" />
                Stop
              </Button>
            ) : (
              <Button
                type="button"
                onClick={submit}
                disabled={disabled || !trimmed}
                aria-label={isLink ? "Add this source" : "Send question"}
                className="h-7 gap-1.5 px-3 text-xs"
              >
                {isLink ? "Add source" : "Ask"}
                {isLink ? (
                  <LinkIcon aria-hidden className="size-3.5" />
                ) : (
                  <ArrowUpIcon aria-hidden className="size-3.5" />
                )}
              </Button>
            )}
          </div>
        </div>

        <p className="hint mt-2 text-quieter">
          {isLink
            ? "That looks like a link — Enter adds it as a source"
            : hasSource
              ? "Enter to send · Shift+Enter for a new line · paste a link to add a source"
              : "Paste a YouTube or article link to add your first source"}
        </p>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept={ACCEPTED}
        multiple
        hidden
        onChange={(event) => {
          for (const file of Array.from(event.target.files ?? [])) onAttach(file);
          event.target.value = "";
        }}
      />
    </div>
  );
}

/** A single token that looks like a web address, rather than a question. */
function looksLikeUrl(value: string): boolean {
  if (/\s/.test(value)) return false;
  if (/^https?:\/\//i.test(value)) return true;
  // Bare hosts like "example.com/docs" count; "what is RAG?" does not.
  return /^[\w-]+(\.[\w-]+)+(\/\S*)?$/.test(value);
}
