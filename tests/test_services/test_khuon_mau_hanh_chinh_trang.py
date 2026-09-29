"""Trang THẬT của khuôn mẫu nhóm hành chính — cùng đường LibreOffice của khuôn gốc.

Cần `soffice` + `pdftoppm`; không có thì bỏ qua (như `test_khuon_mau_trang.py`, nơi mọi
loại registry đã được kiểm ≤ 10 trang, quốc hiệu một dòng, số trang từ trang 2). Mỗi ca
một lượt LibreOffice (~300 MB), chạy tuần tự. Khoá ba điều riêng của nhóm:

1. Phép dò của `/ban-thao/{id}/trang` định vị được mọi chỗ trống của các bên — cả trên
   tệp hai phần (quyết định ban hành + văn bản kèm theo).
2. Văn bản kèm theo bắt đầu ở trang mới; khối ký của quyết định ở trang trước nó.
3. Khối ký hai cột (biên bản, giấy ủy quyền): dòng họ tên hai người thẳng hàng.
"""

import shutil

import pytest

from src.services import ban_thao, dung_trang
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import _tu_pdf, doc
from src.services.tai_lieu import _hang_don_vi
from tests.test_services.test_khuon_mau_hanh_chinh import _spec

pytestmark = pytest.mark.skipif(
    not (shutil.which("soffice") and shutil.which("pdftoppm")), reason="cần LibreOffice và poppler"
)


def _dv(docx: bytes) -> list[dict]:
    return [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]


@pytest.mark.parametrize("loai", ["bien_ban_hop_hdqt", "giay_uy_quyen", "quy_che_noi_bo", "giay_uy_quyen_to_chuc"])
def test_phep_do_dinh_vi_moi_cho_trong_cua_cac_ben(loai):
    docx, ban_do_ = km.dung_docx(_spec(loai))
    dv = _dv(docx)
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d["chi_so"] for d in dv if d.get("dia_chi")}
    cua_ben = {(theo[k], so) for k, ds in ban_do_.items() for so, kh in enumerate(ds) if kh and kh[0] != "van_ban"}
    assert cua_ben
    _, png, vi_tri = dung_trang.dung("docx", docx, "thu-khuon-mau-hc", None, ban_thao.ban_do("docx", dv, []))
    assert png and cua_ben <= set(vi_tri), sorted(cua_ben - set(vi_tri))


def test_van_ban_kem_theo_bat_dau_trang_moi_sau_khoi_ky_quyet_dinh():
    tu = _tu_pdf(dung_trang.dung_pdf(km.dung_docx(_spec("noi_quy"))[0]))
    trang = {n: " ".join(chu for _, chu, _ in ds) for n, ds in tu.items()}
    ky = next(n for n, s in trang.items() if "(Chữ ký của người có thẩm quyền," in s)
    kem = next(n for n, s in trang.items() if "(Kèm theo Quyết định số" in s)
    assert kem == ky + 1
    assert "NỘI QUY LAO ĐỘNG" in trang[kem] and "QUYẾT ĐỊNH:" not in trang[kem]


@pytest.mark.parametrize(
    ("loai", "ben"),
    [("bien_ban_hop_hdqt", ("thu_ky", "chu_toa")), ("giay_uy_quyen", ("ben_duoc_uy_quyen", "ben_uy_quyen"))],
)
def test_ho_ten_hai_nguoi_ky_thang_hang(loai, ben):
    docx, ban_do_ = km.dung_docx(_spec(loai))
    dv = _dv(docx)
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}
    ten = {
        "thu_ky": "Lê Thu Hà",
        "chu_toa": "Trần Quốc Bảo",
        "ben_duoc_uy_quyen": "Hoàng Thị Mai",
        "ben_uy_quyen": "Hoàng Văn Nam",
    }
    phep = [
        {"loai": "dien", "don_vi": theo[k]["chi_so"], "cho_trong": so, "gia_tri": ten[kh[0]]}
        for k, ds in ban_do_.items()
        for so, kh in enumerate(ds)
        if kh and kh[0] in ben and kh[1] == "ho_ten" and theo[k].get("bang")
    ]
    assert len(phep) == 2
    ban, bc = ap_dung_docx(docx, dv, phep)
    assert bc["bo_qua"] == []
    tu = _tu_pdf(dung_trang.dung_pdf(ban))
    y = {chu: round(hop[1]) for ds in tu.values() for _, chu, hop in ds if chu in ("Hà", "Bảo", "Mai", "Nam")}
    a, b = (ten[x].split()[-1] for x in ben)
    assert abs(y[a] - y[b]) <= 2, y
