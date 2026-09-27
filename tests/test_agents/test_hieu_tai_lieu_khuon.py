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
6. Quyết định owner 2026-09-27: lượt soạn trên khuôn gốc luôn dựng phiên bản 1 (phép
   rỗng là chính tệp tải lên); chỉ `van_ban_khac` không dựng gì và chỉ sang checklist.
7. Luật owner 2026-09-27 ("nếu người dùng yêu cầu sửa thì hãy sửa, còn nếu bảo soạn
   thảo văn bản ra thì phải đúng 100%"): `tao_lai` bỏ MỌI phép mô hình đề xuất — bản
   thảo đúng từng byte tệp tải lên; `dien_sua` (mặc định khi thiếu hay lạ) chỉ nhận giá
   trị NGƯỜI HỎI đưa ra — chữ của tài liệu không phải nguồn cho giá trị mới.
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


def _doan(loai, don_vi, noi_dung=None, doan=None):
    return {"loai": loai, "don_vi": don_vi, "cho_trong": None, "gia_tri": None, "noi_dung": noi_dung, "doan": doan}


def _ra(phep, muc_dich="tao_van_ban", nhan="A", yeu_cau="dien_sua", khong_dat=(), quan_sat=()) -> dict:
    """`yeu_cau=None`: mô hình bỏ trường này (ngoài lược đồ strict)."""
    return {
        "muc_dich": muc_dich,
        "mo_ta": "Giấy tiếp nhận",
        "tra_loi_ngan": "Đã điền.",
        "quan_sat": list(quan_sat),
        "suy_luan": [],
        "can_du_kien": [],
        "phep_tinh": [],
        "truong": [],
        "khac_biet": [],
        "dieu_khoan": [],
        "khuon": {
            "tai_lieu": nhan,
            **({"yeu_cau": yeu_cau} if yeu_cau else {}),
            "phep_sua": phep,
            "khong_dat": list(khong_dat),
        },
    }


def _chay(phep, cau=CAU, tai_lieu=TL_KHUON, **st):
    llm = _LLM(_ra(phep, **{k: st.pop(k) for k in ("muc_dich", "nhan", "yeu_cau", "khong_dat", "quan_sat") if k in st}))
    ra = h.hieu_tai_lieu({"query": cau, "cau_hoi_goc": cau, **st}, tai_lieu, llm, "m")
    return ra, llm


# ─────────────────────────────────────────────── prompt và lược đồ khuôn gốc


def test_khuon_goc_dung_prompt_v2_va_luoc_do_khuon_khong_van_ban():
    _, llm = _chay([])
    props = llm.json_schema["properties"]
    assert "khuon" in props and "van_ban" not in props
    assert "khuon" in llm.json_schema["required"] and "van_ban" not in llm.json_schema["required"]
    phep = props["khuon"]["properties"]["phep_sua"]["items"]
    assert phep["required"] == ["loai", "don_vi", "cho_trong", "gia_tri", "noi_dung", "doan"]
    assert phep["properties"]["doan"] == {"anyOf": [{"type": "null"}, {"type": "integer"}]}
    assert phep["properties"]["loai"]["enum"] == ["dien", "thay", "chen_sau", "xoa"]
    assert props["khuon"]["properties"]["tai_lieu"]["enum"] == ["A"]
    assert props["khuon"]["required"] == ["tai_lieu", "yeu_cau", "phep_sua", "khong_dat"]
    assert props["khuon"]["properties"]["yeu_cau"] == {
        "type": "string",
        "enum": ["tao_lai", "dien_sua", "van_ban_khac"],
    }
    assert props["khuon"]["properties"]["khong_dat"] == {"type": "array", "items": {"type": "string"}}
    assert "# Khuôn gốc" in llm.prompt, "prompt v2 mang mục khuôn gốc"
    # Ví dụ của luật owner 2026-09-27, mỗi giá trị `yeu_cau` có câu của nó.
    for vi_du in ('"soạn thảo văn bản này cho tôi"', '"tạo lại văn bản này"', '"xuất file này"'):
        assert vi_du in llm.prompt
    assert "`tao_lai`" in llm.prompt and "`dien_sua`" in llm.prompt and "`van_ban_nay`" not in llm.prompt
    assert '"điền giúp tôi' in llm.prompt and '"sửa ' in llm.prompt
    assert '"dựa vào hợp đồng này soạn đơn xin nghỉ việc"' in llm.prompt and "`van_ban_khac`" in llm.prompt
    assert "`khuon.khong_dat`" in llm.prompt, "giá trị không đặt được thì báo lại, không đoán chỗ"
    assert "bảng danh sách" in llm.prompt, "ô trống của bảng danh sách điền bằng `thay`"


def test_prompt_liet_ke_cho_trong_ngay_duoi_don_vi():
    _, llm = _chay([])
    # Nhãn qua `nhan_sach` cả với hàng lưu trước bộ đọc làm sạch nhãn: cùng tên
    # với trang (`ban_thao.cho_trong_khuon`).
    assert "[A-2] (tr. 1) Điện thoại: ……………… Fax: ………………\n  chỗ trống: 0 «Điện thoại» | 1 «Fax»" in llm.prompt
    # Đơn vị không có địa chỉ ghim thì không điền được — không mời mô hình điền nó.
    assert "«Ghi chú" not in llm.prompt


# Ô tiêu đề thư của BM.M05 như bộ đọc trả (đo trên tệp thật 2026-09-27): ba đoạn
# thô — tên cơ quan, một đoạn rỗng, "Số …./…." — nên "Số" là `doan` 2.
O_TIEU_DE = DonViVanBan(
    chi_so=3,
    trang=1,
    offset_dau=0,
    noi_dung="TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….",
    bang=(0, 1, 0),
    dia_chi=DiaChi("word/document.xml", (1, 3, 1)),
    cho_trong=(
        ChoTrong(so=0, kieu="cham", nhan="Số", doan=2, dau=3, cuoi=5),
        ChoTrong(so=1, kieu="cham", nhan="/", doan=2, dau=6, cuoi=8),
    ),
    doan_chu=("TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN", "", "Số …./…."),
)
CO_QUAN = DonViVanBan(
    chi_so=6,
    trang=1,
    offset_dau=0,
    noi_dung="Cơ quan/Đơn vị tiếp nhận: ………….",
    dia_chi=DiaChi("word/document.xml", (4,)),
    cho_trong=(ChoTrong(so=0, kieu="cham", nhan="Cơ quan/Đơn vị tiếp nhận:", dau=26, cuoi=31),),
    doan_chu=("Cơ quan/Đơn vị tiếp nhận: ………….",),
)
HO_TEN_TAB = DonViVanBan(
    chi_so=7,
    trang=1,
    offset_dau=0,
    noi_dung="Họ và tên:",
    dia_chi=DiaChi("word/document.xml", (5,)),
    cho_trong=(ChoTrong(so=0, kieu="tab", nhan="Họ và tên:", dau=10, cuoi=10),),
    doan_chu=("Họ và tên:",),
)


def _tl(*don_vi: DonViVanBan) -> list[dict]:
    return [{**TL_KHUON[0], "don_vi": list(don_vi)}]


def test_prompt_dat_dau_cho_trong_TAI_CHO_va_danh_so_doan_cua_don_vi_nhieu_doan():
    """Nguyên nhân (a) owner quan sát: danh sách «Số» | «/» tách khỏi câu nên mô hình
    không thấy chỗ trống nằm đâu. Nay mỗi chỗ trống đứng đúng chỗ của nó; `¶n` là
    số `doan` thật (đoạn rỗng vẫn được đếm) để `thay` trỏ đúng một đoạn."""
    _, llm = _chay([], tai_lieu=_tl(O_TIEU_DE, CO_QUAN, HO_TEN_TAB))
    assert "[A-3] (tr. 1, bảng 1 hàng 2 cột 1) ¶0 TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN ¶2 Số ⟦0⟧/⟦1⟧\n" in llm.prompt
    assert "[A-6] (tr. 1) Cơ quan/Đơn vị tiếp nhận: ⟦0⟧\n" in llm.prompt
    assert "[A-7] (tr. 1) Họ và tên: ⟦0⟧" in llm.prompt, "chỗ `tab`: dấu ngay sau nhãn"
    assert "chỗ trống:" not in llm.prompt.split("## Tài liệu A")[1].split("# Quy tắc")[0]


def test_prompt_luot_sua_mang_gia_tri_dang_dien_trong_dau():
    dang_mo = {**DANG_MO, "phep_sua": [_p(3, 0, "12"), _p(6, 0, "Công ty Mẫu Thử")]}
    _, llm = _chay([], muc_dich="sua_ban_thao", tai_lieu=_tl(O_TIEU_DE, CO_QUAN), ban_thao_tong_quat_dang_mo=dang_mo)
    assert "¶2 Số ⟦0=«12»⟧/⟦1⟧" in llm.prompt
    assert "Cơ quan/Đơn vị tiếp nhận: ⟦0=«Công ty Mẫu Thử»⟧" in llm.prompt


THAY_SO = {"loai": "thay", "don_vi": 3, "doan": 2, "noi_dung": "Số 12/2026"}


def test_prompt_luot_sua_doan_da_thay_hien_chu_moi_khong_con_dau():
    """Đoạn (hay cả đơn vị) mà bản thảo đang mở đã `thay` không còn dãy chấm nào:
    prompt hiện chữ HIỆN TẠI, không dấu — một dấu ở đó mời mô hình `dien` vào chỗ
    `gop_phep_sua` sẽ gỡ."""
    thay_cq = {"loai": "thay", "don_vi": 6, "noi_dung": "Cơ quan/Đơn vị tiếp nhận: Công ty TNHH Luật Việt"}
    dang_mo = {**DANG_MO, "phep_sua": [THAY_SO, thay_cq]}
    _, llm = _chay([], muc_dich="sua_ban_thao", tai_lieu=_tl(O_TIEU_DE, CO_QUAN), ban_thao_tong_quat_dang_mo=dang_mo)
    phan = llm.prompt.split("## Tài liệu A")[1].split("# Quy tắc")[0]
    assert "[A-3] (tr. 1, bảng 1 hàng 2 cột 1) ¶0 TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN ¶2 Số 12/2026\n" in phan
    assert "[A-6] (tr. 1) Cơ quan/Đơn vị tiếp nhận: Công ty TNHH Luật Việt" in phan
    assert "⟦" not in phan and "chỗ trống:" not in phan


@pytest.mark.parametrize(
    "hong",
    [
        {"doan_chu": ()},
        {"doan_chu": ("TÊN CƠ QUAN", "", "Số …./….")},
        {"cho_trong": (ChoTrong(so=0, kieu="cham", nhan="Số", doan=2, dau=0, cuoi=3),)},
        {"cho_trong": (ChoTrong(so=0, kieu="cham", nhan="Số", doan=5, dau=3, cuoi=5),)},
    ],
    ids=["dong_cu_khong_doan_chu", "chu_ghep_khac_noi_dung", "lat_khong_con_la_cham", "doan_vang"],
)
def test_khong_chung_minh_duoc_vi_tri_thi_lui_ve_dong_cho_trong(hong):
    """Không bao giờ đặt dấu sai chỗ: vị trí không chứng minh được thì đơn vị ấy giữ
    đúng dòng `chỗ trống:` như trước (dòng lưu trước `doan_chu` rơi vào đây)."""
    from dataclasses import replace

    _, llm = _chay([], tai_lieu=_tl(replace(O_TIEU_DE, **hong)))
    assert "[A-3] (tr. 1, bảng 1 hàng 2 cột 1) TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….\n  chỗ trống: 0 «Số»" in llm.prompt
    assert "⟦" not in llm.prompt.split("## Tài liệu A")[1].split("# Quy tắc")[0]


def test_prompt_noi_quy_uoc_dau_va_thay_cum_viet_hoa_giu_cho():
    _, llm = _chay([])
    assert "⟦n⟧" in llm.prompt and "¶n" in llm.prompt
    assert "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN" in llm.prompt and "`doan`" in llm.prompt
    # Cùng luật với phép kiểm: chữ `thay` thêm phải có nguồn; `doan` chỉ cho `thay`.
    assert "đừng tự viết lại câu bằng lời của bạn" in llm.prompt and "luôn để `doan` = `null`" in llm.prompt


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
        {"don_vi": 1, "so": 0, "kieu": "cham", "nhan": "Cơ quan/Đơn vị tiếp nhận", "doan": 0},
        {"don_vi": 2, "so": 0, "kieu": "cham", "nhan": "Điện thoại", "doan": 0},
    ]
    assert all(c["don_vi"] != 6 for c in k["cho_trong"])


def test_thay_giu_so_dieu_co_san_trong_don_vi_goc_va_chuan_hoa_xuong_dong():
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "Thực hiện theo Điều 5 của quy chế.")]}]
    ra, _ = _chay(
        [
            _doan("thay", 7, "Thực hiện theo Điều 5 của quy chế.\r\nKhông áp dụng ngoại lệ."),
            _doan("chen_sau", 5, "Mã số sinh viên 20260099."),
        ],
        # Chữ `thay` thêm phải có nguồn như mọi `thay`: người hỏi nói câu đó.
        cau="thêm vào đoạn đó: không áp dụng ngoại lệ",
        tai_lieu=tl,
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        {"loai": "thay", "don_vi": 7, "noi_dung": "Thực hiện theo Điều 5 của quy chế.\nKhông áp dụng ngoại lệ."},
    ]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["khong_nguon"], "con số bịa trong đoạn chèn cũng bị bỏ"


def test_thay_khong_dien_cho_trong_va_gia_tri_sau_nhan_phai_co_nguon():
    """`thay`/`chen_sau` không phải lối vòng qua phép nguồn của `dien`: `thay` trên
    đơn vị có chỗ trống mà THÊM chữ không có nguồn bị bỏ (`khong_nguon`, thay cho
    lời từ chối `co_cho_trong` cũ), và giá trị sau "Nhãn:" của một đoạn mới qua
    đúng phép nguồn ấy — dãy chấm đi kèm không rửa được nó. Luật owner 2026-09-27:
    MỌI chữ `chen_sau` thêm phải là lời người hỏi — nhãn chép từ chỗ khác của tài
    liệu ("Người liên hệ:", "Ghi chú:") cũng không phải."""
    nho = [{"loai": "ca_nhan", "khoa": "nganh", "gia_tri": "Luật kinh tế"}]
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "Người liên hệ: Nguyễn Văn Thử")]}]
    ra, _ = _chay(
        [
            _doan("thay", 1, "Cơ quan/Đơn vị tiếp nhận: Công ty Bịa Đặt"),
            _doan("thay", 4, "Họ và tên: Trần Thị Bịa"),
            _doan("thay", 3, "Ngành Luật kinh tế"),  # ký ức lượt này không hỏi tới
            _doan("thay", 7, "Người liên hệ: Trần Thị Bịa"),
            _doan("chen_sau", 5, "Họ và tên: Trần Thị Bịa ……"),
            _doan("chen_sau", 5, "Người liên hệ: Nguyễn Văn Thử."),
            _doan("chen_sau", 5, "Ghi chú: ……"),
            _doan("chen_sau", 5, "Nguyễn Văn Thử."),
        ],
        cau="điền giúp tôi, họ và tên Nguyễn Văn Thử",
        tai_lieu=tl,
        bo_nho_tai_khoan=nho,
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "chen_sau", "don_vi": 5, "noi_dung": "Nguyễn Văn Thử."}]
    assert [(b["don_vi"], b["ly_do"]) for b in k["bo_qua"]] == [
        (1, "khong_nguon"),
        (4, "khong_nguon"),
        (3, "khong_nguon"),
        (7, "khong_nguon"),
        (5, "khong_nguon"),
        (5, "khong_nguon"),
        (5, "khong_nguon"),
    ]


# ─────────────────────────────── `thay` theo đoạn (`doan`) và cụm giữ chỗ viết hoa
CAU_OWNER = (
    "Điền giúp tôi biểu mẫu này: tên cơ quan tiếp nhận là Công ty TNHH Luật Việt, số 12/2026, "
    "sinh viên Nguyễn Văn Ánh, thời gian từ 01/10/2026 đến 31/12/2026."
)


def test_thay_theo_doan_them_chu_co_nguon_thi_giu_khong_nguon_thi_bo():
    """Nguyên nhân (b): "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN" là chỗ để điền của biểu mẫu
    Việt Nam nhưng không phải dãy chấm. `thay` với `doan` thay đúng đoạn đó; mọi chữ
    nó THÊM so với chữ cũ của đoạn (không phân biệt hoa/thường, dấu) phải có nguồn
    như một giá trị `dien`. Thay một đoạn đang mang chỗ trống cũng được."""
    ra, _ = _chay(
        [
            _doan("thay", 3, "CÔNG TY TNHH LUẬT VIỆT", doan=0),
            _doan("thay", 3, "Ten co quan: CÔNG TY TNHH LUẬT VIỆT", doan=0),
            _doan("thay", 3, "Số 12/2026", doan=2),
            _doan("thay", 3, "CÔNG TY BỊA ĐẶT", doan=0),
            _doan("thay", 3, "CÔNG TY TNHH LUẬT VIỆT", doan=5),
            _doan("thay", 3, "CÔNG TY\nTNHH LUẬT VIỆT", doan=0),
            _doan("thay", 3, "CÔNG TY TNHH LUẬT VIỆT", doan=-1),
            {**_doan("thay", 3, "CÔNG TY TNHH LUẬT VIỆT"), "doan": "0"},
            # Cả đơn vị (không `doan`) trên đơn vị có chỗ trống: cùng phép nguồn.
            _doan("thay", 6, "Cơ quan/Đơn vị tiếp nhận: Công ty TNHH Luật Việt"),
            _doan("thay", 6, "Cơ quan tiếp nhận xin xác nhận"),
        ],
        cau=CAU_OWNER,
        tai_lieu=_tl(O_TIEU_DE, CO_QUAN),
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        {"loai": "thay", "don_vi": 3, "doan": 0, "noi_dung": "CÔNG TY TNHH LUẬT VIỆT"},
        {"loai": "thay", "don_vi": 3, "doan": 0, "noi_dung": "Ten co quan: CÔNG TY TNHH LUẬT VIỆT"},
        {"loai": "thay", "don_vi": 3, "doan": 2, "noi_dung": "Số 12/2026"},
        {"loai": "thay", "don_vi": 6, "noi_dung": "Cơ quan/Đơn vị tiếp nhận: Công ty TNHH Luật Việt"},
    ]
    assert [b["ly_do"] for b in k["bo_qua"]] == [
        "khong_nguon",
        "khong_co_doan",
        "sai_hinh_dang",
        "sai_hinh_dang",
        "sai_hinh_dang",
        "khong_nguon",
    ]
    assert k["cho_trong"][0] == {"don_vi": 3, "so": 0, "kieu": "cham", "nhan": "Số", "doan": 2}


def test_thay_theo_doan_tren_don_vi_khong_co_doan_chu_chi_nhan_doan_0():
    """Đơn vị một đoạn (không mang `doan_chu`): `doan` 0 là chính nó, chữ cũ là
    `noi_dung`; số khác thì không có đoạn đó."""
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "TÊN CHỦ QUẢN CỦA CƠ QUAN (nếu có)")]}]
    ra, _ = _chay(
        [_doan("thay", 7, "CÔNG TY MẪU THỬ", doan=0), _doan("thay", 7, "CÔNG TY MẪU THỬ", doan=1)],
        tai_lieu=tl,
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "thay", "don_vi": 7, "doan": 0, "noi_dung": "CÔNG TY MẪU THỬ"}]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["khong_co_doan"]


def test_moi_thay_qua_phep_nguon_cua_chu_them_du_doan_null():
    """`thay` cả đơn vị (`doan` null) trên đơn vị một đoạn ghi ĐÚNG những byte của
    `doan` 0, và một ô nhiều đoạn không chỗ trống cũng có thể là cụm giữ chỗ: chỉ
    một trường null không được quyết định tên bịa có lên biểu mẫu không. Mọi
    `thay` qua cùng phép nguồn của chữ nó thêm; bớt chữ thì không có gì để kiểm."""
    chu_quan = _dv(7, "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)")
    ghi_chu = DonViVanBan(
        chi_so=8,
        trang=1,
        offset_dau=0,
        noi_dung="Ghi chú",
        dia_chi=DiaChi("word/document.xml", (9,)),
        doan_chu=("", "Ghi chú", ""),
    )
    ra, _ = _chay(
        [
            _doan("thay", 7, "BỘ GIÁO DỤC VÀ ĐÀO TẠO"),
            _doan("thay", 7, "BỘ GIÁO DỤC VÀ ĐÀO TẠO", doan=0),
            _doan("thay", 8, "BỘ GIÁO DỤC VÀ ĐÀO TẠO"),
            _doan("thay", 7, "CÔNG TY MẪU THỬ"),
            _doan("thay", 7, "TÊN CHỦ QUẢN CỦA CƠ QUAN"),
        ],
        tai_lieu=[{**TL_KHUON[0], "don_vi": [*DV_M05, chu_quan, ghi_chu]}],
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        {"loai": "thay", "don_vi": 7, "noi_dung": "CÔNG TY MẪU THỬ"},
        {"loai": "thay", "don_vi": 7, "noi_dung": "TÊN CHỦ QUẢN CỦA CƠ QUAN"},
    ]
    assert [(b["don_vi"], b["ly_do"]) for b in k["bo_qua"]] == [(7, "khong_nguon")] * 2 + [(8, "khong_nguon")]


def test_xoa_va_chen_sau_khong_nhan_doan():
    """`doan` chỉ có nghĩa với `thay`. Một `xoa` mang `doan` 2 mà bị nới ra cả đơn vị
    là xoá cả ô tiêu đề thư — tên cơ quan kèm theo — khi người hỏi chỉ xin bỏ dòng
    "Số …/…"; `chen_sau` mang `doan` cũng vậy. Không đoán: bỏ."""
    ra, _ = _chay(
        [_doan("xoa", 3, doan=2), _doan("chen_sau", 3, "Công ty Mẫu Thử", doan=0), _doan("xoa", 3)],
        tai_lieu=_tl(O_TIEU_DE, CO_QUAN),
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "xoa", "don_vi": 3}]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["sai_hinh_dang", "sai_hinh_dang"]


def test_pdf_khong_nhan_thay_theo_doan():
    tl = [
        {
            **TL_KHUON[0],
            "dinh_dang": "pdf",
            "don_vi": [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="TÊN CƠ QUAN", hop=(10, 10, 200, 24))],
        }
    ]
    ra, _ = _chay([_doan("thay", 0, "CÔNG TY MẪU THỬ", doan=0), _doan("thay", 0, "CÔNG TY MẪU THỬ")], tai_lieu=tl)
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [{"loai": "thay", "don_vi": 0, "noi_dung": "CÔNG TY MẪU THỬ"}]
    assert [b["ly_do"] for b in k["bo_qua"]] == ["loai_khong_ho_tro"]


def test_dien_vao_nhan_so_hay_ngay_thang_nam_phai_co_chu_so():
    """Phép kiểm hợp lý tất định, HẸP: đúng lỗi owner thấy — tên công ty (có nguồn)
    rơi vào chỗ trống «Số» — bị bỏ `khong_khop_nhan`; nhãn ngày/tháng/năm cũng đòi
    chữ số. Nhãn khác không có luật nào."""
    ngay = _dv(
        8, "Thời gian: từ ngày … tháng … năm ……", [("cham", "Thời gian: từ ngày"), ("cham", "tháng"), ("cham", "năm")]
    )
    so_en = _dv(9, "No. ……", [("cham", "No.")])
    ra, _ = _chay(
        [
            _dien(3, 0, "Công ty TNHH Luật Việt"),
            _dien(3, 0, "12"),
            _dien(3, 1, "2026"),
            _dien(8, 0, "mười"),
            _dien(8, 1, "10"),
            _dien(8, 2, "năm nay"),
            _dien(9, 0, "Luật Việt"),
            _dien(6, 0, "Công ty TNHH Luật Việt"),
        ],
        cau=CAU_OWNER + " Ngày mười, năm nay.",
        tai_lieu=_tl(O_TIEU_DE, CO_QUAN, ngay, so_en),
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [_p(3, 0, "12"), _p(3, 1, "2026"), _p(8, 1, "10"), _p(6, 0, "Công ty TNHH Luật Việt")]
    assert [(b["don_vi"], b["cho_trong"], b["ly_do"]) for b in k["bo_qua"]] == [
        (3, 0, "khong_khop_nhan"),
        (8, 0, "khong_khop_nhan"),
        (8, 2, "khong_khop_nhan"),
        (9, 0, "khong_khop_nhan"),
    ]
    assert ra["traces"]["khuon_bo_khong_khop_nhan"] == 4


def test_thay_so_dieu_so_theo_cum_khong_theo_chuoi_con():
    """Số Điều so theo cụm: "Điều 5" không lọt vì đơn vị gốc có "Điều 50" ("Khoản 1" vì "Khoản 12")."""
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "Thực hiện theo Điều 50 và Khoản 12 của quy chế.")]}]
    ra, _ = _chay(
        [
            _doan("thay", 7, "Thực hiện theo Điều 5 và Khoản 12 của quy chế."),
            _doan("thay", 7, "Thực hiện theo Điều 50 và Khoản 1 của quy chế."),
            _doan("thay", 7, "Thực hiện theo điều  50 và Khoản 12 của quy chế hiện hành."),
        ],
        # Chữ `thay` thêm ("hành") phải là lời người hỏi — chữ in sẵn ở đơn vị khác
        # ("THỰC HÀNH") không còn là nguồn (luật owner 2026-09-27).
        cau="sửa thành: theo quy chế hiện hành",
        tai_lieu=tl,
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        {"loai": "thay", "don_vi": 7, "noi_dung": "Thực hiện theo điều  50 và Khoản 12 của quy chế hiện hành."}
    ], "cùng số Điều/Khoản, khác cách viết hoa hay khoảng trắng, vẫn là số đã có"
    assert [b["ly_do"] for b in k["bo_qua"]] == ["dieu_luat", "dieu_luat"]


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
    assert "chỗ trống: 0 «Điện thoại» = «0912345678» | 1 «Fax»" in llm.prompt
    assert ra["muc_dich_tai_lieu"] == "sua_ban_thao"
    assert ra["khuon_tong_quat"]["phep_sua"] == [
        {"loai": "dien", "don_vi": 2, "cho_trong": 1, "gia_tri": "0243999888"},
    ]


class _BanThaoGia:
    """`ban_thao` giả cho `dung_ban_thao_tong_quat` — ghi lại `ket` được lưu."""

    def __init__(self, cu: dict | None):
        self.cu, self.tao_ket, self.sua_ket = cu, None, None

    def moi_nhat(self, sub, pid, loai, *, viec_id):
        # Cùng luật `_SQL_MOI_NHAT`: chỉ bản thảo mà phiên bản đang sống trên `viec_id`.
        return self.cu if self.cu and self.cu.get("viec_id") == viec_id else None

    def tao(self, sub, pid, loai, facts, ket):
        self.tao_ket = ket
        return {
            "id": "bt-moi",
            "phien_ban": 1,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "facts": facts,
            # Cột migration 037 như dòng thật trả về (viec của chủ thì giữ).
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
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
            # Cột migration 037 như dòng thật trả về (viec của chủ thì giữ).
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
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


def _cu(phep_sua, **k) -> dict:
    """Dòng `ban_thao` đang sống trên khuôn A (đủ cột `_ket_state` đọc)."""
    return {
        "id": "bt-1",
        "viec_id": A_ID,
        "so_lan_sua": 1,
        "phien_ban": 3,
        "document": "# BM.M05\n",
        "clauses": [],
        "audit": {"muc_kiem": "tong_quat"},
        "facts": {},
        "phep_sua": phep_sua,
        "khuon": {"viec_id": A_ID, "dinh_dang": "docx", "so_trang": 2, "cho_trong": []},
        **k,
    }


def test_luot_sua_khong_doi_gi_thi_khong_len_phien_ban_ma_tra_ban_dang_co(bt_gia):
    g = bt_gia(_cu(DANG_MO["phep_sua"]))
    ra = d.dung_ban_thao_tong_quat(
        {"user_sub": "u", "hoi_thoai_id": "p", "muc_dich_tai_lieu": "sua_ban_thao", "khuon_tong_quat": _khuon([])}
    )
    assert g.sua_ket is None and g.tao_ket is None, "không phiên bản mới, không hạn mức"
    assert ra["ban_thao_tong_quat_loi"] is None
    bt = ra["ban_thao_ket"]
    assert (bt["id"], bt["phien_ban"], bt["phep_sua"], bt["doi_so_voi_truoc"]) == ("bt-1", 3, DANG_MO["phep_sua"], [])
    assert bt["khuon"]["viec_id"] == A_ID and ra["khuon_tong_quat"]["co_san"] is True


def test_luot_sua_moi_thay_doi_deu_bi_bo_thi_noi_loai_loi_khong_noi_gia_tri(bt_gia):
    """`KHONG_DOI_KHUON` chỉ còn cho lượt sửa đã XIN đổi mà mọi phép bị bỏ: nói loại
    lỗi (thiếu nguồn, không hợp nhãn…), không bao giờ nhắc giá trị."""
    g = bt_gia(_cu(DANG_MO["phep_sua"]))
    bo = [
        {"don_vi": 2, "cho_trong": 1, "ly_do": "khong_nguon"},
        {"don_vi": 3, "cho_trong": 0, "ly_do": "khong_khop_nhan"},
        {"don_vi": 3, "cho_trong": 0, "ly_do": "khong_nguon"},
        {"don_vi": 9, "cho_trong": None, "ly_do": "khong_co_doan"},
    ]
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": "u",
            "hoi_thoai_id": "p",
            "muc_dich_tai_lieu": "sua_ban_thao",
            "khuon_tong_quat": {**_khuon([]), "bo_qua": bo},
        }
    )
    assert g.sua_ket is None and ra["ban_thao_ket"] is None
    loi = ra["ban_thao_tong_quat_loi"]
    assert loi.startswith("Lượt này tôi chưa áp được thay đổi nào bạn xin (")
    assert loi.count("giá trị không có trong lời bạn nói") == 1 and "không hợp với nhãn" in loi
    assert "sai chỗ hoặc sai dạng" in loi and "bấm vào chỗ trống trên trang" in loi
    assert "0243999888" not in loi and "«" not in loi


def test_luot_sua_dien_vao_doan_da_thay_khong_bi_nuot_am_tham(bt_gia):
    """Dòng "Số …/…" đã bị `thay` ở phiên bản trước; lượt này mô hình `dien` 3.0/3.1 —
    `gop_phep_sua` gỡ chúng (đoạn đó không còn dãy chấm). Không được đáp "đã có
    sẵn" như thể người hỏi không xin gì: nói lý do. Có phép khác áp được thì phiên
    bản mới vẫn lên, và phép bị gỡ vào `bo_qua` (ghi chú của `assemble`)."""
    cho = h.cho_trong_khuon(_tl(O_TIEU_DE, CO_QUAN)[0])
    g = bt_gia(_cu([THAY_SO]))
    st = {"user_sub": "u", "hoi_thoai_id": "p", "muc_dich_tai_lieu": "sua_ban_thao"}
    ra = d.dung_ban_thao_tong_quat({**st, "khuon_tong_quat": _khuon([_p(3, 0, "13"), _p(3, 1, "2026")], cho)})
    assert g.sua_ket is None and ra["ban_thao_ket"] is None
    loi = ra["ban_thao_tong_quat_loi"]
    assert loi.startswith("Lượt này tôi chưa áp được thay đổi nào bạn xin (") and "viết lại" in loi
    assert "13" not in loi and "«" not in loi
    ra = d.dung_ban_thao_tong_quat(
        {**st, "khuon_tong_quat": _khuon([_p(3, 0, "13"), _p(6, 0, "Công ty Mẫu Thử")], cho)}
    )
    assert g.sua_ket["phep_sua"] == [THAY_SO, _p(6, 0, "Công ty Mẫu Thử")]
    assert ra["khuon_tong_quat"]["bo_qua"] == [{"don_vi": 3, "cho_trong": 0, "ly_do": "da_viet_lai"}]
    assert ra["ban_thao_ket"]["phien_ban"] == 2


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


@pytest.mark.parametrize("phep", [[], [_p(1, 0, "")]], ids=["khong_phep", "chi_go_o"])
def test_luot_tao_khong_phep_nao_van_dung_phien_ban_1_la_chinh_tep_tai_len(bt_gia, monkeypatch, phep):
    """Quyết định owner 2026-09-27: lượt soạn trên khuôn gốc LUÔN dựng phiên bản 1,
    kể cả khi chưa có giá trị nào — phép rỗng, bản thảo là chính tệp tải lên. Cùng
    hạn mức dựng lần đầu và cùng hàng traces `EP_SOAN_THAO` như mọi lượt dựng."""
    g = bt_gia(None)
    goi = []
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **k: goi.append(("han_muc", a[2])))
    monkeypatch.setattr(d, "_ghi_traces", lambda *a, **k: goi.append(("traces", a[1])))
    ra = d.dung_ban_thao_tong_quat(
        {"user_sub": "u", "hoi_thoai_id": "p", "muc_dich_tai_lieu": "tao_van_ban", "khuon_tong_quat": _khuon(phep)}
    )
    assert (g.tao_ket["viec_id"], g.tao_ket["phep_sua"], g.tao_ket["document"]) == (A_ID, [], "# BM.M05\n")
    assert ra["ban_thao_tong_quat_loi"] is None
    assert (ra["ban_thao_ket"]["phien_ban"], ra["ban_thao_ket"]["phep_sua"]) == (1, [])
    assert goi == [("han_muc", bao_ve.EP_SOAN_THAO), ("traces", bao_ve.EP_SOAN_THAO)]


def test_cau_cua_owner_soan_thao_van_ban_nay_dung_lai_dung_tep_tai_len(bt_gia):
    """Đúng câu owner gõ trên một biểu mẫu vừa tải lên (`tao_lai`): mô hình còn đề
    xuất phép — kể cả một giá trị chép từ chính tài liệu — nhưng lượt `tao_lai` bỏ hết,
    tất định: phiên bản 1 phép rỗng, lời đáp nói bản thảo là tệp tải lên."""
    g = bt_gia(None)
    ra, _ = _chay(
        [_dien(1, 0, "Giấy tiếp nhận"), _doan("thay", 5, "Đồng ý tiếp nhận.")],
        cau="soạn thảo văn bản này cho tôi",
        yeu_cau="tao_lai",
        khong_dat=["văn bản này"],
        user_sub="u",
        hoi_thoai_id="p",
    )
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    k = ra["khuon_tong_quat"]
    assert (k["yeu_cau"], k["phep_sua"], k["bo_qua"], k["khong_dat"]) == ("tao_lai", [], [], [])
    tr = ra["traces"]
    assert (tr["khuon_tao_lai"], tr["khuon_so_phep_bo_tao_lai"], tr["khuon_so_phep_giu"]) == (1, 2, 0)
    assert (tr["khuon_so_phep_bo"], tr["khuon_yeu_cau_khac"]) == (0, 0)
    ra = d.dung_ban_thao_tong_quat(ra)
    assert (g.tao_ket["viec_id"], g.tao_ket["phep_sua"]) == (A_ID, [])
    bt = ra["ban_thao_ket"]
    assert (bt["phien_ban"], bt["viec_id"], bt["phep_sua"]) == (1, A_ID, [])
    out = assemble(ra, {}, _No(), "m")
    assert out["result_type"] is ResultType.ban_thao and out["ban_thao"]["id"] == "bt-moi"
    assert out["answer"].startswith(
        "Tôi đã dựng lại văn bản đúng như tệp bạn tải lên (2 trang): mở bản thảo để xem, tải Word hoặc PDF ngay."
    )
    assert out["coverage_note"] is None, "phép bị bỏ vì `tao_lai` không phải phép bị từ chối"
    assert "Còn trống: «Cơ quan/Đơn vị tiếp nhận», «Điện thoại», «Fax», «Ngành» và 1 chỗ khác." in out["answer"]
    assert "Muốn điền, hãy nói giá trị cần điền hoặc bấm vào chỗ trống trên trang." in out["answer"]
    assert "bản gốc" not in out["answer"] and "tài liệu gốc" not in out["answer"]


@pytest.mark.parametrize("phep_cu", [[], DANG_MO["phep_sua"]], ids=["v1_rong_tu_khung_dien", "da_dien"])
def test_cau_cua_owner_khi_da_co_ban_thao_khong_doi_gia_tri(bt_gia, monkeypatch, phep_cu):
    """Cùng câu owner khi hội thoại ĐÃ có bản thảo trên khuôn này (bấm "Điền biểu
    mẫu" tạo phiên bản 1 rỗng, hoặc nói câu đó lần hai): lượt sửa không đổi gì nên
    không lên phiên bản, không tính hạn mức — nhưng lời đáp nói bản thảo đã có sẵn
    để mở/tải, KHÔNG đòi giá trị điền (đúng loại lời owner đã bác 2026-09-27)."""
    g = bt_gia(_cu(phep_cu, so_lan_sua=0))
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **k: pytest.fail("lượt sửa không kiểm hạn mức dựng"))
    monkeypatch.setattr(d, "_ghi_traces", lambda *a, **k: pytest.fail("không phiên bản mới thì không đếm hạn mức"))
    ra, _ = _chay(
        [_dien(2, 1, "0243999888")],
        cau="soạn thảo văn bản này cho tôi",
        yeu_cau="tao_lai",
        user_sub="u",
        hoi_thoai_id="p",
    )
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.tao_ket is None and g.sua_ket is None
    assert ra["ban_thao_ket"]["id"] == "bt-1" and ra["ban_thao_tong_quat_loi"] is None
    out = assemble(ra, {}, _No(), "m")
    assert out["result_type"] is ResultType.ban_thao and out["ban_thao"]["id"] == "bt-1", "chat hiện thẻ bản đang có"
    assert out["answer"] == (
        "Bản thảo trên tệp bạn tải lên đã có sẵn (phiên bản 3): mở bản thảo để xem, tải Word hoặc PDF. "
        "Muốn điền, hãy nói giá trị cần điền hoặc bấm vào chỗ trống trên trang."
    )
    assert "phải có trong lời bạn" not in out["answer"] and "Bạn nói rõ giá trị" not in out["answer"]
    assert "bản gốc" not in out["answer"] and "tài liệu gốc" not in out["answer"]


@pytest.mark.parametrize("yeu_cau", [None, "khong_ro", "van_ban_nay"], ids=["thieu", "la", "gia_tri_cu"])
def test_yeu_cau_thieu_hoac_la_thi_coi_la_dien_sua_va_dung(bt_gia, yeu_cau):
    """Mặc định: `dien_sua` — vẫn an toàn vì chỉ giá trị người hỏi nói mới qua phép
    nguồn. Lượt tạo vẫn dựng (owner: dựng); chỉ `van_ban_khac` rõ ràng mới không dựng."""
    g = bt_gia(None)
    ra, _ = _chay([], yeu_cau=yeu_cau, user_sub="u", hoi_thoai_id="p")
    assert ra["khuon_tong_quat"]["yeu_cau"] == "dien_sua"
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.tao_ket["phep_sua"] == [] and ra["ban_thao_ket"]["phien_ban"] == 1


def test_luot_tao_co_phep_hop_le_van_dien_nhu_cu(bt_gia):
    g = bt_gia(None)
    ra, _ = _chay([_dien(1, 0, "Công ty Mẫu Thử")], user_sub="u", hoi_thoai_id="p")
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.tao_ket["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử")]
    out = assemble(ra, {}, _No(), "m")
    assert out["answer"].startswith("Bản thảo phiên bản 1 là chính biểu mẫu bạn tải lên: đã điền 1/5 chỗ trống")
    assert "dựng lại" not in out["answer"]


@pytest.mark.parametrize("cu", [None, "cung_khuon"], ids=["chua_co_ban_thao", "da_co_ban_thao"])
def test_xin_van_ban_khac_tu_tai_lieu_khuon_goc_chi_duong_checklist(bt_gia, monkeypatch, cu):
    """Lời xin "dựa vào hợp đồng này soạn đơn xin nghỉ việc" (`yeu_cau` =
    `van_ban_khac`): văn bản khác là ngoại lệ có tên của quyết định 2026-09-26 mục 3,
    nên KHÔNG dựng, không sửa bản đang có, không đếm hạn mức — chỉ sang đường
    checklist, và không đòi giá trị điền nào."""
    from src.agents.nodes.route import Intent

    g = bt_gia({"id": "bt-1", "viec_id": A_ID, "so_lan_sua": 0, "clauses": [], "phep_sua": []} if cu else None)
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **k: pytest.fail("không dựng thì không kiểm hạn mức"))
    monkeypatch.setattr(d, "_ghi_traces", lambda *a, **k: pytest.fail("không dựng thì không đếm hạn mức"))
    ra, llm = _chay(
        [_dien(1, 0, "Công ty Mẫu Thử")],
        cau="dựa vào hợp đồng này soạn giúp tôi đơn xin nghỉ việc, cơ quan là Công ty Mẫu Thử",
        muc_dich="hoi",
        yeu_cau="van_ban_khac",
        intent=Intent.soan_thao,
        user_sub="u",
        hoi_thoai_id="p",
    )
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban" and ra["khuon_tong_quat"]["yeu_cau"] == "van_ban_khac"
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.tao_ket is None and g.sua_ket is None and ra["ban_thao_ket"] is None
    assert ra["ban_thao_tong_quat_loi"] == d.KHONG_DIEN_KHUON
    out = assemble(ra, {}, _No(), "m")
    assert out["result_type"] is ResultType.soan_thao_hoi and out.get("ban_thao") is None
    assert "chọn loại văn bản" in out["answer"] and "văn bản khác" in out["answer"]
    assert "giá trị" not in out["answer"] and "đã điền" not in out["answer"]


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


@pytest.mark.parametrize("dinh_dang,tai", [("docx", "tải Word hoặc PDF ngay"), ("pdf", "tải PDF ngay")])
def test_assemble_ban_thao_khuon_chua_dien_gi_noi_la_tep_tai_len_co_tran(dinh_dang, tai):
    """Phiên bản 1 phép rỗng: lời đáp nói bản thảo là tệp tải lên (PDF không có bản
    Word), vẫn liệt kê chỗ còn trống trong trần 900 ký tự / 4 tên."""
    st = {
        "query": "soạn thảo văn bản này cho tôi",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 1, "viec_id": A_ID, "phep_sua": [], "clauses": []},
        "khuon_tong_quat": {**_khuon([], _cho(30)), "dinh_dang": dinh_dang, "so_trang": 3},
    }
    ra = assemble(st, {}, _No(), "m")
    assert ra["result_type"] is ResultType.ban_thao
    assert ra["answer"].startswith(
        f"Tôi đã dựng lại văn bản đúng như tệp bạn tải lên (3 trang): mở bản thảo để xem, {tai}. Còn trống: «Nhãn số 0 "
    )
    assert "và 26 chỗ khác" in ra["answer"] and ra["answer"].count("«") == 4
    assert len(ra["answer"]) <= TRAN_KY_TU and "đã điền" not in ra["answer"]
    assert ("Word" in ra["answer"]) is (dinh_dang == "docx")


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


def test_assemble_khong_dem_cho_trong_cua_doan_da_xoa():
    """Tích hợp wave D: đoạn đã `xoa`/`thay` không còn dãy chấm — cùng luật
    `ban_thao.cho_trong_khuon` (bảng ô điền): không đếm, không kể là còn trống."""
    cho = _cho(3)
    phep = [_p(0, 0, "A"), {"loai": "xoa", "don_vi": 2}]
    st = {
        "query": "q",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 1, "viec_id": A_ID, "phep_sua": phep, "clauses": []},
        "khuon_tong_quat": _khuon(phep, cho),
    }
    ra = assemble(st, {}, _No(), "m")
    assert "đã điền 1/2 chỗ trống và sửa 1 đoạn" in ra["answer"]
    assert "«Nhãn số 1 " in ra["answer"] and "«Nhãn số 2 " not in ra["answer"]


def test_assemble_thay_THEO_DOAN_chi_bo_cho_trong_cua_doan_do():
    cho = [
        {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Tên", "doan": 0},
        {"don_vi": 0, "so": 1, "kieu": "cham", "nhan": "Số", "doan": 2},
        {"don_vi": 1, "so": 0, "kieu": "cham", "nhan": "Cơ quan", "doan": 0},
    ]
    phep = [{"loai": "thay", "don_vi": 0, "doan": 2, "noi_dung": "Số 12"}, _p(1, 0, "A")]
    st = {
        "query": "q",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 1, "viec_id": A_ID, "phep_sua": phep, "clauses": []},
        "khuon_tong_quat": _khuon(phep, cho),
    }
    ra = assemble(st, {}, _No(), "m")
    assert "đã điền 1/2 chỗ trống và sửa 1 đoạn" in ra["answer"] and "Còn trống: «Tên»." in ra["answer"]
    assert "bấm vào chỗ trống trên trang" in ra["answer"] and "bên cạnh" not in ra["answer"]


def test_assemble_ban_co_san_tren_khuon_PDF_khong_moi_tai_Word():
    st = {
        "query": "soạn thảo văn bản này cho tôi",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 2, "viec_id": A_ID, "phep_sua": [], "clauses": []},
        "khuon_tong_quat": {**_khuon([]), "dinh_dang": "pdf", "co_san": True},
    }
    ra = assemble(st, {}, _No(), "m")
    assert ra["result_type"] is ResultType.ban_thao
    assert ra["answer"].startswith(
        "Bản thảo trên tệp bạn tải lên đã có sẵn (phiên bản 2): mở bản thảo để xem, tải PDF."
    )


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
    """Một việc đọc THẬT có khuôn gốc: `viec_id` phải còn trên dòng đã lưu (P4a
    ghi nó qua truy vấn con kiểm chủ, id lạ ra NULL), không chỉ trong state."""
    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    sub, ht = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    vid = _viec(sub, ht)
    tl.luu_khuon_goc(get_engine(), vid, "docx", b"PK\x03\x04", [[595.0, 842.0], [595.0, 842.0]])
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": sub,
            "hoi_thoai_id": ht,
            "muc_dich_tai_lieu": "tao_van_ban",
            "khuon_tong_quat": {**_khuon([_p(1, 0, "Công ty Mẫu Thử")]), "viec_id": vid},
        }
    )
    bt = ra["ban_thao_ket"]
    assert bt["phien_ban"] == 1 and bt["loai"] == "tong_quat" and bt["clauses"] == []
    assert bt["document"] == "# BM.M05\n\n- Cơ quan/Đơn vị tiếp nhận: Công ty Mẫu Thử\n"
    assert bt["viec_id"] == vid and bt["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử")]
    assert (bt["khuon"]["viec_id"], bt["khuon"]["so_trang"]) == (vid, 2)
    luu = ban_thao.chi_tiet(sub, bt["id"])
    assert (luu["viec_id"], luu["phep_sua"]) == (vid, [_p(1, 0, "Công ty Mẫu Thử")])
    assert luu["khuon"] == bt["khuon"]


@pytest.mark.integration
def test_viec_khong_ton_tai_thi_state_noi_dung_dong_da_luu(phien):
    """`ban_thao_ket` là dòng ĐÃ LƯU: một `viec_id` không có hàng (hay của người
    khác) ra NULL trên dòng, nên state không được mang id đó sang `BanThaoOut`."""
    sub, ht = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    ra = d.dung_ban_thao_tong_quat(
        {
            "user_sub": sub,
            "hoi_thoai_id": ht,
            "muc_dich_tai_lieu": "tao_van_ban",
            "khuon_tong_quat": _khuon([_p(1, 0, "Công ty Mẫu Thử")]),
        }
    )
    bt = ra["ban_thao_ket"]
    assert (bt["viec_id"], bt["khuon"]) == (None, None)
    assert ban_thao.chi_tiet(sub, bt["id"])["viec_id"] is None


_VAN_BAN = {
    "tieu_de": "ĐƠN XIN NGHỈ PHÉP",
    "muc": [{"ten": "Lý do", "vung": "than", "khoi": [{"noi_dung": "Việc gia đình.", "bang": []}]}],
}


@pytest.mark.integration
def test_hoi_thoai_xen_ke_ban_thao_khuon_va_HTML_moi_luot_sua_dung_ban_cua_no(phien):
    """Sửa hay dựng mới theo `viec_id` của phiên bản ĐANG sống, không theo bản mới
    nhất của hội thoại: một lượt sửa khuôn gốc không mở bản thứ hai chỉ vì bản
    HTML vừa được dựng, và một lượt sửa HTML không ghi đè bản khuôn gốc (P4a lưu
    `viec_id` của `ket`, nên ghi nhầm là biến bản khuôn thành bản HTML)."""
    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    sub, ht = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    vid = _viec(sub, ht)
    tl.luu_khuon_goc(get_engine(), vid, "docx", b"PK\x03\x04", [[595.0, 842.0]])
    goc = {"user_sub": sub, "hoi_thoai_id": ht}

    def _luot(muc_dich, **st):
        return d.dung_ban_thao_tong_quat({**goc, "muc_dich_tai_lieu": muc_dich, **st})["ban_thao_ket"]

    k1 = _luot("tao_van_ban", khuon_tong_quat={**_khuon([_p(1, 0, "Công ty Mẫu Thử")]), "viec_id": vid})
    h1 = _luot("tao_van_ban", van_ban_tong_quat=_VAN_BAN)
    assert h1["id"] != k1["id"] and h1["viec_id"] is None

    k2 = _luot("sua_ban_thao", khuon_tong_quat={**_khuon([_p(2, 0, "0912345678")]), "viec_id": vid})
    assert (k2["id"], k2["phien_ban"]) == (k1["id"], 2), "bản HTML mới hơn không che bản khuôn gốc"
    assert k2["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử"), _p(2, 0, "0912345678")]

    moi = {**_VAN_BAN, "muc": [{**_VAN_BAN["muc"][0], "khoi": [{"noi_dung": "Việc riêng.", "bang": []}]}]}
    h2 = _luot("sua_ban_thao", van_ban_tong_quat=moi)
    assert (h2["id"], h2["phien_ban"], h2["viec_id"]) == (h1["id"], 2, None), (
        "bản khuôn mới hơn không hút lượt sửa HTML"
    )
    k = ban_thao.chi_tiet(sub, k1["id"])
    assert (k["phien_ban"], k["viec_id"], k["phep_sua"]) == (2, vid, k2["phep_sua"])


@pytest.mark.integration
def test_dong_nhe_cho_prompt_luot_sua_thay_gia_tri_dang_dien_sau_khi_gop(phien):
    """Dòng NHẸ (`ban_thao_tong_quat_dang_mo_nhe`, đọc mỗi lượt hỏi) mang `viec_id`
    + `phep_sua` của phiên bản đang sống, nên prompt lượt sửa kế tiếp thấy giá trị
    đã gộp từ HAI lượt: `= «giá trị»` dưới đúng chỗ trống."""
    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    sub, ht = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    vid = _viec(sub, ht)
    tl.luu_khuon_goc(get_engine(), vid, "docx", b"PK\x03\x04", [[595.0, 842.0]])
    goc = {"user_sub": sub, "hoi_thoai_id": ht}
    d.dung_ban_thao_tong_quat(
        {
            **goc,
            "muc_dich_tai_lieu": "tao_van_ban",
            "khuon_tong_quat": {**_khuon([_p(1, 0, "Công ty Mẫu Thử")]), "viec_id": vid},
        }
    )
    d.dung_ban_thao_tong_quat(
        {
            **goc,
            "muc_dich_tai_lieu": "sua_ban_thao",
            "khuon_tong_quat": {**_khuon([_p(2, 0, "0912345678")]), "viec_id": vid},
        }
    )

    nhe = ban_thao.ban_thao_tong_quat_dang_mo_nhe(sub, ht)
    assert nhe["viec_id"] == vid
    _, llm = _chay(
        [_dien(2, 1, "0243999888")],
        cau="đổi fax thành 0243999888",
        muc_dich="sua_ban_thao",
        tai_lieu=[{**TL_KHUON[0], "id": vid, "viec_id": vid}],
        ban_thao_tong_quat_dang_mo=nhe,
    )
    assert "chỗ trống: 0 «Cơ quan/Đơn vị tiếp nhận» = «Công ty Mẫu Thử»" in llm.prompt
    assert "chỗ trống: 0 «Điện thoại» = «0912345678» | 1 «Fax»" in llm.prompt


@pytest.mark.integration
def test_hoi_thoai_xen_ke_nen_prompt_la_ban_thao_cung_loai_nguon_voi_luot(phien):
    """Nền "# Bản thảo đang có" theo `viec_id` của LƯỢT (khuôn gốc của tài liệu
    đang đọc, `None` cho lượt HTML) — cùng luật với đích lưu — không theo bản
    mới nhất của hội thoại mà `_chuan_bi_phien` đọc (review wave D): lượt HTML
    dựng lại bản HTML từ tóm tắt biểu mẫu, và một hội thoại chỉ có bản khuôn
    thấy "nền để sửa" rồi nhận `KHONG_CO_BAN_THAO`."""
    from src.agents import graph_tra_cuu as g
    from src.services import tai_lieu as tl
    from src.services.db import get_engine

    sub, ht = phien
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    vid, vid_html = _viec(sub, ht), _viec(sub, ht)
    tl.luu_khuon_goc(get_engine(), vid, "docx", b"PK\x03\x04", [[595.0, 842.0]])
    goc = {"user_sub": sub, "hoi_thoai_id": ht}

    def _luot(muc_dich, **st):
        d.dung_ban_thao_tong_quat({**goc, "muc_dich_tai_lieu": muc_dich, **st})

    def _prompt(viec: str) -> str:
        # Đúng thứ tự `n_hieu_tai_lieu`: dòng nhẹ của `_chuan_bi_phien`, nạp tài liệu, chọn nền.
        nhe = ban_thao.ban_thao_tong_quat_dang_mo_nhe(sub, ht)
        st = {**goc, "query": "sửa giúp tôi", "ban_thao_tong_quat_dang_mo": nhe}
        tai_lieu = g._nap_tai_lieu(get_engine(), [viec], {viec: "BM.M05.docx"}, sub)
        llm = _LLM(_ra([], muc_dich="sua_ban_thao"))
        h.hieu_tai_lieu(g._nap_ban_thao_dang_mo(st, tai_lieu), tai_lieu, llm, "m")
        return llm.prompt

    _luot("tao_van_ban", khuon_tong_quat={**_khuon([_p(1, 0, "Công ty Mẫu Thử")]), "viec_id": vid})
    assert "# Bản thảo đang có" not in _prompt(vid_html), "chỉ có bản khuôn: lượt HTML không có nền nào"

    _luot("tao_van_ban", van_ban_tong_quat=_VAN_BAN)
    p = _prompt(vid)
    assert "chỗ trống: 0 «Cơ quan/Đơn vị tiếp nhận» = «Công ty Mẫu Thử»" in p, "bản HTML mới hơn không che giá trị"
    assert "Việc gia đình." not in p

    _luot("sua_ban_thao", khuon_tong_quat={**_khuon([_p(2, 0, "0912345678")]), "viec_id": vid})
    p = _prompt(vid_html)
    assert "# Bản thảo đang có" in p and "Việc gia đình." in p, "bản khuôn mới hơn không thay nền HTML"
    assert "Công ty Mẫu Thử" not in p and "# BM.M05" not in p


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
    assert f"[A-{dt.chi_so}] (tr. 1) Điện thoại: ⟦0⟧ Fax: ⟦1⟧\n" in llm.prompt, "chỗ trống đứng tại chỗ trong câu"
    # Bộ đọc lưu nhãn SẠCH (`doc_tai_lieu.nhan_sach`): không còn dấu `:` cuối.
    assert [c["nhan"] for c in ra["khuon_tong_quat"]["cho_trong"] if c["don_vi"] == dt.chi_so] == ["Điện thoại", "Fax"]
    phep = ban_thao.gop_phep_sua([], ra["khuon_tong_quat"]["phep_sua"])
    assert len(phep) == 2
    hang = json.loads(json.dumps([_hang_don_vi(x) for x in don_vi], ensure_ascii=False))
    moi, bc = ap_dung_docx(goc, hang, phep)
    assert bc == {"da_ap": [0, 1], "bo_qua": []}
    moi_dv = doc(BM_M05.name, moi).don_vi
    assert moi_dv[dt.chi_so].noi_dung.startswith("Điện thoại: 0912345678")
    assert "Fax: ……" in moi_dv[dt.chi_so].noi_dung, "chỗ không có nguồn giữ nguyên dãy chấm"
    assert moi_dv[nganh.chi_so].noi_dung.startswith("Ngành: Luật kinh tế")


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_thay_khong_dien_duoc_gia_tri_bia_vao_cho_trong():
    """Đúng phép thử của reviewer trên tệp thật: `dien` bịa bị bỏ, `thay` cùng giá trị
    trên chính đơn vị ấy cũng bị bỏ (phép nguồn của chữ nó thêm) — không còn phép
    nào tới bộ áp."""
    from src.services.doc_tai_lieu import doc

    don_vi = doc(BM_M05.name, BM_M05.read_bytes()).don_vi
    cq = next(x for x in don_vi if x.noi_dung.startswith("Cơ quan/Đơn vị tiếp nhận:"))
    ra, _ = _chay(
        [
            _dien(cq.chi_so, 0, "Công ty Bịa Đặt"),
            _doan("thay", cq.chi_so, "Cơ quan/Đơn vị tiếp nhận: Công ty Bịa Đặt"),
        ],
        cau="điền giúp tôi",
        tai_lieu=[{**TL_KHUON[0], "ten_tep": BM_M05.name, "don_vi": don_vi}],
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == []
    assert [b["ly_do"] for b in k["bo_qua"]] == ["khong_nguon", "khong_nguon"]


def _m05() -> tuple[bytes, list, list[dict]]:
    """BM.M05 thật: bytes, đơn vị (như `don_vi_cua` trả) và hàng đã lưu (jsonb)."""
    from src.services.doc_tai_lieu import doc
    from src.services.tai_lieu import _hang_don_vi

    goc = BM_M05.read_bytes()
    don_vi = doc(BM_M05.name, goc).don_vi
    hang = json.loads(json.dumps([_hang_don_vi(x) for x in don_vi], ensure_ascii=False))
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
    return goc, hang, tl


def _ngay_m05(dv: int) -> list[dict]:
    return [_dien(dv, i, v) for i, v in enumerate(("01", "10", "2026", "31", "12", "2026"))]


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_cau_owner_theo_hop_dong_moi_giu_tron_tu_prompt_toi_tep_da_dien(bt_gia):
    """Đúng câu owner gõ trên BM.M05 (2026-09-27). Mô hình GIẢ theo hợp đồng prompt
    mới — tên cơ quan `thay` đoạn 0 của ô tiêu đề thư, số tách vào `Số ⟦0⟧/⟦1⟧`, tên
    cơ quan vào chỗ trống sau "Cơ quan/Đơn vị tiếp nhận:" — thì mọi phép qua phép
    kiểm, được lưu, được kể trong lời đáp, và áp lên chính tệp ra đúng chữ."""
    goc, hang, tl = _m05()
    g = bt_gia(None)
    ra, llm = _chay(
        [
            _doan("thay", 3, "CÔNG TY TNHH LUẬT VIỆT", doan=0),
            _dien(3, 0, "12"),
            _dien(3, 1, "2026"),
            _dien(6, 0, "Công ty TNHH Luật Việt"),
            *_ngay_m05(13),
        ],
        cau=CAU_OWNER,
        tai_lieu=tl,
        user_sub="u",
        hoi_thoai_id="p",
    )
    assert "[A-3] (tr. 1, bảng 1 hàng 2 cột 1) ¶0 TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN ¶2 Số ⟦0⟧/⟦1⟧\n" in llm.prompt
    assert "[A-6] (tr. 1) Cơ quan/Đơn vị tiếp nhận: ⟦0⟧\n" in llm.prompt
    k = ra["khuon_tong_quat"]
    assert k["bo_qua"] == [] and len(k["phep_sua"]) == 10
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.tao_ket["phep_sua"] == k["phep_sua"]
    out = assemble(ra, {}, _No(), "m")
    assert out["answer"].startswith("Bản thảo phiên bản 1 là chính biểu mẫu bạn tải lên: đã điền 9/")
    assert "và sửa 1 đoạn" in out["answer"] and out["coverage_note"] is None

    from src.services.doc_tai_lieu import doc

    moi, bc = ban_thao.ap_phep_sua("docx", goc, hang, g.tao_ket["phep_sua"])
    assert bc["bo_qua"] == []
    dv = doc(BM_M05.name, moi).don_vi
    assert dv[3].noi_dung == "CÔNG TY TNHH LUẬT VIỆT Số 12/2026"
    assert dv[6].noi_dung == "Cơ quan/Đơn vị tiếp nhận: Công ty TNHH Luật Việt"
    assert dv[13].noi_dung == "Thời gian: từ ngày 01 tháng 10 năm 2026 đến ngày 31 tháng 12 năm 2026"


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_dau_ra_sai_owner_thay_ten_co_quan_vao_so_bi_bo_khong_khop_nhan(bt_gia):
    """Đầu ra SAI owner quan sát: tên cơ quan (có nguồn!) vào chỗ trống «Số», "12/2026"
    vào «/», chỗ "Cơ quan/Đơn vị tiếp nhận:" bỏ trống. Phép nguồn không bắt được một
    giá trị thật đặt sai chỗ; phép kiểm nhãn hẹp bắt được đúng phép đầu. Lời đáp gọi
    tên chỗ không áp và vẫn kể chỗ cơ quan còn trống."""
    goc, hang, tl = _m05()
    g = bt_gia(None)
    ra, _ = _chay(
        [_dien(3, 0, "Công ty TNHH Luật Việt"), _dien(3, 1, "12/2026"), *_ngay_m05(13)],
        cau=CAU_OWNER,
        tai_lieu=tl,
        user_sub="u",
        hoi_thoai_id="p",
    )
    k = ra["khuon_tong_quat"]
    assert k["bo_qua"] == [{"don_vi": 3, "cho_trong": 0, "ly_do": "khong_khop_nhan"}]
    assert ra["traces"]["khuon_bo_khong_khop_nhan"] == 1
    ra = d.dung_ban_thao_tong_quat(ra)
    out = assemble(ra, {}, _No(), "m")
    assert out["coverage_note"].startswith("Không áp 1 thay đổi") and "«Số»" in out["coverage_note"]
    assert "«Cơ quan/Đơn vị tiếp nhận»" in out["answer"], "chỗ cơ quan vẫn được kể là còn trống"

    from src.services.doc_tai_lieu import doc

    moi, _ = ban_thao.ap_phep_sua("docx", goc, hang, g.tao_ket["phep_sua"])
    dv = doc(BM_M05.name, moi).don_vi
    assert "Luật Việt" not in dv[3].noi_dung and dv[3].noi_dung.startswith("TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số ….")


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_thay_cum_giu_cho_bang_ten_bia_bi_bo():
    """Cả phép thử của reviewer: đơn vị 1 ("TÊN CHỦ QUẢN…", MỘT `w:p`, không chỗ
    trống) — `doan` null hay 0 ghi cùng byte, nên cùng bị bỏ."""
    _, _, tl = _m05()
    bia = "BỘ GIÁO DỤC VÀ ĐÀO TẠO"
    ra, _ = _chay(
        [_doan("thay", 3, "CÔNG TY TNHH BỊA ĐẶT", doan=0), _doan("thay", 1, bia), _doan("thay", 1, bia, doan=0)],
        cau=CAU_OWNER,
        tai_lieu=tl,
    )
    assert ra["khuon_tong_quat"]["phep_sua"] == []
    assert [b["ly_do"] for b in ra["khuon_tong_quat"]["bo_qua"]] == ["khong_nguon"] * 3


def test_traces_dem_luot_yeu_cau_van_ban_khac_va_so_phep_bi_bo_theo():
    """Đếm, không chép: mô hình gọi lượt là `van_ban_khac` thì mọi phép đã qua phép
    kiểm cũng không dựng — hai con số để thấy phân loại sai ngoài đời thật."""
    ra, _ = _chay([_dien(1, 0, "Công ty Mẫu Thử"), _dien(2, 1, "0243999888")], yeu_cau="van_ban_khac")
    tr = ra["traces"]
    assert (tr["khuon_yeu_cau_khac"], tr["khuon_so_phep_bo_yeu_cau_khac"]) == (1, 1)
    ra, _ = _chay([_dien(1, 0, "Công ty Mẫu Thử")])
    assert (ra["traces"]["khuon_yeu_cau_khac"], ra["traces"]["khuon_so_phep_bo_yeu_cau_khac"]) == (0, 0)
    assert "Công ty" not in json.dumps(ra["traces"], ensure_ascii=False)


# ─────────── luật owner 2026-09-27: "nếu người dùng yêu cầu sửa thì hãy sửa, còn nếu
# bảo soạn thảo văn bản ra thì phải đúng 100%" (fix/g4-backend B1–B4)


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
@pytest.mark.parametrize("yeu_cau", ["tao_lai", "dien_sua"])
def test_bm_m05_that_ten_truong_in_san_khong_bao_gio_len_cho_trong(bt_gia, yeu_cau):
    """Lỗi owner thấy 2026-09-27: "soạn thảo văn bản này cho tôi", mô hình điền «Trường
    Đại học Phenikaa» — chữ IN SẴN của đơn vị 9 — vào chỗ «Khoa» của chính câu đó.
    `tao_lai` bỏ mọi phép; và kể cả khi lượt bị gọi là `dien_sua`, chữ của tài liệu
    không phải nguồn cho một giá trị mới (`khong_nguon`). Tải về đúng từng byte."""
    goc, hang, tl = _m05()
    assert "Trường Đại học Phenikaa, thuộc Khoa" in tl[0]["don_vi"][9].noi_dung
    g = bt_gia(None)
    ra, _ = _chay(
        [_dien(9, 0, "Trường Đại học Phenikaa")],
        cau="soạn thảo văn bản này cho tôi",
        yeu_cau=yeu_cau,
        tai_lieu=tl,
        user_sub="u",
        hoi_thoai_id="p",
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == []
    assert k["bo_qua"] == ([] if yeu_cau == "tao_lai" else [{"don_vi": 9, "cho_trong": 0, "ly_do": "khong_nguon"}])
    ra = d.dung_ban_thao_tong_quat(ra)
    assert (g.tao_ket["phep_sua"], ra["ban_thao_ket"]["phien_ban"]) == ([], 1)
    moi, _ = ban_thao.ap_phep_sua("docx", goc, hang, g.tao_ket["phep_sua"])
    assert moi == goc, "bản thảo `tao_lai` là CHÍNH tệp tải lên, từng byte"


def test_chu_cua_tai_lieu_quan_sat_va_ban_thao_dang_mo_khong_la_nguon_gia_tri_moi():
    """Nguồn của giá trị MỚI chỉ còn lời người hỏi (câu gõ, câu đầy đủ), hồ sơ và ký ức
    lượt này hỏi tới. Chữ của đơn vị khác, đoạn trích `quan_sat` và `document` của bản
    đang mở thì không. Một phép y hệt phép phiên bản đang có không phải giá trị mới:
    bỏ qua lặng lẽ (phép gộp giữ nó), không kể là phép bị bỏ."""
    tl = [{**TL_KHUON[0], "don_vi": [*DV_M05, _dv(7, "Người liên hệ: Trần Văn Mẫu")]}]
    dang_mo = {**DANG_MO, "document": DANG_MO["document"] + "- Ghi chú: Hà Nội\n"}
    ra, _ = _chay(
        [
            _dien(1, 0, "Công ty Mẫu Thử"),  # đã có ở phiên bản đang mở
            _dien(3, 0, "Trần Văn Mẫu"),  # chữ của đơn vị 7
            _dien(4, 0, "Hà Nội"),  # chỉ có trong `document` của bản đang mở
            _dien(2, 0, "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP"),  # đoạn trích `quan_sat`
            _doan("thay", 5, "Đồng ý tiếp nhận Trần Văn Mẫu."),
            _doan("chen_sau", 5, "Người liên hệ: Trần Văn Mẫu"),
            _dien(2, 1, "0243999888"),
        ],
        cau="sửa fax thành 0243999888",
        muc_dich="sua_ban_thao",
        tai_lieu=tl,
        ban_thao_tong_quat_dang_mo=dang_mo,
        quan_sat=[{"tai_lieu": "A", "noi_dung": "Tên giấy", "trich": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP"}],
    )
    assert ra["tai_lieu_ket"]["quan_sat"], "đoạn trích neo được — nhưng nó không phải nguồn điền"
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [_p(2, 1, "0243999888")]
    assert [(b["don_vi"], b["cho_trong"], b["ly_do"]) for b in k["bo_qua"]] == [
        (3, 0, "khong_nguon"),
        (4, 0, "khong_nguon"),
        (2, 0, "khong_nguon"),
        (5, None, "khong_nguon"),
        (5, None, "khong_nguon"),
    ]


def test_luot_sua_lap_lai_dung_phep_dang_co_thi_van_la_ban_co_san(bt_gia):
    """Không đổi hành vi owner đã duyệt cho lượt không đổi gì: mô hình lặp lại đúng phép
    đã có (giá trị của lượt TRƯỚC, không còn trong câu lượt này) thì vẫn là thẻ bản đang
    có — không phải "chưa áp được thay đổi nào"."""
    g = bt_gia(_cu(DANG_MO["phep_sua"]))
    ra, _ = _chay(
        [_dien(1, 0, "Công ty Mẫu Thử"), _dien(2, 0, " 0912345678 ")],
        cau="điền giúp tôi biểu mẫu này",
        muc_dich="sua_ban_thao",
        ban_thao_tong_quat_dang_mo=DANG_MO,
        user_sub="u",
        hoi_thoai_id="p",
    )
    assert (ra["khuon_tong_quat"]["phep_sua"], ra["khuon_tong_quat"]["bo_qua"]) == ([], [])
    ra = d.dung_ban_thao_tong_quat(ra)
    assert g.sua_ket is None and ra["ban_thao_ket"]["id"] == "bt-1" and ra["ban_thao_tong_quat_loi"] is None


def test_ho_so_nguoi_noi_la_nguon_gia_dinh_suy_dien_thi_khong():
    """Hồ sơ là nguồn — trừ giả định (`suy_dien`), thứ KLAW tự đọc ra chứ người hỏi
    chưa nói (CONTEXT.md "giả định": không bao giờ là dữ kiện)."""
    ho_so = {
        "vu_viec": {"gia_tri": "Công ty Mẫu Thử", "nguon": "nguoi_noi"},
        "chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"},
    }
    ra, _ = _chay([_dien(1, 0, "Công ty Mẫu Thử"), _dien(3, 0, "người lao động")], cau="điền giúp tôi", ho_so=ho_so)
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [_p(1, 0, "Công ty Mẫu Thử")]
    assert [(b["don_vi"], b["ly_do"]) for b in k["bo_qua"]] == [(3, "khong_nguon")]


def test_khong_dat_chi_giu_gia_tri_nguoi_hoi_da_noi_va_chua_dat():
    """`khuon.khong_dat` là giá trị người hỏi đưa mà mô hình không đặt được. Chỉ giữ mục
    là chuỗi con (không phân biệt hoa/thường, dấu) của lời người hỏi, bỏ trùng, bỏ mục
    đã đặt được; traces chỉ đếm."""
    ra, _ = _chay(
        [_dien(1, 0, "Công ty Mẫu Thử")],
        cau="Điền giúp: cơ quan là Công ty Mẫu Thử, sinh viên Nguyễn Văn Ánh, mã SV 20260099",
        khong_dat=["Nguyen Van Anh", "nguyễn văn ánh", "Trần Thị Bịa", " 20260099 ", "công ty mẫu thử", "", 5],
    )
    k = ra["khuon_tong_quat"]
    assert k["khong_dat"] == ["Nguyen Van Anh", "20260099"]
    assert ra["traces"]["khuon_so_khong_dat"] == 2
    assert "Nguyen" not in json.dumps(ra["traces"], ensure_ascii=False)


@pytest.mark.parametrize("yeu_cau", ["tao_lai", "van_ban_khac"])
def test_khong_dat_rong_khi_khong_dien(yeu_cau):
    ra, _ = _chay([], cau="Nguyễn Văn Ánh", yeu_cau=yeu_cau, khong_dat=["Nguyễn Văn Ánh"])
    assert ra["khuon_tong_quat"]["khong_dat"] == []


def _st_khuon(phep, cho, **khuon) -> dict:
    return {
        "query": "điền giúp",
        "muc_dich_tai_lieu": "tao_van_ban",
        "user_sub": "u",
        "ban_thao_ket": {"id": "bt", "phien_ban": 1, "viec_id": A_ID, "phep_sua": phep, "clauses": []},
        "khuon_tong_quat": {**_khuon(phep, cho), **khuon},
    }


def test_assemble_liet_ke_gia_tri_chua_dat_duoc():
    phep = [_p(0, 0, "A")]
    ra = assemble(_st_khuon(phep, _cho(2), khong_dat=["Nguyễn Văn Ánh"]), {}, _No(), "m")
    assert (
        "Chưa đặt được: «Nguyễn Văn Ánh» — hãy nói rõ chỗ cần điền hoặc bấm vào chỗ trống trên trang." in ra["answer"]
    )
    # Bản có sẵn (lượt sửa không đổi gì) vẫn báo giá trị chưa đặt được.
    st = _st_khuon(phep, _cho(2), khong_dat=["Nguyễn Văn Ánh"], co_san=True)
    assert "Chưa đặt được: «Nguyễn Văn Ánh»" in assemble(st, {}, _No(), "m")["answer"]
    assert "Chưa đặt được" not in assemble(_st_khuon(phep, _cho(2)), {}, _No(), "m")["answer"]


def test_assemble_gia_tri_chua_dat_duoc_trong_tran_900_ky_tu():
    """Trường hợp dài nhất: 30 chỗ trống nhãn dài, nhiều đoạn đã đổi, sáu giá trị dài
    chưa đặt được — lời đáp vẫn ≤ 900 ký tự và vẫn nói có giá trị chưa đặt được."""
    cho = _cho(30)
    phep = [_p(0, 0, "A"), *({"loai": "xoa", "don_vi": i} for i in range(20, 30))]
    st = _st_khuon(phep, cho, khong_dat=[f"Giá trị dài số {i} " + "y" * 60 for i in range(6)])
    st["ban_thao_ket"]["doi_so_voi_truoc"] = [f"Nhãn đổi {i} " + "z" * 50 for i in range(8)]
    ra = assemble(st, {}, _No(), "m")
    assert len(ra["answer"]) <= TRAN_KY_TU and "Chưa đặt được: «Giá trị dài số 0 " in ra["answer"]
    assert "hãy nói rõ chỗ cần điền" in ra["answer"]


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_o_trong_cua_bang_danh_sach_dien_bang_thay():
    """Trang 2 của BM.M05: cột «Họ và tên» của bảng danh sách là các ô RỖNG, không dãy
    chấm nào. `thay` đúng đơn vị ô đó bằng tên người hỏi nói được giữ và áp đúng ô."""
    from src.services.doc_tai_lieu import doc

    goc, hang, tl = _m05()
    ho_ten = next(x for x in tl[0]["don_vi"] if x.bang == (1, 1, 3))
    assert (ho_ten.noi_dung, tl[0]["don_vi"][ho_ten.chi_so - 6].noi_dung) == ("", "Họ và tên")
    ra, llm = _chay(
        [_doan("thay", ho_ten.chi_so, "Nguyễn Văn Ánh")], cau="thêm sinh viên Nguyễn Văn Ánh vào danh sách", tai_lieu=tl
    )
    assert f"[A-{ho_ten.chi_so}] (tr. 2, bảng 2 hàng 2 cột 4) \n" in llm.prompt
    k = ra["khuon_tong_quat"]
    assert (k["phep_sua"], k["bo_qua"]) == (
        [{"loai": "thay", "don_vi": ho_ten.chi_so, "noi_dung": "Nguyễn Văn Ánh"}],
        [],
    )
    moi, bc = ban_thao.ap_phep_sua("docx", goc, hang, k["phep_sua"])
    assert bc["bo_qua"] == []
    assert doc(BM_M05.name, moi).don_vi[ho_ten.chi_so].noi_dung == "Nguyễn Văn Ánh"


def _dv_cham(chi_so: int, s: str, *nhan: str) -> DonViVanBan:
    """Đơn vị một đoạn MANG `doan_chu` như bộ đọc mới: mỗi dãy `…` là một chỗ trống ở
    đúng offset của nó trong chuỗi thô."""
    import re

    cho = tuple(
        ChoTrong(so=i, kieu="cham", nhan=n, doan=0, dau=m.start(), cuoi=m.end())
        for i, (m, n) in enumerate(zip(re.finditer("…+", s), nhan, strict=True))
    )
    return DonViVanBan(
        chi_so=chi_so,
        trang=2,
        offset_dau=0,
        noi_dung=s,
        dia_chi=DiaChi("word/document.xml", (chi_so,)),
        cho_trong=cho,
        doan_chu=(s,),
    )


# Hai hình dạng ngày của BM.M05 (đo trên tệp thật: đơn vị 20 và 14).
NGAY_GACH = _dv_cham(20, "Thời gian: từ … / … / … đến … / … / …", "Thời gian: từ", "/", "/", "đến", "/", "/")
NGAY_CHU = _dv_cham(14, ", ngày … tháng … năm ……….", "ngày", "tháng", "năm")
SO_NGAY = _dv_cham(18, "(Kèm theo giấy số … ngày … tháng … năm …)", "số", "ngày", "tháng", "năm")


@pytest.mark.parametrize("gia_tri", ["01/10/2026", "1-10-2026", "01.10.2026"])
def test_ngay_day_du_vao_cho_dau_cua_bo_ba_gach_cheo_tach_thanh_ba(gia_tri):
    ngay, thang, nam = gia_tri.replace("-", "/").replace(".", "/").split("/")
    ra, _ = _chay(
        [_dien(20, 0, gia_tri), _dien(20, 3, "31/12/2026")],
        cau=f"thời gian từ {gia_tri} đến 31/12/2026",
        tai_lieu=_tl(NGAY_GACH),
    )
    k = ra["khuon_tong_quat"]
    assert k["phep_sua"] == [
        _p(20, 0, ngay),
        _p(20, 1, thang),
        _p(20, 2, nam),
        _p(20, 3, "31"),
        _p(20, 4, "12"),
        _p(20, 5, "2026"),
    ]
    assert k["bo_qua"] == []


def test_ngay_day_du_vao_cho_ngay_cua_ngay_thang_nam_tach_thanh_ba():
    ra, _ = _chay(
        [_dien(14, 0, "27/09/2026"), _dien(18, 1, "5/9/2026")],
        cau="ký ngày 27/09/2026, giấy số 7 ngày 5/9/2026",
        tai_lieu=_tl(NGAY_CHU, SO_NGAY),
    )
    assert ra["khuon_tong_quat"]["phep_sua"] == [
        _p(14, 0, "27"),
        _p(14, 1, "09"),
        _p(14, 2, "2026"),
        _p(18, 1, "5"),
        _p(18, 2, "9"),
        _p(18, 3, "2026"),
    ]


def test_ngay_day_du_khong_tach_khi_mo_hinh_da_dien_hay_khong_dung_hinh_dang():
    """Hẹp, tất định: mô hình đã tự điền một trong hai chỗ sau thì để nguyên; ngày vào
    chỗ không mở một bộ ba (chỗ «số», chỗ giữa bộ ba) hay giá trị không phải ngày đủ
    thì không tách."""
    ra, _ = _chay(
        [
            _dien(20, 0, "01/10/2026"),
            _dien(20, 1, "10"),
            _dien(20, 4, "31/12/2026"),
            _dien(18, 0, "5/9/2026"),
            _dien(14, 0, "10/2026"),
        ],
        cau="từ 01/10/2026 đến 31/12/2026, giấy số 5/9/2026, ký 10/2026",
        tai_lieu=_tl(NGAY_GACH, NGAY_CHU, SO_NGAY),
    )
    assert ra["khuon_tong_quat"]["phep_sua"] == [
        _p(20, 0, "01/10/2026"),
        _p(20, 1, "10"),
        _p(20, 4, "31/12/2026"),
        _p(18, 0, "5/9/2026"),
        _p(14, 0, "10/2026"),
    ]


@pytest.mark.skipif(not BM_M05.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này")
def test_bm_m05_that_ngay_day_du_tach_va_ap_dung_cho():
    from src.services.doc_tai_lieu import doc

    goc, hang, tl = _m05()
    ra, _ = _chay(
        [_dien(20, 0, "01/10/2026"), _dien(20, 3, "31/12/2026"), _dien(13, 0, "01/10/2026"), _dien(14, 0, "27/9/2026")],
        cau="thời gian từ 01/10/2026 đến 31/12/2026, ký ngày 27/9/2026",
        tai_lieu=tl,
    )
    k = ra["khuon_tong_quat"]
    assert k["bo_qua"] == [] and len(k["phep_sua"]) == 12
    moi, bc = ban_thao.ap_phep_sua("docx", goc, hang, k["phep_sua"])
    assert bc["bo_qua"] == []
    dv = doc(BM_M05.name, moi).don_vi
    assert dv[20].noi_dung == "Thời gian: từ 01 / 10 / 2026 đến 31 / 12 / 2026"
    assert dv[13].noi_dung.startswith("Thời gian: từ ngày 01 tháng 10 năm 2026 đến ngày …")
    assert dv[14].noi_dung.startswith(", ngày 27 tháng 9 năm 2026")
