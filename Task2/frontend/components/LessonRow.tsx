"use client";

import { Plus } from "lucide-react";

import { LevelChip } from "@/components/LevelChip";
import { ResourceRow } from "@/components/ResourceRow";
import { Button } from "@/components/ui/button";
import { EditableText } from "@/components/ui/editable-text";
import {
  type PlanEditor,
  formatMinutes,
  lessonNumeral,
  mapLesson,
  provisionalResourceId,
} from "@/lib/plan";
import type { Lesson, Level } from "@/lib/types";

/*
  A lesson is a row in the module's spine, not a card: numeral, title, and the
  two facts a mentor scans for on the right (level and length). The hover wash
  is the affordance for the whole row -- click the title to rename, the chip to
  regrade, the plus to add a resource.
*/

interface Props {
  lesson: Lesson;
  moduleId: string;
  moduleIndex: number;
  lessonIndex: number;
  editor: PlanEditor;
}

export function LessonRow({ lesson, moduleId, moduleIndex, lessonIndex, editor }: Props) {
  const titlePath = `${lesson.id}.title`;
  const summaryPath = `${lesson.id}.summary`;

  return (
    <li
      className="group -mx-2 grid grid-cols-[44px_minmax(0,1fr)_auto] items-baseline gap-x-3 rounded-[4px] px-2 py-3 transition-colors duration-100 hover:bg-paper-warm"
      style={{ animationDelay: `${Math.min(lessonIndex, 6) * 40}ms` }}
    >
      <span className="numeral text-ink-faint">{lessonNumeral(moduleIndex, lessonIndex)}</span>

      <div className="min-w-0">
        <EditableText
          value={lesson.title}
          label={`Lesson ${lessonNumeral(moduleIndex, lessonIndex)} title: ${lesson.title}`}
          placeholder="Untitled lesson"
          className="lesson-title text-ink"
          saving={editor.saving(titlePath)}
          error={editor.error(titlePath)}
          onCommit={(title) =>
            editor.commit(titlePath, (plan) =>
              mapLesson(plan, moduleId, lesson.id, (current) => ({ ...current, title })),
            )
          }
        />

        <EditableText
          value={lesson.summary}
          label={`Summary of ${lesson.title}`}
          placeholder="No summary yet"
          multiline
          allowEmpty
          className="body mt-1 max-w-[72ch] text-ink-soft"
          saving={editor.saving(summaryPath)}
          error={editor.error(summaryPath)}
          onCommit={(summary) =>
            editor.commit(summaryPath, (plan) =>
              mapLesson(plan, moduleId, lesson.id, (current) => ({ ...current, summary })),
            )
          }
        />

        {lesson.resources.length > 0 ? (
          <ul className="mt-2 space-y-2" aria-label={`Resources for ${lesson.title}`}>
            {lesson.resources.map((resource) => (
              <ResourceRow
                key={resource.id}
                resource={resource}
                moduleId={moduleId}
                lessonId={lesson.id}
                editor={editor}
              />
            ))}
          </ul>
        ) : null}

        <Button
          variant="quiet"
          aria-label={`Add a resource to ${lesson.title}`}
          className="mt-2 gap-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
          onClick={() =>
            editor.commit(`${lesson.id}.resources`, (plan) =>
              mapLesson(plan, moduleId, lesson.id, (current) => ({
                ...current,
                resources: [
                  ...current.resources,
                  {
                    id: provisionalResourceId(current),
                    title: "",
                    kind: "article",
                    url: "",
                    provider: "",
                    note: "",
                    link_status: "unchecked",
                  },
                ],
              })),
            )
          }
        >
          <Plus size={14} strokeWidth={1.5} aria-hidden />
          Resource
        </Button>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <LevelChip
          level={lesson.level}
          lessonTitle={lesson.title}
          onChange={(level: Level) =>
            editor.commit(`${lesson.id}.level`, (plan) =>
              mapLesson(plan, moduleId, lesson.id, (current) => ({ ...current, level })),
            )
          }
        />
        <span className="datum text-ink-quiet">{formatMinutes(lesson.duration_minutes)}</span>
      </div>
    </li>
  );
}
