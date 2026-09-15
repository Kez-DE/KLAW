"""Tính toàn vẹn của tập mẫu ứng viên (spec 2026-09-15 §SC-002).

Cùng vai `test_golden_qa.py` với `golden_qa.yaml`: kiểm CẤU TRÚC tập dữ liệu,
không gọi mô hình, không tốn tiền.

Ba điều dễ sai nhất khi dựng tập đánh giá, và cả ba đều hỏng im lặng:

1. Một khoá nhãn gõ sai sẽ không bao giờ khớp, và hệ thống bị chấm trượt một
   trường nó rút đúng.
2. Một `loai` không có thật làm cả mục đó không chạy được.
3. Một nhãn không xuất hiện trong chính tài liệu thì không ai rút ra được — đó
   là lỗi của tập mẫu, không phải của hệ thống.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.agents.nodes.gom_du_kien import truong_cua
from src.services.doc_tai_lieu import doc

GOC = Path("eval/datasets/tai_lieu_mau")
BO = yaml.safe_load((GOC / "manifest_candidates.yaml").read_text(encoding="utf-8"))
MUC = BO["items"]


@pytest.fixture(scope="module", autouse=True)
def _dung_mau():
    subprocess.run([sys.executable, str(GOC / "dung_mau.py")], check=True, capture_output=True)


def test_CHUA_duyet_thi_co_phai_noi_ro():
    """Một con số không có người đứng sau thì không vào báo cáo được."""
    assert BO["da_nguoi_duyet"] is False
    assert BO["duyet_boi"] == ""


def test_id_khong_trung():
    ids = [m["id"] for m in MUC]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("m", MUC, ids=[m["id"] for m in MUC])
def test_loai_co_that_va_MOI_khoa_nhan_la_truong_co_that(m):
    khoa = {t["key"] for t in truong_cua(m["loai"])}
    assert khoa, f"loại {m['loai']} không có trường nào — sai tên loại?"
    la = set(m["nhan"]) - khoa
    assert not la, f"khoá nhãn không tồn tại ở loại {m['loai']}: {sorted(la)}"


@pytest.mark.parametrize("m", MUC, ids=[m["id"] for m in MUC])
def test_gia_tri_co_lua_chon_phai_nam_trong_lua_chon(m):
    meta = {t["key"]: t for t in truong_cua(m["loai"])}
    for k, v in m["nhan"].items():
        lua_chon = meta[k].get("lua_chon")
        if lua_chon:
            assert v in lua_chon, f"{m['id']}.{k} = {v!r} không nằm trong {lua_chon}"


@pytest.mark.parametrize("m", MUC, ids=[m["id"] for m in MUC])
def test_tep_dung_duoc_va_doc_lai_duoc(m):
    tep = GOC / m["tep"]
    assert tep.exists(), "chạy dung_mau.py trước"
    t = doc(tep.name, tep.read_bytes())
    assert t.don_vi and t.so_ky_tu > 0


@pytest.mark.parametrize("m", MUC, ids=[m["id"] for m in MUC])
def test_MOI_nhan_so_deu_XUAT_HIEN_trong_tai_lieu(m):
    """Nhãn không có trong tài liệu là lỗi của tập mẫu, không phải của hệ thống."""
    tep = GOC / m["tep"]
    chu = " ".join(d.noi_dung for d in doc(tep.name, tep.read_bytes()).don_vi)
    khong_dung = "".join(c for c in chu if c.isdigit())
    for k, v in m["nhan"].items():
        if str(v).isdigit():
            assert str(v) in khong_dung, f"{m['id']}: nhãn {k}={v} không xuất hiện trong tài liệu"


def test_ca_bay_thieu_truong_KHONG_co_nhan_cho_truong_do():
    """Tài liệu không nói lương chính thức thì nhãn cũng không được có."""
    m = next(x for x in MUC if x["id"] == "thu-viec-thieu-luong-chinh-thuc")
    assert "luong_chinh_thuc" not in m["nhan"]
    chu = " ".join(d.noi_dung for d in doc(m["tep"], (GOC / m["tep"]).read_bytes()).don_vi)
    assert "chính thức" not in chu.lower()
