import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import build_seed
from scripts.fetch_moj import DOC_IDS
from src.models.domain import Cap
from src.services import prov_parser


def _metadata_rong(raw: Path) -> None:
    """`build()` giờ đọc `data/raw/metadata.parquet` cho `linh_vuc` (T1, 8 lĩnh
    vực) — test ở đây soi vòng lặp MOJ/chinhphu, không soi tra cứu linh_vực,
    nên chỉ cần file tồn tại đúng schema, không cần dữ liệu thật."""
    pd.DataFrame({"id": pd.array([], dtype="string"),
                  "nganh": pd.array([], dtype="string"),
                  "linh_vuc": pd.array([], dtype="string")}).to_parquet(
        raw / "metadata.parquet")


def test_du_6_bo_luat_o_tang_sau():
    bo_luat = {"95942", "96122", "96115", "96172", "139264", "96117"}
    assert bo_luat <= set(DOC_IDS)
    assert all(DOC_IDS[d][0] == "deep" for d in bo_luat)


def test_co_hai_van_ban_bay_hieu_luc():
    # NĐ 74/2024 hết hiệu lực toàn bộ; NĐ 90/2019 MOJ đánh sai "còn hiệu lực"
    assert "168670" in DOC_IDS and "139094" in DOC_IDS


def test_moi_doc_id_co_so_ky_hieu_khong_rong():
    assert all(skh for _, skh in DOC_IDS.values()), "định danh bằng so_ky_hieu, không bằng title"



# ══ Mục H.3 — thay test không thể thất bại ══

def test_so_ky_hieu_duy_nhat_tren_toan_seed():
    """Thay `test_khong_co_doc_id_trung`, vốn assert `len(dict) == len(set(dict))`
    — một hằng đúng của Python, không bao giờ đỏ được. Định danh nghiệp vụ là
    `so_ky_hieu`: hai doc_id cùng so_ky_hieu thì mọi duong_dan của chúng trùng
    nhau và neo trích dẫn mất tính duy nhất trên toàn corpus."""
    skh = [v[1] for v in DOC_IDS.values()]
    assert len(skh) == len(set(skh)), \
        f"so_ky_hieu trùng: {sorted(x for x in skh if skh.count(x) > 1)}"


# ══ Mục H.1 + H.4 — build() gọi parse_anomalies và fail; build() có test ══

def test_build_ghi_du_ba_file_va_checksums(tmp_path, monkeypatch):
    """`build()` chưa có test nào trước vòng này."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "9001.json").write_text(json.dumps({
        "docNum": "1/2020/NĐ-CP",
        "title": "Nghị định thử",
        "docType": {"name": "Nghị định"},
        "effStatus": {"code": "CHL"},
        "issueDate": "2020-01-02T00:00:00",
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            '<p class="prov-clause">1. Nội dung khoản một.</p></div>'},
        "references": [{"targetDocument": {"id": 7, "docNum": "45/2019/QH14"},
                        "referenceType": 3}],
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(build_seed, "DOC_IDS", {"9001": ("deep", "1/2020/NĐ-CP")})
    # Nguồn thứ hai tắt: mỗi test ở đây soi RIÊNG vòng lặp MOJ. Không tắt thì
    # build đi tìm data/raw/chinhphu và đỏ vì một lý do không liên quan.
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    out = tmp_path / "seed"
    assert build_seed.build(tmp_path / "raw", out) == {
        "documents": 1, "provisions": 2, "references": 1}

    provs = [json.loads(x) for x in (out / "provisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert all(p["document_id"] == "9001" for p in provs)
    assert all(p["noi_dung"].strip() for p in provs), "seed ghi noi_dung rỗng"
    cs = json.loads((out / "checksums.json").read_text(encoding="utf-8"))
    assert cs["documents"].keys() == {"9001"}
    # mục `files` là thứ `scripts.ingest._kiem_toan_ven` đọc để bắt seed bị sửa
    # tay; nếu build ghi sai thì ingest chặn cả đường lành.
    assert cs["files"] == {n: build_seed.bam_tep(out / n) for n in
                           ("documents.jsonl", "provisions.jsonl", "references.jsonl")}


def test_build_FAIL_khi_so_ky_hieu_khai_bao_lech_docNum_cua_gateway(tmp_path, monkeypatch):
    """`so_ky_hieu` trong `DOC_IDS` là chữ gõ tay; `docNum` là chữ CSDL quốc gia
    khai cho ĐÚNG id đó. Lệch nhau nghĩa là id sai hoặc gõ sai — nạp tiếp là
    đặt toàn văn một văn bản dưới số hiệu của văn bản khác (đo 2026-09-28: 53/53
    khớp, nên cổng này không chặn văn bản nào đang có)."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "9004.json").write_text(json.dumps({
        "docNum": "38/2022/NĐ-CP",
        "docType": {"name": "Nghị định"}, "effStatus": {"code": "HHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            '<p class="prov-clause">1. Nội dung khoản một.</p></div>'},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(build_seed, "DOC_IDS", {"9004": ("deep", "90/2019/NĐ-CP")})
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    with pytest.raises(ValueError, match="docNum"):
        build_seed.build(tmp_path / "raw", tmp_path / "seed")


def test_build_FAIL_khi_parse_anomalies_bao_bat_thuong(tmp_path, monkeypatch):
    """Mục H: parse_anomalies đã tồn tại, đã có test, CHƯA AI CHẠY trên dữ liệu
    thật — build_seed không gọi nó. Đó là lý do cả bốn lỗi kia lọt được."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "9002.json").write_text(json.dumps({
        "docNum": "2/2020/NĐ-CP",
        "docType": {"name": "Nghị định"}, "effStatus": {"code": "CHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            # neo trích dẫn nằm trong <table> → ra khỏi cây → lỗi CHẶN
            '<table><tr><td><p class="prov-clause">1. Vùng I.</p></td></tr></table>'
            "</div>"},
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(build_seed, "DOC_IDS", {"9002": ("deep", "2/2020/NĐ-CP")})
    # Nguồn thứ hai tắt: mỗi test ở đây soi RIÊNG vòng lặp MOJ. Không tắt thì
    # build đi tìm data/raw/chinhphu và đỏ vì một lý do không liên quan.
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    with pytest.raises(ValueError, match="bất thường cấu trúc"):
        build_seed.build(tmp_path / "raw", tmp_path / "seed")


def _doc_mot_dieu(so_ky_hieu: str, **them) -> str:
    return json.dumps({
        "docNum": so_ky_hieu,
        "docType": {"name": "Luật"}, "effStatus": {"code": "CHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            '<p class="prov-clause">1. Nội dung khoản một.</p></div>'},
        **them,
    }, ensure_ascii=False)


def test_build_CANH_BAO_khi_gateway_tra_references_null(tmp_path, monkeypatch):
    """`references: null` KHÁC `[]`. Từ 2026-09-28 gateway trả null cho mọi văn
    bản — kể cả 161263 và 152668, mà bản cache 2026-09-02 có 8 và 31 quan hệ.
    Đọc null như rỗng là nạp văn bản với 0 quan hệ cấp văn bản mà không ai hay —
    cùng lỗi gộp rỗng-với-đổi-shape `MojClient.fetch_related` cấm."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "9005.json").write_text(_doc_mot_dieu("5/2020/QH14", references=None), encoding="utf-8")
    (raw / "9006.json").write_text(_doc_mot_dieu("6/2020/QH14", references=[]), encoding="utf-8")
    monkeypatch.setattr(build_seed, "DOC_IDS", {"9005": ("deep", "5/2020/QH14"),
                                                "9006": ("deep", "6/2020/QH14")})
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    with pytest.warns(UserWarning, match="9005.*references") as bat:
        build_seed.build(tmp_path / "raw", tmp_path / "seed")
    assert not any("9006" in str(w.message) for w in bat), "`[]` là rỗng thật, không cảnh báo"


def test_build_BO_canh_MOJ_da_doi_chieu_la_sai(tmp_path, monkeypatch):
    """Mảng `references` của 19/2023/QH15 ghi loai 10 "Sửa đổi, bổ sung" tới
    BLLĐ 45/2019/QH14, trong khi Điều 78 chỉ sửa BLTTDS 92/2015. Seed không được
    mang cạnh đó; cạnh thật bên cạnh nó vẫn phải còn."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "161263.json").write_text(_doc_mot_dieu("19/2023/QH15", references=[
        {"targetDocument": {"id": 139264, "docNum": "45/2019/QH14"}, "referenceType": 10},
        {"targetDocument": {"id": 96115, "docNum": "92/2015/QH13"}, "referenceType": 10},
    ]), encoding="utf-8")
    monkeypatch.setattr(build_seed, "DOC_IDS", {"161263": ("deep", "19/2023/QH15")})
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    out = tmp_path / "seed"
    build_seed.build(tmp_path / "raw", out)
    refs = [json.loads(x) for x in (out / "references.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]
    assert [(r["to_document_id"], r["loai"]) for r in refs] == [("96115", 10)]


def test_checksum_DOI_khi_parser_doi_du_HTML_khong_doi(tmp_path, monkeypatch):
    """Kênh dữ liệu CŨ ÂM THẦM. `ingest` bỏ qua document khi checksum không đổi,
    và checksum chỉ băm HTML nguồn. Nên: sửa parser → rebuild seed → `ingest`
    bỏ qua cả 21 văn bản → Postgres giữ nguyên 19.077 dòng hỏng, mọi phép kiểm
    xanh. Đúng loại lỗi mà vòng sửa này tồn tại để diệt.

    Chữa: checksum băm HTML VÀ chính các dòng provision sinh ra từ nó."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "9003.json").write_text(json.dumps({
        "docNum": "3/2020/NĐ-CP",
        "docType": {"name": "Nghị định"}, "effStatus": {"code": "CHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            '<p class="prov-clause">1. Nội dung khoản một.</p></div>'},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(build_seed, "DOC_IDS", {"9003": ("deep", "3/2020/NĐ-CP")})
    # Nguồn thứ hai tắt: mỗi test ở đây soi RIÊNG vòng lặp MOJ. Không tắt thì
    # build đi tìm data/raw/chinhphu và đỏ vì một lý do không liên quan.
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})

    def _checksum(out: Path) -> str:
        build_seed.build(tmp_path / "raw", out)
        return json.loads((out / "checksums.json").read_text(encoding="utf-8"))["documents"]["9003"]

    truoc = _checksum(tmp_path / "s1")

    # Đổi output parser mà KHÔNG đổi một byte HTML nào và không mất chữ nào —
    # đúng hình dạng của vòng sửa này: duong_dan và tieu_de đổi, HTML y nguyên.
    monkeypatch.setitem(prov_parser.NHAN, Cap.khoan, "Khoan")
    sau = _checksum(tmp_path / "s2")

    assert truoc != sau, "checksum không đổi khi parser đổi — ingest sẽ giữ dữ liệu cũ"


def test_build_nap_duoc_nguon_chinhphu(tmp_path, monkeypatch):
    """Vòng lặp nguồn thứ hai: HTML phẳng của trang Chính phủ → seed, qua ĐÚNG
    cổng `_soat_va_bam` như nguồn MOJ.

    Khoá ba thứ mà nguồn này dễ sai và sai im lặng: id mang tiền tố `cp-` (không
    va vào dải id thuần số của MOJ), `nguon_url` trỏ về trang thật (nghĩa vụ ghi
    nguồn), và khối chữ ký nằm ở `phu_luc` chứ KHÔNG chui vào Điều cuối.
    """
    raw = tmp_path / "raw" / "chinhphu"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    (raw / "777.html").write_text(
        '<html><body><div id="block_detail">'
        "<p>QUỐC HỘI</p>"
        "<p>Điều 1. Phạm vi</p>"
        "<p>1. Nội dung khoản một.</p>"
        "<p>Luật này đã được Quốc hội khóa XIII thông qua ngày 11 tháng 11 năm 2011.</p>"
        "<p>CHỦ TỊCH QUỐC HỘI</p>"
        "</div></body></html>", encoding="utf-8")

    monkeypatch.setattr(build_seed, "DOC_IDS", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CONGBAO", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {"777": {
        "so_ky_hieu": "9/2011/QH13", "ten": "Luật thử", "loai_van_ban": "Luật",
        "co_quan_ban_hanh": "Quốc hội", "ngay_ban_hanh": "2011-11-11",
        "ngay_hieu_luc": "2012-07-01", "ngay_het_hieu_luc": None,
        "tinh_trang": "CHL", "depth": "deep"}})

    out = tmp_path / "seed"
    dem = build_seed.build(tmp_path / "raw", out)
    assert dem["documents"] == 1 and dem["references"] == 0

    docs = [json.loads(x) for x in (out / "documents.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert docs[0]["id"] == "cp-777"
    assert "vanban.chinhphu.vn" in docs[0]["nguon_url"]

    provs = [json.loads(x) for x in (out / "provisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    theo_cap = {p["cap"]: p["noi_dung"] for p in provs}
    assert "CHỦ TỊCH QUỐC HỘI" in theo_cap["phu_luc"]
    dieu = next(p for p in provs if p["cap"] == "dieu")
    assert "CHỦ TỊCH QUỐC HỘI" not in dieu["noi_dung"], \
        "khối chữ ký chui vào Điều — neo trích dẫn giả"



def test_build_nap_duoc_nguon_cong_bao_docx(tmp_path, monkeypatch):
    """Nguồn thứ ba (quyết định 2026-09-28 mục 13): `.docx` Công báo → seed qua ĐÚNG cổng
    `_soat_va_bam`; id tiền tố `cb-`, `nguon_url` là trang Công báo, khối chữ ký ở `phu_luc`."""
    import io
    import zipfile

    raw = tmp_path / "raw" / "congbao"
    raw.mkdir(parents=True)
    _metadata_rong(tmp_path / "raw")
    doan = [
        "Điều 1. Phạm vi",
        "1. Nội dung khoản một.",
        "Luật này được Quốc hội khóa XV thông qua ngày 11 tháng 12 năm 2025.",
        "CHỦ TỊCH QUỐC HỘI",
    ]
    than = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in doan)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            f'wordprocessingml/2006/main"><w:body>{than}</w:body></w:document>',
        )
    (raw / "888.docx").write_bytes(buf.getvalue())
    url = "https://congbao.chinhphu.vn/van-ban/luat-so-9-2025-qh15-888.htm"
    monkeypatch.setattr(build_seed, "DOC_IDS", {})
    monkeypatch.setattr(build_seed, "VAN_BAN_CHINHPHU", {})
    monkeypatch.setattr(
        build_seed,
        "VAN_BAN_CONGBAO",
        {
            "888": {
                "url": url,
                "so_ky_hieu": "9/2025/QH15",
                "ten": "Luật thử",
                "loai_van_ban": "Luật",
                "co_quan_ban_hanh": "Quốc hội",
                "ngay_ban_hanh": "2025-12-11",
                "ngay_hieu_luc": "2026-07-01",
                "ngay_het_hieu_luc": None,
                "tinh_trang": "chua_xac_dinh",
                "depth": "deep",
            }
        },
    )

    out = tmp_path / "seed"
    assert build_seed.build(tmp_path / "raw", out)["documents"] == 1
    doc = json.loads((out / "documents.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert (doc["id"], doc["nguon_url"]) == ("cb-888", url)
    provs = [json.loads(x) for x in (out / "provisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert next(p for p in provs if p["cap"] == "khoan")["noi_dung"] == "1. Nội dung khoản một."
    assert "CHỦ TỊCH QUỐC HỘI" in next(p for p in provs if p["cap"] == "phu_luc")["noi_dung"]
