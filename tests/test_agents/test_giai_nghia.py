"""Node `giai_nghia` — biến câu nối tiếp thành câu tự đứng được, KHÔNG hơn.

Nhóm test này canh đúng hai điều mà spec gọi là không nhượng bộ (mục 2 và mục 3
của `2026-09-02-hoi-noi-tiep-design.md`):

* Lịch sử hội thoại chỉ làm câu hỏi TỰ ĐỨNG ĐƯỢC. Nó không chống đỡ khẳng định
  nào, nên câu đã giải nghĩa vẫn phải đi qua đủ truy hồi → tầng 1 → tầng 2.
* Node này KHÔNG được thêm nội dung pháp luật. Lưới chặn là `dinh_danh_bia` —
  một phép so tập, 0 token — vì hai tầng kiểm chứng đọc câu TRẢ LỜI chứ không
  đọc câu HỎI: một số Điều bịa trong câu hỏi đi qua chúng mà không vướng gì.

Cách canh "không gọi LLM": ĐẾM theo `json_schema` của từng lượt gọi, KHÔNG dùng
một fake `raise`. Bài học Pha 2 — `hoi_lai` bắt `Exception` nên nó nuốt luôn
`AssertionError` của fake và làm chết ba lưới canh, một trong đó là lưới của bất
biến tầng 2.
"""

import json

import pytest

from src.agents.nodes.giai_nghia import (
    GIAI_NGHIA_SCHEMA,
    TOI_DA_TRA_LOI,
    dinh_danh_bia,
    giai_nghia,
)
from src.services.llm import Usage

# Đúng chuỗi hội thoại thật trong bảng `traces` 2026-09-02 (spec mục 1): lượt
# đầu trả lời được 21 luận điểm về nghỉ việc, lượt thứ ba trỏ về CÁI BẢNG trong
# câu trả lời đó và được xử lý như một câu độc lập.
LICH_SU = [
    {
        "cau_hoi": "tôi đang chuẩn bị nghỉ việc",
        "tra_loi": "Khi bạn đơn phương chấm dứt hợp đồng lao động, thời hạn báo trước "
                   "phụ thuộc loại hợp đồng bạn đang ký. Bảng dưới đây tóm lại từng mốc.",
        "duong_dan": ["45/2019/QH14 > Điều 35 > Khoản 1"],
    },
    {"cau_hoi": "bạn làm được những gì", "tra_loi": "Mình tra được 6 Bộ luật…", "duong_dan": []},
]

CAU_NOI_TIEP = "liệt kê bảng cho tôi"


class FakeLlm:
    """GHI LẠI `json_schema` của từng lượt gọi. Đếm theo schema identity là cách
    duy nhất không bị một khối `except Exception` hạ nguồn nuốt mất."""

    def __init__(self, ra: dict | str | None = None) -> None:
        self.schema_da_goi: list[dict | None] = []
        self.prompt_da_goi: list[str] = []
        self._ra = ra if ra is not None else {
            "cau_hoi_day_du": "liệt kê bảng thời hạn báo trước khi nghỉ việc",
            "ly_do": "'bảng' trỏ về bảng thời hạn báo trước ở lượt 1",
        }

    def chat(self, model, messages, json_schema=None):
        self.schema_da_goi.append(json_schema)
        self.prompt_da_goi.append(messages[0]["content"])
        raw = self._ra if isinstance(self._ra, str) else json.dumps(self._ra, ensure_ascii=False)
        return raw, Usage(10, 5, 0.00005)

    @property
    def so_lan_giai_nghia(self) -> int:
        return sum(1 for s in self.schema_da_goi if s is GIAI_NGHIA_SCHEMA)


# ══ Ca của spec mục 10, dòng 1 ═══════════════════════════════════════════════


def test_cau_noi_tiep_rong_noi_dung_duoc_giai_nghia_tu_lich_su():
    """`"liệt kê bảng cho tôi"` một mình khớp NHIỄU (spec mục 1: Luật Phòng chống
    ma túy, Luật Thương mại). Sau giải nghĩa nó phải mang lại chủ đề của lượt
    trước, chứ không còn rỗng nội dung."""
    llm = FakeLlm()
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")

    day_du = st["cau_hoi_day_du"]
    assert day_du is not None, "có lịch sử rõ ràng mà vẫn không giải nghĩa được"
    assert "nghỉ việc" in day_du or "báo trước" in day_du, day_du
    assert st["query"] == day_du, "pipeline phải chạy trên câu ĐÃ giải nghĩa"
    assert st["cau_hoi_goc"] == CAU_NOI_TIEP, "câu gốc phải giữ nguyên để hiển thị và ghi traces"
    assert llm.so_lan_giai_nghia == 1


def test_lich_su_di_vao_prompt_va_tra_loi_cu_bi_cat():
    """Toàn văn câu trả lời cũ làm prompt phình mà không thêm tín hiệu (spec mục
    3). Cắt ở `TOI_DA_TRA_LOI`, và cắt ở CHỖ DỰNG PROMPT — không phải ở biên
    HTTP, để client không phải đoán con số này."""
    dai = "A" * (TOI_DA_TRA_LOI + 500)
    llm = FakeLlm()
    giai_nghia({"query": CAU_NOI_TIEP,
                "lich_su": [{"cau_hoi": "x", "tra_loi": dai, "duong_dan": []}]}, llm, "m")

    prompt = llm.prompt_da_goi[0]
    assert "A" * TOI_DA_TRA_LOI in prompt
    assert "A" * (TOI_DA_TRA_LOI + 1) not in prompt, "câu trả lời cũ chưa bị cắt"


def test_duong_dan_luot_truoc_di_vao_prompt():
    """`duong_dan` là thứ định danh CHÍNH XÁC điều khoản lượt trước đã dẫn — bỏ
    nó thì "cái bảng đó" mất neo cụ thể nhất mà lịch sử có."""
    llm = FakeLlm()
    giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")
    assert "45/2019/QH14 > Điều 35 > Khoản 1" in llm.prompt_da_goi[0]


# ══ Lượt ĐẦU: 0 token thêm ═══════════════════════════════════════════════════


@pytest.mark.parametrize("lich_su", [None, []], ids=["thieu-khoa", "rong"])
def test_lich_su_rong_thi_KHONG_goi_LLM(lich_su):
    """Lượt đầu của mỗi hội thoại không được tốn thêm một token nào (spec mục 3
    và mục 9). Đếm lượt gọi, KHÔNG dùng fake `raise`."""
    st_vao = {"query": "thử việc tối đa bao lâu"}
    if lich_su is not None:
        st_vao["lich_su"] = lich_su
    llm = FakeLlm()
    st = giai_nghia(st_vao, llm, "m")

    assert llm.so_lan_giai_nghia == 0, "lượt đầu KHÔNG được gọi giải nghĩa"
    assert llm.schema_da_goi == [], "lượt đầu không được gọi LLM ở bất kỳ vai nào"
    assert st["cau_hoi_day_du"] is None
    assert st["query"] == "thử việc tối đa bao lâu", "câu hỏi lượt đầu không được sửa"
    assert st["traces"]["giai_nghia_cost_usd"] == 0.0


# ══ Mặc định an toàn: không chắc thì nói không biết ══════════════════════════


@pytest.mark.parametrize("ra", [
    {"cau_hoi_day_du": "", "ly_do": "không rõ 'nó' trỏ vào đâu"},
    {"cau_hoi_day_du": "   ", "ly_do": "trống"},
    {"ly_do": "thiếu hẳn khoá"},
], ids=["rong", "toan-trang", "thieu-khoa"])
def test_model_khong_giai_duoc_thi_tra_None_KHONG_doan_bua(ra):
    llm = FakeLlm(ra)
    st = giai_nghia({"query": "còn nếu vậy thì sao", "lich_su": LICH_SU}, llm, "m")
    assert st["cau_hoi_day_du"] is None
    assert st["query"] == "còn nếu vậy thì sao", "không giải được thì KHÔNG sửa câu hỏi"


def test_json_sai_hinh_dang_thi_tra_None_KHONG_raise():
    """JSON dị dạng là lỗi ĐẦU RA của model, không phải lỗi hạ tầng — nó rơi về
    mặc định an toàn (không giải nghĩa được), không thành HTTP 500."""
    llm = FakeLlm("{ không phải json")
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")
    assert st["cau_hoi_day_du"] is None
    assert st["traces"]["giai_nghia_token_in"] == 10, "lượt gọi đã tiêu token thật, phải đếm"


def test_loi_ha_tang_NO_RA_NGOAI_khong_roi_em_thanh_khong_giai_nghia_duoc():
    """Cùng ruling với `route.py`: đây là bước QUYẾT ĐỊNH (câu nào được đem đi
    tra), nên một 429 âm thầm rơi thành "không đủ ngữ cảnh" sẽ đẩy một câu hỏi
    hợp lệ vào đường ngõ cụt mà không ai biết vì sao — và bảng số liệu của
    chương đánh giá đọc nó thành một lượt abstain thật."""
    class Bom:
        def chat(self, *a, **k):
            raise RuntimeError("openrouter 429")

    with pytest.raises(RuntimeError):
        giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, Bom(), "m")


# ══ Lưới chặn: KHÔNG thêm nội dung pháp luật ════════════════════════════════


def test_dinh_danh_bia_bat_so_dieu_khong_co_o_dau_ca():
    assert dinh_danh_bia("nghỉ việc theo Điều 35 thì báo trước bao lâu",
                         CAU_NOI_TIEP, LICH_SU) == []
    assert dinh_danh_bia("nghỉ việc theo Điều 999 thì báo trước bao lâu",
                         CAU_NOI_TIEP, LICH_SU) == ["Điều 999"]


def test_dinh_danh_bia_bat_so_hieu_van_ban_bia():
    assert dinh_danh_bia("bảng báo trước trong 45/2019/QH14", CAU_NOI_TIEP, LICH_SU) == []
    assert dinh_danh_bia("bảng báo trước trong 145/2020/NĐ-CP",
                         CAU_NOI_TIEP, LICH_SU) == ["145/2020"]


def test_dinh_danh_bia_nhan_dinh_danh_co_trong_CAU_GOC():
    """Người hỏi tự gõ số Điều thì nó không phải do model thêm vào."""
    assert dinh_danh_bia("Điều 37 quy định gì", "còn Điều 37 thì sao", []) == []


def test_cau_giai_nghia_bia_dinh_danh_thi_BI_LOAI_ve_None():
    llm = FakeLlm({"cau_hoi_day_du": "liệt kê bảng báo trước tại Điều 999 Bộ luật Lao động",
                   "ly_do": "bịa"})
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")

    assert st["cau_hoi_day_du"] is None, "câu bịa số Điều không được đem đi tra"
    assert st["query"] == CAU_NOI_TIEP
    assert st["traces"]["giai_nghia_nguon"] == "bi_loai", "lưới này nổ thì phải đếm được"


def test_bo_loc_so_voi_DUNG_phan_lich_su_da_dua_vao_prompt():
    """So với phần lịch sử ĐÃ CẮT, không phải toàn văn: model chỉ có thể lấy
    định danh từ đúng những gì nó được cho xem, nên một số Điều nằm ngoài đoạn
    400 ký tự đầu mà xuất hiện trong câu đã giải nghĩa là một trùng hợp, không
    phải một tham chiếu."""
    ls = [{"cau_hoi": "x", "tra_loi": "B" * TOI_DA_TRA_LOI + " Điều 777", "duong_dan": []}]
    assert dinh_danh_bia("còn Điều 777 thì sao", "còn vậy thì sao", ls) == ["Điều 777"]


# ══ Traces: một lượt gọi LLM không đếm được là một lượt vô hình ═════════════


def test_traces_ghi_du_ba_khoa_chi_phi():
    llm = FakeLlm()
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")
    tr = st["traces"]
    assert tr["giai_nghia_token_in"] == 10
    assert tr["giai_nghia_token_out"] == 5
    assert tr["giai_nghia_cost_usd"] == 0.00005
    assert tr["giai_nghia_model"] == "m"
    assert tr["giai_nghia_nguon"] == "llm"


def test_khoa_chi_phi_cua_giai_nghia_nam_trong_ba_danh_sach_cong_don():
    """`traces._COST_KEYS` cộng từ một danh sách CỐ ĐỊNH — một khoá mới không có
    trong đó là một lượt gọi LLM vô hình với trần chi phí ngày, đúng lớp lỗi đã
    làm 32/32 dòng `/soan-thao` mang `cost_usd = 0` (xem `traces.py`)."""
    from src.services.traces import _COST_KEYS, _TOKEN_IN_KEYS, _TOKEN_OUT_KEYS, _tong_hop_traces

    assert "giai_nghia_token_in" in _TOKEN_IN_KEYS
    assert "giai_nghia_token_out" in _TOKEN_OUT_KEYS
    assert "giai_nghia_cost_usd" in _COST_KEYS

    llm = FakeLlm()
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU}, llm, "m")
    assert _tong_hop_traces(st["traces"])["cost_usd"] == 0.00005


def test_traces_cua_node_truoc_KHONG_bi_xoa():
    llm = FakeLlm()
    st = giai_nghia({"query": CAU_NOI_TIEP, "lich_su": LICH_SU,
                     "traces": {"da_co": 1}}, llm, "m")
    assert st["traces"]["da_co"] == 1


# ══ Vòng review (silent-failure-hunter, 2026-09-02) ════════════════════════


@pytest.mark.parametrize("cau_da_giai", [
    # `prompts/giai_nghia.v1.md` ràng buộc 2 cấm model thêm "số Điều, số hiệu văn
    # bản, HAY MỘT MỐC PHÁP LÝ NÀO (số ngày, số tháng, mức lương, phần trăm)".
    # Lưới mã chỉ bắt HAI họ đầu — verify được: `dinh_danh_bia("… 45 ngày … 30%
    # …", "câu gốc", [])` trả RỖNG.
    "tôi phải báo trước 45 ngày đúng không",
    "công ty trừ 30% lương của tôi có đúng không",
    "lương tối thiểu 5 triệu đồng có đúng không",
    "thử việc quá 60 ngày thì sao",
    # Số viết bằng CHỮ là cùng một mốc, chỉ khác chính tả — cùng lỗ hổng đã sửa
    # ở bộ lọc `hoi_lai` sáng nay.
    "tôi phải báo trước bốn mươi lăm ngày đúng không",
    "công ty trừ mười phần trăm lương có đúng không",
])
def test_moc_phap_ly_bia_bi_bat(cau_da_giai):
    """Không tầng nào kiểm TIỀN ĐỀ của câu HỎI.

    Hai tầng kiểm chứng đối chiếu câu TRẢ LỜI với văn bản. Một câu hỏi đã giải
    nghĩa mang mốc bịa ("45 ngày", "30%") đi thẳng vào truy hồi, và mọi khẳng
    định sinh ra sau đó đều kiểm chứng được — về một câu hỏi không ai đặt.

    Không cần kẻ tấn công: `gemini-2.5-flash-lite` chạy đúng quy trình bình
    thường trên một lượt nối tiếp là đủ.
    """
    from src.agents.nodes.giai_nghia import dinh_danh_bia

    assert dinh_danh_bia(cau_da_giai, "câu hỏi gốc không có số nào", []) != [], (
        f"mốc pháp lý bịa lọt qua: {cau_da_giai!r}"
    )


@pytest.mark.parametrize("cau_da_giai, cau_goc, lich_su", [
    # Mốc CÓ trong câu gốc thì KHÔNG bịa — người dùng tự gõ nó.
    ("thử việc 60 ngày có đúng không", "thử việc 60 ngày có đúng không", []),
    # Mốc có trong lịch sử thì cũng không bịa — lượt trước đã nhắc.
    ("liệt kê bảng 30 ngày báo trước", "liệt kê bảng cho tôi",
     [{"cau_hoi": "nghỉ việc", "tra_loi": "phải báo trước 30 ngày", "duong_dan": []}]),
    # Câu sạch, không mốc nào.
    ("thời hạn báo trước khi nghỉ việc là bao lâu", "liệt kê bảng cho tôi",
     [{"cau_hoi": "tôi chuẩn bị nghỉ việc", "tra_loi": "…", "duong_dan": []}]),
])
def test_khong_loai_oan_moc_da_co_trong_nguon(cau_da_giai, cau_goc, lich_su):
    from src.agents.nodes.giai_nghia import dinh_danh_bia

    assert dinh_danh_bia(cau_da_giai, cau_goc, lich_su) == [], (
        f"loại oan: {cau_da_giai!r}"
    )


def test_duong_dan_tung_chuoi_co_tran_do_dai():
    """`max_length=50` trên `list[str]` giới hạn SỐ PHẦN TỬ, KHÔNG giới hạn độ
    dài từng chuỗi. Verify được: `duong_dan=['A'*2_000_000]*50` được pydantic
    CHẤP NHẬN — 100 MB đi thẳng vào prompt `giai_nghia`, không qua bước cắt nào.

    Đúng cái trần `TOI_DA_TRA_LOI` tồn tại để chặn, chỉ ở trường liền kề bị bỏ
    sót — `tra_loi` có trần, `duong_dan` thì không.
    """
    import pydantic
    import pytest as _pt

    from src.models.schemas import LuotTruoc

    with _pt.raises(pydantic.ValidationError):
        LuotTruoc(cau_hoi="x", tra_loi="y", duong_dan=["A" * 2_000_000])


def test_cau_hoi_rong_bi_tu_choi():
    """`cau_hoi=""` từng hợp lệ, nên một `lich_su` toàn rỗng vẫn truthy → kích
    hoạt `giai_nghia` và tắt cache dù không có nội dung thật nào. `query` của
    `TraCuuRequest` có `min_length=1`; trường này phải cùng khuôn."""
    import pydantic
    import pytest as _pt

    from src.models.schemas import LuotTruoc

    with _pt.raises(pydantic.ValidationError):
        LuotTruoc(cau_hoi="", tra_loi="y", duong_dan=[])
