"""Application settings, loaded from the environment (never hardcoded).

The LLM is addressed through the OpenAI **Chat Completions** wire format, which
OpenAI, Google Gemini, Groq, Together and others all speak. Switching provider is
therefore a matter of `LLM_BASE_URL` plus two model names -- no code change. The
older `OPENAI_*` variable names are still accepted as aliases.

The limits here are not decoration: a course plan is a large structured document,
so the module and lesson caps keep one turn inside a sane token budget, and the
link-check settings exist because verifying every resource must never be the slow
part of a turn -- nor block a demo run offline.
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
    # Cheap model for the slot-filling / intent read that opens every turn.
    llm_condense_model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_CONDENSE_MODEL", "OPENAI_CONDENSE_MODEL"),
    )

    # --- Sessions and limits ------------------------------------------------
    session_ttl_minutes: int = 180
    max_sessions: int = 200
    max_history_messages: int = 24
    max_modules: int = 12
    max_lessons_per_module: int = 8
    max_upload_mb: int = 10
    # Syllabus PDFs are read whole rather than chunked, so the prompt needs a ceiling.
    max_syllabus_chars: int = 40_000

    # --- Resource link verification -----------------------------------------
    verify_resource_links: bool = True
    link_check_timeout_seconds: int = 6
    link_check_concurrency: int = 8

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
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
