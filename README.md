# Samasocial Technical Assignment

This repository contains my submission for the Samasocial AI/Full-Stack technical assignment.

| Task | Description | Status |
| ---- | ----------- | ------ |
| [Task 1](./Task1) | Multi-Source AI Learning Assistant — RAG chatbot over YouTube / PDF / PPTX / webpages | In progress |
| Task 2 | AI Course Planning Assistant for Mentors | Not started |

## Task 1 — Multi-Source AI Learning Assistant

A web-based AI chatbot that ingests one or more knowledge sources, indexes them for retrieval, and
answers questions grounded strictly in that content — with citations back to the exact page, slide,
timestamp or section.

- **Backend:** FastAPI (Python 3.14), hybrid retrieval (BM25 + OpenAI embeddings fused with
  reciprocal rank fusion), token-by-token streaming over SSE.
- **Frontend:** Next.js 15 (App Router) + TypeScript + Tailwind.

Setup instructions, environment variables and architecture decisions live in
[`Task1/README.md`](./Task1/README.md).

## Repository layout

```
Task1/     Multi-Source AI Learning Assistant (backend + frontend)
Task2/     AI Course Planning Assistant
```

## Documentation

[`Task1/README.md`](./Task1/README.md) is the complete guide: prerequisites, step-by-step
setup for both processes, every environment variable, what to click first, a troubleshooting
table, a headless end-to-end check, and the architecture decisions with their trade-offs.
