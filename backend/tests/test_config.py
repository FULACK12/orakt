"""Configuration contract tests."""

from pathlib import Path

from app.core.config import Settings


def test_default_storage_layout() -> None:
    settings = Settings(_env_file=None)

    assert settings.hot_data_root == Path("E:/NEWS app/data/hot")
    assert settings.cold_data_root == Path("F:/News data")
    assert settings.cold_archive_min_free_gb == 1024
    assert settings.cold_archive_max_used_percent == 85
    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "qwen3:14b-q4_K_M"
    assert settings.llm_timeout_seconds == 180
    assert settings.research_llm_timeout_seconds == 3_600
    assert settings.llm_max_attempts == 2
    assert settings.llm_max_input_chars == 24_000
    assert settings.llm_fallback_to_mock is True
    assert settings.openai_review_timeout_seconds == 600
    assert settings.embedding_model == "qwen3-embedding:0.6b"
    assert len(settings.cluster_review_secret) >= 32
    assert str(settings.economic_base_url) == "https://api.worldbank.org/v2"
    assert settings.economic_history_start_year == 1960
    assert settings.economic_sync_interval_seconds == 21_600
    assert settings.ucdp_access_token is None
    assert settings.reliefweb_app_name is None
    assert settings.twelve_data_api_key is None
    assert settings.alpha_vantage_api_key is None
    assert settings.alpha_vantage_sync_interval_seconds == 86_400
    assert settings.alpha_vantage_request_interval_seconds == 15
    assert settings.alpha_vantage_price_backfill_per_day == 10
    assert settings.alpha_vantage_price_queue_size == 500
    assert settings.openfigi_api_key is None
    assert settings.openfigi_identity_batch_size == 10
    assert settings.fred_api_key is None
    assert settings.nasa_firms_map_key is None
    assert settings.eia_bulk_max_series_per_dataset == 300
    assert settings.firms_history_days == 1
    assert settings.market_sync_interval_seconds == 3_600
    assert settings.official_evidence_timeout_seconds == 30
    assert settings.causal_validation_enabled is True
    assert settings.causal_validation_window_hours == 336
