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
SO_HIEU_BAT_BUOC = {"dieu", "chuong", "muc", "tieu_muc", "phan"}

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


def test_seed_co_du_van_ban_cua_DOC_IDS_va_khong_rong(documents, provisions):
    """Số văn bản lấy từ BẢNG KHAI BÁO của từng nguồn chứ KHÔNG viết cứng. Viết
    cứng thì mỗi lần mở rộng corpus test này đỏ vì một lý do không liên quan tới
    điều nó khoá — và cách sửa dễ dãi là bump con số, tức test không còn kiểm gì
    cả.

    Hai nguồn từ 2026-09-02: `DOC_IDS` (API MOJ) và `VAN_BAN`
    (vanban.chinhphu.vn, chỉ cho văn bản mà bản MOJ hỏng). CỘNG hai tập chứ
    không nới thành `>=`: bất biến ở đây là "seed chứa ĐÚNG những văn bản đã
    khai báo, không thừa không thiếu", và `>=` sẽ bỏ lọt một văn bản rơi rụng.
    """
    from scripts.fetch_chinhphu import VAN_BAN
    from scripts.fetch_moj import DOC_IDS

    mong_doi = set(DOC_IDS) | {f"cp-{k}" for k in VAN_BAN}
    assert len(documents) == len(mong_doi), len(documents)
    assert {d["id"] for d in documents} == mong_doi
    assert len(provisions) > 19_000, len(provisions)
    assert {p["document_id"] for p in provisions} == {d["id"] for d in documents}


def test_11_van_ban_T1_dung_bo_ba_va_doc_id_toan_so(documents):
    """T1 (8 lĩnh vực, `.superpowers/sdd/tro-ly-8-linh-vuc/task-1-brief.md`) —
    canh KHÔNG qua `metadata.parquet` (gitignored, đỏ trên CI/clone mới — Bẫy
    2 của brief), chỉ qua seed đã commit và `DOC_IDS`/`TIEU_DE_DOI_CHIEU`
    (nguồn khai báo, đã verify tay).

    11/13: `169032` (Luật Nhà ở, giới hạn parser với tiêu đề Chương xuống dòng
    thành hai node) và `175027` (Luật Bảo hiểm xã hội, lỗi chính tả nguồn
    "Điêu 38") bị cổng cấu trúc `parse_anomalies` chặn khi build seed — KHÔNG
    phải id sai — nên bị loại khỏi `DOC_IDS`/`TIEU_DE_DOI_CHIEU`. Xem
    `KHONG_NAP` ở `scripts/fetch_moj.py`. Domain "Nhà ở" và "Bảo hiểm xã hội"
    tạm 0 văn bản mới.

    Bộ ba (doc_id, so_ky_hieu, loai_van_ban): doc_id+so_ky_hieu đối chiếu
    `DOC_IDS`; `loai_van_ban == "Luật"` là lưới an toàn cấu trúc THỨ HAI cho
    đúng bẫy id-trùng-số-hiệu mà `TIEU_DE_DOI_CHIEU` đã chặn ở tầng fetch (nạp
    nhầm một Nghị quyết dưới tên một Luật thì `loai_van_ban` sẽ không phải
    "Luật" nữa). Cộng khẳng định mọi doc_id là chuỗi số.
    """
    from scripts.fetch_moj import DOC_IDS, TIEU_DE_DOI_CHIEU

    by_id = {d["id"]: d for d in documents}
    assert len(TIEU_DE_DOI_CHIEU) == 11
    for doc_id, manh in TIEU_DE_DOI_CHIEU.items():
        assert doc_id.isdigit(), f"doc_id {doc_id} không phải chuỗi số"
        assert doc_id in DOC_IDS, f"{doc_id} thiếu trong DOC_IDS"
        d = by_id[doc_id]
        assert d["so_ky_hieu"] == DOC_IDS[doc_id][1], doc_id
        assert d["loai_van_ban"] == "Luật", (doc_id, d["loai_van_ban"])
        assert manh in d["ten"], f"{doc_id}: ten={d['ten']!r} thiếu mảnh {manh!r}"


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


def test_moi_van_ban_co_nhieu_nhat_MOT_ban_ghi_phu_luc(provisions, documents):
    """Một bản ghi mỗi văn bản nên `duong_dan` tự duy nhất — không đánh số thứ
    tự, đó là bịa ký hiệu không có trong nguồn."""
    dem = Counter(p["document_id"] for p in provisions if p["cap"] == "phu_luc")
    assert not [d for d, c in dem.items() if c > 1], dem
    pl = [p for p in provisions if p["cap"] == "phu_luc"]
    # 17 → 18 sau khi vá H2: Bộ luật Hình sự (96122) có ĐÚNG MỘT
    # `<p class="prov-content">` rỗng đứng SAU khối "Bộ luật này đã được Quốc hội
    # … thông qua" (132 ký tự). Thẻ rỗng đó đẩy mốc `cuoi` vượt qua khối đuôi nên
    # `duoi` thành rỗng và 132 ký tự đó sập lại vào provision đang mở. H2 KHÔNG
    # tiềm ẩn — nó đang hỏng thật trên corpus, chỉ nhỏ nên không cổng nào thấy.
    #
    # 18 → 21 khi <table> vào `noi_dung`: ba văn bản (90/2019/NĐ-CP, 12/2022/NĐ-CP,
    # 337/2025/NĐ-CP) không có CHỮ nào sau thẻ prov-* cuối nhưng CÓ một bảng chữ
    # ký ở đó. Bảng đó là chữ đuôi đúng nghĩa và phải nằm ở cấp KHÔNG trích dẫn
    # được: để nó rơi vào Điều cuối thì một câu trích lấy từ khối chữ ký sẽ
    # "kiểm chứng thành công" trên một neo Điều — đúng véc-tơ mà ruling chữ-đuôi
    # đã đóng cho text và giờ đóng nốt cho bảng.
    # Số lấy từ `documents` chứ không viết cứng: bất biến là "MỖI văn bản đúng
    # một bản ghi phu_luc", không phải "có 21 bản ghi".
    assert len(pl) == len(documents), \
        f"{len(documents)} văn bản có chữ/bảng đuôi, thấy {len(pl)}"
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


# ══ Ruling C1: chữ ĐẦU tách ra bản ghi `mo_dau`, đối xứng với chữ ĐUÔI ══

# Tiêu ngữ chỉ có ở khối mở đầu văn bản. KHÔNG dùng "Căn cứ" làm dấu hiệu: nó
# xuất hiện hợp lệ trong 83 điều luật thật ("Căn cứ vào …"), nên nó không phân
# biệt được lời mở đầu với nội dung quy phạm.
#
# Cùng lý do đó, "Độc lập" một mình cũng KHÔNG dùng được — nó là một từ tiếng
# Việt bình thường: `19/2023/QH15 > Điều 50 > Khoản 1 > Điểm e` mở đầu bằng
# "Độc lập khảo sát, thử nghiệm…" và bị báo oan. Dấu hiệu phải là NGUYÊN cụm
# tiêu ngữ "Độc lập - Tự do - Hạnh phúc", thứ không xuất hiện trong điều luật.
TIEU_NGU = ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc")


def test_noi_dung_cap_trich_dan_duoc_MO_DAU_bang_nhan_cua_chinh_no(provisions):
    """Bất biến QUY THUỘC — thứ mà cả ba cổng đều mù trước vòng này. Bảo toàn ký
    tự bảo rằng chữ KHÔNG MẤT; độ phủ dùng `set()` nên chữ chỉ cần "có mặt". Cả
    hai không thể thấy chữ nằm SAI provision.

    `noi_dung` của một provision cấp trích dẫn được chỉ chứa chữ nằm giữa nhãn
    của nó và nhãn kế tiếp, nên nó phải mở đầu bằng nhãn của chính nó. Đo trên
    seed trước khi sửa: 8 Điều (lời mở đầu văn bản, C1) + 3 Khoản + 1 Điểm (mảnh
    tiếp nối bị tách, H3) vi phạm."""
    import re
    import unicodedata

    def khoa(x: str) -> str:
        return unicodedata.normalize("NFC", re.sub(r"\s+", " ", x)).strip().replace("Ð", "Đ")

    lech = []
    for p in provisions:
        if p["cap"] not in CITABLE:
            continue
        nd, so = khoa(p["noi_dung"]), (p["so_hieu_cap"] or "")
        if p["cap"] == "dieu":
            ok = nd.lower().startswith("điều")
        else:
            ok = bool(so) and nd.lower().startswith(so.lower())
        if not ok:
            lech.append((p["document_id"], p["duong_dan"], nd[:60]))
    assert not lech, f"{len(lech)} neo trích dẫn mở đầu bằng chữ KHÔNG thuộc nó: {lech[:5]}"


def test_moi_van_ban_co_dung_MOT_ban_ghi_mo_dau(provisions, documents):
    """Đã đo: cả 21 văn bản đều có chữ trước thẻ `prov-*` đầu tiên (tiêu ngữ, số
    hiệu, tên văn bản, chuỗi "Căn cứ …"). Một bản ghi mỗi văn bản nên `duong_dan`
    tự duy nhất — không đánh số thứ tự, đó là bịa ký hiệu không có trong nguồn."""
    md = [p for p in provisions if p["cap"] == "mo_dau"]
    assert len(md) == len(documents), \
        f"{len(documents)} văn bản đều có chữ mở đầu, thấy {len(md)}"
    assert {p["document_id"] for p in md} == {d["id"] for d in documents}
    assert len({p["duong_dan"] for p in md}) == len(md)
    for p in md:
        assert p["parent_local_id"] is None, p["duong_dan"]
        assert p["so_hieu_cap"] == "", p["duong_dan"]
        assert p["duong_dan"].endswith(" > Mở đầu"), p["duong_dan"]
        assert p["noi_dung"].strip(), p["duong_dan"]


def test_mo_dau_co_thu_tu_NHO_NHAT_trong_moi_van_ban(provisions):
    """`local_id` ở cuối, `thu_tu` ở đầu: chữ mở đầu nằm đầu văn bản nên nó phải
    xếp trước mọi provision khác. Trước khi sửa: `126319` có `mo_dau` thu_tu=35,
    `phu_luc` thu_tu=36, `dieu` chạy 0–32 — lời mở đầu xếp SAU Phụ lục."""
    nho_nhat: dict[str, int] = {}
    for p in provisions:
        d = p["document_id"]
        if p["cap"] != "mo_dau":
            nho_nhat[d] = min(nho_nhat.get(d, p["thu_tu"]), p["thu_tu"])
    xau = [(p["document_id"], p["thu_tu"], nho_nhat[p["document_id"]]) for p in provisions
           if p["cap"] == "mo_dau" and p["thu_tu"] >= nho_nhat[p["document_id"]]]
    assert not xau, f"mo_dau không xếp đầu: {xau[:5]}"


def test_tieu_ngu_van_ban_KHONG_con_trong_bat_ky_neo_trich_dan_nao(provisions):
    """Kịch bản hỏng của C1: agent sinh câu lấy từ TÊN VĂN BẢN, tầng 1 tìm thấy
    nguyên văn trong `noi_dung` của Điều 1 → "đã kiểm chứng". Trước khi sửa: 4
    Điều 1 chứa nguyên khối tiêu ngữ."""
    xau = [(p["document_id"], p["duong_dan"]) for p in provisions
           if p["cap"] in CITABLE and any(t in p["noi_dung"] for t in TIEU_NGU)]
    assert not xau, f"{len(xau)} neo trích dẫn còn chứa tiêu ngữ văn bản: {xau[:5]}"

    # ĐỐI CHỨNG: siết dấu hiệu ở trên chỉ hợp lệ nếu dấu hiệu MỚI vẫn tìm thấy
    # tiêu ngữ ở nơi nó thật sự nằm. Không có dòng này, một cụm gõ sai sẽ biến
    # phép kiểm thành luôn-xanh mà không ai thấy.
    co = {p["document_id"] for p in provisions
          if p["cap"] == "mo_dau" and any(t in p["noi_dung"] for t in TIEU_NGU)}
    assert len(co) > len({p["document_id"] for p in provisions}) // 2, \
        f"dấu hiệu tiêu ngữ chỉ khớp {len(co)} văn bản — nhiều khả năng nó đã gõ sai"


def test_khoan_va_diem_LUON_co_so_hieu_cap(provisions):
    """H3. `"… > Điều 33 > Khoản"` không phải một dẫn chiếu pháp luật Việt Nam:
    nếu hệ thống hiển thị nó làm citation thì người dùng nhận một trích dẫn không
    thể tra. Trước khi sửa: 3 Khoản + 1 Điểm rỗng."""
    rong = [(p["document_id"], p["duong_dan"]) for p in provisions
            if p["cap"] in {"khoan", "diem"} and not (p["so_hieu_cap"] or "").strip()]
    assert not rong, f"{len(rong)} Khoản/Điểm thiếu so_hieu_cap: {rong}"


def test_checksums_json_khop_documents_jsonl(documents):
    """H4. `checksums.json` không được đọc bởi bất kỳ dòng Python nào trong repo —
    nó là artefact chỉ-ghi. Test này ít nhất bắt được trôi giữa hai file, thứ sẽ
    làm `ingest` bỏ qua văn bản đã đổi."""
    cs = json.loads((SEED / "checksums.json").read_text(encoding="utf-8"))
    assert cs["documents"] == {d["id"]: d["checksum"] for d in documents}


# ══ Bảng nằm TRONG noi_dung, không ở cột riêng ══════════════════════════════

def test_bang_luong_toi_thieu_vung_MOI_VUNG_MOT_NEO(provisions):
    """Ca hỏng đắt nhất của corpus, đã đi qua HAI vòng sửa.

    Vòng 1 (`c5c2c17`): `parse_tables` không có caller nào trong đường sản xuất
    nên mọi <table> bị `decompose()` và biến mất — người lao động hỏi "lương tối
    thiểu vùng I bao nhiêu" nhận một trích dẫn tới điều luật KHÔNG CHỨA CON SỐ
    NÀO. Bảng được đưa vào `noi_dung` vì đó là trường DUY NHẤT verifier tầng 1
    đối chiếu câu trích vào.

    Vòng 2 (`migrations/017`): cả bảng trong MỘT `noi_dung` nghĩa là bốn vùng
    dùng chung MỘT neo, nên mô hình trích hai hàng rồi kết luận "pháp luật quy
    định HAI mức lương tối thiểu" và bảy phép kiểm vẫn xanh — hai citation trỏ
    cùng một `khop_tai_id` nên phép so tập con không có gì để so (trace
    cbd9f317). Nay MỖI VÙNG MỘT NEO.

    Bất biến của vòng 1 không mất: con số vẫn ở trong `noi_dung`, chỉ là
    `noi_dung` của đúng hàng nó thuộc về.
    """
    theo_path = {p["duong_dan"]: p for p in provisions}
    mong_doi = {
        "293/2025/NĐ-CP > Điều 3 > Khoản 1": {
            "Vùng I": "5.310.000", "Vùng II": "4.730.000",
            "Vùng III": "4.140.000", "Vùng IV": "3.700.000"},
        "74/2024/NĐ-CP > Điều 3 > Khoản 1": {
            "Vùng I": "4.960.000", "Vùng II": "4.410.000",
            "Vùng III": "3.860.000", "Vùng IV": "3.450.000"},
    }
    for path, muc in mong_doi.items():
        # Hàng TIÊU ĐỀ ở lại Khoản cha — bỏ nó thì tên cột biến mất.
        assert "| Vùng |" in theo_path[path]["noi_dung"], path
        for vung, so in muc.items():
            neo = f"{path} > {vung}"
            assert neo in theo_path, f"thiếu neo {neo}"
            hang = theo_path[neo]
            assert hang["cap"] == "hang_bang", neo
            assert so in hang["noi_dung"], f"{neo} thiếu mức lương {so}"
            # Và KHÔNG còn ở cha: còn thì một quote hàng khớp ở cả hai dòng,
            # `_tim_quote` trả về cha, và hai vùng lại chung một neo.
            assert so not in theo_path[path]["noi_dung"], f"{so} vẫn nằm ở {path}"


def test_neo_trich_dan_hua_danh_sach_thi_phai_giao(provisions):
    """Cùng phép kiểm mà `migrations/013` canh ở tầng DB, chạy ở tầng seed.

    Ba ngoại lệ là KHIẾM KHUYẾT CỦA NGUỒN MOJ, đã mở HTML đọc tay: hai Khoản của
    BLHS gõ ':' đáng lẽ là '.', còn 145/2020 Điều 56 Khoản 2 hứa công thức lương
    làm đêm mà HTML nguồn có ĐÚNG 0 bảng trong phạm vi Điều 56.
    """
    loi_nguon = {
        "100/2015/QH13 > Điều 200 > Khoản 3",
        "100/2015/QH13 > Điều 236 > Khoản 3",
        "145/2020/NĐ-CP > Điều 56 > Khoản 2",
    }
    co_con = {(p["document_id"], p["parent_local_id"]) for p in provisions}
    tro_troi = [p["duong_dan"] for p in provisions
                if p["cap"] in CITABLE
                and p["noi_dung"].rstrip().endswith(":")
                and (p["document_id"], p["local_id"]) not in co_con
                and p["duong_dan"] not in loi_nguon]
    assert not tro_troi, f"{len(tro_troi)} neo hứa danh sách mà không giao: {tro_troi[:5]}"
