"""Graph trả PHÉP SỬA cho tài liệu có khuôn gốc (kế hoạch `khuon-goc-dien-tai-cho.md`,
P4b; quyết định 2026-09-26 mục 3, 6).

Khoá ở đây, tất cả bằng mô hình GIẢ (0 lượt gọi thật):

1. Tài liệu có khuôn gốc đi prompt v2 + lược đồ `khuon` (không `van_ban`); tài liệu
   không có khuôn gốc giữ nguyên đường HTML (v1, `van_ban`).
2. Mọi phép qua phép kiểm tất định TRƯỚC khi lưu: giá trị có nguồn thì giữ, không
   nguồn thì bỏ, ký ức không được hỏi tới thì bỏ, `thay` chèn số Điều thì bỏ; PDF
   không nhận `chen_sau`/`xoa`; số phép bỏ chỉ vào traces dưới dạng SỐ ĐẾM.
3. Lượt sửa chỉ mang THAY ĐỔI; `dung_ban_thao_tong_quat` gộp chúng vào phép của
   phiên bản đang có (`ban_thao.gop_phep_sua`), giữ các ô đã điền từ khung điền.
4. Không cắt ngầm: một khuôn gốc 10 trang 45.000 ký tự đi trọn trong MỘT lượt gọi;
   quá trần chi phí thì `QUA_DAI`, không cắt.
5. Lượt soạn trên khuôn gốc không gộp vào hồ sơ tài khoản (FR-028); đường checklist
   không đổi.
"""

import json
import uuid
from pathlib import Path

import pytest

from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import TRAN_KY_TU, ResultType, assemble
from src.services import ban_thao, bao_ve, bo_nho
from src.services.doc_tai_lieu import ChoTrong, DiaChi, DonViVanBan

A_ID = "aaaaaaaa-0000-0000-0000-00000000000a"
B_ID = "bbbbbbbb-0000-0000-0000-00000000000b"
THU_MUC_MAU = Path("/Users/kenz_de/giấy tờ thực tập")
BM_M05 = THU_MUC_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"


def _dv(chi_so: int, noi_dung: str, cho=(), *, trang: int = 1, dia_chi: bool = True) -> DonViVanBan:
    return DonViVanBan(
        chi_so=chi_so,
        trang=trang,
        offset_dau=0,
        noi_dung=noi_dung,
        dia_chi=DiaChi("word/document.xml", (chi_so,)) if dia_chi else None,
        # Offset tổng hợp nhưng HỢP LỆ (`_cho_trong_tu_hang` bỏ chỗ `cham` rỗng).
        cho_trong=tuple(ChoTrong(so=i, kieu=k, nhan=n, cuoi=0 if k == "tab" else 3) for i, (k, n) in enumerate(cho)),
    )


# Hình dạng BM.M05 như bộ đọc P2b trả (đo trên tệp thật: nhãn đã `strip()`, một
# đơn vị có thể có nhiều chỗ trống, đơn vị không địa chỉ không điền được).
DV_M05 = [
    _dv(0, "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP"),
    _dv(1, "Cơ quan/Đơn vị tiếp nhận: ………………………", [("cham", "Cơ quan/Đơn vị tiếp nhận:")]),
    _dv(2, "Điện thoại: ……………… Fax: ………………", [("cham", "Điện thoại:"), ("cham", "Fax:")]),
    _dv(3, "Ngành: …………………", [("cham", "Ngành:")]),
    _dv(4, "Họ và tên:", [("tab", "Họ và tên:")]),
    _dv(5, "Đồng ý tiếp nhận sinh viên thực tập theo quy chế của Trường."),
    _dv(6, "Ghi chú: ……………", [("cham", "Ghi chú:")], dia_chi=False),
]
TL_KHUON = [
    {
        "id": A_ID,
        "viec_id": A_ID,
        "ten_tep": "BM.M05.docx",
        "don_vi": DV_M05,
        "co_khuon_goc": True,
        "dinh_dang": "docx",
        "so_trang": 2,
    }
]
CAU = "Điền giúp tôi: cơ quan là Công ty Mẫu Thử, điện thoại 0912345678, họ và tên Nguyễn Văn Thử"


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra):
        self.ra, self.json_schema, self.prompt, self.so_lan_goi = ra, None, None, 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.json_schema, self.prompt = json_schema, messages[-1]["content"]
        self.so_lan_goi += 1
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


def _dien(don_vi, cho_trong, gia_tri):
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": cho_trong, "gia_tri": gia_tri, "noi_dung": None}


def _p(don_vi, cho_trong, gia_tri):
    """Phép `dien` đúng hình dạng node trả và bảng lưu (không khoá thừa)."""
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": cho_trong, "gia_tri": gia_tri}


def _doan(loai, don_vi, noi_dung=None):
    return {"loai": loai, "don_vi": don_vi, "cho_trong": None, "gia_tri": None, "noi_dung": noi_dung}


def _ra(phep, muc_dich="tao_van_ban", nhan="A") -> dict:
    return {
        "muc_dich": muc_dich,
        "mo_ta": "Giấy tiếp nhận",
        "tra_loi_ngan": "Đã điền.",
        "quan_sat": [],
        "suy_luan": [],
        "can_du_kien": [],
        "phep_tinh": [],
        "truong": [],
        "khac_biet": [],
        "dieu_khoan": [],
        "khuon": {"tai_lieu": nhan, "phep_sua": phep},
    }


def _chay(phep, cau=CAU, tai_lieu=TL_KHUON, **st):
    llm = _LLM(_ra(phep, **{k: st.pop(k) for k in ("muc_dich", "nhan") if k in st}))
    ra = h.hieu_tai_lieu({"query": cau, "cau_hoi_goc": cau, **st}, tai_lieu, llm, "m")
    return ra, llm


# ─────────────────────────────────────────────── prompt và lược đồ khuôn gốc


def test_khuon_goc_dung_prompt_v2_va_luoc_do_khuon_khong_van_ban():
    _, llm = _chay([])
    props = llm.json_schema["properties"]
    assert "khuon" in props and "van_ban" not in props
    assert "khuon" in llm.json_schema["required"] and "van_ban" not in llm.json_schema["required"]
    phep = props["khuon"]["properties"]["phep_sua"]["items"]
    assert phep["required"] == ["loai", "don_vi", "cho_trong", "gia_tri", "noi_dung"]
    assert phep["properties"]["loai"]["enum"] == ["dien", "thay", "chen_sau", "xoa"]
    assert props["khuon"]["properties"]["tai_lieu"]["enum"] == ["A"]
    assert "# Khuôn gốc" in llm.prompt, "prompt v2 mang mục khuôn gốc"


def test_prompt_liet_ke_cho_trong_ngay_duoi_don_vi():
    _, llm = _chay([])
    assert "[A-2] (tr. 1) Điện thoại: ……………… Fax: ………………\n  chỗ trống: 0 «Điện thoại:» | 1 «Fax:»" in llm.prompt
    # Đơn vị không có địa chỉ ghim thì không điền được — không mời mô hình điền nó.
    assert "«Ghi chú:»" not in llm.prompt


def test_tai_lieu_khong_khuon_goc_giu_nguyen_duong_html():
    llm = _LLM(
        {"muc_dich": "hoi", "mo_ta": "x", "tra_loi_ngan": "y", "quan_sat": [], "suy_luan": [], "can_du_kien": []}
    )
    tl = [{**TL_KHUON[0], "co_khuon_goc": False, "dinh_dang": None}]
    h.hieu_tai_lieu({"query": CAU}, tl, llm, "m")
    assert "van_ban" in llm.json_schema["properties"] and "khuon" not in llm.json_schema["properties"]
    assert "chỗ trống:" not in llm.prompt and "# Khuôn gốc" not in llm.prompt
    assert llm.prompt == h.PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=CAU,
        tai_lieu=h._khoi_tai_lieu([{**tl[0], "nhan": "A", "gui": h.loc_don_vi(DV_M05, CAU)}]),
        phan_doan="",
        ban_thao_dang_co="",
        bo_nho="",
    ), "đường HTML render đúng từng byte như trước"


def test_pdf_chi_nhan_dien_va_thay():
    tl = [
        {
            **TL_KHUON[0],
            "dinh_dang": "pdf",
            "don_vi": [
                DonViVanBan(
                    chi_so=0,
                    trang=1,
                    offset_dau=0,
                    noi_dung="Họ tên: ……",
                    hop=(10, 10, 200, 24),
                    cho_trong=(ChoTrong(so=0, kieu="cham", nhan="Họ tên:", hop=(60, 10, 200, 24), co_chu=14.0),),
                )
            ],
        }
    ]
    ra, llm = _chay([_doan("chen_sau", 0, "Thêm"), _doan("xoa", 0), _dien(0, 0, "Nguyễn Văn Thử")], tai_lieu=tl)
    assert llm.json_schema["properties"]["khuon"]["properties"]["phep_sua"]["items"]["properties"]["loai"]["enum"] == [
        "dien",
        "thay",
    ]
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "dien", "don_vi": 0, "cho_trong": 0, "gia_tri": "Nguyễn Văn Thử"}]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["loai_khong_ho_tro", "loai_khong_ho_tro"]


# ──────────────────────────────────────────── phép kiểm tất định trước khi lưu


def test_luot_tao_giu_gia_tri_co_nguon_bo_gia_tri_khong_nguon():
    nho = [{"loai": "ca_nhan", "khoa": "nganh", "gia_tri": "Luật kinh tế"}]
    ra, _ = _chay(
        [
            _dien(1, 0, "Công ty Mẫu Thử"),
            # Số điện thoại người hỏi TỰ NÓI là một giá trị điền hợp lệ: luật
            # định danh của `_vuong_luoi_chan` không áp cho `dien`.
            _dien(2, 0, "0912345678"),
            _dien(2, 1, "0243999888"),  # không ai nói số fax này
            _dien(3, 0, "Luật kinh tế"),  # ký ức, lượt này không hỏi tới ngành
            _doan("thay", 5, "Đồng ý tiếp nhận theo Điều 5 Nghị định 45/2019."),
            _dien(6, 0, "x"),  # đơn vị không có địa chỉ
            _dien(4, 0, "Nguyễn Văn Thử"),
        ],
        bo_nho_tai_khoan=nho,
    )
    k = ra["khuon_tong_quat"]
    assert ra["van_ban_tong_quat"] is None and ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert k["viec_id"] == A_ID and k["dinh_dang"] == "docx"
    assert k["phep_sua"] == [
        {"loai": "dien", "don_vi": 1, "cho_trong": 0, "gia_tri": "Công ty Mẫu Thử"},
        {"loai": "dien", "don_vi": 2, "cho_trong": 0, "gia_tri": "0912345678"},
        # Chỗ trống `tab`: bộ áp đặt giá trị ngay sau nhãn, không có dấu cách.
        {"loai": "dien", "don_vi": 4, "cho_trong": 0, "gia_tri": " Nguyễn Văn Thử"},
    ]
    assert [(b["don_vi"], b["cho_trong"], b["ly_do"]) for b in k["bo_qua"]] == [
        (2, 1, "khong_nguon"),
        (3, 0, "bo_nho"),
        (5, None, "dieu_luat"),
        (6, 0, "khong_co_dia_chi"),
    ]
    tr = ra["traces"]
    assert tr["khuon_so_phep_giu"] == 3 and tr["khuon_so_phep_bo"] == 4
    assert tr["khuon_bo_khong_nguon"] == 1 and tr["khuon_bo_bo_nho"] == 1 and tr["khuon_bo_dieu_luat"] == 1
    # Đếm, không chép: không khoá traces nào mang giá trị đã điền.
    assert "0912345678" not in json.dumps(tr, ensure_ascii=False)
    assert k["cho_trong"][:2] == [
        {"don_vi": 1, "so": 0, "kieu": "cham", "nhan": "Cơ quan/Đơn vị tiếp nhận:"},
        {"don_vi": 2, "so": 0, "kieu": "cham", "nhan": "Điện thoại:"},
    ]
    assert all(c["don_vi"] != 6 for c in k["cho_trong"])


def test_thay_giu_so_dieu_co_san_trong_don_vi_goc_va_chuan_hoa_xuong_dong():
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "Thực hiện theo Điều 5 của quy chế.")]}]
    ra, _ = _chay(
        [
            _doan("thay", 7, "Thực hiện theo Điều 5 của quy chế.\r\nKhông áp dụng ngoại lệ."),
            _doan("chen_sau", 5, "Mã số sinh viên 20260099."),
        ],
        tai_lieu=tl,
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        {"loai": "thay", "don_vi": 7, "noi_dung": "Thực hiện theo Điều 5 của quy chế.\nKhông áp dụng ngoại lệ."},
    ]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["khong_nguon"], "con số bịa trong đoạn chèn cũng bị bỏ"


def test_gia_tri_rong_la_go_cho_dien_va_hinh_dang_sai_bi_bo():
    ra, _ = _chay(
        [
            _dien(1, 0, ""),
            _dien(1, 0, None),
            _dien(1, 5, "Công ty Mẫu Thử"),
            _dien(1, 0, "………"),
            {"loai": "doi_mau", "don_vi": 1},
            _dien(99, 0, "x"),
            _dien(1, 0, "Công ty\nMẫu Thử"),
        ],
        muc_dich="sua_ban_thao",
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "dien", "don_vi": 1, "cho_trong": 0, "gia_tri": ""}]
    assert [b["ly_do"] for b in k["bo_qua"]] == [
        "sai_hinh_dang",
        "khong_co_cho_trong",
        "vung_trong",
        "sai_hinh_dang",
        "khong_co_don_vi",
        "sai_hinh_dang",
    ]


def test_ky_uc_duoc_hoi_toi_thi_dien_duoc():
    nho = [{"loai": "ca_nhan", "khoa": "nganh", "gia_tri": "Luật kinh tế"}]
    ra, _ = _chay([_dien(3, 0, "Luật kinh tế")], cau="điền ngành của tôi vào", bo_nho_tai_khoan=nho)
    assert ra["khuon_tong_quat"]["phep_sua"] == [
        {"loai": "dien", "don_vi": 3, "cho_trong": 0, "gia_tri": "Luật kinh tế"}
    ]


def test_luot_khong_soan_thi_khong_co_khuon_tong_quat():
    ra, _ = _chay([_dien(1, 0, "Công ty Mẫu Thử")], muc_dich="tom_tat")
    assert ra["khuon_tong_quat"] is None and ra["van_ban_tong_quat"] is None


# ───────────────────────────────────────────────────────────── lượt sửa


DANG_MO = {
    "document": "# BM.M05\n\n- Cơ quan/Đơn vị tiếp nhận: Công ty Mẫu Thử\n- Điện thoại: 0912345678\n",
    "audit": {"muc_kiem": "tong_quat"},
    "viec_id": A_ID,
    "phep_sua": [
        {"loai": "dien", "don_vi": 1, "cho_trong": 0, "gia_tri": "Công ty Mẫu Thử"},
        {"loai": "dien", "don_vi": 2, "cho_trong": 0, "gia_tri": "0912345678"},
    ],
}


def test_luot_sua_cho_mo_hinh_thay_gia_tri_hien_tai_va_chi_tra_thay_doi():
    ra, llm = _chay(
        [_dien(2, 1, "0243999888")],
        cau="đổi fax thành 0243999888",
        muc_dich="sua_ban_thao",
        ban_thao_tong_quat_dang_mo=DANG_MO,
    )
    assert "chỗ trống: 0 «Điện thoại:» = «0912345678» | 1 «Fax:»" in llm.prompt
    assert ra["muc_dich_tai_lieu"] == "sua_ban_thao"
    assert ra["khuon_tong_quat"]["phep_sua"] == [
        {"loai": "dien", "don_vi": 2, "cho_trong": 1, "gia_tri": "0243999888"},
    ]


class _BanThaoGia:
    """`ban_thao` giả cho `dung_ban_thao_tong_quat` — ghi lại `ket` được lưu."""

    def __init__(self, cu: dict | None):
        self.cu, self.tao_ket, self.sua_ket = cu, None, None

    def moi_nhat(self, sub, pid, loai):
        return self.cu

    def tao(self, sub, pid, loai, facts, ket):
        self.tao_ket = ket
        return {
            "id": "bt-moi",
            "phien_ban": 1,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "facts": facts,
        }

    def sua(self, sub, id, facts, ket):
        self.sua_ket = ket
        return {
            "id": id,
            "phien_ban": 2,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "facts": facts,
        }


@pytest.fixture
def bt_gia(monkeypatch):
    def _dung(cu):
        g = _BanThaoGia(cu)
        monkeypatch.setattr(ban_thao, "moi_nhat_cua_hoi_thoai", g.moi_nhat)
        monkeypatch.setattr(ban_thao, "tao", g.tao)
        monkeypatch.setattr(ban_thao, "sua", g.sua)
        monkeypatch.setattr(bao_ve, "plan_hieu_luc", lambda sub: "free")
        monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **k: None)
        monkeypatch.setattr(d, "_ghi_traces", lambda *a, **k: None)
        return g

    return _dung


def _khuon(phep, cho=None):
    return {
        "viec_id": A_ID,
        "ten_tep": "BM.M05.docx",
        "dinh_dang": "docx",
        "phep_sua": phep,
        "bo_qua": [],
        "cho_trong": cho or h.cho_trong_khuon(TL_KHUON[0]),
    }


def test_luot_sua_gop_thay_doi_giu_o_da_dien_tu_khung_dien(bt_gia):
    cu = {"id": "bt-1", "viec_id": A_ID, "so_lan_sua": 1, "clauses": [], "phep_sua": DANG_MO["phep_sua"]}
    g = bt_gia(cu)
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": "u",
            "hoi_thoai_id": "p",
            "muc_dich_tai_lieu": "sua_ban_thao",
            "khuon_tong_quat": _khuon([_p(2, 1, "0243999888"), _p(1, 0, "")]),
        }
    )
    assert g.tao_ket is None, "cùng khuôn gốc: lượt sửa lên phiên bản mới, không mở bản thứ hai"
    assert g.sua_ket["phep_sua"] == [_p(2, 0, "0912345678"), _p(2, 1, "0243999888")], (
        "ô điền cũ giữ, ô mới thêm, gia_tri rỗng gỡ ô"
    )
    assert g.sua_ket["viec_id"] == A_ID and g.sua_ket["clauses"] == []
    assert g.sua_ket["document"] == "# BM.M05\n\n- Điện thoại: 0912345678\n- Fax: 0243999888\n"
    assert g.sua_ket["audit_report"]["muc_kiem"] == "tong_quat"
    bt = ra["ban_thao_ket"]
    assert bt["viec_id"] == A_ID and bt["phep_sua"] == g.sua_ket["phep_sua"]
    assert bt["doi_so_voi_truoc"] == ["Cơ quan/Đơn vị tiếp nhận:", "Fax:"]


def test_luot_sua_khong_doi_gi_thi_khong_len_phien_ban(bt_gia):
    cu = {"id": "bt-1", "viec_id": A_ID, "so_lan_sua": 1, "clauses": [], "phep_sua": DANG_MO["phep_sua"]}
    g = bt_gia(cu)
    ra = d.dung_ban_thao_tong_quat(
        {"user_sub": "u", "hoi_thoai_id": "p", "muc_dich_tai_lieu": "sua_ban_thao", "khuon_tong_quat": _khuon([])}
    )
    assert g.sua_ket is None and ra["ban_thao_ket"] is None
    assert ra["ban_thao_tong_quat_loi"] == d.KHONG_DOI_KHUON


def test_ban_thao_dang_mo_tren_khuon_khac_thi_mo_ban_moi(bt_gia):
    g = bt_gia({"id": "bt-html", "viec_id": None, "so_lan_sua": 0, "clauses": [{"key": "muc_1"}]})
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": "u",
            "hoi_thoai_id": "p",
            "muc_dich_tai_lieu": "sua_ban_thao",
            "khuon_tong_quat": _khuon([_p(1, 0, "Công ty Mẫu Thử")]),
        }
    )
    assert g.sua_ket is None and g.tao_ket["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử")]
    assert ra["ban_thao_ket"]["id"] == "bt-moi"


def test_nhan_tao_van_ban_tren_khuon_da_co_ban_thao_van_la_luot_sua(bt_gia):
    """Mô hình gán `tao_van_ban` cho một lời xin sửa: bản thảo mới nhất nằm trên
    đúng khuôn này nên lượt vẫn là một phiên bản mới của nó, ô cũ không mất."""
    cu = {"id": "bt-1", "viec_id": A_ID, "so_lan_sua": 1, "clauses": [], "phep_sua": DANG_MO["phep_sua"]}
    g = bt_gia(cu)
    d.dung_ban_thao_tong_quat(
        {
            "user_sub": "u",
            "hoi_thoai_id": "p",
            "muc_dich_tai_lieu": "tao_van_ban",
            "khuon_tong_quat": _khuon([_p(2, 1, "0243999888")]),
        }
    )
    assert g.tao_ket is None
    assert g.sua_ket["phep_sua"] == [*DANG_MO["phep_sua"], _p(2, 1, "0243999888")]


def test_luot_tao_khong_gia_tri_nao_van_dung_ban_de_dien_tay(bt_gia):
    g = bt_gia(None)
    ra = d.dung_ban_thao_tong_quat(
        {"user_sub": "u", "hoi_thoai_id": "p", "muc_dich_tai_lieu": "tao_van_ban", "khuon_tong_quat": _khuon([])}
    )
    assert g.tao_ket["phep_sua"] == [] and g.tao_ket["document"] == "# BM.M05\n"
    assert ra["ban_thao_ket"]["phep_sua"] == []


# ───────────────────────────────────────────────── không cắt ngầm, trần chi phí


def _dai(so_don_vi: int, ky_tu: int) -> list[dict]:
    dv = [
        _dv(i, (f"Đoạn {i} " + "nội dung biểu mẫu " * 40)[:ky_tu], trang=i * 10 // so_don_vi + 1)
        for i in range(so_don_vi)
    ]
    return [{**TL_KHUON[0], "don_vi": dv}]


def test_khuon_goc_10_trang_45000_ky_tu_di_tron_mot_luot():
    tl = _dai(100, 450)
    assert sum(len(x.noi_dung) for x in tl[0]["don_vi"]) == 45_000
    assert max(x.trang for x in tl[0]["don_vi"]) == 10
    _, llm = _chay([], tai_lieu=tl)
    assert llm.so_lan_goi == 1, "không chia lượt: đầu ra là danh sách phép, nhỏ"
    assert all(f"[A-{i}] " in llm.prompt for i in range(100)), "không đơn vị nào bị cắt"


def test_cung_tai_lieu_khong_khuon_goc_van_loc_nhu_cu():
    tl = [{**_dai(100, 450)[0], "co_khuon_goc": False}]
    assert len(h.loc_don_vi(tl[0]["don_vi"], CAU)) < 100


def test_khuon_goc_qua_tran_chi_phi_thi_tu_choi_khong_cat():
    ra, llm = _chay([], tai_lieu=_dai(110, 470))
    assert llm.so_lan_goi == 0
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == h.QUA_DAI
    assert ra["traces"]["hieu_tai_lieu_nguon"] == "vuot_tran" and ra["khuon_tong_quat"] is None


# ─────────────────────────────────────────────────────────────── assemble


class _No:
    def chat(self, *a, **k):  # pragma: no cover
        raise AssertionError("assemble không gọi mô hình cho bản thảo khuôn gốc")


def _cho(n: int) -> list[dict]:
    return [{"don_vi": i, "so": 0, "kieu": "cham", "nhan": f"Nhãn số {i} " + "x" * 50} for i in range(n)]


def test_assemble_noi_so_cho_da_dien_va_liet_ke_cho_con_trong_co_tran():
    cho = _cho(30)
    phep = [_p(0, 0, "A"), _p(1, 0, "B")]
    st = {
        "query": "điền giúp",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "tai_lieu_ket": {"tai_lieu_da_dung": [{"id": A_ID}]},
        "ban_thao_ket": {
            "id": "bt",
            "loai": "tong_quat",
            "ten": d.TEN_TONG_QUAT,
            "phien_ban": 1,
            "document": "# BM",
            "clauses": [],
            "audit_report": {},
            "facts": {},
            "doi_so_voi_truoc": [],
            "viec_id": A_ID,
            "phep_sua": phep,
            "khuon": None,
        },
        "khuon_tong_quat": {
            **_khuon(phep, cho),
            "bo_qua": [
                {"don_vi": 5, "cho_trong": 0, "ly_do": "khong_nguon"},
                {"don_vi": 12, "cho_trong": None, "ly_do": "dieu_luat"},
                *({"don_vi": i, "cho_trong": 0, "ly_do": "khong_nguon"} for i in range(6, 12)),
            ],
        },
    }
    ra = assemble(st, {}, _No(), "m")
    assert ra["result_type"] is ResultType.ban_thao and ra["ban_thao"]["viec_id"] == A_ID
    assert "đã điền 2/30 chỗ trống" in ra["answer"]
    assert "Còn trống: «Nhãn số 2 " in ra["answer"] and "và 24 chỗ khác" in ra["answer"]
    assert ra["answer"].count("«") == 4 and len(ra["answer"]) <= TRAN_KY_TU
    assert "sửa 0 đoạn" not in ra["answer"] and "đã đổi" not in ra["answer"]
    assert ra["coverage_note"] and len(ra["coverage_note"]) <= 160
    assert ra["coverage_note"].startswith("Không áp 8 thay đổi") and "«Nhãn số 5 " in ra["coverage_note"]


def test_assemble_khuon_du_het_thi_khong_liet_ke_va_khong_ghi_chu():
    cho = _cho(1)
    phep = [_p(0, 0, "A")]
    st = {
        "query": "q",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 1, "viec_id": A_ID, "phep_sua": phep, "clauses": []},
        "khuon_tong_quat": _khuon(phep, cho),
    }
    ra = assemble(st, {}, _No(), "m")
    assert "đã điền 1/1 chỗ trống" in ra["answer"] and "Còn trống" not in ra["answer"]
    assert ra["coverage_note"] is None


# ──────────────────────────────────────────────── bộ nhớ và đường checklist


class _LlmDem:
    def __init__(self):
        self.so_lan_goi = 0

    def chat(self, *a, **k):  # pragma: no cover - phải không bao giờ được gọi
        self.so_lan_goi += 1
        raise AssertionError("không được gọi mô hình bộ nhớ cho lượt soạn trên khuôn gốc")


def test_luot_soan_tren_khuon_goc_khong_gop_ho_so_tai_khoan(monkeypatch):
    """FR-028 — `cap_nhat_phien` không chạy (0 lượt gọi mô hình, 0 truy vấn) cho
    lượt có bản thảo khuôn gốc; bản thảo HTML vẫn gộp như cũ."""
    monkeypatch.setattr(bo_nho.hoi_thoai, "bo_nho_cua_phien", lambda *_: pytest.fail("không được chạm DB"))
    payload = {"result_type": "ban_thao", "ban_thao": {"id": "bt", "viec_id": A_ID}}
    rt = bo_nho.loai_luot(payload)
    assert rt in bo_nho.KHONG_GOP_HO_SO
    llm = _LlmDem()
    bo_nho.cap_nhat_phien("pid", "sub", llm, "m", rt)
    assert llm.so_lan_goi == 0
    assert bo_nho.loai_luot({"result_type": "ban_thao", "ban_thao": {"id": "bt", "viec_id": None}}) == "ban_thao"
    assert bo_nho.loai_luot({"result_type": "answer"}) == "answer"


def test_duong_checklist_khong_doi_khi_tai_lieu_co_khuon_goc():
    """Checklist đang mở dở vẫn đi `gom_du_kien` → `dung_ban_thao` (mẫu của KLAW),
    kể cả khi hội thoại giữ một tài liệu có khuôn gốc (quyết định 2026-09-26 mục 3)."""
    from src.agents.graph_tra_cuu import _re_sau_gom_du_kien, _re_sau_route
    from src.agents.nodes.route import Intent

    st = {
        "intent": Intent.soan_thao,
        "user_sub": "u",
        "soan_thao_dang_mo": {"loai": "don_xin_nghi_viec", "facts": {}, "du": True},
        "tai_lieu_phien": [{"id": A_ID, "ten_tep": "BM.M05.docx", "co_khuon_goc": True}],
    }
    assert _re_sau_route(st) == "gom_du_kien"
    assert _re_sau_gom_du_kien(st) == "dung_ban_thao"


# ─────────────────────────────────────────── graph wrapper (Postgres cục bộ)


@pytest.fixture
def phien():
    from sqlalchemy import text

    from src.services.db import get_engine

    with get_engine().begin() as c:
        sub = str(c.execute(text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")).scalar_one())
        ht = str(
            c.execute(
                text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (CAST(:u AS uuid), 'thử') RETURNING id"),
                {"u": sub},
            ).scalar_one()
        )
    yield sub, ht
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:u AS uuid)"), {"u": sub})
        c.execute(text("DELETE FROM traces WHERE user_sub = :u"), {"u": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:u AS uuid)"), {"u": sub})


def _viec(sub: str, ht: str) -> str:
    from sqlalchemy import text

    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    with get_engine().begin() as c:
        vid = str(
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu (user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, so_trang, "
                    "trang_thai) VALUES (CAST(:u AS uuid), CAST(:h AS uuid), 'BM.M05.docx', 'sha256:x len=1', 100, 1, "
                    "'xong') RETURNING id"
                ),
                {"u": sub, "h": ht},
            ).scalar_one()
        )
    tl.luu_don_vi(get_engine(), vid, DV_M05)
    return vid


@pytest.mark.integration
def test_graph_nap_tai_lieu_kem_khuon_goc_theo_chu(phien):
    from src.agents.graph_tra_cuu import _nap_tai_lieu
    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    sub, ht = phien
    co, khong = _viec(sub, ht), _viec(sub, ht)
    tl.luu_khuon_goc(get_engine(), co, "docx", b"PK\x03\x04", [[595.0, 842.0], [595.0, 842.0]])
    ra = _nap_tai_lieu(get_engine(), [co, khong, str(uuid.uuid4())], {co: "BM.M05.docx"}, sub)
    assert [(t["id"], t["viec_id"], t["co_khuon_goc"], t["dinh_dang"], t["so_trang"]) for t in ra] == [
        (co, co, True, "docx", 2),
        (khong, khong, False, None, None),
    ]
    assert ra[0]["ten_tep"] == "BM.M05.docx" and ra[0]["don_vi"][2].cho_trong[1].nhan == "Fax:"
    assert _nap_tai_lieu(get_engine(), [co], {}, str(uuid.uuid4())) == [], "tài liệu người khác không đọc được"
    assert tl.khuon_goc_nhe(get_engine(), co, str(uuid.uuid4())) is None


@pytest.mark.integration
def test_luu_that_ban_thao_khuon_goc_qua_ban_thao_tao(phien):
    from src.services import hoi_thoai

    sub, _ = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    pid = hoi_thoai.tao_phien(sub, "điền biểu mẫu")
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": sub,
            "hoi_thoai_id": pid,
            "muc_dich_tai_lieu": "tao_van_ban",
            "khuon_tong_quat": _khuon([_p(1, 0, "Công ty Mẫu Thử")]),
        }
    )
    bt = ra["ban_thao_ket"]
    assert bt["phien_ban"] == 1 and bt["loai"] == "tong_quat" and bt["clauses"] == []
    assert bt["document"] == "# BM.M05\n\n- Cơ quan/Đơn vị tiếp nhận: Công ty Mẫu Thử\n"
    assert bt["viec_id"] == A_ID and bt["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử")]


# ─────────────────────────────────────── tệp thật của chủ dự án (không commit)


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_phep_giu_lai_ap_duoc_len_khuon_goc():
    from src.services.dien_khuon import ap_dung_docx
    from src.services.doc_tai_lieu import doc
    from src.services.tai_lieu import _hang_don_vi

    goc = BM_M05.read_bytes()
    don_vi = doc(BM_M05.name, goc).don_vi
    dt = next(x for x in don_vi if x.noi_dung.startswith("Điện thoại:"))
    nganh = next(x for x in don_vi if x.noi_dung.startswith("Ngành:"))
    tl = [
        {
            "id": A_ID,
            "viec_id": A_ID,
            "ten_tep": BM_M05.name,
            "don_vi": don_vi,
            "co_khuon_goc": True,
            "dinh_dang": "docx",
            "so_trang": 2,
        }
    ]
    ra, llm = _chay(
        [_dien(dt.chi_so, 0, "0912345678"), _dien(dt.chi_so, 1, "0243999888"), _dien(nganh.chi_so, 0, "Luật kinh tế")],
        cau="Điện thoại của cơ quan là 0912345678, ngành Luật kinh tế",
        tai_lieu=tl,
    )
    assert "«Điện thoại:» | 1 «Fax:»" in llm.prompt
    phep = ban_thao.gop_phep_sua([], ra["khuon_tong_quat"]["phep_sua"])
    assert len(phep) == 2
    hang = json.loads(json.dumps([_hang_don_vi(x) for x in don_vi], ensure_ascii=False))
    moi, bc = ap_dung_docx(goc, hang, phep)
    assert bc == {"da_ap": [0, 1], "bo_qua": []}
    moi_dv = doc(BM_M05.name, moi).don_vi
    assert moi_dv[dt.chi_so].noi_dung.startswith("Điện thoại: 0912345678")
    assert "Fax: ……" in moi_dv[dt.chi_so].noi_dung, "chỗ không có nguồn giữ nguyên dãy chấm"
    assert moi_dv[nganh.chi_so].noi_dung.startswith("Ngành: Luật kinh tế")
