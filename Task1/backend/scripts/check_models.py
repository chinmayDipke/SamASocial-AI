"""List the models your key can actually use, so .env can be set correctly.

    python scripts/check_models.py

Model availability varies by account, which is why OPENAI_CHAT_MODEL is a setting
rather than a constant. Run this once during setup.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.llm.client import MissingApiKey, get_openai_client


async def main() -> int:
    settings = get_settings()
    try:
        client = get_openai_client()
    except MissingApiKey as exc:
        print(f"! {exc}")
        return 1

    try:
        models = [model.id async for model in client.models.list()]
    except Exception as exc:
        print(f"! Could not list models: {exc}")
        return 1

    chat = sorted(m for m in models if m.startswith("gpt") and "embedding" not in m)
    embeddings = sorted(m for m in models if "embedding" in m)

    print(f"{len(models)} models available to this key.\n")
    print("Chat / reasoning models:")
    for model in chat:
        print(f"  {model}")
    print("\nEmbedding models:")
    for model in embeddings:
        print(f"  {model}")

    print("\nCurrently configured:")
    for label, configured in (
        ("OPENAI_CHAT_MODEL", settings.openai_chat_model),
        ("OPENAI_EMBED_MODEL", settings.openai_embed_model),
    ):
        mark = "ok " if configured in models else "MISSING"
        print(f"  [{mark}] {label} = {configured}")

    missing = [m for m in (settings.openai_chat_model, settings.openai_embed_model) if m not in models]
    if missing:
        print(f"\n! Not available to this key: {', '.join(missing)}")
        print("  Set the value in backend/.env to one of the models listed above.")
        return 1

    print("\nConfiguration looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
