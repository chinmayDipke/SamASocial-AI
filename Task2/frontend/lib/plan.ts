import type { CoursePlan, Lesson, Level, Module, Resource } from "./types";

/*
  Everything the plan sheet needs that is not state: the generated numbering,
  the mono summary lines, and the immutable updaters an inline edit commits
  through.

  Numbering lives here rather than in the data because a mentor must never be
  able to edit it into a lie -- `M 03` is the third module by definition, so it
  is derived from position on every render.
*/

/**
 * What every editable line on the sheet needs from the planner hook.
 *
 * Passed down rather than reached for through context: the plan is a shallow
 * tree, and an explicit prop keeps it obvious that a row cannot save anything
 * the hook has not agreed to.
 */
export interface PlanEditor {
  commit: (path: string, produce: (plan: CoursePlan) => CoursePlan) => void;
  saving: (path: string) => boolean;
  error: (path: string) => string | null;
}

export const LEVELS: readonly Level[] = ["beginner", "intermediate", "advanced"];

/** 1, 2 or 3 filled bars -- the difficulty chip's non-colour encoding. */
export function levelBars(level: Level): number {
  return LEVELS.indexOf(level) + 1;
}

export function moduleNumeral(moduleIndex: number): string {
  return `M ${String(moduleIndex + 1).padStart(2, "0")}`;
}

export function lessonNumeral(moduleIndex: number, lessonIndex: number): string {
  return `${String(moduleIndex + 1).padStart(2, "0")}.${lessonIndex + 1}`;
}

/** `45 MIN` under an hour, `2 H 15` above it, so durations stay one line. */
export function formatMinutes(minutes: number): string {
  if (minutes <= 0) return "—";
  if (minutes < 60) return `${minutes} MIN`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} H` : `${hours} H ${String(rest).padStart(2, "0")}`;
}

function count(n: number, singular: string): string {
  return `${n} ${singular}${n === 1 ? "" : "S"}`;
}

export function planSummary(plan: CoursePlan): string {
  const lessons = plan.modules.reduce((total, module) => total + module.lessons.length, 0);
  return `${count(plan.modules.length, "MODULE")} · ${count(lessons, "LESSON")}`;
}

export function moduleSummary(module: Module): string {
  const minutes = module.lessons.reduce((total, lesson) => total + lesson.duration_minutes, 0);
  const parts = [count(module.lessons.length, "LESSON")];
  if (minutes > 0) parts.push(formatMinutes(minutes));
  return parts.join(" · ");
}

/** A mentor judges a resource by its domain first, so the host is always shown. */
export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "link";
  }
}

/*
  Immutable updaters. Each returns a whole new plan, because the PUT body is the
  whole plan -- there is no field-level endpoint to be clever about.
*/

export function withPlanFields(plan: CoursePlan, changes: Partial<CoursePlan>): CoursePlan {
  return { ...plan, ...changes };
}

export function mapModule(
  plan: CoursePlan,
  moduleId: string,
  change: (module: Module) => Module,
): CoursePlan {
  return {
    ...plan,
    modules: plan.modules.map((module) => (module.id === moduleId ? change(module) : module)),
  };
}

export function mapLesson(
  plan: CoursePlan,
  moduleId: string,
  lessonId: string,
  change: (lesson: Lesson) => Lesson,
): CoursePlan {
  return mapModule(plan, moduleId, (module) => ({
    ...module,
    lessons: module.lessons.map((lesson) => (lesson.id === lessonId ? change(lesson) : lesson)),
  }));
}

export function mapResource(
  plan: CoursePlan,
  moduleId: string,
  lessonId: string,
  resourceId: string,
  change: (resource: Resource) => Resource,
): CoursePlan {
  return mapLesson(plan, moduleId, lessonId, (lesson) => ({
    ...lesson,
    resources: lesson.resources.map((resource) =>
      resource.id === resourceId ? change(resource) : resource,
    ),
  }));
}

/**
 * A client-side id for a resource the mentor has just added.
 *
 * Provisional -- the server reissues every id on the next PUT -- but it has to be
 * unique *now*, because React keys the row by it. The resource count is not enough:
 * a refinement can leave the ordinals with a gap (`r1`, `r3`), and `count + 1`
 * would then hand back an id already on the row above.
 */
export function provisionalResourceId(lesson: Lesson): string {
  const used = new Set(lesson.resources.map((resource) => resource.id));
  let ordinal = lesson.resources.length + 1;
  while (used.has(`${lesson.id}-r${ordinal}`)) ordinal += 1;
  return `${lesson.id}-r${ordinal}`;
}

/**
 * Write one entry of a string list.
 *
 * Committing an empty value deletes the entry: an objective a mentor has
 * cleared is an objective they meant to remove, and that is one less delete
 * affordance cluttering the sheet.
 */
export function setListEntry(list: string[], index: number, value: string): string[] {
  const next = [...list];
  const trimmed = value.trim();
  if (trimmed === "") next.splice(index, 1);
  else next[index] = trimmed;
  return next;
}

export function removeListEntry(list: string[], index: number): string[] {
  return list.filter((_, position) => position !== index);
}

/**
 * The one-line note under an assistant turn that changed the plan.
 *
 * Reported from the diff rather than from what the model claimed it did, so the
 * note cannot be wrong.
 */
export function describePlanChange(
  previous: CoursePlan | null,
  next: CoursePlan,
): string | null {
  if (!previous) return `DRAFTED ${count(next.modules.length, "MODULE")}`;

  const before = previous.modules;
  const after = next.modules;

  if (after.length > before.length) {
    const known = new Set(before.map((module) => module.id));
    const index = after.findIndex((module) => !known.has(module.id));
    return `ADDED MODULE ${moduleNumeral(index === -1 ? after.length - 1 : index).slice(2)}`;
  }
  if (after.length < before.length) {
    return `REMOVED ${count(before.length - after.length, "MODULE")}`;
  }

  const changed = after.findIndex(
    (module, index) => JSON.stringify(module) !== JSON.stringify(before[index]),
  );
  if (changed === -1) return null;
  return `REVISED MODULE ${moduleNumeral(changed).slice(2)}`;
}
