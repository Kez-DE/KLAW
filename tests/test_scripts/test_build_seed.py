import json
from pathlib import Path

import pytest

from scripts import build_seed
from scripts.fetch_moj import DOC_IDS
from src.models.domain import Cap
from src.services import prov_parser


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
    (raw / "9001.json").write_text(json.dumps({
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
    out = tmp_path / "seed"
    assert build_seed.build(tmp_path / "raw", out) == {
        "documents": 1, "provisions": 2, "references": 1}

    provs = [json.loads(x) for x in (out / "provisions.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert all(p["document_id"] == "9001" for p in provs)
    assert all(p["noi_dung"].strip() for p in provs), "seed ghi noi_dung rỗng"
    assert json.loads((out / "checksums.json").read_text(encoding="utf-8")).keys() == {"9001"}


def test_build_FAIL_khi_parse_anomalies_bao_bat_thuong(tmp_path, monkeypatch):
    """Mục H: parse_anomalies đã tồn tại, đã có test, CHƯA AI CHẠY trên dữ liệu
    thật — build_seed không gọi nó. Đó là lý do cả bốn lỗi kia lọt được."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    (raw / "9002.json").write_text(json.dumps({
        "docType": {"name": "Nghị định"}, "effStatus": {"code": "CHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            # neo trích dẫn nằm trong <table> → ra khỏi cây → lỗi CHẶN
            '<table><tr><td><p class="prov-clause">1. Vùng I.</p></td></tr></table>'
            "</div>"},
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(build_seed, "DOC_IDS", {"9002": ("deep", "2/2020/NĐ-CP")})
    with pytest.raises(ValueError, match="bất thường cấu trúc"):
        build_seed.build(tmp_path / "raw", tmp_path / "seed")


def test_checksum_DOI_khi_parser_doi_du_HTML_khong_doi(tmp_path, monkeypatch):
    """Kênh dữ liệu CŨ ÂM THẦM. `ingest` bỏ qua document khi checksum không đổi,
    và checksum chỉ băm HTML nguồn. Nên: sửa parser → rebuild seed → `ingest`
    bỏ qua cả 21 văn bản → Postgres giữ nguyên 19.077 dòng hỏng, mọi phép kiểm
    xanh. Đúng loại lỗi mà vòng sửa này tồn tại để diệt.

    Chữa: checksum băm HTML VÀ chính các dòng provision sinh ra từ nó."""
    raw = tmp_path / "raw" / "moj"
    raw.mkdir(parents=True)
    (raw / "9003.json").write_text(json.dumps({
        "docType": {"name": "Nghị định"}, "effStatus": {"code": "CHL"},
        "documentContent": {"content":
            '<div class="WordSection1">'
            '<p id="a1" class="prov-article"><b>Điều 1. Phạm vi</b></p>'
            '<p class="prov-clause">1. Nội dung khoản một.</p></div>'},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(build_seed, "DOC_IDS", {"9003": ("deep", "3/2020/NĐ-CP")})

    def _checksum(out: Path) -> str:
        build_seed.build(tmp_path / "raw", out)
        return json.loads((out / "checksums.json").read_text(encoding="utf-8"))["9003"]

    truoc = _checksum(tmp_path / "s1")

    # Đổi output parser mà KHÔNG đổi một byte HTML nào và không mất chữ nào —
    # đúng hình dạng của vòng sửa này: duong_dan và tieu_de đổi, HTML y nguyên.
    monkeypatch.setitem(prov_parser.NHAN, Cap.khoan, "Khoan")
    sau = _checksum(tmp_path / "s2")

    assert truoc != sau, "checksum không đổi khi parser đổi — ingest sẽ giữ dữ liệu cũ"
