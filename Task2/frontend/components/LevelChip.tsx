"use client";

import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { LEVELS, levelBars } from "@/lib/plan";
import type { Level } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  Difficulty is the one place this app grades a colour, so it is encoded three
  ways at once: depth of hue, a filled-bar count, and the word. Greyscale the
  screen and the bars still say which level this is -- which is the whole reason
  it is not a red/amber/green pill.
*/

const LEVEL_INK: Record<Level, string> = {
  beginner: "text-level-1",
  intermediate: "text-level-2",
  advanced: "text-level-3",
};

function Bars({ level }: { level: Level }) {
  const filled = levelBars(level);
  return (
    <span aria-hidden className="flex gap-[2px]">
      {[0, 1, 2].map((index) => (
        <i
          key={index}
          className={cn("h-2 w-[3px]", index < filled ? "bg-current" : "bg-current/25")}
        />
      ))}
    </span>
  );
}

function Chip({ level, className }: { level: Level; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[3px] bg-level-tint px-1.5 py-0.5",
        LEVEL_INK[level],
        className,
      )}
    >
      <Bars level={level} />
      {/* Below lg the word gives way to its initial; the full word stays in aria-label. */}
      <span className="label hidden lg:inline">{level}</span>
      <span className="label lg:hidden" aria-hidden>
        {level.charAt(0)}
      </span>
    </span>
  );
}

interface Props {
  level: Level;
  onChange: (level: Level) => void;
  /** Names the lesson this chip grades, for the trigger's accessible name. */
  lessonTitle: string;
}

export function LevelChip({ level, onChange, lessonTitle }: Props) {
  return (
    <Select value={level} onValueChange={(next) => onChange(next as Level)}>
      <SelectTrigger
        aria-label={`Difficulty of ${lessonTitle}: ${level}. Change it.`}
        title={level}
        className="rounded-[3px] border border-transparent transition-colors duration-100 hover:border-rule-firm hover:bg-paper"
      >
        <Chip level={level} />
      </SelectTrigger>
      <SelectContent>
        {LEVELS.map((option) => (
          <SelectItem key={option} value={option}>
            <Chip level={option} className="bg-transparent" />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
