"""Ba lỗ ở BIÊN — cùng một hình dạng: biên tin dữ liệu đến quá mức.

1. `nguon` tính đúng trong assemble rồi biến mất ở biên HTTP (mặc định `[]` của
   pydantic lấp chỗ trống thay vì báo thiếu) — ca thứ BA của "tính năng chết mà
   không lỗi nào nổ", sau `khop_tai_id` và `doc_id`.
2. `facts` từ client ghi đè THAM SỐ nội bộ của rule.
3. `/soat` nhận văn bản không giới hạn kích thước, xử lý đồng bộ trong handler async.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.rules import Rule, check


@pytest.fixture
def c():
    return TestClient(app)


# ── 1. nguon phải sống sót qua biên HTTP ────────────────────────────────────
@pytest.mark.asyncio
async def test_nguon_khong_bi_vut_o_bien_HTTP(client, monkeypatch):
    """`partial_coverage` LUÔN có `citations: []` theo thiết kế. `nguon` là thứ
    DUY NHẤT cho phép giao diện mở được văn bản đang nói tới — mất nó thì người
    dùng nhận một ngõ cụt bằng văn xuôi, đúng thất bại mà docstring của
    `NguonOut` cảnh báo."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.partial_coverage,
                "answer": None, "citations": [], "warnings": [],
                "coverage_note": "Câu hỏi thuộc 84/2015/QH13 …",
                "nguon": [{"doc_id": "84265", "so_ky_hieu": "84/2015/QH13",
                           "bo_luat": "Luật An toàn, vệ sinh lao động"}],
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 200
    assert r.json()["nguon"] == [{"doc_id": "84265", "so_ky_hieu": "84/2015/QH13",
                                  "bo_luat": "Luật An toàn, vệ sinh lao động"}], (
        "route quên truyền `nguon=`; pydantic lấp `[]` mặc định nên không lỗi nào nổ"
    )


# ── 2. facts KHÔNG được ghi đè tham số của rule ─────────────────────────────
def test_facts_khong_ghi_de_duoc_tham_so_cua_rule():
    """`ns = {**tham_so, **facts}` để client đè `bang_thang` — gửi một bảng
    lương toàn số 0 thì rule lương tối thiểu luôn "đạt" bất kể lương thật.
    Rule là DỮ LIỆU DO ĐỘI NGŨ KIỂM SOÁT; input người dùng không được sửa nó."""
    r = Rule(id="x", can_cu="c", muc_do="chan", mo_ta="m",
             can_facts=["luong_thang", "vung"], kiem="luong_thang >= bang[vung]",
             cfg={"id": "x", "can_cu": "c", "muc_do": "chan", "mo_ta": "m",
                  "can_facts": ["luong_thang", "vung"], "kiem": "luong_thang >= bang[vung]",
                  "bang": {"I": 5_000_000}})
    assert check(r, {"luong_thang": 1_000_000, "vung": "I"}) is False, "1tr < 5tr → vi phạm"
    assert check(r, {"luong_thang": 1_000_000, "vung": "I", "bang": {"I": 0}}) is False, (
        "client gửi kèm `bang` phải KHÔNG đổi được kết quả"
    )


@pytest.mark.parametrize("endpoint,them", [
    ("/api/v1/soat", {"text": "x" * 40}),
    ("/api/v1/soan-thao", {}),
])
def test_bien_tu_choi_fact_trung_ten_tham_so(c, endpoint, them):
    r = c.post(endpoint, json={"loai_van_ban": "hdld", "facts": {"bang_thang": {"I": 0}}, **them})
    assert r.status_code == 422, "khoá trùng tên tham số phải bị từ chối RÕ RÀNG, không bỏ qua im lặng"
    assert "bang_thang" in r.text


# ── 3. /soat phải chặn văn bản khổng lồ ─────────────────────────────────────
def test_soat_tu_choi_van_ban_qua_lon(c):
    """`text` không có `max_length`, và `extract_clauses`/`draft_audit` chạy
    ĐỒNG BỘ ngay trong handler async — một payload vài chục MB treo cả tiến
    trình uvicorn (một worker) cho MỌI người dùng khác."""
    r = c.post("/api/v1/soat", json={"loai_van_ban": "hdld", "text": "x" * 2_000_000})
    assert r.status_code == 422


# ── 4. facts của `/ban-thao/{id}/dung` phải có BIÊN ─────────────────────────
@pytest.mark.parametrize("facts,cum", [
    ({f"k{i}": "x" for i in range(41)}, "tối đa"),
    ({"ghi_chu": {"long": "dong"}}, "ghi_chu"),
    ({"ghi_chu": ["a", "b"]}, "ghi_chu"),
    ({"ghi_chu": "x" * 501}, "ghi_chu"),
])
def test_dung_lai_tu_choi_facts_qua_bien(facts, cum):
    """`facts` của endpoint dựng lại đi thẳng vào placeholder `{facts}` của
    `draft_generate` — một lượt LLM TRẢ PHÍ. Không có biên thì mỗi lời gọi mang
    được tới trần body (2 MB) vào prompt đó, tức kẻ gọi tự chọn giá của một
    request. Biên: tối đa 40 khoá, giá trị là chữ/số/đúng-sai/rỗng, chữ dưới 500
    ký tự — 422 với câu tiếng Việt, không phải 500 hay một prompt khổng lồ."""
    from pydantic import ValidationError

    from src.api.routes_ban_thao import DungLaiRequest

    with pytest.raises(ValidationError) as e:
        DungLaiRequest(facts=facts)
    assert cum in str(e.value)


def test_dung_lai_nhan_facts_hop_le():
    """Bốn kiểu giá trị mà `gom_du_kien`/biểu mẫu thật sinh ra phải đi qua được."""
    from src.api.routes_ban_thao import DungLaiRequest

    hop_le = {"ten": "Nguyễn Văn A", "so_ngay": 30, "ty_le": 0.5, "co_phu_luc": True, "ghi_chu": None}
    assert DungLaiRequest(facts=hop_le).facts == hop_le
