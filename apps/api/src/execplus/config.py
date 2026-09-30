"""Use case: Loads runtime configuration.

What it does: Validates environment, service, and model settings before API startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EXECPLUS_",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = Field(
        default="postgresql+psycopg://execplus:execplus@localhost:5432/execplus", repr=False
    )
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "execplus-local"
    object_store_access_key: str = Field(default="execplus", repr=False)
    object_store_secret_key: str = Field(default="change-me", repr=False)
    llm_mode: Literal["disabled", "local", "hosted"] = "disabled"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = Field(default="", repr=False)
    llm_small_model: str = ""
    llm_large_model: str = ""
    llm_json_mode: bool = False
    llm_max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    llm_reasoning_effort: Literal["none", "low", "medium", "high", "max"] | None = None
    llm_selection_base_url: str = ""
    llm_selection_model: str = ""
    llm_selection_api_key: str = Field(default="", repr=False)
    production_evidence_path: str = ""
    email_mode: Literal["disabled", "smtp"] = "disabled"
    smtp_host: str = ""
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_sender: str = ""
    vector_mode: Literal["disabled"] = "disabled"
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    web_origin: str = "http://localhost:3000"
    query_timeout_seconds: float = Field(default=15.0, gt=0)
    query_memory_limit_mb: int = Field(default=256, ge=1)
    query_row_limit: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_model_route(self) -> "Settings":
        if self.llm_mode != "disabled" and not self.llm_small_model.strip():
            raise ValueError("An active language-model route requires EXECPLUS_LLM_SMALL_MODEL")
        if self.llm_mode != "disabled" and not self.llm_large_model.strip():
            raise ValueError("An active language-model route requires EXECPLUS_LLM_LARGE_MODEL")
        if self.llm_mode == "hosted" and not self.llm_api_key.strip():
            raise ValueError("A hosted language-model route requires EXECPLUS_LLM_API_KEY")
        if bool(self.llm_selection_base_url.strip()) != bool(self.llm_selection_model.strip()):
            raise ValueError("Selection requires both a base URL and model name")
        if self.llm_mode == "disabled" and self.llm_selection_model:
            raise ValueError("Selection requires an active primary model")
        if self.email_mode == "smtp" and not all(
            (self.smtp_host, self.smtp_username, self.smtp_password, self.smtp_sender)
        ):
            raise ValueError("SMTP delivery requires host, username, password and sender")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
