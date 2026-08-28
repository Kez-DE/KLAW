from src.config import Settings


def test_temperature_mac_dinh_la_0_khong_phai_0_7():
    s = Settings(_env_file=None)
    assert s.llm_temperature == 0.0


def test_embedding_mac_dinh_la_bge_m3_dim_1024():
    s = Settings(_env_file=None)
    assert s.openrouter_embedding_model_name == "baai/bge-m3"
    assert s.openrouter_embedding_dim == 1024


def test_ba_vai_llm_la_ba_model_khac_nhau():
    s = Settings(_env_file=None)
    assert s.openrouter_generate_model_name != s.openrouter_judge_model_name, (
        "judge phải khác họ với generate — self-preference bias, spec 7b.2"
    )


def test_database_url_mac_dinh_la_postgres_khong_phai_sqlite():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql://")


def test_abstain_threshold_bi_chan_trong_khoang_0_1():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, abstain_threshold=1.5)


def test_retrieve_topk_co_the_bang_0_de_tat_mot_nhanh():
    """Task 9 (eval ablation) cần bm25_only/dense_only tắt hẳn nhánh còn lại
    bằng topk=0 — gt=0 (đặt từ commit khởi tạo config.py, trước khi ablation
    tồn tại) chặn giá trị này một cách sai."""
    s = Settings(_env_file=None, retrieve_bm25_topk=0, retrieve_dense_topk=20)
    assert s.retrieve_bm25_topk == 0
    s2 = Settings(_env_file=None, retrieve_bm25_topk=20, retrieve_dense_topk=0)
    assert s2.retrieve_dense_topk == 0


def test_settings_tu_choi_field_la_khong_nuot_im_lang():
    """H3 (review-final-p2): `Settings(rrf_K=5)` từng giữ nguyên mặc định rrf_k=60,
    không warning — đúng kịch bản sweep rrf_k: một lần gõ nhầm là bốn hàng ablation
    bằng nhau và kết luận 'rrf_k không ảnh hưởng'."""
    import pytest

    with pytest.raises(ValueError, match="rrf_K"):
        Settings(_env_file=None, rrf_K=5)


def test_settings_van_bo_qua_key_la_trong_env_file():
    """`.env` chứa key của công cụ khác (LANGCHAIN_*, COHERE_API_KEY…) — chặn
    kwargs KHÔNG được biến thành chặn env file, nếu không app không khởi động nổi."""
    s = Settings()
    assert s.database_url.startswith("postgresql://")
