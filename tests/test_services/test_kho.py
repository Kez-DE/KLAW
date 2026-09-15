"""Câu hỏi VỀ KHO — số liệu thuần SQL, và một câu đóng không model nào xoá được.

ĐO ĐƯỢC 2026-09-02, trước Pha 1: "Hiện tại có bao nhiêu bộ luật?" đi đường tra
cứu NỘI DUNG luật, truy hồi 10 kết quả, mở rộng ra 30 điều khoản tầng sâu, sinh
**0 luận điểm**, rồi trả `abstain` với `answer` rỗng. Người hỏi nhận màn hình
trắng trong khi câu trả lời là một phép `count(*)`.

Ràng buộc mà nhóm test này canh — quan trọng hơn con số đúng: kho là một tập
được CHỌN cho đề tài, không phải một cuộc tổng điều tra. "Trong kho của mình
hiện có 6 Bộ luật" là sự thật kiểm được; "Việt Nam hiện có 6 Bộ luật" là ảo giác
— và là loại verifier KHÔNG BẮT ĐƯỢC, vì không có trích dẫn nào để đối chiếu.
Nên câu giới hạn phạm vi phải là HẰNG SỐ trong mã, và mọi đường trả lời đều
phải đi qua nó.

Phần lớn test ở đây chạy trên tầng THUẦN (`dung_cau_tra_loi`) chứ không cần
Postgres: guard chống ảo giác phải xanh/đỏ trong bộ test mặc định
(`-m "not integration"`), không phải chỉ khi có DB.
"""

import re
from datetime import date

import pytest

from src.models.schemas import Bang
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import (
    CAU_GIOI_HAN,
    dung_bang,
    dung_cau_tra_loi,
    moi_so_hieu_trong,
    tra_loi_ve_kho,
    xin_dang_bang,
)


def _vb(so, ten, loai="Bộ luật", depth="deep", verdict=V.con_hieu_luc,
        tin_cay="cao", ly_do="không có tín hiệu chấm dứt nào", linh_vuc=None):
    return {"so_ky_hieu": so, "ten": ten, "loai_van_ban": loai, "depth": depth,
            "hieu_luc": Effectivity(verdict, tin_cay, ly_do), "linh_vuc": linh_vuc}


# Sáu Bộ luật hiện hành: một `con_hieu_luc`, năm `mot_phan_khong_xac_dinh` —
# ĐÚNG phân bố đo được trên DB thật 2026-09-02, không phải một fixture đẹp.
HIEN_HANH = [
    _vb("91/2015/QH13", "Bộ luật Dân sự số 91/2015/QH13"),
    _vb("100/2015/QH13", "Bộ luật Hình sự số 100/2015/QH13",
        verdict=V.mot_phan_khong_xac_dinh, tin_cay="thap", ly_do="bị 59/2024/QH15 sửa đổi"),
    _vb("101/2015/QH13", "Bộ luật Tố tụng hình sự số 101/2015/QH13",
        verdict=V.mot_phan_khong_xac_dinh, tin_cay="thap", ly_do="bị 02/2021/QH15 sửa đổi"),
    _vb("92/2015/QH13", "Bộ luật Tố tụng dân sự số 92/2015/QH13",
        verdict=V.mot_phan_khong_xac_dinh, tin_cay="thap", ly_do="bị 59/2020/QH14 sửa đổi"),
    _vb("45/2019/QH14", "Bộ Luật lao động số 45/2019/QH14",
        verdict=V.mot_phan_khong_xac_dinh, tin_cay="thap", ly_do="bị 19/2023/QH15 sửa đổi"),
    _vb("95/2015/QH13", "Bộ luật Hàng hải số 95/2015/QH13",
        verdict=V.mot_phan_khong_xac_dinh, tin_cay="thap", ly_do="bị 12/2017/QH14 sửa đổi"),
]

# Sáu bản ĐÃ BỊ THAY, vẫn nằm trong `documents` với cùng `loai_van_ban='Bộ
# luật'`. Đây là cái bẫy: `SELECT count(*) WHERE loai_van_ban='Bộ luật'` trả 12.
DA_THAY = [
    _vb("10/2012/QH13", "Bộ luật Lao động số 10/2012/QH13", depth="shallow",
        verdict=V.het_hieu_luc, ly_do="ngày hết hiệu lực 2021-01-01 đã qua"),
    _vb("15/1999/QH10", "Bộ luật Hình sự số 15/1999/QH10", depth="shallow",
        verdict=V.het_hieu_luc, ly_do="ngày hết hiệu lực 2018-01-01 đã qua"),
    _vb("19/2003/QH11", "Bộ luật Tố tụng hình sự số 19/2003/QH11", depth="shallow",
        verdict=V.het_hieu_luc, ly_do="ngày hết hiệu lực 2018-01-01 đã qua"),
    _vb("24/2004/QH11", "Bộ luật Tố tụng dân sự số 24/2004/QH11", depth="shallow",
        verdict=V.bi_thay_the, ly_do="bị 92/2015/QH13 thay thế"),
    _vb("33/2005/QH11", "Bộ luật Dân sự số 33/2005/QH11", depth="shallow",
        verdict=V.bi_thay_the, ly_do="bị 91/2015/QH13 thay thế"),
    _vb("40/2005/QH11", "Bộ luật Hàng hải Việt Nam số 40/2005/QH11", depth="shallow",
        verdict=V.bi_thay_the, ly_do="bị 95/2015/QH13 thay thế"),
]

KHO = [
    *HIEN_HANH, *DA_THAY,
    _vb("45/2013/QH13", "Luật Việc làm số 38/2013/QH13", loai="Luật"),
    _vb("84/2015/QH13", "Luật An toàn, vệ sinh lao động", loai="Luật", depth="shallow"),
    _vb("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP hướng dẫn Bộ luật Lao động",
        loai="Nghị định"),
    _vb("90/2019/NĐ-CP", "Nghị định 90/2019/NĐ-CP về lương tối thiểu vùng",
        loai="Nghị định", depth="shallow", verdict=V.bi_thay_the,
        ly_do="bị 74/2024/NĐ-CP thay thế"),
]

CAU_HOI_TOM_TAT = "Hiện tại có bao nhiêu bộ luật?"
MOI_DANG_CAU_HOI = (
    CAU_HOI_TOM_TAT,
    "kho của bạn phủ những gì?",
    "có Nghị định 145/2020 không?",
    "có Nghị định 999/2099/NĐ-CP không?",
    "Bộ luật Lao động 10/2012/QH13 còn trong kho chứ?",
)


# ══ Đếm đúng ════════════════════════════════════════════════════════════════

def test_dem_bo_luat_ra_6_khong_phai_12():
    """Cái bẫy trung tâm của Pha 1. `loai_van_ban='Bộ luật'` có 12 dòng; sáu
    trong đó đã bị thay. Lọc bằng verdict hiệu lực, KHÔNG bằng `tinh_trang`
    (sáu bản cũ đều `chua_xac_dinh`) và KHÔNG bằng `depth` (nói mức đã nạp,
    không nói hiệu lực)."""
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, KHO)
    assert "Bộ luật: 6" in out, out
    assert "Bộ luật: 12" not in out


def test_sau_bo_luat_duoc_neu_dich_danh_va_ban_da_thay_thi_khong():
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, KHO)
    for r in HIEN_HANH:
        assert r["ten"] in out, f"thiếu {r['so_ky_hieu']}"
    for r in DA_THAY:
        assert r["so_ky_hieu"] not in out, f"{r['so_ky_hieu']} đã bị thay, không được liệt kê"


def test_muc_phu_theo_depth_duoc_noi_ra():
    """`deep` có toàn văn tra được tới điều khoản; `shallow`/`metadata` chỉ có
    số hiệu và tên (một hàng `mo_dau`, xem migration 016). Gộp hai thứ đó lại
    thành một con số là nói quá mức phủ của kho."""
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, KHO)
    assert "Luật: 2" in out and "1 có toàn văn" in out


# ══ Không phát biểu thay cho nền pháp luật Việt Nam ═════════════════════════

# `\d` ngay sau: câu ảo giác luôn kèm một con số. "văn bản pháp luật Việt Nam"
# trong câu giới hạn phạm vi KHÔNG khớp, và đó là chủ đích.
_RE_AO_GIAC = re.compile(r"Việt Nam\s+(?:hiện\s+|đang\s+)*có\s+\d")


def test_regex_ao_giac_bat_duoc_cau_mau():
    """Positive control — không có nó thì test dưới xanh vì regex hỏng, không
    vì mã đúng."""
    assert _RE_AO_GIAC.search("Việt Nam hiện có 6 Bộ luật")
    assert _RE_AO_GIAC.search("Việt Nam có 130 văn bản")
    assert not _RE_AO_GIAC.search(CAU_GIOI_HAN)


@pytest.mark.parametrize("cau_hoi", MOI_DANG_CAU_HOI)
def test_khong_bao_gio_phat_bieu_thay_nen_phap_luat_viet_nam(cau_hoi):
    assert not _RE_AO_GIAC.search(dung_cau_tra_loi(cau_hoi, KHO))


@pytest.mark.parametrize("cau_hoi", MOI_DANG_CAU_HOI)
def test_moi_duong_tra_loi_deu_dong_bang_cau_gioi_han_pham_vi(cau_hoi):
    """So với HẰNG SỐ, không hardcode lại chuỗi: nếu ai đó sửa lời câu đóng thì
    test này vẫn canh đúng bất biến (mọi nhánh đều mang nó), thay vì đỏ vì lời."""
    assert CAU_GIOI_HAN in dung_cau_tra_loi(cau_hoi, KHO)


@pytest.mark.parametrize("cau_hoi", MOI_DANG_CAU_HOI)
def test_moi_duong_tra_loi_deu_xung_trong_kho_cua_toi(cau_hoi):
    assert "kho của tôi" in dung_cau_tra_loi(cau_hoi, KHO)


# ══ Có/không một văn bản cụ thể ═════════════════════════════════════════════

@pytest.mark.parametrize("cau_hoi,mong", [
    ("có Nghị định 145/2020 không?", "145/2020"),
    ("kho có 145/2020/NĐ-CP chứ?", "145/2020"),
    ("Bộ luật Lao động 45/2019/QH14 có không", "45/2019"),
    ("có thông tư 10/2020/TT-BLĐTBXH không", "10/2020"),
    (CAU_HOI_TOM_TAT, None),
    ("kho của bạn phủ những gì?", None),
    ("có bao nhiêu nghị định về lao động", None),
    # Ngày, KHÔNG phải số hiệu — câu thật trong `golden_qa.yaml`. Không có
    # lookbehind trong `_RE_SO_HIEU` thì "1/1/2026" đọc thành số hiệu "1/2026".
    ("Từ ngày 1/1/2026, công ty tôi có được giảm lương của nhân viên không?", None),
    ("hợp đồng ký ngày 15/3/2024 thì áp dụng luật nào", None),
])
def test_so_hieu_trong_nhan_dien_bang_quy_tac(cau_hoi, mong):
    # `moi_so_hieu_trong` trả LIST (câu hỏi ghép nhiều số hiệu, vòng review 2).
    # Bảng tham số giữ nguyên hình dạng cũ — mỗi ca ở đây có 0 hoặc 1 số hiệu.
    assert moi_so_hieu_trong(cau_hoi) == ([mong] if mong else [])


def test_van_ban_co_trong_kho_thi_tra_loi_co():
    out = dung_cau_tra_loi("có Nghị định 145/2020 không?", KHO)
    assert "145/2020/NĐ-CP" in out
    assert "hướng dẫn Bộ luật Lao động" in out
    assert "toàn văn" in out


def test_so_hieu_khong_co_trong_kho_thi_noi_khong_co_va_KHONG_biu():
    """Sai chế độ tệ nhất ở đây không phải "không biết" — mà là gán cho kho một
    văn bản nó không có. Câu trả lời phải nêu lại đúng số hiệu được hỏi và
    không được kéo một văn bản khác vào chỗ đó."""
    out = dung_cau_tra_loi("có Nghị định 999/2099/NĐ-CP không?", KHO)
    assert "999/2099" in out
    assert "không có" in out.lower()
    for r in KHO:
        assert r["so_ky_hieu"] not in out, f"bịa {r['so_ky_hieu']} cho một số hiệu không tồn tại"


def test_ban_da_bi_thay_the_van_la_CO_trong_kho():
    """BLLĐ 2012 nằm trong kho thật — nó chỉ không được ĐẾM vào số Bộ luật đang
    dùng. Trả "không có" là một lời nói sai về chính kho của mình."""
    out = dung_cau_tra_loi("Bộ luật Lao động 10/2012/QH13 còn trong kho chứ?", KHO)
    assert out.startswith("Có."), out
    assert "hết hiệu lực" in out
    assert "2021-01-01" in out, "phải nêu lý do nguyên văn của effectivity"


# ══ Không được trình bày điều chưa biết như điều đã biết ════════════════════

def test_chua_xac_dinh_KHONG_bi_goi_la_con_hieu_luc():
    """`chua_xac_dinh` nghĩa là đồ thị không có tín hiệu nào — không phải "còn
    hiệu lực". Đây là mặc định an toàn mà `effectivity.py` quy định dứt khoát;
    một nhãn sai ở đây biến "không biết" thành một khẳng định."""
    kho = [_vb("1/2020/QH14", "Luật Thử số 1/2020/QH14", loai="Luật",
               verdict=V.chua_xac_dinh, tin_cay="thap", ly_do="không có tín hiệu nào")]
    out = dung_cau_tra_loi("có Luật 1/2020/QH14 không", kho)
    assert "còn hiệu lực" not in out
    assert "chưa xác định" in out


def test_bo_luat_bi_sua_doi_mot_phan_phai_noi_ra():
    """Năm trong sáu Bộ luật hiện hành là `mot_phan_khong_xac_dinh`: bị sửa đổi
    một phần mà CSDL quốc gia không công bố phần nào. Liệt kê chúng như văn bản
    nguyên vẹn là bỏ đúng cái người đọc cần biết."""
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, KHO)
    assert out.count("một phần") >= 5, out


def test_tong_so_khong_gop_ban_da_thay_vao_so_dang_dung():
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, KHO)
    # KHO có 16 văn bản: 9 còn dùng được, 7 đã hết hiệu lực hoặc bị thay thế.
    assert "16" in out and "9" in out and "7" in out


# ══ DB thật ═════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_kho_that_ra_dung_6_bo_luat():
    from src.config import as_of_hieu_luc
    from src.services.db import get_engine

    out = tra_loi_ve_kho(get_engine(), CAU_HOI_TOM_TAT, as_of_hieu_luc(None))
    assert "Bộ luật: 6" in out, out
    assert CAU_GIOI_HAN in out
    assert not _RE_AO_GIAC.search(out)


@pytest.mark.integration
def test_kho_that_tra_dung_nghi_dinh_145_2020():
    from src.services.db import get_engine

    out = tra_loi_ve_kho(get_engine(), "kho có Nghị định 145/2020 không?", date(2026, 9, 2))
    assert out.startswith("Có."), out
    assert "145/2020/NĐ-CP" in out


@pytest.mark.integration
def test_kho_that_khong_bia_van_ban_khong_ton_tai():
    from src.services.db import get_engine

    out = tra_loi_ve_kho(get_engine(), "có Nghị định 999/2099/NĐ-CP không?", date(2026, 9, 2))
    assert "999/2099" in out and "không có" in out.lower()


# ══ Vòng review 1 (2026-09-02) — tách nhóm "chưa xác định" ═════════════════


def test_chua_xac_dinh_khong_bi_gop_vao_so_van_ban_dung_duoc():
    """44/130 văn bản trên DB thật mang `chua_xac_dinh` — đồ thị KHÔNG CÓ tín
    hiệu nào về chúng.

    Phép lọc của kho là một PHỦ ĐỊNH (loại đúng hai verdict dứt khoát
    `het_hieu_luc`/`bi_thay_the`), nên `chua_xac_dinh` và `can_doi_chieu_tay`
    lọt vào cùng rổ với `con_hieu_luc`. Diễn đạt phòng thủ ("chưa ghi nhận bị
    thay thế") là đúng về chữ, nhưng người đọc thấy một con số tổng sẽ hiểu là
    "dùng được" — và một phần ba kho thật ra là "mình không biết".

    Đây đúng chỗ dự án này không được phép nói mềm: khoảng cách giữa "đã kiểm và
    ổn" với "không có thông tin" là toàn bộ lý do có bảy phép kiểm.
    """
    kho_thu = [
        _vb("1/2020/QH14", "Luật A", loai="Luật"),                              # con_hieu_luc
        _vb("2/2020/QH14", "Luật B", loai="Luật", verdict=V.mot_phan_khong_xac_dinh),
        _vb("3/2020/QH14", "Luật C", loai="Luật", verdict=V.chua_xac_dinh),
        _vb("4/2020/QH14", "Luật D", loai="Luật", verdict=V.chua_xac_dinh),
        _vb("5/2020/QH14", "Luật E", loai="Luật", verdict=V.can_doi_chieu_tay),
        _vb("6/2020/QH14", "Luật F", loai="Luật", verdict=V.het_hieu_luc),
    ]
    tl = dung_cau_tra_loi(CAU_HOI_TOM_TAT, kho_thu)

    # BA nhóm, không hai và không một: 2 xác định được (con_hieu_luc +
    # mot_phan_khong_xac_dinh), 2 chưa kết luận được (chua_xac_dinh), 1 cần đối
    # chiếu tay (can_doi_chieu_tay — CÓ tín hiệu, thiếu ngày), 1 đã hết hiệu lực.
    assert "2 văn bản tôi xác định được" in tl, f"thiếu nhóm xác định được:\n{tl}"
    assert "2 văn bản tôi chưa kết luận được" in tl, f"thiếu nhóm chưa kết luận:\n{tl}"
    assert "1 văn bản cần đối chiếu tay" in tl, f"thiếu nhóm cần người:\n{tl}"
    # Không được gộp cả năm thành một con số rồi trình bày như nhau.
    assert "5 văn bản chưa ghi nhận" not in tl, f"vẫn gộp:\n{tl}"


def test_chua_xac_dinh_khong_bao_gio_duoc_goi_la_con_hieu_luc():
    kho_thu = [_vb("9/2020/QH14", "Luật X", loai="Luật", verdict=V.chua_xac_dinh)]
    tl = dung_cau_tra_loi(CAU_HOI_TOM_TAT, kho_thu)
    assert "1 văn bản còn hiệu lực" not in tl
    assert "còn hiệu lực" not in tl.split("Phân theo loại")[0], (
        f"phần mở đầu gọi một văn bản chưa xác định là còn hiệu lực:\n{tl}"
    )


# ══ `số/năm` KHÔNG định danh duy nhất ═══════════════════════════════════════

_TRUNG_SO_HIEU = [
    _vb("128/2025/NĐ-CP", "Nghị định 128/2025/NĐ-CP về X", loai="Nghị định"),
    _vb("128/2025/QH15", "Luật Y số 128/2025/QH15", loai="Luật", depth="shallow"),
]


def test_mot_so_nam_khop_NHIEU_van_ban_thi_neu_HET():
    """ĐO ĐƯỢC trên DB thật: `128/2025` khớp CẢ `128/2025/NĐ-CP` lẫn
    `128/2025/QH15` — hai văn bản khác nhau, khác cả loại. Trả về `khop[0]` rồi
    im lặng về phần còn lại là một phát biểu THIẾU về chính kho: người hỏi tin
    rằng kho có đúng một văn bản mang số hiệu đó."""
    out = dung_cau_tra_loi("kho có 128/2025 không?", [*KHO, *_TRUNG_SO_HIEU])
    assert out.startswith("Có."), out
    for r in _TRUNG_SO_HIEU:
        assert r["so_ky_hieu"] in out, f"thiếu {r['so_ky_hieu']}"
        assert r["ten"] in out
    assert CAU_GIOI_HAN in out


@pytest.mark.integration
def test_kho_that_so_hieu_trung_thi_neu_het_hai_van_ban():
    from src.services.db import get_engine

    out = tra_loi_ve_kho(get_engine(), "kho có 128/2025 không?", date(2026, 9, 2))
    assert "128/2025/NĐ-CP" in out and "128/2025/QH15" in out, out


@pytest.mark.integration
def test_nap_kho_cho_verdict_Y_HET_duong_tung_van_ban():
    """`nap_kho` gộp thành hai truy vấn thay vì gọi `danh_gia_theo_id` 130 lần.

    Đo được 2026-09-02: đường từng-cái là 392–522 round-trip mỗi request
    (130 × [1 ping của `pool_pre_ping` + 2 truy vấn của `nap_ngu_canh` + 1 truy
    vấn có điều kiện]); đường gộp là 5, không phụ thuộc cỡ corpus. 0,17s so với
    0,011s trên localhost — nhưng con số localhost CHE mất vấn đề thật: 0,17s
    chia ~450 round-trip ra ~0,3ms, tức latency loopback. Với DB ở xa (Railway)
    riêng phần mạng đã là 0,4–2,6 giây cho đúng cái đường lẽ ra là "0 token, trả
    lời ngay".

    Test này KHÔNG đo tốc độ (đo thời gian trong test là nguồn flake). Nó pin
    thứ có thể vỡ khi đổi đường: **verdict phải y hệt**. Đã đối chiếu cả 130 văn
    bản 2026-09-02 — 0 lệch verdict.

    (Lệch `ly_do` ở 5 văn bản bị NHIỀU văn bản khác sửa: hai đường nêu tên một
    văn bản sửa khác nhau trong cùng tập, cùng verdict, cả hai đều đúng sự thật.
    Lệch này CÓ TỪ TRƯỚC — `routes_tim_kiem.py` vốn đã dùng đường gộp trong khi
    `expand`/`tier1` dùng đường từng-cái — nên test này pin verdict, không pin
    `ly_do`. Ghi nợ riêng.)
    """
    from datetime import date

    from src.services.db import get_engine
    from src.services.effectivity import danh_gia_theo_id
    from src.services.kho import nap_kho

    e, hom_nay = get_engine(), date.today()
    kho = nap_kho(e, hom_nay)
    assert kho, "kho rỗng — không kiểm được gì"
    lech = [
        r["so_ky_hieu"] for r in kho
        if str(r["hieu_luc"].verdict) != str(danh_gia_theo_id(e, r["id"], hom_nay).verdict)
    ]
    assert not lech, f"đường gộp cho verdict khác đường từng-văn-bản: {lech[:5]}"


# ══ Vòng review 2 (silent-failure-hunter, 2026-09-02) ══════════════════════


def test_cau_hoi_ghep_NHIEU_so_hieu_duoc_tra_loi_ve_TAT_CA():
    """"có nghị định 145/2020 và nghị định 90/2019 không?" — bản trước dùng
    `re.search` nên chỉ lấy số hiệu ĐẦU TIÊN, trả lời về 145/2020 rồi im lặng
    hoàn toàn về 90/2019.

    Không có cảnh báo phạm vi nào, nên câu trả lời TRÔNG đầy đủ và tự tin trong
    khi đã bỏ mất một nửa câu hỏi — đúng chế độ hỏng mà cả đề tài coi là nguy
    hiểm nhất, chỉ ở dạng thiếu phạm vi thay vì bịa dữ liệu.
    """
    out = dung_cau_tra_loi("có nghị định 145/2020 và nghị định 90/2019 không?", KHO)
    assert "145/2020" in out
    assert "90/2019" in out, f"bỏ mất số hiệu thứ hai:\n{out}"
    # Vẫn đúng một câu giới hạn phạm vi ở cuối, không lặp lại mỗi khối.
    assert out.count(CAU_GIOI_HAN) == 1, f"lặp câu giới hạn {out.count(CAU_GIOI_HAN)} lần"


def test_cau_hoi_ghep_mot_co_mot_khong_noi_dung_ca_hai():
    out = dung_cau_tra_loi("kho có 145/2020 và 999/2099 không?", KHO)
    assert "145/2020/NĐ-CP" in out
    assert "999/2099" in out
    assert "không có" in out.lower(), "phải nói rõ cái nào kho không có"


@pytest.mark.parametrize("cau_hoi, mong", [
    ("có nghị định 145/2020 và 90/2019 không", ["145/2020", "90/2019"]),
    ("có Nghị định 145/2020 không?", ["145/2020"]),
    ("Từ ngày 1/1/2026, công ty tôi có được giảm lương không?", []),
    ("hợp đồng ký ngày 15/3/2024 thì áp dụng luật nào", []),
    (CAU_HOI_TOM_TAT, []),
    # Nhắc HAI LẦN cùng một số hiệu là một số hiệu, không phải hai.
    ("nghị định 145/2020 ấy, tức 145/2020/NĐ-CP, có không", ["145/2020"]),
])
def test_moi_so_hieu_trong_lay_HET_va_khong_trung_lap(cau_hoi, mong):
    from src.services.kho import moi_so_hieu_trong

    assert moi_so_hieu_trong(cau_hoi) == mong


def test_can_doi_chieu_tay_KHONG_bi_mo_ta_la_khong_co_tin_hieu():
    """`can_doi_chieu_tay` nghĩa là BIẾT có sửa nhưng chưa đọc được ngày — tức
    CÓ tín hiệu, chỉ thiếu một dữ kiện. Gộp nó vào câu "đồ thị văn bản không có
    tín hiệu nào về chúng" là một phát biểu SAI về 3 văn bản trong kho thật.

    Đúng thứ dự án này không được phép làm: nói sai về mức độ mình biết.
    """
    kho_thu = [_vb("7/2020/QH14", "Luật G", loai="Luật", verdict=V.can_doi_chieu_tay,
                   ly_do="biết bị sửa nhưng không đọc được ngày")]
    tl = dung_cau_tra_loi(CAU_HOI_TOM_TAT, kho_thu)
    assert "không có tín hiệu nào" not in tl, f"mô tả sai can_doi_chieu_tay:\n{tl}"
    assert "đối chiếu tay" in tl.lower(), f"không nói ra vì sao chưa kết luận được:\n{tl}"


# ══ `so_ky_hieu` dị dạng — không trình bày "Không số" như một định danh ═════
# ĐO ĐƯỢC 2026-09-02 trên mặt người dùng: `documents` id 8532 có
# `so_ky_hieu = 'Không số'` và `ten = 'Luật Thương mại số Không số'` (crawler
# ghép `ten + " số " + so_ky_hieu`), và câu trả lời hiện ra
# "Không số (Luật Thương mại số Không số)" — hai lời nói sai trong một dòng.


def test_hien_van_ban_giu_nguyen_so_hieu_that():
    from src.services.kho import hien_van_ban

    assert hien_van_ban("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP") == (
        "145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP")


def test_hien_van_ban_bo_so_hieu_khong_co_chu_so_nao():
    """Kiểm bằng CHỮ SỐ, không bằng danh sách giá trị xấu: mọi số hiệu văn bản
    pháp luật Việt Nam đều mang năm ban hành, nên phép kiểm này không loại oan
    một số hiệu thật nào — và nó bắt được cả dạng dị dạng chưa từng xuất hiện."""
    from src.services.kho import hien_van_ban

    so, ten = hien_van_ban("Không số", "Luật Thương mại số Không số")
    assert so == "", "'Không số' không phải một số hiệu, không được hiện như định danh"
    assert ten == "Luật Thương mại", "hậu tố crawler ghép vào phải bị cắt"


def test_hien_van_ban_cat_hau_to_theo_QUY_TAC_khong_theo_chuoi_cung():
    """Viết cứng `" số Không số"` sẽ bỏ sót dòng thứ hai xuất hiện với một dạng
    dị dạng khác — mà `documents` là dữ liệu crawl, dạng thứ hai là chuyện khi
    nào chứ không phải có hay không."""
    from src.services.kho import hien_van_ban

    assert hien_van_ban("Chưa rõ", "Nghị quyết số Chưa rõ") == ("", "Nghị quyết")
    assert hien_van_ban("KHÔNG SỐ", "Thông tư số KHÔNG SỐ") == ("", "Thông tư")


def test_hien_van_ban_khong_cat_khi_ten_khong_lap_so_hieu():
    from src.services.kho import hien_van_ban

    assert hien_van_ban("Không số", "Luật Thương mại") == ("", "Luật Thương mại")


def test_so_hieu_di_dang_KHONG_xuat_hien_trong_chuoi_nguoi_dung_doc():
    """Phép canh ở tầng CHUỖI THẬT, không chỉ ở hàm thuần: `dung_cau_tra_loi`
    ghép nhiều nhánh, và một nhánh quên gọi `hien_van_ban` vẫn đưa được
    'Không số' tới màn hình."""
    # `loai_van_ban='Bộ luật'` là đường DUY NHẤT một văn bản dị dạng ra tới mặt
    # người đọc qua module này: `_tom_tat` nêu đích danh từng Bộ luật, còn hai
    # nhánh tra-một-số-hiệu thì không tới được ('Không số' không phải `số/năm`
    # nên `moi_so_hieu_trong` không bao giờ khớp nó).
    kho_thu = [
        _vb("Không số", "Luật Thương mại số Không số", depth="shallow"),
        _vb("45/2019/QH14", "Bộ Luật lao động số 45/2019/QH14"),
    ]
    out = dung_cau_tra_loi(CAU_HOI_TOM_TAT, kho_thu)
    assert "Không số" not in out, f"vẫn hiện số hiệu dị dạng:\n{out}"
    assert "Luật Thương mại" in out, f"cắt số hiệu dị dạng mà mất luôn văn bản:\n{out}"


# ══ T4 — nhận diện "xin bảng" (0 token, tầng thuần) ═════════════════════════


@pytest.mark.parametrize("cau_hoi", [
    "cho tôi xem dạng bảng nhé",
    # Câu tái hiện đúng lỗi ĐO ĐƯỢC trong task-4-brief.md.
    "đưa cho tôi bảng hiển thị để xem dễ hơn",
    "đưa bảng cho mình với",
    "liệt kê hết ra cho mình",
    "trình bày dạng cột được không",
    "có cách nào xem dễ hơn không",
    "cho ra table luôn",
    "kẻ bảng giúp mình",
    "cho tôi bảng được không",
])
def test_xin_dang_bang_bat_dung_cau_xin_trinh_bay(cau_hoi):
    assert xin_dang_bang(cau_hoi), cau_hoi


@pytest.mark.parametrize("cau_hoi", [
    "bảng lương của tôi tính thế nào",
    "cho tôi bảng lương tháng này",
    "đưa bảng chấm công cho tôi xem",
    "kẻ bảng giá đất mới nhất cho tôi",
    CAU_HOI_TOM_TAT,
    "kho có Nghị định 145/2020 không?",
    # Fix round 1 (finding 3): ba cụm KHÔNG kết thúc bằng "bảng" — danh từ pháp
    # lý đứng CÁCH cụm kích hoạt một hoặc hai từ nối, không phải ngay sau nó.
    # Bản trước chỉ gác bốn cụm kết thúc bằng "bảng" nên cả ba câu này lọt qua
    # kích hoạt sai (đo được: "liệt kê bảng lương của tôi" từng bật chế độ bảng
    # cho một câu hỏi NỘI DUNG về bảng lương).
    "liệt kê bảng lương",
    "xem dễ hơn bảng chấm công",
    "dạng cột của bảng giá",
])
def test_xin_dang_bang_KHONG_bat_danh_tu_phap_ly_chua_chu_bang(cau_hoi):
    """Chỗ dễ sai nhất của T4 (brief tự nêu): "bảng lương"/"bảng chấm
    công"/"bảng giá" là danh từ pháp lý trong NỘI DUNG câu hỏi, không phải
    yêu cầu trình bày — kể cả khi đứng ngay sau các cụm xin-bảng ("cho tôi
    bảng", "đưa bảng", "kẻ bảng"), hay cách một từ nối sau các cụm còn lại
    ("liệt kê", "dạng cột", "xem dễ hơn")."""
    assert not xin_dang_bang(cau_hoi), cau_hoi


@pytest.mark.parametrize(("cau_hoi", "ky_vong"), [
    # Chiều 1 — guard CÒN hiệu lực (bảy cụm): "bảng"/từ nối đứng NGAY TRƯỚC
    # danh từ pháp lý, đọc được thành danh từ ghép nội dung → phải chặn.
    ("liệt kê bảng lương của tôi", False),
    ("xem dễ hơn bảng chấm công", False),
    ("dạng cột của bảng giá", False),
    # Chiều 2 — guard đã GỠ (hai cụm): "bảng hiển thị"/"table" luôn cần một
    # chủ đề theo sau, không tự ghép thành danh từ pháp lý với lương/chấm
    # công/giá → đây LÀ yêu cầu trình bày thật, không được chặn oan. Đây
    # chính là hồi quy fix round 1 đã gây ra (guard bản trước phủ cả chín
    # cụm, hai câu này từng trả về False sai) — chiều này là chiều mà fix
    # round 1 KHÔNG có test nào canh, nên hồi quy lọt qua không ai biết.
    ("bảng hiển thị lương của nhân viên theo tháng", True),
    ("table lương nhân viên tháng này", True),
])
def test_xin_dang_bang_gac_chi_o_bay_cum_khong_phai_chin(cau_hoi, ky_vong):
    assert xin_dang_bang(cau_hoi) is ky_vong, cau_hoi


def test_loi_dan_bang_khong_lap_lai_noi_dung_bang_thanh_van_xuoi():
    """`answer` khi xin bảng phải là câu dẫn NGẮN rồi đóng bằng `CAU_GIOI_HAN`
    — không lặp lại số liệu của bảng thành văn xuôi (người đọc không cần
    cùng một con số hai lần)."""
    from src.services.kho import loi_dan_bang

    tra_loi = loi_dan_bang()
    assert CAU_GIOI_HAN in tra_loi
    assert "Bộ luật" not in tra_loi, "không được liệt kê văn bản như `_tom_tat`"
    assert len(tra_loi) < 400, "câu dẫn phải NGẮN, không phải một bài văn xuôi"


# ══ T4 — dung_bang, Bảng 1 (loại văn bản): dùng LẠI phép đếm của _tom_tat ═══


def test_dung_bang_tra_ve_dung_hai_bang():
    bang = dung_bang(CAU_HOI_TOM_TAT, KHO)
    assert len(bang) == 2
    assert [b.tieu_de for b in bang] == ["Phân theo loại văn bản", "Phân theo lĩnh vực"]


def test_dung_bang_bang_1_dung_dung_cot_theo_brief():
    b1 = dung_bang(CAU_HOI_TOM_TAT, KHO)[0]
    assert b1.cot == ["Loại văn bản", "Tổng", "Có toàn văn", "Chỉ có số hiệu và tên"]


def test_dung_bang_bang_1_dung_lai_dung_phep_dem_voi_van_xuoi():
    """Đúng số mà `test_dem_bo_luat_ra_6_khong_phai_12` và
    `test_muc_phu_theo_depth_duoc_noi_ra` đã canh ở văn xuôi trên CÙNG `KHO` —
    hai phép đếm, một con số, vì `dung_bang` dùng lại `_dem_theo_loai`/
    `_sap_xep_loai` của `_tom_tat`, không viết lại."""
    b1 = dung_bang(CAU_HOI_TOM_TAT, KHO)[0]
    assert b1.dong == [
        ["Bộ luật", "6", "6", "0"],
        ["Luật", "2", "1", "1"],
        ["Nghị định", "1", "1", "0"],
    ]


# ══ T4 — dung_bang, Bảng 2 (lĩnh vực) ════════════════════════════════════════

_LV_DU_BA_TANG = "Lao động - Thương binh và Xã hội"
_LV_CHI_LUAT_GOC = "Dân sự"
_LV_CHI_SHALLOW = "Thương mại"
# 76 ký tự — giá trị THẬT dài nhất đo được trên DB (ruling task-4-brief.md),
# không phải một chuỗi dựng tay cho gọn.
_LV_DAI = "Chính sách thuế Quản lý thuế, phí, lệ phí và thu khác của ngân sách nhà nước"
_LV_NHIEU = "Bảo vệ và chăm sóc trẻ em, An toàn lao động"

KHO_LINH_VUC = [
    _vb("1/2020/QH14", "Luật A", loai="Luật", linh_vuc=_LV_DU_BA_TANG),
    _vb("2/2020/NĐ-CP", "Nghị định B", loai="Nghị định", linh_vuc=_LV_DU_BA_TANG),
    _vb("3/2020/TT-BLĐTBXH", "Thông tư C", loai="Thông tư", linh_vuc=_LV_DU_BA_TANG),
    _vb("4/2020/QH14", "Luật D", loai="Luật", linh_vuc=_LV_CHI_LUAT_GOC),
    _vb("5/2020/QH14", "Luật E", loai="Luật", depth="shallow", linh_vuc=_LV_CHI_SHALLOW),
    _vb("6/2020/QH14", "Luật F", loai="Luật", linh_vuc=_LV_DAI),
    _vb("7/2020/QH14", "Luật G", loai="Luật", linh_vuc=_LV_NHIEU),
    _vb("8/2020/QH14", "Luật H", loai="Luật", linh_vuc=None),
]


def test_dung_bang_bang_2_dung_dung_cot_theo_brief():
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    assert b2.tieu_de == "Phân theo lĩnh vực"
    assert b2.cot == ["Lĩnh vực", "Số văn bản", "Độ sâu"]


def test_do_sau_du_ba_tang_khi_co_ca_luat_nghi_dinh_thong_tu():
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    hang = next(h for h in b2.dong if h[0] == _LV_DU_BA_TANG)
    assert hang == [_LV_DU_BA_TANG, "3", "đủ luật, nghị định, thông tư"]


def test_do_sau_chi_luat_goc_khi_khong_co_nghi_dinh_thong_tu_toan_van():
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    hang = next(h for h in b2.dong if h[0] == _LV_CHI_LUAT_GOC)
    assert hang == [_LV_CHI_LUAT_GOC, "1", "chỉ luật gốc"]


def test_do_sau_chi_so_hieu_va_ten_khi_toan_shallow():
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    hang = next(h for h in b2.dong if h[0] == _LV_CHI_SHALLOW)
    assert hang == [_LV_CHI_SHALLOW, "1", "chỉ số hiệu và tên"]


def test_linh_vuc_null_khong_bia_nhan_ma_de_o_rong():
    """`linh_vuc IS NULL` gộp về khoá `""`, KHÔNG một nhãn bịa như "Chưa phân
    loại" — chính nhãn đó đã bị `scripts/nap_linh_vuc.py` coi là rỗng vì lý do
    này (`_CHUA_PHAN_LOAI`), và T1 phải gỡ nó khỏi một chỗ khác vì lý do y hệt
    (ruling task-4-brief.md)."""
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    nhan = [h[0] for h in b2.dong]
    assert "" in nhan
    assert not any(n and ("chưa" in n.lower() or "phân loại" in n.lower()) for n in nhan)


def test_linh_vuc_dai_hien_verbatim_khong_cat_ngan():
    """Cắt ngắn tên lĩnh vực là nói dối về nó; bảng đã có cuộn ngang ở FE cho
    nội dung rộng (xem lịch sử `bang`/`nguyen-van`), nên backend không cần và
    không được tự rút gọn."""
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    assert len(_LV_DAI) == 76
    assert _LV_DAI in [h[0] for h in b2.dong]


def test_linh_vuc_nhieu_gia_tri_cach_nhau_bang_phay_KHONG_bi_tach():
    """Dữ liệu nguồn (`metadata.parquet`, T1) có chuỗi nhiều lĩnh vực cách
    nhau bằng dấu phẩy trong CÙNG một giá trị — nguyên văn, không phải lỗi cần
    "làm sạch". Tách nó thành hai lĩnh vực là suy diễn, không phải đọc dữ liệu."""
    b2 = dung_bang(CAU_HOI_TOM_TAT, KHO_LINH_VUC)[1]
    nhan = [h[0] for h in b2.dong]
    assert _LV_NHIEU in nhan
    for ve in _LV_NHIEU.split(", "):
        assert ve not in nhan, f"'{_LV_NHIEU}' bị tách thành lĩnh vực riêng '{ve}'"


# ══ T4 — `Bang.dong[i]` phải khớp số cột với `Bang.cot` ═════════════════════


def test_bang_chan_hang_lech_so_cot():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Bang(tieu_de="X", cot=["a", "b"], dong=[["1", "2", "3"]])


def test_bang_hop_le_khong_bi_chan():
    b = Bang(tieu_de="X", cot=["a", "b"], dong=[["1", "2"], ["3", "4"]])
    assert b.dong == [["1", "2"], ["3", "4"]]


# ═══ Thứ tự khối: trả lời đúng câu hỏi trước, bối cảnh sau ══════════════════


def test_hoi_dich_danh_bo_luat_nhan_ra_dung():
    from src.services.kho import hoi_dich_danh_bo_luat

    for co in ("có bao nhiêu bộ luật", "Kho có những BỘ LUẬT nào?", "bo luat nao dang co"):
        assert hoi_dich_danh_bo_luat(co), co
    for khong in ("kho của bạn có gì", "bạn làm được gì", "có bao nhiêu nghị định"):
        assert not hoi_dich_danh_bo_luat(khong), khong


@pytest.mark.integration
def test_hoi_BO_LUAT_thi_khoi_bo_luat_dung_DAU():
    """Đo 2026-09-15: câu trả lời 1761 ký tự mở bằng "1634 văn bản… 209… 234…"
    và mãi ~700 ký tự sau mới tới "6 Bộ luật". Mọi con số đều đúng; câu trả lời
    vẫn sai, vì thứ người hỏi cần nằm giữa một bức tường họ không đọc tới."""
    from datetime import date

    from src.services.db import get_engine
    from src.services.kho import dung_cau_tra_loi, nap_kho

    kho = nap_kho(get_engine(), date.today())
    ra = dung_cau_tra_loi("có bao nhiêu bộ luật", kho)
    dau = ra.split("\n\n")[0]
    assert "Bộ luật đang có trong kho" in dau, f"khối đầu là: {dau[:120]}"
    # Bối cảnh kho KHÔNG bị cắt — nó chỉ không được đứng trước câu trả lời.
    assert "Trong kho của tôi hiện có" in ra


@pytest.mark.integration
def test_hoi_CHUNG_ve_kho_van_giu_thu_tu_cu():
    from datetime import date

    from src.services.db import get_engine
    from src.services.kho import dung_cau_tra_loi, nap_kho

    kho = nap_kho(get_engine(), date.today())
    ra = dung_cau_tra_loi("kho của bạn có những gì", kho)
    assert ra.split("\n\n")[0].startswith("Trong kho của tôi hiện có")
