"use client";

import { AlertTriangleIcon, CpuIcon } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ModelOption } from "@/lib/types";

interface Props {
  models: ModelOption[];
  value: string | null;
  disabled?: boolean;
  onChange: (id: string) => void;
}

/**
 * Model picker for the composer.
 *
 * Each row states what the model is for and what it costs you in quota. The
 * limit line is honest about where the number came from: a documented daily cap
 * where one is known, the count of requests this backend has actually made, and
 * the provider's own message once a model runs out.
 */
export function ModelPicker({ models, value, disabled, onChange }: Props) {
  if (models.length === 0) return null;

  const current = models.find((option) => option.id === value);

  return (
    <Select value={value ?? undefined} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger
        size="sm"
        aria-label="Model used to answer"
        title={current ? `${current.label} — ${current.note}` : "Choose a model"}
        className="h-7 w-auto gap-1.5 border-line bg-ink-950 px-2 text-xs text-quiet hover:text-bright focus:ring-1 focus:ring-offset-0"
      >
        <CpuIcon aria-hidden className="size-3.5 shrink-0 text-quieter" />
        <SelectValue placeholder="Model" />
      </SelectTrigger>

      <SelectContent className="max-w-[340px] border-line bg-ink-850">
        {models.map((option) => (
          <SelectItem
            key={option.id}
            value={option.id}
            className="flex-col items-start gap-0.5 py-2 pr-2 pl-8 text-xs"
            // Only the label goes in ItemText, so the closed trigger stays one line.
            detail={
              <span className="flex flex-col gap-0.5">
                <span className="text-[11.5px] leading-[1.4] text-quiet">{option.note}</span>
                <span className="label flex items-center gap-1.5 text-quieter">
                  {option.limit_reached && (
                    <AlertTriangleIcon aria-hidden className="size-3 text-warn" />
                  )}
                  {describeLimit(option)}
                </span>
              </span>
            }
          >
            <span className="flex items-center gap-1.5 text-[13px] text-bright">
              {option.label}
              {option.recommended && <span className="label text-accent/80">default</span>}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** One line summarising this model's quota position, from most to least certain. */
function describeLimit(option: ModelOption): string {
  if (option.limit_reached) return "limit reached — pick another model";

  const parts: string[] = [];
  if (option.documented_daily !== null) {
    parts.push(`${option.documented_daily}/day free tier`);
  }
  parts.push(
    option.requests_used === 1
      ? "1 request this run"
      : `${option.requests_used} requests this run`,
  );
  return parts.join(" · ");
}
