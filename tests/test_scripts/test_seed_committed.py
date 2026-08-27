"""Bất biến trên `data/seed/*.jsonl` — file NẰM TRONG GIT.

Mục H của brief: `parse_anomalies()` đã tồn tại, đã có test, chưa ai chạy trên
dữ liệu thật; và test duy nhất chạm dữ liệu thật bị chặn HAI lần (`@integration`
VÀ skip khi thiếu `data/raw`, mà `data/raw` thì gitignored). Kết quả: clone mới
→ test xanh, 0 assertion về 19.100 dòng seed.

File này khác: nó đọc `data/seed/`, đã commit, nên nó chạy trên clone sạch —
KHÔNG cần Docker, KHÔNG cần API key, KHÔNG `@integration`. Nếu ai sửa parser làm
hỏng seed rồi commit, CI đỏ chứ không phải dữ liệu hỏng âm thầm.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parents[2] / "data" / "seed"
CITABLE = {"dieu", "khoan", "diem"}
SO_HIEU_BAT_BUOC = {"dieu", "chuong", "muc", "tieu_muc"}

# Đã kiểm tay trên dữ liệu thật: cả 6 Bộ luật liên tục hoàn hảo, thiếu 0, trùng 0.
SO_DIEU_BO_LUAT = {
    "91/2015/QH13": 689,   # Bộ luật Dân sự
    "92/2015/QH13": 517,   # Bộ luật Tố tụng dân sự
    "101/2015/QH13": 510,  # Bộ luật Tố tụng hình sự
    "100/2015/QH13": 426,  # Bộ luật Hình sự
    "95/2015/QH13": 341,   # Bộ luật Hàng hải
    "45/2019/QH14": 220,   # Bộ luật Lao động
}


def _doc(name: str) -> list[dict]:
    p = SEED / f"{name}.jsonl"
    assert p.exists(), f"{p} phải nằm trong git — chạy `python -m scripts.build_seed`"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture(scope="module")
def provisions() -> list[dict]:
    return _doc("provisions")


@pytest.fixture(scope="module")
def documents() -> list[dict]:
    return _doc("documents")


def test_seed_co_du_21_van_ban_va_khong_rong(documents, provisions):
    assert len(documents) == 21, len(documents)
    assert len(provisions) > 19_000, len(provisions)
    assert {p["document_id"] for p in provisions} == {d["id"] for d in documents}


def test_noi_dung_KHONG_RONG_o_moi_cap_trich_dan_duoc(provisions):
    """Trước vòng này: rỗng ở 17.813/19.077 (93,4%). Đây là trường verifier tầng
    1 đối chiếu câu trích vào — rỗng nghĩa là phép kiểm không kiểm gì cả."""
    rong = [(p["document_id"], p["duong_dan"]) for p in provisions
            if p["cap"] in CITABLE and not (p["noi_dung"] or "").strip()]
    assert not rong, f"{len(rong)} provision cấp trích dẫn được có noi_dung rỗng: {rong[:5]}"


def test_duong_dan_DUY_NHAT_o_cap_trich_dan_duoc(provisions):
    """Hai provision cùng neo ⇒ một claim sai được 'kiểm chứng thành công' trên
    văn bản của provision kia. Cấp container được phép trùng (NĐ 145/2020 thật
    sự đánh số hai 'Chương XI'), cấp trích dẫn được thì không."""
    dem = Counter(p["duong_dan"] for p in provisions if p["cap"] in CITABLE)
    trung = {k: v for k, v in dem.items() if v > 1}
    assert not trung, f"neo trích dẫn trùng: {trung}"


def test_so_hieu_cap_KHONG_RONG_o_dieu_chuong_muc_tieu_muc(provisions):
    """Chương VIII của Bộ luật Hình sự từng ra duong_dan '… > Chương' vì thẻ nhãn
    trơ '<strong>Chương </strong>' tạo node số rỗng."""
    rong = [(p["document_id"], p["cap"], p["duong_dan"]) for p in provisions
            if p["cap"] in SO_HIEU_BAT_BUOC and not (p["so_hieu_cap"] or "").strip()]
    assert not rong, f"{len(rong)} node thiếu so_hieu_cap: {rong[:5]}"


def test_chuong_VIII_bo_luat_hinh_su_co_so_hieu(provisions):
    """Ca cụ thể mà Cổng A bắt được: BLHS đi Chương VII → (thiếu VIII) → IX."""
    chuong = [p["so_hieu_cap"] for p in provisions
              if p["document_id"] == "96122" and p["cap"] == "chuong"]
    assert "VIII" in chuong, chuong


def test_tieu_muc_co_mat_trong_seed(provisions):
    """prov-subsection tồn tại 43 lần trong HTML; thiếu cấp này thì 23 Tiểu mục
    Bộ luật Dân sự mất trắng."""
    tm = [p for p in provisions if p["cap"] == "tieu_muc"]
    assert len(tm) == 23, len(tm)
    assert all(p["document_id"] == "95942" for p in tm)


def test_day_so_DIEU_cua_6_bo_luat_lien_tuc_khong_thieu_khong_trung(documents, provisions):
    """Phép kiểm CẤU TRÚC mà token coverage về bản chất không thấy: coverage dùng
    `set()` nên một Điều bị gộp vào Điều bên cạnh vẫn để lại đủ token.

    Liên tục = `max - min + 1 - count(distinct) == 0` VÀ count khớp số Điều thật.
    """
    skh = {d["id"]: d["so_ky_hieu"] for d in documents}
    theo_doc: dict[str, list[int]] = defaultdict(list)
    for p in provisions:
        if p["cap"] != "dieu":
            continue
        s = skh[p["document_id"]]
        if s in SO_DIEU_BO_LUAT:
            theo_doc[s].append(int("".join(c for c in p["so_hieu_cap"] if c.isdigit())))

    for s, mong_doi in SO_DIEU_BO_LUAT.items():
        nums = theo_doc[s]
        rieng = set(nums)
        assert len(nums) == mong_doi, f"{s}: {len(nums)} Điều, phải {mong_doi}"
        assert len(rieng) == mong_doi, \
            f"{s}: trùng số Điều {sorted(k for k, v in Counter(nums).items() if v > 1)}"
        thieu = sorted(set(range(min(rieng), max(rieng) + 1)) - rieng)
        assert not thieu, f"{s}: dãy Điều bị đứt, thiếu {thieu}"


def test_cay_provision_khong_co_parent_treo(provisions):
    """`parent_local_id` phải trỏ vào một local_id CÓ THẬT trong cùng document và
    phải đứng TRƯỚC nó — nếu không, guard thứ tự của scripts.ingest sẽ nổ."""
    theo_doc: dict[str, set[int]] = defaultdict(set)
    for p in provisions:
        theo_doc[p["document_id"]].add(p["local_id"])
    treo = [(p["document_id"], p["local_id"], p["parent_local_id"]) for p in provisions
            if p["parent_local_id"] is not None
            and (p["parent_local_id"] not in theo_doc[p["document_id"]]
                 or p["parent_local_id"] >= p["local_id"])]
    assert not treo, f"parent treo hoặc đứng sau con: {treo[:5]}"


def test_moi_container_co_it_nhat_mot_con(provisions):
    """Container không con = cây bị vỡ ở đúng chỗ token coverage không thấy."""
    co_con: dict[str, set[int]] = defaultdict(set)
    for p in provisions:
        if p["parent_local_id"] is not None:
            co_con[p["document_id"]].add(p["parent_local_id"])
    ro = [(p["document_id"], p["duong_dan"]) for p in provisions
          if p["cap"] in {"phan", "chuong", "muc", "tieu_muc"}
          and p["local_id"] not in co_con[p["document_id"]]]
    assert not ro, f"{len(ro)} container không có con: {ro[:5]}"


def test_text_trong_seed_da_NFC(provisions):
    """Corpus không thuần NFC (96117 có 'ư'+U+0323). NFD một phía làm độ phủ sụp
    về 0,28–0,37 và làm truy vấn của người dùng âm thầm không khớp."""
    import unicodedata
    lech = [p["duong_dan"] for p in provisions
            if unicodedata.normalize("NFC", p["noi_dung"]) != p["noi_dung"]
            or unicodedata.normalize("NFC", p["tieu_de"]) != p["tieu_de"]]
    assert not lech, f"{len(lech)} provision còn ở dạng NFD: {lech[:5]}"


# ══ Ruling: chữ đuôi tách ra bản ghi `phu_luc`, không làm loãng neo trích dẫn ══

def test_dieu_115_cua_ND_145_khong_con_chua_chu_duoi(provisions):
    """Trước ruling: `145/2020/NĐ-CP > Điều 115` dài 44.106 ký tự vì toàn bộ Phụ
    lục gắn vào nó, nên một câu trích lấy từ Phụ lục sẽ 'kiểm chứng thành công'
    trên neo Điều 115. Phép kiểm không cần ngưỡng bịa: Điều 115 phải ngắn lại
    theo cỡ độ lớn, và chữ đó phải xuất hiện lại trong bản ghi `phu_luc`."""
    theo_path = {p["duong_dan"]: p for p in provisions}
    d115 = theo_path["145/2020/NĐ-CP > Điều 115"]
    pl = theo_path["145/2020/NĐ-CP > Phụ lục"]
    assert len(d115["noi_dung"]) < 2_000, len(d115["noi_dung"])
    assert len(pl["noi_dung"]) > 40_000, len(pl["noi_dung"])
    assert pl["cap"] == "phu_luc" and pl["cap"] not in CITABLE
    # chữ không mất: đuôi chuyển chỗ, không bốc hơi
    assert len(d115["noi_dung"]) + len(pl["noi_dung"]) >= 44_000


def test_khong_provision_trich_dan_duoc_nao_om_ca_khoi_phu_luc(provisions):
    """Ba neo từng phình vì chữ đuôi: 145/2020 Điều 115 (44.106),
    09/2020 Điều 13 Khoản 2 Điểm b (25.912), 29/2019 Điều 29 (22.155)."""
    to = [(p["duong_dan"], len(p["noi_dung"])) for p in provisions
          if p["cap"] in CITABLE and len(p["noi_dung"]) > 20_000]
    assert not to, f"neo trích dẫn còn ôm khối chữ đuôi: {to}"


def test_moi_van_ban_co_nhieu_nhat_MOT_ban_ghi_phu_luc(provisions):
    """Một bản ghi mỗi văn bản nên `duong_dan` tự duy nhất — không đánh số thứ
    tự, đó là bịa ký hiệu không có trong nguồn."""
    dem = Counter(p["document_id"] for p in provisions if p["cap"] == "phu_luc")
    assert not [d for d, c in dem.items() if c > 1], dem
    pl = [p for p in provisions if p["cap"] == "phu_luc"]
    assert len(pl) == 17, f"17 văn bản có chữ đuôi, thấy {len(pl)}"
    assert len({p["duong_dan"] for p in pl}) == len(pl)
    for p in pl:
        assert p["parent_local_id"] is None, p["duong_dan"]
        assert p["so_hieu_cap"] == "", p["duong_dan"]
        assert p["duong_dan"].endswith(" > Phụ lục"), p["duong_dan"]


def test_phu_luc_khong_bao_gio_la_cha_cua_provision_nao(provisions):
    pl = {(p["document_id"], p["local_id"]) for p in provisions if p["cap"] == "phu_luc"}
    con = [p["duong_dan"] for p in provisions
           if (p["document_id"], p["parent_local_id"]) in pl]
    assert not con, f"phu_luc có con — nó là cấp tài liệu, không phải cấp cây: {con}"
