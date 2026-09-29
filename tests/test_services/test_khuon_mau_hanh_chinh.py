"""Khuôn mẫu nhóm HÀNH CHÍNH — công văn, quyết định, nghị quyết, quy chế/nội quy kèm
quyết định ban hành, biên bản, giấy ủy quyền, văn bản giải trình (thiết kế
`khuon-mau-thiet-ke.md` §1, §2, §7; NĐ 30/2020 Phụ lục III Mẫu 1.1–1.5, 1.9; NĐ 124/2020
Mẫu 01, 02).

Hàm thuần: không DB, không mô hình, không LibreOffice (trang thật ở
`test_khuon_mau_hanh_chinh_trang.py`, căn cứ của kho ở `test_khuon_mau_hanh_chinh_kho.py`).
Khoá năm lời hứa cho mỗi loại:

1. Mục registry nạp được; mục khung (`muc_khung`) là mục THẬT của checklist.
2. Bộ đọc của khuôn gốc thấy đúng mọi chỗ trống bộ dựng viết, và bộ áp điền được hết.
3. Điều luật đòi mà mô hình bỏ sót được chèn thành chỗ trống, có tên, lúc tạo.
4. Căn cứ: dòng của kho in nghiêng, đủ số; dòng của khung không bao giờ là một luật
   thiếu số ("Bộ luật … số ……" là lỗi chủ dự án đã chỉ).
5. Bố cục đúng mẫu: thứ tự đầu – giữa – đuôi, vị trí ngày, khối ký, nơi nhận.
"""

import io
import re
import zipfile

import pytest
from lxml import etree

from src.agents.graph_soan_thao import cac_loai as cac_checklist
from src.agents.graph_soan_thao import load_checklist_cached
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
C = km.CHO

HANH_CHINH = {
    "cong_van": "hanh_chinh",
    "quyet_dinh_bo_nhiem": "hanh_chinh",
    "quyet_dinh_cham_dut_hdld": "hanh_chinh",
    "quyet_dinh_ky_luat": "hanh_chinh",
    "quyet_dinh_hdqt": "hanh_chinh",
    "quy_che_noi_bo": "hanh_chinh",
    "noi_quy": "hanh_chinh",
    "quy_che_dan_chu": "hanh_chinh",
    "bien_ban_hop_hdqt": "hanh_chinh",
    "giay_uy_quyen_to_chuc": "hanh_chinh",
    "van_ban_giai_trinh_to_chuc": "hanh_chinh",
    "giay_uy_quyen": "don",
    "van_ban_giai_trinh": "don",
}
KEM_THEO = ("quy_che_noi_bo", "noi_quy", "quy_che_dan_chu")
QUYET_DINH = ("quyet_dinh_bo_nhiem", "quyet_dinh_cham_dut_hdld", "quyet_dinh_ky_luat", "quyet_dinh_hdqt")
CAN_CU = [
    {"dong": "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;", "doc_id": "139264"},
    {"dong": "Căn cứ Luật Doanh nghiệp số 59/2020/QH14 ngày 17 tháng 6 năm 2020.", "doc_id": "142881"},
]


def _dieu_mau(loai: str) -> list[dict]:
    """Một điều cho mỗi mục thân cố định, cộng hai điều tự do có một chỗ trống."""
    ra = [{"key": k, "ten": "", "doan": [f"Nội dung mục {k} là {C}."]} for k in sorted(km.muc_than(km.nap(loai)))]
    return ra + [
        {"key": None, "ten": "Hiệu lực", "doan": ["Văn bản có hiệu lực kể từ ngày ký."]},
        {"key": None, "ten": "Tổ chức thực hiện", "doan": [f"Đơn vị {C} chịu trách nhiệm thực hiện."]},
    ]


def _spec(loai: str, *, dieu=None, trich_yeu=None, can_cu=CAN_CU) -> dict:
    return km.spec_tu(
        km.nap(loai), tieu_de=None, trich_yeu=trich_yeu, can_cu=can_cu, dieu=_dieu_mau(loai) if dieu is None else dieu
    )


def _goc(docx: bytes):
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        return etree.fromstring(z.read("word/document.xml"))


def _chu(e) -> str:
    return "".join(t.text or "" for t in e.iter(f"{_W}t"))


def _doan_than(docx: bytes) -> list:
    """Con trực tiếp của `w:body` theo thứ tự: ("p", chữ, phần tử) hay ("tbl", chữ, phần tử)."""
    body = _goc(docx).find(f"{_W}body")
    return [(e.tag.split("}")[1], _chu(e), e) for e in body if e.tag in (f"{_W}p", f"{_W}tbl")]


def _don_vi(docx: bytes) -> list[dict]:
    return [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]


# ── 1. Registry ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("loai", "bo_cuc"), sorted(HANH_CHINH.items()))
def test_muc_nap_duoc_dung_bo_cuc_va_ghi_nguon(loai, bo_cuc):
    d = km.nap(loai)
    assert d["bo_cuc"] == bo_cuc
    ng = d["nguon"]
    assert ng["loai"] in ("mau_chinh_thuc", "tuong_tu") and ng["tep_d2"] and re.fullmatch(r"[0-9a-f]{64}", ng["sha256"])
    assert ng["van_ban"] and ng["ghi_chu"] and ng["trang"]


@pytest.mark.parametrize("loai", sorted(x for x in HANH_CHINH if x in cac_checklist()))
def test_muc_khung_la_muc_that_cua_checklist(loai):
    """`muc_khung` báo cho phép kiểm điều bắt buộc rằng khung đã có mục đó: một khoá gõ
    sai sẽ để phép kiểm tưởng mục được đáp ứng trong khi không có gì trên trang."""
    khoa = {m["key"] for m in load_checklist_cached(loai).muc}
    entry = km.nap(loai)
    assert set(entry.get("muc_khung") or []) <= khoa
    assert km.muc_than(entry) <= khoa, "mục thân cố định phải là mục checklist để mô hình viết đúng chỗ"


# ── 2. Chỗ trống: bộ đọc thấy đúng, bộ áp điền được hết ─────────────────────


@pytest.mark.parametrize("loai", sorted(HANH_CHINH))
def test_ban_do_khop_bo_doc_va_bo_ap_dien_duoc_het(loai):
    docx, ban_do = km.dung_docx(_spec(loai))
    dv = _don_vi(docx)
    theo = {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}
    for k, ds in ban_do.items():
        assert len(theo[k].get("cho_trong") or []) == len(ds), theo[k]["noi_dung"]
    assert {k for k, d in theo.items() if d.get("cho_trong")} == set(ban_do), "chỗ trống lạc ngoài bản đồ"
    phep = [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": f"GT{d['chi_so']}-{c['so']}"}
        for d in dv
        for c in d.get("cho_trong") or []
    ]
    ban, bao_cao = ap_dung_docx(docx, dv, phep)
    assert bao_cao["bo_qua"] == [] and len(bao_cao["da_ap"]) == len(phep)
    chu = "\n".join(d.noi_dung for d in doc("k.docx", ban).don_vi)
    assert all(p["gia_tri"] in chu for p in phep)


@pytest.mark.parametrize("loai", sorted(HANH_CHINH))
def test_khong_dau_giu_cho_nao_tren_trang(loai):
    chu = _chu(_goc(km.dung_docx(_spec(loai))[0]))
    assert not re.search(r"[{}⟦⟧¶]|\[[^\]]*\]|<[^>]*>", chu), chu[:300]


@pytest.mark.parametrize("loai", sorted(HANH_CHINH))
def test_moi_truong_cua_cac_ben_la_mot_cho_trong_co_nhan(loai):
    """Giá trị các bên người dùng nói trong chat thành phép `dien`: mỗi trường của mỗi
    khối bên in trên trang phải có ít nhất một chỗ trống trong bản đồ."""
    entry = km.nap(loai)
    _, ban_do = km.dung_docx(_spec(loai))
    co = {k for ds in ban_do.values() for k in ds if k}
    in_ra = {m["ben"] for m in entry["than"] if "ben" in m}
    for b in entry.get("ben") or []:
        if b["khoa"] not in in_ra:
            continue
        for mau in b.get("dong") or []:
            for t in re.findall(r"\{(\w+)\}", mau if isinstance(mau, str) else mau["d"]):
                assert (b["khoa"], t) in co, (b["khoa"], t)


def test_gia_tri_dien_vao_cho_dan_cham_chi_mot_dau_cach():
    """Bộ áp đặt một dấu cách trước giá trị của chỗ `tab` (`chuan_hoa_dien`): nhãn của
    mẫu đứng liền chỗ trống, nên trang ra "…trình: Phạm Minh Đức;" — không hai dấu cách."""
    docx, _ = km.dung_docx(_spec("van_ban_giai_trinh"))
    dv = _don_vi(docx)
    d = next(x for x in dv if x["noi_dung"].startswith("Họ và tên người giải trình"))
    ban, _ = ap_dung_docx(
        docx, dv, [{"loai": "dien", "don_vi": d["chi_so"], "cho_trong": 0, "gia_tri": " Phạm Minh Đức"}]
    )
    chu = [x.noi_dung for x in doc("k.docx", ban).don_vi]
    assert "Họ và tên người giải trình: Phạm Minh Đức;" in chu


def test_dong_can_cu_cua_khung_dien_xong_khong_con_dan_cham():
    docx, _ = km.dung_docx(_spec("quyet_dinh_ky_luat"))
    dv = _don_vi(docx)
    d = next(x for x in dv if x["noi_dung"].startswith("Căn cứ Nội quy lao động"))
    ban, _ = ap_dung_docx(
        docx,
        dv,
        [{"loai": "dien", "don_vi": d["chi_so"], "cho_trong": 0, "gia_tri": "của Công ty ngày 12 tháng 5 năm 2025"}],
    )
    chu = [x.noi_dung for x in doc("k.docx", ban).don_vi]
    assert "Căn cứ Nội quy lao động của Công ty ngày 12 tháng 5 năm 2025;" in chu


# ── 3. Điều luật đòi ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("loai", sorted(x for x in HANH_CHINH if x in cac_checklist()))
def test_dieu_luat_doi_bi_bo_sot_duoc_chen_thanh_cho_trong_co_ten(loai):
    """Mô hình không viết điều nào: mọi mục luật đòi (trừ mục khung đã có và mục luật để
    ngỏ) lên trang, ở đúng mục thân cố định hay thành một Điều mang tên mục, với chỗ trống."""
    cl = load_checklist_cached(loai)
    entry = km.nap(loai)
    dieu, kq = km.them_dieu_bat_buoc([], loai)
    khong_bb = set(cl.khong_bat_buoc.get("keys") or [])
    mong = {m["key"] for m in cl.muc} - km.khoa_khung(entry) - khong_bb
    assert set(kq["thieu"]) == mong and {d["key"] for d in dieu} == mong
    chu = "\n".join(d["noi_dung"] for d in _don_vi(km.dung_docx(_spec(loai, dieu=dieu))[0]))
    ten = {m["key"]: m["ten"] for m in cl.muc}
    nhan = {m["muc"]: m.get("nhan") for m in entry["than"] if "muc" in m}
    for k in mong:
        # Mục thân cố định không nhãn (công văn: khối nội dung) là chính vị trí của nó.
        if k not in nhan or nhan[k]:
            assert (nhan.get(k) or ten[k]) in chu, k
    assert C in chu


def test_duong_checklist_bo_muc_the_thuc_khoi_dieu_khoan(monkeypatch):
    """Graph checklist viết một điều cho MỌI mục, kể cả quốc hiệu, số, nơi nhận — khung đã
    dựng các mục ấy nên `dat_khuon_mau` bỏ chúng: trang không in "Điều 1. Quốc hiệu…", và
    số Điều của trang bằng số Điều đã lưu (chat "sửa điều 1" trúng đúng điều)."""
    from src.services import ban_thao

    dung: dict = {}

    def _luu(sub, hoi_thoai, loai, tieu_de, docx):
        dung["docx"] = docx
        return {"viec_id": "v1", "don_vi": _don_vi(docx), "so_trang": 1, "ten_tep": "k.docx"}

    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _luu)
    monkeypatch.setattr(ban_thao.graph_soan_thao, "requirements", lambda loai: ([], None, {}))
    monkeypatch.setattr(ban_thao, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(ban_thao, "get_engine", lambda: None)
    clauses = [
        {"key": "quoc_hieu", "ten": "Quốc hiệu và Tiêu ngữ", "noi_dung": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"},
        {"key": "noi_nhan", "ten": "Nơi nhận", "noi_dung": "Như Điều 3"},
        {"key": "noi_dung", "ten": "Bổ nhiệm", "noi_dung": "Bổ nhiệm ông (bà) [họ tên] giữ chức vụ [chức vụ]."},
    ]
    ket = {"clauses": clauses, "audit_report": {}}
    ra = ban_thao.dat_khuon_mau("s", "h1", "quyet_dinh_bo_nhiem", {}, ket)
    assert [c["key"] for c in ra["clauses"]] == ["noi_dung"]
    assert "## Điều 1. Bổ nhiệm" in ra["document"] and "Quốc hiệu" not in ra["document"]
    chu = [d["noi_dung"] for d in _don_vi(dung["docx"])]
    # "./." tách khỏi chỗ trống cuối câu: "……./." thì dấu chấm dính vào chỗ trống.
    assert [c for c in chu if c.startswith("Điều ")] == [f"Điều 1. Bổ nhiệm ông (bà) {C} giữ chức vụ {C} ./."]


# ── 4. Căn cứ ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("loai", sorted(HANH_CHINH))
def test_dong_can_cu_cua_khung_khong_bao_gio_la_luat_thieu_so(loai):
    """Luật, bộ luật, nghị định chỉ đến từ kho (đủ số, ngày) — khung chỉ có chỗ trống cho
    văn bản của CHÍNH tổ chức (Điều lệ, nội quy, hợp đồng, biên bản) hay dòng trống của mẫu."""
    for x in [km.nap(loai), km.nap(loai).get("ban_hanh") or {}]:
        for d in (x.get("the_thuc") or {}).get("can_cu_them") or []:
            mau = d["dong"] if isinstance(d, dict) else d
            assert not re.search(r"\b(Luật|Bộ luật|Nghị định|Thông tư|Nghị quyết)\b", mau), mau


@pytest.mark.parametrize("loai", sorted(QUYET_DINH + KEM_THEO))
def test_can_cu_kho_in_nghieng_dong_cuoi_ket_cham_phay_khi_con_dong_khung(loai):
    docx, _ = km.dung_docx(_spec(loai))
    p = [e for _, chu, e in _doan_than(docx) if chu.startswith("Căn cứ Bộ luật Lao động")]
    assert p and p[0].find(f"{_W}r/{_W}rPr/{_W}i") is not None
    chu = [c for _, c, _ in _doan_than(docx)]
    ld = next(c for c in chu if c.startswith("Căn cứ Luật Doanh nghiệp"))
    assert ld.endswith(";"), "dòng kho cuối kết ';' vì dòng căn cứ của khung đi sau"


def test_khong_co_can_cu_trong_kho_thi_khong_in_dong_luat_nao():
    chu = [c for _, c, _ in _doan_than(km.dung_docx(_spec("quyet_dinh_hdqt", can_cu=[]))[0])]
    can_cu = [c for c in chu if c.startswith(("Căn cứ", "Theo đề nghị"))]
    assert can_cu == ["Căn cứ Điều lệ Công ty;", "Căn cứ Biên bản họp Hội đồng quản trị."]


# ── 5. Bố cục từng mẫu ───────────────────────────────────────────────────────


def _thu_tu(chu: list[str], *moc: str) -> list[int]:
    return [next(i for i, c in enumerate(chu) if c.startswith(m)) for m in moc]


@pytest.mark.parametrize("loai", QUYET_DINH)
def test_quyet_dinh_theo_mau_1_1_1_2(loai):
    """Tên loại → trích yếu → THẨM QUYỀN → căn cứ → "QUYẾT ĐỊNH:"/"QUYẾT NGHỊ:" → Điều
    ("Điều n." đậm mở đầu đoạn, không dòng tên riêng) → "./." → Nơi nhận | người ký."""
    entry = km.nap(loai)
    docx, _ = km.dung_docx(_spec(loai, trich_yeu="bổ nhiệm Phó Giám đốc"))
    than = _doan_than(docx)
    chu = [c for _, c, _ in than]
    lenh = entry["the_thuc"]["lenh"]
    i_loai, i_cc, i_lenh, i_d1 = _thu_tu(chu, entry["tieu_de"], "Căn cứ Bộ luật", lenh, "Điều 1. ")
    assert i_loai < i_cc < i_lenh < i_d1
    # Điều mở đầu bằng run đậm "Điều n. " rồi chính lời điều trong CÙNG đoạn.
    p1 = than[i_d1][2]
    r0 = p1.findall(f"{_W}r")[0]
    assert _chu(r0) == "Điều 1. " and r0.find(f"{_W}rPr/{_W}b") is not None and len(_chu(p1)) > len("Điều 1. ")
    assert not any(re.fullmatch(r"Điều \d+\. ?\S{0,40}", c) for c in chu), "không có dòng tên điều riêng"
    cuoi = [c for c in chu if c.startswith("Điều ")][-1]
    assert cuoi.endswith("./.")
    bang = [e for t, _, e in than if t == "tbl"]
    ky = bang[-1].findall(f"{_W}tr/{_W}tc")
    assert _chu(ky[0]).startswith("Nơi nhận:") and "(Chữ ký của người có thẩm quyền," in _chu(ky[1])


def test_dau_ket_sau_cho_trong_cuoi_cau_dien_xong_van_dung():
    """ "……./." thì dấu chấm của câu thành một phần chỗ trống: điền xong còn "Giám đốc/."."""
    dieu = [{"key": None, "ten": "Bổ nhiệm", "doan": [f"Bổ nhiệm ông (bà) Trần Văn Bình giữ chức vụ {C}."]}]
    docx, _ = km.dung_docx(_spec("quyet_dinh_bo_nhiem", dieu=dieu))
    dv = _don_vi(docx)
    d = next(x for x in dv if x["noi_dung"].startswith("Điều 1."))
    ban, _ = ap_dung_docx(docx, dv, [{"loai": "dien", "don_vi": d["chi_so"], "cho_trong": 0, "gia_tri": "Giám đốc"}])
    chu = [x.noi_dung for x in doc("k.docx", ban).don_vi]
    assert "Điều 1. Bổ nhiệm ông (bà) Trần Văn Bình giữ chức vụ Giám đốc ./." in chu


def test_trich_yeu_mo_hinh_lap_chu_tinh_cua_mau_khong_lap_tren_trang():
    for ty in ("Về việc bổ nhiệm Phó Giám đốc", "về việc bổ nhiệm Phó Giám đốc", "bổ nhiệm Phó Giám đốc"):
        chu = [c for _, c, _ in _doan_than(km.dung_docx(_spec("quyet_dinh_bo_nhiem", trich_yeu=ty))[0])]
        assert "Về việc bổ nhiệm Phó Giám đốc" in chu, ty


def test_ten_co_quan_tham_quyen_chuc_vu_nguoi_ky_in_hoa_du_nguoi_dung_go_thuong():
    docx, ban_do = km.dung_docx(_spec("quyet_dinh_bo_nhiem"))
    goc = _goc(docx)
    cho = [r for r in goc.iter(f"{_W}r") if _chu(r) == C and r.find(f"{_W}rPr/{_W}caps") is not None]
    # Tên cơ quan (đầu trang), thẩm quyền ban hành, chức vụ người ký.
    assert len(cho) == 3
    assert {("co_quan", "ten_to_chuc"), ("van_ban", "tham_quyen"), ("nguoi_ky", "chuc_vu")} <= {
        k for ds in ban_do.values() for k in ds if k
    }


@pytest.mark.parametrize("loai", KEM_THEO)
def test_quy_che_noi_quy_la_quyet_dinh_ban_hanh_roi_van_ban_kem_theo(loai):
    """Mẫu 1.3 + mẫu văn bản kèm theo: trang 1 là QUYẾT ĐỊNH (Số, ngày, căn cứ, Điều 1
    "Ban hành kèm theo Quyết định này …", khối ký, Nơi nhận); ngắt trang; văn bản kèm theo
    không Số, không ngày, không khối ký, mang dòng "(Kèm theo Quyết định số …)"."""
    entry = km.nap(loai)
    docx, _ = km.dung_docx(_spec(loai))
    than = _doan_than(docx)
    ngat = next(
        i for i, (t, _, e) in enumerate(than) if t == "p" and e.find(f".//{_W}br[@{_W}type='page']") is not None
    )
    truoc, sau = than[:ngat], than[ngat + 1 :]
    chu_truoc = [c for _, c, _ in truoc]
    assert "QUYẾT ĐỊNH" in chu_truoc and "QUYẾT ĐỊNH:" in chu_truoc
    ten = entry["tieu_de"][:1] + entry["tieu_de"][1:].lower()
    assert any(c.startswith(f"Điều 1. Ban hành kèm theo Quyết định này {ten}") for c in chu_truoc)
    assert any(c.startswith("Nơi nhận:") for c in chu_truoc)
    chu_sau = " ".join(c for _, c, _ in sau)
    assert entry["tieu_de"] in chu_sau and "(Kèm theo Quyết định số" in chu_sau
    assert "Số:" not in chu_sau and "ngày " + C + " tháng" not in chu_sau.split("(Kèm theo")[0]
    assert "Nơi nhận:" not in chu_sau and "Chữ ký" not in chu_sau
    # Điều khoản của lượt vào văn bản kèm theo, đánh số lại từ 1; "./." sau đoạn cuối.
    assert "Điều 1. Hiệu lực" in chu_sau and chu_sau.rstrip().endswith("./.")
    # Không đoạn rỗng mang chỗ trống nào (đoạn ngắt trang không phải đơn vị văn bản).
    assert all(d["noi_dung"].strip() for d in _don_vi(docx))


def test_ten_van_ban_mang_trich_yeu_quy_che():
    chu = [c for _, c, _ in _doan_than(km.dung_docx(_spec("quy_che_noi_bo", trich_yeu="Quản lý tài sản"))[0])]
    assert "Ban hành Quy chế quản lý tài sản" in chu
    assert "Điều 1. Ban hành kèm theo Quyết định này Quy chế quản lý tài sản" in chu
    assert chu.count("Quản lý tài sản") == 1, "trích yếu dưới tên loại QUY CHẾ ở văn bản kèm theo"


def test_bien_ban_theo_mau_1_9():
    """Không dòng địa danh-ngày ở đầu; câu kết "Cuộc họp … kết thúc vào …" mang "./.";
    THƯ KÝ trái, CHỦ TỌA phải; Nơi nhận DƯỚI hai khối ký."""
    docx, _ = km.dung_docx(_spec("bien_ban_hop_hdqt"))
    than = _doan_than(docx)
    dau = than[0][2]
    assert "ngày" not in _chu(dau) and "Số:" in _chu(dau)
    chu = [c for _, c, _ in than]
    ket = next(c for c in chu if c.startswith("Cuộc họp kết thúc vào"))
    assert ket.endswith("./.") and not any(c.endswith("./.") for c in chu if c != ket)
    i_ky = max(i for i, (t, _, _) in enumerate(than) if t == "tbl")
    o = than[i_ky][2].findall(f"{_W}tr/{_W}tc")
    assert [_chu(x).split("(")[0] for x in o] == ["THƯ KÝ", "CHỦ TỌA"]
    assert any(c.startswith("Nơi nhận:") for c in chu[i_ky + 1 :])
    _, a, b = _thu_tu(chu, "Thời gian bắt đầu", "Chủ trì (chủ tọa)", "Nội dung (theo diễn biến cuộc họp)")
    assert a < b


def test_giay_uy_quyen_ca_nhan_theo_mau_02_nd124():
    docx, _ = km.dung_docx(_spec("giay_uy_quyen"))
    than = _doan_than(docx)
    chu = [c for _, c, _ in than]
    assert chu.index("GIẤY ỦY QUYỀN") < _thu_tu(chu, "Họ và tên người ủy quyền")[0]
    assert _thu_tu(chu, "Họ và tên người ủy quyền")[0] < _thu_tu(chu, "Họ và tên người được ủy quyền")[0]
    i_ky = max(i for i, (t, _, _) in enumerate(than) if t == "tbl")
    o = than[i_ky][2].findall(f"{_W}tr/{_W}tc")
    assert [_chu(x).split("(")[0] for x in o] == ["NGƯỜI ĐƯỢC ỦY QUYỀN", "NGƯỜI ỦY QUYỀN"]
    assert any(c.startswith("XÁC NHẬN CỦA CƠ QUAN,") for c in chu[i_ky + 1 :])


def test_giay_uy_quyen_to_chuc_nguoi_ky_cung_truong_nguoi_dai_dien():
    """Mẫu 1.4: tổ chức ủy quyền là cơ quan ban hành — tên ở đầu trang và ở khối bên ủy
    quyền là CÙNG trường; chức vụ, họ tên người ký là trường của người đại diện."""
    _, ban_do = km.dung_docx(_spec("giay_uy_quyen_to_chuc"))
    dem: dict = {}
    for ds in ban_do.values():
        for k in ds:
            if k:
                dem[k] = dem.get(k, 0) + 1
    assert dem[("co_quan", "ten_to_chuc")] == 2
    assert dem[("co_quan", "chuc_vu")] == 2 and dem[("co_quan", "nguoi_dai_dien")] == 2


def test_van_ban_giai_trinh_to_chuc_theo_cong_van():
    chu = [c for _, c, _ in _doan_than(km.dung_docx(_spec("van_ban_giai_trinh_to_chuc"))[0])]
    assert any("V/v giải trình về vi phạm hành chính" in c for c in chu)
    assert any(c.startswith("Kính gửi:") for c in chu) and "VĂN BẢN GIẢI TRÌNH" not in chu


def test_loi_dap_van_ban_hanh_chinh_noi_the_thuc_la_tap_quan_voi_doanh_nghiep():
    """Quyết định 2026-09-29 ("Consequences"): văn bản của doanh nghiệp tư mang thể thức
    Phụ lục I theo tập quán — lời đáp nói rõ NĐ 30/2020 chỉ buộc khu vực nhà nước."""
    from src.agents.nodes.assemble import assemble
    from src.agents.nodes.route import Intent

    bt = {
        "id": "b1",
        "loai": "quyet_dinh_bo_nhiem",
        "ten": "quyết định bổ nhiệm",
        "phien_ban": 1,
        "document": "# QUYẾT ĐỊNH\n",
        "clauses": [],
        "facts": {},
        "doi_so_voi_truoc": [],
        "audit_report": {"khung": {"bo_cuc": "hanh_chinh", "can_cu": []}},
        "viec_id": "v1",
        "phep_sua": [],
        "khuon": {
            "viec_id": "v1",
            "dinh_dang": "docx",
            "so_trang": 1,
            "nguon": "khuon_mau",
            "can_cu": [],
            "cho_trong": [],
        },
    }
    st = {
        "query": "soạn quyết định bổ nhiệm",
        "intent": Intent.soan_thao,
        "user_sub": "s",
        "muc_dich_tai_lieu": "tao_van_ban",
        "ban_thao_ket": bt,
        "khuon_mau_tong_quat": {},
    }
    a = assemble(st, {}, None, "")["answer"]
    assert "bắt buộc với cơ quan, tổ chức nhà nước và doanh nghiệp nhà nước" in a and "tập quán" in a


def test_luot_chat_xin_trich_yeu_va_trang_in_mot_lan(monkeypatch):
    """Loại hành chính có dòng trích yếu ("Về việc …"): prompt v3 xin `trich_yeu` (quy tắc 2
    để null với loại có sẵn), `kiem_khuon_mau` giữ nó, trang in "Về việc …" đúng một lần
    dù mô hình viết kèm "Về việc". Mô hình GIẢ, không DB."""
    import json

    from src.agents import graph_tra_cuu as g
    from src.agents.nodes import hieu_tai_lieu as h
    from src.agents.nodes.route import Intent

    class _Usage:
        token_in, token_out, cost_usd = 1, 1, 0.0

    class _LLM:
        prompt = ""

        def chat(self, model, messages, json_schema=None, max_tokens=None):
            _LLM.prompt = messages[-1]["content"]
            ra = {
                "muc_tieu": "ban_moi",
                "tieu_de": None,
                "trich_yeu": "Về việc bổ nhiệm Phó Giám đốc kinh doanh",
                "bo_cuc": None,
                "ben": None,
                "can_cu": None,
                "gia_tri": [],
                "sua_dieu": None,
                "khong_dat": [],
                "dieu": [{"key": "noi_dung", "ten": "Bổ nhiệm", "doan": [f"Bổ nhiệm ông (bà) {C} giữ chức vụ {C}."]}],
            }
            return json.dumps(ra, ensure_ascii=False), _Usage()

    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), {}))
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(g.gst, "can_cu_van_ban_co_id", lambda e, d_, a: [])
    cau = "Soạn quyết định bổ nhiệm Phó Giám đốc kinh doanh"
    st = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "quyet_dinh_bo_nhiem"}})
    st.update(query=cau, cau_hoi_goc=cau, intent=Intent.soan_thao, user_sub="s", hoi_thoai_id="h")
    ra = h.hieu_tai_lieu(st, [], _LLM(), "m")
    assert "`trich_yeu`: nội dung chính của văn bản" in _LLM.prompt
    khung = ra["khuon_mau_tong_quat"]["khung"]
    assert khung["trich_yeu"] == "Về việc bổ nhiệm Phó Giám đốc kinh doanh"
    docx, _ = km.dung_docx(
        km.spec_tu(km.nap("quyet_dinh_bo_nhiem"), tieu_de=None, trich_yeu=khung["trich_yeu"], can_cu=[], dieu=[])
    )
    chu = [c for _, c, _ in _doan_than(docx)]
    assert "Về việc bổ nhiệm Phó Giám đốc kinh doanh" in chu and not any("Về việc Về việc" in c for c in chu)
