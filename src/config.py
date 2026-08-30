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

    def __init__(self, **kw: object) -> None:
        """`extra="ignore"` là CỐ Ý cho `.env` (nó chứa key của công cụ khác —
        LANGCHAIN_*, COHERE_API_KEY… — chặn chúng thì app không khởi động nổi),
        nhưng kwargs thì phải NỔ. `Settings(rrf_K=5)` từng lặng lẽ giữ mặc định
        `rrf_k=60`: đúng kịch bản sweep `rrf_k` qua `overlay_settings(**preset)`
        — một lần gõ nhầm là bốn hàng ablation bằng nhau và kết luận sai
        "rrf_k không ảnh hưởng". Kwargs `_`-prefixed là của pydantic (`_env_file`…).
        """
        la = {k for k in kw if not k.startswith("_")} - set(type(self).model_fields)
        if la:
            raise ValueError(f"Settings: field không tồn tại: {sorted(la)}")
        super().__init__(**kw)

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
    # ge=0 (không phải gt=0): eval ablation (Task 9) tắt hẳn một nhánh bằng 0
    # để đo bm25_only/dense_only — 0 là giá trị hợp lệ, không phải lỗi cấu hình.
    retrieve_bm25_topk: int = Field(default=20, ge=0)
    retrieve_dense_topk: int = Field(default=20, ge=0)
    rrf_k: int = Field(default=60, gt=0)
    # ts_rank normalization bitmask (0=không chuẩn hoá, 1=chia 1+log(len),
    # 2=chia len, 4=mean harmonic distance, 32=rank/(rank+1); cộng dồn được).
    # Mặc định 0 của Postgres KHÔNG chuẩn hoá độ dài → top-k toàn chunk dài.
    # =1 chọn THEO ĐO, không đoán: sweep 5 giá trị × 2 (xem `scripts/sweep_bm25.py`,
    # bảng trong `eval/results/report.md`) cho 1 và 33 tốt nhất (Recall@5 0,2143 so
    # với 0,1299 của 0), 2 sụp hẳn (0,013 — chia thẳng độ dài phạt quá tay điều
    # luật dài). Lấy 1 chứ không 33 vì 32 chỉ chia rank+1: biến đổi đơn điệu, đổi
    # THANG ĐIỂM chứ không đổi THỨ TỰ, nên 33 cho y hệt 1 mà khó giải thích hơn.
    bm25_rank_normalization: int = Field(default=1, ge=0, le=63)
    # Bỏ hư từ tiếng Việt khỏi TRUY VẤN trước khi dựng tsquery — 'simple' không
    # có stopword list tiếng Việt nên hư từ thành lexeme và nối OR biến truy hồi
    # thành xếp hạng gần như cả corpus. Cũng chọn theo đo: bật cho +50% tương đối
    # ở MỌI mức normalization (0,2143 → 0,3117 tại normalization=1).
    bm25_strip_stopwords: bool = True
    retrieve_final_topk: int = Field(default=10, gt=0)
    # le=3: một giá trị sweep vô ý (Task 9 ablation) không còn cách nào làm
    # phình tập expand() không kiểm soát được (task-7 review, 2026-08-31).
    expand_reference_hops: int = Field(default=1, ge=0, le=3)

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
