from pathlib import Path

from src.services.prompts import messages


def test_soul_v2_duoc_tiem_va_co_ba_cau_moi():
    soul = "\n".join(m["content"] for m in messages("x") if m.get("role") == "system")
    assert "chọn nhánh hiển nhiên hoặc phổ biến nhất" in soul
    assert "Trả lời trước, giải thích sau" in soul
    assert "bảng chỉ đi bằng trường `bang`" in soul
    assert "thay vì chọn bừa một nhánh" not in soul


def test_bo_luat_agent_co_qt5():
    md = Path("docs/bo-luat-agent.md").read_text(encoding="utf-8")
    assert "### QT-5" in md and "hỏi chỉ khi đổi kết quả" in md
