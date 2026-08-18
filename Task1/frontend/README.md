# Frontend — Multi-Source AI Learning Assistant

Next.js 16 (App Router) + TypeScript + Tailwind v4. Talks to the FastAPI backend in `../backend`.

```bash
npm install
cp .env.local.example .env.local   # only if the backend is not on 127.0.0.1:8000
npm run dev                        # http://localhost:3000
```

Setup, environment variables and architectural decisions for the whole task are in
[`../README.md`](../README.md).

## Layout

```
app/          route shell (server) + global design tokens
components/   Assistant · Shelf · Conversation · Answer · Composer · QuizPanel
hooks/        useAssistant — session, sources, streaming turns
lib/          api client + SSE reader, answer/footnote parser, types, source inks
```
