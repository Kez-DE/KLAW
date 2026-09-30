"""Bản đồ sửa đổi cấp điều khoản — biến `mot_phan_khong_xac_dinh` thành tên riêng.

Nhãn `HHL1P` của CSDL quốc gia nói "hết hiệu lực một phần" nhưng KHÔNG nói phần
nào. Hôm nay hỏi "nghỉ thai sản con thứ hai bao lâu?" thì hệ thống trả **06
tháng** kèm trích dẫn qua được cả hai tầng kiểm — trung thực (`ly_do` thừa nhận
không xác định được) nhưng đó là dạng yếu nhất của sự thật: khoản 1 Điều 139 ĐÃ
bị khoản 1 Điều 29 Luật Dân số 113/2025/QH15 sửa từ 01/7/2026, và VBHN
`18/VBHN-VPQH` nói ra điều đó bằng cấu trúc XML đọc được.

Hai nhóm test, cùng khuôn `test_effectivity.py`:
  * **Đơn vị** — `ap_sua_doi` là hàm thuần, ghim từng nhánh.
  * **Tích hợp** — DB thật, ca `Điều 139 Khoản 1` và tính idempotent của `014`.
"""

from datetime import date

import pytest
from sqlalchemy import inspect, text

from src.services.db import get_engine, run_migrations
from src.services.effectivity import Effectivity, ap_sua_doi, nap_sua_doi
from src.services.effectivity import EffectivityVerdict as V

HOM_NAY = date(2026, 9, 1)

MOT_PHAN = Effectivity(V.mot_phan_khong_xac_dinh, "thap",
                       "văn bản hết hiệu lực một phần; CSDL quốc gia không công bố dữ liệu "
                       "cấp điều khoản nên không xác định được điều này còn hiệu lực hay không")


def _bg(**kw) -> dict:
    """Một dòng `sua_doi_dieu_khoan`."""
    return {"sua_boi_so_ky_hieu": "113/2025/QH15", "sua_boi_duong_dan": "khoản 1 Điều 29",
            "tu_ngay": date(2026, 7, 1), "do_tin_cay": "cao",
            "nguon": "congbao.chinhphu.vn — 18/VBHN-VPQH",
            "vi_tri": "Điều 139 > Khoản 1"} | kw


# ── Không có bản ghi ⇒ KHÔNG ĐỔI GÌ (chống hồi quy) ──────────────────────────

def test_khong_co_ban_ghi_thi_verdict_giu_nguyen_tuyet_doi():
    """19.135 điều khoản, 4 điểm sửa. Nhánh mặc định là 19.131 dòng còn lại —
    nếu nó dịch dù chỉ một ký tự `ly_do`, cả bảng số liệu của khoá luận lệch."""
    for base in (MOT_PHAN,
                 Effectivity(V.con_hieu_luc, "thap", "..."),
                 Effectivity(V.bi_thay_the, "cao", "..."),
                 Effectivity(V.het_hieu_luc, "cao", "..."),
                 Effectivity(V.chua_xac_dinh, "thap", "...")):
        assert ap_sua_doi(base, [], HOM_NAY) is base


# ── Có bản ghi, đã tới ngày ⇒ nêu ĐÍCH DANH ──────────────────────────────────

def test_ban_ghi_da_hieu_luc_doi_nhan_va_neu_dich_danh_van_ban_va_ngay():
    r = ap_sua_doi(MOT_PHAN, [_bg()], HOM_NAY)
    assert r.verdict is V.bi_sua_doi
    assert "113/2025/QH15" in r.ly_do
    assert "2026-07-01" in r.ly_do
    assert "Điều 139 > Khoản 1" in r.ly_do
    assert "khoản 1 Điều 29" in r.ly_do
    assert r.tin_cay == "cao"


def test_ly_do_dan_nguon_congbao():
    """Công báo yêu cầu ghi rõ nguồn khi phát hành lại thông tin."""
    assert "congbao.chinhphu.vn" in ap_sua_doi(MOT_PHAN, [_bg()], HOM_NAY).ly_do


def test_tin_cay_theo_do_tin_cay_cua_ban_ghi_khong_ghim_cung():
    """`cao` chỉ khi số hiệu văn bản sửa đối chiếu được với `documents`. Ngoài
    corpus thì `trung_binh` — neo vị trí vẫn là cấu trúc, nhưng KHÔNG có nguồn
    thứ hai xác nhận câu trích dẫn."""
    assert ap_sua_doi(MOT_PHAN, [_bg(do_tin_cay="trung_binh")], HOM_NAY).tin_cay == "trung_binh"


# ── Chưa tới ngày ⇒ KHÔNG khai tử sớm ────────────────────────────────────────

def test_ban_ghi_chua_toi_ngay_thi_dieu_khoan_van_dung_nguyen_van_hom_nay():
    """VBHN xuất bản TRƯỚC ngày sửa đổi có hiệu lực là chuyện thường. Nói
    "đã bị sửa" lúc đó là sai theo hướng ngược lại — văn bản gốc đang là luật
    đúng, và người dùng cần biết nó sắp đổi chứ không phải nó đã hỏng."""
    r = ap_sua_doi(MOT_PHAN, [_bg(tu_ngay=date(2027, 1, 1))], HOM_NAY)
    assert r.verdict is V.con_hieu_luc
    assert "sẽ bị" in r.ly_do and "113/2025/QH15" in r.ly_do and "2027-01-01" in r.ly_do


def test_ban_ghi_thieu_ngay_khong_duoc_coi_la_da_hieu_luc():
    """`tu_ngay = NULL` (regex không đọc được ngày) — không biết thì KHÔNG
    được mặc định là đã tới. Mặc định an toàn của cả `effectivity.py`."""
    r = ap_sua_doi(MOT_PHAN, [_bg(tu_ngay=None, do_tin_cay="can_doi_chieu_tay")], HOM_NAY)
    assert r.verdict is V.can_doi_chieu_tay
    assert "đọc được ngày hiệu lực" in r.ly_do


# ── Không khớp khuôn ⇒ khai báo, không đoán ──────────────────────────────────

def test_can_doi_chieu_tay_khong_bia_ten_van_ban():
    r = ap_sua_doi(MOT_PHAN, [_bg(sua_boi_so_ky_hieu=None, sua_boi_duong_dan=None,
                                  tu_ngay=None, do_tin_cay="can_doi_chieu_tay")], HOM_NAY)
    assert r.verdict is V.can_doi_chieu_tay
    assert "None" not in r.ly_do


# ── Ưu tiên giữa các mức ─────────────────────────────────────────────────────

def test_van_ban_da_bi_thay_the_toan_bo_thi_sua_doi_cap_khoan_khong_lat_nguoc():
    """Sửa đổi cấp khoản KHÔNG được nâng một văn bản đã chết dậy. `ap_sua_doi`
    chỉ tinh chỉnh phán quyết "một phần / chưa rõ", không lật `bi_thay_the`,
    `het_hieu_luc` hay `chua_hieu_luc`."""
    for chet in (Effectivity(V.bi_thay_the, "cao", "x"),
                 Effectivity(V.het_hieu_luc, "cao", "x"),
                 Effectivity(V.chua_hieu_luc, "cao", "x")):
        assert ap_sua_doi(chet, [_bg()], HOM_NAY) is chet


def test_nhieu_ban_ghi_lay_ban_moi_nhat_da_hieu_luc():
    som = _bg(sua_boi_so_ky_hieu="124/2025/QH15", tu_ngay=date(2026, 1, 1))
    muon = _bg(sua_boi_so_ky_hieu="113/2025/QH15", tu_ngay=date(2026, 7, 1))
    r = ap_sua_doi(MOT_PHAN, [som, muon], HOM_NAY)
    assert "113/2025/QH15" in r.ly_do
    assert "124/2025/QH15" in r.ly_do, "bản ghi cũ hơn vẫn phải được liệt kê, không nuốt"


# ══════════════════════════ Tích hợp: DB thật ══════════════════════════

# Tra theo `duong_dan`, KHÔNG ghim `provisions.id`. Lý do đã trả giá ngay trong
# phiên này: `id` là BIGSERIAL, một lần chạy lại `scripts/ingest.py` đẩy Điều 139
# Khoản 1 từ 141467 sang 162327 và mọi hằng số id trong test hoá vô nghĩa —
# nhưng test vẫn XANH nếu nó chỉ kiểm "không có bản ghi", vì id không tồn tại và
# id không bị sửa cho ra cùng một kết quả rỗng. `duong_dan` là khoá ỔN ĐỊNH và
# cũng chính là thứ người đọc thấy trong trích dẫn.
DD_139_KHOAN_1 = "45/2019/QH14 > Điều 139 > Khoản 1"
DD_139 = "45/2019/QH14 > Điều 139"
# Đối chứng MẠNH nhất có thể: EM RUỘT của khoản đã bị sửa. Cùng Điều 139,
# cùng cha, nhưng không có bản ghi nào — nếu bản đồ lan sang ngang hoặc lan
# xuống từ cha thì đúng dòng này đỏ.
DD_KHONG_SUA = "45/2019/QH14 > Điều 139 > Khoản 2"


def _pid(duong_dan: str) -> int:
    with get_engine().connect() as c:
        pid = c.execute(text("SELECT id FROM provisions WHERE duong_dan = :d"),
                        {"d": duong_dan}).scalar()
    assert pid is not None, f"không có điều khoản {duong_dan!r} trong corpus"
    return pid


@pytest.mark.integration
def test_migration_014_tao_bang_va_chay_hai_lan_cho_cung_ket_qua():
    # `"014"` chứ không cả chuỗi: test này đo tính idempotent của 014, và một
    # migration-cổng khác đang đỏ không được làm nó đỏ theo (mọi file chạy chung
    # MỘT transaction). Cổng đó vẫn chặn khởi động ứng dụng như thiết kế.
    run_migrations("014")
    truoc = _anh_chup()
    run_migrations("014")
    assert _anh_chup() == truoc
    assert "sua_doi_dieu_khoan" in set(inspect(get_engine()).get_table_names())


def _anh_chup() -> tuple:
    with get_engine().connect() as c:
        n = c.execute(text("SELECT count(*) FROM sua_doi_dieu_khoan")).scalar()
        cols = tuple(sorted(r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'sua_doi_dieu_khoan'"))))
    return n, cols


@pytest.mark.integration
def test_CHAP_NHAN_dieu_139_khoan_1_ra_nhan_neu_dich_danh_luat_dan_so():
    """Ca trung tâm. Trước thay đổi này: `mot_phan_khong_xac_dinh` + "không xác
    định được điều này còn hiệu lực hay không". Sau: nêu tên 113/2025/QH15 và
    ngày 01/7/2026."""
    engine = get_engine()
    pid = _pid(DD_139_KHOAN_1)
    bg = nap_sua_doi(engine, [pid])
    assert bg.get(pid), (
        "chưa nạp bản đồ sửa đổi — chạy `python -m scripts.nap_sua_doi_vbhn`")
    r = ap_sua_doi(MOT_PHAN, bg[pid], HOM_NAY)
    assert r.verdict is V.bi_sua_doi
    assert "113/2025/QH15" in r.ly_do and "2026-07-01" in r.ly_do


@pytest.mark.integration
def test_dieu_cha_thua_huong_sua_doi_cua_khoan_con():
    """Câu trả lời thường dẫn cả Điều. Nếu bản đồ chỉ tra đúng `provision_id`
    của Khoản thì một claim dẫn "Điều 139" đi qua mà không cảnh báo gì — đúng
    lỗ hổng im lặng mà cả việc này tồn tại để bịt."""
    pid = _pid(DD_139)
    assert nap_sua_doi(get_engine(), [pid]).get(pid)


@pytest.mark.integration
def test_khoan_em_ruot_cua_khoan_bi_sua_KHONG_bi_lay_nhan_theo():
    assert not nap_sua_doi(get_engine(), [_pid(DD_KHONG_SUA)])


@pytest.mark.integration
def test_bon_diem_sua_khao_sat_tim_duoc_deu_co_mat():
    """`18/VBHN-VPQH` chỉ ra đúng bốn điểm sửa trên Bộ luật Lao động."""
    with get_engine().connect() as c:
        thuc = {(r[0], r[1]) for r in c.execute(text(
            "SELECT p.duong_dan, s.sua_boi_so_ky_hieu FROM sua_doi_dieu_khoan s "
            "JOIN provisions p ON p.id = s.provision_id"))}
    assert {
        ("45/2019/QH14 > Điều 59 > Khoản 2 > Điểm a", "124/2025/QH15"),
        ("45/2019/QH14 > Điều 61 > Khoản 3", "124/2025/QH15"),
        ("45/2019/QH14 > Điều 139 > Khoản 1", "113/2025/QH15"),
        ("45/2019/QH14 > Điều 154", "71/2025/QH15"),   # khoản 8a là khoản MỚI
    } <= thuc


# F1 (2026-09-29): 87/2025/QH15 khoản 1 Điều 1 sửa CẢ Điều 4 của 64/2025/QH15
# (`vi_tri = 'Điều 4'`) — mọi khoản của nó trong CSDL là bản trước sửa (14 khoản,
# còn "cấp huyện"). Trace c8a98c3d (2026-09-30): khoản 13 chỉ mang
# `mot_phan_khong_xac_dinh` cạnh danh sách mới, ở bối cảnh sinh luận điểm lẫn trích dẫn.
DD_4_KHOAN_13 = "64/2025/QH15 > Điều 4 > Khoản 13"
# Đối chứng: bản ghi "Điều 154 > Khoản 8a" neo ở Điều 154 chỉ vì khoản 8a mới
# chưa có dòng — chín khoản cũ của Điều 154 không ai đụng tới.
DD_154_KHOAN_1 = "45/2019/QH14 > Điều 154 > Khoản 1"


@pytest.mark.integration
def test_khoan_cua_dieu_bi_sua_ca_dieu_mang_nhan_cua_dieu():
    pid = _pid(DD_4_KHOAN_13)
    bg = nap_sua_doi(get_engine(), [pid]).get(pid)
    assert bg and {b["sua_boi_so_ky_hieu"] for b in bg} == {"87/2025/QH15"}, bg
    assert ap_sua_doi(Effectivity(V.con_hieu_luc, "cao", "x"), bg, HOM_NAY).verdict is V.bi_sua_doi


@pytest.mark.integration
def test_ban_ghi_khoan_moi_neo_o_dieu_KHONG_lan_xuong_khoan_cu():
    assert not nap_sua_doi(get_engine(), [_pid(DD_154_KHOAN_1)])
