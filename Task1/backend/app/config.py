"""Application settings, loaded from the environment (never hardcoded)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- OpenAI -------------------------------------------------------------
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5.5"
    # Cheap model for query condensation. Falls back to the chat model if unset.
    openai_condense_model: str = ""
    openai_embed_model: str = "text-embedding-3-small"
    embed_batch_size: int = 96

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
        return self.openai_condense_model or self.openai_chat_model

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
