"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NEWSAPP_",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    app_name: str = "NEWS App API"
    environment: str = "development"
    log_level: str = "INFO"
    # Devnet operator-only provenance, not public login authorization.
    solana_writes_enabled: bool = False
    solana_operator_token: SecretStr | None = None
    solana_publisher: str = ""
    solana_namespace: str = "orakt-local-v1"

    hot_data_root: Path = Path("E:/NEWS app/data/hot")
    cold_data_root: Path = Path("F:/News data")
    hot_document_body_chars: int = Field(default=2_000, ge=256, le=50_000)
    fulltext_min_chars: int = Field(default=1_200, ge=600, le=100_000)
    fulltext_verified_short_min_chars: int = Field(default=600, ge=600, le=5_000)
    fulltext_batch_size: int = Field(default=20, ge=1, le=200)
    fulltext_max_response_bytes: int = Field(default=4_000_000, ge=100_000, le=20_000_000)
    fulltext_retry_after_days: int = Field(default=7, ge=1, le=90)
    fulltext_max_concurrency: int = Field(default=8, ge=1, le=32)
    fulltext_domain_delay_seconds: float = Field(default=0.75, ge=0, le=10)
    fulltext_sync_interval_seconds: int = Field(default=300, ge=30, le=86_400)
    fulltext_request_timeout_seconds: float = Field(default=45, ge=5, le=180)
    fulltext_user_agent: str = Field(
        default="NEWS-Map/0.18 personal research full-text archiver",
        min_length=12,
        max_length=255,
    )
    cold_archive_min_free_gb: int = Field(default=1024, ge=1)
    cold_archive_max_used_percent: int = Field(default=85, ge=1, le=99)

    database_url: str = "postgresql+psycopg://newsapp:newsapp_dev_only@localhost:5432/newsapp"
    database_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "newsapp"
    minio_secret_key: str = "newsapp_dev_only"

    llm_provider: Literal["ollama", "llama_cpp", "vllm", "mock"] = "ollama"
    llm_base_url: HttpUrl = Field(default=HttpUrl("http://127.0.0.1:11434"))
    llm_model: str = "qwen3:14b-q4_K_M"
    llm_timeout_seconds: float = Field(default=180, ge=1, le=600)
    research_llm_timeout_seconds: float = Field(default=3_600, ge=60, le=7_200)
    llm_max_attempts: int = Field(default=2, ge=1, le=5)
    llm_max_input_chars: int = Field(default=24_000, ge=1_000, le=1_000_000)
    llm_fallback_to_mock: bool = True
    llm_training_manifest_path: Path | None = None
    embedding_model: str = "qwen3-embedding:0.6b"
    cluster_review_secret: str = Field(
        default="newsapp-local-review-signing-key-change-me",
        min_length=32,
    )
    cluster_watchdog_stall_seconds: int = Field(default=900, ge=60, le=7_200)
    cluster_watchdog_cancel_grace_seconds: int = Field(default=300, ge=30, le=1_800)
    research_watchdog_stall_seconds: int = Field(default=1_200, ge=60, le=7_200)
    research_watchdog_model_stall_seconds: int = Field(default=3_900, ge=60, le=7_200)
    research_watchdog_cancel_grace_seconds: int = Field(default=300, ge=30, le=1_800)
    research_batch_max_attempts: int = Field(default=3, ge=1, le=10)
    economic_base_url: HttpUrl = Field(
        default=HttpUrl("https://api.worldbank.org/v2"),
    )
    economic_history_start_year: int = Field(default=1960, ge=1960, le=2100)
    economic_sync_interval_seconds: int = Field(default=21_600, ge=300)
    economic_request_timeout_seconds: float = Field(default=90, ge=5, le=300)

    ucdp_access_token: SecretStr | None = None
    ucdp_dataset_version: str = Field(
        default="26.0.6",
        pattern=r"^\d+(?:\.\d+){1,4}$",
    )
    ucdp_history_days: int = Field(default=365, ge=1, le=3_650)
    ucdp_page_size: int = Field(default=1_000, ge=1, le=1_000)
    ucdp_sync_interval_seconds: int = Field(default=21_600, ge=3_600)
    ucdp_request_timeout_seconds: float = Field(default=90, ge=5, le=300)
    reliefweb_app_name: str | None = Field(default=None, min_length=3, max_length=255)
    twelve_data_api_key: SecretStr | None = None
    alpha_vantage_api_key: SecretStr | None = None
    alpha_vantage_sync_interval_seconds: int = Field(default=86_400, ge=3_600)
    alpha_vantage_request_timeout_seconds: float = Field(default=90, ge=5, le=300)
    alpha_vantage_request_interval_seconds: float = Field(default=15, ge=12, le=300)
    alpha_vantage_price_backfill_per_day: int = Field(default=10, ge=1, le=20)
    alpha_vantage_price_queue_size: int = Field(default=500, ge=20, le=5_000)
    openfigi_api_key: SecretStr | None = None
    openfigi_request_timeout_seconds: float = Field(default=45, ge=5, le=180)
    openfigi_identity_batch_size: int = Field(default=10, ge=1, le=50)
    fred_api_key: SecretStr | None = None
    eia_api_key: SecretStr | None = None
    nasa_firms_map_key: SecretStr | None = None
    acled_access_key: SecretStr | None = None
    acled_email: str | None = Field(default=None, min_length=3, max_length=320)
    acled_aggregate_history_days: int = Field(default=1_095, ge=28, le=7_300)
    openai_api_key: SecretStr | None = None
    openai_auto_review_enabled: bool = False
    openai_review_model: str = "gpt-5.6-terra"
    openai_review_base_url: HttpUrl = Field(
        default=HttpUrl("https://api.openai.com/v1"),
    )
    openai_review_timeout_seconds: float = Field(default=600, ge=10, le=3_600)
    sec_user_agent: str = Field(
        default="NEWS-Map/0.16 personal research operator",
        min_length=12,
        max_length=255,
    )
    sec_contact_email: SecretStr | None = Field(
        default=None,
        min_length=5,
        max_length=320,
    )
    sec_delisting_evidence_per_day: int = Field(default=3, ge=1, le=20)
    sec_delisting_request_interval_seconds: float = Field(default=0.25, ge=0.1, le=10)
    company_sync_interval_seconds: int = Field(default=86_400, ge=3_600)
    company_price_history_start_year: int = Field(default=1900, ge=1900, le=2100)
    china_equity_history_start_year: int = Field(default=2015, ge=1990, le=2100)
    china_equity_leaders_per_sector: int = Field(default=10, ge=1, le=20)
    china_equity_ranking_days: int = Field(default=90, ge=30, le=365)
    china_equity_sync_interval_seconds: int = Field(default=86_400, ge=3_600)
    eia_bulk_datasets: str = (
        "STEO,INTL,TOTAL,PET,NG,SEDS,AEO.2026,PET_IMPORTS,COAL,EMISS"
    )
    eia_bulk_max_series_per_dataset: int = Field(default=300, ge=10, le=5_000)
    eia_bulk_max_observations_per_series: int = Field(
        default=2_500,
        ge=100,
        le=100_000,
    )
    eia_bulk_sync_interval_seconds: int = Field(default=86_400, ge=3_600)
    eia_bulk_request_timeout_seconds: float = Field(default=900, ge=30, le=3_600)
    firms_sources: str = "VIIRS_NOAA20_NRT,VIIRS_NOAA21_NRT"
    firms_area: str = "world"
    firms_history_days: int = Field(default=1, ge=1, le=5)
    firms_grid_degrees: float = Field(default=0.25, ge=0.05, le=2.0)
    firms_max_clusters: int = Field(default=1_500, ge=100, le=10_000)
    firms_sync_interval_seconds: int = Field(default=1_800, ge=300)
    firms_request_timeout_seconds: float = Field(default=180, ge=10, le=600)
    market_sync_interval_seconds: int = Field(default=3_600, ge=300)
    entry_calibration_interval_seconds: int = Field(default=86_400, ge=3_600)
    entry_calibration_min_signals: int = Field(default=30, ge=10, le=10_000)
    daily_equity_ai_report_budget: int = Field(default=12, ge=0, le=50)
    daily_equity_ai_event_report_budget: int = Field(default=4, ge=0, le=20)
    market_request_timeout_seconds: float = Field(default=30, ge=5, le=120)
    official_evidence_timeout_seconds: float = Field(default=30, ge=5, le=120)
    causal_validation_enabled: bool = True
    causal_validation_window_hours: int = Field(
        default=336,
        ge=24,
        le=8_760,
    )
    gdelt_sync_interval_seconds: int = Field(default=21_600, ge=900)
    gdelt_request_timeout_seconds: float = Field(default=30, ge=10, le=300)
    gdelt_records_per_topic: int = Field(default=125, ge=10, le=250)
    gdelt_request_interval_seconds: float = Field(default=900, ge=5, le=1_800)
    gdelt_max_attempts: int = Field(default=1, ge=1, le=5)


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object per process."""
    return Settings()
