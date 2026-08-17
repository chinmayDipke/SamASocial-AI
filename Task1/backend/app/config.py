"""Application settings, loaded from the environment (never hardcoded).

The LLM is addressed through the OpenAI **Chat Completions** wire format, which
OpenAI, Google Gemini, Groq, Together and others all speak. Switching provider is
therefore a matter of `LLM_BASE_URL` plus three model names -- no code change.
The older `OPENAI_*` variable names are still accepted as aliases.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Convenience presets so `LLM_BASE_URL=gemini` works instead of a long URL.
BASE_URL_PRESETS = {
    "openai": "",  # the SDK default
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Both names are accepted; `.env.local` wins, matching the Next.js convention.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM provider -------------------------------------------------------
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LLM_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"
        ),
    )
    # A preset name from BASE_URL_PRESETS, or a full URL. Empty means OpenAI.
    llm_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_chat_model: str = Field(
        default="gpt-5.5",
        validation_alias=AliasChoices("LLM_CHAT_MODEL", "OPENAI_CHAT_MODEL"),
    )
    # Cheap model for query condensation. Falls back to the chat model.
    llm_condense_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_CONDENSE_MODEL", "OPENAI_CONDENSE_MODEL"),
    )
    llm_embed_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("LLM_EMBED_MODEL", "OPENAI_EMBED_MODEL"),
    )
    embed_batch_size: int = 96
    # Some providers cap embedding inputs per request; 0 means "no extra limit".
    embed_max_batch_items: int = 0

    # --- Chunking -----------------------------------------------------------
    chunk_target_chars: int = 1200
    chunk_overlap_chars: int = 200

    # --- Retrieval ----------------------------------------------------------
    retrieval_top_k: int = 8
    context_char_budget: int = 12_000
    max_chunks_per_source: int = 4
    rrf_k: int = 60
    # Out-of-scope floor: if nothing clears these, decline without calling the LLM.
    min_vector_score: float = 0.18
    min_bm25_score: float = 0.05

    # --- Sessions and limits ------------------------------------------------
    session_ttl_minutes: int = 120
    max_sessions: int = 200
    max_history_messages: int = 12
    max_sources_per_session: int = 8
    max_upload_mb: int = 25
    max_pdf_pages: int = 300
    request_timeout_seconds: int = 15

    # --- Feature flags ------------------------------------------------------
    # Audio-transcription fallback for caption-less YouTube videos.
    # Requires yt-dlp and ffmpeg on PATH; off by default (see README).
    enable_audio_fallback: bool = False

    # --- HTTP ---------------------------------------------------------------
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def condense_model(self) -> str:
        return self.llm_condense_model or self.llm_chat_model

    @property
    def resolved_base_url(self) -> str | None:
        """Expand a preset name to a URL. None means the SDK's own default."""
        preset = BASE_URL_PRESETS.get(self.llm_base_url.strip().lower())
        url = preset if preset is not None else self.llm_base_url.strip()
        return url or None

    @property
    def provider_label(self) -> str:
        """Which provider the current base URL points at, for logs and health."""
        url = self.resolved_base_url
        if not url:
            return "openai"
        for name, preset in BASE_URL_PRESETS.items():
            if preset and preset in url:
                return name
        return "custom"

    @property
    def embed_batch(self) -> int:
        if self.embed_max_batch_items > 0:
            return min(self.embed_batch_size, self.embed_max_batch_items)
        return self.embed_batch_size

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
