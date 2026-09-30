"""`GET /bo-loc` · `GET /tim-kiem` — tìm kiếm DANH SÁCH điều khoản (Pha 2).

Khác `/tra-cuu` ở đúng một điểm quyết định mọi thứ còn lại: nó trả **một danh
sách để duyệt**, không phải một câu trả lời đã kiểm chứng. Nên nó KHÔNG gọi LLM,
KHÔNG gọi embedding, và vì vậy KHÔNG đi qua `cong_bao_ve`.

## Vì sao chỉ BM25, không dense

`chunks.embedding` có sẵn, nhưng dùng nó buộc phải embed CÂU TRUY VẤN mỗi lần —
một request HTTP trả tiền tới Voyage cho mỗi ký tự người dùng gõ vào ô tìm kiếm.
Ba hệ quả, không cái nào chấp nhận được cho một ô tìm kiếm:
  * mỗi lượt gõ là một khoản chi ⇒ endpoint đọc thuần trở thành endpoint tốn
    tiền ⇒ phải dựng cổng ⇒ ô tìm kiếm bị rate limit như một lượt hỏi AI;
  * độ trễ đi từ ~20ms (GIN index tại chỗ) lên ~300-500ms (mạng);
  * nhánh dense hỏng (429, hết hạn mức) làm ô tìm kiếm chết, trong khi `tsv`
    không bao giờ cần mạng.
Người dùng gõ TỪ KHOÁ vào ô tìm kiếm, không gõ câu hỏi — đó đúng là việc của
BM25. Câu hỏi tự nhiên vẫn đi `/tra-cuu`, nơi dense đã được đo là tốt hơn.

## Vì sao 422 chứ không phải danh sách rỗng cho một giá trị lọc lạ

`kiem-ke-fe-lovable.md` §9: FE giả định 11 loại văn bản và 8 cơ quan; DB có 8 và
3. Một chip trỏ vào giá trị không tồn tại trả rỗng nghĩa là người dùng đọc
"KLAW không có văn bản nào về việc này" — một khẳng định SAI, phát ra im lặng.
422 kèm danh sách giá trị thật là thứ duy nhất làm lỗi đó lộ ra ở lần chạy đầu.
"""

import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import as_of_hieu_luc, get_settings
from src.models.schemas import (
    BoLocResponse,
    DongTimTrongVanBan,
    GiaTriLoc,
    HieuLucOut,
    KetQuaTimKiem,
    TimKiemResponse,
    TimTrongVanBanResponse,
)
from src.services.db import get_engine
from src.services.effectivity import bac_con_song, danh_gia_toan_bo
from src.services.embedding import from_settings as embedder_from_settings
from src.services.hien_thi import chan_neu_an, dieu_khoan_an, hieu_luc_ra, nap_van_ban_dan, tap_hien_thi

logger = logging.getLogger(__name__)

router = APIRouter()

SAP_XEP = ("lien_quan", "moi_nhat", "con_hieu_luc_truoc")
SapXep = Literal["lien_quan", "moi_nhat", "con_hieu_luc_truoc"]

# Trần cứng của `limit`. 100 điều khoản đã dài hơn mọi màn hình; cao hơn nữa chỉ
# phục vụ một vòng lặp kéo cả corpus qua một endpoint không có cổng nào.
LIMIT_MAX = 100
TRICH_MAX = 400


# Loại `depth = 'metadata'` ở CẢ BA truy vấn — từ vựng của bộ lọc phải mô tả
# đúng tập hợp mà bộ lọc tìm trong đó. `/tim-kiem` khớp trên `provisions`, nên
# bản ghi tầng metadata (0 điều khoản) là thứ nó không bao giờ trả về; đếm
# chúng vào đây khiến mỗi chip hứa nhiều hơn thứ bấm vào nhận được.
#
# Sửa 2026-09-02: trước đây lọc `depth = 'deep'`, đo đúng lúc corpus chỉ có
# hai tầng `deep`/`metadata` (deep=47 đều có điều khoản, metadata=79 đều
# không). Mở kho ra 8 lĩnh vực thêm tầng `shallow` (87 văn bản, mỗi văn bản 1
# provision `cap='mo_dau'` — tên văn bản, không phải điều khoản thật) — và
# provision đó CÓ chunk, nên `/tim-kiem` VẪN với tới được nó (khớp trên tên
# văn bản). Lọc `depth = 'deep'` từ đó bỏ sót 87 văn bản mà bộ lọc lẽ ra phải
# đếm, tái diễn đúng lỗi mà comment này từng sửa. Đo 2026-09-02: mọi văn bản
# có `depth <> 'metadata'` đều có provision (141/141), mọi văn bản `metadata`
# đều không (0/4) — đổi điều kiện sang phủ định `depth = 'metadata'` để bất
# biến này không vỡ lại lần nữa khi thêm một tầng độ sâu mới.
#
# Tầng metadata KHÔNG bị giấu: `/pham-vi` công bố riêng cả ba tầng — đó là
# chỗ đúng để nói ra, không phải bộ lọc.
#
# `id = ANY(:hien)` (quyết định 2026-09-28 mục 8): mọi con số của bộ lọc chỉ đếm
# văn bản được HIỆN, để số cạnh ô tick luôn bằng số dòng danh sách trả về.
_KHONG_METADATA = " WHERE depth <> 'metadata' AND id = ANY(CAST(:hien AS text[]))"

_SQL_BO_LOC = text(
    "SELECT count(*)::int AS tong,"
    # Có toàn văn = có ít nhất một điều khoản thật, cùng thước `/pham-vi` (hàng
    # `mo_dau` của migration 016 chỉ mang tên văn bản). Quyết định 2026-09-28 mục
    # 16: văn bản chưa có toàn văn vẫn được hiện, nên con số này ≠ `tong`.
    " count(*) FILTER (WHERE EXISTS (SELECT 1 FROM provisions p"
    "   WHERE p.document_id = documents.id AND p.cap <> 'mo_dau'))::int AS so_co_toan_van,"
    " count(*) FILTER (WHERE co_quan_ban_hanh IS NULL)::int AS khong_ro_co_quan,"
    " min(extract(year FROM ngay_ban_hanh))::int AS nam_min,"
    " max(extract(year FROM ngay_ban_hanh))::int AS nam_max"
    " FROM documents" + _KHONG_METADATA
)
_SQL_LOAI = text(
    "SELECT loai_van_ban AS gia_tri, count(*)::int AS so_van_ban FROM documents"
    + _KHONG_METADATA + " GROUP BY 1 ORDER BY 2 DESC, 1"
)
_SQL_CO_QUAN = text(
    "SELECT co_quan_ban_hanh AS gia_tri, count(*)::int AS so_van_ban FROM documents"
    + _KHONG_METADATA + " AND co_quan_ban_hanh IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1"
)


def _bo_loc_sync() -> BoLocResponse:
    eff = danh_gia_toan_bo(get_engine(), as_of_hieu_luc(None))
    with get_engine().connect() as c:
        hien = {"hien": list(tap_hien_thi(c, eff))}
        tong = c.execute(_SQL_BO_LOC, hien).mappings().one()
        loai = [GiaTriLoc(**dict(r)) for r in c.execute(_SQL_LOAI, hien).mappings().all()]
        co_quan = [GiaTriLoc(**dict(r)) for r in c.execute(_SQL_CO_QUAN, hien).mappings().all()]
    return BoLocResponse(
        tong_van_ban=tong["tong"],
        so_co_toan_van=tong["so_co_toan_van"],
        loai_van_ban=loai,
        co_quan_ban_hanh=co_quan,
        co_quan_khong_ro=tong["khong_ro_co_quan"],
        nam_min=tong["nam_min"],
        nam_max=tong["nam_max"],
        sap_xep=list(SAP_XEP),
    )


@router.get("/bo-loc", response_model=BoLocResponse)
async def bo_loc() -> BoLocResponse:
    """Từ vựng bộ lọc, đếm từ DB. FE dựng chip TỪ ĐÂY, không hardcode."""
    return await run_in_threadpool(_bo_loc_sync)


# ── /tim-kiem ────────────────────────────────────────────────────────────────

# Cùng khuôn tsquery với `retrieval.Retriever.bm25` — `plainto_tsquery` nối AND,
# mà một truy vấn thật gần như không bao giờ chứa ĐỦ mọi từ của điều luật, nên
# AND cho rỗng và ô tìm kiếm trông như hỏng. Đổi '&' → '|' và để `ts_rank` xếp
# hạng theo số lexeme khớp. Guard `tq::text <> ''` chặn truy vấn không sinh
# lexeme nào khớp bừa cả bảng.
#
# `max(ts_rank(...))` + `GROUP BY provision_id`: một Điều dài bị cắt thành nhiều
# chunk, và không lọc `embedding_model` thì MỖI điều khoản đếm hai lần (corpus
# giữ song song hai bộ embedding — `bge-m3` và `voyage-4-lite` — trên cùng một
# `noi_dung_embed`, xem eval-baseline-moi.md). Đó là cách "N điều khoản" thành
# 2N mà không ai thấy.
_KHOP = (
    "WITH q AS ("
    "  SELECT replace(plainto_tsquery('simple', unaccent(:q))::text, '&', '|')::tsquery AS tq"
    "), khop AS ("
    "  SELECT c.provision_id, max(ts_rank(c.tsv, q.tq, CAST(:norm AS integer))) AS score,"
    "         (array_agg(c.noi_dung_embed ORDER BY ts_rank(c.tsv, q.tq, CAST(:norm AS integer)) DESC))[1] AS chunk"
    "  FROM chunks c, q"
    "  WHERE c.embedding_model = :model AND q.tq::text <> '' AND c.tsv @@ q.tq"
    "  GROUP BY c.provision_id"
    "), loc AS ("
    "  SELECT k.provision_id, k.score, k.chunk, p.cap, p.so_hieu_cap, p.duong_dan,"
    "         p.tieu_de, p.noi_dung, d.id AS doc_id, d.so_ky_hieu, d.ten AS bo_luat,"
    "         d.loai_van_ban, d.co_quan_ban_hanh, d.ngay_ban_hanh"
    "  FROM khop k"
    "  JOIN provisions p ON p.id = k.provision_id"
    # Chỉ văn bản được hiện (`services/hien_thi`) — trong SQL, để hai con số
    # tổng và phân trang đếm đúng tập người dùng thấy.
    "  JOIN documents d ON d.id = p.document_id AND d.id = ANY(CAST(:hien AS text[]))"
    # … và không có điều khoản bị bãi bỏ nào (quyết định 2026-09-30 mục 9).
    "   AND NOT (p.id = ANY(CAST(:bai_bo AS bigint[])))"
    # `CAST(... AS text[]) IS NULL` ở CẢ hai vế: psycopg gửi tham số không kèm
    # kiểu, và một `$n IS NULL` trần làm Postgres không suy được kiểu ⇒
    # AmbiguousParameter. Ép kiểu ở vế kiểm NULL, không chỉ ở vế so sánh.
    "  WHERE (CAST(:loai AS text[]) IS NULL"
    "         OR d.loai_van_ban = ANY(CAST(:loai AS text[])))"
    "    AND (CAST(:co_quan AS text[]) IS NULL"
    "         OR d.co_quan_ban_hanh = ANY(CAST(:co_quan AS text[])))"
    "    AND (CAST(:tu_ngay AS date) IS NULL OR d.ngay_ban_hanh >= CAST(:tu_ngay AS date))"
    "    AND (CAST(:den_ngay AS date) IS NULL OR d.ngay_ban_hanh <= CAST(:den_ngay AS date))"
    ")"
)

_SQL_TONG = text(
    _KHOP + " SELECT count(*)::int AS tong_dieu_khoan,"
    " count(DISTINCT doc_id)::int AS tong_van_ban FROM loc"
)

# `array_position(:thu_tu_doc, doc_id)` — bậc hiệu lực tính TRONG Python bởi
# `effectivity.danh_gia`, đưa xuống SQL dưới dạng một mảng doc_id đã xếp bậc.
# Phải xếp ở tầng SQL (không phải sau khi lấy trang) vì `sap_xep` áp lên TOÀN
# tập khớp: sắp xếp một trang đã cắt là sắp xếp nhầm 20 dòng đầu tiên tình cờ
# rơi vào đó. Mảng ≤126 phần tử (cả corpus) nên phép tra rẻ.
#
# Chốt đuôi bằng `provision_id` ở MỌI nhánh: `ORDER BY` không tất định thì hai
# trang liên tiếp chồng nhau và bỏ sót — cùng dòng, người dùng thấy hai lần.
_ORDER = {
    "lien_quan": "ORDER BY score DESC, provision_id",
    "moi_nhat": "ORDER BY ngay_ban_hanh DESC NULLS LAST, score DESC, provision_id",
    "con_hieu_luc_truoc": (
        "ORDER BY array_position(CAST(:thu_tu_doc AS text[]), doc_id),"
        " score DESC, provision_id"
    ),
}

_SQL_TRANG = {
    k: text(_KHOP + " SELECT * FROM loc " + v + " LIMIT :limit OFFSET :offset")
    for k, v in _ORDER.items()
}


def _trich(noi_dung: str, chunk: str) -> str:
    """Đoạn xem trước của một kết quả.

    `provisions.noi_dung` rỗng ở 73,6% số Điều (Điều chỉ có tiêu đề, nội dung
    nằm trong Khoản con) — trả nó thẳng là trả một ô trống cho phần lớn kết quả.
    `chunks.noi_dung_embed` mang nguyên cây Điều, nhưng dòng ĐẦU của nó là
    `duong_dan` (tiền tố do chunker thêm) và đã có sẵn ở trường `duong_dan` —
    lặp lại là chiếm mất chỗ của nội dung thật.

    ponytail: cắt theo ký tự, KHÔNG `ts_headline`. `chunks.tsv` dựng trên
    `unaccent(...)` nên tsquery không dấu không khớp được văn bản CÓ dấu, và
    chạy headline trên bản không dấu trả về một đoạn tiếng Việt mất dấu — không
    đọc được. Tô sáng để FE làm phía client; nâng cấp khi có `tsv` giữ dấu.
    """
    than = (noi_dung or "").strip()
    if not than:
        than = (chunk or "").split("\n", 1)[-1].strip()
    return than[:TRICH_MAX] + "…" if len(than) > TRICH_MAX else than


def kiem_gia_tri_loc(conn, cot: str, gia_tri: list[str] | None, hien: frozenset[str]) -> None:
    """Từ chối một giá trị lọc không có trong DB, nêu tên các giá trị THẬT — của
    văn bản được hiện: một giá trị chỉ văn bản ẩn mang là một chip trả rỗng."""
    if not gia_tri:
        return
    that = {
        r[0] for r in conn.execute(
            text(f"SELECT DISTINCT {cot} FROM documents WHERE {cot} IS NOT NULL"  # noqa: S608
                 " AND id = ANY(CAST(:hien AS text[]))"),
            {"hien": list(hien)},
        ).all()
    }
    la = sorted(set(gia_tri) - that)
    if la:
        raise HTTPException(status_code=422, detail=(
            f"{cot} không có giá trị {la} trong CSDL. Giá trị thật: {sorted(that)}. "
            "Lấy danh sách này từ GET /api/v1/bo-loc, đừng viết cứng."
        ))


def _tim_kiem_sync(
    q: str, loai: list[str] | None, co_quan: list[str] | None,
    tu_nam: int | None, den_nam: int | None, sap_xep: str,
    limit: int, offset: int, as_of: date,
) -> TimKiemResponse:
    s = get_settings()
    tham_so = {
        "q": q,
        "norm": s.bm25_rank_normalization,
        # Cùng model với đường truy hồi: hai bộ embedding song song trên cùng
        # `noi_dung_embed`, không lọc là đếm đôi mọi điều khoản.
        "model": embedder_from_settings().model,
        "loai": loai,
        "co_quan": co_quan,
        "tu_ngay": date(tu_nam, 1, 1) if tu_nam else None,
        "den_ngay": date(den_nam, 12, 31) if den_nam else None,
    }
    # Phán quyết hiệu lực của TOÀN corpus: cần cho cột `hieu_luc` của mỗi dòng,
    # và (khi sap_xep=con_hieu_luc_truoc) cho cả thứ tự. Một lượt, 2 truy vấn —
    # xem `danh_gia_toan_bo`.
    #
    # Chạy TRƯỚC `with ... connect()`, không phải bên trong. `danh_gia_toan_bo`
    # tự mở kết nối của nó, nên gọi nó khi đang giữ kết nối #1 làm MỘT request
    # chiếm HAI suất pool cùng lúc — pool phục vụ được một nửa số request đồng
    # thời so với cỡ của nó, và phần còn lại chờ hết `pool_timeout` rồi 500.
    # Đo được (concurrency 24, máy chủ dev): median 30,181s kèm 500, và
    # `/api/v1/bo-loc` — endpoint không liên quan, bình thường 0,005s — bị kéo
    # lên 29,832s vì cạn pool làm chết đói toàn bộ tầng DB.
    eff = danh_gia_toan_bo(get_engine(), as_of)
    tham_so["bai_bo"] = sorted(dieu_khoan_an(get_engine(), as_of))

    with get_engine().connect() as c:
        hien = tap_hien_thi(c, eff)
        tham_so["hien"] = list(hien)
        kiem_gia_tri_loc(c, "loai_van_ban", loai, hien)
        kiem_gia_tri_loc(c, "co_quan_ban_hanh", co_quan, hien)

        tong = c.execute(_SQL_TONG, tham_so).mappings().one()

        if sap_xep == "con_hieu_luc_truoc":
            tham_so["thu_tu_doc"] = [
                doc_id for doc_id, e in sorted(eff.items(), key=lambda kv: bac_con_song(kv[1]))
            ]
        rows = c.execute(
            _SQL_TRANG[sap_xep], {**tham_so, "limit": limit, "offset": offset}
        ).mappings().all()
        dan = nap_van_ban_dan(c, (v for r in rows if r["doc_id"] in eff for v in eff[r["doc_id"]].van_ban), hien)

    # `chua_xac_dinh` cho văn bản vắng mặt trong `eff` — KHÔNG `con_hieu_luc`.
    # Nhánh này không đến được hôm nay (`danh_gia_toan_bo` phủ mọi dòng
    # `documents`, và JOIN ở trên bảo đảm mỗi kết quả có một dòng ở đó), nhưng
    # mặc định an toàn phải nằm ở chính chỗ nó có thể vỡ — cùng lý lẽ với
    # `graph_tra_cuu.n_tier1`.
    thieu = HieuLucOut(
        verdict="chua_xac_dinh", tin_cay="thap",
        ly_do="không đánh giá được hiệu lực của văn bản này",
    )
    ket_qua = [
        KetQuaTimKiem(
            provision_id=r["provision_id"], doc_id=r["doc_id"], so_ky_hieu=r["so_ky_hieu"],
            bo_luat=r["bo_luat"], loai_van_ban=r["loai_van_ban"],
            co_quan_ban_hanh=r["co_quan_ban_hanh"], ngay_ban_hanh=r["ngay_ban_hanh"],
            cap=r["cap"], so_hieu_cap=r["so_hieu_cap"], duong_dan=r["duong_dan"],
            tieu_de=r["tieu_de"], trich=_trich(r["noi_dung"], r["chunk"]),
            score=float(r["score"]),
            hieu_luc=(
                HieuLucOut(**hieu_luc_ra(e, dan)) if (e := eff.get(r["doc_id"])) is not None else thieu
            ),
        )
        for r in rows
    ]
    return TimKiemResponse(
        q=q, tong_dieu_khoan=tong["tong_dieu_khoan"], tong_van_ban=tong["tong_van_ban"],
        limit=limit, offset=offset, sap_xep=sap_xep, ket_qua=ket_qua,
    )


@router.get("/tim-kiem", response_model=TimKiemResponse)
async def tim_kiem(
    q: str = Query(..., min_length=1, max_length=500),
    loai: list[str] | None = Query(default=None),
    co_quan: list[str] | None = Query(default=None),
    tu_nam: int | None = Query(default=None, ge=1900, le=2100),
    den_nam: int | None = Query(default=None, ge=1900, le=2100),
    sap_xep: SapXep = "lien_quan",
    limit: int = Query(default=20, ge=1, le=LIMIT_MAX),
    offset: int = Query(default=0, ge=0),
    as_of_date: date | None = None,
) -> TimKiemResponse:
    """Danh sách điều khoản khớp `q`, kèm TỔNG ("N điều khoản trong M văn bản").

    Mỗi kết quả mang phán quyết hiệu lực của KLAW (`hieu_luc`), KHÔNG BAO GIỜ
    `documents.tinh_trang` thô — CSDL quốc gia đánh bốn nghị định lương tối
    thiểu đã bị thay là "còn hiệu lực", và một trang tìm kiếm render trường đó
    lật ngược đúng đóng góp trung tâm của hệ thống.

    KHÔNG có cổng `cong_bao_ve`: không LLM, không embedding, không một xu nào
    rời khỏi ví (xem docstring module).
    """
    if tu_nam and den_nam and tu_nam > den_nam:
        raise HTTPException(
            status_code=422, detail=f"tu_nam ({tu_nam}) lớn hơn den_nam ({den_nam})"
        )
    return await run_in_threadpool(
        _tim_kiem_sync, q, loai, co_quan, tu_nam, den_nam, sap_xep, limit, offset,
        as_of_hieu_luc(as_of_date),
    )


# ══ GET /van-ban/{doc_id}/tim — ô lọc mục lục ═══════════════════════════════
#
# Ba khác biệt so với `/tim-kiem`, cả ba theo sau từ việc đây là một Ô LỌC:
#
#   1. Khớp CHUỖI CON (`ILIKE`), không phải lexeme. Người dùng gõ dần và mong
#      danh sách hẹp lại từ "thai s"; `to_tsquery` chỉ khớp trọn lexeme nên một
#      chuỗi dở dang không khớp gì và ô lọc trông như hỏng.
#   2. Xếp theo `thu_tu` (thứ tự văn bản), không theo điểm — xáo mục lục theo độ
#      liên quan là làm người đọc mất chỗ đang đứng.
#   3. Quét `provisions`, không quét `chunks`: `chunks` phủ 6.067/36.710 điều
#      khoản (0 Điểm, 0 Chương/Mục), nên lọc qua nó thì gõ tên một Chương ra
#      rỗng. ĐO ĐƯỢC 9,2ms trên văn bản lớn nhất (2.515 dòng, index
#      `ix_provisions_document_id` lọc trước rồi mới ILIKE) — rẻ hơn nhiều so
#      với dựng một cột `tsv` thứ hai cho một ô lọc.
#
# ponytail: ILIKE tuyến tính trong phạm vi MỘT văn bản. Nếu về sau có văn bản
# hàng chục nghìn điều khoản thì thêm index trigram (`pg_trgm`) trên
# `klaw_tsv`-style biểu thức; hôm nay đó là index cho một truy vấn 9ms.

_SQL_TIM_TRONG_VB = (
    " FROM provisions p"
    " WHERE p.document_id = :doc_id"
    # Điều khoản bị bãi bỏ không được tìm thấy (quyết định 2026-09-30 mục 9); thân trang
    # văn bản chỉ còn câu "Đã bị bãi bỏ bởi …" cho nó.
    "   AND NOT (p.id = ANY(CAST(:bai_bo AS bigint[])))"
    "   AND unaccent(p.tieu_de || ' ' || p.noi_dung)"
    "       ILIKE '%' || unaccent(:q) || '%' ESCAPE '\\'"
)
_SQL_TIM_TRONG_VB_DEM = text("SELECT count(*)::int" + _SQL_TIM_TRONG_VB)
_SQL_TIM_TRONG_VB_TRANG = text(
    "SELECT p.id AS provision_id, p.cap, p.so_hieu_cap, p.duong_dan, p.tieu_de,"
    " p.noi_dung, p.thu_tu" + _SQL_TIM_TRONG_VB + " ORDER BY p.thu_tu LIMIT :limit"
)

_SQL_DOC_TOI_THIEU = text("SELECT so_ky_hieu FROM documents WHERE id = :doc_id")


def _thoat_like(q: str) -> str:
    r"""`%` và `_` trong truy vấn là CHỮ CỦA NGƯỜI DÙNG, không phải toán tử.

    Không thoát thì gõ `%` khớp MỌI điều khoản — một ô lọc "không lọc gì" mà
    không thông báo nào, và `_` khớp một ký tự bất kỳ cho kết quả sai lặng lẽ.
    `\` phải thoát TRƯỚC hai ký tự kia, nếu không nó thoát mất chính dấu thoát
    vừa chèn.
    """
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _tim_trong_van_ban_sync(doc_id: str, q: str, limit: int) -> TimTrongVanBanResponse:
    mau = _thoat_like(q)
    as_of = as_of_hieu_luc(None)
    chan_neu_an(get_engine(), doc_id, as_of)
    bai_bo = sorted(dieu_khoan_an(get_engine(), as_of))
    with get_engine().connect() as c:
        so_ky_hieu = c.execute(_SQL_DOC_TOI_THIEU, {"doc_id": doc_id}).scalar_one_or_none()
        if so_ky_hieu is None:
            raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")
        tham_so = {"doc_id": doc_id, "q": mau, "bai_bo": bai_bo}
        tong = c.execute(_SQL_TIM_TRONG_VB_DEM, tham_so).scalar_one()
        rows = c.execute(
            _SQL_TIM_TRONG_VB_TRANG, {**tham_so, "limit": limit}
        ).mappings().all()

    return TimTrongVanBanResponse(
        doc_id=doc_id, so_ky_hieu=so_ky_hieu, q=q, tong=tong, limit=limit,
        ket_qua=[
            DongTimTrongVanBan(
                provision_id=r["provision_id"], cap=r["cap"], so_hieu_cap=r["so_hieu_cap"],
                duong_dan=r["duong_dan"], tieu_de=r["tieu_de"], thu_tu=r["thu_tu"],
                # Chương/Mục có `noi_dung` rỗng theo thiết kế (chúng là nhãn cấu
                # trúc); rơi về `tieu_de` để dòng kết quả không trống trơn.
                trich=_trich(r["noi_dung"] or r["tieu_de"], ""),
            )
            for r in rows
        ],
    )


@router.get("/van-ban/{doc_id}/tim", response_model=TimTrongVanBanResponse)
async def tim_trong_van_ban(
    doc_id: str,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
) -> TimTrongVanBanResponse:
    """Lọc mục lục + nội dung của MỘT văn bản theo chuỗi con, không dấu cũng khớp.

    `tong` là số dòng khớp trong CẢ văn bản (không phải trong trang), để ô lọc
    hiển thị được "112 kết quả" ngay cả khi chỉ vẽ 100 dòng đầu.
    """
    return await run_in_threadpool(_tim_trong_van_ban_sync, doc_id, q, limit)
