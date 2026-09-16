"""Đo phần metadata của một lượt `run_cau_tra_loi` — hàm THUẦN, không cần
graph/mạng/DB.

Vì sao có tệp này: hai lượt đo chỉ so được với nhau khi biết chúng chạy trên
cùng model, cùng corpus, cùng `as_of_date` và cùng trạng thái cache. Các tệp
kết quả cũ trong `eval/results/` không ghi model, nên `glm/v3.json`
(`trung_dan=0.364`) và `soul-v4/v3-77.json` (`0.662`) — CÙNG `assemble.v3` —
không thể đối chiếu được nữa. Metadata phải nằm trong chính tệp kết quả, không
nằm trong tên tệp hay trí nhớ người chạy.
"""

from datetime import date

from eval.run_cau_tra_loi import _moi_truong, _p95


def test_moi_truong_ghi_model_tung_vai_tu_settings():
    from src.config import get_settings

    s = get_settings()
    mt = _moi_truong(dem={"chunks": 1, "provisions": 2, "documents": 3})

    assert mt["model"]["chinh"] == s.openrouter_model_name
    assert mt["model"]["generate"] == s.openrouter_generate_model_name
    assert mt["model"]["judge"] == s.openrouter_judge_model_name
    assert mt["model"]["embedding"] == s.openrouter_embedding_model_name


def test_moi_truong_giu_nguyen_so_dem_corpus_duoc_truyen_vao():
    mt = _moi_truong(dem={"chunks": 14770, "provisions": 43720, "documents": 1634})
    assert mt["corpus"] == {"chunks": 14770, "provisions": 43720, "documents": 1634}


def test_moi_truong_ghi_as_of_date_dang_iso_va_trang_thai_cache():
    mt = _moi_truong(dem={})
    date.fromisoformat(mt["as_of_date"])  # ném ValueError nếu sai định dạng
    assert isinstance(mt["cache_ttl_ngay"], int)


def test_moi_truong_khong_mang_theo_api_key():
    """Tệp kết quả được commit vào `eval/results/`, nên nó không được chứa khoá."""
    phang = repr(_moi_truong(dem={}))
    assert "sk-" not in phang
    assert "api_key" not in phang.lower()


def test_p95_lay_moc_95_phan_tram_khong_phai_lon_nhat():
    assert _p95([1.0]) == 1.0
    assert _p95([]) == 0.0
    # 20 mẫu: p95 là mẫu thứ 19 (index 18) sau khi sắp xếp, không phải 100.0
    assert _p95([100.0] + [1.0] * 19) == 1.0
    assert _p95([float(i) for i in range(1, 21)]) == 19.0
