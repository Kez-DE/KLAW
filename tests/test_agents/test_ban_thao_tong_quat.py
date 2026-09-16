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

VAN_BAN = {
    "tieu_de": "BIÊN BẢN BÀN GIAO THIẾT BỊ",
    "muc": [
        {"ten": "Thời gian bàn giao", "noi_dung": "Bàn giao ngày 01/10/2026 tại kho A."},
        {"ten": "Giá trị", "noi_dung": "Tổng giá trị thiết bị 20.000.000 đồng."},
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


def _sach(muc: list[dict], nguon: str = NGUON):
    return h.lam_sach_van_ban({"tieu_de": "T", "muc": muc}, nguon)


# ────────────────────────────────────── phép kiểm bịa nội dung (0 token)


def test_gia_tri_chep_tu_tai_lieu_di_qua_nguyen_ven():
    van_ban, dem = _sach([{"ten": "Thời gian", "noi_dung": "Bàn giao ngày 01/10/2026 tại kho A."}])
    assert van_ban["muc"][0]["noi_dung"] == "Bàn giao ngày 01/10/2026 tại kho A."
    assert dem == {"muc_lam_sach": 0, "gia_tri_lam_sach": 0, "muc_bo": 0}


def test_so_hieu_tai_lieu_trong_mot_muc_khong_bi_coi_la_bia():
    """Số hiệu CỦA CHÍNH tài liệu ("12/2026") có trong nguồn, nên nó qua phép
    chứa; `_vuong_luoi_chan` vẫn bắt nó ở tầng sau và mục bị bỏ — đó là hai
    phép kiểm khác nhau, và test này khoá phép ĐẦU."""
    van_ban, dem = _sach([{"ten": "Căn cứ", "noi_dung": "Theo biên bản số 12/2026 đã lập."}])
    assert dem["gia_tri_lam_sach"] == 0, "giá trị có trong nguồn thì không bị thay"


def test_ngay_thang_bia_bi_thay_bang_dau_ba_cham():
    van_ban, dem = _sach([{"ten": "Thời gian", "noi_dung": "Bàn giao ngày 15/11/2027 tại kho A."}])
    assert "15/11/2027" not in van_ban["muc"][0]["noi_dung"]
    assert "[…]" in van_ban["muc"][0]["noi_dung"]
    assert dem["muc_lam_sach"] == 1 and dem["gia_tri_lam_sach"] == 1


def test_so_tien_bia_bi_thay_va_dem_theo_tung_gia_tri():
    van_ban, dem = _sach([{"ten": "Giá trị", "noi_dung": "Trị giá 99.000.000 đồng, đặt cọc 5.000.000 đồng."}])
    assert "99.000.000" not in van_ban["muc"][0]["noi_dung"]
    assert "5.000.000" not in van_ban["muc"][0]["noi_dung"]
    assert dem["gia_tri_lam_sach"] == 2 and dem["muc_lam_sach"] == 1


def test_so_viet_kieu_khac_van_khop_gia_tri_trong_nguon():
    """`20.000.000` trong tài liệu và `20000000` mô hình viết là MỘT con số —
    phép so đọc theo cùng quy ước với `phep_tinh`, không so chuỗi thô."""
    van_ban, dem = _sach([{"ten": "Giá trị", "noi_dung": "Tổng 20000000 đồng."}])
    assert dem["gia_tri_lam_sach"] == 0


def test_so_dieu_luat_bia_bi_thay_roi_muc_duoc_giu():
    """"Điều 42" không có trong nguồn → số bị thay bằng `[…]`, và sau đó mục
    không còn vướng lưới chặn nên nó ở lại (có nhãn, người đọc tự điền)."""
    van_ban, dem = _sach([{"ten": "Căn cứ", "noi_dung": "Căn cứ Điều 42 của quy chế công ty."}])
    assert dem["muc_bo"] == 0 and dem["gia_tri_lam_sach"] == 1
    assert "Điều […]" in van_ban["muc"][0]["noi_dung"]


def test_muc_con_vuong_luoi_chan_sau_khi_lam_sach_thi_bi_bo():
    """Số Điều CÓ trong nguồn đi qua phép chứa, nên chỉ lưới chặn dùng chung với
    `bo_nho` mới bắt được — và mục đó bị bỏ, có đếm."""
    van_ban, dem = _sach(
        [{"ten": "Căn cứ", "noi_dung": "Căn cứ Điều 42 Bộ luật Lao động."}],
        nguon="Căn cứ Điều 42 Bộ luật Lao động",
    )
    assert van_ban["muc"] == [] and dem["muc_bo"] == 1


def test_dau_vet_dinh_danh_ca_nhan_bi_bo_ca_muc():
    van_ban, dem = _sach(
        [{"ten": "Liên hệ", "noi_dung": "Liên hệ ban@vidu.vn để nhận bàn giao."}],
        nguon="Liên hệ ban@vidu.vn để nhận bàn giao",
    )
    assert van_ban["muc"] == [] and dem["muc_bo"] == 1


def test_muc_rong_hoac_sai_hinh_dang_bi_bo_khong_no():
    van_ban, dem = h.lam_sach_van_ban({"tieu_de": "T", "muc": ["x", {"ten": "", "noi_dung": ""}]}, NGUON)
    assert van_ban["muc"] == []


# ─────────────────────────────────────────── node hieu_tai_lieu phát `van_ban`


def test_schema_co_van_ban_va_hai_muc_dich_soan_lam_duoc():
    llm = _LLM(_ra())
    h.hieu_tai_lieu({"query": "soạn biên bản bàn giao từ nội dung này"}, TL, llm, "m")
    props = llm.json_schema["properties"]
    assert set(props["van_ban"]["properties"]) == {"tieu_de", "muc"}
    assert {"tao_van_ban", "sua_ban_thao"} <= h.MUC_DICH_LAM_DUOC


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
    bia = {"tieu_de": "X", "muc": [{"ten": "Giá trị", "noi_dung": "Trị giá 77.000.000 đồng."}]}
    ra = h.hieu_tai_lieu({"query": "soạn biên bản"}, TL, _LLM(_ra(van_ban=bia)), "m")
    assert "77.000.000" not in ra["van_ban_tong_quat"]["muc"][0]["noi_dung"]
    assert ra["traces"]["dung_ban_thao_so_gia_tri_lam_sach"] == 1


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
    checklist nào, nên nhánh này phải dựng thẳng từ `clauses`."""
    md = ban_thao._render_markdown("tong_quat", d.clauses_tu(VAN_BAN), "BIÊN BẢN")
    assert md.startswith("# BIÊN BẢN") and "## 2. Giá trị" in md


def test_doi_muc_goi_ten_muc_da_doi():
    cu = d.clauses_tu(VAN_BAN)
    moi = d.clauses_tu({**VAN_BAN, "muc": [VAN_BAN["muc"][0], {"ten": "Giá trị", "noi_dung": "Khác."}]})
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

    moi = {**VAN_BAN, "muc": [VAN_BAN["muc"][0], {"ten": "Giá trị", "noi_dung": "Tổng 20.000.000 đồng."}]}
    ra2 = d.dung_ban_thao_tong_quat({**st, "muc_dich_tai_lieu": "sua_ban_thao", "van_ban_tong_quat": moi})
    bt2 = ra2["ban_thao_ket"]
    assert bt2["id"] == bt["id"] and bt2["phien_ban"] == 2
    assert bt2["doi_so_voi_truoc"] == ["Giá trị"]

    ve = ban_thao.lui(nguoi, bt["id"])
    assert ve["phien_ban"] == 1 and ve["document"] == bt["document"]


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
