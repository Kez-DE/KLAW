"""Nạp cạnh quan hệ hiệu lực ĐI VÀO các văn bản trong corpus.

API `/doc/{id}` (và endpoint `related`) chỉ trả cạnh ĐI RA — đã ĐO ở Plan 1
rằng `related` không lọc theo quan hệ thật (gọi `/doc/96122/related` trả về
văn bản "mới nhất toàn hệ thống", không liên quan BLHS). Cơ chế hiệu lực Mức 2
(Task 2) cần cạnh ĐI VÀO ("ai đã thay thế văn bản này?") → phải quét đồ thị
`data/raw/relationships.parquet` (1.033.255 cạnh, crawl vài giây), không tra
từng văn bản qua API.

CẢNH BÁO NGUỒN: `relationships.parquet` và `metadata.parquet` không tải từ API
MOJ — chúng đến từ dataset HuggingFace `th1nhng0/vietnamese-legal-documents`,
một crawl bên thứ ba VINTAGE KHÔNG RÕ (xác định ở Plan 1). Cạnh hiệu lực nạp từ
đây KHÔNG được tin thẳng là đúng-hiện-tại — Task 2 áp guard hợp lý trước khi
dùng để quyết định hiệu lực.

Chỉ 4 quan hệ mang TÍN HIỆU HIỆU LỰC được nạp (`QUAN_HE_HIEU_LUC`); 1.053/1.233
cạnh đi vào corpus là "Căn cứ" (căn cứ pháp lý, không phải hiệu lực) và các
quan hệ dẫn chiếu/hướng dẫn khác — CỐ Ý không nạp.

FK `references_from_document_fk` bắt `from_document_id` có trong `documents`,
mà cạnh đi vào xuất phát từ văn bản NGOÀI corpus theo định nghĩa. Trước khi nạp
cạnh, hàm chèn các văn bản ngoài corpus đó dưới dạng CHỈ-METADATA
(`depth='metadata'`, `tinh_trang='chua_xac_dinh'`, `checksum='metadata-only'`)
— đủ để thoả FK và để trích dẫn được văn bản sửa đổi bằng so_ky_hieu, không
đụng tới văn bản THẬT nào của corpus (`ON CONFLICT DO NOTHING`).
"""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from scripts.fetch_moj import DOC_IDS
from src.models.domain import sql_khoa_so_ky_hieu
from src.services.db import run_migrations

# Quan hệ mang TÍN HIỆU HIỆU LỰC (không phải "Căn cứ", "Dẫn chiếu", "Quy định chi
# tiết, hướng dẫn thi hành", "Hướng dẫn áp dụng"...) → mã loai TỰ SUY RA, dải
# 20..23 do migration 007 sở hữu — không đụng 1..15 của MOJ.
QUAN_HE_HIEU_LUC: dict[str, int] = {
    "Sửa đổi, bổ sung": 20,
    "Thay thế": 21,
    "Văn bản quy định hết hiệu lực": 22,
    "Văn bản quy định hết hiệu lực 1 phần": 23,
}

_COT_METADATA = ("id", "so_ky_hieu", "title", "loai_van_ban",
                  "ngay_ban_hanh", "ngay_co_hieu_luc", "ngay_het_hieu_luc")

# Cạnh parquet ĐÃ ĐỐI CHIẾU NGUYÊN VĂN là sai: `(doc_id, other_doc_id,
# relationship)`. Ghi TƯỜNG MINH từng cạnh, cùng lý do `013_bang_trong_noi_dung`
# không nới điều kiện: thêm dòng là hành vi có ý thức, đòi mở nguồn ra đọc.
CANH_SAI: frozenset[tuple[str, str, str]] = frozenset({
    # 19/2023/QH15 (Bảo vệ quyền lợi người tiêu dùng) "sửa" BLLĐ 45/2019/QH14:
    # Điều 78 chỉ sửa BLTTDS 92/2015 "đã được sửa đổi, bổ sung một số điều theo
    # Bộ luật số 45/2019/QH14, ..." — crawl nguồn bắt nhầm số hiệu trong câu.
    # 18/VBHN-VPQH (hợp nhất BLLĐ) không có 19/2023. Đo 2026-09-28.
    ("161263", "139264", "Sửa đổi, bổ sung"),
    # Không văn bản nào dưới đây sửa Luật Thi hành án hình sự 127/2025/QH15 (đọc
    # toàn văn gateway 2026-09-28): 143/2025/QH15 Điều 50 khoản 2 sửa Luật Thuế
    # TNDN 67/2025 "đã được sửa đổi, bổ sung ... theo Luật số ... 127/2025/QH15"
    # — cùng lỗi bắt nhầm số hiệu; 231/2026/NĐ-CP chỉ "Căn cứ" và thi hành 127/2025.
    ("187601", "187035", "Sửa đổi, bổ sung"),
    ("386e5ad0-7d09-11f1-9c00-f9e84f25c1dc", "187035", "Sửa đổi, bổ sung"),
})

# Bản ghi trùng (dòng thừa → dòng giữ): gateway và parquet mang HAI id cho cùng một
# văn bản; `scripts/don_kho.py` gộp chúng trong DB, và ở đây mọi cạnh parquet của
# dòng thừa được trỏ sang dòng giữ để nạp lại không chèn dòng thừa trở lại.
# Bằng chứng (response gateway 2026-09-28), cả bốn id đều Publish, cùng số, cùng ngày:
# - 33/2005/NĐ-CP: 18451 có publicDate 2013-03-02, tệp '33.2005.ND.CP.doc', tiêu
#   đề "Pháp lệnh Thú y"; 40022 không publicDate, tệp 'ND 33 Huong dan PLTY 15.3.05.doc'.
# - 60/2020/QH14: 142846 là văn bản Quốc hội thông qua; 153788 là bản sao y
#   ("SAO Y BẢN CHÍNH … Số: 05/SY-VPCTN") của Văn phòng Chủ tịch nước.
BAN_TRUNG: dict[str, str] = {"40022": "18451", "153788": "142846"}

# Cùng quan hệ sai ấy trong mảng `references` MOJ của 19/2023/QH15 (loai 10,
# `raw_text` '45/2019/QH14'): `(from, to, loai)`. `build_seed` bỏ nó khỏi seed,
# `ingest` xoá nó khỏi DB đã nạp từ seed cũ.
CANH_SAI_MOJ: frozenset[tuple[str, str, int]] = frozenset({
    ("161263", "139264", 10),
})

# Cạnh hiệu lực ĐỌC TỪ NGUYÊN VĂN mà parquet không có (0 cạnh hiệu lực nào chạm
# 154245, đo 2026-09-28): `(from, to, loai, relationship)`, chiều như parquet —
# `from` là văn bản ĐI THAY.
CANH_DOI_CHIEU_NGUYEN_VAN: tuple[tuple[str, str, int, str], ...] = (
    # 38/2022/NĐ-CP Điều 5 khoản 2: "Nghị định số 90/2019/NĐ-CP ... hết hiệu lực
    # kể từ ngày Nghị định này có hiệu lực thi hành" (01/7/2022).
    ("154245", "139094", 21, "Thay thế"),
    # 74/2024/NĐ-CP Điều 5 khoản 2, cùng câu cho 38/2022/NĐ-CP; `applicationNote`
    # của gateway cho 154245: "Bị thay thế bởi Nghị định số 74/2024/NĐ-CP".
    ("168670", "154245", 21, "Thay thế"),
    # 145/2020/NĐ-CP Điều 114 khoản 2 điểm đ: "các Nghị định sau đây hết hiệu
    # lực thi hành: ... Nghị định số 121/2018/NĐ-CP" — cùng khoản mà parquet ghi
    # loai 21 cho 44/2013, 45/2013, 49/2013..., riêng 121/2018 thì thiếu. Không
    # có cạnh này, 121/2018 ra `con_hieu_luc` theo effStatus CHL đã cũ của MOJ.
    ("152668", "131010", 21, "Thay thế"),
    # 38/2019/QH14 Điều 151 khoản 3: "Luật Quản lý thuế số 78/2006/QH11 ... hết
    # hiệu lực kể từ ngày Luật này có hiệu lực thi hành". Parquet không có cạnh
    # hiệu lực nào cho 14832 (chỉ hai cạnh MOJ loai 12, Mức 2a không đọc).
    ("136036", "14832", 21, "Thay thế"),
)

# Văn bản hợp nhất (Công báo) nêu đích danh luật đi sửa từng điều khoản
# (`sua_doi_dieu_khoan`, `scripts/nap_sua_doi_vbhn.py`) ⇒ cạnh "Sửa đổi, bổ
# sung" cấp VĂN BẢN. Nối `sua_boi_so_ky_hieu` sang id bằng số hiệu.
_SQL_VBHN = text(
    "SELECT DISTINCT s.sua_boi_so_ky_hieu AS sk, d.id AS f, p.document_id AS t"
    " FROM sua_doi_dieu_khoan s"
    " JOIN provisions p ON p.id = s.provision_id"
    f" JOIN documents d ON {sql_khoa_so_ky_hieu('d.so_ky_hieu')} = {sql_khoa_so_ky_hieu('s.sua_boi_so_ky_hieu')}"
    " WHERE s.do_tin_cay <> 'can_doi_chieu_tay'"
)


def _canh_tu_vbhn(conn) -> list[tuple[str, str, int, str]]:
    """Cạnh loai 20 suy từ VBHN. Số hiệu KHÔNG duy nhất trong `documents` (Luật
    và Nghị quyết dùng chung số) — trùng thì RAISE, không đoán văn bản nào."""
    theo_sk: dict[tuple[str, str], set[str]] = {}
    for sk, f, t in conn.execute(_SQL_VBHN):
        theo_sk.setdefault((sk, t), set()).add(f)
    mo_ho = {k: v for k, v in theo_sk.items() if len(v) > 1}
    if mo_ho:
        raise ValueError(f"số hiệu đi sửa khớp nhiều văn bản, không chọn được: {mo_ho}")
    return [(f, t, QUAN_HE_HIEU_LUC["Sửa đổi, bổ sung"], "Sửa đổi, bổ sung")
            for (_, t), (f,) in sorted(theo_sk.items()) if f != t]


def _bo_sung(canh: pd.DataFrame, them) -> pd.DataFrame:
    """Nối `them` vào `canh`, bỏ cạnh `(from, to, loai)` đã có — một quan hệ
    hai nguồn cùng nói thì vẫn là MỘT cạnh (`/lien-quan` liệt kê từng dòng)."""
    co = set(zip(canh["from_document_id"], canh["to_document_id"], canh["loai"], strict=True))
    moi = []
    for f, t, loai, ten in them:
        if (f, t, loai) not in co:
            co.add((f, t, loai))
            moi.append({"from_document_id": f, "to_document_id": t, "loai": loai, "raw_text": ten})
    return pd.concat([canh, pd.DataFrame(moi)], ignore_index=True) if moi else canh


def _canh_hieu_luc_di_vao(rel: pd.DataFrame, corpus: set[str]) -> pd.DataFrame:
    """Trích cạnh ĐI VÀO `corpus` mang tín hiệu hiệu lực, map tên quan hệ sang loai.

    Cột của `relationships.parquet`: `doc_id` (bên THỰC HIỆN hành vi sửa đổi/thay
    thế/...), `other_doc_id` (bên BỊ tác động), `relationship` (tên quan hệ tiếng
    Việt). Cạnh ĐI VÀO corpus là cạnh có `other_doc_id` nằm trong corpus — hướng
    ngược với "đi ra" mà API trả.

    Loại cạnh TỰ TRỎ (`doc_id == other_doc_id`, "văn bản X thay thế/sửa đổi
    chính X") — rác của nguồn crawl bên thứ ba (xem cảnh báo đầu file), không
    phải một quan hệ pháp lý có thật. Đo được 2026-09-02 sau khi mở corpus
    (`other_doc_id` giờ phủ cả 87 văn bản tầng `shallow`, không chỉ 53 văn
    bản `deep` của `DOC_IDS`): đúng 3 cạnh loại này lộ ra, cả ba đều trỏ vào
    một văn bản `shallow` (`2322`, `146541`, `132170`) — trước đó bị lọc mất
    tình cờ vì `other_doc_id` của chúng chưa từng nằm trong corpus hẹp.
    """
    df = rel[["doc_id", "other_doc_id", "relationship"]].copy()
    df["doc_id"] = df["doc_id"].astype(str).replace(BAN_TRUNG)
    df["other_doc_id"] = df["other_doc_id"].astype(str).replace(BAN_TRUNG)
    df = df[df["other_doc_id"].isin(corpus) & df["relationship"].isin(QUAN_HE_HIEU_LUC)
            & (df["doc_id"] != df["other_doc_id"])].drop_duplicates()
    sai = pd.Series([k in CANH_SAI for k in zip(df["doc_id"], df["other_doc_id"],
                                                  df["relationship"], strict=True)],
                    index=df.index, dtype=bool)
    df = df[~sai]
    df["loai"] = df["relationship"].map(QUAN_HE_HIEU_LUC)
    return df.rename(columns={"doc_id": "from_document_id", "other_doc_id": "to_document_id",
                               "relationship": "raw_text"})


def _ngay(s: object) -> date | None:
    """metadata.parquet ghi ngày dạng chuỗi 'DD/MM/YYYY'; NaN khi văn bản còn
    hiệu lực (chưa có ngày hết hiệu lực) — không phải lỗi, trả None."""
    if not isinstance(s, str) or not s:
        return None
    return datetime.strptime(s, "%d/%m/%Y").date()


def load_from_parquet(path: Path, engine: Engine, them_van_ban_ngoai: bool = True) -> int:
    """Nạp cạnh hiệu lực đi vào corpus từ `path` (relationships.parquet) vào
    `"references"`. `metadata.parquet` được suy ra CÙNG THƯ MỤC với `path`.

    Idempotent: chèn văn bản ngoài corpus qua `ON CONFLICT DO NOTHING`, và xoá
    sạch cạnh loai 20..23 cũ trước khi chèn lại — chạy hai lần cho cùng số dòng.

    Trả số cạnh đã ghi. RAISE trước khi chạm DB nếu có cạnh trỏ tới văn bản
    ngoài corpus mà `metadata.parquet` không có — không tự bịa dữ liệu, không
    âm thầm bỏ qua (yêu cầu #3).

    `corpus`: khi có `engine`, đọc TRỰC TIẾP từ `documents` (`depth <>
    'metadata'`) — sửa 2026-09-02. Trước đó dùng `set(DOC_IDS)` (danh sách 53
    văn bản `deep` mà `fetch_moj.py` tải toàn văn), đúng lúc corpus THẬT chỉ
    có đúng ngần ấy văn bản; mở kho ra 8 lĩnh vực thêm 87 văn bản tầng
    `shallow` vào `documents` mà KHÔNG thêm vào `DOC_IDS` (chúng không tải
    toàn văn), nên "corpus" của loader tụt lại phía sau "corpus" thật — cạnh
    đi vào các văn bản `shallow` bị loại oan, và văn bản `shallow` đóng vai
    `from_document_id` bị coi nhầm là ngoài corpus. `DOC_IDS` giữ lại làm
    phương án lùi khi `engine=None` (test đơn vị dựng tay, không có DB).

    ĐỌC corpus TRƯỚC khi gọi `run_migrations()` ở dưới — KHÔNG đảo thứ tự.
    `run_migrations()` (qua `016_tang_nong.sql`) nâng cấp `depth='metadata'`
    thành `'shallow'` cho văn bản chỉ-metadata đủ điều kiện, mà CHÍNH HÀM
    NÀY vừa chèn những văn bản chỉ-metadata đó ở lần gọi TRƯỚC. Gọi
    `run_migrations()` rồi mới đọc corpus tạo một vòng phản hồi: mỗi lần gọi
    lại nâng cấp lô văn bản chỉ-metadata của lần gọi trước thành `shallow`
    (⇒ vào corpus), corpus phình ra, kéo thêm cạnh mới, tạo thêm văn bản
    chỉ-metadata mới cho lần gọi kế — không bao giờ dừng, và
    `test_idempotent_chay_hai_lan_cung_so_dong` bắt được ngay (683→776 dòng
    chỉ-metadata chỉ sau một lần gọi lại). Đọc corpus TRƯỚC giữ nó là một ẢNH
    CHỤP của `documents` tại thời điểm gọi, độc lập với tác dụng phụ của
    chính lần gọi này.

    `them_van_ban_ngoai=False`: KHÔNG chèn văn bản chỉ-metadata mới; cạnh từ văn
    bản chưa có trong `documents` bị bỏ và ĐẾM ra. Dùng khi kho vừa nhận văn
    bản deep mới mà quyết định mở kho có ranh giới
    (`docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md` mục 4)
    chưa cho nạp vòng văn bản kế tiếp.

    Sau cạnh parquet (trừ `CANH_SAI`) là `CANH_DOI_CHIEU_NGUYEN_VAN` và cạnh suy
    từ VBHN (`_canh_tu_vbhn`); hai đầu của chúng phải có trong `documents`,
    thiếu thì RAISE.
    """
    if engine is not None:
        with engine.connect() as c:
            corpus = {r[0] for r in c.execute(
                text("SELECT id FROM documents WHERE depth <> 'metadata'")
            )}
            da_co = {r[0] for r in c.execute(text("SELECT id FROM documents"))}
    else:
        corpus = set(DOC_IDS)
        da_co = corpus
    rel = pd.read_parquet(path)
    canh = _canh_hieu_luc_di_vao(rel, corpus)
    if not them_van_ban_ngoai:
        ngoai = ~canh["from_document_id"].isin(da_co)
        print(f"bỏ {int(ngoai.sum())} cạnh từ {canh[ngoai]['from_document_id'].nunique()} "
              "văn bản chưa có trong documents (them_van_ban_ngoai=False)")
        canh = canh[~ngoai]

    ngoai_corpus = set(canh["from_document_id"]) - corpus
    meta = pd.read_parquet(path.parent / "metadata.parquet", columns=list(_COT_METADATA))
    meta["id"] = meta["id"].astype(str)
    meta = meta[meta["id"].isin(ngoai_corpus)].set_index("id")

    thieu = ngoai_corpus - set(meta.index)
    if thieu:
        raise ValueError(
            f"{len(thieu)} văn bản ngoài corpus không có metadata trong metadata.parquet — "
            f"KHÔNG nạp được cạnh trỏ tới chúng (không tự bịa dữ liệu): {sorted(thieu)}"
        )

    run_migrations()
    with engine.begin() as conn:
        for doc_id, row in meta.iterrows():
            conn.execute(text(
                "INSERT INTO documents"
                " (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, depth, checksum,"
                "  ngay_ban_hanh, ngay_hieu_luc, ngay_het_hieu_luc)"
                " VALUES (:id, :so_ky_hieu, :loai_van_ban, :ten, 'chua_xac_dinh', 'metadata',"
                "         'metadata-only', :ngay_ban_hanh, :ngay_hieu_luc, :ngay_het_hieu_luc)"
                " ON CONFLICT (id) DO NOTHING"
            ), {"id": doc_id, "so_ky_hieu": row["so_ky_hieu"], "loai_van_ban": row["loai_van_ban"],
                "ten": row["title"], "ngay_ban_hanh": _ngay(row["ngay_ban_hanh"]),
                "ngay_hieu_luc": _ngay(row["ngay_co_hieu_luc"]),
                "ngay_het_hieu_luc": _ngay(row["ngay_het_hieu_luc"])})

        them = [*CANH_DOI_CHIEU_NGUYEN_VAN, *_canh_tu_vbhn(conn)]
        co = {r[0] for r in conn.execute(text("SELECT id FROM documents"))}
        vang = sorted({x for f, t, _, _ in them for x in (f, t)} - co)
        if vang:
            raise ValueError(f"cạnh bổ sung trỏ tới văn bản chưa có trong documents: {vang}")
        canh = _bo_sung(canh, them)

        conn.execute(text('DELETE FROM "references" WHERE loai IN (20, 21, 22, 23)'))
        ghi = 0
        for r in canh.itertuples(index=False):
            conn.execute(text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                " VALUES (:f, :t, :l, :r)"
            ), {"f": r.from_document_id, "t": r.to_document_id, "l": r.loai, "r": r.raw_text})
            ghi += 1
    return ghi


if __name__ == "__main__":
    import sys

    from src.config import get_settings
    from src.services.db import get_engine

    s = get_settings()
    n = load_from_parquet(Path(s.data_raw_dir) / "relationships.parquet", get_engine(),
                          them_van_ban_ngoai="--khong-them-van-ban-ngoai" not in sys.argv)
    print(f"cạnh hiệu lực đi vào đã nạp: {n}")
