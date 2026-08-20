"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { UploadState } from "@/hooks/usePlanner";
import { cn } from "@/lib/utils";

/*
  Restructure an existing syllabus.

  Solid border, because this is something you click and drop onto -- dashed is
  reserved for things that are merely stated. Progress is the same drawn rule
  the plan skeleton uses rather than a spinner, so the two loading states in the
  app read as one idea.

  Every failure names the file and says what to do next: a mentor who dropped a
  scan needs different advice from one who dropped a 40 MB export, and "upload
  failed" would serve neither.
*/

interface Props {
  disabled: boolean;
  state: UploadState;
  maxUploadMb: number;
  onUpload: (file: File) => void;
  onDismiss: () => void;
}

export function SyllabusDrop({ disabled, state, maxUploadMb, onUpload, onDismiss }: Props) {
  const [over, setOver] = useState(false);

  const take = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (!disabled) take(event.dataTransfer.files);
      }}
      className={cn(
        "shrink-0 rounded-[4px] border border-rule-firm px-3 py-2 transition-colors duration-100",
        over ? "border-accent bg-accent-tint" : "bg-paper",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="label text-ink-quiet">Syllabus PDF</span>
        <Button asChild variant="quiet">
          <label className="cursor-pointer">
            Browse
            <input
              type="file"
              accept="application/pdf,.pdf"
              hidden
              disabled={disabled}
              onChange={(event) => {
                take(event.target.files);
                event.target.value = "";
              }}
            />
          </label>
        </Button>
      </div>

      {state.status === "idle" ? (
        <p className="caption mt-1 text-ink-quiet">
          Drop one here, up to {maxUploadMb} MB, and the assistant restructures it into modules.
        </p>
      ) : null}

      {state.status === "uploading" ? (
        <div className="mt-2">
          <p className="datum truncate text-ink-quiet">Reading {state.filename}</p>
          <div className="rule-draw mt-1 h-px bg-accent" />
        </div>
      ) : null}

      {state.status === "done" ? (
        <p className="datum mt-2 truncate text-ink-quiet">Restructured {state.filename}</p>
      ) : null}

      {state.status === "failed" ? (
        <div className="mt-2">
          <p className="body text-danger">{state.message}</p>
          <Button variant="quiet" onClick={onDismiss} className="mt-1">
            Dismiss
          </Button>
        </div>
      ) : null}
    </div>
  );
}
