"""Khuôn mẫu nhóm ĐƠN TỪ và giấy tờ (thiết kế `khuon-mau-thiet-ke.md` §1, §7; quyết định
2026-09-29 mục 5–8): đơn khởi kiện, đơn khiếu nại, đơn xin nghỉ việc và các loại người
dùng đã hỏi (tạm hoãn nghĩa vụ quân sự, học lại, kiểm điểm, biên bản họp, giấy tờ thực
tập).

Không DB, không mô hình. Mỗi loại khoá bốn điều:

1. Registry nạp được; mọi chỗ trống bộ dựng viết là chỗ trống bộ đọc của khuôn gốc
   thấy (không thiếu, không lạc), mọi trường của các bên trỏ tới một chỗ trống, bộ áp
   điền được hết.
2. Mục luật đòi (checklist) luôn có chỗ trên trang: không mục nào bị bộ dựng bỏ lặng lẽ.
3. Căn cứ của từng mục (checklist `can_cu`) là điều khoản có thật của văn bản được
   hiện — ở đây trên `data/seed`; phép hiện đầy đủ (hiệu lực, link) chạy trên DB thật
   ở `test_khuon_mau_don_tu_db.py`.
4. Bố cục đúng mẫu: bảng đầu trang và khối ký không viền, bảng dữ liệu có viền và ô
   trống là chỗ `o` mang tên cột; biên bản đặt "Nơi nhận" dưới hai khối ký.

Trang thật (LibreOffice) ở cuối tệp, bỏ qua khi máy không có `soffice`.
"""

import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from src.agents.graph_soan_thao import cac_loai as cac_checklist
from src.agents.graph_soan_thao import load_checklist_cached
from src.services import ban_thao
from src.services import khuon_mau as km
from src.services.dien_khuon import ap_dung_docx
from src.services.doc_tai_lieu import doc
from src.services.hien_thi import TINH_TRANG_HIEN
from src.services.tai_lieu import _hang_don_vi

LOAI = [
    "don_khoi_kien",
    "don_khieu_nai",
    "don_xin_nghi_viec",
    "don_xin_tam_hoan_nvqs",
    "don_xin_hoc_lai",
    "ban_kiem_diem_ca_nhan",
    "bien_ban_hop",
    "giay_tiep_nhan_thuc_tap",
    "phieu_danh_gia_thuc_tap",
    "ke_hoach_thuc_tap",
    "don_dang_ky_thuc_tap",
]
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SEED = Path("data/seed")


def _dieu_mau(loai: str) -> list[dict]:
    """Một đoạn cho mỗi mục thân của mẫu, cộng hai điều không khoá cho loại có danh sách
    Điều — như một lượt v3 đã qua `kiem_khuon_mau`."""
    e = km.nap(loai)
    ra = [{"key": k, "ten": "", "doan": [f"Nội dung mục {k} với một chỗ trống ……."]} for k in sorted(km.muc_than(e))]
    if any("dieu" in m for m in e["than"]):
        ra += [
            {"key": None, "ten": "Mục tiêu", "doan": ["Hoàn thành công việc đúng thời hạn ……."]},
            {"key": None, "ten": "Nội dung", "doan": ["Đoạn thứ nhất.", "Đoạn thứ hai."]},
        ]
    return km.them_dieu_bat_buoc(ra, loai)[0]


def _dung(loai: str, dieu: list[dict] | None = None) -> tuple[bytes, dict, list[dict]]:
    spec = km.spec_tu(
        km.nap(loai), tieu_de=None, trich_yeu=None, can_cu=[], dieu=_dieu_mau(loai) if dieu is None else dieu
    )
    docx, ban_do = km.dung_docx(spec)
    return docx, ban_do, [_hang_don_vi(d) for d in doc(f"{loai}.docx", docx).don_vi]


def _theo_dia_chi(dv: list[dict]) -> dict:
    return {(d["dia_chi"]["phan"], tuple(d["dia_chi"]["chi_muc"])): d for d in dv if d.get("dia_chi")}


@pytest.mark.parametrize("loai", LOAI)
def test_nap_duoc_va_ghi_nguon(loai):
    e = km.nap(loai)
    assert e["loai"] == loai and e["bo_cuc"] in km.BO_CUC
    assert e["nguon"].get("ghi_chu") or e["nguon"].get("van_ban")


@pytest.mark.parametrize("dieu", [None, []], ids=["co_dieu", "trong"])
@pytest.mark.parametrize("loai", LOAI)
def test_moi_cho_trong_bo_dung_viet_la_cho_bo_doc_thay(loai, dieu):
    docx, ban_do, dv = _dung(loai, dieu)
    theo = _theo_dia_chi(dv)
    for k, ds in ban_do.items():
        assert len(theo[k].get("cho_trong") or []) == len(ds), theo[k]["noi_dung"]
    assert {k for k, d in theo.items() if d.get("cho_trong")} == set(ban_do), "chỗ trống lạc ngoài bản đồ"


@pytest.mark.parametrize("loai", LOAI)
def test_moi_truong_cua_cac_ben_tro_toi_cho_trong_va_bo_ap_dien_het(loai):
    docx, ban_do, dv = _dung(loai)
    o = ban_thao.o_truong(dv, ban_do)
    co = {(x["ben"], x["truong"]) for x in o}
    e = km.nap(loai)
    for b in e.get("ben") or []:
        for t in [
            *(b.get("truong") or []),
            *(x for d in b.get("dong") or [] for x in km._cac_o(km._chuoi_cua_dong(d))),
        ]:
            if t and ({"ben": b["khoa"]} in e["than"] or b["khoa"] == "co_quan"):
                assert (b["khoa"], t) in co, (b["khoa"], t)
    # Tên dưới chữ ký là CÙNG trường họ tên của bên ký: điền một lần, hiện cả hai nơi.
    for x in (e.get("ky") or {}).get("o") or []:
        if x.get("ho_ten_tu"):
            assert (x["khoa"], x["ho_ten_tu"]) in co, x["khoa"]
    phep = [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": f"GT{d['chi_so']}-{c['so']}"}
        for d in dv
        for c in d.get("cho_trong") or []
    ]
    ban, bao_cao = ap_dung_docx(docx, dv, phep)
    assert phep and bao_cao["bo_qua"] == [] and len(bao_cao["da_ap"]) == len(phep)
    chu = "\n".join(d.noi_dung for d in doc("k.docx", ban).don_vi)
    assert all(p["gia_tri"] in chu for p in phep)


@pytest.mark.parametrize("loai", LOAI)
def test_khong_dau_giu_cho_nao_trong_tep(loai):
    docx, _, _ = _dung(loai)
    with zipfile.ZipFile(io.BytesIO(docx)) as z:
        for ten in z.namelist():
            chu = "".join(t.text or "" for t in etree.fromstring(z.read(ten)).iter(f"{_W}t"))
            assert not re.search(r"[{}⟦⟧¶]|\[[^\]]*\]|<[^>]*>", chu), (ten, chu[:200])


def _chu_doan(docx: bytes) -> list[str]:
    """Chữ từng `w:p`, `w:tab` là "\\t" — `noi_dung` bỏ tab, nên không thấy một giá trị
    dính chữ đứng sau dòng chấm của nó."""
    goc = etree.fromstring(zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml"))
    return [
        "".join(
            (e.text or "") if e.tag == f"{_W}t" else "\t"
            for r in p.iter(f"{_W}r")
            for e in r.iter(f"{_W}t", f"{_W}tab")
        )
        for p in goc.iter(f"{_W}p")
    ]


@pytest.mark.parametrize("nguon", ["chen_bat_buoc", "co_dieu"])
@pytest.mark.parametrize("loai", LOAI)
def test_moi_cho_trong_dien_qua_trang_cach_chu_dung_mot_dau_cach(loai, nguon):
    """Điền MỌI chỗ trống bộ đọc báo, đúng đường `/o-dien` (`chuan_hoa_dien` → bộ áp):
    không giá trị nào dính chữ hai bên ("kết thúc vào16 giờ30"), không dòng nào mang hai
    dấu cách liền (nhãn mẫu giữ dấu cách trước dãy chấm: "Số điện thoại: ……(nếu có)")."""
    dieu = km.them_dieu_bat_buoc([], loai)[0] if nguon == "chen_bat_buoc" else None
    docx, _, dv = _dung(loai, dieu)
    cho = ban_thao.cho_trong_khuon("docx", dv, [])
    phep = [
        {"loai": "dien", "don_vi": o["don_vi"], "cho_trong": o["so"], "gia_tri": ban_thao.chuan_hoa_dien("Giá Trị", o)}
        for o in cho
    ]
    ban, bao_cao = ban_thao.ap_phep_sua("docx", docx, dv, phep)
    assert cho and bao_cao["bo_qua"] == []
    chu = [c for c in _chu_doan(ban) if "Giá Trị" in c]
    assert sum(c.count("Giá Trị") for c in chu) == len(cho)
    assert not [c for c in chu if re.search(r"\wGiá Trị|Giá Trị\w|  ", c)]


@pytest.mark.parametrize("loai", [lo for lo in LOAI if lo in cac_checklist()])
def test_moi_muc_checklist_co_cho_tren_trang(loai):
    """Mục luật đòi luôn có chỗ: là khối khung (bên, ngày, ký), một mục thân của mẫu, hay
    rơi vào danh sách Điều — bộ dựng không bỏ lặng lẽ mục nào (`_Dung.than`)."""
    e = km.nap(loai)
    co_dieu = any("dieu" in m for m in e["than"])
    cho = km.khoa_khung(e) | km.muc_than(e)
    for m in load_checklist_cached(loai).muc:
        assert co_dieu or m["key"] in cho, m["key"]


def _khong_ten(dv: list[dict]) -> int:
    return sum(1 for o in ban_thao.cho_trong_khuon("docx", dv, []) if not o["nhan"])


@pytest.mark.parametrize("loai", [lo for lo in LOAI if lo in cac_checklist()])
def test_muc_chen_vi_luat_doi_in_cho_trong_co_ten(loai):
    """Lúc tạo không có điều khoản nào: mục luật đòi được chèn một "……" (`them_dieu_bat_buoc`).
    Trên trang nó là chỗ trống CỦA MẪU (dòng dẫn chấm, "1 ……", nhãn mang `{}`) hay một
    dòng mang tên mục — không bao giờ một "……" trơ trọi mà trang gọi "Chỗ trống (n)"."""
    dieu, kq = km.them_dieu_bat_buoc([], loai)
    assert kq["thieu"] and {d["key"] for d in dieu if d.get("chen")} == set(kq["thieu"])
    docx, _, dv = _dung(loai, dieu)
    rong, _, dv_rong = _dung(loai, [])
    assert _khong_ten(dv) == _khong_ten(dv_rong), [d["noi_dung"] for d in dv]
    if not any("dieu" in m for m in km.nap(loai)["than"]):
        # Mẫu chỉ có mục cố định (NĐ 124 Mẫu 01, Mẫu 23-DS): mục chèn trống in ĐÚNG bản trống.
        assert docx == rong
    else:
        ten = {m["key"]: m["ten"] for m in load_checklist_cached(loai).muc}
        assert {ten[k] for k in kq["thieu"]} <= {o["nhan"] for o in ban_thao.cho_trong_khuon("docx", dv, [])}


@pytest.mark.parametrize("loai", LOAI)
def test_loai_khong_checklist_khong_doi_muc_nao(loai):
    if loai in cac_checklist():
        pytest.skip("có checklist")
    dieu = _dieu_mau(loai)
    assert km.them_dieu_bat_buoc(dieu, loai)[1] == {"thieu": [], "completeness": None}


@pytest.fixture
def duong_checklist(monkeypatch):
    """`dat_khuon_mau` không DB, không LibreOffice (như `test_mang_phep_sang`): yêu cầu
    checklist rỗng, tệp "lưu" được đọc lại bằng bộ đọc thật."""
    monkeypatch.setattr(ban_thao.graph_soan_thao, "requirements", lambda loai: ([], None, {}))
    monkeypatch.setattr(ban_thao, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(ban_thao, "get_engine", lambda: None)
    tep: dict = {}

    def _luu(sub, hoi_thoai_id, loai, tieu_de, docx):
        tep["docx"] = docx
        dv = [_hang_don_vi(d) for d in doc("k.docx", docx).don_vi]
        return {"viec_id": "viec-1", "don_vi": dv, "so_trang": 1, "ten_tep": "k.docx"}

    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _luu)
    return tep


@pytest.mark.parametrize("loai", [lo for lo in LOAI if lo in cac_checklist()])
def test_duong_checklist_bo_dieu_khoan_cua_khoi_khung(loai, duong_checklist):
    """Đường checklist (`dat_khuon_mau`: drawer dựng lại, phiên checklist mở dở) nhận MỘT
    điều khoản cho mọi mục checklist, kể cả mục khung đã dựng (các bên, ngày, chữ ký). Mục
    khung không in thành đoạn thân (trùng khối các bên), không lặng lẽ biến mất khỏi một
    trang vẫn đếm nó, và không nằm lại trong `clauses` (bản lưu = trang). Không mất dữ kiện
    nào: checklist này không gom fact nào (`rules: []`), nên `truong_tu_facts` không có gì
    để ánh xạ và chữ của mục khung chỉ là lời mô hình viết khi không biết gì."""
    from src.agents.nodes.gom_du_kien import truong_cua

    assert truong_cua(loai) == []
    muc = load_checklist_cached(loai).muc
    ket = {
        "document": "",
        "clauses": [
            {"key": m["key"], "ten": m["ten"], "noi_dung": f"Chữ mục {m['key']}.", "can_cu_provision_id": 0}
            for m in muc
        ],
        "audit_report": {"dat": True, "findings": []},
        "can_cu_co_id": [],
    }
    ra = ban_thao.dat_khuon_mau("s", "h", loai, {}, ket)
    khung = km.khoa_khung(km.nap(loai))
    chu = "\n".join(_chu_doan(duong_checklist["docx"]))
    giu = [m["key"] for m in muc if m["key"] not in khung]
    assert [c["key"] for c in ra["clauses"]] == giu
    assert [k for k in giu if f"Chữ mục {k}." not in chu] == [], chu
    assert [k for k in khung if f"Chữ mục {k}." in chu] == []


def _seed_provisions(duong_dan: set[str]) -> dict[str, str]:
    ra = {}
    with (SEED / "provisions.jsonl").open(encoding="utf-8") as f:
        for dong in f:
            r = json.loads(dong)
            if r.get("duong_dan") in duong_dan:
                ra[r["duong_dan"]] = r["document_id"]
    return ra


def test_can_cu_cua_muc_la_dieu_khoan_that_cua_van_ban_con_hieu_luc():
    can_cu = {m["can_cu"] for lo in LOAI if lo in cac_checklist() for m in load_checklist_cached(lo).muc}
    tim = _seed_provisions(can_cu)
    assert can_cu == set(tim), sorted(can_cu - set(tim))
    tinh_trang = {}
    with (SEED / "documents.jsonl").open(encoding="utf-8") as f:
        for dong in f:
            r = json.loads(dong)
            tinh_trang[r["id"]] = r["tinh_trang"]
    assert all(tinh_trang.get(d) in TINH_TRANG_HIEN for d in tim.values()), {d: tinh_trang.get(d) for d in tim.values()}


@pytest.mark.parametrize("loai", LOAI)
def test_khung_khong_in_dong_can_cu_nao(loai):
    """Đơn, biên bản, giấy tờ thực tập không có khối căn cứ (các mẫu gốc không có; Luật
    Nghĩa vụ quân sự chưa có trong kho): căn cứ của lượt không bao giờ in ra ở đây."""
    e = km.nap(loai)
    assert not e["the_thuc"].get("can_cu")
    spec = km.spec_tu(e, tieu_de=None, trich_yeu=None, can_cu=[{"dong": "Căn cứ X;", "doc_id": "1"}], dieu=[])
    assert "Căn cứ X" not in "\n".join(
        d["noi_dung"] for d in [_hang_don_vi(x) for x in doc("k.docx", km.dung_docx(spec)[0]).don_vi]
    )


@pytest.mark.parametrize("loai", LOAI)
def test_bang_dau_trang_va_khoi_ky_khong_vien_bang_du_lieu_co_vien(loai):
    docx, _, dv = _dung(loai)
    co_bang_du_lieu = any("bang" in m for m in km.nap(loai)["than"])
    for d in dv:
        if not d.get("bang"):
            continue
        o = [c for c in d.get("cho_trong") or [] if c["kieu"] == "o"]
        if d["bang_vien"]:
            assert co_bang_du_lieu
        else:
            assert not o, "bảng xếp chỗ không mời ô nào"
    if co_bang_du_lieu:
        nhan = {c["nhan"] for d in dv for c in d.get("cho_trong") or [] if c["kieu"] == "o"}
        assert nhan and all(re.search(r" \(dòng \d+\)$", n) for n in nhan), nhan


def test_phieu_danh_gia_o_diem_mang_ten_cot_va_dong():
    _, _, dv = _dung("phieu_danh_gia_thuc_tap")
    nhan = {c["nhan"] for d in dv for c in d.get("cho_trong") or [] if c["kieu"] == "o"}
    assert {"Điểm đánh giá (dòng 1)", "Điểm đánh giá (dòng 6)", "Điểm tối đa (dòng 1)"} <= nhan


def test_bien_ban_noi_nhan_duoi_hai_khoi_ky_thu_ky_trai_chu_toa_phai():
    docx, _, dv = _dung("bien_ban_hop")
    chu = [d["noi_dung"] for d in dv]
    ky = next(i for i, c in enumerate(chu) if c.startswith("THƯ KÝ"))
    assert chu[ky + 1].startswith("CHỦ TỌA"), "hai khối ký cùng một hàng, THƯ KÝ trước"
    assert chu.index("Nơi nhận:") > ky + 1, "Nơi nhận ở dưới khối ký"
    assert any(c.endswith("./.") and c.startswith("Cuộc họp") for c in chu), "./. sau câu kết"
    # Không có dòng địa danh-ngày ở đầu biên bản (Mẫu 1.9).
    assert not any(re.search(r"ngày …… tháng …… năm ……$", c) for c in chu[:3])


def test_don_khieu_nai_noi_dung_dien_ngay_sau_nhan_va_giu_dau_cau_cua_mau():
    dieu = [
        {"key": "ve_viec", "ten": "", "doan": ["Khiếu nại lần đầu quyết định xử phạt."]},
        {"key": "noi_dung_ly_do", "ten": "", "doan": ["Tôi không vi phạm.", "Đề nghị hủy quyết định"]},
    ]
    _, _, dv = _dung("don_khieu_nai", dieu)
    chu = [d["noi_dung"] for d in dv]
    assert "Khiếu nại về việc: Khiếu nại lần đầu quyết định xử phạt;" in chu
    assert "Nội dung khiếu nại: Tôi không vi phạm." in chu and "Đề nghị hủy quyết định." in chu
    # Yêu cầu giải quyết: mục checklist không nhãn, KHÔNG in khi trống (mẫu không có dòng đó).
    assert not [c for c in chu if c == km.CHO]


def test_ky_nhieu_cot_ho_ten_thang_hang():
    """Các cột ký có cùng số đoạn trước dòng họ tên (dòng chức danh, ghi chú đệm thêm)."""
    docx, _, _ = _dung("bien_ban_hop")
    goc = etree.fromstring(zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml"))
    bang_ky = [t for t in goc.iter(f"{_W}tbl") if any("THƯ KÝ" in (x.text or "") for x in t.iter(f"{_W}t"))][0]
    so_doan = [len(tc.findall(f"{_W}p")) for tc in bang_ky.iter(f"{_W}tc")]
    assert len(set(so_doan)) == 1, so_doan


# ─── Trang thật (LibreOffice), tuần tự ─────────────────────────────────────


@pytest.mark.skipif(not (shutil.which("soffice") and shutil.which("pdftoppm")), reason="cần LibreOffice và poppler")
@pytest.mark.parametrize("loai", LOAI)
def test_trang_that_mot_trang_va_phep_do_dinh_vi_moi_cho_trong(loai):
    """Bản trống mỗi mẫu ra MỘT trang A4, và phép dò của `/ban-thao/{id}/trang` định vị
    được mọi chỗ trống (các bên, ngày, ô bảng)."""
    from src.services import dung_trang

    docx, _, dv = _dung(loai, [])
    assert dung_trang.so_trang_pdf(dung_trang.dung_pdf(docx)) == 1
    _, png, vi_tri = dung_trang.dung("docx", docx, "thu-don-tu", None, ban_thao.ban_do("docx", dv, []))
    moi = {(d["chi_so"], c["so"]) for d in dv for c in d.get("cho_trong") or []}
    assert png and moi <= set(vi_tri), sorted(moi - set(vi_tri))


@pytest.mark.skipif(not (shutil.which("soffice") and shutil.which("pdftoppm")), reason="cần LibreOffice và poppler")
def test_ke_hoach_ba_muc_trang_cuoi_khong_chi_co_khoi_ky():
    """Kế hoạch ba mục ra hai trang: đuôi bảng tiến độ sang trang cùng ba chữ ký — trang
    cuối không bao giờ chỉ có khối ký (trang chữ ký rời)."""
    from src.services import dung_trang

    dieu = [
        {"key": None, "ten": "Mục tiêu thực tập", "doan": ["Nắm được quy trình phát triển phần mềm tại doanh nghiệp."]},
        {
            "key": None,
            "ten": "Nội dung công việc",
            "doan": [
                "Giai đoạn đầu: tìm hiểu cơ cấu tổ chức, nội quy và sản phẩm của công ty.",
                "Giai đoạn giữa: tham gia viết ca kiểm thử và thực hiện kiểm thử chức năng.",
                "Giai đoạn cuối: tổng hợp kết quả, viết báo cáo thực tập.",
            ],
        },
        {"key": None, "ten": "Kết quả dự kiến", "doan": ["Hoàn thành báo cáo thực tập và bộ tài liệu kiểm thử."]},
    ]
    docx, _, _ = _dung("ke_hoach_thuc_tap", dieu)
    dv = doc("k.pdf", dung_trang.dung_pdf(docx)).don_vi
    cuoi = max(d.trang for d in dv)
    assert cuoi == 2, "kịch bản cần hai trang"
    assert any(" đến " in d.noi_dung for d in dv if d.trang == cuoi), [d.noi_dung for d in dv if d.trang == cuoi]


# ─── Ngữ cảnh của lượt soạn (prompt v3) ─────────────────────────────────────


@pytest.mark.parametrize(
    ("loai", "khoa", "co_trich_yeu"),
    [
        ("don_xin_hoc_lai", ["ly_do", "noi_dung"], False),
        ("giay_tiep_nhan_thuc_tap", ["noi_dung"], False),
        ("bien_ban_hop", ["noi_dung"], True),
    ],
)
def test_ngu_canh_loai_khong_checklist_dung_ten_muc_cua_registry(loai, khoa, co_trich_yeu):
    """Loại không checklist không chạm DB: mục thân của mẫu đi thẳng vào prompt, tên mục
    là `ten` (không phải nhãn mang `{}`), và mẫu không trích yếu thì mô hình không viết."""
    from src.agents.graph_tra_cuu import _nap_khuon_mau

    ng = _nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": loai}})["khuon_mau_ngu_canh"]
    assert ng["loai"] == loai and ng["khoa"] == khoa and ng["co_trich_yeu"] is co_trich_yeu
    assert not [m for m in ng["muc"] if "{" in m["ten"]]


def test_prompt_mang_huong_dan_cua_mau_chinh_thuc():
    from src.agents.nodes.hieu_tai_lieu import _khoi_muc_khuon_mau

    e = km.nap("don_khieu_nai")
    muc = [
        {"key": m["muc"], "ten": m.get("ten") or m["muc"], "trich": "", "huong_dan": m.get("huong_dan")}
        for m in e["than"]
        if "muc" in m
    ]
    khoi = _khoi_muc_khuon_mau({"muc": muc, "khoa_than": sorted(km.muc_than(e)), "co_dieu": False})
    assert "(hướng dẫn của mẫu: (5) Khiếu nại quyết định hành chính, hành vi hành chính về việc gì" in khoi
    assert "Chỉ viết đúng các mục dưới đây" in khoi


@pytest.mark.parametrize(
    ("loai", "bo_cuc", "mong"),
    [
        ("don_khieu_nai", "don", " Trình bày theo Nghị định 124/2020/NĐ-CP, Mẫu số 01."),
        ("don_khoi_kien", "don", " Trình bày theo Nghị quyết 01/2017/NQ-HĐTP, Mẫu số 23-DS."),
        ("don_xin_hoc_lai", "don", " Thể thức theo tập quán, tham khảo Phụ lục I Nghị định 30/2020/NĐ-CP."),
        # NĐ 30 chỉ buộc cơ quan nhà nước (Đ2.1): nói rõ, không gọi là luật đòi (quyết
        # định 2026-09-29, Consequences).
        (
            "bien_ban_hop",
            "hanh_chinh",
            " Thể thức theo Phụ lục I Nghị định 30/2020/NĐ-CP: bắt buộc với cơ quan, tổ chức nhà nước và doanh"
            " nghiệp nhà nước; với doanh nghiệp, tổ chức khác là tập quán.",
        ),
    ],
)
def test_loi_dap_noi_dung_nguon_the_thuc(loai, bo_cuc, mong):
    """Mẫu chính thức không bị gọi là "tập quán" (owner: không nói điều không đúng)."""
    from src.agents.nodes.assemble import _cau_the_thuc

    assert _cau_the_thuc({"loai": loai, "bo_cuc": bo_cuc}) == mong
