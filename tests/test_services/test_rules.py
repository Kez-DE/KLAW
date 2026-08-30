"""Rule engine tests — config/rules.yaml is the single source of legality
rules; this file proves three things the thesis depends on:

1. Every `can_cu` resolves to a real `provisions.duong_dan` — a rule citing
   a nonexistent article would make the whole audit report worthless while
   looking fine (`test_MOI_can_cu_TON_TAI_trong_DB`,
   `test_can_cu_gia_bi_bat_KHONG_can_DB_that`).
2. A missing fact is reported as "could not check", never silently treated
   as compliant or as a violation (`test_check_*`, `test_thieu_fact_thi_*`).
3. `rules.py` never grows a Python branch per rule id — editing `kiem:` in
   YAML is the only thing needed to add a rule
   (`test_them_rule_moi_qua_YAML_khong_can_sua_python`).
"""

from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from src.services.db import get_engine
from src.services.rules import Rule, check, kiem_tra_can_cu_ton_tai, load_rules, run_rules

RULES = load_rules(Path("config/rules.yaml"))


# ══ Given rules load correctly, ids unique ══════════════════════════════════


def test_du_5_rule_va_id_duy_nhat():
    ids = [r.id for r in RULES]
    assert len(ids) == 5 and len(set(ids)) == 5


# ══ thu_viec_toi_da ══════════════════════════════════════════════════════


def test_thu_viec_90_ngay_cho_cong_viec_khac_la_VI_PHAM():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 90, "nhom_chuc_danh": "cong_viec_khac"})
    assert any(x.rule_id == "thu_viec_toi_da" for x in v)


def test_thu_viec_180_ngay_cho_quan_ly_doanh_nghiep_la_HOP_PHAP():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 180, "nhom_chuc_danh": "quan_ly_doanh_nghiep"})
    assert not any(x.rule_id == "thu_viec_toi_da" for x in v)


def test_thu_viec_181_ngay_cho_quan_ly_la_VI_PHAM_bien_dung():
    v = run_rules(RULES, {"thoi_gian_thu_viec_ngay": 181, "nhom_chuc_danh": "quan_ly_doanh_nghiep"})
    assert any(x.rule_id == "thu_viec_toi_da" for x in v)


# ══ luong_thu_viec_toi_thieu ═════════════════════════════════════════════


def test_luong_thu_viec_84_phan_tram_la_VI_PHAM():
    v = run_rules(RULES, {"luong_thu_viec": 8_400_000, "luong_chinh_thuc": 10_000_000})
    assert any(x.rule_id == "luong_thu_viec_toi_thieu" for x in v)


def test_luong_thu_viec_dung_85_phan_tram_la_HOP_PHAP():
    v = run_rules(RULES, {"luong_thu_viec": 8_500_000, "luong_chinh_thuc": 10_000_000})
    assert not any(x.rule_id == "luong_thu_viec_toi_thieu" for x in v)


# ══ luong_toi_thieu_vung ═════════════════════════════════════════════════


def test_luong_duoi_toi_thieu_vung_I_la_VI_PHAM():
    v = run_rules(RULES, {"luong_thang": 5_000_000, "vung": "I"})
    assert any(x.rule_id == "luong_toi_thieu_vung" for x in v)


def test_thieu_fact_thi_KHONG_bao_vi_pham_ma_bao_khong_kiem_duoc():
    v = run_rules(RULES, {"luong_thang": 5_000_000})  # thiếu `vung`
    lq = [x for x in v if x.rule_id == "luong_toi_thieu_vung"]
    assert lq and lq[0].khong_kiem_duoc is True, "thiếu fact phải báo 'không kiểm được', KHÔNG được im lặng cho qua"


# ══ cam_phat_tien_nld ═══════════════════════════════════════════════════


def test_dieu_khoan_phat_tien_la_VI_PHAM():
    assert any(x.rule_id == "cam_phat_tien_nld" for x in run_rules(RULES, {"co_dieu_khoan_phat_tien": True}))


# ══ check(): None vs False vs True must never be conflated ═════════════════
# (mandatory requirement #1, beyond the brief)


def test_check_thieu_fact_tra_ve_None_dung_bang_identity():
    rule = next(r for r in RULES if r.id == "luong_toi_thieu_vung")
    ket_qua = check(rule, {"luong_thang": 5_000_000})  # thiếu `vung`
    assert ket_qua is None, "check() phải trả về None (identity), không phải False/0/''"


def test_check_vi_pham_tra_ve_False_dung_bang_identity():
    rule = next(r for r in RULES if r.id == "thu_viec_toi_da")
    ket_qua = check(rule, {"thoi_gian_thu_viec_ngay": 90, "nhom_chuc_danh": "cong_viec_khac"})
    assert ket_qua is False


def test_check_hop_phap_tra_ve_True_dung_bang_identity():
    rule = next(r for r in RULES if r.id == "thu_viec_toi_da")
    ket_qua = check(rule, {"thoi_gian_thu_viec_ngay": 5, "nhom_chuc_danh": "cong_viec_khac"})
    assert ket_qua is True


def test_thieu_fact_KHONG_duoc_tao_violation_nhu_vi_pham_that():
    """Bug thật nếu code gọi dùng `if not check(...)`: None và False đều
    falsy trong Python, nên một document CHỈ THIẾU DỮ LIỆU sẽ bị đọc nhầm
    thành vi phạm. run_rules dùng `is None` / `is False` tường minh bên
    trong — test này khoá lại: ca thiếu fact phải có khong_kiem_duoc=True,
    không được lẫn với Violation của một vi phạm thật.
    """
    v = run_rules(RULES, {"luong_thang": 5_000_000})  # thiếu `vung`
    lq = next(x for x in v if x.rule_id == "luong_toi_thieu_vung")
    assert lq.khong_kiem_duoc is True


# ══ Rules are DATA — a new rule must need zero Python changes ══════════════
# (mandatory requirement #2, beyond the brief)


def test_them_rule_moi_qua_YAML_khong_can_sua_python(tmp_path):
    """Chứng minh rules.py không có nhánh Python theo từng rule id: một rule
    HOÀN TOÀN MỚI, với công thức chưa từng xuất hiện ở 5 rule gốc (số học +
    so sánh trên hai fact), chạy đúng chỉ bằng cách thêm YAML — không sửa
    một dòng nào trong src/services/rules.py. can_cu ở đây là placeholder,
    KHÔNG phải một trích dẫn thật (test này không gọi kiem_tra_can_cu_ton_tai).
    """
    yaml_moi = tmp_path / "rules_moi.yaml"
    yaml_moi.write_text(
        """
rules:
  - id: tuoi_lao_dong_toi_thieu
    can_cu: "TEST/0000 > Điều 0"
    muc_do: chan
    mo_ta: "Người lao động chưa đủ tuổi lao động tối thiểu"
    can_facts: [tuoi_nld]
    tuoi_toi_thieu: 15
    kiem: tuoi_nld >= tuoi_toi_thieu
""",
        encoding="utf-8",
    )
    rules_moi = load_rules(yaml_moi)
    assert check(rules_moi[0], {"tuoi_nld": 14}) is False
    assert check(rules_moi[0], {"tuoi_nld": 15}) is True
    assert check(rules_moi[0], {}) is None


def test_kiem_khong_duoc_goi_ham_bi_tu_choi_luc_load(tmp_path):
    """`kiem` không phải chỗ chạy mã tuỳ ý — một biểu thức gọi hàm (kể cả hàm
    built-in vô hại như `len`) phải bị load_rules từ chối ngay, không được
    lặng lẽ chấp nhận rồi thất bại khó hiểu lúc check().
    """
    yaml_xau = tmp_path / "rules_xau.yaml"
    yaml_xau.write_text(
        """
rules:
  - id: xau
    can_cu: "45/2019/QH14 > Điều 25"
    muc_do: chan
    mo_ta: x
    can_facts: [a]
    kiem: "len(a) > 0"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="không được phép"):
        load_rules(yaml_xau)


# ══ load_rules fails loud — never silently drops a broken rule ═════════════
# (mandatory requirement #3, beyond the brief)


def test_yaml_sai_cu_phap_thi_load_rules_LOI(tmp_path):
    p = tmp_path / "sai.yaml"
    p.write_text("rules: [{id: a, kiem: 'a <'}\n", encoding="utf-8")  # thiếu ] và } đóng
    with pytest.raises(yaml.YAMLError):
        load_rules(p)


def test_thieu_truong_bat_buoc_thi_load_rules_LOI(tmp_path):
    p = tmp_path / "thieu.yaml"
    p.write_text(
        """
rules:
  - id: khong_co_can_cu
    muc_do: chan
    mo_ta: x
    can_facts: []
    kiem: "1 == 1"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="can_cu"):
        load_rules(p)


def test_id_trung_lap_thi_load_rules_LOI(tmp_path):
    p = tmp_path / "trung.yaml"
    p.write_text(
        """
rules:
  - id: trung
    can_cu: "45/2019/QH14 > Điều 25"
    muc_do: chan
    mo_ta: x
    can_facts: []
    kiem: "1 == 1"
  - id: trung
    can_cu: "45/2019/QH14 > Điều 26"
    muc_do: chan
    mo_ta: y
    can_facts: []
    kiem: "1 == 1"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="trùng lặp"):
        load_rules(p)


def test_can_cu_gia_bi_bat_KHONG_can_DB_that():
    """Chứng minh test tích hợp bên dưới THỰC SỰ có khả năng đỏ: dùng một tập
    duong_dan giả (không đụng Postgres) để khoá hành vi 'raise khi can_cu lạ'
    của kiem_tra_can_cu_ton_tai — bằng chứng chạy được, nhanh, không phụ
    thuộc DB, thay vì chỉ tin lời rằng test tích hợp 'sẽ' đỏ.
    """
    rule_gia = Rule(
        id="gia",
        can_cu="00/0000/XX-YY > Điều 0",
        muc_do="chan",
        mo_ta="x",
        can_facts=[],
        kiem="1 == 1",
        cfg={},
    )
    with pytest.raises(ValueError, match="00/0000/XX-YY"):
        kiem_tra_can_cu_ton_tai([rule_gia], duong_dan_hop_le={"45/2019/QH14 > Điều 25"})

    # Chiều ngược lại: không raise khi mọi can_cu đều có trong tập hợp lệ.
    kiem_tra_can_cu_ton_tai(RULES, duong_dan_hop_le={r.can_cu for r in RULES})


# ══ Integration — every real can_cu must exist in the real DB ══════════════
# Global Constraint of Task 2.


@pytest.mark.integration
def test_MOI_can_cu_TON_TAI_trong_DB():
    """Rule trích dẫn điều luật không tồn tại thì audit report vô giá trị."""
    kiem_tra_can_cu_ton_tai(RULES)  # đọc DB thật qua get_engine(); raise nếu thiếu can_cu nào


@pytest.mark.integration
def test_can_cu_khop_dung_provisions_duong_dan_that():
    """Đối chiếu trực tiếp, không qua kiem_tra_can_cu_ton_tai, để hai đường
    kiểm tra (hàm sản phẩm + truy vấn độc lập ngay trong test) không cùng che
    giấu một lỗi chung.
    """
    with get_engine().connect() as c:
        co = {r[0] for r in c.execute(text("SELECT duong_dan FROM provisions")).all()}
    thieu = [r.can_cu for r in RULES if r.can_cu not in co]
    assert not thieu, f"căn cứ không có trong DB: {thieu}"
