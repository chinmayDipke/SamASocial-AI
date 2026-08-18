"""List the models your key can actually use, so .env can be set correctly.

    python scripts/check_models.py

Model availability differs per provider and per account, which is why the model
names are settings rather than constants. Run this once during setup.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.llm.client import MissingApiKey, get_openai_client
from app.llm.errors import describe_llm_error

# Model families that cannot answer a chat request: speech, vision generation,
# video, music, robotics and retrieval-only endpoints.
NOT_CHAT = (
    "embed",
    "tts",
    "audio",
    "image",
    "veo",
    "lyria",
    "banana",
    "robotics",
    "live",
    "computer-use",
    "transcribe",
    "realtime",
    "moderation",
    "dall-e",
    "whisper",
    "aqa",
    "translate",
)


def short(model_id: str) -> str:
    """Gemini returns ids as `models/gemini-3.7-flash`; the API accepts either form."""
    return model_id.split("/")[-1]


async def main() -> int:
    settings = get_settings()
    try:
        client = get_openai_client()
    except MissingApiKey as exc:
        print(f"! {exc}")
        return 1

    print(f"provider: {settings.provider_label} ({settings.resolved_base_url or 'api.openai.com'})\n")

    try:
        models = [short(model.id) async for model in client.models.list()]
    except Exception as exc:
        print(f"! Could not list models: {describe_llm_error(exc) or exc}")
        return 1

    embeddings = sorted(m for m in models if "embed" in m)
    chat = sorted(m for m in models if not any(term in m for term in NOT_CHAT))

    print(f"{len(models)} models available to this key.\n")
    print("Chat models:")
    for model in chat:
        print(f"  {model}")
    print("\nEmbedding models:")
    for model in embeddings:
        print(f"  {model}")

    available = set(models)
    configured = (
        ("LLM_CHAT_MODEL", settings.llm_chat_model),
        ("LLM_CONDENSE_MODEL", settings.condense_model),
        ("LLM_EMBED_MODEL", settings.llm_embed_model),
    )

    print("\nCurrently configured:")
    for label, value in configured:
        mark = "ok " if short(value) in available else "MISSING"
        print(f"  [{mark}] {label} = {value}")

    missing = [value for _label, value in configured if short(value) not in available]
    if missing:
        print(f"\n! Not available to this key: {', '.join(missing)}")
        print("  Set these in backend/.env (or .env.local) to models listed above.")
        return 1

    # Listing models costs nothing, so it passes even on an account with no credit.
    # Spend a token on each real endpoint to find out whether the key can be used.
    print("\nProbing the endpoints this app actually calls…")
    try:
        await client.embeddings.create(model=settings.llm_embed_model, input="ping")
        print("  embeddings   ok")
    except Exception as exc:
        print(f"  embeddings   FAILED — {describe_llm_error(exc) or exc}")
        return 1

    try:
        response = await client.chat.completions.create(
            model=settings.llm_chat_model,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
        reply = (response.choices[0].message.content or "").strip()
        print(f"  chat         ok — replied {reply[:40]!r}")
    except Exception as exc:
        print(f"  chat         FAILED — {describe_llm_error(exc) or exc}")
        return 1

    print("\nConfiguration looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
