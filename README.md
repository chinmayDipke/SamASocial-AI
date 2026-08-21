# Samasocial Technical Assignment

This repository contains my submission for the Samasocial AI/Full-Stack technical assignment.

| Task | Description | Status |
| ---- | ----------- | ------ |
| [Task 1](./Task1) | Multi-Source AI Learning Assistant — RAG chatbot over YouTube / PDF / PPTX / webpages | Complete |
| [Task 2](./Task2) | AI Course Planning Assistant for Mentors — guided intake, structured course plan, live editing | Complete |

## Task 1 — Multi-Source AI Learning Assistant

A web-based AI chatbot that ingests one or more knowledge sources, indexes them for retrieval, and
answers questions grounded strictly in that content — with citations back to the exact page, slide,
timestamp or section.

- **Backend:** FastAPI (Python 3.14), hybrid retrieval (BM25 + OpenAI embeddings fused with
  reciprocal rank fusion), token-by-token streaming over SSE.
- **Frontend:** Next.js 15 (App Router) + TypeScript + Tailwind.

Setup instructions, environment variables and architecture decisions live in
[`Task1/README.md`](./Task1/README.md).

## Task 2 — AI Course Planning Assistant for Mentors
You can just follow the Task1 README.md for the task2 work on your laptop/desktop.

A conversational assistant that interviews a mentor about the course they want to teach, then
generates a structured course plan — modules, learning objectives, prerequisites, lessons with a
difficulty level, verified public resources, and an end-of-module assessment. The mentor refines it
either by asking in the chat or by clicking any field and typing over it, and exports the result as
JSON.

- **Backend:** FastAPI (Python 3.12+), a two-call turn pipeline (cheap structured read/route, then
  schema-validated plan generation), server-side verification of every recommended link, streaming
  over SSE.
- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind v4 — split panel, chat on one side,
  a live click-to-edit plan on the other.

All three bonus features are implemented: syllabus-PDF restructuring, a difficulty level per lesson,
and prerequisite topics per module.

Setup instructions, environment variables and architecture decisions live in
[`Task2/README.md`](./Task2/README.md).

## Repository layout

```
Task1/     Multi-Source AI Learning Assistant (backend + frontend)
Task2/     AI Course Planning Assistant for Mentors (backend + frontend)
```

Each task is self-contained: its own backend, its own frontend, its own README, and its own `.env`.
They share no code and can be run independently or side by side.

## Documentation

Each task's README is the complete guide for that task: prerequisites, step-by-step setup for both
processes, every environment variable, what to click first, a troubleshooting table, a headless
end-to-end check, and the architecture decisions with their trade-offs.

- [`Task1/README.md`](./Task1/README.md)
- [`Task2/README.md`](./Task2/README.md)

## Challenges

The assignment asks that anything I got stuck on be written down rather than quietly skipped. The
four below were the substantive ones.

**Hallucinated resource links.** In one measured Task 2 run the model recommended 24 resources:
18 URLs resolved, 6 did not. Every URL is now fetched server-side before the mentor sees the plan,
and each resource carries a `verified` / `unreachable` / `unchecked` badge. YouTube goes through
the oEmbed endpoint rather than the watch page, because `watch?v=<anything>` returns HTTP 200 for
deleted and non-existent videos — a check that passes everything is worse than no check.

**Two writers, one document.** A mentor's inline edit and an AI refinement both write the whole
plan, and a session lock orders those writes without knowing one is out of date. `PUT /plan` is
therefore a version precondition: a write built on an overtaken plan is refused with `409`, and
the response carries the current plan so the browser can show what happened. The client carries
that version forward across in-flight saves, or fast typing conflicts with itself.

**Refinements that silently deleted work.** A refinement can come back valid, schema-conformant
and shorter — the failure no type system catches. An offline check compares the result against the
plan it came from and rejects one that dropped modules nobody asked to drop.

**A portable out-of-scope threshold.** In Task 1 a fixed cosine floor tuned on one embedding
provider accepted everything on another: the same unrelated question scored 0.05 with
`text-embedding-3-small` and 0.48 with `gemini-embedding-001`. The floor is now derived per
session from probe queries rather than configured.
