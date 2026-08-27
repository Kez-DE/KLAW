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
