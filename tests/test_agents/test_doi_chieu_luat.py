"""GĐ5 — đối chiếu luật: điều khoản của người hỏi thành DỮ KIỆN cho đường pháp lý.

Năm điều bị khoá ở đây, và cả năm đều là biên của cùng một lời hứa: tài liệu của
người hỏi KHÔNG phải căn cứ, và hệ thống KHÔNG phán quyết.

1. Điều khoản ra khỏi `hieu_tai_lieu` phải neo được về đúng đơn vị đã đọc; cái
   không neo được bị loại, và một lượt đối chiếu KHÔNG còn điều khoản nào thì
   không được đi tiếp vào đường pháp lý với một danh sách rỗng.
2. Câu hỏi đường pháp lý đi tra là CÂU HỎI PHÁP LÝ của điều khoản, ghép bằng mã;
   câu người hỏi gõ ở lại `cau_hoi_goc` (đúng quy ước `giai_nghia`).
3. Điều khoản vào lời nhắc hành văn dưới đúng một nhãn "dữ kiện, KHÔNG phải căn
   cứ" — cùng ô `{tinh_huong}` mà mọi prompt đã gắn nhãn sẵn.
4. `tai_lieu_neo` đi kèm câu trả lời pháp lý; `tai_lieu` thì KHÔNG — lượt này
   trả lời bằng luật, không phải bằng tài liệu.
5. QT-1: một câu văn xuôi phán quyết ("hợp pháp", "thắng kiện", "vô hiệu") không
   được phát hành, kể cả khi mọi trích dẫn phía sau nó đã qua hai tầng kiểm.
"""

import json
from pathlib import Path

import pytest

from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu
from src.agents.nodes import assemble as a
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import (
    NHAN_DIEU_KHOAN_TAI_LIEU,
    ResultType,
    assemble,
    cau_phan_quyet,
    khoi_tinh_huong_doi_chieu,
)
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.models.schemas import TraCuuResponse
from src.services.bo_nho import khoi_tinh_huong
from src.services.doc_tai_lieu import DonViVanBan
from tests.test_agents.test_assemble import DB, _pass
from tests.test_agents.test_hieu_tai_lieu import _LLM, A_ID, _ra

DV_HD = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="HỢP ĐỒNG LAO ĐỘNG số 12/2026"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="Điều 2. Thời gian thử việc: 90 ngày kể từ ngày ký."),
    DonViVanBan(chi_so=2, trang=1, offset_dau=100, noi_dung="Điều 3. Lương thử việc bằng 70% lương chính thức."),
    DonViVanBan(chi_so=3, trang=1, offset_dau=160, noi_dung="Điều 4. Người lao động làm thêm tối đa 400 giờ một năm."),
    DonViVanBan(chi_so=4, trang=1, offset_dau=230, noi_dung="Điều 5. Hợp đồng chấm dứt khi hết thời hạn đã ghi."),
]
TL_HD = [{"id": A_ID, "ten_tep": "hopdong.docx", "don_vi": DV_HD}]
ST_HD = {"query": "hợp đồng này có đúng luật không"}

THU_VIEC = "Điều 2. Thời gian thử việc: 90 ngày kể từ ngày ký."
LUONG = "Điều 3. Lương thử việc bằng 70% lương chính thức."
HOI_THU_VIEC = "thời gian thử việc tối đa cho công việc này là bao lâu"
HOI_LUONG = "lương thử việc tối thiểu bằng bao nhiêu phần trăm lương chính thức"


def _dk(trich: str, cau_hoi: str) -> dict:
    return {"trich": trich, "cau_hoi_phap_ly": cau_hoi}


def _doc(dieu_khoan: list[dict], **ghi_de) -> dict:
    """Một lượt đối chiếu luật chạy qua node thật, mô hình giả."""
    llm = _LLM(_ra(muc_dich="doi_chieu_luat", dieu_khoan=dieu_khoan, **ghi_de))
    return h.hieu_tai_lieu(ST_HD, TL_HD, llm, "m")


# ───────────────────────────────────────────── lược đồ và phép neo điều khoản


def test_schema_co_dieu_khoan_hai_truong():
    s = h.schema_hieu(["A"])
    assert "dieu_khoan" in s["required"]
    assert s["properties"]["dieu_khoan"]["items"]["required"] == ["trich", "cau_hoi_phap_ly"]


def test_doi_chieu_luat_nam_trong_muc_dich_lam_duoc():
    assert "doi_chieu_luat" in h.MUC_DICH_LAM_DUOC


def test_dieu_khoan_neo_duoc_thanh_tai_lieu_neo():
    ra = _doc([_dk(THU_VIEC, HOI_THU_VIEC)])
    assert len(ra["tai_lieu_neo"]) == 1
    n = ra["tai_lieu_neo"][0]
    assert n["tai_lieu_id"] == A_ID and n["chi_so_don_vi"] == 1 and n["trang"] == 1
    assert n["vung"] == "than" and n["bang"] is None and n["nguon_chu"] == "lop_chu" and n["do_tin"] is None
    assert n["trich"] == THU_VIEC and n["cau_hoi_phap_ly"] == HOI_THU_VIEC
    assert ra["traces"]["hieu_tai_lieu_so_dieu_khoan"] == 1
    assert ra["traces"]["hieu_tai_lieu_so_dieu_khoan_bo"] == 0


def test_dieu_khoan_khong_tra_nguoc_duoc_bi_loai():
    ra = _doc([_dk("Thời gian thử việc: 15 ngày", HOI_THU_VIEC)])
    assert ra["tai_lieu_neo"] == []
    assert ra["traces"]["hieu_tai_lieu_so_dieu_khoan_bo"] == 1


def test_dieu_khoan_thieu_cau_hoi_phap_ly_bi_loai():
    """Một điều khoản không có câu hỏi pháp lý không hỏi được kho điều gì."""
    ra = _doc([_dk(THU_VIEC, "  ")])
    assert ra["tai_lieu_neo"] == []
    assert ra["traces"]["hieu_tai_lieu_so_dieu_khoan_bo"] == 1


def test_tran_ba_dieu_khoan():
    ra = _doc([
        _dk(THU_VIEC, HOI_THU_VIEC),
        _dk(LUONG, HOI_LUONG),
        _dk("Điều 4. Người lao động làm thêm tối đa 400 giờ một năm.", "làm thêm tối đa bao nhiêu giờ một năm"),
        _dk("Điều 5. Hợp đồng chấm dứt khi hết thời hạn đã ghi.", "hợp đồng chấm dứt trong trường hợp nào"),
    ])
    assert len(ra["tai_lieu_neo"]) == h.TOI_DA_DIEU_KHOAN == 3


def test_muc_dich_khac_thi_khong_lay_dieu_khoan():
    """Điều khoản chỉ có nghĩa ở lượt đối chiếu; một lượt tóm tắt kèm
    `dieu_khoan` là mô hình điền cho đủ hình dạng."""
    llm = _LLM(_ra(muc_dich="tom_tat", dieu_khoan=[_dk(THU_VIEC, HOI_THU_VIEC)]))
    ra = h.hieu_tai_lieu(ST_HD, TL_HD, llm, "m")
    assert ra["tai_lieu_neo"] == []


def test_khong_neo_duoc_dieu_khoan_nao_thi_ha_ve_hoi_va_noi_that():
    ra = _doc([_dk("không có câu này trong tài liệu", HOI_THU_VIEC)])
    assert ra["muc_dich_tai_lieu"] == "doi_chieu_luat", "mục đích THẬT vẫn được ghi lại"
    assert ra["tai_lieu_ket"]["muc_dich"] == "hoi", "hành vi rơi về `hoi`"
    assert h.DOI_CHIEU_KHONG_NEO in ra["tai_lieu_ket"]["tra_loi_ngan"]


# ─────────────────────────────────────────────────────────────── quyết định rẽ


def test_re_sang_tien_de_khi_doi_chieu_va_co_dieu_khoan():
    st = {"muc_dich_tai_lieu": "doi_chieu_luat", "tai_lieu_neo": [{"trich": THU_VIEC}]}
    assert _re_sau_hieu_tai_lieu(st) == "tien_de"


def test_doi_chieu_khong_co_dieu_khoan_van_ve_assemble():
    st = {"muc_dich_tai_lieu": "doi_chieu_luat", "tai_lieu_neo": []}
    assert _re_sau_hieu_tai_lieu(st) == "assemble"


@pytest.mark.parametrize("muc_dich", ["tom_tat", "hoi", "phan_tich", "trich_du_kien", "so_sanh", None])
def test_muc_dich_khac_ve_assemble(muc_dich):
    st = {"muc_dich_tai_lieu": muc_dich, "tai_lieu_neo": [{"trich": THU_VIEC}]}
    assert _re_sau_hieu_tai_lieu(st) == "assemble"


# ──────────────────────────────────────────────── câu hỏi đưa sang đường luật


def test_cau_hoi_day_du_ghep_tu_cau_hoi_phap_ly():
    ra = _doc([_dk(THU_VIEC, HOI_THU_VIEC), _dk(LUONG, HOI_LUONG)])
    assert ra["cau_hoi_day_du"] == f"{HOI_THU_VIEC}; {HOI_LUONG}"
    assert ra["query"] == ra["cau_hoi_day_du"], "cả đường pháp lý chạy trên câu đã ghép"
    assert ra["cau_hoi_goc"] == ST_HD["query"], "câu người hỏi gõ không bị mất"


def test_cau_hoi_day_du_bi_cat_theo_tran():
    dai = "a" * 250
    ra = _doc([_dk(THU_VIEC, dai), _dk(LUONG, dai)])
    assert len(ra["cau_hoi_day_du"]) <= h.CAU_HOI_TOI_DA


def test_cau_hoi_goc_co_san_thi_khong_bi_ghi_de():
    """Lượt NỐI TIẾP đã qua `giai_nghia`: câu gõ nằm ở `cau_hoi_goc`, còn
    `query` đã là câu giải nghĩa — không được lấy câu giải nghĩa làm câu gốc."""
    llm = _LLM(_ra(muc_dich="doi_chieu_luat", dieu_khoan=[_dk(THU_VIEC, HOI_THU_VIEC)]))
    st = {"query": "điều khoản thử việc trong hợp đồng vừa gửi", "cau_hoi_goc": "còn điều đó thì sao"}
    ra = h.hieu_tai_lieu(st, TL_HD, llm, "m")
    assert ra["cau_hoi_goc"] == "còn điều đó thì sao"


def test_luot_khong_doi_chieu_khong_dung_toi_cau_hoi():
    llm = _LLM(_ra(muc_dich="hoi"))
    ra = h.hieu_tai_lieu(ST_HD, TL_HD, llm, "m")
    assert ra.get("cau_hoi_day_du") is None
    assert ra["query"] == ST_HD["query"]


# ───────────────────────────────────────── khối tình huống của lời nhắc hành văn

HO_SO = {"vai_tro": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}}
NEO = [
    {"tai_lieu_id": A_ID, "chi_so_don_vi": 1, "trang": 1, "vung": "than", "bang": None,
     "nguon_chu": "lop_chu", "do_tin": None, "trich": THU_VIEC, "cau_hoi_phap_ly": HOI_THU_VIEC},
]


def test_khoi_tinh_huong_giu_ho_so_va_them_dieu_khoan_co_nhan():
    khoi = khoi_tinh_huong_doi_chieu(HO_SO, NEO)
    assert khoi_tinh_huong(HO_SO) in khoi, "dữ kiện tình huống cũ không được mất"
    assert NHAN_DIEU_KHOAN_TAI_LIEU in khoi
    assert f'- "{THU_VIEC}"' in khoi


def test_khoi_tinh_huong_khong_co_dieu_khoan_thi_giu_nguyen():
    assert khoi_tinh_huong_doi_chieu(HO_SO, []) == khoi_tinh_huong(HO_SO)


def test_trich_dai_bi_cat_truoc_khi_vao_loi_nhac():
    dai = [{**NEO[0], "trich": "x" * 400}]
    khoi = khoi_tinh_huong_doi_chieu(HO_SO, dai)
    assert "x" * 400 not in khoi
    assert len(max(khoi.split("\n"), key=len)) <= 210


# ───────────────────────────────────────── phép kiểm phán quyết (QT-1, 0 token)

CITATION_VO_HIEU = [{"quote": "Hợp đồng lao động vô hiệu toàn bộ khi toàn bộ nội dung vi phạm pháp luật",
                     "duong_dan": "45/2019/QH14 > Điều 49"}]


@pytest.mark.parametrize("cau", [
    "Hợp đồng của bạn không hợp pháp.",
    "Điều khoản này trái luật.",
    "Thoả thuận này trái pháp luật.",
    "Điều khoản này vô hiệu.",
    "Điều này có lợi cho bạn.",
    "Điều khoản đó bất lợi cho người lao động.",
    "Bạn sẽ thắng kiện nếu khởi kiện.",
    "Bạn chắc chắn thắng.",
    "Bạn được bồi thường hai tháng lương.",
])
def test_cau_phan_quyet_bat_duoc_loi_tien_doan(cau):
    assert cau_phan_quyet(cau, []) is not None


def test_cau_neu_luat_va_khac_biet_di_qua():
    cau = "Điều 25 yêu cầu thời gian thử việc không quá 60 ngày; hợp đồng ghi 90 ngày."
    assert cau_phan_quyet(cau, []) is None


def test_cum_nam_trong_trich_dan_da_kiem_thi_duoc_phep():
    """Chính kho nói "hợp đồng lao động vô hiệu" — chặn cụm ấy là cấm trợ lý đọc
    lại điều luật nó vừa dẫn."""
    cau = "Theo căn cứ đã dẫn, hợp đồng lao động vô hiệu toàn bộ khi toàn bộ nội dung vi phạm pháp luật."
    assert cau_phan_quyet(cau, CITATION_VO_HIEU) is None
    assert cau_phan_quyet(cau, []) is not None, "không có trích dẫn nào chống đỡ thì vẫn bị chặn"


# ────────────────────────────────────────── câu trả lời pháp lý của lượt đối chiếu

KET_TAI_LIEU = {
    "muc_dich": "doi_chieu_luat", "mo_ta": "Hợp đồng lao động", "tra_loi_ngan": "…",
    "quan_sat": [], "suy_luan": [], "phep_tinh": [], "khac_biet": [], "can_du_kien": [],
    "du_kien": [], "tai_lieu_da_dung": [{"id": A_ID, "ten_tep": "hopdong.docx", "nhan": "A"}],
}
HOP_LE = "Điều 26 buộc trả ít nhất 85% mức lương; hợp đồng ghi 70%."
PHAN_QUYET = "Điều 26 buộc trả ít nhất 85% mức lương, nên điều khoản 70% là không hợp pháp."


class _Llm:
    """Ghi lại lời nhắc hành văn; trả đúng câu văn xuôi được đặt hàng."""

    def __init__(self, answer: str) -> None:
        self.answer, self.prompt = answer, None

    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage

        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        self.prompt = messages[-1]["content"]
        return json.dumps({"answer": self.answer}, ensure_ascii=False), Usage(1, 1, 0.0)


def _phap_ly(answer: str, llm: _Llm | None = None, **ghi_de):
    st = {
        "intent": None, "query": HOI_THU_VIEC, "ho_so": HO_SO,
        "expanded": [DB[11]], "tier1": [_pass()], "tier2": [Tier2Verdict(0, True, "ok")],
        "abstain_threshold": 0.5, "tai_lieu_neo": NEO, "tai_lieu_ket": KET_TAI_LIEU,
    }
    return assemble({**st, **ghi_de}, DB, llm or _Llm(answer), "m",
                    prompt_path=Path("prompts/assemble.v6.md"))


def test_tai_lieu_ket_khong_cuop_nhanh_cua_luot_doi_chieu():
    """`tai_lieu_ket` còn trong state suốt đường pháp lý — nhánh tài liệu không
    được hớt tay trên một câu trả lời đã qua hai tầng kiểm."""
    ra = _phap_ly(HOP_LE)
    assert ra["result_type"] is ResultType.answer
    assert ra["answer"] == HOP_LE


def test_answer_mang_tai_lieu_neo_va_KHONG_mang_tai_lieu():
    ra = _phap_ly(HOP_LE)
    assert ra["tai_lieu_neo"] == NEO
    assert ra.get("tai_lieu") is None, "lượt này trả lời bằng luật, không bằng tài liệu"


def test_tai_lieu_neo_tuan_tu_hoa_duoc_qua_TraCuuResponse():
    """Hợp đồng với giao diện: hai trường của nhánh này (`trich`,
    `cau_hoi_phap_ly`) phải đi trọn qua `NeoTaiLieuOut`, không rơi ở biên HTTP."""
    ra = _phap_ly(HOP_LE)
    resp = TraCuuResponse(
        result_type=ra["result_type"].value, answer=ra["answer"], citations=[], warnings=[],
        coverage_note=None, tai_lieu=ra.get("tai_lieu"), tai_lieu_neo=ra["tai_lieu_neo"],
        trace_id="t", config_name="c",
    )
    assert resp.tai_lieu is None
    assert resp.tai_lieu_neo[0].trich == THU_VIEC
    assert resp.tai_lieu_neo[0].cau_hoi_phap_ly == HOI_THU_VIEC
    assert resp.tai_lieu_neo[0].chi_so_don_vi == 1 and resp.tai_lieu_neo[0].vung == "than"


def test_abstain_van_mang_tai_lieu_neo():
    ra = _phap_ly(HOP_LE, tier1=[], tier2=[])
    assert ra["result_type"] is ResultType.abstain
    assert ra["tai_lieu_neo"] == NEO


def test_dieu_khoan_vao_loi_nhac_duoi_nhan_du_kien():
    llm = _Llm(HOP_LE)
    _phap_ly(HOP_LE, llm=llm)
    assert NHAN_DIEU_KHOAN_TAI_LIEU in llm.prompt
    assert THU_VIEC in llm.prompt


def test_van_xuoi_phan_quyet_KHONG_duoc_phat_hanh():
    """Chặn VĂN XUÔI, không chặn CĂN CỨ.

    Bản trước hạ cả lượt xuống `abstain` và trả `citations: []` — đo toàn tuyến
    2026-09-16 thấy người hỏi mất luôn `45/2019/QH14 > Điều 25 > Khoản 2` đã qua
    hai tầng kiểm, tức mất đúng thứ sản phẩm này tồn tại để đưa ra. Chỉ có câu
    kết luận là sai; căn cứ thì không. `abstain` cũng nói sai sự thật: nó nghĩa
    là KHÔNG đủ căn cứ, mà ở đây căn cứ có và đã kiểm.
    """
    ra = _phap_ly(PHAN_QUYET)
    assert ra["result_type"] is ResultType.answer
    assert ra["traces"]["assemble_phan_quyet_bi_chan"] == "không hợp pháp"
    # Văn xuôi phát hành là bản DỰNG TỪ luận điểm đã kiểm, không phải của mô hình.
    assert PHAN_QUYET not in (ra["answer"] or "")
    assert "Ít nhất 85%." in ra["answer"] and THU_VIEC in ra["answer"]
    assert ra["citations"], "căn cứ đã kiểm phải còn lại"


def test_luot_KHONG_doi_chieu_khong_bi_phep_kiem_phan_quyet_cham_toi():
    """Phép kiểm chỉ gác lượt đối chiếu: một câu trả lời tra cứu thường vẫn được
    đọc lại điều luật nói "vô hiệu"."""
    ra = _phap_ly("Điều 26 quy định hợp đồng vô hiệu trong trường hợp này.",
                  tai_lieu_neo=[], tai_lieu_ket=None)
    assert ra["result_type"] is ResultType.answer
    assert ra["traces"].get("assemble_phan_quyet_bi_chan") is None


# ───────────────── phán quyết nói VÒNG: cùng kết luận, chữ khác
# Đo toàn tuyến HTTP 2026-09-16: câu trả lời thật viết "Riêng mức thử việc 90
# ngày bạn nêu trong hợp đồng có thể KHÔNG ĐÚNG QUY ĐỊNH PHÁP LUẬT". Không cụm
# nào trong danh sách khớp, nhưng nó là đúng kết luận mà QT-1 cấm — chỉ nói
# vòng và thêm "có thể". Một danh sách chặn theo chữ mà bỏ cách nói phổ biến
# nhất thì nó chỉ dạy mô hình nói vòng.


@pytest.mark.parametrize(
    "cau",
    [
        "Mức thử việc 90 ngày có thể không đúng quy định pháp luật.",
        "Điều khoản này không đúng quy định của pháp luật.",
        "Thoả thuận này không phù hợp với quy định pháp luật.",
        "Điều khoản đó vi phạm pháp luật lao động.",
        "Hợp đồng này sai quy định.",
        "Điều khoản này là hợp lệ.",
        "Thoả thuận này không hợp lệ.",
    ],
)
def test_phan_quyet_noi_vong_van_bi_chan(cau):
    assert a.cau_phan_quyet(cau, []) is not None


@pytest.mark.parametrize(
    "cau",
    [
        "Điều 25 yêu cầu thời gian thử việc không quá 60 ngày; hợp đồng ghi 90 ngày.",
        "Luật quy định tối đa 60 ngày. Tài liệu của bạn ghi 90 ngày, dài hơn 30 ngày.",
        "Điều 25 Khoản 2 đặt trần 60 ngày cho công việc yêu cầu trình độ cao đẳng trở lên.",
    ],
)
def test_neu_luat_va_cho_lech_KHONG_bi_chan(cau):
    assert a.cau_phan_quyet(cau, []) is None
