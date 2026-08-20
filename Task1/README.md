# Task 1 — Multi-Source AI Learning Assistant

A web chatbot that ingests **PDFs, PowerPoint decks, YouTube videos and public web pages**, indexes
them for retrieval, and answers questions **grounded strictly in that material** — with a footnote on
every claim pointing back to the exact page, slide, timestamp or section it came from.

```
Task1/
├─ backend/    FastAPI · ingestion, hybrid retrieval, streaming chat
└─ frontend/   Next.js 16 · App Router, TypeScript, Tailwind v4
```

---

## Setup

Two processes. You need **Python 3.11+**, **Node 20+**, and an API key for one LLM provider.

The app speaks the **OpenAI Chat Completions** wire format, which OpenAI, Google Gemini, Groq and
Together all implement, so the provider is configuration rather than code. It ships configured for
**Gemini** (free tier, and it covers both chat and embeddings from one key):

```env
LLM_API_KEY=...            # https://aistudio.google.com/apikey
LLM_BASE_URL=gemini
LLM_CHAT_MODEL=gemini-3.6-flash
LLM_CONDENSE_MODEL=gemini-3.5-flash-lite
LLM_EMBED_MODEL=gemini-embedding-001
```

For OpenAI instead, leave `LLM_BASE_URL` empty and use `gpt-5.5` / `text-embedding-3-small`.

> **Gemini free-tier note.** Daily request limits are per model, and they differ a lot: the
> newest flash model allowed only 20 requests/day on the key this was built with, which one
> session exhausts. `gemini-3.6-flash` was the best-performing model with workable limits.
> If answers start failing with a quota message, run `python scripts/check_models.py` — it
> probes the endpoints for real and tells you which models the key can actually use.

### 1. Backend

```bash
cd Task1/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

cp .env.example .env            # then put your key in .env
python scripts/check_models.py  # confirms your key can use the configured models
uvicorn app.main:app --reload --port 8000
```

`check_models.py` matters: model availability differs per account, so the chat and embedding models
are settings rather than constants. It prints what your key can actually use and flags a mismatch.

### 2. Frontend

```bash
cd Task1/frontend
npm install
cp .env.local.example .env.local   # only needed if the backend is not on 127.0.0.1:8000
npm run dev
```

Open <http://localhost:3000>.

### 3. Check it end to end (optional, no browser needed)

```bash
cd Task1/backend
python scripts/smoke.py --url https://en.wikipedia.org/wiki/Retrieval-augmented_generation
python scripts/smoke.py --pdf lecture.pdf --youtube https://youtu.be/VIDEO_ID
```

It ingests each source, prints the summary, streams an answer token by token, asks a follow-up that
only resolves in context, asks something off-topic to confirm the assistant declines, then generates
a quiz. It exits non-zero if any of those checks fail.

---

## Environment variables

All backend settings are read from `backend/.env` (see `.env.example` for the full list).

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_API_KEY` | — | **Required.** Chat, embeddings and quizzes. `OPENAI_API_KEY` / `GEMINI_API_KEY` are accepted as aliases. |
| `LLM_BASE_URL` | `gemini` | Preset (`openai`, `gemini`, `groq`, `together`) or a full base URL. Empty = OpenAI. |
| `LLM_CHAT_MODEL` | `gemini-2.5-flash` | Answering, summaries and quizzes. Verify with `check_models.py`. |
| `LLM_CONDENSE_MODEL` | falls back to chat model | Cheap model for rewriting follow-up questions. |
| `LLM_EMBED_MODEL` | `gemini-embedding-001` | Dense retrieval vectors. |
| `EMBED_BATCH_SIZE` | `96` | Chunks per embedding request. |
| `EMBED_MAX_BATCH_ITEMS` | `0` | Lower cap for providers that limit items per request; `0` = no extra limit. |
| `CHUNK_TARGET_CHARS` / `CHUNK_OVERLAP_CHARS` | `1200` / `200` | Chunk size and overlap. |
| `RETRIEVAL_TOP_K` | `8` | Chunks sent to the model per question. |
| `CONTEXT_CHAR_BUDGET` | `12000` | Hard cap on assembled context. |
| `MAX_CHUNKS_PER_SOURCE` | `4` | Stops one long source dominating an answer. |
| `MIN_VECTOR_SCORE` | `0.18` | Out-of-scope floor; lower = more willing to attempt an answer. |
| `SESSION_TTL_MINUTES` | `120` | Idle session lifetime. |
| `MAX_HISTORY_MESSAGES` | `12` | Turns kept in the prompt. |
| `MAX_SOURCES_PER_SESSION` | `8` | Per-session source cap. |
| `MAX_UPLOAD_MB` / `MAX_PDF_PAGES` | `25` / `300` | Upload limits. |
| `ENABLE_AUDIO_FALLBACK` | `false` | Audio transcription for caption-less videos (needs ffmpeg). |
| `ALLOWED_ORIGINS` | `http://localhost:3000,…` | CORS allowlist. |

Frontend: `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`).

---

## How it works

```
upload / paste URL ──► POST /sources ──► background task
                            │              extract → chunk → embed → index → summarise
                            ▼                            │
                     status: processing ──── poll ───────► ready + summary + passage count

question ──► POST /chat (SSE)
                 condense follow-up into a standalone query
                 → BM25 ⊕ vector search, fused with RRF
                 → grounded prompt → stream tokens → citations → done
```

### Requirements, and where they are implemented

| Requirement | Where |
| --- | --- |
| Chunking & retrieval (no whole-document prompts) | `app/chunking.py`, `app/retrieval/` |
| Token-by-token streaming | `app/routers/chat.py` (SSE), `lib/api.ts` (`fetch` + `ReadableStream`) |
| Session memory across turns | `app/sessions.py`, `app/llm/chat.py` |
| Citations ("from slide 4", "at 3:22") | locators in `app/ingest/*`, rendered by `lib/answer.ts` |
| Explain simply / cross-questions | condense step + system prompt in `app/llm/prompts.py` |
| Graceful out-of-scope refusal | relevance floor in `app/llm/chat.py`, prompt contract |
| Mixed sources in one session | session-wide indexes, per-source context cap |
| Per-answer source attribution *(bonus)* | footnote apparatus in `components/Answer.tsx` |
| Quiz mode *(bonus)* | `app/llm/quiz.py`, `components/QuizPanel.tsx` |
| Model picker with live quota usage | `app/llm/catalog.py`, `components/ui/model-picker.tsx` |
| One box for questions, links and files | `components/Composer.tsx` (a bare URL becomes a source) |
| Chat history that survives a restart | `lib/history.ts` (browser-side archive), listed in `components/Shelf.tsx` |
| Per-source summary *(bonus)* | `app/llm/summarize.py`, shown on each source card |

---

## Architectural decisions

**Hybrid retrieval, fused by rank rather than score.** The brief allows embeddings *or* keyword
search; using both covers each one's blind spot — embeddings handle paraphrase ("how do I set this
up?" → "Installation"), BM25 handles exact tokens like error codes, function names and acronyms that
embeddings smooth over. Their scores are not comparable, so they are combined with **reciprocal rank
fusion**, which only needs each retriever's ordering. No calibration constant to tune.

**Locators are carried, not reconstructed.** Each ingestor emits `Segment(text, position, locator)`,
and chunking records the span it covers, so a chunk knows it is "pages 3-4" or "03:15-04:02". Citation
accuracy is therefore a property of the data model rather than something the model is asked to infer.

**A condense step before retrieval.** "Explain that in simpler terms" contains nothing to retrieve on.
Each turn with history is first rewritten into a standalone query. This is the single change that made
follow-ups work; without it the second question in a conversation retrieves noise.

**Per-source context caps.** With a 200-page PDF and a 10-minute video loaded, a plain top-k cut is
almost entirely the PDF. Capping each source's share of the window is what lets one answer draw on
both, and is what makes per-source attribution meaningful.

**Two-layer scope control.** A cheap, model-free floor (best cosine similarity plus the fraction of
question terms that appear anywhere in the corpus) declines clearly-unrelated questions without
spending a request. Everything else is handled by the prompt contract, which instructs the model to
say plainly when the material does not cover something. Belt and braces, cheapest first.

**In-memory sessions.** The brief asks for memory "for the duration of the session", so there is no
database: sources, chunks, both indexes and the transcript live in `SessionStore` with TTL eviction.
It is one interface, so swapping in Redis or Supabase later touches one file. The trade-off is
explicit: restart the server and sessions are gone.

**NumPy instead of a vector database.** A session holds a few thousand chunks at most, where one
`matmul` over a normalised `float32` matrix beats building an index. It also keeps the dependency
list free of native wheels — which mattered here, since the only interpreter on the development
machine was Python 3.14 and FAISS/PyTorch have no wheels for it.

**Ingestion runs in the background.** Uploads return `202` immediately with a `processing` source, and
the UI polls. A source becomes `ready` only once it is in *both* indexes, so a question can never hit
a half-indexed source. Summaries fill in afterwards, since they should not delay the first question.

**The provider is a setting, not a dependency.** Everything goes through the OpenAI Chat Completions
format, so `LLM_BASE_URL` plus three model names moves the whole app between OpenAI, Gemini, Groq and
Together with no code change. Two consequences worth noting: embedding calls fall back to
one-request-per-chunk if a provider rejects batched input, and quiz generation degrades from
`json_schema` to `json_object` when strict schemas are unsupported — validated with Pydantic either
way, so a malformed quiz is rejected rather than displayed.

**Errors are written for the reader.** Every ingestion failure raises `IngestError` with a message
intended for the person who pasted the link — "this PDF is a scan, which needs OCR", "captions are
disabled on this video" — and the UI shows it verbatim on the source card.

### UI

The interface treats a grounded answer as what it actually is: **a footnoted document**. The shell
(rails, your own questions) is dark; answers land on a light "paper" surface, because they are the
thing you read. Each source is assigned one of five inks, and its footnote markers carry that colour,
so *which source said this* is answerable at a glance. Clicking a marker reveals the exact passage
that was retrieved. Type is split by job: a reading serif for answers, a grotesque for controls, a
mono for anything you would verify (refs, locators, counts).

---

## Security notes

- **SSRF guard.** User-supplied URLs are resolved before fetching and rejected if they point at
  loopback, private, link-local or reserved addresses; only `http`/`https` are accepted.
- **Upload limits.** Extension allowlist, a streaming size cap, and a page-count cap on PDFs.
- **No secrets in the client.** The OpenAI key is only ever used server-side.

---

## Tests

```bash
cd Task1/backend
python -m pytest tests -q     # 32 tests: chunking, locators, BM25, RRF, ingestion
python -m ruff check .

cd ../frontend
npm run lint && npm run build
```

The tests cover the parts where correctness is subtle and a regression would be invisible in a demo:
locator ranges across chunk boundaries, overlap behaviour when a single segment is larger than a
chunk, BM25 ranking and its out-of-scope coverage signal, RRF determinism, and the per-source cap.

---

## Known limitations

- **Videos without captions.** Transcripts come from caption tracks. A video with none cannot be read
  unless `ENABLE_AUDIO_FALLBACK` is on, which needs `ffmpeg` and `yt-dlp` installed. The UI says so
  explicitly rather than failing vaguely.
- **Scanned PDFs and image-only slides** produce no text; there is no OCR. Detected and reported.
- **JavaScript-rendered pages** may extract thin — the scraper reads server-rendered HTML. A
  canonical article or docs URL works best.
- **Sessions are in-process**, so restarting the backend clears them (see the decision above).
- **YouTube may rate-limit** transcript requests from cloud IPs; this surfaces as a clear error.
