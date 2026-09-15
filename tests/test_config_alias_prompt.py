"""Ba prompt phải đặt được từ biến môi trường (spec 2026-09-15f).

`src/config.py` KHÔNG dùng `env_prefix`: field nào cần đọc từ môi trường phải tự
khai `validation_alias`. Thiếu alias thì biến môi trường bị bỏ qua **im lặng** —
không lỗi, không cảnh báo, chỉ là giá trị mặc định.

Đo được 2026-09-15: một lượt eval 77 câu đặt `KLAW_ASSEMBLE_PROMPT` trỏ
`assemble.v4.md`, thực tế chạy v3, tốn $0,68 và cho một bảng so sánh trông như
v4 kém hơn 4,7%. Không ai phát hiện được nếu bảng không in kèm tên prompt.

File này khoá lớp lỗi đó: mọi field prompt và model đều phải có alias.
"""

import pytest

from src.config import Settings


@pytest.mark.parametrize(
    "ten, alias",
    [
        ("assemble_prompt", "KLAW_ASSEMBLE_PROMPT"),
        ("rewrite_prompt", "KLAW_REWRITE_PROMPT"),
        ("route_prompt", "KLAW_ROUTE_PROMPT"),
    ],
)
def test_prompt_dat_duoc_tu_moi_truong(ten, alias, monkeypatch):
    monkeypatch.setenv(alias, "prompts/thu-nghiem.md")
    assert getattr(Settings(_env_file=None), ten) == "prompts/thu-nghiem.md"


@pytest.mark.parametrize("ten", ["assemble_prompt", "rewrite_prompt", "route_prompt"])
def test_van_dat_duoc_bang_tham_so_truc_tiep(ten):
    """Alias KHÔNG được làm mất đường đặt trực tiếp — mọi test của repo dùng nó."""
    assert getattr(Settings(_env_file=None, **{ten: "prompts/x.md"}), ten) == "prompts/x.md"


def test_MOI_field_prompt_va_model_deu_DAT_DUOC_tu_moi_truong(monkeypatch):
    """Bất biến thật không phải "có alias" mà là "đặt được từ môi trường".

    `openrouter_model_name` không có alias nhưng vẫn nhận `OPENROUTER_MODEL_NAME`,
    vì pydantic khớp thẳng tên field viết hoa. `assemble_prompt` hỏng chỉ vì tên
    env tôi chọn (`KLAW_ASSEMBLE_PROMPT`) KHÁC tên field. Kiểm tính chất, không
    kiểm cơ chế — nếu không, test sẽ bắt thêm alias cho những field đang chạy tốt.
    """
    thieu = []
    for ten, f in Settings.model_fields.items():
        if "prompt" not in ten and "model_name" not in ten:
            continue
        alias = f.validation_alias if isinstance(f.validation_alias, str) else ten.upper()
        monkeypatch.setenv(alias, "GIA-TRI-THU")
        if getattr(Settings(_env_file=None), ten) != "GIA-TRI-THU":
            thieu.append(f"{ten} (thử qua {alias})")
        monkeypatch.delenv(alias, raising=False)
    assert thieu == [], f"không đặt được từ môi trường: {thieu}"


def test_mac_dinh_van_la_v3():
    """v4 chưa đo xong thì chưa được thành mặc định."""
    assert Settings(_env_file=None).assemble_prompt == "prompts/assemble.v3.md"
