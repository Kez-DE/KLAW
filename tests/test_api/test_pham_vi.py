"""`/pham-vi` phải đếm ĐỘ PHỦ THẬT, không đếm số dòng trong bảng.

ĐO ĐƯỢC 2026-09-02: trang xếp **125** văn bản vào tầng "có toàn văn" khi thật ra
chỉ **49** — phóng đại độ phủ 2,5 lần, trên đúng con số đưa cho khách xem.

Nguyên nhân: `_pham_vi` phân tầng theo `so_dieu_khoan > 0`, và ruling ở đó viết
rõ lý do — "`depth` là ý định lúc thu thập, còn số điều khoản là kết quả; văn bản
đánh dấu 'deep' mà nạp hỏng thì thuộc tầng nông trên thực tế". Lý lẽ ĐÚNG. Cái
phá nó là `migrations/016_tang_nong.sql`: nó chèn cho MỌI văn bản không-metadata
đúng một hàng `cap='mo_dau'` mang tên văn bản, nên `so_dieu_khoan > 0` thành đúng
cho cả hai tầng (125 hàng `mo_dau` = 49 deep + 76 shallow).

Bản sửa GIỮ nguyên tắc gốc và chỉ làm nó miễn nhiễm với 016: đếm điều khoản
TRÍCH DẪN ĐƯỢC (`cap <> 'mo_dau'`). Một văn bản `deep` nạp hỏng vẫn có 0 và vẫn
rơi đúng vào tầng nông — điều mà ruling gốc muốn.

Từ quyết định 2026-09-28 mục 8, `/pham-vi` chỉ đếm văn bản được HIỆN
(`services/hien_thi`) — mọi phép đếm đối chứng dưới đây cũng vậy.
"""

import pytest
from sqlalchemy import text


def _hien() -> list[str]:
    from src.config import as_of_hieu_luc
    from src.services.db import get_engine
    from src.services.hien_thi import hien_thi_luc

    return list(hien_thi_luc(get_engine(), as_of_hieu_luc(None)))


def _dem_tu_db(engine) -> tuple[int, int]:
    """(số văn bản có điều khoản trích dẫn được, số văn bản có ÍT NHẤT một dòng),
    trong tập được hiện.

    Đếm lại từ DB thay vì viết cứng 49/125: một test viết cứng con số sẽ đỏ khi
    corpus lớn lên, và người sửa sẽ cập nhật con số thay vì kiểm quy tắc.
    """
    with engine.connect() as c:
        return tuple(c.execute(text(
            "SELECT count(*) FILTER (WHERE trich_dan_duoc > 0),"
            "       count(*) FILTER (WHERE tat_ca > 0)"
            " FROM (SELECT d.id,"
            "              count(p.id) AS tat_ca,"
            "              count(p.id) FILTER (WHERE p.cap <> 'mo_dau') AS trich_dan_duoc"
            "       FROM documents d LEFT JOIN provisions p ON p.document_id = d.id"
            "       WHERE d.id = ANY(CAST(:hien AS text[]))"
            "       GROUP BY d.id) x"
        ), {"hien": _hien()}).one())


@pytest.mark.integration
def test_tang_sau_dem_dieu_khoan_TRICH_DAN_DUOC_khong_dem_hang_mo_dau():
    from src.api.routes import _pham_vi
    from src.services.db import get_engine

    trich_dan_duoc, co_dong = _dem_tu_db(get_engine())
    if trich_dan_duoc == co_dong:
        # Mục 9 của cùng quyết định: mọi văn bản được hiện có toàn văn — khi đó
        # tầng nông rỗng là ĐÚNG, và test này không còn đối tượng.
        pytest.skip("không văn bản được hiện nào chỉ có hàng `mo_dau`")

    r = _pham_vi()
    assert r.sau.so_van_ban == trich_dan_duoc
    assert r.sau.so_van_ban != co_dong, (
        f"vẫn đếm mọi văn bản có ít nhất một dòng ({co_dong}) thay vì "
        f"văn bản trích dẫn được ({trich_dan_duoc}) — phóng đại độ phủ"
    )


@pytest.mark.integration
def test_hai_tang_cong_lai_bang_toan_bo_corpus():
    """Không văn bản nào bị mất hay bị đếm hai lần giữa hai tầng."""
    from sqlalchemy import text as _t

    from src.api.routes import _pham_vi
    from src.services.db import get_engine

    with get_engine().connect() as c:
        tong = c.execute(_t("SELECT count(*) FROM documents WHERE id = ANY(CAST(:hien AS text[]))"),
                         {"hien": _hien()}).scalar_one()
    r = _pham_vi()
    assert r.sau.so_van_ban + r.nong.so_van_ban == tong


@pytest.mark.integration
def test_van_ban_tang_nong_bao_0_dieu_khoan_khong_bao_1():
    """Văn bản tầng nông chỉ có hàng `mo_dau` mang tên nó — không trích dẫn được.
    Báo "1 điều khoản" cho nó là mời người đọc tin rằng có một điều khoản để đọc."""
    from src.api.routes import _pham_vi

    r = _pham_vi()
    if not r.nong.van_ban:
        pytest.skip("không văn bản được hiện nào ở tầng nông (quyết định 2026-09-28 mục 9)")
    xau = [v.so_ky_hieu for v in r.nong.van_ban if v.so_dieu_khoan != 0]
    assert not xau, f"tầng nông báo số điều khoản khác 0: {xau[:5]}"
