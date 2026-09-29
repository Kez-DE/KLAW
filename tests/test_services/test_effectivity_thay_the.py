"""Quyết định 2026-09-28 mục 12 — văn bản hết hiệu lực luôn chỉ ra văn bản thay thế.

Ba vế, 0 LLM:

  1. Mức 1 (hết hạn theo ngày) vẫn nêu văn bản thay thế theo cạnh đồ thị, và câu
     cho người đọc là "Đã được thay thế bởi X." ở mọi bề mặt.
  2. Văn bản thay mà chính nó đã chết thì đi tiếp theo chuỗi tới văn bản đầu tiên
     còn sống — cùng một kết quả ở đường toàn kho và đường từng văn bản.
  3. Cạnh đã đối chiếu nguyên văn chính thống (`canh_doi_chieu`) không bị guard
     "khác chủ đề" hay guard thứ bậc hạ xuống; cạnh chưa đối chiếu giữ guard cũ.

Phần thuần chạy trên engine giả trong bộ nhớ. Phần `integration` chạy đúng câu
SQL trên bảng TẠM (`pg_temp`, một kết nối `StaticPool`) — không đọc, không ghi
một dòng nào của DB dùng chung.
"""

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.agents.nodes import assemble as asm
from src.services import effectivity as eff
from src.services.effectivity import EffectivityVerdict as V
from src.services.effectivity import VanBanNeu, danh_gia, ke_nhiem_con_song
from src.services.hien_thi import VERDICT_HIEN, canh_bao, mo_ta, van_ban_thay

AS_OF = date(2026, 9, 29)

TEN_12 = (
    "Nghị định số 12/2022/NĐ-CP Quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội,"
    " người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng"
)
TEN_283 = (
    "Nghị định quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội, người lao động"
    " Việt Nam đi làm việc ở nước ngoài theo hợp đồng"
)
TEN_49 = "Nghị định số 49/2013/NĐ-CP Hướng dẫn Bộ luật Lao động về tiền lương"
TEN_145 = (
    "Nghị định số 145/2020/NĐ-CP Quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về"
    " điều kiện lao động và quan hệ lao động"
)
TEN_63 = (
    "Nghị định số 63/2015/NĐ-CP Quy định chính sách đối với người lao động dôi dư khi sắp xếp lại công ty"
    " trách nhiệm hữu hạn một thành viên do Nhà nước làm chủ sở hữu"
)


def _doc(**kw) -> dict:
    base = {
        "id": "x",
        "so_ky_hieu": "1/2020/NĐ-CP",
        "loai_van_ban": "Nghị định",
        "ten": "Nghị định thử",
        "ngay_hieu_luc": date(2020, 1, 1),
        "ngay_het_hieu_luc": None,
        "tinh_trang": "CHL",
    }
    return base | kw


def _canh(tu: str, so: str, ten: str, ngay: date, loai: int = 21, chieu: str = "di_vao", **kw) -> dict:
    return {
        "loai": loai,
        "chieu": chieu,
        "from_document_id": tu,
        "from_so_ky_hieu": so,
        "from_ten": ten,
        "from_ngay_hieu_luc": ngay,
        "from_loai_van_ban": "Nghị định",
    } | kw


DOC_12 = _doc(
    id="153913",
    so_ky_hieu="12/2022/NĐ-CP",
    ten=TEN_12,
    ngay_hieu_luc=date(2022, 1, 17),
    ngay_het_hieu_luc=date(2026, 9, 10),
    tinh_trang="HHL",
)
THAY_12 = _canh("k8-283", "283/2026/NĐ-CP", TEN_283, date(2026, 9, 10))
DOC_49 = _doc(id="30466", so_ky_hieu="49/2013/NĐ-CP", ten=TEN_49, ngay_hieu_luc=date(2013, 7, 1), tinh_trang="HHL1P")
CANH_145 = _canh("152668", "145/2020/NĐ-CP", TEN_145, date(2021, 2, 1))
CANH_63 = _canh("72046", "63/2015/NĐ-CP", TEN_63, date(2015, 9, 15))
DA_DOI_CHIEU = {"da_doi_chieu": True}


# ─────────────────────── 1. hết hạn theo ngày vẫn nêu văn bản thay thế


def test_12_2022_het_han_theo_ngay_neu_283_2026_o_moi_be_mat():
    r = danh_gia(DOC_12, [THAY_12], AS_OF)
    assert r.verdict is V.het_hieu_luc
    assert r.van_ban == (VanBanNeu("k8-283", "283/2026/NĐ-CP"),)
    assert mo_ta(r) == "Đã được thay thế bởi 283/2026/NĐ-CP."
    assert canh_bao("12/2022/NĐ-CP", r) == "12/2022/NĐ-CP không còn hiệu lực. Đã được thay thế bởi 283/2026/NĐ-CP."
    # Câu cho người hỏi khi mọi nguồn đã chết: nêu đích danh, không "chưa xác định".
    cau = asm._ly_do_moi_nguon_bi_thay([SimpleNamespace(effectivity=r)])
    assert "283/2026/NĐ-CP" in cau and "chưa xác định" not in cau, cau


def test_cau_moi_nguon_bi_thay_KHONG_neu_van_ban_chet_o_nhanh_cut_nhung_giu_suy_luan_2b():
    cut = eff.Effectivity(V.bi_thay_the, "cao", "đồ thị xác nhận: bị 38/2022/NĐ-CP thay thế từ 2022-07-01")
    assert "38/2022" not in asm._ly_do_moi_nguon_bi_thay([SimpleNamespace(effectivity=cut)])
    suy = eff.Effectivity(V.bi_thay_the, "trung_binh", "suy luận cùng chủ đề: 293/2025/NĐ-CP cùng chủ đề")
    assert "293/2025/NĐ-CP" in asm._ly_do_moi_nguon_bi_thay([SimpleNamespace(effectivity=suy)])


def test_het_han_theo_ngay_voi_canh_DA_DOI_CHIEU_khac_chu_de_van_neu_van_ban_bai_bo():
    """49/2013 khi B-R4 điền ngày hết hiệu lực: 145/2020 Điều 114 k2 bãi bỏ nó, hai
    tiêu đề khác chủ đề. Chưa đối chiếu thì không nêu (guard cũ), đã đối chiếu thì nêu."""
    het = DOC_49 | {"ngay_het_hieu_luc": date(2021, 2, 1)}
    assert danh_gia(het, [CANH_145], AS_OF).van_ban == ()
    r = danh_gia(het, [CANH_145 | DA_DOI_CHIEU], AS_OF)
    assert r.verdict is V.het_hieu_luc and r.van_ban == (VanBanNeu("152668", "145/2020/NĐ-CP"),)


# ─────────────────────── 3. cạnh đã đối chiếu nguyên văn


def test_canh_DA_DOI_CHIEU_khac_chu_de_la_bi_thay_the_con_canh_chua_doi_chieu_van_can_doi_chieu_tay():
    chua = danh_gia(DOC_49, [CANH_145], AS_OF)
    assert chua.verdict is V.can_doi_chieu_tay and chua.van_ban == ()
    da = danh_gia(DOC_49, [CANH_145 | DA_DOI_CHIEU], AS_OF)
    assert (da.verdict, da.tin_cay) == (V.bi_thay_the, "cao")
    assert da.van_ban == (VanBanNeu("152668", "145/2020/NĐ-CP"),)
    assert mo_ta(da) == "Đã được thay thế bởi 145/2020/NĐ-CP."


@pytest.mark.parametrize("thu_tu", [1, -1])
def test_canh_chua_doi_chieu_dung_truoc_KHONG_che_canh_da_doi_chieu(thu_tu):
    """Đo trên DB 2026-09-29: 49/2013 có hai cạnh loai 21, từ 145/2020 (đúng, Điều 114)
    và từ 63/2015 (chưa đối chiếu). Phán quyết không được phụ thuộc thứ tự dòng SQL,
    và cạnh chưa đối chiếu khác chủ đề không được nêu tên."""
    r = danh_gia(DOC_49, [CANH_145 | DA_DOI_CHIEU, CANH_63][::thu_tu], AS_OF)
    assert r.verdict is V.bi_thay_the
    assert r.van_ban == (VanBanNeu("152668", "145/2020/NĐ-CP"),)


def test_bai_bo_MOT_PHAN_da_doi_chieu_khong_khai_tu_ca_van_ban():
    """135/2020 ← 158/2025 Điều 44 k2 điểm c: chỉ bốn khoản và Phụ lục III (loai 23)."""
    doc = _doc(
        id="152734",
        so_ky_hieu="135/2020/NĐ-CP",
        ten="Nghị định số 135/2020/NĐ-CP Quy định về tuổi nghỉ hưu",
        ngay_hieu_luc=date(2021, 1, 1),
        tinh_trang="HHL1P",
    )
    canh = _canh(
        "178757",
        "158/2025/NĐ-CP",
        "Nghị định quy định chi tiết Luật Bảo hiểm xã hội",
        date(2025, 7, 1),
        loai=23,
        chieu="di_ra",
        **DA_DOI_CHIEU,
    )
    r = danh_gia(doc, [canh], AS_OF)
    assert r.verdict is V.mot_phan_khong_xac_dinh and r.verdict in VERDICT_HIEN


def test_canh_sua_doi_DA_DOI_CHIEU_khong_bi_guard_thu_bac_bo_ten():
    tt = _canh("tt", "5/2025/TT-BLĐTBXH", "Thông tư sửa đổi", date(2025, 1, 1), loai=20, from_loai_van_ban="Thông tư")
    doc = _doc(tinh_trang="HHL1P")
    assert danh_gia(doc, [tt], AS_OF).van_ban == ()
    assert danh_gia(doc, [tt | DA_DOI_CHIEU], AS_OF).van_ban == (VanBanNeu("tt", "5/2025/TT-BLĐTBXH"),)


# ─────────────────────── 2. chuỗi thay thế tới văn bản còn sống


def _e(verdict, *van_ban):
    return eff.Effectivity(verdict, "cao", "x", van_ban=tuple(van_ban))


A, B, C, D = (VanBanNeu(i, f"{i}/2020/NĐ-CP") for i in "ABCD")


def test_chuoi_ba_buoc_toi_van_ban_con_song():
    bang = {"A": _e(V.bi_thay_the, B), "B": _e(V.het_hieu_luc, C), "C": _e(V.bi_thay_the, D), "D": _e(V.con_hieu_luc)}
    assert ke_nhiem_con_song(_e(V.het_hieu_luc, A), bang.get) == (D,)
    # Văn bản còn sống: văn bản nó nêu là văn bản SỬA nó, không có chuỗi nào để đi.
    assert ke_nhiem_con_song(_e(V.mot_phan_khong_xac_dinh, A), bang.get) == ()


def test_chuoi_vong_hay_qua_sau_thi_khong_treo_va_khong_neu_van_ban_chet():
    vong = {"A": _e(V.bi_thay_the, B), "B": _e(V.bi_thay_the, A)}
    assert ke_nhiem_con_song(_e(V.het_hieu_luc, A), vong.get) == ()
    bang = {"A": _e(V.bi_thay_the, B), "B": _e(V.het_hieu_luc, C), "C": _e(V.bi_thay_the, D), "D": _e(V.con_hieu_luc)}
    assert ke_nhiem_con_song(_e(V.het_hieu_luc, A), bang.get, sau_toi_da=2) == ()


def test_tran_mac_dinh_du_cho_chuoi_luong_toi_thieu_16_buoc_va_con_du():
    """Đo 2026-09-29: 03/2006/NĐ-CP → … → 293/2025/NĐ-CP là 16 bước, dài thêm mỗi năm."""
    vb = [VanBanNeu(str(n), f"{n}/2000/NĐ-CP") for n in range(33)]
    bang = {v.doc_id: _e(V.het_hieu_luc, vb[n + 1]) for n, v in enumerate(vb[:-1])} | {"32": _e(V.con_hieu_luc)}
    assert ke_nhiem_con_song(_e(V.het_hieu_luc, vb[0]), bang.get) == (vb[-1],)


class _EngineGia:
    """Engine trong bộ nhớ: trả đúng hình dạng hàng của bốn câu SQL phán quyết."""

    url = "gia://k9"

    def __init__(self, docs: list[dict], canh: list[dict]):
        self.docs, self.canh = {d["id"]: d for d in docs}, canh
        self.so_truy_van = 0

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, p=None):
        self.so_truy_van += 1
        if sql is eff._SQL_DOC_TAT_CA:
            rows = list(self.docs.values())
        elif sql is eff._SQL_CANH_TAT_CA:
            rows = self.canh
        elif sql is eff._SQL_DOC:
            rows = [self.docs[p["i"]]]
        elif sql is eff._SQL_CANH:
            rows = [c for c in self.canh if c["chu"] == p["i"]]
        else:
            rows = []  # `_SQL_UNG_VIEN`: không ứng viên Mức 2b nào
        m = SimpleNamespace(all=lambda: rows, one=lambda: rows[0])
        return SimpleNamespace(mappings=lambda: m)


_CHUOI = [
    ("n157", "157/2018/NĐ-CP", date(2019, 1, 1), date(2020, 1, 1)),
    ("n90", "90/2019/NĐ-CP", date(2020, 1, 1), None),
    ("n38", "38/2022/NĐ-CP", date(2022, 7, 1), date(2024, 7, 1)),
    ("n293", "293/2025/NĐ-CP", date(2026, 1, 1), None),
]
_TEN_LUONG = "Nghị định quy định mức lương tối thiểu"


def _kho_chuoi() -> _EngineGia:
    docs = [
        _doc(id=i, so_ky_hieu=so, ten=_TEN_LUONG, ngay_hieu_luc=hl, ngay_het_hieu_luc=het) for i, so, hl, het in _CHUOI
    ]
    canh = [
        _canh(sau[0], sau[1], _TEN_LUONG, sau[2], chu=truoc[0]) for truoc, sau in zip(_CHUOI, _CHUOI[1:], strict=False)
    ]
    return _EngineGia(docs, canh)


def test_chuoi_ba_buoc_CUNG_ket_qua_o_duong_toan_kho_va_duong_tung_van_ban():
    """157/2018 (Mức 1) → 90/2019 → 38/2022 (Mức 1) → 293/2025: câu nêu 293/2025."""
    kho = _kho_chuoi()
    toan = eff._danh_gia_toan_bo_tinh(kho, AS_OF)
    assert kho.so_truy_van == 2, "đường toàn kho vẫn đúng hai truy vấn"
    for i in ("n157", "n90", "n38"):
        assert toan[i].van_ban == (VanBanNeu("n293", "293/2025/NĐ-CP"),), i
        assert eff.danh_gia_theo_id(kho, i, AS_OF) == toan[i], i
    assert mo_ta(toan["n157"]) == "Đã được thay thế bởi 293/2025/NĐ-CP."
    assert toan["n293"].verdict is V.con_hieu_luc


_TEN_GTDB = "Luật Giao thông đường bộ"
_LUAT = {"from_loai_van_ban": "Luật"}


@pytest.mark.parametrize(
    ("tin_hieu", "verdict_23"),
    [
        # Đo 2026-09-29: 35/2024/QH15 "Luật Đường bộ" → 23/2008/QH12, khác đầu đề.
        (_canh("35", "35/2024/QH15", "Luật Đường bộ số 35/2024/QH15", date(2025, 1, 1), **_LUAT), V.can_doi_chieu_tay),
        # Như 136/2007/NĐ-CP (HHL, bị 94/2015/NĐ-CP sửa): Mức 2c trả lời trước Mức 3.
        (_canh("94", "94/2015/QH13", "Luật sửa đổi", date(2015, 12, 1), loai=20, **_LUAT), V.mot_phan_khong_xac_dinh),
    ],
)
@pytest.mark.parametrize("tinh_trang_23", ["HHL", "CHL"])
def test_chuoi_KHONG_neu_van_ban_Bo_Tu_phap_khai_HHL(tin_hieu, verdict_23, tinh_trang_23):
    """26/2001/QH10 → 23/2008/QH12: 23/2008 do Bộ Tư pháp khai HHL, trang của nó nói
    "không còn hiệu lực", nên văn bản chết không được chỉ người đọc sang đó. Phán
    quyết của chính 23/2008 giữ nguyên — guard khác chủ đề trước Mức 3 là cố ý, cho
    ca MOJ khai HHL sai (Luật BHXH 41/2024). Văn bản chưa rõ mà MOJ không khai HHL
    thì vẫn được nêu, như trước."""
    luat = {"loai_van_ban": "Luật"}
    docs = [
        _doc(
            id="26",
            so_ky_hieu="26/2001/QH10",
            ten=_TEN_GTDB,
            ngay_hieu_luc=date(2002, 1, 1),
            ngay_het_hieu_luc=date(2009, 7, 1),
            tinh_trang="HHL",
            **luat,
        ),
        _doc(
            id="23",
            so_ky_hieu="23/2008/QH12",
            ten=f"{_TEN_GTDB} số 23/2008/QH12",
            ngay_hieu_luc=date(2009, 7, 1),
            tinh_trang=tinh_trang_23,
            **luat,
        ),
    ]
    canh = [
        _canh("23", "23/2008/QH12", f"{_TEN_GTDB} số 23/2008/QH12", date(2009, 7, 1), chu="26", **_LUAT),
        tin_hieu | {"chu": "23"},
    ]
    kho = _EngineGia(docs, canh)
    toan = eff._danh_gia_toan_bo_tinh(kho, AS_OF)
    assert toan["23"].verdict is verdict_23
    ke = () if tinh_trang_23 == "HHL" else (VanBanNeu("23", "23/2008/QH12"),)
    assert toan["26"].verdict is V.het_hieu_luc and toan["26"].van_ban == ke
    assert eff.danh_gia_theo_id(kho, "26", AS_OF) == toan["26"]
    assert van_ban_thay(toan["26"], toan, frozenset()) == ke


# ─────────────────────── đúng câu SQL, trên bảng TẠM


@pytest.fixture
def kho_tam():
    from src.services.db import get_engine

    e = create_engine(get_engine().url, poolclass=StaticPool)
    with e.begin() as c:
        for bang in ("documents", '"references"'):
            c.execute(text(f"CREATE TEMP TABLE {bang} (LIKE public.{bang} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
        # Hình dạng của migration 039 (K8) — viết tay để test không phụ thuộc bảng thật.
        c.execute(
            text(
                "CREATE TEMP TABLE canh_doi_chieu (reference_id bigint PRIMARY KEY, dieu_khoan text NOT NULL,"
                " trich text NOT NULL, url text NOT NULL, kiem_boi text NOT NULL, kiem_luc timestamptz NOT NULL)"
            )
        )
        for i, so, ten, hl, het, tt in [
            *((i, so, _TEN_LUONG, hl, het, "HHL" if het else "CHL") for i, so, hl, het in _CHUOI),
            ("k9-49", "49/2013/NĐ-CP", TEN_49, date(2013, 7, 1), None, "HHL1P"),
            ("k9-145", "145/2020/NĐ-CP", TEN_145, date(2021, 2, 1), None, "HHL1P"),
            ("k9-63", "63/2015/NĐ-CP", TEN_63, date(2015, 9, 15), None, "CHL"),
        ]:
            c.execute(
                text(
                    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, ngay_hieu_luc,"
                    " ngay_het_hieu_luc, depth, checksum) VALUES (:i, :so, 'Nghị định', :ten, :tt, :hl, :het,"
                    " 'shallow', 'k9')"
                ),
                {"i": i, "so": so, "ten": ten, "tt": tt, "hl": hl, "het": het},
            )
        canh = [(sau[0], truoc[0], 21) for truoc, sau in zip(_CHUOI, _CHUOI[1:], strict=False)]
        canh += [("k9-145", "k9-49", 21), ("k9-63", "k9-49", 21)]
        for n, (tu, toi, loai) in enumerate(canh, 1):
            c.execute(
                text(
                    'INSERT INTO "references" (id, from_document_id, to_document_id, loai) VALUES (:n, :tu, :toi, :l)'
                ),
                {"n": n, "tu": tu, "toi": toi, "l": loai},
            )
    yield e, len(canh) - 1  # id cạnh 145/2020 → 49/2013
    e.dispose()


@pytest.mark.integration
def test_SQL_that_noi_chuoi_va_doc_canh_doi_chieu(kho_tam):
    e, canh_145 = kho_tam
    tt = eff._danh_gia_toan_bo_tinh(e, AS_OF)
    assert tt["n157"].van_ban == (VanBanNeu("n293", "293/2025/NĐ-CP"),)
    assert eff.danh_gia_theo_id(e, "n157", AS_OF) == tt["n157"]
    assert tt["k9-49"].verdict is V.can_doi_chieu_tay, "chưa đối chiếu: guard chủ đề giữ nguyên"
    with e.begin() as c:
        c.execute(
            text(
                "INSERT INTO canh_doi_chieu VALUES (:r, 'Điều 114 khoản 2', 'Nghị định số 49/2013/NĐ-CP …',"
                " 'https://congbao.chinhphu.vn/x', 'k9-test', now())"
            ),
            {"r": canh_145},
        )
    tt = eff._danh_gia_toan_bo_tinh(e, AS_OF)
    assert tt["k9-49"].verdict is V.bi_thay_the
    assert tt["k9-49"].van_ban == (VanBanNeu("k9-145", "145/2020/NĐ-CP"),)
    assert eff.danh_gia_theo_id(e, "k9-49", AS_OF) == tt["k9-49"]
