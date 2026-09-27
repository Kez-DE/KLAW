"""Bản thảo trên khuôn gốc (P4a) — kế hoạch `docs/plans/active/khuon-goc-dien-tai-cho.md`,
hợp đồng Storage và "Edit operations"; quyết định 2026-09-26.

Phần đầu là hàm THUẦN (không DB): gộp phép sửa, chỗ trống của một phiên bản,
chuẩn hoá giá trị điền, "đã đổi" và bản tóm tắt Markdown. Phần sau chạm DB thật
(`integration`): vòng phiên bản, cascade, và lưu ô điền (`sua_o_dien`).
"""

import pytest

from src.services import ban_thao
from src.services.ban_thao import cho_trong_khuon, chuan_hoa_dien, doi_so_voi, gop_phep_sua, tom_tat_khuon


def _d(don_vi: int, cho: int, gia_tri: str) -> dict:
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": cho, "gia_tri": gia_tri}


def _thay(don_vi: int, noi_dung: str) -> dict:
    return {"loai": "thay", "don_vi": don_vi, "noi_dung": noi_dung}


def _xoa(don_vi: int) -> dict:
    return {"loai": "xoa", "don_vi": don_vi}


def _chen(don_vi: int, noi_dung: str) -> dict:
    return {"loai": "chen_sau", "don_vi": don_vi, "noi_dung": noi_dung}


# ───────────────────────────────────────────────────────── gop_phep_sua


def test_gop_dien_MOI_thang_GIU_cho_cu_va_khong_dung_vao_dau_vao():
    cu = [_d(1, 0, "A"), _d(2, 0, "B")]
    moi = [_d(1, 0, "C")]
    assert gop_phep_sua(cu, moi) == [_d(1, 0, "C"), _d(2, 0, "B")]
    assert cu == [_d(1, 0, "A"), _d(2, 0, "B")] and moi == [_d(1, 0, "C")]


def test_gop_dien_RONG_go_o_da_dien_de_dau_cham_tro_lai():
    cu = [_d(1, 0, "A"), _d(2, 0, "B")]
    assert gop_phep_sua(cu, [_d(2, 0, "")]) == [_d(1, 0, "A")]
    assert gop_phep_sua(cu, [_d(2, 0, "   ")]) == [_d(1, 0, "A")]
    assert gop_phep_sua(cu, [_d(9, 0, "")]) == cu, "gỡ một ô chưa điền là không làm gì"


def test_gop_dien_trung_trong_CUNG_lan_gui_thi_lan_sau_thang():
    assert gop_phep_sua([], [_d(1, 0, "A"), _d(1, 0, "B"), _d(1, 1, "C")]) == [_d(1, 0, "B"), _d(1, 1, "C")]


def test_gop_thay_va_xoa_chung_MOT_khoa_theo_don_vi():
    assert gop_phep_sua([_thay(5, "x")], [_xoa(5)]) == [_xoa(5)]
    assert gop_phep_sua([_xoa(5)], [_thay(5, "y")]) == [_thay(5, "y")]
    assert gop_phep_sua([_thay(5, "x"), _thay(6, "z")], [_thay(5, "y")]) == [_thay(5, "y"), _thay(6, "z")]


def test_gop_chen_sau_bo_trung_giu_thu_tu():
    cu = [_chen(3, "a")]
    assert gop_phep_sua(cu, [_chen(3, "b"), _chen(3, "a"), _chen(4, "a")]) == [
        _chen(3, "a"),
        _chen(3, "b"),
        _chen(4, "a"),
    ]


def test_gop_bo_phep_khong_thuoc_bon_loai():
    assert gop_phep_sua([None, {"loai": "la"}], [_d(1, 0, "A"), "rac"]) == [_d(1, 0, "A")]
    assert gop_phep_sua(None, []) == []


def test_gop_thay_xoa_tren_don_vi_go_moi_dien_cua_don_vi_do():
    """Tích hợp wave D: `dien` và `thay`/`xoa` khoá riêng, nên một danh sách gộp
    từng giữ được `dien(10,…)` cùng `xoa(10)` — bộ áp bỏ `dien` (`xung_dot`) còn
    `assemble` đếm nó là đã điền. Đoạn đã thay/xoá không còn dãy chấm nào."""
    cu = [_d(10, 0, "A"), _d(10, 1, "B"), _d(11, 0, "C")]
    assert gop_phep_sua(cu, [_xoa(10)]) == [_d(11, 0, "C"), _xoa(10)]
    assert gop_phep_sua([_thay(10, "x")], [_d(10, 0, "A"), _d(11, 0, "C")]) == [_thay(10, "x"), _d(11, 0, "C")], (
        "dien SAU lên đơn vị đã thay/xoá là dien vào chỗ trống không còn"
    )
    assert gop_phep_sua([], [_d(10, 0, "A"), _xoa(10), _d(10, 0, "B")]) == [_xoa(10)]


def test_gop_cheo_loai_bo_ap_khong_bo_phep_nao_va_cho_trong_khop():
    """Bộ áp DOCX thật trên danh sách gộp chéo loại: không phép nào vào `bo_qua`,
    và `cho_trong_khuon` không mời điền đoạn đã xoá — ba nơi đọc một sự thật."""
    du_lieu = docx_that(*_DONG)
    don_vi = [tl._hang_don_vi(d) for d in doc("x.docx", du_lieu).don_vi]
    phep = gop_phep_sua([_d(0, 0, "Ánh"), _d(1, 0, "0912")], [_xoa(1)])
    _, bao_cao = ban_thao.ap_phep_sua("docx", du_lieu, don_vi, phep)
    assert bao_cao["bo_qua"] == []
    assert [(o["don_vi"], o["gia_tri"]) for o in cho_trong_khuon("docx", don_vi, phep)] == [(0, "Ánh")]


# ───────────────────────────────────────────────────────── cho_trong_khuon

_DOCX = [
    {
        "chi_so": 0,
        "noi_dung": "Họ và tên: ......",
        "dia_chi": {"phan": "word/document.xml", "chi_muc": [0]},
        "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 11, "cuoi": 17, "nhan": "Họ và tên:"}],
    },
    {
        "chi_so": 1,
        "noi_dung": "Điện thoại: ...... Email: ......",
        "dia_chi": {"phan": "word/document.xml", "chi_muc": [1]},
        "cho_trong": [
            {"so": 0, "kieu": "cham", "doan": 0, "dau": 12, "cuoi": 18, "nhan": "Điện thoại:"},
            {"so": 1, "kieu": "tab", "doan": 0, "dau": 26, "cuoi": 26, "nhan": "Email:"},
            {"so": 2, "kieu": "la", "doan": 0, "dau": 0, "cuoi": 1, "nhan": "hỏng"},
        ],
    },
    # Không có địa chỉ: bộ áp không tới được, bảng điền không được mời điền nó.
    {
        "chi_so": 2,
        "noi_dung": "Ngày: ......",
        "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 6, "cuoi": 12, "nhan": "Ngày:"}],
    },
    {"chi_so": 3, "noi_dung": "Ghi chú", "dia_chi": {"phan": "word/document.xml", "chi_muc": [3]}},
]

_PDF = [
    {
        "chi_so": 0,
        "trang": 1,
        "hop": [72, 30, 300, 44],
        "noi_dung": "Ho ten: ....",
        "cho_trong": [{"so": 0, "kieu": "cham", "hop": [120, 30, 300, 44], "co_chu": 14.0, "nhan": "Ho ten:"}],
    },
    # Chỗ trống mang hình dạng DOCX trên khuôn PDF: bộ áp PDF không có toạ độ.
    {
        "chi_so": 1,
        "trang": 1,
        "hop": [72, 50, 300, 64],
        "noi_dung": "Ngay: ....",
        "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 6, "cuoi": 10, "nhan": "Ngay:"}],
    },
]


def test_cho_trong_DOCX_chi_don_vi_co_dia_chi_va_gia_tri_theo_phien_ban():
    ra = cho_trong_khuon("docx", _DOCX, [_d(1, 1, " a@b.vn")])
    assert ra == [
        {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Họ và tên:", "gia_tri": None},
        {"don_vi": 1, "so": 0, "kieu": "cham", "nhan": "Điện thoại:", "gia_tri": None},
        {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email:", "gia_tri": " a@b.vn"},
    ]


def test_cho_trong_PDF_chi_cho_trong_co_hop():
    ra = cho_trong_khuon("pdf", _PDF, [_d(0, 0, "Ánh")])
    assert ra == [{"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Ho ten:", "gia_tri": "Ánh"}]


def test_cho_trong_cua_doan_da_THAY_hay_XOA_khong_con_dien_duoc():
    """Đoạn đã bị thay/xoá không còn dãy chấm nào: mời điền nó là mời một lần
    lưu chắc chắn bị bộ áp bỏ (`xung_dot`)."""
    ra = cho_trong_khuon("docx", _DOCX, [_thay(0, "Họ và tên: A"), _xoa(1)])
    assert ra == []


def test_cho_trong_don_vi_rong_hay_sai_hinh_dang():
    assert cho_trong_khuon("docx", [], []) == []
    assert cho_trong_khuon("docx", [None, {"chi_so": "x"}], None) == []


# ───────────────────────────────────────────────────────── chuan_hoa_dien

_CHAM = {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Họ và tên:"}
_TAB_KHONG_CACH = {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email:"}
_TAB_CO_CACH = {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email: "}


def test_chuan_hoa_cat_khoang_trang_va_dua_ve_NFC():
    assert chuan_hoa_dien("  Nguyễn Văn A  ", _CHAM) == "Nguyễn Văn A"
    assert chuan_hoa_dien("Nguyễn Văn", _CHAM) == "Nguyễn Văn"


def test_chuan_hoa_o_TAB_them_mot_cach_khi_nhan_khong_ket_bang_khoang_trang():
    assert chuan_hoa_dien("a@b.vn", _TAB_KHONG_CACH) == " a@b.vn"
    assert chuan_hoa_dien("a@b.vn", _TAB_CO_CACH) == "a@b.vn"
    assert chuan_hoa_dien("  ", _TAB_KHONG_CACH) == "", "giá trị rỗng là gỡ ô, không thành một dấu cách"


@pytest.mark.parametrize("sai", ["A\nB", "A\r\nB", "A\tB", "A\x00", "A​", "A\x7f"])
def test_chuan_hoa_tu_choi_xuong_dong_va_ky_tu_dieu_khien(sai):
    with pytest.raises(ValueError) as e:
        chuan_hoa_dien(sai, _CHAM)
    assert str(e.value) == ban_thao.LOI_GIA_TRI_DIEN


# ───────────────────────────────────────────────────── đã đổi, tóm tắt


def _khuon(*o: tuple) -> dict:
    return {
        "viec_id": "v",
        "dinh_dang": "docx",
        "so_trang": 1,
        "cho_trong": [{"don_vi": d, "so": s, "kieu": "cham", "nhan": n, "gia_tri": g} for d, s, n, g in o],
    }


def test_doi_so_voi_KHUON_liet_ke_o_doi_cu_sang_moi():
    truoc = {"facts": {}, "khuon": _khuon((0, 0, "Họ và tên:", None), (1, 0, "Email:", " a@b.vn"), (2, 0, "", "x"))}
    sau = {"facts": {}, "khuon": _khuon((0, 0, "Họ và tên:", "Ánh"), (1, 0, "Email:", None), (2, 0, "", "x"))}
    assert doi_so_voi(truoc, sau) == ["Họ và tên: … → Ánh", "Email: a@b.vn → …"]


def test_doi_so_voi_KHONG_khuon_giu_hinh_dang_facts():
    assert doi_so_voi({"facts": {"a": 1}}, {"facts": {"a": 2}, "khuon": None}) == ["a"]


def test_tom_tat_khuon_la_tieu_de_va_mot_dong_moi_o_da_dien():
    k = _khuon((0, 0, "Họ và tên:", "Ánh"), (1, 0, "Email:", None), (1, 1, "", " a@b.vn"))
    assert tom_tat_khuon("Giấy tiếp nhận", k) == "# Giấy tiếp nhận\n\n- Họ và tên: Ánh\n- Ô 1.1: a@b.vn\n"
    assert tom_tat_khuon(None, _khuon()) == "# Văn bản\n"


def test_ket_qua_chat_mang_CUNG_khuon_voi_GET_ban_thao():
    """`assemble` đưa `state["ban_thao_ket"]` thẳng vào `BanThaoOut`: thiếu `khuon`
    ở đó thì kết quả SSE của lượt soạn và `GET /ban-thao/{id}` nói hai điều khác nhau."""
    from src.agents.nodes.dung_ban_thao_tong_quat import _ket_state
    from src.models.schemas import BanThaoOut

    khuon = _khuon((0, 0, "Họ và tên:", "Ánh"))
    bt = {"id": "x", "phien_ban": 1, "document": "# A\n", "clauses": [], "audit": {}, "facts": {}, "khuon": khuon}
    assert BanThaoOut(**_ket_state(bt, "Bản thảo tổng quát", [])).khuon == khuon
    assert BanThaoOut(**_ket_state({**bt, "khuon": None}, "Bản thảo tổng quát", [])).khuon is None


# ═══ Chạm DB thật ══════════════════════════════════════════════════════════

import json  # noqa: E402
import uuid  # noqa: E402

from sqlalchemy import text  # noqa: E402

from src.services import bao_ve, hoi_thoai  # noqa: E402
from src.services import tai_lieu as tl  # noqa: E402
from src.services.db import get_engine, run_migrations  # noqa: E402
from src.services.doc_tai_lieu import doc  # noqa: E402
from tests.test_services.test_dung_trang import docx_that  # noqa: E402

_DONG = ("Họ và tên: ..............................", "Số điện thoại: ................ Email: ................")
_AUDIT = {
    "dat": None,
    "completeness": None,
    "so_dieu_khoan": 0,
    "self_audit": False,
    "findings": [],
    "muc_kiem": "tong_quat",
}


def _ket(viec_id: str | None, phep: list | None, tieu_de: str = "Giấy tiếp nhận") -> dict:
    ket = {"document": f"# {tieu_de}\n", "clauses": [], "audit_report": dict(_AUDIT)}
    if viec_id:
        ket |= {"viec_id": viec_id, "phep_sua": phep}
    return ket


def _viec(sub: str, phien: str, du_lieu: bytes | None = None, don_vi_them: dict | None = None) -> str:
    """Một việc đọc CÓ khuôn gốc: bytes docx thật, `don_vi` của chính bộ đọc."""
    du_lieu = du_lieu or docx_that(*_DONG)
    viec = tl.tao_viec(
        get_engine(), user_sub=sub, hoi_thoai_id=phien, ten_tep="Giấy tiếp nhận.docx", du_lieu=du_lieu, loai=None
    )
    tl.luu_don_vi(get_engine(), viec, doc("x.docx", du_lieu).don_vi)
    tl.luu_khuon_goc(get_engine(), viec, "docx", du_lieu, [[595.0, 842.0]])
    if don_vi_them:
        with get_engine().begin() as c:
            c.execute(
                text(
                    "UPDATE viec_doc_tai_lieu SET don_vi = jsonb_set(don_vi, '{0,cho_trong}', CAST(:c AS jsonb)) WHERE id = :i"
                ),
                {"c": json.dumps(don_vi_them), "i": viec},
            )
    return viec


@pytest.fixture
def nguoi():
    run_migrations("036")
    run_migrations("037")
    subs = [str(uuid.uuid4()), str(uuid.uuid4())]
    for s in subs:
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield subs
    with get_engine().begin() as c:
        for s in subs:
            c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


def _gia_tri(bt: dict) -> dict:
    return {(o["don_vi"], o["so"]): o["gia_tri"] for o in bt["khuon"]["cho_trong"]}


@pytest.mark.integration
def test_VONG_phien_ban_tao_chi_tiet_sua_lui_khoi_phuc_phep_sua(nguoi):
    a, _ = nguoi
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    viec = _viec(a, phien)
    v1 = [_d(0, 0, "Nguyễn Văn Ánh")]
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, v1))
    assert (bt["viec_id"], bt["phep_sua"]) == (viec, v1)
    assert {k: bt["khuon"][k] for k in ("viec_id", "dinh_dang", "so_trang")} == {
        "viec_id": viec,
        "dinh_dang": "docx",
        "so_trang": 1,
    }
    assert _gia_tri(bt) == {(0, 0): "Nguyễn Văn Ánh", (1, 0): None, (1, 1): None}
    assert ban_thao.chi_tiet(a, bt["id"])["khuon"] == bt["khuon"]
    assert ban_thao.moi_nhat_cua_hoi_thoai(a, phien, ban_thao.LOAI_TONG_QUAT, viec_id=viec)["khuon"] == bt["khuon"]

    v2 = [*v1, _d(1, 1, "a@b.vn")]
    bt2 = ban_thao.sua(a, bt["id"], {}, _ket(viec, v2))
    assert (bt2["phien_ban"], bt2["phep_sua"], _gia_tri(bt2)[(1, 1)]) == (2, v2, "a@b.vn")
    snap = bt2["phien_ban_truoc"][-1]
    assert (snap["phien_ban"], snap["phep_sua"], snap["viec_id"]) == (1, v1, viec)
    assert snap["doi"] == ["Email: … → a@b.vn"], "lịch sử nói ô nào đổi, không phải facts rỗng"
    cu = ban_thao.phien_ban_chi_tiet(a, bt["id"], 1)
    assert cu["phep_sua"] == v1 and _gia_tri(cu)[(1, 1)] is None

    bt3 = ban_thao.lui(a, bt["id"])
    assert (bt3["phien_ban"], bt3["phep_sua"], bt3["viec_id"]) == (1, v1, viec)
    assert _gia_tri(bt3) == _gia_tri(bt)


@pytest.mark.integration
def test_ban_thao_HTML_khong_co_khuon_va_viec_NGUOI_KHAC_khong_duoc_gan(nguoi):
    a, b = nguoi
    phien_a, phien_b = hoi_thoai.tao_phien(a, "a"), hoi_thoai.tao_phien(b, "b")
    html = ban_thao.tao(a, phien_a, ban_thao.LOAI_TONG_QUAT, {}, _ket(None, None))
    assert (html["viec_id"], html["phep_sua"], html["khuon"]) == (None, None, None)
    viec_b = _viec(b, phien_b)
    la = ban_thao.tao(a, phien_a, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec_b, [_d(0, 0, "X")]))
    assert (la["viec_id"], la["khuon"]) == (None, None), "khuôn gốc của tài khoản khác không bao giờ gắn vào được"


@pytest.mark.integration
def test_XOA_viec_doc_thi_ban_thao_van_mo_duoc_nhu_van_ban(nguoi):
    a, _ = nguoi
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    viec = _viec(a, phien)
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, [_d(0, 0, "Ánh")]))
    ban_thao.sua(a, bt["id"], {}, _ket(viec, [_d(0, 0, "Bình")]))
    tl.xoa_theo_hoi_thoai(get_engine(), phien, a)

    ct = ban_thao.chi_tiet(a, bt["id"])
    assert (ct["viec_id"], ct["khuon"], ct["document"]) == (None, None, "# Giấy tiếp nhận\n")
    assert ct["phep_sua"] == [_d(0, 0, "Bình")]
    assert ban_thao.phien_ban_chi_tiet(a, bt["id"], 1)["khuon"] is None
    ve = ban_thao.lui(a, bt["id"])
    assert (ve["phien_ban"], ve["viec_id"], ve["khuon"]) == (1, None, None), (
        "lùi không khôi phục một khoá ngoại đã chết"
    )


# ─────────────────────────────────────────────────────────── sua_o_dien


def _o(don_vi: int, cho: int, gia_tri: str) -> dict:
    return {"don_vi": don_vi, "cho_trong": cho, "gia_tri": gia_tri}


@pytest.mark.integration
def test_sua_o_dien_GOP_vao_phien_ban_dang_co_va_tinh_vao_tran_sua(nguoi):
    a, _ = nguoi
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    viec = _viec(a, phien)
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, [_d(0, 0, "Ánh"), _d(1, 0, "0912")]))

    ra = ban_thao.sua_o_dien(a, bt["id"], 1, [_o(1, 1, "  a@b.vn "), _o(1, 0, "")])
    assert isinstance(ra, dict), ra
    assert ra["phien_ban"] == 2 and ra["so_lan_sua"] == 1
    assert ra["phep_sua"] == [_d(0, 0, "Ánh"), _d(1, 1, "a@b.vn")]
    assert _gia_tri(ra) == {(0, 0): "Ánh", (1, 0): None, (1, 1): "a@b.vn"}
    assert ra["document"] == "# Giấy tiếp nhận\n\n- Họ và tên: Ánh\n- Email: a@b.vn\n"
    assert ra["audit"]["sua_tay"] is True and ra["audit"]["muc_kiem"] == "tong_quat"
    # Thứ tự đọc của chỗ trống, không thứ tự gửi lên.
    assert ra["phien_ban_truoc"][-1]["doi"] == ["Số điện thoại: 0912 → …", "Email: … → a@b.vn"]

    assert ban_thao.sua_o_dien(a, bt["id"], 1, [_o(0, 0, "Bình")]) == ban_thao.LOI_PHIEN_BAN_DA_DOI
    khong_doi = ban_thao.sua_o_dien(a, bt["id"], 2, [_o(0, 0, "Ánh")])
    assert (khong_doi["phien_ban"], khong_doi["so_lan_sua"]) == (2, 1), "lưu không đổi gì không tốn một phiên bản"

    with get_engine().begin() as c:
        c.execute(
            text("UPDATE ban_thao SET so_lan_sua = :n WHERE id = CAST(:i AS uuid)"),
            {"n": ban_thao.TRAN_SUA, "i": bt["id"]},
        )
    assert ban_thao.sua_o_dien(a, bt["id"], 2, [_o(0, 0, "Bình")]) == ban_thao.LOI_HET_LAN_SUA


@pytest.mark.integration
def test_sua_o_dien_tu_choi_ban_thao_HTML_o_la_va_gia_tri_nhieu_dong(nguoi):
    a, b = nguoi
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    viec = _viec(a, phien)
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, []))
    html = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(None, None))

    assert ban_thao.sua_o_dien(a, html["id"], 1, [_o(0, 0, "A")]) == ban_thao.LOI_KHONG_PHAI_KHUON
    assert ban_thao.sua_o_dien(a, bt["id"], 1, [_o(0, 7, "A")]) == ban_thao.LOI_O_KHONG_THAY
    assert ban_thao.sua_o_dien(a, bt["id"], 1, [_o(0, 0, "A\nB")]) == ban_thao.LOI_GIA_TRI_DIEN
    assert ban_thao.sua_o_dien(b, bt["id"], 1, [_o(0, 0, "A")]) is None, "bản thảo của người khác là không thấy"
    assert ban_thao.chi_tiet(a, bt["id"])["phien_ban"] == 1, "không lần từ chối nào ghi một phiên bản"


@pytest.mark.integration
def test_sua_o_dien_TU_CHOI_luu_khi_bo_ap_bo_mot_phep(nguoi):
    """Chỗ trống lệch khỏi dãy chấm thật (khuôn gốc không khớp địa chỉ đã ghim):
    bộ áp bỏ phép `cho_trong_da_doi` — không được lưu một phiên bản mà phép của
    nó không áp được, và lời từ chối nói số ô và TÊN ô bị bỏ — không thì "rút
    gọn ô đó" không chỉ ra ô nào giữa các ô vừa sửa (WCAG 3.3.1)."""
    a, _ = nguoi
    phien = hoi_thoai.tao_phien(a, "biểu mẫu")
    lech = [
        {"so": 0, "kieu": "cham", "doan": 0, "dau": 11, "cuoi": 41, "nhan": "Họ và tên:"},
        {"so": 1, "kieu": "cham", "doan": 0, "dau": 0, "cuoi": 5, "nhan": "Lệch"},
    ]
    viec = _viec(a, phien, don_vi_them=lech)
    bt = ban_thao.tao(a, phien, ban_thao.LOAI_TONG_QUAT, {}, _ket(viec, []))
    ra = ban_thao.sua_o_dien(a, bt["id"], 1, [_o(0, 0, "Ánh"), _o(0, 1, "X")])
    assert ra == ban_thao.LOI_KHONG_AP_DUOC.format(n=1, o=" (“Lệch”)")
    assert "“Lệch”" in ra and "Họ và tên" not in ra, "chỉ ô bộ áp bỏ, không ô đã áp được"
    assert ban_thao.chi_tiet(a, bt["id"])["phien_ban"] == 1
    assert isinstance(ban_thao.sua_o_dien(a, bt["id"], 1, [_o(0, 0, "Ánh")]), dict)
