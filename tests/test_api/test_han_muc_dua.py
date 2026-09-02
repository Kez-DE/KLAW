"""H4 — hạn mức tháng RÒ khi có chùm request song song, và advisory lock KHÔNG vá được.

## Vì sao khoá dùng được ở `kiem_rate_limit` mà không dùng được ở đây

`kiem_rate_limit` giữ hoàn hảo (đo được: 25 request song song, hạn mức 10 → đúng
10 qua, 15 chặn) vì lượt GHI và lượt ĐẾM nằm trong CÙNG một transaction đã khoá:

    pg_advisory_xact_lock(ip) → DELETE cũ → INSERT lượt này → COUNT

Người thứ hai vào khoá đã thấy hàng của người thứ nhất.

`kiem_han_muc_thang` đọc `traces`, mà `traces` chỉ được ghi ở CUỐI một request
dài 10–50 giây, trong một transaction KHÁC, không khoá. Khoá lượt đọc vì thế chỉ
xếp hàng các lượt đọc: cả chùm vẫn đọc đúng con số TRƯỚC chùm, vì chưa ai trong
chùm kịp ghi gì. Đo được, cùng kịch bản (đã dùng 9/10, 25 request song song):

    không khoá        → 25 qua, 0 chặn
    có advisory lock  → 25 qua, 0 chặn   ← khoá không đổi một con số nào

Nên vết vá "thêm `pg_advisory_xact_lock(hashtext('quota:' || sub))`" đã được
THỬ và GỠ BỎ, thay vì ship một cổng trông như đã khoá.

## Vá thật thì cần gì

Phải ĐẶT CHỖ tại cổng, chứ không chỉ đếm: trong cùng một transaction đã khoá,
đếm `traces` CỘNG số lượt đang chạy, rồi ghi một lượt đang chạy của chính mình;
lượt đó được quyết toán (hoặc nhả ra) khi request kết thúc, và một bộ quét dọn
những lượt mồ côi do tiến trình chết.

Đó là một quyết định SẢN PHẨM chưa chốt, không phải một vết vá: nó ghi vào
`traces` — bảng số liệu của khoá luận — ở một thời điểm mới và với một trạng
thái mới, nên "một lượt đang chạy" nghĩa là gì trong chương đánh giá là câu hỏi
phải được trả lời trước. Xem `.superpowers/sdd/va-bao-mat-report.md`.
"""

import concurrent.futures as cf
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.services import bao_ve
from src.services.db import get_engine

_DA_DUNG = 9
_HAN_MUC = 10
_SONG_SONG = 25

_SQL_NEN = text(
    "INSERT INTO traces (id, endpoint, query, config_name, result_type,"
    " latency_ms, cost_usd, cache_hit, user_sub)"
    " VALUES (:id, '/api/v1/tra-cuu', 'nen-test-han-muc', 'x', 'answer', 1, 0, false, :sub)"
)


@pytest.mark.integration
@pytest.mark.xfail(
    reason="H4 chưa vá: hạn mức tháng đọc `traces`, mà `traces` chỉ được ghi ở CUỐI "
           "request — cả chùm song song đều đọc con số trước chùm. Advisory lock đã "
           "thử và ĐO ĐƯỢC là không đổi kết quả; vá thật cần đặt chỗ tại cổng.",
    strict=False,
)
def test_han_muc_thang_KHONG_ro_khi_co_chum_song_song(monkeypatch):
    """Giữ lỗ hổng ở dạng CHẠY ĐƯỢC, không phải một đoạn văn trong runbook.

    Ai làm phần đặt chỗ chỉ cần gỡ `xfail` — test này đã mô tả sẵn tiêu chí đạt.
    """
    sub = str(uuid.uuid4())
    monkeypatch.setattr(bao_ve, "han_muc_thang", lambda plan: _HAN_MUC)

    try:
        with get_engine().begin() as c:
            for _ in range(_DA_DUNG):
                c.execute(_SQL_NEN, {"id": str(uuid.uuid4()), "sub": sub})

        def mot() -> bool:
            try:
                bao_ve.kiem_han_muc_thang(sub, "free")
                return True
            except HTTPException:
                return False

        with cf.ThreadPoolExecutor(max_workers=_SONG_SONG) as ex:
            qua = sum(ex.map(lambda _: mot(), range(_SONG_SONG)))

        assert qua == _HAN_MUC - _DA_DUNG, (
            f"{qua}/{_SONG_SONG} request qua cổng khi chỉ còn "
            f"{_HAN_MUC - _DA_DUNG} suất — hạn mức tháng rò dưới tải song song"
        )
    finally:
        # Bảng `traces` là dữ liệu đo lường của khoá luận: không để lại một dòng nào.
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM traces WHERE user_sub = :sub"), {"sub": sub})
