from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "KLAW API"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # OpenRouter — MỘT key, ba endpoint (spec 7b.1, 8.1)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_name: str = "mistralai/mistral-nemo"
    openrouter_generate_model_name: str = "google/gemini-2.5-flash-lite"
    openrouter_judge_model_name: str = "mistralai/mistral-small-3.2-24b-instruct"
    openrouter_embedding_model_name: str = "baai/bge-m3"
    openrouter_embedding_dim: int = Field(default=1024, gt=0)
    openrouter_rerank_model_name: str = "cohere/rerank-4-fast"
    openrouter_rerank_enabled: bool = False

    # temperature 0.0 — spec 8.1: bảng ablation phải tái lập được
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Database
    database_url: str = "postgresql://klaw:klaw@localhost:5432/klaw"

    # Retrieval & chunking
    chunk_max_tokens: int = Field(default=1500, gt=0)
    retrieve_bm25_topk: int = Field(default=20, gt=0)
    retrieve_dense_topk: int = Field(default=20, gt=0)
    rrf_k: int = Field(default=60, gt=0)
    retrieve_final_topk: int = Field(default=10, gt=0)
    expand_reference_hops: int = Field(default=1, ge=0)

    # Verifier
    verify_tier2_enabled: bool = True
    abstain_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    as_of_date: date | None = None

    # Eval
    eval_config_name: str = "full"
    eval_dataset_dir: str = "./eval/datasets"
    eval_result_dir: str = "./eval/results"

    # Data & ingest
    data_raw_dir: str = "./data/raw"
    data_seed_dir: str = "./data/seed"
    moj_api_base: str = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public"
    moj_rate_limit_sleep: float = Field(default=1.5, ge=0.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
