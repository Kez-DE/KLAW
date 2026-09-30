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


class LlmDocTinhHuong:
    """Rewrite giả chỉ dùng điều nó được thấy: khối tình huống nói tới hợp đồng lao động
    thì nó phán định lao động và viết truy vấn chấm dứt HĐLĐ — đúng hướng mô hình thật đã
    đi ở trace c8a98c3d (hạng 11–22 của truy hồi: 9 điều BLLĐ về chấm dứt hợp đồng, từ hai
    biến thể của rewrite; hạng 1–10 của câu gốc không có điều nào của BLLĐ)."""

    def __init__(self):
        self.prompt: list[str] = []

    def chat(self, model, messages, json_schema=None):
        p = messages[-1]["content"]
        self.prompt.append(p)
        # Chỉ khối tình huống: thân prompt v2 tự có ví dụ "chấm dứt hợp đồng lao động".
        tinh_huong = p.split("TÌNH HUỐNG CỦA NGƯỜI HỎI")[-1].split("CÂU HỎI:")[0]
        lao_dong = "hợp đồng lao động" in tinh_huong
        ra = {
            "quan_he": "chấm dứt hợp đồng lao động" if lao_dong else "hệ thống pháp luật",
            "vai": "người lao động" if lao_dong else "chưa rõ",
            "linh_vuc": "lao_dong" if lao_dong else "khac",
            "ba_lop": ["nguyen_tac"],
            "du_kien_van_ban": [],
            "queries": (
                ["các trường hợp chấm dứt hợp đồng lao động", "trợ cấp thôi việc khi hết hạn hợp đồng lao động"]
                if lao_dong
                else ["hệ thống văn bản quy phạm pháp luật", "hiệu lực pháp lý của Hiến pháp"]
            ),
        }
        return json.dumps(ra, ensure_ascii=False), Usage(1, 1, 0.0)


def test_rewrite_khong_doc_nen_nen_truy_van_khong_lech_sang_lao_dong():
    """Phát lại câu HE_THONG với hồ sơ tài khoản thật, prompt rewrite THẬT (v2 mặc định).
    Nền không được vào khối tình huống của rewrite: mô hình dùng khối đó để chọn vai và
    quan hệ khi viết truy vấn, và CHÍNH nó là bước phán định lĩnh vực — đọc nền ở đây là
    để ký ức lao động vừa lái truy hồi vừa tự quyết mình có liên quan hay không."""
    from pathlib import Path

    from src.agents.nodes.generate_claims import generate_claims
    from src.config import Settings

    llm = LlmDocTinhHuong()
    st = rewrite_query(_vao(HE_THONG, HO_SO_TAI_KHOAN), llm, "m", prompt_path=Path(Settings().rewrite_prompt))
    assert "Ocenpark" not in llm.prompt[0] and "Sắp kết thúc hợp đồng lao động" not in llm.prompt[0]
    assert not [q for q in st["queries"] if "lao động" in q]
    assert st["linh_vuc_du_doan"] != "lao_dong" and st["ho_so"] == {}

    class Gen:
        def chat(self, model, messages, json_schema=None):
            self.prompt = messages[-1]["content"]
            return json.dumps({"insufficient_evidence": True, "claims": []}), Usage(1, 1, 0.0)

    gen = Gen()
    prov = {
        "id": 1,
        "document_id": "d",
        "duong_dan": "Hiến pháp năm 2013 > Điều 2",
        "tieu_de": "Điều 2.",
        "noi_dung": "Nhà nước Cộng hòa xã hội chủ nghĩa Việt Nam…",
        "so_ky_hieu": "Hiến pháp năm 2013",
    }
    generate_claims({**st, "expanded": [prov]}, gen, "m")
    assert "Ocenpark" not in gen.prompt and "Thực tập sinh" not in gen.prompt


def test_cau_hoi_lao_dong_van_nhan_nen_sau_phan_dinh():
    """Chiều ngược lại của cùng bản sửa: câu hỏi lao động được phán định KHÔNG cần nền, rồi
    nền vào lại lượt (generate, assemble, hỏi lại) như trước."""
    from pathlib import Path

    from src.config import Settings

    class LaoDong(LlmDocTinhHuong):
        def chat(self, model, messages, json_schema=None):
            raw, u = super().chat(model, messages, json_schema)
            return json.dumps({**json.loads(raw), "linh_vuc": "lao_dong"}, ensure_ascii=False), u

    llm = LaoDong()
    st = rewrite_query(
        _vao("hết hạn hợp đồng thì công ty có phải trả trợ cấp không", HO_SO_TAI_KHOAN),
        llm,
        "m",
        prompt_path=Path(Settings().rewrite_prompt),
    )
    assert "Ocenpark" not in llm.prompt[0]
    assert st["ho_so"] == HO_SO_TAI_KHOAN


def test_suy_dien_khong_doan_vai_khi_nen_da_co_vai():
    st = suy_dien(_vao("tôi bị công ty cho nghỉ việc", HO_SO_TAI_KHOAN))
    assert "chu_the" not in st["ho_so"]
    assert st["traces"]["suy_dien_chu_the"] is None


def test_moi_khoa_state_vao_deu_duoc_KLawState_khai():
    """LangGraph bỏ âm thầm khoá không khai: `ho_so_nen` rơi ở đó thì `rewrite_query` không
    bao giờ trả được nền cho một câu hỏi lao động."""
    from src.agents.state import KLawState

    assert set(_vao("x", HO_SO_TAI_KHOAN)) <= set(KLawState.__annotations__)
