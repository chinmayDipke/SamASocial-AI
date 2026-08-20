# Task 1 — Multi-Source AI Learning Assistant

A web chatbot that reads **PDFs, PowerPoint decks, YouTube videos and public web pages**, indexes
them for retrieval, and answers questions **grounded strictly in that material** — with a footnote on
every claim pointing back to the exact page, slide, timestamp or section it came from. Ask something
the material does not cover and it says so instead of guessing.

```
Task1/
├─ backend/    FastAPI · ingestion, hybrid retrieval, streaming chat
└─ frontend/   Next.js 16 · App Router, TypeScript, Tailwind v4
```

**What it does**

- Four source types in one session, mixed freely — and one answer can cite several of them.
- Citations you can click: each footnote reveals the exact passage that was retrieved, with a
  deep link back to the video timestamp or page.
- Token-by-token streaming, session memory for follow-ups ("explain that more simply"), and a
  measured out-of-scope refusal.
- Bonus features: per-source summaries, a "quiz me" mode, per-answer source attribution.
- A model picker showing each model's remaining free-tier allowance, and chat history that
  survives a restart.

---

## Getting it running on your machine

Everything below is copy-pasteable. Total time from clone to first answer: about five minutes,
most of it `pip install` and `npm install`.

### 0. What you need first

| | Version | Check with |
| --- | --- | --- |
| Python | 3.11 or newer (built and tested on 3.14) | `python --version` |
| Node.js | 20 or newer (built on 24) | `node --version` |
| Git | any | `git --version` |

You also need **one API key**, from any provider listed in step 2. There is nothing else to
install — no database, no Docker, no vector store, no ffmpeg (unless you turn on the optional
audio fallback).

```bash
git clone https://github.com/chinmayDipke/SamASocial-AI.git
cd "SamASocial-AI/Task1"
```

### 1. Backend — install

Run these from `Task1/backend`:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment — this line differs per shell:

```powershell
.venv\Scripts\Activate.ps1     # Windows PowerShell
```
```bat
.venv\Scripts\activate.bat     :: Windows cmd.exe
```
```bash
source .venv/bin/activate      # macOS / Linux / Git Bash
```

> On Windows PowerShell, if activation is blocked by an execution policy, either use `cmd.exe`
> with `activate.bat` or run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for this terminal only.

```bash
pip install -r requirements.txt
```

### 2. Get an API key and put it in `.env`

The app speaks the **OpenAI Chat Completions** wire format, which OpenAI, Google Gemini, Groq and
Together all implement, so the provider is configuration rather than code. It ships configured for
**Gemini**, because its free tier covers both chat *and* embeddings from a single key.

```bash
cp .env.example .env       # Windows: copy .env.example .env
```

Open `backend/.env` and paste your key into `LLM_API_KEY`. The file already contains working
defaults for Gemini:

```env
LLM_API_KEY=your-key-here          # https://aistudio.google.com/apikey  (free)
LLM_BASE_URL=gemini
LLM_CHAT_MODEL=gemini-3.6-flash
LLM_CONDENSE_MODEL=gemini-3.5-flash-lite
LLM_EMBED_MODEL=gemini-embedding-001
```

To use **OpenAI** instead, change four lines — nothing else:

```env
LLM_API_KEY=sk-...
LLM_BASE_URL=                      # empty means OpenAI
LLM_CHAT_MODEL=gpt-5.5
LLM_EMBED_MODEL=text-embedding-3-small
```

`.env` is gitignored. The key is only ever read server-side and never reaches the browser.

### 3. Confirm the key actually works — do not skip this

```bash
python scripts/check_models.py
```

This lists the models your key can use and then **spends one real token on each endpoint**, so it
cannot pass on a key that is valid but out of quota. You are looking for:

```
embeddings   ok
chat         ok — replied '...'
Configuration looks good.
```

If it names a missing model, copy one it *does* list into `.env`. Model availability differs per
account and changes over time, which is exactly why the model names are settings rather than
constants.

> **Free-tier warning, worth reading.** Daily limits are per model and differ enormously. On the
> key this was built with, the newest flash model allowed only **20 requests per day** — one
> demo session exhausts it. `gemini-3.6-flash` was the best-performing model with workable
> limits. If answers start failing with a quota message, either wait, switch model in the
> dropdown next to the input box (limits are per model, so this recovers immediately), or run
> `check_models.py` again.

### 4. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Leave it running. Confirm it in a browser: <http://127.0.0.1:8000/api/health> should report
`"status": "ok"` and `"llm_key_configured": true`.

### 5. Frontend — in a second terminal

```bash
cd Task1/frontend
npm install
cp .env.local.example .env.local     # only needed if the backend is not on 127.0.0.1:8000
npm run dev
```

Open <http://localhost:3000>.

### 6. Use it

Everything happens in the **one box at the bottom**. It works out what you gave it:

| What you do | What happens |
| --- | --- |
| Paste a bare link (article, docs page, YouTube URL) | It is added as a source |
| Type anything else | It is asked as a question |
| Click the paperclip | Upload a PDF or `.pptx` |

1. Paste a link — a Wikipedia article, or a YouTube video **that has captions** — and press Enter.
2. Wait for the card in the left rail to change from `reading` to a passage count (a few seconds).
   A one-line summary of the source appears with it.
3. Ask a question. The answer streams in, with small superscript numbers after each claim.
4. **Click a number** to see the exact passage it came from, with its page, slide or timestamp.
5. Try a follow-up with no keywords in it — "explain that more simply". It still works, because
   follow-ups are rewritten into standalone questions before retrieval.
6. Ask something your material does not cover. It should decline rather than improvise.
7. **Quiz me on this** (bottom of the left rail) generates multiple-choice questions from your
   material, each with a citation.

The dropdown next to the paperclip picks which model answers, and shows what is known about each
one's limit — a published figure, requests spent this run, or "limit reached" with the provider's
own message. Under the source list, **chats** lists this session's questions as jump links plus
every earlier chat; those are saved in the browser and reopen read-only (see
[Architectural decisions](#architectural-decisions)).

### 7. If something goes wrong

| Symptom | Cause | Fix |
| --- | --- | --- |
| Red bar: "no LLM_API_KEY set" | The backend cannot see your key | Check `.env` is in `Task1/backend/`, then restart uvicorn — it reads the file only at startup |
| "Cannot reach the assistant service" | Backend not running, or on another port | Start uvicorn; if it is not on `127.0.0.1:8000`, set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` |
| Source card: "quota is used up" | Free-tier daily limit for that model | Switch model in the dropdown (limits are per model), or wait for the reset |
| Source card: "does not recognise the configured model" | That model is not available to your key | Run `python scripts/check_models.py` and copy a model it lists into `.env` |
| A model shows "limit reached" in the dropdown | It returned a quota error | Pick another; the choice applies to your next question |
| The dropdown is empty | The backend could not list models | Check `/api/health` shows `llm_key_configured: true`, then restart uvicorn |
| YouTube source fails | The video has no captions, or YouTube is rate-limiting the request | Try another video; captions are required unless you enable the audio fallback |
| PDF: "no selectable text" | It is a scan — images of text | Use a text-based PDF; there is no OCR |
| Web page: "no readable article text" | The page builds its content with JavaScript | Use a direct article or docs URL |
| Answers ignore a source | It is still indexing | Wait for its card to show a passage count |
| Saved chats disappeared | History lives in this browser's `localStorage` | Same browser, not a private window; clearing site data deletes them |
| A reopened chat won't let me type | Old chats are read-only by design — their index is gone | Press **Back to this chat**, or start a new one and re-add the sources |
| `pip install` fails building a wheel | Your Python is older/newer than the published wheels | Use Python 3.11–3.14; all dependencies are pure-Python or ship wheels for those |

### 8. Check the whole pipeline without a browser

```bash
cd Task1/backend
python scripts/smoke.py --url https://en.wikipedia.org/wiki/Retrieval-augmented_generation
```

Pass any mix of sources — the flags repeat:

```bash
python scripts/smoke.py --pdf lecture.pdf --youtube https://youtu.be/VIDEO_ID
```

It ingests each source, prints the generated summary, streams an answer token by token, asks a
follow-up that only resolves in context, asks something off-topic to confirm the assistant declines,
checks the session remembered the conversation, then generates a quiz. It prints
`PASS  ingestion, citations, follow-up grounding, scope refusal, memory and quiz all OK` and exits
non-zero if any check fails. With no flags it defaults to a Wikipedia article.

---

## Environment variables

All backend settings are read from `backend/.env`; `.env.example` is the annotated full list. The
defaults below are the **code** defaults (`app/config.py`) — `.env.example` ships the Gemini values
in place of the OpenAI ones.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_API_KEY` | — | **Required.** Chat, embeddings and quizzes. `OPENAI_API_KEY`, `GEMINI_API_KEY` and `GOOGLE_API_KEY` are accepted as aliases. |
| `LLM_BASE_URL` | empty | Preset (`openai`, `gemini`, `groq`, `together`) or a full base URL. Empty = OpenAI. |
| `LLM_CHAT_MODEL` | `gpt-5.5` | Answering, summaries and quizzes. Verify with `check_models.py`. |
| `LLM_CONDENSE_MODEL` | falls back to chat model | Cheap model for rewriting follow-up questions. |
| `LLM_EMBED_MODEL` | `text-embedding-3-small` | Dense retrieval vectors. |
| `EMBED_BATCH_SIZE` | `96` | Chunks per embedding request. |
| `EMBED_MAX_BATCH_ITEMS` | `0` | Lower cap for providers that limit items per request (Gemini's compat layer: 100); `0` = no extra limit. |
| `CHUNK_TARGET_CHARS` / `CHUNK_OVERLAP_CHARS` | `1200` / `200` | Chunk size and overlap. |
| `RETRIEVAL_TOP_K` | `8` | Chunks sent to the model per question. |
| `CONTEXT_CHAR_BUDGET` | `12000` | Hard cap on assembled context. |
| `MAX_CHUNKS_PER_SOURCE` | `4` | Stops one long source dominating an answer. |
| `RRF_K` | `60` | Rank-fusion constant when merging the keyword and vector rankings. |
| `SCOPE_MARGIN` | `0.15` | How far above the measured "unrelated" baseline a question must score to be answered. Raise to refuse more. |
| `SCOPE_TERM_COVERAGE` | `0.5` | If this fraction of the question's content words appear in the material, treat it as in scope regardless of vector score. |
| `SESSION_TTL_MINUTES` | `120` | Idle session lifetime. |
| `MAX_SESSIONS` | `200` | Concurrent session cap. |
| `MAX_HISTORY_MESSAGES` | `12` | Turns kept in the prompt. |
| `MAX_SOURCES_PER_SESSION` | `8` | Per-session source cap. |
| `MAX_UPLOAD_MB` / `MAX_PDF_PAGES` | `25` / `300` | Upload limits. |
| `REQUEST_TIMEOUT_SECONDS` | `15` | Outbound fetch timeout. |
| `ENABLE_AUDIO_FALLBACK` | `false` | Audio transcription for caption-less videos (needs `ffmpeg` + `yt-dlp`). |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | CORS allowlist. |

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
                 → scope check (model-free, before any spend)
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
| Graceful out-of-scope refusal | `app/retrieval/calibration.py`, applied in `app/llm/chat.py` |
| Mixed sources in one session | session-wide indexes, per-source context cap |
| Per-answer source attribution *(bonus)* | footnote apparatus in `components/Answer.tsx` |
| Quiz mode *(bonus)* | `app/llm/quiz.py`, `components/QuizPanel.tsx` |
| Per-source summary *(bonus)* | `app/llm/summarize.py`, shown on each source card |
| Model picker with live quota usage | `app/llm/catalog.py`, `components/ui/model-picker.tsx` |
| One box for questions, links and files | `components/Composer.tsx` (a bare URL becomes a source) |
| Chat history that survives a restart | `lib/history.ts` (browser-side archive), listed in `components/Shelf.tsx` |

---

## Architectural decisions

**Hybrid retrieval, fused by rank rather than score.** The brief allows embeddings *or* keyword
search; using both covers each one's blind spot — embeddings handle paraphrase ("how do I set this
up?" → "Installation"), BM25 handles exact tokens like error codes, function names and acronyms that
embeddings smooth over. Their scores are not comparable (BM25 is unbounded, cosine is 0–1), so they
are combined with **reciprocal rank fusion**, which uses only each retriever's ordering. There is no
weighting constant to tune, and therefore none to silently drift when the model changes.

**Locators are carried, not reconstructed.** Each ingestor emits `Segment(text, position, locator)`,
and chunking records the span it covers, so a chunk knows it is "pages 3-4" or "03:15-04:02". Citation
accuracy is therefore a property of the data model rather than something the model is asked to infer.
Only citations whose label actually appears in the answer text are displayed.

**A condense step before retrieval.** "Explain that in simpler terms" contains nothing to retrieve on.
Each turn with history is first rewritten into a standalone query by a cheap model. This is the single
change that made follow-ups work; without it the second question in a conversation retrieves noise.

**Per-source context caps.** With a 200-page PDF and a 10-minute video loaded, a plain top-k cut is
almost entirely the PDF. Capping each source's share of the window is what lets one answer draw on
both, and is what makes per-source attribution meaningful rather than decorative.

**The out-of-scope threshold is measured, not hardcoded.** A fixed cosine floor (0.18) worked on
OpenAI and silently failed on Gemini: for the same corpus, a deliberately unrelated question
("average rainfall in Mumbai") scores ≈0.05 on OpenAI but ≈0.48 on Gemini, so the fixed floor
accepted everything. Embedding models simply do not share a scale. Instead, each session measures its
own baseline by embedding five deliberately unrelated probe questions against the loaded material,
and a question must clear that baseline by `SCOPE_MARGIN` of the remaining headroom. Measured on the
real corpus: baseline 0.471, threshold 0.551, genuine questions 0.59–0.81, and the Mumbai question
0.49 → refused. The check costs nothing, because it runs before any chat request; a lexical
coverage escape hatch stops it over-refusing questions built from words that are demonstrably in the
material.

**In-memory sessions.** The brief asks for memory "for the duration of the session", so there is no
database: sources, chunks, both indexes and the transcript live in `SessionStore` with TTL eviction.
It is one interface, so swapping in Redis or Supabase later touches one file. The trade-off is
explicit: restart the server and sessions are gone.

**Chat history is archived client-side.** Because of the decision above, a restart used to erase the
conversation too. The transcript (not the index) is therefore saved in the browser — `localStorage`,
last 25 chats, written when an answer completes rather than per token. Reopened chats are
deliberately **read-only**: the passages they were answered from lived in a session that has ended,
so offering a composer would mean answering from a different index or failing silently. The UI says
which, and why.

**NumPy instead of a vector database.** A session holds a few thousand chunks at most, where one
`matmul` over a normalised `float32` matrix beats building an index — there is no index to build. It
also keeps the dependency list free of native wheels, which mattered here: the only interpreter on
the development machine was Python 3.14, and FAISS/PyTorch have no wheels for it.

**Ingestion runs in the background.** Uploads return immediately with a `processing` source, and the
UI polls. A source becomes `ready` only once it is in *both* indexes, so a question can never hit a
half-indexed source. Summaries fill in afterwards, since they should not delay the first question.

**The provider is a setting, not a dependency.** Everything goes through the OpenAI Chat Completions
format, so `LLM_BASE_URL` plus three model names moves the whole app between OpenAI, Gemini, Groq and
Together with no code change. Two consequences worth noting: embedding calls fall back to
one-request-per-chunk if a provider rejects batched input, and quiz generation degrades from
`json_schema` to `json_object` when strict schemas are unsupported — validated with Pydantic either
way, so a malformed quiz is rejected rather than displayed.

**Model limits are reported, never invented.** Providers do not expose rate limits over the API, so
`/api/models` intersects the provider's own model list with a curated catalog and labels each limit by
how much it can be trusted: *measured* (quoted verbatim from a real quota error, which also disables
the model), *counted* (requests this process has spent), or *documented* (a published figure). An
unknown limit says "unknown" rather than showing a plausible number a user would plan around.

**Errors are written for the reader.** Every ingestion failure raises `IngestError` with a message
intended for the person who pasted the link — "this PDF is a scan, which needs OCR", "captions are
disabled on this video" — and the UI shows it verbatim on the source card.

### UI

The interface treats a grounded answer as what it actually is: **a footnoted document** — the claim,
a superscript marker, and an apparatus underneath resolving each marker to a source, a locator and
the quoted passage one click away. Everything sits in one dark palette, with answers on a panel
raised a step above the shell. Each source is assigned one of five inks and its markers carry that
colour, so *which source said this* is answerable at a glance; all five were contrast-checked
against the answer surface. Type is split by job: a reading serif for answers, a grotesque for
controls, a mono for anything you would verify (refs, locators, counts). Input is deliberately a
single box — a pasted link becomes a source, anything else is a question — because the app can tell
the difference without making the user declare it.

---

## Security notes

- **SSRF guard.** User-supplied URLs are resolved before fetching and rejected if they point at
  loopback, private, link-local or reserved addresses; only `http`/`https` are accepted.
- **Upload limits.** Extension allowlist, a streaming size cap, and a page-count cap on PDFs.
- **No secrets in the client.** The API key is only ever used server-side; the browser talks only to
  this backend.

---

## Tests

```bash
cd Task1/backend
python -m pytest tests -q     # 38 tests: chunking, locators, ingestion, BM25, RRF, quiz parsing
python -m ruff check .

cd ../frontend
npx tsc --noEmit && npm run lint && npm run build
```

The tests target the places where correctness is subtle and a regression would be invisible in a
demo: locator ranges across chunk boundaries, overlap behaviour when a single segment is larger than
a chunk (a real bug this caught), BM25 ranking and its out-of-scope coverage signal, RRF determinism,
the per-source cap, and quiz attribution parsing.

---

## Known limitations

- **Videos without captions.** Transcripts come from caption tracks. A video with none cannot be read
  unless `ENABLE_AUDIO_FALLBACK` is on, which needs `ffmpeg` and `yt-dlp` installed. The UI says so
  explicitly rather than failing vaguely.
- **Scanned PDFs and image-only slides** produce no text; there is no OCR. Detected and reported.
- **JavaScript-rendered pages** may extract thin — the scraper reads server-rendered HTML. A
  canonical article or docs URL works best.
- **Sessions are in-process**, so restarting the backend clears them. Transcripts survive in the
  browser; the retrieval index does not.
- **Chat history is per browser**, not per account — there is no login.
- **YouTube may rate-limit** transcript requests from cloud IPs; this surfaces as a clear error.
