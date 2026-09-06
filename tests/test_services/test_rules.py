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

from src.agents.graph_soan_thao import cac_loai, load_checklist_cached
from src.services.checklist import cac_can_cu
from src.services.db import get_engine
from src.services.rules import Rule, check, kiem_tra_can_cu_ton_tai, load_rules, run_rules

RULES_PATH = Path("config/rules.yaml")
RULES = load_rules(RULES_PATH)


# ══ Given rules load correctly, ids unique ══════════════════════════════════


def test_id_duy_nhat_va_KHONG_RULE_NAO_NAM_CHET():
    """id không trùng, và mỗi rule được ÍT NHẤT MỘT checklist khai áp dụng.

    Đếm cứng "đủ 5 rule" là một con số phải sửa mỗi lần thêm rule, và nó không
    khoá được điều đáng khoá. Điều đáng khoá là: rules.yaml là THƯ VIỆN, còn
    checklist mới quyết định rule nào chạy — nên một rule không checklist nào
    khai là một phép kiểm KHÔNG BAO GIỜ CHẠY, nằm trong kho trông như đang bảo
    vệ ai đó.
    """
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids)), f"id trùng lặp trong {RULES_PATH}"
    da_dung = {i for loai in cac_loai() for i in load_checklist_cached(loai).rules}
    assert not set(ids) - da_dung, (
        f"rule không checklist nào khai áp dụng (sẽ không bao giờ chạy): {sorted(set(ids) - da_dung)}"
    )


# ══ lai_suat_vay_toi_da (BLDS Đ468.1) ════════════════════════════════════


def test_lai_suat_20_phan_tram_la_HOP_PHAP_bien_dung():
    v = run_rules(RULES, {"lai_suat_nam_phan_tram": 20})
    assert not any(x.rule_id == "lai_suat_vay_toi_da" for x in v)


def test_lai_suat_20_01_phan_tram_la_VI_PHAM_bien_dung():
    v = run_rules(RULES, {"lai_suat_nam_phan_tram": 20.01})
    assert any(x.rule_id == "lai_suat_vay_toi_da" and x.muc_do == "chan" for x in v)


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


# ══ cam_giu_giay_to / cam_dat_coc — tách khỏi cam_giu_giay_to_dat_coc ══════
# (Đ17 rỗng thân bị bắt bởi phép ratchet dưới — trước bản này nó là rule DUY
# NHẤT đang chạy có can_cu mở ra một đầu đề rỗng)


def test_giu_giay_to_la_VI_PHAM_doc_lap_voi_dat_coc():
    v = run_rules(RULES, {"co_dieu_khoan_giu_giay_to": True, "co_dieu_khoan_dat_coc": False})
    assert any(x.rule_id == "cam_giu_giay_to" and x.muc_do == "chan" for x in v)
    assert not any(x.rule_id == "cam_dat_coc" for x in v)


def test_dat_coc_la_VI_PHAM_doc_lap_voi_giu_giay_to():
    v = run_rules(RULES, {"co_dieu_khoan_giu_giay_to": False, "co_dieu_khoan_dat_coc": True})
    assert any(x.rule_id == "cam_dat_coc" and x.muc_do == "chan" for x in v)
    assert not any(x.rule_id == "cam_giu_giay_to" for x in v)


# ══ tran_phat_vi_pham_hop_dong (LTM 36/2005/QH11 Đ301) ═════════════════════


def test_phat_dung_8_phan_tram_phan_vi_pham_la_HOP_PHAP_bien_dung():
    v = run_rules(
        RULES,
        {"muc_phat_thoa_thuan": 8_000_000, "gia_tri_phan_nghia_vu_bi_vi_pham": 100_000_000},
    )
    assert not any(x.rule_id == "tran_phat_vi_pham_hop_dong" for x in v)


def test_phat_vuot_8_phan_tram_phan_vi_pham_la_VI_PHAM_bien_dung():
    v = run_rules(
        RULES,
        {"muc_phat_thoa_thuan": 8_000_001, "gia_tri_phan_nghia_vu_bi_vi_pham": 100_000_000},
    )
    assert any(x.rule_id == "tran_phat_vi_pham_hop_dong" and x.muc_do == "chan" for x in v)


def test_phat_canh_dung_MAU_SO_khong_chi_canh_con_so_8():
    """Đ301 đặt trần 8% trên giá trị PHẦN NGHĨA VỤ BỊ VI PHẠM, không phải tổng
    giá trị hợp đồng — cùng một `muc_phat_thoa_thuan`, đổi mẫu số từ nhỏ sang
    lớn phải đổi cả phán quyết. Nếu rule (hoặc một bản sửa sau này) lỡ dùng
    tổng giá trị hợp đồng làm mẫu số, test này đỏ: nó không chỉ canh con số 8,
    nó canh chính cái mẫu số được dùng để tính ra con số đó.
    """
    muc_phat = 8_000_000
    vi_pham = run_rules(
        RULES, {"muc_phat_thoa_thuan": muc_phat, "gia_tri_phan_nghia_vu_bi_vi_pham": 50_000_000}
    )
    assert any(x.rule_id == "tran_phat_vi_pham_hop_dong" for x in vi_pham), (
        "8tr phạt trên 50tr giá trị phần bị vi phạm là 16% — phải bị bắt"
    )
    hop_phap_neu_dung_tong_gia_tri = run_rules(
        RULES, {"muc_phat_thoa_thuan": muc_phat, "gia_tri_phan_nghia_vu_bi_vi_pham": 1_000_000_000}
    )
    assert not any(x.rule_id == "tran_phat_vi_pham_hop_dong" for x in hop_phap_neu_dung_tong_gia_tri), (
        "cùng 8tr phạt đó trên 1 tỷ là 0.8% — không bị bắt; hai kết quả PHẢI khác nhau"
    )


# ══ thieu_dieu_khoan_giai_quyet_tranh_chap (LTM Đ317 Khoản 3) ═══════════════


def test_thieu_dieu_khoan_tranh_chap_la_CANH_BAO_khong_phai_CHAN():
    """Đ317 liệt kê HÌNH THỨC giải quyết tranh chấp, không đặt nghĩa vụ phải có
    điều khoản đó — mã hoá việc thiếu thành `chan` sẽ dựng một khẳng định pháp
    luật không đặt ra. Khoá cứng `muc_do` ở đây để một sửa đổi sau này không
    lặng lẽ nâng mức lên `chan`.
    """
    v = run_rules(RULES, {"co_dieu_khoan_giai_quyet_tranh_chap": False})
    ph = [x for x in v if x.rule_id == "thieu_dieu_khoan_giai_quyet_tranh_chap"]
    assert ph and ph[0].muc_do == "canh_bao"


def test_co_dieu_khoan_tranh_chap_thi_KHONG_bao_thieu():
    v = run_rules(RULES, {"co_dieu_khoan_giai_quyet_tranh_chap": True})
    assert not any(x.rule_id == "thieu_dieu_khoan_giai_quyet_tranh_chap" for x in v)


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


# ══ Ratchet — can_cu KHÔNG được mở ra một đầu đề rỗng ══════════════════════
#
# `kiem_tra_can_cu_ton_tai` (và test tích hợp ngay trên) chỉ bắt một loại lỗi:
# can_cu trỏ tới một duong_dan KHÔNG TỒN TẠI. Nó không bắt được loại lỗi thứ
# hai, âm thầm hơn: can_cu trỏ tới một duong_dan CÓ TỒN TẠI nhưng RỖNG THÂN —
# provision đó chỉ có dòng tiêu đề (`btrim(noi_dung) == btrim(tieu_de)`), ví dụ
# "Điều 317. Hình thức giải quyết tranh chấp" mà không có câu luật nào theo
# sau. `ux_provisions_neo_trich_dan` (index đứng sau can_cu viết tay) phủ mọi
# cấp (dieu/khoan/diem/hang_bang) nên vẫn resolve — và `test_MOI_can_cu_TON_TAI`
# vẫn xanh — trong khi trích dẫn đó không mang gì để đọc.
#
# ĐÂY LÀ CHUYỆN NGƯỜI DÙNG, không phải chuyện nội bộ: can_cu không nằm gọn
# trong config/. Nó ra tới response schema (`FindingOut.can_cu`/`doc_id`/
# `khop_tai_id` — `src/models/schemas.py`), và comment ở đó ghi rõ giao diện
# mở panel đối chiếu từ chính hai khoá này. `citation_khong_hop_le` gán
# `can_cu=None` vì "bản thân can_cu đó không tồn tại nên không có gì để mở" —
# tức lớp bảo vệ đó xử ca đường dẫn KHÔNG TỒN TẠI. Một đường dẫn TỒN TẠI mà
# RỖNG THÂN không thuộc ca đó, nên nó đi lọt như một trích dẫn hợp lệ: người
# soát bấm vào, panel mở ra một đầu đề không có thân. Đo được lúc viết test
# này: 48/213 đường dẫn phân biệt trong config/ — 21% số can_cu viết tay —
# rỗng thân, trong một sản phẩm lấy "trích dẫn kiểm chứng được" làm đóng góp
# chính.
#
# BASELINE DƯỚI ĐÂY LÀ NỢ ĐÃ GHI SỔ, KHÔNG PHẢI HÀNH VI ĐÚNG. Test chỉ đỏ khi
# xuất hiện một can_cu MỚI rỗng thân KHÔNG nằm trong danh sách này — tức khi ai
# đó THÊM một trích dẫn hỏng, không phải khi danh sách đã có co lại. Sửa một
# đường dẫn trong danh sách (đẩy nó xuống đúng khoản/điểm mang câu thật) thì
# XOÁ nó khỏi đây — danh sách không tự co, sửa xong mà không xoá thì baseline
# nói dối về việc đã sửa.
#
# 48 CHỖ NÀY KHÔNG CÙNG MỘT LOẠI NỢ — người sửa tiếp theo sẽ dễ đi sai đường
# nếu coi cả 48 là một việc. Phần lớn chỉ là tra "khoản/điểm nào mang đúng câu
# này rồi trỏ xuống đó". Nhưng một số ít là TRIỆU CHỨNG của một rule khẳng
# định HAI việc bằng MỘT can_cu (đúng hình dạng của `cam_giu_giay_to_dat_coc`
# trước khi tách ở task này — Đ17 rỗng thân đúng vì không khoản con nào trỏ
# đủ cả "giữ giấy tờ" lẫn "buộc đặt cọc"). Với loại thứ hai, chọn đại một
# khoản con sẽ TỆ HƠN nguyên trạng: nó ghim một rule hai việc vào trích dẫn
# của một việc, đọc ra một độ chính xác trích dẫn không có thật. Thứ tự câu
# hỏi đúng là "rule/mục này khẳng định MỘT việc không?" TRƯỚC "khoản nào mang
# câu đó?" — không phải ngược lại.
#
# Sinh bằng, KHÔNG gõ tay:
#   SELECT duong_dan FROM provisions
#    WHERE btrim(noi_dung) = btrim(tieu_de) AND duong_dan = ANY(:cac_can_cu)
#   với :cac_can_cu = _tat_ca_can_cu_trong_config() (bên dưới), chạy trực tiếp
#   qua docker exec + psql lúc viết test này (xem báo cáo Task 8).
_CAN_CU_RONG_THAN_DA_GHI_SO = frozenset(
    {
        "36/2005/QH11 > Điều 24",
        "36/2005/QH11 > Điều 34",
        "36/2005/QH11 > Điều 35",
        "36/2005/QH11 > Điều 37",
        "36/2005/QH11 > Điều 44",
        "36/2005/QH11 > Điều 49",
        "45/2019/QH14 > Điều 122",
        "45/2019/QH14 > Điều 124",
        "45/2019/QH14 > Điều 34",
        "45/2019/QH14 > Điều 36",
        "45/2019/QH14 > Điều 45",
        "45/2019/QH14 > Điều 46",
        "45/2019/QH14 > Điều 48",
        "59/2020/QH14 > Điều 157",
        "91/2015/QH13 > Điều 328",
        "91/2015/QH13 > Điều 398",
        "91/2015/QH13 > Điều 431",
        "91/2015/QH13 > Điều 433",
        "91/2015/QH13 > Điều 450",
        "91/2015/QH13 > Điều 465",
        "91/2015/QH13 > Điều 466",
        "91/2015/QH13 > Điều 468",
        "91/2015/QH13 > Điều 470",
        "91/2015/QH13 > Điều 473",
        "91/2015/QH13 > Điều 474",
        "91/2015/QH13 > Điều 476",
        "91/2015/QH13 > Điều 477",
        "91/2015/QH13 > Điều 480",
        "91/2015/QH13 > Điều 481",
        "91/2015/QH13 > Điều 482",
        "91/2015/QH13 > Điều 504",
        "91/2015/QH13 > Điều 515",
        "91/2015/QH13 > Điều 517",
        "91/2015/QH13 > Điều 519",
        "91/2015/QH13 > Điều 520",
        "91/2015/QH13 > Điều 544",
        "91/2015/QH13 > Điều 546",
        "91/2015/QH13 > Điều 549",
        "91/2015/QH13 > Điều 550",
        "91/2015/QH13 > Điều 551",
        "91/2015/QH13 > Điều 552",
        "91/2015/QH13 > Điều 562",
        "91/2015/QH13 > Điều 563",
        "91/2015/QH13 > Điều 564",
        "91/2015/QH13 > Điều 565",
        "91/2015/QH13 > Điều 567",
        "91/2015/QH13 > Điều 569",
        "92/2015/QH13 > Điều 98",
    }
)


def _tat_ca_can_cu_trong_config() -> set[str]:
    """Mọi can_cu-giống-đường-dẫn đang khai trong config/: can_cu của RULES
    cộng can_cu (+ can_cu_goc/can_cu_chi_tiet/khối ngoại lệ) của MỌI checklist.
    Dùng `cac_can_cu` sẵn có của checklist.py — hàm sản phẩm THẬT sự đọc can_cu
    để kiểm tồn tại — thay vì một parser YAML riêng có thể lệch khỏi nó.
    """
    return {r.can_cu for r in RULES} | {
        p for loai in cac_loai() for p in cac_can_cu(load_checklist_cached(loai))
    }


@pytest.mark.integration
def test_KHONG_THEM_can_cu_moi_rong_than():
    """RATCHET, không phải phép canh tuyệt đối — xem comment phía trên
    `_CAN_CU_RONG_THAN_DA_GHI_SO` để hiểu vì sao (49 → giờ 48 chỗ là nợ đã ghi
    sổ, sửa dần, không sửa hết trong một task). Test này chỉ đỏ khi ai đó THÊM
    một can_cu mới trỏ vào một đầu đề rỗng — nó không đỏ vì danh sách nợ có
    sẵn, và cũng không xanh giả nếu danh sách nợ co lại mà quên xoá dòng tương
    ứng ở trên (dòng thừa chỉ vô hại, không che giấu gì thêm).
    """
    with get_engine().connect() as c:
        rong_than_toan_kho = {
            row[0]
            for row in c.execute(
                text("SELECT duong_dan FROM provisions WHERE btrim(noi_dung) = btrim(tieu_de)")
            ).all()
        }
    rong_than_dang_dung = rong_than_toan_kho & _tat_ca_can_cu_trong_config()
    moi = rong_than_dang_dung - _CAN_CU_RONG_THAN_DA_GHI_SO
    assert not moi, (
        f"can_cu MỚI trỏ vào một đầu đề rỗng (không có trong nợ đã ghi sổ): {sorted(moi)} — "
        "trỏ xuống đúng khoản/điểm mang câu thật, đừng thêm vào danh sách nợ."
    )


@pytest.mark.integration
def test_hai_can_cu_moi_cua_task_8_KHONG_rong_than():
    """Khoá riêng hai can_cu mà task này thêm (Đ301, Đ317.3) — cả hai PHẢI qua
    được phép canh và PHẢI KHÔNG có mặt trong danh sách nợ đã ghi sổ. Đây
    chính xác là lý do rule tranh chấp phải trỏ xuống Khoản 3 thay vì Điều 317
    trần: xem ghi_chu của `thieu_dieu_khoan_giai_quyet_tranh_chap` ở rules.yaml.
    """
    can_cu_moi = {
        "36/2005/QH11 > Điều 301",
        "36/2005/QH11 > Điều 317 > Khoản 3",
    }
    assert not (can_cu_moi & _CAN_CU_RONG_THAN_DA_GHI_SO)
    with get_engine().connect() as c:
        rong_than_toan_kho = {
            row[0]
            for row in c.execute(
                text("SELECT duong_dan FROM provisions WHERE btrim(noi_dung) = btrim(tieu_de)")
            ).all()
        }
    assert not (can_cu_moi & rong_than_toan_kho)
