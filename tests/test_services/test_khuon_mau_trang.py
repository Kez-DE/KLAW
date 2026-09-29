"""Trang THẬT của khuôn mẫu — cùng đường LibreOffice của khuôn gốc (`dung_trang`),
thiết kế `khuon-mau-thiet-ke.md` §6 ("`NGAN_SACH_KY_TU` is measured") và §8.

Cần `soffice` + `pdftoppm`; không có thì bỏ qua (như `test_dung_trang.py`). Mỗi ca một
lượt LibreOffice (~300 MB), chạy tuần tự.

Khoá bốn điều:
1. Mỗi mẫu có trong registry dựng ≤ 10 trang (trần `ck_khuon_goc_so_trang`).
2. Bản TỐI ĐA mỗi bố cục — 25 Điều, chữ đủ `NGAN_SACH_KY_TU` — dựng ≤ 9 trang: một
   trang dư cho Liberation Serif so với Times New Roman.
3. Quốc hiệu trên MỘT dòng; trang 1 không số, trang 2 mang "2".
4. Phép dò của `/ban-thao/{id}/trang` định vị được mọi chỗ trống của các bên.
"""

import shutil

import pytest

from src.services import ban_thao, dung_trang
from src.services import khuon_mau as km
from src.services.doc_tai_lieu import _tu_pdf, doc
from src.services.tai_lieu import _hang_don_vi

pytestmark = pytest.mark.skipif(
    not (shutil.which("soffice") and shutil.which("pdftoppm")), reason="cần LibreOffice và poppler"
)

_CAU = (
    "Các bên thực hiện đúng nội dung đã thỏa thuận, thông báo cho nhau bằng văn bản khi có thay đổi "
    "và phối hợp giải quyết kịp thời những vướng mắc phát sinh trong quá trình thực hiện. "
)


def _dieu_toi_da() -> list[dict]:
    """25 Điều, mỗi Điều chia đoạn ≤ 1.200 ký tự, tổng đúng `NGAN_SACH_KY_TU`."""
    moi = km.NGAN_SACH_KY_TU // km.TOI_DA_DIEU
    ra = []
    for n in range(km.TOI_DA_DIEU):
        chu = (_CAU * (moi // len(_CAU) + 1))[:moi].rstrip() + "."
        doan = [chu[i : i + 400].strip() for i in range(0, len(chu), 400)]
        ra.append({"key": None, "ten": f"Nội dung thỏa thuận thứ {n + 1}", "doan": doan})
    return ra


_BEN = [{"khoa": "ben_a", "vai": "Bên thứ nhất", "loai": "to_chuc"}, {"khoa": "ben_b", "vai": "Bên thứ hai"}]
_CAN_CU = [
    {"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015;", "doc_id": "95942"},
    {"dong": "Căn cứ Luật Hôn nhân và gia đình số 52/2014/QH13 ngày 19 tháng 6 năm 2014.", "doc_id": "36870"},
]


def _pdf(spec: dict) -> bytes:
    return dung_trang.dung_pdf(km.dung_docx(spec)[0])


@pytest.mark.parametrize("bo_cuc", km.BO_CUC)
def test_ban_toi_da_moi_bo_cuc_trong_9_trang(bo_cuc):
    spec = km.spec_tu(
        {**km.khung_tong_quat(bo_cuc, _BEN), "loai": None},
        tieu_de="Thỏa thuận hợp tác",
        trich_yeu="về việc hợp tác",
        can_cu=_CAN_CU,
        dieu=_dieu_toi_da(),
    )
    assert sum(len(x) for d in spec["dieu"] for x in d["doan"]) >= km.NGAN_SACH_KY_TU - km.TOI_DA_DIEU
    assert dung_trang.so_trang_pdf(_pdf(spec)) <= 9


@pytest.mark.parametrize("loai", sorted(km.cac_loai()))
def test_moi_mau_registry_trong_10_trang_quoc_hieu_mot_dong_so_trang_tu_trang_2(loai):
    dieu, _ = km.them_dieu_bat_buoc(_dieu_toi_da()[:4], loai)
    pdf = _pdf(km.spec_tu(km.nap(loai), tieu_de=None, trich_yeu="về việc thử", can_cu=_CAN_CU, dieu=dieu))
    assert dung_trang.so_trang_pdf(pdf) <= 10
    tu = _tu_pdf(pdf)
    dong_quoc_hieu = {round(hop[1]) for _, chu, hop in tu[1] if chu in ("CỘNG", "NAM")}
    assert len(dong_quoc_hieu) == 1, "quốc hiệu vỡ dòng"
    # Trang 1 không mang số trang ở lề trên; trang 2 (nếu có) mang "2" ở lề trên.
    le_tren = 56
    assert not any(chu == "1" and hop[1] < le_tren for _, chu, hop in tu[1])
    if len(tu) > 1:
        assert any(chu == "2" and hop[1] < le_tren for _, chu, hop in tu[2])


def test_phep_do_dinh_vi_moi_cho_trong_cua_cac_ben():
    """Cùng đường `/ban-thao/{id}/trang`: bản dò (`ban_thao.ban_do`) + `dung_trang.dung`."""
    docx, ban_do_ = km.dung_docx(km.spec_tu(km.nap("don_khoi_kien"), tieu_de=None, trich_yeu=None, can_cu=[], dieu=[]))
    dv = [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d["chi_so"] for d in dv if d.get("dia_chi")}
    cua_ben = {(theo[k], so) for k, ds in ban_do_.items() for so, kh in enumerate(ds) if kh and kh[0] != "van_ban"}
    _, png, vi_tri = dung_trang.dung("docx", docx, "thu-khuon-mau", None, ban_thao.ban_do("docx", dv, []))
    assert png and cua_ben <= set(vi_tri), sorted(cua_ben - set(vi_tri))
