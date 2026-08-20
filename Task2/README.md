# Task 2 — AI Course Planning Assistant for Mentors

A conversational assistant that helps a mentor plan a complete course. It interviews them one
question at a time, drafts a structured course plan, and then lets them change it two ways at
once — by asking in the chat ("make module 2 simpler") or by clicking any field on the plan and
typing over it. The plan is always real structured data, exportable as JSON, and the panel on the
right updates live as it changes.

- **Backend:** FastAPI (Python 3.12+), two-call turn pipeline, JSON-schema-validated plan
  generation, server-side resource-link verification, token-by-token streaming over SSE.
- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind v4, split-panel with click-to-edit
  fields.

---

## Getting it running on your machine

### 0. What you need first

| Thing | Version | Check with |
| ----- | ------- | ---------- |
| Python | 3.12 or newer | `python --version` |
| Node.js | 20 or newer | `node --version` |
| An LLM API key | — | see step 2 |

Two terminals. The backend runs on port 8000, the frontend on 3000.

### 1. Backend — install

```bash
cd Task2/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Get an API key and put it in `.env`

```bash
cp .env.example .env
```

Open `.env` and set `LLM_API_KEY`. Everything else already has a working default.

The cheapest way to run this is Google Gemini's free tier — get a key at
<https://aistudio.google.com/apikey> and leave the other three provider lines as they ship:

```env
LLM_API_KEY=your-key-here
LLM_BASE_URL=gemini
LLM_CHAT_MODEL=gemini-3.6-flash
LLM_CONDENSE_MODEL=gemini-3.5-flash-lite
```

For OpenAI instead, set `LLM_API_KEY=sk-...`, leave `LLM_BASE_URL` **empty**, and set
`LLM_CHAT_MODEL=gpt-5.5`. Groq and Together also work — see the comments in `.env.example`. No code
changes either way; the app speaks the OpenAI Chat Completions wire format, which all of them
implement.

`.env` and `.env.local` are gitignored. Never commit a key.

### 3. Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

Confirm it came up healthy — **do not skip this**, because a bad key looks exactly like a broken app
until you ask:

```bash
curl http://127.0.0.1:8000/api/health
```

`llm_key_configured` must be `true`. It also echoes back which provider and model you are pointed
at, so a typo in the model name shows up here rather than three clicks into the UI.

### 4. Frontend — in a second terminal

```bash
cd Task2/frontend
npm install
npm run dev
```

Open <http://localhost:3000>. If your backend is not on `127.0.0.1:8000`, copy
`.env.local.example` to `.env.local` and point `NEXT_PUBLIC_API_BASE_URL` at it.

### 5. Use it

The left panel interviews you. Answer in your own words — you do not have to fill the slots in
order, and one sentence can fill several at once ("a 6-week intro to Python for 14-year-olds with no
coding background, aiming at building a small game"). The checklist ticks as it understands you.

Once it knows the subject and enough else, it drafts the plan and the right panel fills in. From
there:

- **Ask for changes in the chat** — "make module 2 simpler", "add a project-based assignment",
  "swap the YouTube video in lesson 3 for something shorter".
- **Click any line on the plan and type over it.** Course title, outcomes, module titles,
  objectives, prerequisites, lesson titles and summaries, resource titles. Enter or clicking away
  commits, Escape cancels. Difficulty is a dropdown.
- **Drop a syllabus PDF** on the chat panel and it will read and restructure it into a plan.
- **Export JSON** in the plan toolbar downloads the plan, or copies it to your clipboard.

Your edits and the AI's refinements coexist safely: a pending edit is always written to the server
*before* a chat message is sent, so when you ask for a refinement the model is working from the plan
including everything you just typed. See "Architectural decisions" below.

### 6. If something goes wrong

| What you see | What it means | Fix |
| ------------ | ------------- | --- |
| "Cannot reach the assistant service" | Backend is not running, or is on another port | Start it; check `NEXT_PUBLIC_API_BASE_URL` |
| "No LLM API key is set" | `.env` missing or `LLM_API_KEY` empty | Step 2, then restart the backend |
| "…rejected the API key" | Key is wrong, expired, or for another provider | Re-copy it; check `LLM_BASE_URL` matches the key |
| "…does not recognise the configured model" | `LLM_CHAT_MODEL` is not a model this key can use | Try `gemini-3.6-flash` (Gemini) or `gpt-5.5` (OpenAI) |
| "The quota is used up" | Free-tier allowance exhausted | Wait for the window to reset, or use another key |
| "This session has expired" | Idle longer than `SESSION_TTL_MINUTES` | Start a new one; the UI offers this |
| Every resource says "unchecked" | Link verification is off, or has no network | Set `VERIFY_RESOURCE_LINKS=true` and check your connection |
| Resources say "unreachable" | The link really did not respond | Ask in chat for a replacement resource |

CORS errors mean `ALLOWED_ORIGINS` does not list the origin your browser is using.

### 7. Check it without a browser

```bash
# Create a session, then answer the intake in one go.
SID=$(curl -s -X POST http://127.0.0.1:8000/api/sessions | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -N -X POST http://127.0.0.1:8000/api/sessions/$SID/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"A 6-week intro to Python for absolute beginners aged 14-16, two 1-hour sessions a week. Goal: they can build a small text game by the end."}'

# Then read back the structured plan.
curl -s http://127.0.0.1:8000/api/sessions/$SID/plan/export | head -40
```

You should see `status`, `intake`, `token`, `plan`, `status: checking-links` and a second `plan`
frame stream past, then valid JSON from the export.

### 8. Tests

```bash
cd Task2/backend
python -m pytest          # note: `python -m`, so `app` is importable
```

71 tests. They need **no API key and no network** — the link checker is driven through an
`httpx.MockTransport`, and the parts worth testing (id assignment, intake slot logic, the refinement
guard, JSON extraction) are pure functions by design.

`tests/test_turn.py` deserves a mention: it drives a whole turn and asserts every SSE event name and
payload key. The frontend and backend were built in parallel against a written contract, and nothing
in either toolchain would catch one side renaming a field — a build passes straight over it and the
app silently does nothing. That test fails instead.

```bash
cd Task2/frontend
npm run lint
npm run build
```

---

## Environment variables

All backend config is read from `.env` / `.env.local` via `pydantic-settings`; nothing is hardcoded.
`.env.example` documents every one inline. The ones that matter:

| Variable | Default | What it does |
| -------- | ------- | ------------ |
| `LLM_API_KEY` | — | **Required.** `OPENAI_API_KEY` and `GEMINI_API_KEY` are accepted as aliases |
| `LLM_BASE_URL` | `gemini` | Preset (`openai` / `gemini` / `groq` / `together`) or a full URL |
| `LLM_CHAT_MODEL` | `gemini-3.6-flash` | Writes the plans — use the strongest model you have |
| `LLM_CONDENSE_MODEL` | `gemini-3.5-flash-lite` | Cheap model for the read/route call. Falls back to the chat model |
| `SESSION_TTL_MINUTES` | `180` | Idle lifetime of a planning session |
| `MAX_SESSIONS` | `200` | Concurrency cap; least-recently-used is evicted past it |
| `MAX_HISTORY_MESSAGES` | `24` | Turns of context sent back to the model |
| `MAX_MODULES` | `12` | Ceiling on a generated plan |
| `MAX_LESSONS_PER_MODULE` | `8` | Ceiling on a generated plan |
| `MAX_UPLOAD_MB` | `10` | Largest syllabus PDF accepted |
| `MAX_SYLLABUS_CHARS` | `40000` | Extracted syllabus text is truncated to this |
| `VERIFY_RESOURCE_LINKS` | `true` | Set `false` for an offline demo — links then read "unchecked" |
| `LINK_CHECK_TIMEOUT_SECONDS` | `6` | Per-link timeout. Short so one slow host cannot stall a turn |
| `LINK_CHECK_CONCURRENCY` | `8` | Links checked at once |
| `ALLOWED_ORIGINS` | `localhost:3000,127.0.0.1:3000` | CORS allow-list |

Frontend: `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`).

---

## How it works

### One turn, end to end

```
mentor types
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│ 1. READ  (cheap model, structured JSON)                 │
│    llm/intake.py -> {intake slots, action, target}      │
│    Nothing is generated yet.                            │
└─────────────────────────────────────────────────────────┘
     │  emits: status, intake
     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. _resolve_action()  — state overrides the model       │
│    no subject? -> ask.  no plan? -> can't refine.       │
└─────────────────────────────────────────────────────────┘
     │
     ├── ask      -> stream one question about the next empty slot
     ├── answer   -> stream an answer about the plan; plan untouched
     ├── generate -> stream ack, then build_plan()   ─┐
     └── refine   -> stream ack, then refine_plan()  ─┤
                                                      ▼
                              ┌──────────────────────────────────┐
                              │ 3. assign_ids -> check_refinement │
                              │    validate against JSON schema   │
                              └──────────────────────────────────┘
                                                      │ emits: plan
                                                      ▼
                              ┌──────────────────────────────────┐
                              │ 4. verify_links() concurrently    │
                              └──────────────────────────────────┘
                                       emits: status, plan (again)
```

Frames are `status`, `token`, `intake`, `plan`, `done`, `error`.

### Requirements, and where they are implemented

| Requirement | Where |
| ----------- | ----- |
| Intake — subject, audience, duration, goals | `llm/intake.py`, `llm/prompts.py`, `components/IntakeChecklist.tsx` |
| Module breakdown with learning objectives | `schemas.py: Module`, `llm/planner.py` |
| Lesson topics per module | `schemas.py: Lesson` |
| Public resources per lesson | `schemas.py: Resource`, allow-list in `llm/prompts.py`, verified in `resources/links.py` |
| Assessment at module end | `schemas.py: Assessment` |
| Refinement by follow-up | `llm/turn.py` (`refine` branch), `llm/planner.py: refine_plan` |
| Export as structured JSON | `GET /api/sessions/{id}/plan/export`, toolbar in `PlanPanel.tsx` |
| Live preview, updating in real time | `plan` SSE frames → `hooks/usePlanner.ts` → `PlanPanel.tsx` |
| Multi-turn context | `sessions.py`, `MAX_HISTORY_MESSAGES` |
| Structured output, not free text | JSON schema + Pydantic validation in `llm/planner.py` |
| Editable fields in the UI | `components/ui/editable-text.tsx`, `PUT /api/sessions/{id}/plan` |
| Clean split-panel UI | `components/Planner.tsx` |
| **Bonus** — restructure a syllabus PDF | `ingest/syllabus_pdf.py`, `routers/syllabus.py`, `SyllabusDrop.tsx` |
| **Bonus** — difficulty per lesson | `schemas.py: Level`, `components/LevelChip.tsx` |
| **Bonus** — prerequisites per module | `schemas.py: Module.prerequisites`, `ModuleSection.tsx` |

---

## Architectural decisions

### Two LLM calls per turn, with different jobs

The obvious design is one call that both talks and produces the plan. It is worse. Reading intent is
cheap and mechanical; writing a twelve-module course is expensive and creative. Splitting them means
a misread costs one wasted question instead of a rewritten course, and the routing call can run on a
model an order of magnitude cheaper (`LLM_CONDENSE_MODEL`). It also makes the whole app legible:
`llm/turn.py` is the architecture in one file.

### State has the last word on routing, not the model

`_resolve_action()` exists because a model will cheerfully offer to refine a plan that does not exist
yet, or draft a course with no subject. Those are not judgement calls — the session knows the answer.
So the model's `action` is a suggestion and session state overrides it. Cheaper than pushing harder
on the prompt, and it cannot regress.

### The plan is validated structured data, with a fallback ladder

Plans are generated against a hand-written JSON Schema and then validated with Pydantic, so a
malformed plan is **rejected rather than displayed**. The schema is written out by hand, not derived
from the Pydantic model, because providers reject keywords like `minItems`; this is the portable
subset. Providers also disagree about `response_format`, so generation degrades in two steps —
`json_schema`, then `json_object` — and validates either way.

### Refinement cannot destroy the mentor's work

Three guards, because this is the feature most likely to lose someone's afternoon:

1. `refine_plan()` is given the **current** plan — inline edits included — and returns the whole
   plan, preserving everything it was not asked to change.
2. `check_refinement()` compares before and after. If the model dropped modules nobody asked it to
   drop, the refinement is **rejected**, the old plan is kept, and the assistant says so in its
   reply. This guard is pure and offline: a safety check that needs an API call fails exactly when
   the API does.
3. The session's `plan_lock` is held across the whole refine call, so a mentor's inline `PUT` landing
   mid-refinement waits rather than being silently overwritten a moment later.
4. `PUT` is a **version precondition**, not a blind write. The plan carries a `version`; if the stored
   plan is newer than the one the mentor was editing, the write is refused with `409` and the current
   plan comes back in the body, so the UI can show what actually happened instead of quietly losing
   a change. The lock alone was not enough: it serialises writes but still lets a `PUT` already on the
   wire land after a refinement completes.

### Ids are assigned by the server

`m1`, `m1-l2`, `m1-l2-r1`. The UI keys editable rows off them, so churning ids would lose half-typed
edits. `assign_ids()` matches an item to its previous id by id, then title, then resource URL, so ids
stay stable across a refinement for everything that survived it. The model is never trusted to
generate them.

### Recommended links are verified, not just generated

Resources are the one place this app can invent a fact, and "no hallucination" is the heaviest single
line in the grading. Two defences:

- **Prompt-side** — the model may only cite an allow-list of public platforms, and must name the
  platform in `provider`.
- **Server-side** — every URL is actually fetched before the mentor sees it, concurrently and with a
  short timeout, and the row shows `verified` / `unreachable` / `unchecked` honestly. Nothing is
  silently deleted; the mentor sees the badge and decides.

For YouTube this hits the **oEmbed** endpoint rather than the watch page, because the watch page
returns HTTP 200 for videos that were deleted or never existed — oEmbed returns 404. A check that
passes everything is worse than no check, because it lies.

### Edits are flushed before a chat message is sent

The correctness guarantee for the whole edit/refine feature. Typing into a field updates the UI
immediately, tags the row as saving, and resets a shared ~400 ms debounce so ten keystrokes become
one request. But sending a chat message first **awaits** the pending flush, because the server's
refine path reads the stored plan — so it always reads the mentor-edited one. A monotonic sequence
guard means a slow `PUT` response can never overwrite text the mentor is still typing, and a failed
`PUT` rolls the field back and says why, inline.

One subtlety worth knowing: when a save is in flight and the mentor keeps typing, the server's echo
has stale *text* but a current *version*. The version is carried forward while the text is discarded —
without that, ordinary fast typing would trip the `409` precondition against itself.

### Sessions live in memory

The spec asks for context that lasts the planning session, so there is no database to provision for
a demo. Everything goes through `SessionStore` — TTL eviction, a hard size cap, an `asyncio.Lock` —
so moving to Redis or Postgres is a change to that one file. The honest trade-off: a server restart
loses in-flight plans, and it will not scale past one process. Both are the right call at this size
and the wrong one at scale.

### The provider is a setting, not a decision

Four environment variables select OpenAI, Gemini, Groq or Together. There is no provider-specific
code path, because the assignment says "any LLM API" and hardcoding one is a decision that costs
nothing now and everything later.

### UI

The design brief was to look like a planning surface a professional would use, not a chat toy — and
specifically not like generated UI. So:

- **A document, not nested cards.** Hierarchy is a hanging-margin outline with a generated `M 01`
  spine in the left gutter, lessons behind a single hairline, resources marked by a tick with no rule
  at all. You can read the shape of the course down the numerals without reading any words. Boxes
  inside boxes inside boxes is the tell of generated layout.
- **Difficulty is encoded three ways at once** — one slate hue at three depths, a filled-bar count,
  and the word itself — so it survives greyscale and colour blindness. It is deliberately *not* a
  green/amber/red pill: a traffic light says advanced is a warning, which is a lie.
- **Editable fields carry no idle chrome**, so the plan reads as a document rather than a form. The
  discoverability that costs is bought back once, globally, with a hint in the toolbar — the way
  Notion does it — plus a real focus state so keyboard users get parity.
- **Every contrast pair was computed, not eyeballed.** Three colours failed WCAG and were changed,
  which is also why resource rows sit on the paper surface rather than the desk surface.
- Light theme only, deliberately: Task 1 is a dark reading room, and these are two different
  products in one portfolio.

---

## Security notes

- No key ever reaches the browser. The frontend only ever talks to this backend.
- CORS is an explicit allow-list, not `*`.
- Uploads are capped by `MAX_UPLOAD_MB`, checked for a real PDF header rather than trusting the
  filename, and truncated to `MAX_SYLLABUS_CHARS` before reaching the model.
- Link verification follows model-supplied URLs, which is a deliberate outbound request against
  untrusted input. Anything that is not `http`/`https` is rejected by an explicit check before a
  request is made — not left to the HTTP client to refuse, because that is a security property that
  would break silently on a dependency bump. It is also bounded by a short timeout and a concurrency
  cap, and can be switched off entirely with `VERIFY_RESOURCE_LINKS=false`.
- LLM API errors are translated into messages that name the actual fix (`llm/errors.py`) instead of
  leaking a stack trace or saying "something went wrong".

---

## Known limitations

- **In-memory sessions.** Restarting the backend loses active plans, and it will not scale beyond a
  single process. `SessionStore` is the only file that would change.
- **Link verification proves reachability, not quality.** A `verified` badge means the URL responded,
  not that the video is good or still on-topic. The badge is worded to claim only what it checked.
- **A verified link can rot later.** Verification happens when the plan is generated; nothing
  re-checks it afterwards.
- **Image-only (scanned) syllabus PDFs cannot be read.** There is no OCR; the app says so plainly
  rather than producing a plan from nothing.
- **Refinement rewrites the whole plan each time.** Simple and safe, but it costs more tokens than a
  targeted patch would, and it is why the rejection guard exists.
- **Non-English course plans are untested.** The prompts are written in English and nothing forces
  the output language.
