"""Trang THẬT của khuôn mẫu nhóm hành chính — cùng đường LibreOffice của khuôn gốc.

Cần `soffice` + `pdftoppm`; không có thì bỏ qua (như `test_khuon_mau_trang.py`, nơi mọi
loại registry đã được kiểm ≤ 10 trang, quốc hiệu một dòng, số trang từ trang 2). Mỗi ca
một lượt LibreOffice (~300 MB), chạy tuần tự. Khoá ba điều riêng của nhóm:

1. Phép dò của `/ban-thao/{id}/trang` định vị được mọi chỗ trống của các bên — cả trên
   tệp hai phần (quyết định ban hành + văn bản kèm theo).
2. Văn bản kèm theo bắt đầu ở trang mới; khối ký của quyết định ở trang trước nó; số
   trang của văn bản kèm theo đếm lại từ 1, trang đầu của nó không số.
3. Khối ký hai cột (biên bản, giấy ủy quyền): dòng họ tên hai người thẳng hàng.
4. Trang có chữ ký luôn có chữ của thân văn bản ("./." của đoạn cuối) phía trên.
"""

import shutil

import pytest

from src.services import ban_thao, dung_trang
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import _tu_pdf, doc
from src.services.tai_lieu import _hang_don_vi
from tests.test_services.test_khuon_mau_hanh_chinh import C, _spec

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
    # Phụ lục I, Phần I mục 7 ("không hiển thị số trang thứ nhất") và Phần III mục 1.đ
    # (phụ lục "được đánh số riêng"): trang đầu văn bản kèm theo không số, trang sau là "2".
    so = {n: [chu for _, chu, hop in ds if chu.isdigit() and hop[1] < _LE_TREN] for n, ds in tu.items()}
    assert so[ky] == [] and so[kem] == []
    if kem + 1 in so:
        assert so[kem + 1] == ["2"]


# Lề trên (pt): số trang nằm trong lề trên 20 mm (`test_khuon_mau_trang.py`).
_LE_TREN = 56
# Bảy điều của một quyết định kỷ luật thật cỡ (bản dựng thử 2026-09-29): đoạn cuối rơi sát
# chân trang 1, trước khi đoạn cuối giữ cùng trang với khối ký thì trang 2 chỉ có Nơi nhận
# và chữ ký.
_KY_LUAT = [
    (
        "Hình thức xử lý kỷ luật",
        f"Thi hành kỷ luật lao động bằng hình thức khiển trách đối với ông (bà) {C}, Nhân viên kho, Phòng Hậu cần.",
    ),
    (
        "Hành vi vi phạm và lỗi",
        f"Người lao động đã tự ý bỏ vị trí làm việc trong ca trực ngày {C}; hành vi có lỗi cố ý và đã được người lao động thừa nhận tại cuộc họp xử lý kỷ luật.",
    ),
    (
        "Căn cứ nội quy",
        f"Hành vi trên vi phạm quy định về trật tự tại nơi làm việc tại khoản {C} Điều {C} Nội quy lao động của Công ty.",
    ),
    (
        "Thời hiệu",
        "Hành vi vi phạm được xử lý trong thời hiệu xử lý kỷ luật lao động theo quy định của pháp luật lao động.",
    ),
    (
        "Tổ chức đại diện người lao động",
        "Cuộc họp xử lý kỷ luật lao động có sự tham gia của Ban Chấp hành Công đoàn cơ sở Công ty.",
    ),
    ("Quyền tự bào chữa", "Người lao động có mặt tại cuộc họp, được tự bào chữa và đã ký biên bản cuộc họp."),
    (
        "Hiệu lực và thi hành",
        "Quyết định này có hiệu lực kể từ ngày ký. Phòng Hành chính - Nhân sự, Phòng Hậu cần và người lao động nêu trên chịu trách nhiệm thi hành Quyết định này.",
    ),
]
_CAN_CU_KY_LUAT = [
    {"dong": "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", "doc_id": "139264"},
    {
        "dong": "Căn cứ Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 của Chính phủ quy định chi tiết và"
        " hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động.",
        "doc_id": "145",
    },
]


def test_trang_co_chu_ky_luon_co_chu_cua_than_van_ban():
    """Owner: "chuẩn chỗ kí, có đầu, giữa, đuôi". Một trang chỉ có Nơi nhận và chữ ký thì
    ai cũng thay được các trang phía trên: đoạn cuối thân ("./.") phải cùng trang chữ ký."""
    dieu = [{"key": None, "ten": t, "doan": [x]} for t, x in _KY_LUAT]
    pdf = dung_trang.dung_pdf(km.dung_docx(_spec("quyet_dinh_ky_luat", dieu=dieu, can_cu=_CAN_CU_KY_LUAT))[0])
    tu = _tu_pdf(pdf)
    trang = {n: [chu for _, chu, _ in ds] for n, ds in tu.items()}
    ky = next(n for n, ds in trang.items() if "(Chữ" in ds and "thẩm" in ds)
    assert any(chu.endswith("./.") for chu in trang[ky]), trang[ky][:12]


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
