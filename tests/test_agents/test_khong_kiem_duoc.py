"""`khong_kiem_duoc` phải sống sót tới biên HTTP, không bị đọc lại từ chuỗi.

`rules.Violation` mang cờ `khong_kiem_duoc=True` khi thiếu fact — phân biệt
"chưa biết" với "vi phạm thật", bất biến trung tâm của rule engine
(`check() -> bool | None`). `draft_audit` bỏ cờ đó khi dựng `AuditFinding`, nên
frontend phải **đọc lại dấu hiệu từ chuỗi** `" — không kiểm được: thiếu "`.

Hậu quả đo được TRƯỚC khi frontend tự vá: một rule **chưa hề được kiểm** đeo
nhãn *"Trái quy định"* — giao diện nói văn bản người dùng SAI LUẬT trong khi
máy chỉ thiếu dữ liệu. Đúng lời nói dối mà `bool | None` sinh ra để tránh, bị
đánh mất ở tầng cuối.

Buộc giao diện vào hình dạng một câu tiếng Việt là buộc nó vào thứ sẽ đổi: sửa
câu thông báo là làm hỏng phân loại, và không test nào đỏ.
"""

import pytest

from src.agents.nodes.draft_audit import draft_audit
from src.services.checklist import load_checklist
from src.services.rules import load_rules

from pathlib import Path

RULES = load_rules(Path("config/rules.yaml"))
CHECKLIST = load_checklist(Path("config/checklist_hdld.yaml"))


def test_finding_mang_co_khong_kiem_duoc_khi_thieu_fact():
    st = draft_audit({"clauses": [], "facts": {}, "nganh": "thuong_mai", "self_audit": False},
                     RULES, CHECKLIST, {})
    trai_luat = [f for f in st["audit_report"].findings if f.loai == "trai_luat"]
    assert trai_luat, "không fact nào → mọi rule phải ra finding 'chưa kiểm được'"
    assert all(f.khong_kiem_duoc for f in trai_luat), (
        "cờ phải đi kèm finding, không để tầng trên suy lại từ chuỗi thông báo"
    )


@pytest.mark.asyncio
async def test_co_song_sot_qua_bien_HTTP(client):
    r = await client.post("/api/v1/soat", json={
        "loai_van_ban": "hdld", "text": "Điều 1. Công việc và địa điểm làm việc. " * 3,
    })
    assert r.status_code == 200
    fs = [f for f in r.json()["audit_report"]["findings"] if f["loai"] == "trai_luat"]
    assert fs, "không gửi facts → phải có finding chưa kiểm được"
    assert all(f["khong_kiem_duoc"] is True for f in fs), (
        "pydantic vứt field không khai báo trong im lặng — đây là ca thứ TƯ của cùng kiểu hỏng"
    )
