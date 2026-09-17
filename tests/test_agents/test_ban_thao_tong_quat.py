"""Bản thảo tổng quát (S6) — soạn một văn bản MỚI từ tài liệu người hỏi gửi,
không qua checklist nào (CONTEXT.md "bản thảo tổng quát", "mức kiểm").

Năm điều bị khoá ở đây:

1. Mọi con số, ngày tháng, số tiền, số hiệu trong một mục do mô hình viết phải
   CÓ THẬT trong nguồn của lượt (tài liệu + lời người hỏi + dữ kiện đã có).
   Cái không có bị thay bằng `[…]` — không bao giờ bằng một giá trị đoán
   (FR-011).
2. Một mục còn vướng `bo_nho._vuong_luoi_chan` sau khi làm sạch thì bị BỎ: số
   Điều/Khoản và dấu vết định danh cá nhân không có chỗ trong một bản thảo
   chưa kiểm pháp lý.
3. Bản thảo tổng quát đi qua ĐÚNG bảng `ban_thao` cũ, nên phiên bản,
   `phien_ban_truoc` và `lui` không phải viết lại lần thứ hai.
4. `audit_report.muc_kiem == "tong_quat"` và lời đáp nói thẳng "chưa kiểm pháp
   lý" — không lượt nào được để nó trông như đã qua rà soát.
5. Khách chưa đăng nhập không chạm tới chỗ lưu: họ nhận lời mời đăng nhập,
   cùng hình dạng với nhánh `soan_thao_hoi` đã có.

Phase 8 đổi hình dạng nội dung một mục từ `noi_dung`/`bang` cố định (Phase 7)
sang `khoi` — mảng khối theo đúng thứ tự tài liệu, mỗi khối lại là
`noi_dung`/`bang` — cộng `vung` (đầu trang/chân trang/thân bài). Các test
"phép kiểm bảng" và "hình dạng mục" dưới đây viết theo hình dạng MỚI; test
`_muc()` là hàm dựng nhanh một mục một-khối cho các ca không cần nhiều khối.
"""

import json
import uuid
from pathlib import Path

import pytest

from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import ResultType, assemble
from src.models.schemas import TraCuuResponse
from src.services import ban_thao
from src.services.doc_tai_lieu import DonViVanBan, doc
from src.services.llm import TruncatedOutputError

A_ID = "aaaaaaaa-0000-0000-0000-000000000001"

DV_A = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Biên bản bàn giao thiết bị số 12/2026"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=60, noi_dung="Bàn giao ngày 01/10/2026 tại kho A"),
    DonViVanBan(chi_so=2, trang=1, offset_dau=120, noi_dung="Tổng giá trị thiết bị 20.000.000 đồng"),
]
TL = [{"id": A_ID, "ten_tep": "bienban.docx", "don_vi": DV_A}]
NGUON = "\n".join(dv.noi_dung for dv in DV_A)


def _muc(ten: str, noi_dung: str = "", bang=None, vung: str = "than") -> dict:
    """Dựng nhanh MỘT mục một-khối — đủ cho mọi ca không cần nhiều khối."""
    return {"ten": ten, "vung": vung, "khoi": [{"noi_dung": noi_dung, "bang": bang or []}]}


VAN_BAN = {
    "tieu_de": "BIÊN BẢN BÀN GIAO THIẾT BỊ",
    "muc": [
        _muc("Thời gian bàn giao", "Bàn giao ngày 01/10/2026 tại kho A."),
        _muc("Giá trị", "Tổng giá trị thiết bị 20.000.000 đồng."),
    ],
}


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra):
        self.ra, self.json_schema = ra, None
        self.so_lan_goi = 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.json_schema = json_schema
        self.so_lan_goi += 1
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


def _ra(**ghi_de) -> dict:
    ra = {"muc_dich": "tao_van_ban", "mo_ta": "Biên bản bàn giao", "tra_loi_ngan": "Đã soạn.",
          "quan_sat": [], "suy_luan": [], "can_du_kien": [], "phep_tinh": [], "truong": [],
          "khac_biet": [], "van_ban": VAN_BAN}
    ra.update(ghi_de)
    return ra


def _sach(muc: list[dict], nguon: str = NGUON, goi: list[dict] | None = None):
    return h.lam_sach_van_ban({"tieu_de": "T", "muc": muc}, nguon, goi)


# ────────────────────────────────────── phép kiểm bịa nội dung (0 token)


def test_gia_tri_chep_tu_tai_lieu_di_qua_nguyen_ven():
    van_ban, dem = _sach([_muc("Thời gian", "Bàn giao ngày 01/10/2026 tại kho A.")])
    assert van_ban["muc"][0]["khoi"][0]["noi_dung"] == "Bàn giao ngày 01/10/2026 tại kho A."
    assert dem == {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0}


def test_so_hieu_tai_lieu_trong_mot_muc_khong_bi_coi_la_bia():
    """Số hiệu CỦA CHÍNH tài liệu ("12/2026") có trong nguồn, nên nó qua phép
    chứa; `_vuong_luoi_chan` vẫn bắt nó ở tầng sau và mục bị bỏ — đó là hai
    phép kiểm khác nhau, và test này khoá phép ĐẦU."""
    van_ban, dem = _sach([_muc("Căn cứ", "Theo biên bản số 12/2026 đã lập.")])
    assert dem["gia_tri_lam_sach"] == 0, "giá trị có trong nguồn thì không bị thay"


def test_ngay_thang_bia_bi_thay_bang_dau_ba_cham():
    van_ban, dem = _sach([_muc("Thời gian", "Bàn giao ngày 15/11/2027 tại kho A.")])
    noi_dung = van_ban["muc"][0]["khoi"][0]["noi_dung"]
    assert "15/11/2027" not in noi_dung
    assert "[…]" in noi_dung
    assert dem["muc_lam_sach"] == 1 and dem["gia_tri_lam_sach"] == 1


def test_so_tien_bia_bi_thay_va_dem_theo_tung_gia_tri():
    van_ban, dem = _sach([_muc("Giá trị", "Trị giá 99.000.000 đồng, đặt cọc 5.000.000 đồng.")])
    noi_dung = van_ban["muc"][0]["khoi"][0]["noi_dung"]
    assert "99.000.000" not in noi_dung
    assert "5.000.000" not in noi_dung
    assert dem["gia_tri_lam_sach"] == 2 and dem["muc_lam_sach"] == 1


def test_so_viet_kieu_khac_van_khop_gia_tri_trong_nguon():
    """`20.000.000` trong tài liệu và `20000000` mô hình viết là MỘT con số —
    phép so đọc theo cùng quy ước với `phep_tinh`, không so chuỗi thô."""
    van_ban, dem = _sach([_muc("Giá trị", "Tổng 20000000 đồng.")])
    assert dem["gia_tri_lam_sach"] == 0


def test_so_dieu_luat_bia_bi_thay_roi_muc_duoc_giu():
    """"Điều 42" không có trong nguồn → số bị thay bằng `[…]`, và sau đó mục
    không còn vướng lưới chặn nên nó ở lại (có nhãn, người đọc tự điền)."""
    van_ban, dem = _sach([_muc("Căn cứ", "Căn cứ Điều 42 của quy chế công ty.")])
    assert dem["muc_bo"] == 0 and dem["gia_tri_lam_sach"] == 1
    assert "Điều […]" in van_ban["muc"][0]["khoi"][0]["noi_dung"]


def test_muc_con_vuong_luoi_chan_sau_khi_lam_sach_thi_bi_bo():
    """Số Điều CÓ trong nguồn đi qua phép chứa, nên chỉ lưới chặn dùng chung với
    `bo_nho` mới bắt được — và mục đó bị bỏ, có đếm."""
    van_ban, dem = _sach(
        [_muc("Căn cứ", "Căn cứ Điều 42 Bộ luật Lao động.")],
        nguon="Căn cứ Điều 42 Bộ luật Lao động",
    )
    assert van_ban["muc"] == [] and dem["muc_bo"] == 1


def test_dau_vet_dinh_danh_ca_nhan_bi_bo_ca_muc():
    van_ban, dem = _sach(
        [_muc("Liên hệ", "Liên hệ ban@vidu.vn để nhận bàn giao.")],
        nguon="Liên hệ ban@vidu.vn để nhận bàn giao",
    )
    assert van_ban["muc"] == [] and dem["muc_bo"] == 1


def test_muc_rong_hoac_sai_hinh_dang_bi_bo_khong_no():
    van_ban, dem = h.lam_sach_van_ban({"tieu_de": "T", "muc": ["x", {"ten": "", "khoi": []}]}, NGUON)
    assert van_ban["muc"] == []


def test_vung_khong_hop_le_roi_ve_than():
    """`vung` lạ (không phải `than`/`dau_trang`/`chan_trang`) rơi về `than` —
    fail-closed, không để một giá trị lạ đi tiếp vào `clauses`."""
    van_ban, _ = _sach([_muc("Ghi chú", "BM.X", vung="linh_tinh")])
    assert van_ban["muc"][0]["vung"] == "than"


def test_vung_chan_trang_song_sot():
    """Phase 8 R2 — một mục đánh dấu `chan_trang` giữ đúng nhãn đó qua phép
    làm sạch, không bị gộp về `than`."""
    chan = "BM.ĐT.18.11 (02-15/05/2025)-BL: 03 năm sau tốt nghiệp"
    van_ban, _ = _sach([_muc("Chân trang", chan, vung="chan_trang")], nguon=chan)
    assert van_ban["muc"][0]["vung"] == "chan_trang"
    assert van_ban["muc"][0]["khoi"][0]["noi_dung"] == chan


# ──────────────────────────────────────────────── phép kiểm khối (Phase 8 R1)


NGUON_BANG = "1 Ý thức chấp hành nội quy 2,0 2 Tinh thần trách nhiệm 2,0"
BANG_HOP_LE = [
    ["TT", "Tiêu chí đánh giá", "Điểm tối đa"],
    ["1", "Ý thức chấp hành nội quy", "2,0"],
]


def test_muc_bang_khong_can_noi_dung_de_duoc_giu():
    """Nội dung một khối BẢNG nằm ở `bang`, không ở `noi_dung` — `noi_dung`
    rỗng không còn là một khối thiếu chữ khi `bang` có hàng."""
    van_ban, dem = _sach([_muc("Đánh giá", bang=BANG_HOP_LE)], nguon=NGUON_BANG)
    assert len(van_ban["muc"]) == 1
    assert van_ban["muc"][0]["khoi"] == [
        {"noi_dung": "", "bang": BANG_HOP_LE, "can_le": "trai", "nhip": [], "ti_le": []}
    ]
    assert dem["gia_tri_lam_sach"] == 0


def test_muc_khong_khoi_nao_van_bi_bo():
    """Mảng `khoi` rỗng — mục không còn nội dung nào, bị bỏ như trước (Phase 8
    không nới lỏng luật này, chỉ đổi chỗ kiểm từ noi_dung/bang sang khoi)."""
    van_ban, _ = h.lam_sach_van_ban(
        {"tieu_de": "T", "muc": [{"ten": "Trống", "vung": "than", "khoi": []}]}, NGUON_BANG
    )
    assert van_ban["muc"] == []


def test_khoi_rong_ca_hai_bi_loai_nhung_muc_van_con_khoi_khac():
    """Một khối RỖNG cả `noi_dung` lẫn `bang` bị loại khỏi `khoi`; các khối
    khác của CÙNG mục vẫn giữ — không bỏ cả mục vì một khối trắng."""
    muc = {"ten": "Đánh giá", "vung": "than", "khoi": [
        {"noi_dung": "", "bang": []},
        {"noi_dung": "", "bang": BANG_HOP_LE},
    ]}
    van_ban, _ = _sach([muc], nguon=NGUON_BANG)
    assert van_ban["muc"][0]["khoi"] == [
        {"noi_dung": "", "bang": BANG_HOP_LE, "can_le": "trai", "nhip": [], "ti_le": []}
    ]


def test_khoi_nhieu_phan_tu_giu_dung_thu_tu():
    """Phase 8 R1 — câu dẫn, một bảng, RỒI một câu kết: BA khối, giữ ĐÚNG thứ
    tự tài liệu, không bị nén về một cặp noi_dung/bang cố định như Phase 7."""
    muc = {
        "ten": "Đánh giá",
        "vung": "than",
        "khoi": [
            {"noi_dung": "Kết quả chấm điểm như sau:", "bang": []},
            {"noi_dung": "", "bang": BANG_HOP_LE},
            {"noi_dung": "Điểm trên do hội đồng thống nhất.", "bang": []},
        ],
    }
    van_ban, _ = _sach([muc], nguon=NGUON_BANG)
    khoi = van_ban["muc"][0]["khoi"]
    assert [bool(k["bang"]) for k in khoi] == [False, True, False]
    assert khoi[0]["noi_dung"] == "Kết quả chấm điểm như sau:"
    assert khoi[2]["noi_dung"] == "Điểm trên do hội đồng thống nhất."


def test_o_bang_bia_bi_thay_bang_dau_ba_cham_nhu_noi_dung():
    """Một ô có số KHÔNG có trong nguồn đi qua ĐÚNG phép làm sạch của
    `noi_dung`/`ten` — một ô cũng là một giá trị có thể bịa."""
    bang = [["TT", "Điểm tối đa"], ["1", "2,0"], ["2", "9,9"]]  # "9,9" bịa, không có trong nguồn
    van_ban, dem = _sach([_muc("Đánh giá", bang=bang)], nguon=NGUON_BANG)
    khoi_bang = van_ban["muc"][0]["khoi"][0]["bang"]
    assert khoi_bang[1] == ["1", "2,0"]
    assert khoi_bang[2] == ["2", "[…]"]
    assert dem["gia_tri_lam_sach"] == 1


def test_bang_vuong_luoi_chan_lam_bo_ca_muc():
    """Một ô còn số Điều/Khoản sau khi làm sạch bắt mục qua ĐÚNG lưới chặn
    dùng chung với văn xuôi — không có đường né nào riêng cho bảng."""
    bang = [["Căn cứ"], ["Điều 42 Bộ luật Lao động"]]
    van_ban, dem = _sach([_muc("Căn cứ", bang=bang)], nguon="Điều 42 Bộ luật Lao động")
    assert van_ban["muc"] == [] and dem["muc_bo"] == 1


def test_bang_khong_phai_mang_hay_hang_khong_phai_mang_bi_bo_khong_no():
    van_ban, _ = _sach([_muc("Đánh giá", bang="không phải mảng")], nguon=NGUON_BANG)
    assert van_ban["muc"] == []
    van_ban2, _ = _sach(
        [_muc("Đánh giá", bang=["không phải mảng", ["1", "2,0"]])],
        nguon=NGUON_BANG,
    )
    assert van_ban2["muc"][0]["khoi"][0]["bang"] == [["1", "2,0"]]


def test_hang_ngan_hon_tieu_de_di_qua_nguyen_khong_bi_dem():
    """Phase 8 R4 — ô gộp trong tài liệu nguồn: hàng "Tổng" chỉ có 2 ô trong
    khi hàng tiêu đề có 4. Giữ ĐÚNG số ô thật, không đệm rỗng cho đủ cột và
    không cắt bớt — quyết định "hàng ngắn được giữ nguyên" nằm ở đây; phía
    hiển thị (frontend `coSpanHang`) mới quyết định cách VẼ hàng ngắn đó."""
    bang = [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức chấp hành nội quy", "2,0", "2,0"],
        ["Tổng", "10"],
    ]
    van_ban, _ = _sach(
        [_muc("Đánh giá", bang=bang)], nguon="1 Ý thức chấp hành nội quy 2,0 2,0 Tổng 10"
    )
    assert van_ban["muc"][0]["khoi"][0]["bang"][2] == ["Tổng", "10"]


def test_hang_du_cot_voi_o_cuoi_rong_khong_bi_cat():
    """Review round 1 [CRITICAL] — một hàng ĐỦ 4 cột (khớp hàng tiêu đề) mà ô
    CUỐI để trống vì bản thân tiêu chí đó CHƯA CHẤM (không phải ô gộp) phải
    giữ ĐỦ 4 ô, không bị cắt xuống 3 rồi bị `coSpanHang` phía đọc hiểu nhầm là
    một hàng gộp — đúng ca một phiếu ĐANG CHỜ ĐIỀN có cả cột "Điểm đánh giá"
    để trống, phổ biến hơn hàng "Tổng" thật sự gộp. Một bản trước của
    `_bang_sach` cắt ô rỗng ở cuối để sửa ca mô hình đệm dư hàng "Tổng" — sửa
    đó bị BỎ vì nó không phân biệt được ca này với ca kia (xem docstring
    `_bang_sach`); hàng ngắn do mô hình đệm dư (không phải gộp thật) vẫn có
    thể hiện sai cột — hạn chế đã ghi trong báo cáo, không phải lỗi có thể
    sửa an toàn ở tầng này."""
    bang = [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức tốt", "2,0", ""],
    ]
    van_ban, _ = _sach([_muc("Đánh giá", bang=bang)], nguon="1 Ý thức tốt 2,0")
    assert van_ban["muc"][0]["khoi"][0]["bang"][1] == ["1", "Ý thức tốt", "2,0", ""]


def test_hang_trang_toan_o_rong_khong_bi_cat_ve_rong():
    """Review round 1 [CRITICAL], hệ quả thứ hai của phép cắt đã bỏ — một hàng
    ĐỦ cột mà TOÀN BỘ là ô rỗng (một hàng ngăn cách/để trống có chủ đích trong
    biểu mẫu) không bị cắt trụi về `[]`; nó vẫn là một hàng 3 ô rỗng."""
    bang = [["A", "B", "C"], ["", "", ""]]
    van_ban, _ = _sach([_muc("Đánh giá", bang=bang)], nguon="x")
    assert van_ban["muc"][0]["khoi"][0]["bang"][1] == ["", "", ""]


def test_khoi_ca_hai_khac_rong_bi_tach_thanh_hai_khoi():
    """Review round 1 [IMPORTANT] — một khối thô có CẢ `noi_dung` lẫn `bang`
    khác rỗng (rule 15 chỉ XIN, schema không ép "một trong hai") bị TÁCH thành
    HAI khối sạch, văn xuôi TRƯỚC rồi bảng — không phía nào phải tự chọn ưu
    tiên và bỏ mất nội dung còn lại, đúng lỗi hai phía đọc (`_khoi_thanh_van_ban`
    và `xuat-tep.ts::khoiMotHopLe`) từng chọn ngược nhau."""
    muc = {
        "ten": "Đánh giá",
        "vung": "than",
        "khoi": [{"noi_dung": "Kết quả chấm điểm như sau:", "bang": BANG_HOP_LE}],
    }
    van_ban, _ = _sach([muc], nguon=NGUON_BANG)
    khoi = van_ban["muc"][0]["khoi"]
    assert len(khoi) == 2
    assert khoi[0] == {
        "noi_dung": "Kết quả chấm điểm như sau:", "bang": [], "can_le": "trai", "nhip": [], "ti_le": [],
    }
    assert khoi[1] == {"noi_dung": "", "bang": BANG_HOP_LE, "can_le": "trai", "nhip": [], "ti_le": []}


def test_letterhead_hai_cot_song_sot_nhu_bang():
    """Brief "Proof required", ca THUẬN (mô hình tự viết ĐÚNG hình dạng bảng,
    không cần khớp lại) — một bảng KHÔNG viền, hàng đầu đủ 2 cột (tên đơn vị /
    quốc hiệu), hàng hai chỉ 1 ô gộp cả hai cột (tên cơ quan + số hiệu). Phải
    sống sót NGUYÊN dạng bảng — không bị dẹt thành các dòng văn xuôi đứng
    riêng — và hàng gộp giữ ĐÚNG 1 ô, không bị đệm hay cắt.

    Review round 2: đo thật cho thấy mô hình KHÔNG luôn viết đúng hình dạng
    này — xem `test_node_khop_lai_letterhead_bi_mo_hinh_xe_thanh_van_xuoi`
    dưới, ca mô hình xé letterhead thành văn xuôi và phép khớp lại
    (`_khop_bang`) phải tự cứu, không đợi mô hình viết đúng."""
    letterhead = [
        [
            "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
            "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
        ],
        ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
    ]
    nguon = " ".join(o for hang in letterhead for o in hang)
    van_ban, _ = _sach([_muc("Đầu trang", bang=letterhead)], nguon=nguon)
    khoi = van_ban["muc"][0]["khoi"][0]
    assert khoi["noi_dung"] == "", "letterhead không lẫn vào văn xuôi"
    assert len(khoi["bang"]) == 2 and len(khoi["bang"][0]) == 2, "hàng đầu giữ đúng 2 cột"
    assert khoi["bang"] == letterhead, "sống sót NGUYÊN dạng bảng, không dẹt thành dòng"


# ────────────────────── phép khớp lại bảng thật từ don_vi (review round 2)
#
# Root cause chung với review round 1: cấu trúc reader ĐÃ BIẾT (bảng thật,
# `(bảng, hàng, cột)` từ `doc_tai_lieu`) bị bắt mô hình đoán/gõ lại. `_khop_bang`
# đối chiếu NGUYÊN VĂN từng khối mô hình viết với chính đơn vị-trong-bảng của
# tài liệu, rồi THAY bằng bảng thật khi khớp — không đợi mô hình khai đúng.

# BM.M05 thật (đo lại `w:gridSpan` trực tiếp, Phase 11 fix round 2): hàng hai
# KHÔNG gộp — nó có ĐỦ 2 ô lưới thật như hàng đầu, ô thứ hai chỉ rỗng chữ
# (không có `w:gridSpan` nào trên cả hai ô của hàng này). Bản trước (Phase 8,
# và Phase 11 round 1 kế thừa) đọc nhầm thành "gộp" vì reader CŨ bỏ qua ô rỗng
# chữ — hàng chỉ còn 1 ô THẤY ĐƯỢC nên bị suy là gộp, đúng lỗi round 2 sửa
# (`doc_tai_lieu._duyet_than` giờ giữ cả ô rỗng).
DV_LETTERHEAD = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Mẫu QT.ĐT.28-M05"),
    DonViVanBan(
        chi_so=1, trang=1, offset_dau=20,
        noi_dung="TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)", bang=(0, 0, 0),
    ),
    DonViVanBan(
        chi_so=2, trang=1, offset_dau=80,
        noi_dung="CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc", bang=(0, 0, 1),
    ),
    DonViVanBan(
        chi_so=3, trang=1, offset_dau=150,
        noi_dung="TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", bang=(0, 1, 0),
    ),
    DonViVanBan(chi_so=4, trang=1, offset_dau=190, noi_dung="", bang=(0, 1, 1)),
]
GOI_LETTERHEAD = [{"id": "x", "ten_tep": "bm05.docx", "don_vi": DV_LETTERHEAD, "nhan": "A", "gui": DV_LETTERHEAD}]
NGUON_LETTERHEAD = "\n".join(dv.noi_dung for dv in DV_LETTERHEAD if dv.noi_dung)


def test_bang_theo_nhan_dung_lai_dung_luoi_tu_don_vi():
    """`_bang_theo_nhan` — dựng lại bảng THẬT 0 token, không đoán: CẢ hai hàng
    đủ 2 ô thật (Phase 11 fix round 2 — ô thứ hai của hàng hai rỗng chữ nhưng
    vẫn là một Ô THẬT, không phải một hàng gộp: reader giờ giữ ô rỗng thay vì
    coi số ô ít hơn là dấu hiệu gộp). `nhip` đi CÙNG `hang`, cả hai hàng đều
    nhịp 1×1 — không suy đoán gộp từ số ô chênh lệch."""
    ra = h._bang_theo_nhan(GOI_LETTERHEAD)
    assert ra == {
        "A0": {
            "hang": [
                [
                    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                ],
                ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", ""],
            ],
            "nhip": [[1, 1], [1, 1]],
            "ti_le": [],
        }
    }


def test_khop_bang_cuu_letterhead_bi_xe_thanh_van_xuoi():
    """Review round 2 [chứng cứ chính] — mô phỏng ĐÚNG chế độ hỏng đo được
    thật trên BM.M05: mô hình xé letterhead thành BA khối văn xuôi riêng,
    BỎ SÓT một ô (không nhắc "TÊN CHỦ QUẢN…" luôn). `_khop_bang` phải khớp hai
    khối còn lại (liền kề, cùng khớp bảng A0) và THAY bằng bảng THẬT — kể cả ô
    mô hình bỏ sót cũng quay lại, vì nó lấy nguyên bảng chứ không chỉ phần mô
    hình nhắc tới."""
    muc_xe = {
        "ten": "Đầu trang",
        "vung": "dau_trang",
        "khoi": [
            {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []},
            {
                "noi_dung": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                "bang": [],
            },
            {"noi_dung": "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", "bang": []},
        ],
    }
    van_ban, _ = _sach([muc_xe], nguon=NGUON_LETTERHEAD, goi=GOI_LETTERHEAD)
    assert van_ban["muc"][0]["khoi"] == [
        {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": [], "can_le": "trai", "nhip": [], "ti_le": []},
        {
            "noi_dung": "",
            "bang": [
                [
                    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                ],
                ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", ""],
            ],
            "nhip": [[1, 1], [1, 1]],
            "ti_le": [],
            "can_le": "trai",
        },
    ]


def test_khop_bang_khong_gop_mot_dong_van_xuoi_don_le_trung_ngau_nhien():
    """Ngưỡng ≥2 khối liền kề: MỘT khối văn xuôi trùng khớp một ô của bảng
    không đủ để kết luận cả mục đó là bảng bị xé lẻ — giữ nguyên văn xuôi."""
    muc = {
        "ten": "Ghi chú",
        "vung": "than",
        "khoi": [{"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []}],
    }
    van_ban, _ = _sach([muc], nguon=NGUON_LETTERHEAD, goi=GOI_LETTERHEAD)
    assert van_ban["muc"][0]["khoi"] == [
        {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": [], "can_le": "trai", "nhip": [], "ti_le": []}
    ]


def test_khop_bang_gop_qua_hai_muc_khac_nhau_khong_chi_hai_khoi_cung_muc():
    """Phase 11 fix round 1 — đo được thật trên BM.M05 (draft `b0c76517…`, HTTP
    trực tiếp): mô hình xé letterhead 2 cột thành HAI MỤC RIÊNG, mỗi mục đúng
    MỘT khối ("Quốc hiệu và tiêu ngữ" và "Thông tin cơ quan tiếp nhận") — không
    phải hai khối trong CÙNG một mục như `test_khop_bang_cuu_letterhead_bi_xe_thanh_van_xuoi`
    mô phỏng. Corpus check (một lượt gọi model KHÁC) từng thấy bảng được cứu vì
    mô hình tình cờ gộp cả hai khối vào MỘT mục — hai lượt gọi khác nhau ra hai
    hình dạng khác nhau, và bản vá trước chỉ đúng cho MỘT trong hai. `_khop_bang`
    giờ xét TOÀN VĂN BẢN (mọi mục ghép phẳng), nên hai khối liền kề ở hai mục
    liền nhau vẫn gộp được — mục thứ hai hết khối, bị bỏ, mục đầu giữ bảng thật."""
    muc_1 = {
        "ten": "Quốc hiệu và tiêu ngữ",
        "vung": "than",
        "khoi": [
            {"noi_dung": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập – Tự do – Hạnh phúc", "bang": []}
        ],
    }
    muc_2 = {
        "ten": "Thông tin cơ quan tiếp nhận",
        "vung": "than",
        "khoi": [{"noi_dung": "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN\nSố …./….", "bang": []}],
    }
    van_ban, _ = _sach([muc_1, muc_2], nguon=NGUON_LETTERHEAD, goi=GOI_LETTERHEAD)
    assert len(van_ban["muc"]) == 1, "mục thứ hai hết khối (gộp hết vào bảng) phải bị bỏ, không còn đứng riêng"
    khoi = van_ban["muc"][0]["khoi"]
    assert len(khoi) == 1 and khoi[0]["bang"] == [
        [
            "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
            "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
        ],
        ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", ""],
    ], "bảng thật nguyên vẹn, kể cả ô mô hình chưa từng nhắc tới (TÊN CHỦ QUẢN...)"


# BM.ĐT.18.11 thật: hàng cuối "Tổng | 10" gộp 3 cột nhãn thành 1 (Phase 8 R4).
DV_BANG_DIEM = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="TT", bang=(0, 0, 0)),
    DonViVanBan(chi_so=1, trang=1, offset_dau=3, noi_dung="Tiêu chí đánh giá", bang=(0, 0, 1)),
    DonViVanBan(chi_so=2, trang=1, offset_dau=25, noi_dung="Điểm tối đa", bang=(0, 0, 2)),
    DonViVanBan(chi_so=3, trang=1, offset_dau=40, noi_dung="Điểm đánh giá", bang=(0, 0, 3)),
    DonViVanBan(chi_so=4, trang=1, offset_dau=55, noi_dung="1", bang=(0, 1, 0)),
    DonViVanBan(chi_so=5, trang=1, offset_dau=57, noi_dung="Ý thức chấp hành nội quy", bang=(0, 1, 1)),
    DonViVanBan(chi_so=6, trang=1, offset_dau=85, noi_dung="2,0", bang=(0, 1, 2)),
    DonViVanBan(chi_so=7, trang=1, offset_dau=90, noi_dung="1,8", bang=(0, 1, 3)),
    # "Tổng" gộp thật 2 cột lưới (TT + Tiêu chí, `w:gridSpan="2"` đo trên tệp
    # thật, Phase 11 R6) — "10" đứng ở cột lưới THẬT (2, "Điểm tối đa"), không
    # phải cột kế tiếp theo số thứ tự ô.
    DonViVanBan(chi_so=8, trang=1, offset_dau=95, noi_dung="Tổng", bang=(0, 2, 0), bang_nhip=2),
    DonViVanBan(chi_so=9, trang=1, offset_dau=100, noi_dung="10", bang=(0, 2, 2)),
]
GOI_BANG_DIEM = [{"id": "y", "ten_tep": "dt1811.docx", "don_vi": DV_BANG_DIEM, "nhan": "A", "gui": DV_BANG_DIEM}]
NGUON_BANG_DIEM = "\n".join(dv.noi_dung for dv in DV_BANG_DIEM)


def test_khop_bang_cuu_hang_gop_bi_dem_du():
    """Review round 2 — mô phỏng ĐÚNG chế độ hỏng đo được thật trên
    BM.ĐT.18.11 (fix round 1): mô hình đệm hàng "Tổng" thành đủ 4 ô
    (`["Tổng","10","",""]`) dù nguồn chỉ có 2 ô gộp. Mọi ô khác rỗng của khối
    này khớp riêng một bảng (A0) → `_khop_bang` thay NGUYÊN bảng đó, hàng
    "Tổng" trở lại đúng 2 ô — không cần biết "đệm" là gì, chỉ cần đối chiếu.
    Đây cũng là hệ quả round 2 mang lại cho residual round 1 đã ghi nhận: một
    khi nội dung bảng đến từ `don_vi` chứ không phải mô hình gõ, không còn gì
    để đệm sai nữa."""
    bang_dem = [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức chấp hành nội quy", "2,0", "1,8"],
        ["Tổng", "10", "", ""],
    ]
    muc = {"ten": "Đánh giá", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_dem}]}
    van_ban, _ = _sach([muc], nguon=NGUON_BANG_DIEM, goi=GOI_BANG_DIEM)
    khoi_bang = van_ban["muc"][0]["khoi"][0]
    assert khoi_bang["bang"] == [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức chấp hành nội quy", "2,0", "1,8"],
        # Hàng gộp trở lại đúng nhịp thật: "Tổng" chiếm 2 cột (nhịp 2), "10"
        # 1 cột, và một Ô ĐỆM rỗng lấp cột lưới còn thiếu (Phase 11 R6) — thay
        # vì đệm sai cột như mô hình đã viết, đây là ô đệm ĐÚNG vị trí ("Điểm
        # đánh giá" thật sự trống ở hàng Tổng).
        ["Tổng", "10", ""],
    ]
    assert khoi_bang["nhip"][-1] == [2, 1, 1], "Tổng chiếm 2 cột, 10 chiếm 1, ô đệm chiếm phần còn lại"


def test_khop_bang_khong_ghi_de_bang_da_sua_giu_lai_mot_o_goc():
    """Review round 3 [HIGH] — người dùng xin "chỉ giữ lại hàng Tổng", mô hình
    LÀM ĐÚNG: bảng mới chỉ còn một hàng, nhãn cột viết lại khác nguồn, chỉ MỘT
    ô ("Tổng") tình cờ trùng chữ với bảng gốc. Một bản trước của `_khop_bang`
    lọc bỏ các ô KHÔNG khớp rồi chỉ xét ô đã khớp — ở đây "Tổng" là ô DUY NHẤT
    còn lại sau khi lọc, nên nó "khớp một bảng duy nhất" và bị ghi đè NGUYÊN
    bảng gốc, HUỶ MẤT sửa đổi thật của người dùng. Luật ĐÚNG (docstring
    `_khop_bang` đã nói, giờ code phải làm đúng): MỌI ô khác rỗng phải khớp,
    không chỉ ô nào tình cờ khớp — "Mục"/"Giá trị"/"8" không khớp gì cả nên
    khối này KHÔNG được thay, giữ nguyên bảng đã sửa."""
    bang_da_sua = [["Mục", "Giá trị"], ["Tổng", "8"]]
    muc = {"ten": "Đánh giá", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_da_sua}]}
    van_ban, _ = _sach([muc], nguon="Mục Giá trị Tổng 8", goi=GOI_BANG_DIEM)
    assert van_ban["muc"][0]["khoi"][0]["bang"] == bang_da_sua


# ────────────── Phase 11 R7 — letterhead gộp NHIỀU DÒNG thành MỘT khối văn xuôi
#
# Đo thật trên BM.ĐT.18.05 (draft `9d0aa73e…`): mỗi ô letterhead có 2 đoạn văn
# nguồn, reader nối chúng bằng DẤU CÁCH thành MỘT đơn vị-trong-bảng ("TRƯỜNG
# ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN"). Mô hình, khi tái hiện, gộp cả
# BỐN dòng nguồn (2 ô × 2 đoạn) thành MỘT khối `noi_dung`, nối bằng `\n`
# ("TRƯỜNG ĐẠI HỌC PHENIKAA\nTRƯỜNG CÔNG NGHỆ THÔNG TIN\nCỘNG HOÀ...\nĐộc
# lập...") — khớp NGUYÊN VĂN khối đó vào MỘT ô (`_bang_cua`) không bao giờ
# đúng vì khối dài hơn bất kỳ ô nào, nên khối ở lại dạng văn xuôi, đúng lỗi đo
# được ("KLAW renders all four lines as one left-aligned prose block").

DV_LETTERHEAD_2_DOAN = [
    DonViVanBan(
        chi_so=0, trang=1, offset_dau=0,
        noi_dung="TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN",
        bang=(0, 0, 0), bang_ti_le=(45, 55),
    ),
    DonViVanBan(
        chi_so=1, trang=1, offset_dau=60,
        noi_dung="CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc",
        bang=(0, 0, 1), bang_ti_le=(45, 55),
    ),
]
GOI_LETTERHEAD_2_DOAN = [
    {"id": "z", "ten_tep": "bm1805.docx", "don_vi": DV_LETTERHEAD_2_DOAN, "nhan": "A", "gui": DV_LETTERHEAD_2_DOAN}
]
NGUON_LETTERHEAD_2_DOAN = "\n".join(dv.noi_dung for dv in DV_LETTERHEAD_2_DOAN)


def test_bang_cua_nhieu_dong_ghep_dung_letterhead_bi_gop_mot_khoi():
    """Phase 11 R7 — mô phỏng ĐÚNG khối mô hình thật viết cho BM.ĐT.18.05: bốn
    dòng nguồn gộp thành MỘT khối `noi_dung`, nối bằng `\\n`. `_bang_cua`
    (khớp nguyên khối vào một ô) không khớp vì khối dài hơn một ô; ghép dòng
    lại thành hai ô thật (`_bang_cua_nhieu_dong`) thì khớp TRỌN VẸN — không
    còn dòng nào thừa, không ô nào thiếu — nên khối được thay bằng bảng thật,
    dù chỉ là MỘT khối (không cần ≥2 khối liền kề như câu trùng khớp một ô lẻ)."""
    khoi_ghep = (
        "TRƯỜNG ĐẠI HỌC PHENIKAA\nTRƯỜNG CÔNG NGHỆ THÔNG TIN\n"
        "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc"
    )
    muc = {"ten": "Đầu trang", "vung": "than", "khoi": [{"noi_dung": khoi_ghep, "bang": []}]}
    van_ban, _ = _sach([muc], nguon=NGUON_LETTERHEAD_2_DOAN, goi=GOI_LETTERHEAD_2_DOAN)
    khoi = van_ban["muc"][0]["khoi"]
    assert len(khoi) == 1, "letterhead trở thành bảng, không còn là văn xuôi"
    assert khoi[0]["bang"] == [
        [
            "TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN",
            "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc",
        ]
    ]
    assert khoi[0]["ti_le"] == [45, 55]


def test_bang_cua_nhieu_dong_khong_khop_khi_thua_dong_hoac_thieu_o():
    """Round-3-style — khớp phải TRỌN VẸN cả hai phía: một khối thừa MỘT dòng
    ngoài đúng hai ô của bảng (không thể ghép hết vào hai ô) không được cứu,
    giữ nguyên văn xuôi."""
    khoi_du_dong = (
        "TRƯỜNG ĐẠI HỌC PHENIKAA\nTRƯỜNG CÔNG NGHỆ THÔNG TIN\n"
        "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc\nPhòng Đào tạo"
    )
    muc = {"ten": "Đầu trang", "vung": "than", "khoi": [{"noi_dung": khoi_du_dong, "bang": []}]}
    van_ban, _ = _sach(
        [muc], nguon=NGUON_LETTERHEAD_2_DOAN + "\nPhòng Đào tạo", goi=GOI_LETTERHEAD_2_DOAN
    )
    assert van_ban["muc"][0]["khoi"] == [
        {"noi_dung": khoi_du_dong, "bang": [], "can_le": "trai", "nhip": [], "ti_le": []}
    ]


def test_khop_bang_khong_dung_vao_bang_moi_mo_hinh_tu_soan():
    """Một bảng mô hình SOẠN MỚI (không có ô nào trong tài liệu nguồn) không
    khớp bảng thật nào → giữ NGUYÊN như mô hình viết — chức năng "soạn bảng
    mới" (không chỉ sao y bảng có sẵn) không bị mất vì phép khớp lại."""
    bang_moi = [["Hạng mục", "Số lượng"], ["Bàn ghế", "5 bộ"]]
    muc = {"ten": "Thiết bị bàn giao", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_moi}]}
    van_ban, _ = _sach(
        [muc], nguon="Hạng mục Số lượng Bàn ghế 5 bộ", goi=GOI_BANG_DIEM
    )
    assert van_ban["muc"][0]["khoi"][0]["bang"] == bang_moi


# ────────────── Phase 11 fix round 2 — bảng TRẮNG (hàng để trống cho tay viết)
#
# BM.M05 thật: bảng "DANH SÁCH SINH VIÊN/HỌC VIÊN" có 1 hàng tiêu đề (6 cột)
# cộng 4 hàng TRẮNG (mọi ô rỗng chữ) — 5 hàng nguồn. Trước bản vá round 2,
# `doc_tai_lieu` bỏ qua Ô rỗng chữ như một đoạn văn rỗng, nên `don_vi` không
# còn dấu vết 4 hàng trắng tồn tại, và `_bang_theo_nhan` dựng lại đúng 1 hàng.

DV_DANH_SACH = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="STT", bang=(0, 0, 0)),
    DonViVanBan(chi_so=1, trang=1, offset_dau=5, noi_dung="Lớp quản lý", bang=(0, 0, 1)),
    DonViVanBan(chi_so=2, trang=1, offset_dau=20, noi_dung="Mã sinh viên/ học viên", bang=(0, 0, 2)),
    DonViVanBan(chi_so=3, trang=1, offset_dau=45, noi_dung="Họ và tên", bang=(0, 0, 3)),
    DonViVanBan(chi_so=4, trang=1, offset_dau=58, noi_dung="Ngày sinh", bang=(0, 0, 4)),
    DonViVanBan(chi_so=5, trang=1, offset_dau=70, noi_dung="Ghi chú", bang=(0, 0, 5)),
    # 4 hàng trắng — MỖI ô một đơn vị rỗng chữ riêng (Phase 11 fix round 2),
    # không phải một hàng bị bỏ qua hoàn toàn.
    *(
        DonViVanBan(chi_so=6 + h * 6 + c, trang=1, offset_dau=80 + h * 10 + c, noi_dung="", bang=(0, h, c))
        for h in range(1, 5)
        for c in range(6)
    ),
]
GOI_DANH_SACH = [
    {"id": "w", "ten_tep": "bm05.docx", "don_vi": DV_DANH_SACH, "nhan": "A", "gui": DV_DANH_SACH}
]
NGUON_DANH_SACH = "\n".join(dv.noi_dung for dv in DV_DANH_SACH if dv.noi_dung)


def test_bang_theo_nhan_giu_du_hang_trang_khong_chi_hang_tieu_de():
    """`_bang_theo_nhan` phải dựng lại ĐỦ 5 hàng (1 tiêu đề + 4 trắng), không
    chỉ hàng có chữ — mỗi hàng trắng vẫn đủ 6 ô rỗng riêng, không gộp thành
    một ô trống duy nhất (khác ca "hàng ngắn hơn tiêu đề" của R6: ở đây MỌI
    cột đều có ô thật, chỉ là rỗng chữ)."""
    ra = h._bang_theo_nhan(GOI_DANH_SACH)
    tbl = ra["A0"]
    assert len(tbl["hang"]) == 5, "1 hàng tiêu đề + 4 hàng trắng, không bị rút xuống 1"
    for hang_trang in tbl["hang"][1:]:
        assert hang_trang == ["", "", "", "", "", ""], "mỗi hàng trắng đủ 6 ô rỗng riêng"
    assert tbl["nhip"][1] == [1, 1, 1, 1, 1, 1]


def test_khop_bang_cuu_bang_danh_sach_giu_hang_trang():
    """Qua ĐỦ `_khop_bang`: mô hình chỉ viết hàng tiêu đề (đúng chế độ hỏng đo
    được thật, model không tự biết có 4 hàng trắng phía sau) — khớp lại vẫn
    phải trả về ĐỦ 5 hàng của bảng thật, không dừng ở hàng tiêu đề mô hình đã
    viết."""
    muc = {
        "ten": "Bảng danh sách sinh viên/học viên",
        "vung": "than",
        "khoi": [
            {
                "noi_dung": "",
                "bang": [["STT", "Lớp quản lý", "Mã sinh viên/ học viên", "Họ và tên", "Ngày sinh", "Ghi chú"]],
            }
        ],
    }
    van_ban, _ = _sach([muc], nguon=NGUON_DANH_SACH, goi=GOI_DANH_SACH)
    bang = van_ban["muc"][0]["khoi"][0]["bang"]
    assert len(bang) == 5, "bảng khớp lại phải giữ đủ 4 hàng trắng nguồn khai báo"
    assert bang[1:] == [["", "", "", "", "", ""]] * 4


# ───────────── Phase 9 U2 — giá trị Ô TRÙNG LẶP trong CÙNG một bảng thật
#
# `.sdd/phase-9-brief.md` U2 — đo TRỰC TIẾP trên bảng thật của BM.ĐT.18.11
# (`psql` chính draft `30e8cdb9…` nêu trong brief): 4 tiêu chí, cột "Điểm tối
# đa" lặp "2,0" BA lần (chỉ tiêu chí 4 là "4,0"). `_bang_cua` bản trước round
# 3 đòi khớp ĐÚNG MỘT Ô trên toàn tài liệu — "2,0" khớp ba ô CÙNG một bảng thì
# `len(khop) == 3`, hàm trả `None`, `_bang_khop_het` thấy một "ô không khớp
# được" dù nó khớp thật ba lần, và cả khối bị bỏ qua: hàng "Tổng" đệm dư
# `["Tổng","10","",""]` không được cứu — ĐÚNG NHƯ QUAN SÁT trên form thật.

DV_BANG_DIEM_THAT = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="TT", bang=(0, 0, 0)),
    DonViVanBan(chi_so=1, trang=1, offset_dau=3, noi_dung="Tiêu chí đánh giá", bang=(0, 0, 1)),
    DonViVanBan(chi_so=2, trang=1, offset_dau=25, noi_dung="Điểm tối đa", bang=(0, 0, 2)),
    DonViVanBan(chi_so=3, trang=1, offset_dau=40, noi_dung="Điểm đánh giá", bang=(0, 0, 3)),
    DonViVanBan(chi_so=4, trang=1, offset_dau=55, noi_dung="1", bang=(0, 1, 0)),
    DonViVanBan(
        chi_so=5, trang=1, offset_dau=57,
        noi_dung="Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập", bang=(0, 1, 1),
    ),
    DonViVanBan(chi_so=6, trang=1, offset_dau=120, noi_dung="2,0", bang=(0, 1, 2)),
    DonViVanBan(chi_so=7, trang=1, offset_dau=124, noi_dung="2", bang=(0, 2, 0)),
    DonViVanBan(
        chi_so=8, trang=1, offset_dau=126,
        noi_dung="Tinh thần trách nhiệm, thái độ đối với công việc", bang=(0, 2, 1),
    ),
    DonViVanBan(chi_so=9, trang=1, offset_dau=180, noi_dung="2,0", bang=(0, 2, 2)),
    DonViVanBan(chi_so=10, trang=1, offset_dau=184, noi_dung="3", bang=(0, 3, 0)),
    DonViVanBan(
        chi_so=11, trang=1, offset_dau=186,
        noi_dung="Khả năng vận dụng kiến thức chuyên môn đã học vào thực tiễn", bang=(0, 3, 1),
    ),
    DonViVanBan(chi_so=12, trang=1, offset_dau=250, noi_dung="2,0", bang=(0, 3, 2)),
    DonViVanBan(chi_so=13, trang=1, offset_dau=254, noi_dung="4", bang=(0, 4, 0)),
    DonViVanBan(
        chi_so=14, trang=1, offset_dau=256,
        noi_dung="Kết quả hoàn thành thực tập  theo đề cương chi tiết", bang=(0, 4, 1),
    ),
    DonViVanBan(chi_so=15, trang=1, offset_dau=310, noi_dung="4,0", bang=(0, 4, 2)),
    # "Tổng" gộp thật 2 cột lưới (TT + Tiêu chí, `w:gridSpan="2"` đo trên tệp
    # thật, Phase 11 R6); "10" đứng ở cột lưới THẬT (2, "Điểm tối đa").
    DonViVanBan(chi_so=16, trang=1, offset_dau=314, noi_dung="Tổng", bang=(0, 5, 0), bang_nhip=2),
    DonViVanBan(chi_so=17, trang=1, offset_dau=319, noi_dung="10", bang=(0, 5, 2)),
]
GOI_BANG_DIEM_THAT = [
    {"id": "y2", "ten_tep": "dt1811.docx", "don_vi": DV_BANG_DIEM_THAT, "nhan": "A", "gui": DV_BANG_DIEM_THAT}
]
NGUON_BANG_DIEM_THAT = "\n".join(dv.noi_dung for dv in DV_BANG_DIEM_THAT)


def test_khop_bang_cuu_hang_gop_khi_gia_tri_trung_lap_trong_cung_bang():
    """Phase 9 U2 — mô phỏng ĐÚNG hàng "Tổng" đệm dư quan sát được trên
    BM.ĐT.18.11 THẬT (draft `30e8cdb9…`), với ĐỦ 4 tiêu chí (cột "Điểm tối đa"
    lặp "2,0" ba lần) thay vì fixture rút gọn một hàng cũ. Trước bản vá round
    3+ này, `_bang_cua` coi "2,0" khớp BA ô là nhập nhằng (dù cả ba đều CÙNG
    một bảng A0) nên khối này không được cứu — TÁI HIỆN đúng lỗi brief mô tả.
    Sau bản vá, `_bang_cua` gộp theo KHOÁ BẢNG trước khi đếm, nên ba lần khớp
    cùng bảng A0 vẫn ra MỘT khoá và khối được thay bằng bảng thật, "Tổng" trở
    lại đúng 2 ô — "10" nằm dưới "Điểm tối đa", không phải dưới "Tiêu chí"."""
    bang_dem = [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập", "2,0", ""],
        ["2", "Tinh thần trách nhiệm, thái độ đối với công việc", "2,0", ""],
        ["3", "Khả năng vận dụng kiến thức chuyên môn đã học vào thực tiễn", "2,0", ""],
        ["4", "Kết quả hoàn thành thực tập  theo đề cương chi tiết", "4,0", ""],
        ["Tổng", "10", "", ""],
    ]
    muc = {"ten": "Bảng đánh giá", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_dem}]}
    van_ban, _ = _sach([muc], nguon=NGUON_BANG_DIEM_THAT, goi=GOI_BANG_DIEM_THAT)
    bang_ra = van_ban["muc"][0]["khoi"][0]["bang"]
    # Hàng gộp trở lại đúng NHỊP thật: "Tổng" chiếm 2 cột, "10" 1 cột, cộng một
    # ô đệm rỗng lấp cột lưới còn lại (Phase 11 R6) — không còn đệm sai kiểu
    # mô hình đã viết (`["Tổng","10","",""]`, "10" trôi sang cột "Tiêu chí").
    assert bang_ra[-1] == ["Tổng", "10", ""], "hàng gộp trở lại đúng nhịp, không còn đệm sai cột"
    assert bang_ra[0][2] == "Điểm tối đa" and bang_ra[-1][1] == "10", '"10" nằm dưới đúng cột "Điểm tối đa"'


def test_khop_bang_gia_tri_trung_lap_khong_du_de_ghi_de_khi_con_o_moi():
    """Phase 9 U2 [giữ luật round 3] — bảng có NHIỀU ô trùng "2,0" với nguồn
    (nên mỗi ô riêng lẻ khớp NHẬP NHẰNG ba lần) NHƯNG cũng có một ô THẬT SỰ
    MỚI, không có trong tài liệu ("Nhận xét thêm") — phép gộp-theo-khoá-bảng
    (sửa cho ca trên) không được biến điều này thành "mọi ô đều khớp": khối
    này vẫn phải bị BỎ QUA (giữ nguyên như mô hình viết), vì luật round 3 vẫn
    đòi MỌI ô khác rỗng khớp được, và "Nhận xét thêm" thì không khớp gì cả."""
    bang_sua = [
        ["Điểm tối đa", "2,0", "2,0", "2,0"],
        ["Nhận xét thêm", "", "", ""],
    ]
    muc = {"ten": "Bảng đánh giá", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_sua}]}
    van_ban, _ = _sach([muc], nguon=NGUON_BANG_DIEM_THAT, goi=GOI_BANG_DIEM_THAT)
    assert van_ban["muc"][0]["khoi"][0]["bang"] == bang_sua, "một ô mới không khớp gì thì chặn cả khối, không ghi đè"


# BM.ĐT.18.11 THẬT có bảng ký cạnh bảng điểm — hai bảng thật trong CÙNG tài
# liệu, khoá theo review task quality [Medium]: chưa fixture nào của file
# này dùng `bang=(1, …)`, nên tính chất "khớp ở HAI bảng khác nhau vẫn chặn"
# (khác "khớp NHIỀU ô CÙNG một bảng thì gộp lại") chỉ được xác nhận bằng suy
# luận tay, chưa có test khoá.
DV_HAI_BANG_THAT = DV_BANG_DIEM_THAT + [
    DonViVanBan(chi_so=18, trang=1, offset_dau=400, noi_dung="GV HƯỚNG DẪN (Ký, ghi rõ họ tên)", bang=(1, 0, 0)),
    DonViVanBan(chi_so=19, trang=1, offset_dau=440, noi_dung="ĐẠI DIỆN CƠ SỞ (Ký, ghi rõ họ tên)", bang=(1, 0, 1)),
    # Giá trị "2,0" LẶP LẠI ở bảng KHÁC (bảng 1) — không phải lặp trong CÙNG
    # một bảng như `DV_BANG_DIEM_THAT` đã có (ca đó gộp về MỘT khoá bảng,
    # được cứu). Ở đây "2,0" phải trỏ tới HAI khoá bảng khác nhau (A0 và A1)
    # → nhập nhằng THẬT, `_bang_cua` phải trả `None`.
    DonViVanBan(chi_so=20, trang=1, offset_dau=480, noi_dung="2,0", bang=(1, 1, 0)),
]
GOI_HAI_BANG_THAT = [
    {"id": "y3", "ten_tep": "dt1811.docx", "don_vi": DV_HAI_BANG_THAT, "nhan": "A", "gui": DV_HAI_BANG_THAT}
]
NGUON_HAI_BANG_THAT = "\n".join(dv.noi_dung for dv in DV_HAI_BANG_THAT)


def test_khop_bang_khop_hai_bang_khac_nhau_van_chan_khong_ghi_de():
    """Phase 9 U2 [reviewer Medium] — "2,0" (bảng điểm A0) và "10" (cũng bảng
    điểm A0) không phải ca này chứng minh; ca này cần một GIÁ TRỊ khớp cùng
    lúc ở HAI BẢNG THẬT KHÁC NHAU của cùng tài liệu ("GV HƯỚNG DẪN..." chỉ có
    trong bảng ký A1, không có trong bảng điểm A0 — không đại diện được). Mô
    phỏng bằng một mảng ô do mô hình VIẾT LẠI chỉ gồm giá trị "1" — "1" có mặt
    ở CẢ bảng điểm (hàng đầu, cột TT) LẪN không có trong bảng ký, nên tự nó
    không đủ; thay bằng giá trị THẬT sự trùng cả hai bảng — "GV HƯỚNG DẪN
    (Ký, ghi rõ họ tên)" chỉ ở A1, nên đổi chiến lược: bảng mô hình viết dùng
    "Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập" (chỉ A0) TRỘN với
    "GV HƯỚNG DẪN (Ký, ghi rõ họ tên)" (chỉ A1) trong CÙNG một khối — hai ô
    khớp hai bảng KHÁC NHAU, nên khối phải bị chặn (giữ nguyên), không được
    ghép nhầm vào bảng nào."""
    bang_hai_nguon = [
        ["Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập", "GV HƯỚNG DẪN (Ký, ghi rõ họ tên)"],
    ]
    muc = {"ten": "Ghi chú trộn", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_hai_nguon}]}
    van_ban, _ = _sach([muc], nguon=NGUON_HAI_BANG_THAT, goi=GOI_HAI_BANG_THAT)
    assert van_ban["muc"][0]["khoi"][0]["bang"] == bang_hai_nguon, (
        "hai ô khớp hai bảng KHÁC NHAU vẫn phải chặn — không gộp nhầm vào bảng nào"
    )


def test_bang_cua_mot_gia_tri_khop_hai_bang_khac_nhau_van_nhap_nhang():
    """Phase 9 U2 [reviewer Medium, sát cơ chế nhất] — ĐÚNG MỘT giá trị
    ("2,0") xuất hiện ở CẢ bảng điểm (A0, lặp trong-cùng-bảng, đã gộp về một
    khoá — xem test cứu hàng gộp phía trên) LẪN bảng ký (A1, một ô ĐỘC LẬP
    của bảng khác). Khác ca "lặp trong cùng một bảng", ca này phải KHÔNG gộp
    được: `_bang_cua("2,0")` phải trả về khoá bảng ứng với tập {A0, A1} có
    2 phần tử → `None`, đúng "khớp ở hai bảng khác nhau thì vẫn nhập nhằng"
    mà việc gộp-theo-khoá-bảng (sửa U2) không được xoá mất."""
    bang_chi_gia_tri_trung = [["2,0"]]
    muc = {"ten": "Ghi chú", "vung": "than", "khoi": [{"noi_dung": "", "bang": bang_chi_gia_tri_trung}]}
    van_ban, _ = _sach([muc], nguon=NGUON_HAI_BANG_THAT, goi=GOI_HAI_BANG_THAT)
    assert van_ban["muc"][0]["khoi"][0]["bang"] == bang_chi_gia_tri_trung, (
        '"2,0" khớp hai bảng khác nhau (A0, A1) vẫn phải nhập nhằng, không được cứu vào bảng nào'
    )


# ──────────────────────────── Phase 9 U1 — tên mục KLAW bịa không được in ra


def test_ten_muc_khong_co_trong_nguon_bi_danh_dau_khong_that():
    """Phase 9 U1 — mô hình đặt tên mục để TỔ CHỨC bản thảo ("Chữ ký") nhưng
    chữ đó không nằm ở đâu trong tài liệu nguồn (đo trên BM.ĐT.18.11 thật:
    không đơn vị nào của form này có nội dung đúng "Chữ ký") → `ten_that`
    phải là `False`, để giao diện không in nhãn này ra trang."""
    muc = {"ten": "Chữ ký", "vung": "than", "khoi": [{"noi_dung": "", "bang": [["GV HƯỚNG DẪN"]]}]}
    van_ban, _ = _sach([muc], nguon="GV HƯỚNG DẪN", goi=GOI_BANG_DIEM_THAT)
    assert van_ban["muc"][0]["ten_that"] is False


def test_ten_muc_la_tieu_de_that_trong_nguon_duoc_danh_dau_that():
    """Phase 9 U1 — ngược lại: một tên mục TRÙNG NGUYÊN VĂN một đơn vị thật
    của tài liệu (một tiêu đề THẬT, ví dụ "Bảng đánh giá" khi form đó có đúng
    dòng này) phải được đánh dấu `ten_that = True`, để giao diện KHÔNG ẩn oan
    một tiêu đề có thật — đây là nửa còn lại brief đòi, chống việc chặn quá tay
    bằng danh sách từ khoá."""
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Bảng đánh giá"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=20, noi_dung="Tiêu chí đánh giá", bang=(0, 0, 0)),
    ]
    goi = [{"id": "z2", "ten_tep": "x.docx", "don_vi": dv, "nhan": "A", "gui": dv}]
    muc = {"ten": "Bảng đánh giá", "vung": "than", "khoi": [{"noi_dung": "", "bang": [["Tiêu chí đánh giá"]]}]}
    van_ban, _ = _sach([muc], nguon="Bảng đánh giá Tiêu chí đánh giá", goi=goi)
    assert van_ban["muc"][0]["ten_that"] is True


def test_ten_muc_that_viet_khac_hoa_thuong_van_duoc_danh_dau_that():
    """Phase 9 U1 fix round 1 [reviewer Important] — ca Ở GIỮA hai test trên,
    trước bản vá này chưa có gì khoá: một tiêu đề THẬT trong nguồn viết hoa
    toàn bộ ("PHIẾU ĐÁNH GIÁ..."), như các biểu mẫu thường làm, nhưng mô hình
    tái hiện tên mục theo lối chữ hoa/thường thường ("Phiếu đánh giá...") —
    một thói quen bình thường của LLM, không phải một chữ bịa. `ten_that`
    phải vẫn là `True`: so khớp gập hoa/thường (`_khong_hoa`) mới đúng, so
    khớp nghiêm như `normalize()` gốc (round 0) sẽ đánh dấu sai `False` và ẩn
    oan tiêu đề này — đúng lỗi brief cảnh báo ("không được xoá oan một tiêu
    đề thật")."""
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP TỐT NGHIỆP"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=50, noi_dung="Họ và tên sinh viên: …………"),
    ]
    goi = [{"id": "z3", "ten_tep": "x.docx", "don_vi": dv, "nhan": "A", "gui": dv}]
    muc = {
        "ten": "Phiếu đánh giá quá trình thực tập tốt nghiệp",
        "vung": "than",
        "khoi": [{"noi_dung": "Họ và tên sinh viên: …………", "bang": []}],
    }
    van_ban, _ = _sach(
        [muc], nguon="PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP TỐT NGHIỆP Họ và tên sinh viên: …………", goi=goi
    )
    assert van_ban["muc"][0]["ten_that"] is True


# ──────── Phase 11 fix round 2 — tên mục THẬT không được lặp lại làm thân bài
#
# Đo thật trên BM.M05 (draft `66ee94f8…`): mục "Xác nhận của Cơ quan/Đơn vị"
# có `ten_that=True` (tên khớp một đoạn thật của nguồn) — ĐÚNG, không phải
# lỗi U1 — nhưng khối văn xuôi đầu tiên của chính mục đó LẶP LẠI dòng đó rồi
# mới tới "(Ký và ghi rõ họ tên, chức vụ, đóng dấu)". Trang in tiêu đề mục
# RỒI thân bài, nên câu đó xuất hiện HAI LẦN.


def test_ten_muc_that_trung_dong_dau_khoi_thi_bo_dong_do_giu_phan_con_lai():
    dv = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Xác nhận của Cơ quan/Đơn vị"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="(Ký và ghi rõ họ tên, chức vụ, đóng dấu)"),
    ]
    goi = [{"id": "z4", "ten_tep": "bm05.docx", "don_vi": dv, "nhan": "A", "gui": dv}]
    muc = {
        "ten": "Xác nhận của Cơ quan/Đơn vị",
        "vung": "than",
        "khoi": [
            {
                "noi_dung": "Xác nhận của Cơ quan/Đơn vị\n(Ký và ghi rõ họ tên, chức vụ, đóng dấu)",
                "bang": [],
            }
        ],
    }
    van_ban, _ = _sach(
        [muc],
        nguon="Xác nhận của Cơ quan/Đơn vị (Ký và ghi rõ họ tên, chức vụ, đóng dấu)",
        goi=goi,
    )
    ket = van_ban["muc"][0]
    assert ket["ten_that"] is True, "tên vẫn thật, vẫn in ra làm tiêu đề mục"
    assert ket["khoi"] == [
        {"noi_dung": "(Ký và ghi rõ họ tên, chức vụ, đóng dấu)", "bang": [], "can_le": "trai", "nhip": [], "ti_le": []}
    ], "dòng đầu (trùng tên) bị bỏ, phần còn lại của khối vẫn giữ nguyên"


def test_ten_muc_that_bang_dung_ca_khoi_thi_bo_ca_khoi_giu_muc():
    """Phase 11 fix round 3 (reviewer I3) — khối CHỈ có đúng dòng trùng tên
    (không còn gì khác): bỏ CẢ khối, nhưng MỤC vẫn còn với `khoi=[]` (không vô
    đề, vì `ten` đã in ra rồi). Trước bản vá này, khối rỗng đi lẫn với luật
    "mục không có khối nào" và bị bỏ CẢ MỤC — biến ca "in tên hai lần" (lỗi
    round 2 sửa) thành "in tên không lần nào", mất luôn cả tiêu đề."""
    dv = [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Xác nhận của Cơ quan/Đơn vị")]
    goi = [{"id": "z5", "ten_tep": "bm05.docx", "don_vi": dv, "nhan": "A", "gui": dv}]
    muc = {
        "ten": "Xác nhận của Cơ quan/Đơn vị",
        "vung": "than",
        "khoi": [{"noi_dung": "Xác nhận của Cơ quan/Đơn vị", "bang": []}],
    }
    van_ban, _ = _sach([muc], nguon="Xác nhận của Cơ quan/Đơn vị", goi=goi)
    assert len(van_ban["muc"]) == 1, "khối duy nhất bị bỏ hết vì trùng tên KHÔNG kéo theo mất cả mục"
    ket = van_ban["muc"][0]
    assert ket["ten_that"] is True
    assert ket["khoi"] == [], "không còn khối thân bài nào — tên đã in ra làm tiêu đề mục rồi"


def test_ten_muc_bia_trung_dong_dau_khoi_khong_bi_bo():
    """Đối chứng: một tên mục KLAW bịa (`ten_that=False`) không in ra trang,
    nên trùng chữ với dòng đầu nội dung không phải một sự lặp lại thật — giữ
    nguyên khối, không bỏ dòng nào."""
    muc = {
        "ten": "Xác nhận của Cơ quan/Đơn vị",
        "vung": "than",
        "khoi": [
            {
                "noi_dung": "Xác nhận của Cơ quan/Đơn vị\n(Ký và ghi rõ họ tên, chức vụ, đóng dấu)",
                "bang": [],
            }
        ],
    }
    van_ban, _ = _sach(
        [muc], nguon="Xác nhận của Cơ quan/Đơn vị (Ký và ghi rõ họ tên, chức vụ, đóng dấu)", goi=GOI_BANG_DIEM
    )
    ket = van_ban["muc"][0]
    assert ket["ten_that"] is False
    assert ket["khoi"][0]["noi_dung"] == "Xác nhận của Cơ quan/Đơn vị\n(Ký và ghi rõ họ tên, chức vụ, đóng dấu)"


# ────────────── Phase 11 fix round 2 — tiêu đề đặt ĐÚNG vị trí nguồn, không
# phải luôn ở đầu trang
#
# Đo thật trên BM.M05 (draft `4722079d…`): nguồn có thứ tự "Mẫu QT.ĐT.28-M05"
# (chỉ số 0) → letterhead (chỉ số 1–3) → tiêu đề "GIẤY TIẾP NHẬN THỰC HÀNH/
# THỰC TẬP" (chỉ số 4) → phần còn lại. Mô hình không tự in tiêu đề ra thân
# bài (nó chỉ sống trong `tieu_de`) — `<h1>` cũ luôn vẽ Ở ĐẦU nên trang hiện
# tiêu đề TRƯỚC letterhead, sai thứ tự nguồn.

DV_THU_TU = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Mẫu QT.ĐT.28-M05"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=20, noi_dung="Tên chủ quản", bang=(0, 0, 0)),
    DonViVanBan(chi_so=2, trang=1, offset_dau=40, noi_dung="Quốc hiệu", bang=(0, 0, 1)),
    DonViVanBan(
        chi_so=3, trang=1, offset_dau=60, noi_dung="GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP", can_le="giua",
    ),
    DonViVanBan(chi_so=4, trang=1, offset_dau=110, noi_dung="Cơ quan/Đơn vị tiếp nhận: ………"),
]
GOI_THU_TU = [{"id": "y", "ten_tep": "bm05.docx", "don_vi": DV_THU_TU, "nhan": "A", "gui": DV_THU_TU}]
NGUON_THU_TU = "\n".join(dv.noi_dung for dv in DV_THU_TU)


def test_tieu_de_chen_dung_vi_tri_nguon_khong_luon_o_dau():
    van_ban = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {"ten": "Tiêu đề biểu mẫu", "vung": "than", "khoi": [{"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []}]},
            {
                "ten": "Quốc hiệu và tiêu ngữ",
                "vung": "than",
                "khoi": [{"noi_dung": "", "bang": [["Tên chủ quản", "Quốc hiệu"]]}],
            },
            {
                "ten": "Thông tin chi tiết",
                "vung": "than",
                "khoi": [{"noi_dung": "Cơ quan/Đơn vị tiếp nhận: ………", "bang": []}],
            },
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, NGUON_THU_TU, goi=GOI_THU_TU)
    ten_theo_thu_tu = [m["ten"] for m in ket["muc"]]
    assert ten_theo_thu_tu == [
        "Tiêu đề biểu mẫu",
        "Quốc hiệu và tiêu ngữ",
        "Tiêu đề văn bản",
        "Thông tin chi tiết",
    ], "tiêu đề chen ĐÚNG giữa letterhead và mục kế tiếp, không nhảy lên đầu"
    muc_tieu_de = ket["muc"][2]
    assert muc_tieu_de["ten_that"] is False, "tên tổ chức nội bộ, không phải chữ thật — không in ra làm tiêu đề mục"
    assert muc_tieu_de["khoi"] == [
        {
            "noi_dung": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
            "bang": [],
            "can_le": "giua",
            "nhip": [],
            "ti_le": [],
        }
    ]


def test_tieu_de_da_co_trong_than_bai_thi_khong_chen_them():
    """Ca R4 gốc (BM.ĐT.18.05-style): tiêu đề ĐÃ được mô hình in ra như một
    dòng thân bài (chung khối với quốc hiệu) — không chèn thêm một bản sao
    thứ hai, `<h1>` phía render cũng đã tự ẩn đi (thấy trong thân bài rồi)."""
    van_ban = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {
                "ten": "Quốc hiệu và tiêu ngữ",
                "vung": "than",
                "khoi": [{"noi_dung": "Tên chủ quản\nGIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP", "bang": []}],
            },
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, NGUON_THU_TU, goi=GOI_THU_TU)
    assert len(ket["muc"]) == 1, "không chèn mục nào thêm — tiêu đề đã có trong thân bài"


def test_tieu_de_khong_dinh_vi_duoc_thi_khong_chen():
    """Tiêu đề không khớp CHỮ THẬT nào của nguồn (mô hình soạn/paraphrase) —
    không có vị trí nguồn nào để dùng, không chèn gì (giữ nguyên hành vi cũ,
    `<h1>` phía render lo phần hiện tiêu đề)."""
    van_ban = {
        "tieu_de": "Một tiêu đề mô hình tự bịa, không có trong nguồn",
        "muc": [
            {"ten": "Tiêu đề biểu mẫu", "vung": "than", "khoi": [{"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []}]},
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, NGUON_THU_TU, goi=GOI_THU_TU)
    assert len(ket["muc"]) == 1, "không định vị được thì không chèn mục nào"


def test_tieu_de_khong_muc_nao_dinh_vi_duoc_thi_khong_chen_cuoi():
    """Phase 11 fix round 3 (reviewer I1) — tiêu đề khớp được vị trí nguồn,
    nhưng KHÔNG mục nào của bản thảo định vị được (mọi mục bị mô hình
    paraphrase hết, không còn khớp NGUYÊN VĂN dòng nguồn nào). Trước bản vá
    này, `idx` mặc định về CUỐI danh sách mục và không có mục nào đủ bằng
    chứng để dời nó lên — tiêu đề bị cắm xuống DƯỚI CÙNG trang dù nguồn thật
    đặt nó ở đầu (chỉ số 3), tệ hơn cả hành vi trước khi có khối chèn này
    (R4 đã ẩn `<h1>` đi vì tiêu đề giờ trùng chữ với thân bài). Không định vị
    được mục nào thì bỏ qua chèn, để `<h1>` phía render lo như cũ."""
    van_ban = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {
                "ten": "Phần một",
                "vung": "than",
                "khoi": [{"noi_dung": "Nội dung đã được diễn giải lại theo lời mô hình", "bang": []}],
            },
            {
                "ten": "Phần hai",
                "vung": "than",
                "khoi": [{"noi_dung": "Một đoạn khác cũng bị viết lại, không khớp nguyên văn", "bang": []}],
            },
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, NGUON_THU_TU, goi=GOI_THU_TU)
    assert len(ket["muc"]) == 2, "không mục nào định vị được nguồn → không chèn tiêu đề vào đâu cả"
    assert [m["ten"] for m in ket["muc"]] == ["Phần một", "Phần hai"]


DV_TIEU_DE_TRONG_BANG = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP", bang=(0, 0, 0)),
    DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="Cơ quan/Đơn vị tiếp nhận: ………"),
]
GOI_TIEU_DE_TRONG_BANG = [
    {"id": "y2", "ten_tep": "bm05.docx", "don_vi": DV_TIEU_DE_TRONG_BANG, "nhan": "A", "gui": DV_TIEU_DE_TRONG_BANG}
]
NGUON_TIEU_DE_TRONG_BANG = "\n".join(dv.noi_dung for dv in DV_TIEU_DE_TRONG_BANG)


def test_tieu_de_da_co_trong_o_bang_thi_khong_chen_them():
    """Phase 11 fix round 3 (reviewer I2) — tiêu đề sống NGAY trong một ô
    bảng (letterhead in tên biểu mẫu trong ô của nó, hình dạng thật gặp ở
    form tiếng Việt) mà mô hình đã tái hiện ĐÚNG như bảng. `da_co` trước bản
    vá này chỉ quét đoạn văn xuôi (`if not k["bang"]`) nên không thấy tiêu đề
    đã có, và chèn thêm một bản sao thứ hai dạng đoạn văn xuôi rời. Sau bản
    vá, quét cả ô bảng thì thấy "đã có", không chèn gì thêm."""
    van_ban = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {
                "ten": "Letterhead",
                "vung": "than",
                "khoi": [{"noi_dung": "", "bang": [["GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP"]]}],
            },
            {
                "ten": "Thông tin",
                "vung": "than",
                "khoi": [{"noi_dung": "Cơ quan/Đơn vị tiếp nhận: ………", "bang": []}],
            },
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, NGUON_TIEU_DE_TRONG_BANG, goi=GOI_TIEU_DE_TRONG_BANG)
    assert len(ket["muc"]) == 2, "tiêu đề đã có trong ô bảng — không chèn thêm mục nào"
    assert [m["ten"] for m in ket["muc"]] == ["Letterhead", "Thông tin"]


# ─────────── Phase 11 fix round 3 — thứ tự nguồn ghim trên chính FILE THẬT,
# không chỉ trên `don_vi` tự tay soạn (review task quality [Minor M4/proof
# gap]: ba test thứ tự ở trên đưa `don_vi` ĐÃ sắp đúng thứ tự assertion cần,
# không gì ghim thứ tự sản ra từ chính tệp thật). Đọc BM.M05 bằng
# `doc_tai_lieu.doc()` (0 token, không cần mô hình) và dựng một `van_ban` mô
# phỏng đúng cách mô hình vẫn xử lý form này (letterhead gộp vào MỘT khối
# bảng, tiêu đề KHÔNG tự in ra thân bài) — bỏ qua an toàn khi kho mẫu ngoài
# repo không có trên máy đang chạy, cùng quy ước `test_doc_tai_lieu.py`.

_KHO_MAU = Path.home() / "giấy tờ thực tập"
_BM_M05 = _KHO_MAU / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"


@pytest.mark.skipif(not _KHO_MAU.is_dir(), reason="kho mẫu ngoài repo không có trên máy này")
def test_tieu_de_dung_vi_tri_tren_file_BM_M05_that():
    if not _BM_M05.exists():
        pytest.skip("không thấy BM.M05 trong kho mẫu")
    t = doc(_BM_M05.name, _BM_M05.read_bytes())
    goi = [{"id": "bm05", "ten_tep": _BM_M05.name, "don_vi": t.don_vi, "nhan": "A", "gui": t.don_vi}]
    nguon = "\n".join(dv.noi_dung for dv in t.don_vi if dv.noi_dung)
    van_ban = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {"ten": "Tiêu đề biểu mẫu", "vung": "than", "khoi": [{"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []}]},
            {
                "ten": "Quốc hiệu và tiêu ngữ",
                "vung": "than",
                "khoi": [{
                    "noi_dung": "",
                    "bang": [
                        [
                            "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                            "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                        ],
                        ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
                    ],
                }],
            },
            {
                "ten": "Thông tin tiếp nhận",
                "vung": "than",
                "khoi": [{
                    "noi_dung": "Cơ quan/Đơn vị tiếp nhận: ……………………………………………………………….",
                    "bang": [],
                }],
            },
        ],
    }
    ket, _ = h.lam_sach_van_ban(van_ban, nguon, goi=goi)
    assert [m["ten"] for m in ket["muc"]] == [
        "Tiêu đề biểu mẫu",
        "Quốc hiệu và tiêu ngữ",
        "Tiêu đề văn bản",
        "Thông tin tiếp nhận",
    ], "trên file BM.M05 thật, tiêu đề chen giữa letterhead và mục kế tiếp — đúng thứ tự word/document.xml"


# ─────────────────────────────────────────── node hieu_tai_lieu phát `van_ban`


def test_schema_co_van_ban_va_hai_muc_dich_soan_lam_duoc():
    llm = _LLM(_ra())
    h.hieu_tai_lieu({"query": "soạn biên bản bàn giao từ nội dung này"}, TL, llm, "m")
    props = llm.json_schema["properties"]
    assert set(props["van_ban"]["properties"]) == {"tieu_de", "muc"}
    assert {"tao_van_ban", "sua_ban_thao"} <= h.MUC_DICH_LAM_DUOC


def test_schema_muc_them_khoi_giu_khoi_va_vung():
    """Phase 8 R1/R2 — một mục không còn `noi_dung`/`bang` cố định (Phase 7)
    mà là `khoi` (mảng khối theo thứ tự) và `vung` (đầu/chân/thân trang), cả
    hai `required` (strict `json_schema` không có trường tuỳ chọn)."""
    llm = _LLM(_ra())
    h.hieu_tai_lieu({"query": "soạn biên bản bàn giao"}, TL, llm, "m")
    muc_schema = llm.json_schema["properties"]["van_ban"]["properties"]["muc"]["items"]
    assert set(muc_schema["properties"]) == {"ten", "vung", "khoi"}
    assert set(muc_schema["required"]) == {"ten", "vung", "khoi"}
    assert muc_schema["properties"]["vung"] == {
        "type": "string",
        "enum": ["than", "dau_trang", "chan_trang"],
    }
    khoi_schema = muc_schema["properties"]["khoi"]["items"]
    assert set(khoi_schema["properties"]) == {"noi_dung", "bang"}
    assert set(khoi_schema["required"]) == {"noi_dung", "bang"}
    assert khoi_schema["properties"]["bang"] == {
        "type": "array",
        "items": {"type": "array", "items": {"type": "string"}},
    }


def test_node_phat_van_ban_tong_quat_khi_muc_dich_la_tao_van_ban():
    ra = h.hieu_tai_lieu({"query": "soạn biên bản bàn giao"}, TL, _LLM(_ra()), "m")
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert ra["van_ban_tong_quat"]["tieu_de"] == "BIÊN BẢN BÀN GIAO THIẾT BỊ"
    assert [m["ten"] for m in ra["van_ban_tong_quat"]["muc"]] == ["Thời gian bàn giao", "Giá trị"]
    assert ra["traces"]["dung_ban_thao_so_muc"] == 2


def test_node_khong_phat_van_ban_khi_muc_dich_khac():
    ra = h.hieu_tai_lieu({"query": "phiếu này nói gì"}, TL, _LLM(_ra(muc_dich="hoi")), "m")
    assert ra["van_ban_tong_quat"] is None


def test_node_lam_sach_gia_tri_bia_truoc_khi_ra_khoi_file():
    bia = {"tieu_de": "X", "muc": [_muc("Giá trị", "Trị giá 77.000.000 đồng.")]}
    ra = h.hieu_tai_lieu({"query": "soạn biên bản"}, TL, _LLM(_ra(van_ban=bia)), "m")
    assert "77.000.000" not in ra["van_ban_tong_quat"]["muc"][0]["khoi"][0]["noi_dung"]
    assert ra["traces"]["dung_ban_thao_so_gia_tri_lam_sach"] == 1


def test_node_giu_bang_va_lam_sach_gia_tri_bia_trong_o():
    """Phase 8 R1 qua ĐỦ node `hieu_tai_lieu` (không chỉ `lam_sach_van_ban` đơn
    lẻ): một khối BẢNG sống sót nguyên `bang`, và một ô bịa bị thay như một
    `noi_dung` — "20.000.000" có trong `DV_A` (nguồn), "9.999.999" thì không."""
    bia = {
        "tieu_de": "X",
        "muc": [
            _muc(
                "Giá trị",
                bang=[
                    ["Hạng mục", "Giá trị"],
                    ["Thiết bị", "20.000.000 đồng"],
                    ["Phụ phí", "9.999.999 đồng"],
                ],
            )
        ],
    }
    ra = h.hieu_tai_lieu({"query": "soạn biên bản"}, TL, _LLM(_ra(van_ban=bia)), "m")
    bang = ra["van_ban_tong_quat"]["muc"][0]["khoi"][0]["bang"]
    assert bang[1] == ["Thiết bị", "20.000.000 đồng"]
    assert bang[2] == ["Phụ phí", "[…] đồng"]


TL_LETTERHEAD = [{"id": "z", "ten_tep": "bm05.docx", "don_vi": DV_LETTERHEAD}]


def test_node_khop_lai_letterhead_bi_mo_hinh_xe_thanh_van_xuoi():
    """Review round 2 [chứng cứ chính, qua ĐỦ node] — mô phỏng ĐÚNG chế độ
    hỏng đo được thật trên BM.M05: mô hình xé letterhead 2 cột thành BA khối
    văn xuôi riêng, bỏ sót một ô. Chạy qua CẢ `hieu_tai_lieu` (không chỉ
    `lam_sach_van_ban` đơn lẻ, xem `test_khop_bang_cuu_letterhead_bi_xe_thanh_van_xuoi`
    ở trên) phải khớp lại thành MỘT khối bảng hai cột — brief R2 đòi đúng chữ
    "phải trở lại thành cùng cách sắp xếp hai cột đó", không phải bốn dòng
    đứng riêng."""
    van_ban_xe = {
        "tieu_de": "GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
        "muc": [
            {
                "ten": "Đầu trang",
                "vung": "dau_trang",
                "khoi": [
                    {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []},
                    {
                        "noi_dung": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                        "bang": [],
                    },
                    {"noi_dung": "TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", "bang": []},
                ],
            }
        ],
    }
    ra = h.hieu_tai_lieu(
        {"query": "dựng lại nguyên văn biểu mẫu này"}, TL_LETTERHEAD, _LLM(_ra(van_ban=van_ban_xe)), "m"
    )
    khoi = ra["van_ban_tong_quat"]["muc"][0]["khoi"]
    assert khoi == [
        {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": [], "can_le": "trai", "nhip": [], "ti_le": []},
        {
            "noi_dung": "",
            "bang": [
                [
                    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                ],
                ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./….", ""],
            ],
            "nhip": [[1, 1], [1, 1]],
            "ti_le": [],
            "can_le": "trai",
        },
    ]


def test_loi_ha_tang_khong_de_lai_van_ban_bia():
    class _No:
        def chat(self, *a, **k):
            raise RuntimeError("502")

    ra = h.hieu_tai_lieu({"query": "soạn biên bản"}, TL, _No(), "m")
    assert ra["van_ban_tong_quat"] is None


# ───────────────────────────── Phase 16 R2/R3 — tài liệu dài chia nhiều lượt
#
# `.sdd/phase-16-brief.md` — một tài liệu ĐƠN đủ dài để một lượt trả lời có
# nguy cơ cắt giữa chừng (`finish_reason=length`, đo thật trên tài liệu chủ sở
# hữu) được chia thành nhiều lượt kế tiếp (`_hieu_theo_phan`), mỗi lượt dựng
# một phần `van_ban.muc` rồi ghép — thay vì một lượt duy nhất ôm cả tài liệu.

# 20 đơn vị × 1.000 ký tự = 20.000 > `NGUONG_PHAN_KY_TU` (15.000) — chia đúng
# HAI phần theo thuật toán cộng dồn của `_chia_theo_ky_tu`: phần 1 = 15 đơn vị
# đầu (cộng dồn đúng 15.000, đơn vị 16 sẽ vượt), phần 2 = 5 đơn vị còn lại.
DON_VI_LON = [
    DonViVanBan(chi_so=i, trang=1, offset_dau=i * 1000, noi_dung="a" * 1000) for i in range(20)
]
TL_LON = [{"id": "lon", "ten_tep": "van-ban-dai.docx", "don_vi": DON_VI_LON}]


def test_chia_theo_ky_tu_giu_thu_tu_va_tran_moi_phan():
    """Hàm THUẦN — chia đúng theo cộng dồn ký tự, giữ thứ tự `chi_so`."""
    phan = h._chia_theo_ky_tu(DON_VI_LON, ky_tu_moi_phan=h.NGUONG_PHAN_KY_TU)
    assert [len(p) for p in phan] == [15, 5]
    assert [d.chi_so for p in phan for d in p] == list(range(20)), "thứ tự tài liệu phải giữ nguyên"


def test_chia_theo_ky_tu_mot_don_vi_qua_dai_van_giu_rieng_khong_cat_giua():
    """Một đơn vị DÀI HƠN cả ngưỡng không bị cắt giữa — vẫn đứng một mình
    trong một phần riêng, đúng docstring."""
    dv = [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="a" * 20_000)]
    phan = h._chia_theo_ky_tu(dv, ky_tu_moi_phan=10_000)
    assert len(phan) == 1 and len(phan[0]) == 1


def test_tai_lieu_ngan_khong_chia_van_dung_MOT_lan_goi():
    """Tài liệu dưới ngưỡng đi ĐÚNG đường một lượt như trước bản vá — không đổi
    hành vi, không đổi chi phí cho trường hợp thường gặp (corpus mẫu)."""
    llm = _LLM(_ra())
    h.hieu_tai_lieu({"query": "soạn biên bản bàn giao"}, TL, llm, "m")
    assert llm.so_lan_goi == 1


def test_hai_tai_lieu_khong_chia_du_tong_ky_tu_vuot_nguong():
    """Từ HAI tài liệu trở lên (so sánh/đối chiếu) không chia — `_khop_bang`
    chỉ được chứng minh an toàn cho một tài liệu tại một thời điểm (brief:
    "không được để một bảng khớp với một tài liệu chưa đầy đủ"), nên lượt có
    từ hai tài liệu đi nguyên đường cũ dù TỔNG ký tự vượt ngưỡng chia phần.

    Mỗi tài liệu 9.000 ký tự (dưới `NGUONG_PHAN_KY_TU` MỘT MÌNH) — tổng 18.000
    vượt ngưỡng chia phần nhưng vẫn dưới trần chi phí đầu vào (25.000 ký tự,
    `tai_lieu.kiem_tran_chi_phi_tai_lieu`), để phép kiểm này KHÔNG trộn hai
    trần khác nhau vào một phép so."""
    don_vi_vua = DON_VI_LON[:9]  # 9 × 1.000 = 9.000 ký tự
    tl_hai = [
        {"id": "x1", "ten_tep": "a.docx", "don_vi": don_vi_vua},
        {"id": "x2", "ten_tep": "b.docx", "don_vi": don_vi_vua},
    ]
    llm = _LLM(_ra(muc_dich="so_sanh"))
    h.hieu_tai_lieu({"query": "so sánh hai tài liệu"}, tl_hai, llm, "m")
    assert llm.so_lan_goi == 1


def test_tai_lieu_dai_khong_xin_soan_chi_goi_MOT_lan():
    """`muc_dich` lượt đầu không thuộc `MUC_DICH_SOAN` ⇒ dừng ngay, không lãng
    phí thêm lượt gọi nào cho một tài liệu dài nhưng câu hỏi không xin dựng lại
    toàn văn."""
    llm = _LLM(_ra(muc_dich="hoi", van_ban={"tieu_de": "", "muc": []}))
    ra = h.hieu_tai_lieu({"query": "tài liệu này có mấy trang"}, TL_LON, llm, "m")
    assert llm.so_lan_goi == 1
    assert ra["van_ban_tong_quat"] is None


class _LLMTheoPhan:
    """Trả `van_ban.muc` KHÁC NHAU tuỳ lượt, đọc từ chính đoạn `phan_doan` mà
    `_hieu_theo_phan` chèn vào prompt — để phép kiểm ghép phân biệt được THỨ
    TỰ các phần, không chỉ đếm số lượt gọi."""

    def __init__(self) -> None:
        self.so_lan_goi = 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.so_lan_goi += 1
        noi_dung = messages[-1]["content"]
        if "phần 1/2" in noi_dung:
            muc_dich, muc = "tao_van_ban", [_muc("Phần đầu", "Nội dung mở đầu.")]
        else:
            assert "phần 2/2" in noi_dung, noi_dung
            assert "đã xác định là `tao_van_ban` ở phần trước" in noi_dung
            muc_dich, muc = "hoi", [_muc("Phần cuối", "Nội dung kết luận.")]  # bị bỏ qua, chỉ van_ban được ghép
        ra = _ra(muc_dich=muc_dich, van_ban={"tieu_de": "VĂN BẢN DÀI", "muc": muc})
        return json.dumps(ra, ensure_ascii=False), _Usage()


def test_tai_lieu_dai_chia_hai_luot_ghep_dung_thu_tu():
    """Chứng cứ chính Phase 16 R2: tài liệu 20.000 ký tự (vượt `NGUONG_PHAN_KY_TU`)
    chia đúng 2 lượt, `van_ban.muc` ghép ĐÚNG THỨ TỰ từ cả hai lượt — `tieu_de`
    và `muc_dich` lấy từ lượt ĐẦU, `muc_dich` giả của lượt hai ("hoi") KHÔNG
    làm đổi `muc_dich_tai_lieu` cuối cùng."""
    llm = _LLMTheoPhan()
    ra = h.hieu_tai_lieu({"query": "dựng lại nguyên văn biểu mẫu này"}, TL_LON, llm, "m")
    assert llm.so_lan_goi == 2
    assert ra["muc_dich_tai_lieu"] == "tao_van_ban"
    assert ra["van_ban_tong_quat"]["tieu_de"] == "VĂN BẢN DÀI"
    assert [m["ten"] for m in ra["van_ban_tong_quat"]["muc"]] == ["Phần đầu", "Phần cuối"]


class _LLMGioiHanKichThuoc:
    """Mô phỏng ĐÚNG chế độ hỏng đo được thật (Phase 16 R1, brief): một lượt
    cố dựng lại NHIỀU đơn vị hơn `ran_han` (đứng cho trần token ra thật của
    model) bị cắt giữa chừng — cùng lỗi `finish_reason=length` production đã
    đo hai lần liên tiếp trên MỘT tài liệu không chia lượt. Đếm số đơn vị bằng
    số lần `"[A-"` xuất hiện trong prompt — đúng nhãn `_khoi_tai_lieu` đánh số."""

    def __init__(self, ran_han: int, ra_thanh_cong: dict) -> None:
        self.ran_han, self.ra_thanh_cong, self.so_lan_goi = ran_han, ra_thanh_cong, 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.so_lan_goi += 1
        so_don_vi = messages[-1]["content"].count("[A-")
        if so_don_vi > self.ran_han:
            raise TruncatedOutputError(
                f"model m: JSON bị cắt giữa chừng (finish_reason=length) — {so_don_vi} đơn vị"
            )
        return json.dumps(self.ra_thanh_cong, ensure_ascii=False), _Usage()


def test_tai_lieu_dai_KHONG_chia_thi_cat_giua_chung_chia_roi_thi_qua():
    """Chứng cứ "reproduces this exact failure ... and passes after" (brief,
    Proof required): với TRẦN GIẢ LẬP 16 đơn vị/lượt, một lượt ÔM CẢ 20 đơn vị
    (đường CŨ, trước Phase 16 R2) vượt trần và bị cắt giữa chừng — ĐÚNG chế độ
    hỏng brief mô tả, tái hiện bằng `git stash` trên `hieu_tai_lieu.py`/
    `llm.py`: hàm `_hieu_theo_phan` không tồn tại nữa, `TruncatedOutputError`
    không import được, cùng lỗi thu thập test. Chia thành 2 lượt (15 + 5 đơn
    vị, cả hai ĐỀU dưới trần giả lập) thì mỗi lượt qua được — không sửa mock,
    chỉ sửa CÁCH `hieu_tai_lieu` gọi nó."""
    llm = _LLMGioiHanKichThuoc(ran_han=16, ra_thanh_cong=_ra())
    ra = h.hieu_tai_lieu({"query": "dựng lại nguyên văn biểu mẫu này"}, TL_LON, llm, "m")
    assert llm.so_lan_goi == 2
    assert ra["van_ban_tong_quat"] is not None
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] != h.KHONG_DUNG_LAI_DUOC.format(
        so_ky_tu=sum(d.noi_dung.__len__() for d in DON_VI_LON)
    )


def test_cat_giua_chung_du_da_chia_phan_tra_loi_KHONG_DUNG_LAI_DUOC():
    """Phase 16 R3 — đã chia lượt mà VẪN cắt cấu trúc (lượt đầu, trước khi có
    gì để ghép): thông điệp phải nói rõ độ dài đo được và KHÔNG lặp lại lời
    khuyên "tách nhỏ rồi gửi lại" của `QUA_DAI` (không dùng được cho một biểu
    mẫu người dùng không tự viết ra)."""

    class _LuonCat:
        def chat(self, *a, **k):
            raise TruncatedOutputError("model m: JSON bị cắt giữa chừng (finish_reason=length)")

    ra = h.hieu_tai_lieu({"query": "dựng lại nguyên văn biểu mẫu này"}, TL_LON, _LuonCat(), "m")
    so_ky_tu = sum(len(d.noi_dung) for d in DON_VI_LON)
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == h.KHONG_DUNG_LAI_DUOC.format(so_ky_tu=so_ky_tu)
    assert ra["traces"]["hieu_tai_lieu_nguon"] == "qua_dai_dau_ra"
    assert ra["van_ban_tong_quat"] is None
    assert "tách nhỏ" not in ra["tai_lieu_ket"]["tra_loi_ngan"], "không lặp lại lời khuyên sai chỗ của QUA_DAI"


def test_tai_lieu_ngan_cat_giua_chung_cung_tra_loi_KHONG_DUNG_LAI_DUOC():
    """Cùng thông điệp R3 áp dụng cho đường KHÔNG chia (tài liệu ngắn nhưng vẫn
    cắt cấu trúc) — một chỗ `except` DUY NHẤT phục vụ cả hai đường, không phải
    hai thông điệp khác nhau cho cùng một nguyên nhân."""

    class _LuonCat:
        def chat(self, *a, **k):
            raise TruncatedOutputError("model m: JSON bị cắt giữa chừng (finish_reason=length)")

    ra = h.hieu_tai_lieu({"query": "soạn biên bản bàn giao"}, TL, _LuonCat(), "m")
    so_ky_tu = sum(len(dv.noi_dung) for t in TL for dv in t["don_vi"])
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == h.KHONG_DUNG_LAI_DUOC.format(so_ky_tu=so_ky_tu)


# ──────────────────────────────────────────── hình dạng mục / markdown / audit


def test_clauses_danh_khoa_theo_thu_tu_doc():
    cl = d.clauses_tu(VAN_BAN)
    assert [c["key"] for c in cl] == ["muc_1", "muc_2"]
    assert cl[0]["ten"] == "Thời gian bàn giao"


def test_clauses_tu_giu_khoi_va_vung_mac_dinh_than():
    """Phase 8 R1/R2 — `khoi` và `vung` LUÔN có mặt trong `clauses`. Một `muc`
    KHÔNG mang hai khoá này (viết tay, tương đương một `van_ban` từ TRƯỚC bản
    vá này) vẫn ra một clause hợp lệ: `khoi` rỗng, `vung` mặc định `than`."""
    cl = d.clauses_tu(VAN_BAN)
    assert cl[0]["khoi"] == VAN_BAN["muc"][0]["khoi"]
    assert cl[0]["vung"] == "than"

    cl_thieu = d.clauses_tu({"tieu_de": "T", "muc": [{"ten": "Trống"}]})
    assert cl_thieu[0]["khoi"] == [] and cl_thieu[0]["vung"] == "than"


def test_ket_ban_thao_dung_markdown_va_audit_muc_kiem():
    ket = d.ket_ban_thao(VAN_BAN)
    assert ket["document"].startswith("# BIÊN BẢN BÀN GIAO THIẾT BỊ")
    assert "## 1. Thời gian bàn giao" in ket["document"]
    assert ket["audit_report"] == {
        "dat": None, "completeness": None, "so_dieu_khoan": 2,
        "self_audit": False, "findings": [], "muc_kiem": "tong_quat",
    }


def test_khong_muc_nao_thi_khong_dung_ban_thao():
    assert d.ket_ban_thao({"tieu_de": "X", "muc": []}) is None


def test_render_markdown_tong_quat_khong_tra_checklist():
    """`_render_markdown` cũ nạp checklist theo `loai`; `tong_quat` không có
    checklist nào, nên nhánh này phải dựng thẳng từ danh sách mục — hàm chỉ
    đòi `ten`/`noi_dung` phẳng, không quan tâm `clauses` phía trên nó có
    `khoi` hay không (đó là việc của `dung_ban_thao_tong_quat._khoi_thanh_van_ban`,
    kiểm ở test `ket_ban_thao` bên trên)."""
    muc = [{"ten": "Thời gian bàn giao", "noi_dung": "…"}, {"ten": "Giá trị", "noi_dung": "…"}]
    md = ban_thao._render_markdown("tong_quat", muc, "BIÊN BẢN")
    assert md.startswith("# BIÊN BẢN") and "## 2. Giá trị" in md


def test_doi_muc_goi_ten_muc_da_doi():
    cu = d.clauses_tu(VAN_BAN)
    moi = d.clauses_tu({**VAN_BAN, "muc": [VAN_BAN["muc"][0], _muc("Giá trị", "Khác.")]})
    assert d.doi_muc(cu, moi) == ["Giá trị"]


# ───────────────────────────────────────────────────────────── định tuyến


@pytest.mark.parametrize("muc_dich", ["tao_van_ban", "sua_ban_thao"])
def test_re_sau_hieu_tai_lieu_di_toi_node_moi(muc_dich):
    from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu

    assert _re_sau_hieu_tai_lieu({"muc_dich_tai_lieu": muc_dich}) == "dung_ban_thao_tong_quat"


def test_re_sau_hieu_tai_lieu_giu_nguyen_duong_cu():
    from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu

    assert _re_sau_hieu_tai_lieu({"muc_dich_tai_lieu": "hoi"}) == "assemble"


def test_BUOC_TRA_CUU_co_buoc_moi_va_chi_tiet_dem_so_muc():
    from src.api.routes import BUOC_TRA_CUU, chi_tiet_buoc

    assert ("dung_ban_thao_tong_quat", "Dựng bản thảo tổng quát") in BUOC_TRA_CUU
    ten = [t for t, _ in BUOC_TRA_CUU]
    assert ten.index("dung_ban_thao_tong_quat") == ten.index("hieu_tai_lieu") + 1
    st = {"ban_thao_ket": {"clauses": d.clauses_tu(VAN_BAN)}}
    assert chi_tiet_buoc("dung_ban_thao_tong_quat", st) == {"so_muc": 2}


# ───────────────────────────────────────────────────────────────── assemble


class _No:
    def chat(self, *a, **k):  # pragma: no cover - chỉ để nổ nếu bị gọi
        raise AssertionError("nhánh bản thảo tổng quát không được gọi mô hình")


TAI_LIEU_KET = {
    "muc_dich": "tao_van_ban", "mo_ta": "Biên bản", "tra_loi_ngan": "Đã soạn.",
    "quan_sat": [], "suy_luan": [], "phep_tinh": [], "khac_biet": [],
    "can_du_kien": [], "du_kien": [], "tai_lieu_da_dung": [],
}
BAN_THAO_KET = {
    "id": "11111111-0000-0000-0000-000000000001",
    "loai": "tong_quat", "ten": "BIÊN BẢN BÀN GIAO THIẾT BỊ", "phien_ban": 1,
    "document": "# BIÊN BẢN", "clauses": d.clauses_tu(VAN_BAN),
    "audit_report": {"muc_kiem": "tong_quat", "findings": []},
    "facts": {}, "doi_so_voi_truoc": [],
}


def _chay(**ghi_de):
    st = {"query": "soạn biên bản bàn giao", "muc_dich_tai_lieu": "tao_van_ban",
          "tai_lieu_ket": TAI_LIEU_KET, "user_sub": "u", "ban_thao_ket": BAN_THAO_KET}
    return assemble({**st, **ghi_de}, {}, _No(), "m")


def test_assemble_tra_ban_thao_voi_nhan_chua_kiem_phap_ly():
    ra = _chay()
    assert ra["result_type"] is ResultType.ban_thao
    assert ra["ban_thao"] == BAN_THAO_KET
    assert "chưa kiểm pháp lý" in ra["answer"]
    assert "đã kiểm" not in ra["answer"]


def test_assemble_bao_doi_gi_o_luot_sua():
    ra = _chay(muc_dich_tai_lieu="sua_ban_thao",
               ban_thao_ket={**BAN_THAO_KET, "phien_ban": 2, "doi_so_voi_truoc": ["Giá trị"]})
    assert "Giá trị" in ra["answer"] and "phiên bản 2" in ra["answer"]


def test_assemble_khach_chua_dang_nhap_khong_cham_cho_luu():
    ra = _chay(user_sub=None, ban_thao_ket=None)
    assert ra["result_type"] is ResultType.soan_thao_hoi
    assert ra["soan_thao_hoi"]["can_dang_nhap"] is True
    assert ra["soan_thao_hoi"]["loai"] == "tong_quat"


def test_assemble_noi_that_khi_khong_dung_duoc():
    ra = _chay(ban_thao_ket=None, ban_thao_tong_quat_loi=ban_thao.LOI_HET_LAN_SUA)
    assert ra["result_type"] is ResultType.soan_thao_hoi
    assert ra["answer"] == ban_thao.LOI_HET_LAN_SUA
    assert ra["soan_thao_hoi"]["het_han_muc"] == ban_thao.LOI_HET_LAN_SUA


def test_assemble_khong_cuop_nhanh_tai_lieu_thuong():
    ra = assemble({"query": "x", "muc_dich_tai_lieu": "hoi", "tai_lieu_ket": TAI_LIEU_KET}, {}, _No(), "m")
    assert ra["result_type"] is ResultType.tai_lieu


def test_payload_tuan_tu_hoa_duoc_qua_TraCuuResponse():
    ra = _chay()
    resp = TraCuuResponse(
        result_type=ra["result_type"].value, answer=ra["answer"], citations=[], warnings=[],
        coverage_note=None, ban_thao=ra["ban_thao"], trace_id="t", config_name="c",
    )
    assert resp.ban_thao.loai == "tong_quat"
    assert resp.ban_thao.audit_report["muc_kiem"] == "tong_quat"


# ─────────────────────────────────────────── lưu thật (Postgres cục bộ)


@pytest.fixture
def nguoi():
    from sqlalchemy import text

    from src.services import bao_ve
    from src.services.db import get_engine

    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@pytest.mark.integration
def test_tao_roi_sua_len_phien_ban_2_va_lui_ve_duoc(nguoi):
    """Bản thảo tổng quát dùng ĐÚNG bảng và đúng hàm của bản thảo checklist —
    nên phiên bản, `phien_ban_truoc` và `lui` không phải viết lại lần thứ hai."""
    from src.services import hoi_thoai

    pid = hoi_thoai.tao_phien(nguoi, "biên bản bàn giao")
    st = {"user_sub": nguoi, "hoi_thoai_id": pid, "muc_dich_tai_lieu": "tao_van_ban",
          "van_ban_tong_quat": VAN_BAN}
    ra = d.dung_ban_thao_tong_quat(st)
    bt = ra["ban_thao_ket"]
    assert bt["phien_ban"] == 1 and bt["loai"] == "tong_quat"
    assert bt["audit_report"]["muc_kiem"] == "tong_quat"
    assert ban_thao.moi_nhat_cua_hoi_thoai(nguoi, pid, "tong_quat")["id"] == bt["id"]

    moi = {**VAN_BAN, "muc": [VAN_BAN["muc"][0], _muc("Giá trị", "Tổng 20.000.000 đồng.")]}
    ra2 = d.dung_ban_thao_tong_quat({**st, "muc_dich_tai_lieu": "sua_ban_thao", "van_ban_tong_quat": moi})
    bt2 = ra2["ban_thao_ket"]
    assert bt2["id"] == bt["id"] and bt2["phien_ban"] == 2
    assert bt2["doi_so_voi_truoc"] == ["Giá trị"]

    ve = ban_thao.lui(nguoi, bt["id"])
    assert ve["phien_ban"] == 1 and ve["document"] == bt["document"]


@pytest.mark.integration
def test_ten_la_ten_loai_khong_phai_tieu_de_van_ban(nguoi):
    """Phase 7 R4 — `ten` trả lời "bản thảo này THUỘC LOẠI gì" (`BanThaoOut.ten`),
    CỐ ĐỊNH `TEN_TONG_QUAT`, không phải `tieu_de` của văn bản
    ("BIÊN BẢN BÀN GIAO THIẾT BỊ"). `routes_ban_thao._ten_loai` đã trả cố định
    tên này ở mọi lần tải lại trang — gán `tieu_de` vào `ten` ở lượt vừa soạn
    (SSE) làm nó lệch khỏi giá trị đó ngay khi tải lại."""
    from src.services import hoi_thoai

    pid = hoi_thoai.tao_phien(nguoi, "biên bản bàn giao")
    st = {"user_sub": nguoi, "hoi_thoai_id": pid, "muc_dich_tai_lieu": "tao_van_ban",
          "van_ban_tong_quat": VAN_BAN}
    bt = d.dung_ban_thao_tong_quat(st)["ban_thao_ket"]
    assert bt["ten"] == d.TEN_TONG_QUAT
    assert bt["ten"] != VAN_BAN["tieu_de"]


@pytest.mark.integration
def test_sua_khi_chua_co_ban_thao_nao_thi_noi_that(nguoi):
    from src.services import hoi_thoai

    pid = hoi_thoai.tao_phien(nguoi, "biên bản")
    ra = d.dung_ban_thao_tong_quat({"user_sub": nguoi, "hoi_thoai_id": pid,
                                    "muc_dich_tai_lieu": "sua_ban_thao", "van_ban_tong_quat": VAN_BAN})
    assert ra["ban_thao_ket"] is None
    assert ra["ban_thao_tong_quat_loi"] == d.KHONG_CO_BAN_THAO


@pytest.mark.integration
def test_dung_lai_tu_choi_ban_thao_tong_quat_thay_vi_no(nguoi):
    """`dung_lai` chạy `graph_soan_thao`, mà graph đó nạp checklist theo `loai` —
    `tong_quat` không có checklist nào nên nó sẽ nổ 500. Chặn ở CHỖ DÙNG CHUNG,
    nên cả drawer sửa mục (`POST /ban-thao/{id}/dung`) lẫn lệnh sửa bằng lời của
    đường checklist đều nhận cùng một lời từ chối."""
    import asyncio

    from src.services import hoi_thoai

    pid = hoi_thoai.tao_phien(nguoi, "biên bản")
    bt = ban_thao.tao(nguoi, pid, "tong_quat", {}, d.ket_ban_thao(VAN_BAN))
    with pytest.raises(ValueError, match="tổng quát"):
        asyncio.run(ban_thao.dung_lai(nguoi, bt["id"], {}, pid))


@pytest.mark.integration
def test_het_tran_sua_chan_bang_dung_bo_dem_cua_ban_thao(nguoi):
    from src.services import hoi_thoai

    pid = hoi_thoai.tao_phien(nguoi, "biên bản")
    st = {"user_sub": nguoi, "hoi_thoai_id": pid, "muc_dich_tai_lieu": "tao_van_ban",
          "van_ban_tong_quat": VAN_BAN}
    bt = d.dung_ban_thao_tong_quat(st)["ban_thao_ket"]
    for _ in range(ban_thao.TRAN_SUA):
        ban_thao.sua(nguoi, bt["id"], {}, d.ket_ban_thao(VAN_BAN))
    ra = d.dung_ban_thao_tong_quat({**st, "muc_dich_tai_lieu": "sua_ban_thao"})
    assert ra["ban_thao_ket"] is None and ra["ban_thao_tong_quat_loi"] == ban_thao.LOI_HET_LAN_SUA
