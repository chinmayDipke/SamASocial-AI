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
