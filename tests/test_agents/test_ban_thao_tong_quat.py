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

import pytest

from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import ResultType, assemble
from src.models.schemas import TraCuuResponse
from src.services import ban_thao
from src.services.doc_tai_lieu import DonViVanBan

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

    def chat(self, model, messages, json_schema=None):
        self.json_schema = json_schema
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
    assert van_ban["muc"][0]["khoi"] == [{"noi_dung": "", "bang": BANG_HOP_LE}]
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
    assert van_ban["muc"][0]["khoi"] == [{"noi_dung": "", "bang": BANG_HOP_LE}]


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
    assert khoi[0] == {"noi_dung": "Kết quả chấm điểm như sau:", "bang": []}
    assert khoi[1] == {"noi_dung": "", "bang": BANG_HOP_LE}


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

# BM.M05 thật (probe 2026-09-17): một letterhead 2 cột, hàng hai gộp 1 ô.
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
]
GOI_LETTERHEAD = [{"id": "x", "ten_tep": "bm05.docx", "don_vi": DV_LETTERHEAD, "nhan": "A", "gui": DV_LETTERHEAD}]
NGUON_LETTERHEAD = "\n".join(dv.noi_dung for dv in DV_LETTERHEAD)


def test_bang_theo_nhan_dung_lai_dung_luoi_tu_don_vi():
    """`_bang_theo_nhan` — dựng lại bảng THẬT 0 token, không đoán: hàng đầu 2
    cột, hàng hai (gộp) chỉ 1 cột — ĐÚNG số cột thật của từng hàng, không suy
    ra từ hàng tiêu đề."""
    ra = h._bang_theo_nhan(GOI_LETTERHEAD)
    assert ra == {
        "A0": [
            [
                "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
            ],
            ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
        ]
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
        {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []},
        {
            "noi_dung": "",
            "bang": [
                [
                    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                ],
                ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
            ],
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
    assert van_ban["muc"][0]["khoi"] == [{"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []}]


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
    DonViVanBan(chi_so=8, trang=1, offset_dau=95, noi_dung="Tổng", bang=(0, 2, 0)),
    DonViVanBan(chi_so=9, trang=1, offset_dau=100, noi_dung="10", bang=(0, 2, 1)),
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
    assert van_ban["muc"][0]["khoi"][0]["bang"] == [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa", "Điểm đánh giá"],
        ["1", "Ý thức chấp hành nội quy", "2,0", "1,8"],
        ["Tổng", "10"],
    ]


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
        {"noi_dung": "Mẫu QT.ĐT.28-M05", "bang": []},
        {
            "noi_dung": "",
            "bang": [
                [
                    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
                    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
                ],
                ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
            ],
        },
    ]


def test_loi_ha_tang_khong_de_lai_van_ban_bia():
    class _No:
        def chat(self, *a, **k):
            raise RuntimeError("502")

    ra = h.hieu_tai_lieu({"query": "soạn biên bản"}, TL, _No(), "m")
    assert ra["van_ban_tong_quat"] is None


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
