from src.config import Settings
from src.services.llm import _provider


def test_temperature_mac_dinh_la_0_khong_phai_0_7():
    s = Settings(_env_file=None)
    assert s.llm_temperature == 0.0


def test_embedding_mac_dinh_la_voyage_4_lite_dim_1024():
    """Đổi từ `bge-m3` sang `voyage-4-lite` (2026-09-01) — đo trên corpus
    36.710 điều khoản: Recall@5 **0,7273 vs 0,5974**.

    Dim vẫn 1024 — đã hỏi chính dữ liệu đã nhúng (`vector_dims`) chứ không tin
    tài liệu nhà cung cấp: cả hai model đều 1024, nên đổi mặc định không cần
    nhúng lại và không đụng schema `vector(1024)`.
    """
    s = Settings(_env_file=None)
    assert s.openrouter_embedding_model_name == "voyageai/voyage-4-lite"
    assert s.openrouter_embedding_dim == 1024


def test_nhanh_tu_vung_TAT_mac_dinh():
    """`bm25_topk=0` = tắt nhánh từ vựng.

    `scripts/sweep_fusion.py` cho cực đại đúng tại 0, và CHỈ MỘT ứng viên từ
    vựng kéo MRR@5 từ 0,4286 xuống 0,2604. `rrf` cộng đều — không có alpha để
    pha loãng, chỉ bật hoặc tắt. Mặc định cũ (`hybrid` + `bge-m3`) đo được
    0,4740, tức tổ hợp TỆ NHẤT trong bốn ô đã chạy.
    """
    s = Settings(_env_file=None)
    assert s.retrieve_bm25_topk == 0
    assert s.retrieve_dense_topk > 0, "tắt cả hai nhánh thì truy hồi trả rỗng"


def test_generate_va_judge_khac_provider_mac_dinh():
    """Kiểm PROVIDER (phần trước dấu '/', xấp xỉ thô của "họ model" — xem
    `_provider()` trong `src/services/llm.py`), không so chuỗi đầy đủ: hai
    model có thể có tên khác nhau nhưng cùng nhà cung cấp (xem test âm bên
    dưới) — self-preference bias, spec 7b.2. Đây không phải bảo đảm, chỉ là
    tín hiệu để cảnh báo."""
    s = Settings(_env_file=None)
    assert _provider(s.openrouter_generate_model_name) != _provider(s.openrouter_judge_model_name)


def test_provider_bat_duoc_cap_nguy_hiem_nhat_du_ten_khac_nhau():
    """Test ÂM: 'gemini-2.5-flash-lite' và 'gemini-2.5-flash' là hai CHUỖI
    khác nhau nhưng CÙNG provider 'google' — đúng cặp spec 7b.2 lo ngại nhất.
    Trước khi sửa, bản cũ của test này so chuỗi đầy đủ (== test_config.py
    trước Task 3, cùng lỗi với `generate_model() != judge_model()`) và sẽ
    XANH nhầm cho cặp này — đo được bằng tay: assert chuỗi != chuỗi -> True
    (qua nhầm), còn assert _provider(...) != _provider(...) -> False (đúng,
    bắt được). Test này xanh nghĩa là so theo provider bắt được ca đó."""
    s = Settings(
        _env_file=None,
        openrouter_generate_model_name="google/gemini-2.5-flash-lite",
        openrouter_judge_model_name="google/gemini-2.5-flash",
    )
    assert s.openrouter_generate_model_name != s.openrouter_judge_model_name  # chuỗi thật sự khác nhau
    assert _provider(s.openrouter_generate_model_name) == _provider(s.openrouter_judge_model_name)  # nhưng cùng họ


def test_database_url_mac_dinh_la_postgres_khong_phai_sqlite():
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql://")


def test_abstain_threshold_bi_chan_trong_khoang_0_1():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, abstain_threshold=1.5)


def test_retrieve_topk_co_the_bang_0_de_tat_mot_nhanh():
    """Task 9 (eval ablation) cần lexical_only/dense_only tắt hẳn nhánh còn lại
    bằng topk=0 — gt=0 (đặt từ commit khởi tạo config.py, trước khi ablation
    tồn tại) chặn giá trị này một cách sai."""
    s = Settings(_env_file=None, retrieve_bm25_topk=0, retrieve_dense_topk=20)
    assert s.retrieve_bm25_topk == 0
    s2 = Settings(_env_file=None, retrieve_bm25_topk=20, retrieve_dense_topk=0)
    assert s2.retrieve_dense_topk == 0


def test_expand_reference_hops_bi_chan_tren_o_3():
    """task-7 review (2026-08-31): `ge=0` một mình không có trần — một giá trị
    sweep vô ý (Task 9 ablation, vd. 10) không còn cách nào cản `expand()` khỏi
    phình tập không kiểm soát được qua nhiều hop liên tiếp."""
    import pytest
    from pydantic import ValidationError

    s = Settings(_env_file=None, expand_reference_hops=3)
    assert s.expand_reference_hops == 3
    with pytest.raises(ValidationError):
        Settings(_env_file=None, expand_reference_hops=4)


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


def test_prompt_path_va_linh_vuc_bonus_co_mac_dinh_an_toan():
    from src.config import Settings

    s = Settings(_env_file=None)
    assert s.assemble_prompt == "prompts/assemble.v2.md"
    assert s.rewrite_prompt == "prompts/rewrite_query.v1.md"
    assert s.linh_vuc_bonus == 0.0, "cộng điểm lĩnh vực phải TẮT mặc định cho tới khi đo được"


def test_route_prompt_mac_dinh_v1():
    from src.config import Settings

    assert Settings(_env_file=None).route_prompt == "prompts/route.v1.md"
