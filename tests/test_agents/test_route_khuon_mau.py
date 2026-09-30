"""Định tuyến khi một khuôn mẫu đang mở — thiết kế `khuon-mau-thiet-ke.md` §4, §8.

Router quyết định, không có phép đè nào sau nó: điều thay đổi là router THẤY bản thảo
Word đang mở (`{dang_soan}`, chỉ từ dữ liệu repo). Lượt soạn không đính kèm gì không kéo
tệp tải lên cũ vào; lượt ảnh không nhận khuôn mẫu làm nền.
"""

import json
from pathlib import Path

import pytest

from src.agents import graph_tra_cuu as g
from src.agents.nodes import route as r
from src.agents.nodes.route import Intent

KM = {
    "document": "# HỢP ĐỒNG BỊA\n",
    "audit": {"so_dieu_khoan": 7, "khung": {"tieu_de": "HỢP ĐỒNG BỊA"}},
    "viec_id": "v-km",
    "phep_sua": [],
    "nguon": "khuon_mau",
    "loai_khuon": "hdld",
}
TQ = {**KM, "loai_khuon": None, "audit": {"so_dieu_khoan": 3, "khung": {"tieu_de": "HỢP ĐỒNG BỊA"}}}
HTML = {"document": "# ĐƠN\n", "audit": {}, "viec_id": None, "phep_sua": None, "nguon": None, "loai_khuon": None}
TAI_LEN = {**HTML, "viec_id": "v-up", "phep_sua": [], "nguon": "tai_len"}


def test_dang_soan_khuon_mau_theo_ten_registry_va_so_dieu():
    assert r._dang_soan(None, KM) == "hợp đồng lao động (bản thảo Word đang mở, 7 điều)"


def test_dang_soan_tu_soan_khong_bao_gio_mang_tieu_de_mo_hinh():
    s = r._dang_soan(None, TQ)
    assert s == "văn bản tự soạn (bản thảo Word đang mở, 3 điều)" and "BỊA" not in s


@pytest.mark.parametrize("bt", [HTML, TAI_LEN, None])
def test_dang_soan_ban_html_hay_tep_tai_len_la_khong(bt):
    assert r._dang_soan(None, bt) == "(không)"


def test_phien_checklist_giu_dong_cua_no():
    assert r._dang_soan({"loai": "hdld", "facts": {"a": 1}}, KM) == "hợp đồng lao động (đã có 1 dữ kiện)"


class _LLM:
    def __init__(self, intent: str):
        self.intent, self.prompt = intent, None

    def chat(self, model, messages, json_schema=None, **kw):
        from src.services.llm import Usage

        self.prompt = messages[-1]["content"]
        return json.dumps(
            {
                "intent": self.intent,
                "loai_van_ban": "khong_ro",
                "thay_the": [],
                "ly_do": "",
                "dang_tra_loi": "van_xuoi",
                "y_dinh_phu": "khong",
            }
        ), Usage(1, 1, 0.0)


@pytest.mark.parametrize(
    ("cau", "intent"),
    [
        ("Giải thích quy định về sửa chữa tài sản thuê theo Bộ luật Dân sự.", "tra_cuu"),
        ("thêm điều về phạt vi phạm", "soan_thao"),
        ("bỏ điều 5", "soan_thao"),
    ],
)
def test_router_thay_ban_thao_va_khong_bi_de(cau, intent):
    llm = _LLM(intent)
    ra = r.route(
        {"query": cau, "ban_thao_tong_quat_dang_mo": KM, "tai_lieu_phien": []},
        llm,
        "m",
        prompt_path=Path("prompts/route.v5.md"),
    )
    assert "ĐANG SOẠN: hợp đồng lao động (bản thảo Word đang mở, 7 điều)" in llm.prompt
    assert ra["intent"] == Intent(intent), "không phép đè nào sau router"


def test_enum_loai_router_gom_ca_khuon_mau():
    assert set(r.schema_v2()["properties"]["loai_van_ban"]["enum"]) >= {"hdld", "don_khoi_kien", "cong_van"}


TL = [{"id": "up-1", "ten_tep": "cu.docx"}]


@pytest.mark.parametrize(
    ("intent", "ids", "nhe", "mong"),
    [
        (Intent.soan_thao, [], KM, []),
        (Intent.soan_thao, ["up-2"], KM, ["up-2"]),
        (Intent.tai_lieu, [], KM, ["up-1"]),
        (Intent.soan_thao, [], HTML, ["up-1"]),
    ],
    ids=["soan-khuon-mau-khong-keo", "dinh-kem-van-doc", "hoi-tai-lieu-van-keo", "ban-html-van-keo"],
)
def test_khong_keo_tep_cu_chi_khi_soan_va_khuon_mau_dang_mo(intent, ids, nhe, mong):
    st = {"intent": intent, "tai_lieu_ids": ids, "tai_lieu_phien": TL, "ban_thao_tong_quat_dang_mo": nhe}
    assert g.tai_lieu_cua_luot(st) == mong


def test_nap_ban_thao_dang_mo_ba_loai(monkeypatch):
    goi: list = []
    monkeypatch.setattr(
        g.ban_thao,
        "ban_thao_tong_quat_dang_mo_nhe",
        lambda sub, pid, viec_id: goi.append(viec_id) or {"viec_id": viec_id},
    )
    st = {"user_sub": "s", "hoi_thoai_id": "h", "ban_thao_tong_quat_dang_mo": KM}
    # Không tài liệu: khuôn mẫu là nền v3, không đọc lại gì.
    assert g._nap_ban_thao_dang_mo(st, []) == st and goi == []
    # Ảnh (không khuôn gốc): không nền nào, chỉ biết có khuôn mẫu đang mở.
    anh = g._nap_ban_thao_dang_mo(st, [{"viec_id": "anh", "co_khuon_goc": False}])
    assert anh["ban_thao_tong_quat_dang_mo"] is None and anh["khuon_mau_dang_mo"] == KM and goi == []
    # Tệp có khuôn gốc: đọc lại theo chính tệp đó, như trước.
    up = g._nap_ban_thao_dang_mo(st, [{"viec_id": "up", "co_khuon_goc": True, "dinh_dang": "docx"}])
    assert goi == ["up"] and up["ban_thao_tong_quat_dang_mo"] == {"viec_id": "up"}
