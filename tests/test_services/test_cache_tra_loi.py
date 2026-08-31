"""Khoá cache câu trả lời — phần THUẦN (không DB).

Cache sai khoá không "chậm hơn một chút": nó trả HIỆU LỰC SAI cho một mốc thời
gian khác, hoặc đóng băng câu trả lời của một corpus đã bị thay. Bốn thành phần
khoá dưới đây mỗi cái khoá một chế độ hỏng riêng, nên mỗi cái có một test riêng.
"""

from datetime import date

import pytest

from src.services.cache_tra_loi import KET_QUA_DUOC_CACHE, khoa_cache

_CO_SO = {
    "cau_hoi": "thử việc bao lâu",
    "config_name": "full",
    "as_of": date(2026, 8, 31),
    "checksum": "19135:2026-08-30T14:59:20",
}


def test_cung_dau_vao_cho_cung_khoa():
    assert khoa_cache(**_CO_SO) == khoa_cache(**_CO_SO)


def test_as_of_date_khac_thi_khoa_khac():
    """Hiệu lực PHỤ THUỘC as_of_date — `expand()` lọc văn bản theo nó. Dùng
    chung một câu trả lời cho hai mốc thời gian là trả về hiệu lực sai, tức
    đúng chế độ hỏng mà cả khoá luận tồn tại để chống."""
    assert khoa_cache(**{**_CO_SO, "as_of": date(2020, 1, 1)}) != khoa_cache(**_CO_SO)


def test_corpus_checksum_khac_thi_khoa_khac():
    """Seed lại corpus phải làm cache TỰ hết hiệu lực — không cần ai nhớ xoá tay."""
    assert khoa_cache(**{**_CO_SO, "checksum": "19200:2026-09-01T00:00:00"}) != khoa_cache(**_CO_SO)


def test_config_name_khac_thi_khoa_khac():
    """`config_name` là nhãn ablation (bm25_only, dense_only…) — hai cấu hình
    truy hồi khác nhau cho ra hai câu trả lời khác nhau cho CÙNG câu hỏi."""
    assert khoa_cache(**{**_CO_SO, "config_name": "bm25_only"}) != khoa_cache(**_CO_SO)


@pytest.mark.parametrize(
    "bien_the",
    [
        "  thử việc bao lâu  ",          # khoảng trắng đầu/cuối
        "thử   việc\tbao\nlâu",           # khoảng trắng gộp
        "thử việc bao lâu​",         # zero-width
    ],
)
def test_chuan_hoa_dung_normalize_da_co_nen_bien_the_khoang_trang_cung_khoa(bien_the):
    """CÙNG hàm `verify_tier1.normalize` mà tầng 1 dùng — KHÔNG viết hàm chuẩn
    hoá thứ hai: hai hàm chuẩn hoá là cách chắc chắn để cache bắn nhầm."""
    assert khoa_cache(**{**_CO_SO, "cau_hoi": bien_the}) == khoa_cache(**_CO_SO)


def test_KHONG_casefold_nen_khac_hoa_thi_khoa_khac():
    """`normalize` cố ý KHÔNG casefold (xem docstring của nó — dấu là chữ trong
    tiếng Việt). Hệ quả ở tầng cache: khác hoa/thường là cache MISS, tức tốn
    thêm một lượt LLM. Đó là hướng hỏng AN TOÀN (miss, không phải trả sai), và
    ghi ra đây để nó là một quyết định chứ không phải một phát hiện muộn."""
    assert khoa_cache(**{**_CO_SO, "cau_hoi": "Thử việc bao lâu"}) != khoa_cache(**_CO_SO)


def test_chi_cache_answer_va_partial_coverage():
    """`abstain` KHÔNG vào cache: một lần thiếu căn cứ do lỗi tạm (OpenRouter
    429, DB chậm) sẽ bị đóng băng thành câu trả lời vĩnh viễn "không tìm thấy
    căn cứ". `abstain` là hành vi ĐƯỢC TÍNH ĐIỂM, không phải thứ được hoá đá."""
    assert KET_QUA_DUOC_CACHE == frozenset({"answer", "partial_coverage"})
    assert "abstain" not in KET_QUA_DUOC_CACHE
    assert "out_of_scope" not in KET_QUA_DUOC_CACHE
