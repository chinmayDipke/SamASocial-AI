"""End-to-end check of the whole pipeline, no browser required.

    python scripts/smoke.py --url https://en.wikipedia.org/wiki/Retrieval-augmented_generation
    python scripts/smoke.py --pdf notes.pdf --youtube https://youtu.be/VIDEO_ID

Runs the real FastAPI app in-process: ingests each source, then asks an in-scope
question, a follow-up that only makes sense in context, and an off-topic question.
Tokens are printed as they arrive, so streaming is observed rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

IN_SCOPE = "What are the main ideas covered in this material?"
FOLLOW_UP = "Explain that in simpler terms, as if I am new to the topic."
OUT_OF_SCOPE = "What was the average rainfall in Mumbai during July 1998?"

DECLINE_MARKERS = ("could not find", "does not cover", "not in the sources", "nothing about")


def ask(client: TestClient, session_id: str, question: str) -> tuple[str, list[dict], bool]:
    """Send one question and consume the SSE stream, printing tokens as they arrive."""
    print(f"\n> {question}\n")
    answer: list[str] = []
    citations: list[dict] = []
    out_of_scope = False

    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/chat",
        json={"message": question},
    ) as response:
        response.raise_for_status()
        event = ""
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                payload = json.loads(line.removeprefix("data: "))
                if event == "token":
                    text = payload.get("text", "")
                    answer.append(text)
                    print(text, end="", flush=True)
                elif event == "status":
                    print(f"[{payload.get('stage')}] ", end="", flush=True)
                elif event == "citations":
                    citations = payload.get("citations", [])
                elif event == "done":
                    out_of_scope = bool(payload.get("out_of_scope"))
                elif event == "error":
                    print(f"\n! stream error: {payload.get('detail')}")
    print()
    if citations:
        print("  citations: " + ", ".join(f"[{c['ref']} | {c['locator']}]" for c in citations))
    return "".join(answer), citations, out_of_scope


def add_source(client: TestClient, session_id: str, *, url: str | None, pdf: Path | None) -> dict:
    if pdf is not None:
        with pdf.open("rb") as handle:
            response = client.post(
                f"/api/sessions/{session_id}/sources/file",
                files={"file": (pdf.name, handle, "application/octet-stream")},
            )
    else:
        response = client.post(f"/api/sessions/{session_id}/sources/url", json={"url": url})

    if response.status_code >= 400:
        print(f"  rejected: HTTP {response.status_code} {response.json().get('detail')}")
        return {}

    # TestClient runs background tasks before returning, so the source is already processed.
    sources = client.get(f"/api/sessions/{session_id}/sources").json()
    return sources[-1] if sources else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", default=[], help="webpage or YouTube URL")
    parser.add_argument("--pdf", action="append", default=[], help="path to a PDF or PPTX file")
    parser.add_argument("--youtube", action="append", default=[], help="YouTube URL (alias for --url)")
    args = parser.parse_args()

    urls = [*args.url, *args.youtube]
    files = [Path(p) for p in args.pdf]
    if not urls and not files:
        urls = ["https://en.wikipedia.org/wiki/Retrieval-augmented_generation"]
        print("No sources given; defaulting to the RAG Wikipedia article.")

    if not get_settings().llm_api_key:
        print("! LLM_API_KEY is not set. Copy .env.example to .env and add your key.")
        return 1

    failures: list[str] = []
    with TestClient(app) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        print(f"session {session_id}")

        ready = 0
        for url in urls:
            print(f"\n+ {url}")
            source = add_source(client, session_id, url=url, pdf=None)
            print(f"  {source.get('status')} - {source.get('title')} ({source.get('chunk_count')} chunks)")
            if source.get("error"):
                print(f"  error: {source['error']}")
            if source.get("summary"):
                print(f"  summary:\n    {source['summary'].replace(chr(10), chr(10) + '    ')}")
            ready += source.get("status") == "ready"

        for path in files:
            print(f"\n+ {path}")
            if not path.exists():
                failures.append(f"missing file {path}")
                print("  file not found")
                continue
            source = add_source(client, session_id, url=None, pdf=path)
            print(f"  {source.get('status')} - {source.get('title')} ({source.get('chunk_count')} chunks)")
            if source.get("error"):
                print(f"  error: {source['error']}")
            if source.get("summary"):
                print(f"  summary:\n    {source['summary'].replace(chr(10), chr(10) + '    ')}")
            ready += source.get("status") == "ready"

        if not ready:
            print("\n! No source could be indexed, so the chat checks cannot run.")
            return 1

        answer, citations, _ = ask(client, session_id, IN_SCOPE)
        if not answer.strip():
            failures.append("in-scope question returned an empty answer")
        if not citations:
            failures.append("in-scope answer carried no citations")

        follow_up, follow_up_citations, _ = ask(client, session_id, FOLLOW_UP)
        if not follow_up.strip():
            failures.append("follow-up returned an empty answer")
        if not follow_up_citations:
            failures.append("follow-up lost its grounding (no citations)")

        refusal, _, flagged = ask(client, session_id, OUT_OF_SCOPE)
        declined = flagged or any(marker in refusal.lower() for marker in DECLINE_MARKERS)
        if not declined:
            failures.append("out-of-scope question was answered instead of declined")

        history = client.get(f"/api/sessions/{session_id}").json()
        if history["message_count"] < 6:
            failures.append(f"session memory kept only {history['message_count']} messages")

        print("\n--- quiz ---")
        quiz = client.post(f"/api/sessions/{session_id}/quiz", params={"count": 3})
        if quiz.status_code == 200:
            for index, question in enumerate(quiz.json()["questions"], start=1):
                correct = question["options"][question["correct_index"]]
                print(f"{index}. {question['question']}")
                print(f"   answer: {correct}  [{question['source_ref']} | {question['locator']}]")
        else:
            failures.append(f"quiz failed: HTTP {quiz.status_code} {quiz.text[:120]}")

    print("\n=== result ===")
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        return 1
    print("PASS  ingestion, citations, follow-up grounding, scope refusal, memory and quiz all OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
