"""Dữ kiện NỀN (hồ sơ tài khoản kế thừa vào phiên, `nguon = tai_khoan`) chỉ vào một
lượt khi lượt ấy là câu hỏi lao động.

Tái hiện lỗi đo trên app thật 2026-09-30 (phiên 983aa465…, 5f5e036b…): một tài khoản
Pro có hồ sơ lao động («Thực tập sinh», «Ocenpark», «Sắp kết thúc hợp đồng lao động»)
thấy dòng "Dựa trên" mang đúng các dữ kiện đó dưới một HỢP ĐỒNG THUÊ NHÀ và dưới câu
hỏi "hiện tại pháp luật việt nam chia thành những gì" — và mọi prompt sau đó nhận
chúng làm "tình huống của người hỏi". Test thuần: LLM giả, không DB.
"""

import json
from datetime import date

from src.agents.nodes.assemble import ResultType, _base
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.suy_dien import suy_dien
from src.api import routes
from src.models.schemas import TraCuuRequest
from src.services.llm import Usage

# Nguyên văn `hoi_thoai.ho_so` của phiên 983aa465-1700-475d-8faf-b9852dfa99df (seed từ
# `ho_so_tai_khoan` khi mở phiên, `routes._chuan_bi_phien`).
HO_SO_TAI_KHOAN = {
    "chu_the": {"nguon": "tai_khoan", "gia_tri": "Thực tập sinh"},
    "vu_viec": {
        "nguon": "tai_khoan",
        "gia_tri": "Sắp kết thúc hợp đồng lao động, cần nắm vững luật để bảo vệ quyền lợi",
    },
    "tham_nien": {"nguon": "tai_khoan", "gia_tri": "từ đủ 12 tháng trở lên"},
    "vung_luong": {"nguon": "tai_khoan", "gia_tri": "Ocenpark"},
    "loai_hop_dong": {"nguon": "tai_khoan", "gia_tri": "xác định thời hạn từ 12 tháng trở lên"},
}
THUE_NHA = (
    "Soạn hợp đồng thuê nhà ở giữa bên cho thuê là ông Nguyễn Văn An và bên thuê là bà Trần Thị Bình, "
    "giá thuê 10 triệu đồng một tháng, thời hạn 12 tháng"
)
HE_THONG = "hiện tại pháp luật việt nam chia thành những gì"


def _vao(query: str, ho_so: dict) -> dict:
    return routes._state_vao(TraCuuRequest(query=query), date(2026, 9, 30), "t", {"tom_tat": None, "ho_so": ho_so})


class Llm:
    def __init__(self, tra_ve: dict):
        self.tra_ve, self.prompt = tra_ve, []

    def chat(self, model, messages, json_schema=None):
        self.prompt.append(messages[-1]["content"])
        return json.dumps(self.tra_ve, ensure_ascii=False), Usage(1, 1, 0.0)


def _v2(linh_vuc: str) -> dict:
    return {
        "quan_he": "x",
        "vai": "chưa rõ",
        "linh_vuc": linh_vuc,
        "ba_lop": ["nguyen_tac"],
        "du_kien_van_ban": [],
        "queries": ["q1"],
    }


def _mau(tmp_path):
    p = tmp_path / "v2.md"
    p.write_text("quan_he vai linh_vuc {tinh_huong} {cau_hoi}", encoding="utf-8")
    return p


def test_ban_thao_thue_nha_khong_hien_du_kien_lao_dong_cua_tai_khoan():
    st = _vao(THUE_NHA, HO_SO_TAI_KHOAN)
    assert _base(st, ResultType.ban_thao)["ho_so_da_dung"] == []
    # Lượt soạn đọc hồ sơ làm NGUỒN giá trị điền (`hieu_tai_lieu._nguon_nguoi`): «Ocenpark»
    # không được là giá trị hợp lệ cho một hợp đồng thuê nhà.
    assert st["ho_so"] == {}


def test_du_kien_phien_tu_noi_van_o_lai():
    noi = {"chu_the": {"nguon": "nguoi_noi", "gia_tri": "người thuê nhà"}}
    st = _vao(THUE_NHA, {**HO_SO_TAI_KHOAN, **noi})
    assert st["ho_so"] == noi
    assert [d["gia_tri"] for d in _base(st, ResultType.ban_thao)["ho_so_da_dung"]] == ["người thuê nhà"]


def test_cau_hoi_he_thong_phap_luat_bo_nen(tmp_path):
    llm = Llm(_v2("hanh_chinh"))
    st = rewrite_query(_vao(HE_THONG, HO_SO_TAI_KHOAN), llm, "m", prompt_path=_mau(tmp_path))
    assert st["ho_so"] == {}
    assert _base(st, ResultType.abstain)["ho_so_da_dung"] == []


def test_cau_hoi_lao_dong_dung_nen(tmp_path):
    llm = Llm(_v2("lao_dong"))
    st = rewrite_query(
        _vao("hết hợp đồng tôi có được trợ cấp không", HO_SO_TAI_KHOAN), llm, "m", prompt_path=_mau(tmp_path)
    )
    assert st["ho_so"] == HO_SO_TAI_KHOAN
    assert "Ocenpark" in {d["gia_tri"] for d in _base(st, ResultType.answer)["ho_so_da_dung"]}


def test_rewrite_doc_ca_nen_de_phan_dinh_linh_vuc(tmp_path):
    """Nền là thứ để PHÂN ĐỊNH lĩnh vực của một câu mơ hồ ("hết hợp đồng thì sao") — bước
    đó đọc hồ sơ đầy đủ; chỉ các bước SAU nó mới bị giới hạn theo phán định."""
    llm = Llm(_v2("hanh_chinh"))
    rewrite_query(_vao(HE_THONG, HO_SO_TAI_KHOAN), llm, "m", prompt_path=_mau(tmp_path))
    assert "Ocenpark" in llm.prompt[0]


def test_suy_dien_khong_doan_vai_khi_nen_da_co_vai():
    st = suy_dien(_vao("tôi bị công ty cho nghỉ việc", HO_SO_TAI_KHOAN))
    assert "chu_the" not in st["ho_so"]
    assert st["traces"]["suy_dien_chu_the"] is None


def test_moi_khoa_state_vao_deu_duoc_KLawState_khai():
    """LangGraph bỏ âm thầm khoá không khai: `ho_so_nen` rơi ở đó thì `rewrite_query` không
    bao giờ trả được nền cho một câu hỏi lao động."""
    from src.agents.state import KLawState

    assert set(_vao("x", HO_SO_TAI_KHOAN)) <= set(KLawState.__annotations__)
