"""Bộ nhớ ba lớp và hồ sơ tình huống (spec 2026-09-09 §6)."""

import asyncio
import json
import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, bo_nho, ho_so, hoi_thoai
from src.services.db import get_engine
from src.services.llm import Usage


class LlmGia:
    def __init__(self, tra: dict):
        self.tra, self.da_goi = tra, []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append(messages)
        return json.dumps(self.tra, ensure_ascii=False), Usage(token_in=10, token_out=5, cost_usd=0.0001)


@pytest.mark.parametrize(
    "gia_tri, hop_le",
    [
        ("người lao động", True),
        ("làm 3 năm, hợp đồng không xác định thời hạn", True),
        ("theo Điều 35 Bộ luật Lao động", False),
        ("Đ.35", False),  # viết tắt chuẩn pháp lý — không có khoảng trắng, có dấu chấm
        ("đ.35 BLLĐ", False),  # thường, không dấu, có hậu tố bộ luật
        ("Điều35", False),  # đủ chữ nhưng dính liền số
        ("Đ. 35, Quận 1", False),  # dương tính giả CHỦ Ý (review round 2): "Đ." cũng là viết tắt "Đường"
        ("45/2019/QH14", False),
        ("Nghị định 145/2020/NĐ-CP", False),
        ("Thông tư 10/2020/TT-BLĐTBXH", False),
        ("CMND 012345678912", False),
        ("a@b.vn", False),
        ("", False),
        ("x" * 121, False),
        # `thoi_diem` là khoá NGƯỜI TA trả lời tự nhiên nhất bằng "tháng M/YYYY";
        # lưới chặn số hiệu văn bản từng nuốt sạch nó nên hồ sơ không bao giờ đầy
        # và `hoi_lai` hỏi lại đúng dữ kiện đó mỗi lượt.
        ("tháng 3/2024", True),
        ("vào làm từ tháng 6/2015", True),
        ("nghỉ việc 15/10/2026", True),
        ("làm từ 1/2020 đến nay", False),  # dương tính giả CHỦ Ý — xem `_vuong_luoi_chan`
    ],
)
def test_gia_tri_hop_le(gia_tri, hop_le):
    assert bo_nho.gia_tri_hop_le(gia_tri) is hop_le


def test_gop_ho_so_moi_de_cu_nhung_suy_dien_khong_de_nguoi_noi():
    cu = {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}}
    ra = bo_nho.gop_ho_so(cu, {"chu_the": "người sử dụng lao động", "tham_nien": "3 năm", "la": "bo"}, "suy_dien")
    assert ra["chu_the"]["gia_tri"] == "người lao động"  # nguoi_noi thắng suy_dien
    assert ra["tham_nien"] == {"gia_tri": "3 năm", "nguon": "suy_dien"}
    assert "la" not in ra  # khoá lạ bị bỏ
    ra2 = bo_nho.gop_ho_so(ra, {"chu_the": "người sử dụng lao động"}, "nguoi_noi")
    assert ra2["chu_the"]["gia_tri"] == "người sử dụng lao động"
    ra3 = bo_nho.gop_ho_so(ra2, {"tham_nien": "theo Điều 35"}, "nguoi_noi")
    assert ra3["tham_nien"]["gia_tri"] == "3 năm"  # giá trị vi phạm lưới chặn giữ bản cũ


def test_khoi_tinh_huong_va_ho_so_da_dung():
    ho_so = {
        "chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"},
        "tham_nien": {"gia_tri": "3 năm", "nguon": "nguoi_noi"},
    }
    khoi = bo_nho.khoi_tinh_huong(ho_so)
    assert "- Vai của bạn: người lao động (tôi đoán)" in khoi and "- Thâm niên: 3 năm" in khoi
    assert bo_nho.khoi_tinh_huong({}) == bo_nho.KHONG_CO_DU_KIEN
    assert bo_nho.ho_so_da_dung(ho_so) == [
        {"khoa": "chu_the", "nhan": "Vai của bạn", "gia_tri": "người lao động", "gia_dinh": True},
        {"khoa": "tham_nien", "nhan": "Thâm niên", "gia_tri": "3 năm", "gia_dinh": False},
    ]


@pytest.mark.parametrize(
    "den_cu, moi, ra", [(0, 6, None), (0, 7, (1, 1)), (0, 9, (1, 3)), (3, 9, None), (3, 12, (4, 6))]
)
def test_luot_can_gop(den_cu, moi, ra):
    # K=6: lượt 7 ghi xong thì lượt 1 rơi khỏi cửa sổ nguyên văn và phải vào tóm tắt.
    assert bo_nho.luot_can_gop(den_cu, moi) == ra


class _CaiDatGia:
    def __init__(self, bat: bool):
        self.bo_nho_nen = bat


async def test_len_lich_cap_nhat_tat_khong_xep_lich(monkeypatch):
    goi = []
    monkeypatch.setattr(bo_nho, "cap_nhat_phien", lambda *a, **k: goi.append(a))
    monkeypatch.setattr(bo_nho, "get_settings", lambda: _CaiDatGia(False))
    bo_nho.len_lich_cap_nhat("pid", "sub")
    assert goi == [] and bo_nho._DANG_CHAY == set()


async def test_len_lich_cap_nhat_bat_xep_lich_va_chay(monkeypatch):
    goi = []
    monkeypatch.setattr(bo_nho, "cap_nhat_phien", lambda *a, **k: goi.append(a))
    monkeypatch.setattr(bo_nho, "get_settings", lambda: _CaiDatGia(True))
    bo_nho.len_lich_cap_nhat("pid", "sub")
    assert len(bo_nho._DANG_CHAY) == 1
    await asyncio.gather(*list(bo_nho._DANG_CHAY))
    assert goi == [("pid", "sub")]
    assert bo_nho._DANG_CHAY == set()  # done_callback đã dọn task xong


def test_luu_suy_dien_khong_lam_gi_khi_khong_co_khoa_nguon_suy_dien(monkeypatch):
    doc_goi, ghi_goi = [], []
    monkeypatch.setattr(hoi_thoai, "bo_nho_cua_phien", lambda pid: doc_goi.append(pid) or {"ho_so": {}})
    monkeypatch.setattr(hoi_thoai, "ghi_ho_so", lambda pid, ho_so: ghi_goi.append((pid, ho_so)))
    bo_nho.luu_suy_dien("pid", {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}})
    assert doc_goi == [] and ghi_goi == []  # không đọc, không ghi — không có gì mới của suy_dien


def test_luu_suy_dien_loc_theo_nguon_va_gop_vao_ho_so_cu(monkeypatch):
    monkeypatch.setattr(
        hoi_thoai,
        "bo_nho_cua_phien",
        lambda pid: {"ho_so": {"tham_nien": {"gia_tri": "3 năm", "nguon": "nguoi_noi"}}, "khong_ghi_nho": False},
    )
    ghi_goi = []
    monkeypatch.setattr(hoi_thoai, "ghi_ho_so", lambda pid, ho_so: ghi_goi.append((pid, ho_so)))
    bo_nho.luu_suy_dien(
        "pid",
        {
            "chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"},
            "vu_viec": {"gia_tri": "tranh chấp lương", "nguon": "nguoi_noi"},  # nguồn khác — phải bị lọc
        },
    )
    assert len(ghi_goi) == 1
    pid, ho_so_gop = ghi_goi[0]
    assert pid == "pid"
    assert ho_so_gop["chu_the"] == {"gia_tri": "người lao động", "nguon": "suy_dien"}
    assert ho_so_gop["tham_nien"] == {"gia_tri": "3 năm", "nguon": "nguoi_noi"}  # hồ sơ cũ vẫn giữ
    assert "vu_viec" not in ho_so_gop  # nguồn nguoi_noi trong ho_so_state không đi vào gộp


def test_luu_suy_dien_khong_ghi_khi_phien_tat_bo_nho(monkeypatch):
    """"Không ghi nhớ phiên này" phải chặn MỌI đường ghi vào hồ sơ phiên, không
    riêng tóm tắt: `cap_nhat_phien` đã tôn trọng cờ này, nên nếu `luu_suy_dien`
    không tôn trọng thì một phiên đã tắt bộ nhớ vẫn tích luỹ và nạp lại một hồ sơ
    tình huống bền — đúng thứ người dùng vừa tắt."""
    ghi_goi = []
    monkeypatch.setattr(hoi_thoai, "bo_nho_cua_phien", lambda pid: {"ho_so": {}, "khong_ghi_nho": True})
    monkeypatch.setattr(hoi_thoai, "ghi_ho_so", lambda pid, ho_so: ghi_goi.append((pid, ho_so)))
    bo_nho.luu_suy_dien("pid", {"chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"}})
    assert ghi_goi == []


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ho_so_tai_khoan WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM traces WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _len_pro(sub: str) -> None:
    with get_engine().begin() as c:
        c.execute(
            text(
                "UPDATE users SET plan = 'pro', plan_het_han = now() + interval '30 days' WHERE sub = CAST(:s AS uuid)"
            ),
            {"s": sub},
        )


def _phien_8_luot(sub: str) -> str:
    pid = hoi_thoai.tao_phien(sub, "tôi là nhân viên, hợp đồng không xác định thời hạn, sắp nghỉ việc")
    for i in range(1, 9):
        hoi_thoai.ghi_luot(pid, f"câu {i}", {"answer": f"trả lời {i}", "citations": []}, f"t{i}")
    return pid


@pytest.mark.integration
def test_cap_nhat_phien_gop_tom_tat_va_ho_so_free_khong_ghi_tai_khoan(nguoi):
    pid = _phien_8_luot(nguoi)
    llm = LlmGia(
        {
            "tom_tat": "Người hỏi là nhân viên sắp nghỉ việc, đã hỏi về báo trước.",
            "ho_so": {
                "chu_the": "người lao động",
                "loai_hop_dong": "không xác định thời hạn",
                "tham_nien": "",
                "vung_luong": "",
                "thoi_diem": "",
                "van_ban_da_co": "",
                "vu_viec": "sắp nghỉ việc; theo Điều 35",
            },
        }
    )
    bo_nho.cap_nhat_phien(pid, nguoi, llm=llm, model="gia")
    bn = hoi_thoai.bo_nho_cua_phien(pid)
    assert bn["tom_tat"].startswith("Người hỏi") and bn["tom_tat_den_thu_tu"] == 2  # 8 - K(6) = 2
    assert bn["ho_so"]["chu_the"] == {"gia_tri": "người lao động", "nguon": "nguoi_noi"}
    assert "vu_viec" not in bn["ho_so"]  # "theo Điều 35" vướng lưới chặn
    prompt = llm.da_goi[0][-1]["content"]
    assert "câu 1" in prompt and "câu 2" in prompt and "câu 8" in prompt and "câu 5" not in prompt
    assert bo_nho.ho_so_tai_khoan(nguoi) == []  # Free không ghi tài khoản
    with get_engine().connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM traces WHERE endpoint = :e AND user_sub = CAST(:s AS uuid)"),
                {"e": bo_nho.ENDPOINT_TRACE, "s": nguoi},
            ).scalar_one()
            == 1
        )


@pytest.mark.integration
def test_pro_gop_vao_tai_khoan_va_khong_ghi_nho_chan(nguoi):
    _len_pro(nguoi)
    pid = _phien_8_luot(nguoi)
    ho_so = {k: "" for k in bo_nho.KHOA_HO_SO} | {"chu_the": "người lao động", "tham_nien": "3 năm"}
    bo_nho.cap_nhat_phien(pid, nguoi, llm=LlmGia({"tom_tat": "x", "ho_so": ho_so}), model="gia")
    muc = {m["khoa"]: m["gia_tri"] for m in bo_nho.ho_so_tai_khoan(nguoi)}
    assert muc == {"chu_the": "người lao động", "tham_nien": "3 năm"}
    assert bo_nho.ho_so_tu_tai_khoan(nguoi)["tham_nien"] == {"gia_tri": "3 năm", "nguon": "tai_khoan"}
    hoi_thoai.dat_khong_ghi_nho(nguoi, pid, True)
    bo_nho.cap_nhat_phien(
        pid, nguoi, llm=LlmGia({"tom_tat": "y", "ho_so": ho_so | {"tham_nien": "5 năm"}}), model="gia"
    )
    assert hoi_thoai.bo_nho_cua_phien(pid)["tom_tat"] == "x"  # không tóm tắt, không gộp
    assert {m["khoa"]: m["gia_tri"] for m in bo_nho.ho_so_tai_khoan(nguoi)}["tham_nien"] == "3 năm"
    bo_nho.dat_ghi_nho(nguoi, False)
    assert bo_nho.doc_ghi_nho(nguoi) is False
    bo_nho.sua_khoa_tai_khoan(nguoi, "tham_nien", "4 năm")
    assert {m["khoa"]: m["gia_tri"] for m in bo_nho.ho_so_tai_khoan(nguoi)}["tham_nien"] == "4 năm"
    bo_nho.xoa_khoa_tai_khoan(nguoi, "chu_the")
    bo_nho.xoa_het_tai_khoan(nguoi)
    assert bo_nho.ho_so_tai_khoan(nguoi) == []


@pytest.mark.integration
def test_llm_loi_thi_giu_ban_cu(nguoi):
    pid = _phien_8_luot(nguoi)
    hoi_thoai.ghi_bo_nho(pid, "cũ", 1, {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}})

    class LlmNo:
        def chat(self, *a, **k):
            raise RuntimeError("mạng")

    bo_nho.cap_nhat_phien(pid, nguoi, llm=LlmNo(), model="gia")
    bn = hoi_thoai.bo_nho_cua_phien(pid)
    assert (
        bn["tom_tat"] == "cũ"
        and bn["tom_tat_den_thu_tu"] == 1
        and bn["ho_so"]["chu_the"]["gia_tri"] == "người lao động"
    )


@pytest.mark.integration
def test_cap_nhat_phien_tom_tat_dinh_danh_giu_ban_cu(nguoi):
    """Tóm tắt hợp lệ về Điều/số hiệu nhưng lọt một số điện thoại — vẫn phải bị chặn
    (finding 3, review round 1): lưới chặn của tóm tắt dùng chung với hồ sơ."""
    pid = _phien_8_luot(nguoi)
    hoi_thoai.ghi_bo_nho(pid, "cũ", 1, {})
    llm = LlmGia({"tom_tat": "Liên hệ 0912345678 để biết thêm.", "ho_so": {k: "" for k in bo_nho.KHOA_HO_SO}})
    bo_nho.cap_nhat_phien(pid, nguoi, llm=llm, model="gia")
    assert hoi_thoai.bo_nho_cua_phien(pid)["tom_tat"] == "cũ"  # số điện thoại vướng lưới chặn, giữ bản cũ


@pytest.mark.integration
def test_bo_nho_trace_khong_lam_bien_dang_hoat_dong_va_phan_loai(nguoi):
    """Finding 4 (review round 1): một dòng trace của chính `bo_nho` không được lọt
    vào lịch hoạt động hay bảng phân loại câu hỏi mà người dùng nhìn thấy trên hồ sơ."""
    pid = _phien_8_luot(nguoi)
    llm = LlmGia({"tom_tat": "x", "ho_so": {k: "" for k in bo_nho.KHOA_HO_SO}})
    bo_nho.cap_nhat_phien(pid, nguoi, llm=llm, model="gia")
    tong = ho_so.tong_hop(nguoi)
    assert tong["hoat_dong"] == []  # dòng trace duy nhất là của bo_nho — không tính là hoạt động
    assert tong["phan_loai"] == []  # và không rơi vào phân loại (kể cả về "Khác")


@pytest.mark.integration
def test_luot_8_van_biet_vai_va_loai_hop_dong(nguoi):
    """Lỗi chủ dự án thấy 2026-09-09: sau lượt 3 agent quên vai. Nay hồ sơ giữ vai qua 8 lượt
    và hoi_lai không hỏi lại hai chiều đã biết."""
    from src.agents.nodes import hoi_lai

    pid = _phien_8_luot(nguoi)
    ho_so = {k: "" for k in bo_nho.KHOA_HO_SO} | {
        "chu_the": "người lao động",
        "loai_hop_dong": "không xác định thời hạn",
    }
    bo_nho.cap_nhat_phien(pid, nguoi, llm=LlmGia({"tom_tat": "đã bàn về nghỉ việc", "ho_so": ho_so}), model="gia")
    bn = hoi_thoai.bo_nho_cua_phien(pid)
    da_biet = frozenset(k for k, v in bn["ho_so"].items() if v.get("gia_tri"))
    cau = hoi_lai.dung_cau_hoi_lai([], da_biet=da_biet)
    assert "người lao động hay phía công ty" not in cau and "thời hạn thế nào" not in cau
    assert "Vai của bạn: người lao động" in bo_nho.khoi_tinh_huong(bn["ho_so"])


def test_cap_nhat_phien_bo_qua_khi_phien_khong_thuoc_nguoi_goi(monkeypatch):
    """`bo_nho_cua_phien` không lọc theo chủ (caller đã kiểm), nhưng `cap_nhat_phien`
    GỘP hồ sơ phiên vào hồ sơ TÀI KHOẢN của `user_sub`. Một cặp (phiên, sub) lệch
    nhau vì thế là một đường rò dữ liệu giữa hai tài khoản — phòng thủ theo chiều
    sâu: giá trị cần so đã nằm sẵn trong `bn`."""
    ghi = []
    monkeypatch.setattr(
        hoi_thoai,
        "bo_nho_cua_phien",
        lambda pid: {"ho_so": {}, "khong_ghi_nho": False, "tom_tat": None, "tom_tat_den_thu_tu": 0, "user_sub": "chu-that"},
    )
    monkeypatch.setattr(hoi_thoai, "dem_luot", lambda pid: ghi.append(pid) or 1)
    bo_nho.cap_nhat_phien("pid", "ke-khac")
    assert ghi == [], "không được đọc/ghi gì thêm cho một phiên không thuộc người gọi"
