"use client";

import { Check, CircleDashed, ExternalLink, Unlink } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EditableText } from "@/components/ui/editable-text";
import { type PlanEditor, hostOf, mapResource } from "@/lib/plan";
import type { LinkStatus, Resource } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
  Depth 3 of the outline: an em-tick marker and no vertical rule, so a resource
  reads as a footnote to its lesson rather than another nested box.

  The verification badge is reported exactly as the server found it. A dead link
  is struck through as well as coloured, and never deletes itself -- the mentor
  decides whether a resource is worth replacing, and `Replace` turns the URL
  into an editable field. Editing a URL resets its badge to UNCHECKED, because
  nothing has verified the new one yet.
*/

const BADGE: Record<LinkStatus, { Glyph: typeof Check; ink: string; word: string }> = {
  verified: { Glyph: Check, ink: "text-verified", word: "verified" },
  unreachable: { Glyph: Unlink, ink: "text-unreachable", word: "unreachable" },
  unchecked: { Glyph: CircleDashed, ink: "text-unchecked", word: "unchecked" },
};

interface Props {
  resource: Resource;
  moduleId: string;
  lessonId: string;
  editor: PlanEditor;
}

export function ResourceRow({ resource, moduleId, lessonId, editor }: Props) {
  const [replacing, setReplacing] = useState(false);
  const { Glyph, ink, word } = BADGE[resource.link_status];
  const dead = resource.link_status === "unreachable";
  const titlePath = `${resource.id}.title`;
  const urlPath = `${resource.id}.url`;
  // A resource the mentor just added has no address yet, so the row opens on
  // the field that needs filling rather than offering a link to nowhere.
  const hasUrl = resource.url.trim() !== "";

  return (
    <li className="resource-row group/resource relative flex flex-wrap items-baseline gap-2 pl-5">
      <EditableText
        value={resource.title}
        label={`Resource title: ${resource.title}`}
        placeholder="Untitled resource"
        saving={editor.saving(titlePath)}
        error={editor.error(titlePath)}
        className={cn(
          "body text-accent underline decoration-rule-firm decoration-1 underline-offset-[3px] hover:decoration-accent",
          dead && "line-through decoration-unreachable/60",
        )}
        onCommit={(title) =>
          editor.commit(titlePath, (plan) =>
            mapResource(plan, moduleId, lessonId, resource.id, (current) => ({
              ...current,
              title,
            })),
          )
        }
      />

      {hasUrl ? (
        <>
          <a
            href={resource.url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Open ${resource.title} at ${hostOf(resource.url)} in a new tab`}
            className="text-accent transition-colors duration-100 hover:text-accent-deep"
          >
            <ExternalLink size={14} strokeWidth={1.5} aria-hidden />
          </a>
          {/* A mentor judges a resource by its domain first, so it is always shown. */}
          <span className="datum shrink-0 text-ink-quiet">{hostOf(resource.url)}</span>
        </>
      ) : null}

      <span className={cn("inline-flex shrink-0 items-center gap-1", ink)}>
        <Glyph size={14} strokeWidth={1.5} aria-hidden />
        {/* Below xl the word gives way to the glyph, which keeps the name. */}
        <span className="label hidden xl:inline">{word}</span>
        <span className="sr-only xl:hidden">{word}</span>
      </span>

      {dead && !replacing ? (
        <Button
          variant="quiet"
          onClick={() => setReplacing(true)}
          className="opacity-0 group-hover/resource:opacity-100 focus-visible:opacity-100"
        >
          Replace
        </Button>
      ) : null}

      {replacing || !hasUrl ? (
        <span className="basis-full">
          <EditableText
            value={resource.url}
            label={`Address for ${resource.title}`}
            placeholder="https://"
            saving={editor.saving(urlPath)}
            error={editor.error(urlPath)}
            className="code text-ink-soft"
            onCommit={(url) => {
              setReplacing(false);
              editor.commit(urlPath, (plan) =>
                mapResource(plan, moduleId, lessonId, resource.id, (current) => ({
                  ...current,
                  url,
                  link_status: "unchecked",
                })),
              );
            }}
          />
        </span>
      ) : null}
    </li>
  );
}
