"""Registry khuôn mẫu (`config/khuon_mau/*.yaml`) — thiết kế `khuon-mau-thiet-ke.md` §7.

Ba điều khoá ở đây, không DB, không mô hình:

1. Mọi mục nạp được qua `khuon_mau.nap` (bố cục, trường, bên, mục thân đều đã biết).
2. Nguồn của mỗi mục là trang chính thức, hoặc ghi rõ "tương tự"/"tự dựng" kèm lý do.
3. Một mẫu CHÍNH THỨC tái hiện ĐÚNG chữ tĩnh của tệp gốc, đúng thứ tự: dãy đoạn của
   bản dựng bằng danh sách đã chép tay từ tệp (`du_lieu/nhan_mau_chinh_thuc.yaml`).
"""

import io
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from lxml import etree

from src.agents.graph_soan_thao import cac_loai as cac_checklist
from src.services import khuon_mau as km

NHAN = yaml.safe_load((Path(__file__).parent / "du_lieu" / "nhan_mau_chinh_thuc.yaml").read_text(encoding="utf-8"))
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _chinh_thuc(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return url.startswith("https://") and (
        host.endswith(".gov.vn") or host == "vbpl.vn" or host.endswith("chinhphu.vn")
    )


@pytest.mark.parametrize("loai", sorted(km.cac_loai()))
def test_moi_muc_nap_duoc_va_ghi_nguon(loai):
    d = km.nap(loai)
    ng = d["nguon"]
    if ng["loai"] == "mau_chinh_thuc":
        assert _chinh_thuc(ng["url"]), ng["url"]
        assert re.fullmatch(r"[0-9a-f]{64}", ng["sha256"])
    else:
        assert ng.get("ghi_chu") or ng.get("van_ban"), "mẫu tương tự/tự dựng phải nói vì sao"
        assert not ng.get("url") or _chinh_thuc(ng["url"])


@pytest.mark.xfail(strict=True, reason="D3 dựng mục registry cho cả 29 checklist; bỏ dấu này khi xong")
def test_moi_checklist_co_khuon_mau():
    assert cac_checklist() <= km.cac_loai()


def _doan_cua_ban_dung(docx: bytes) -> list[str]:
    """Chữ từng `w:p` của bản dựng theo thứ tự tài liệu, bỏ "……" và U+2060 (`km.NOI`, vô
    hình), gộp khoảng trắng."""
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        goc = etree.fromstring(z.read("word/document.xml"))
    ra = []
    for p in goc.iter(f"{_W}p"):
        chu = "".join(t.text or "" for t in p.iter(f"{_W}t")).replace(km.CHO, "").replace(km.NOI, "")
        if chu := " ".join(chu.split()):
            ra.append(chu)
    return ra


@pytest.mark.parametrize("loai", sorted(NHAN))
def test_mau_chinh_thuc_tai_hien_dung_chu_tinh_va_thu_tu(loai):
    d = km.nap(loai)
    assert d["nguon"]["loai"] == "mau_chinh_thuc"
    assert (d["nguon"]["tep_d2"], d["nguon"]["sha256"]) == (NHAN[loai]["tep_d2"], NHAN[loai]["sha256"])
    docx, _ = km.dung_docx(km.spec_tu(d, tieu_de=None, trich_yeu=None, can_cu=[], dieu=[]))
    assert _doan_cua_ban_dung(docx) == NHAN[loai]["nhan"]


def test_moi_mau_chinh_thuc_co_nhan_da_ghi():
    chinh_thuc = {lo for lo in km.cac_loai() if km.nap(lo)["nguon"]["loai"] == "mau_chinh_thuc"}
    assert chinh_thuc == set(NHAN)


@pytest.mark.parametrize(
    ("sua", "loi"),
    [
        ({"bo_cuc": "la"}, "bo_cuc"),
        ({"than": [{"ben": "khong_co"}]}, "bên lạ"),
        ({"than": [{"dong": "Tên: {truong_bia}"}]}, "trường lạ"),
        ({"nguon": {"loai": "mau_chinh_thuc", "url": "https://x.gov.vn/a"}}, "sha256"),
    ],
)
def test_muc_hong_no_luc_nap(sua, loi):
    d = {**yaml.safe_load((km.THU_MUC / "hdld.yaml").read_text(encoding="utf-8")), **sua}
    assert loi in (km._kiem_muc(d, "hdld") or "")
