"use client";

import { useRef, useState } from "react";

const ACCEPTED = ".pdf,.pptx";

interface Props {
  disabled: boolean;
  onAdd: (input: { url?: string; file?: File }) => void;
}

/**
 * One control for four source types: paste a link, or drop a file. The URL box
 * does not ask which kind of link it is -- the backend decides from the URL.
 */
export function AddSource({ disabled, onAdd }: Props) {
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const submitUrl = (event: React.FormEvent) => {
    event.preventDefault();
    const value = url.trim();
    if (!value || disabled) return;
    onAdd({ url: value });
    setUrl("");
  };

  const takeFiles = (files: FileList | null) => {
    if (!files || disabled) return;
    for (const file of Array.from(files)) onAdd({ file });
  };

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        takeFiles(event.dataTransfer.files);
      }}
      className={`rounded-[10px] border border-dashed p-3 transition-colors ${
        dragging ? "border-accent bg-accent/5" : "border-line bg-ink-900/60"
      }`}
    >
      <form onSubmit={submitUrl} className="flex gap-1.5">
        <input
          type="text"
          inputMode="url"
          value={url}
          disabled={disabled}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a YouTube or article link"
          aria-label="Source link"
          className="min-w-0 flex-1 rounded-md border border-line bg-ink-950 px-2.5 py-2 text-[13px] text-bright placeholder:text-quieter focus:border-accent/70 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !url.trim()}
          className="control rounded-md bg-accent px-3.5 py-2 text-ink-950 transition-opacity hover:opacity-90 disabled:opacity-30"
        >
          Add
        </button>
      </form>

      <div className="mt-2.5 flex items-center gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => fileInput.current?.click()}
          className="control whitespace-nowrap rounded-md border border-line px-3 py-1.5 text-quiet transition-colors hover:border-accent/60 hover:text-bright disabled:opacity-40"
        >
          Choose a file
        </button>
        <span className="hint text-quieter">or drop it here</span>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept={ACCEPTED}
        multiple
        hidden
        onChange={(event) => {
          takeFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
