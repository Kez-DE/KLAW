"""Chunk toàn corpus rồi embed, ghi vào chunks.

Chạy lại với CÙNG model → thay thế bộ cũ. Chạy với model KHÁC → thêm bộ mới
song song (đó là cơ chế của bảng so sánh embedding tuần 4).
"""

import sys

from sqlalchemy import text

from src.config import get_settings
from src.services.chunker import build_chunks, load_provisions
from src.services.db import get_engine, run_migrations
from src.services.embedding import EmbeddingClient

# Server OpenRouter nhận lô tối đa 100 text/request (đã kiểm ở Task 3) — lô
# lớn hơn mặc định EmbeddingClient.batch=32 để giảm số request cho ~3.283 chunk.
_EMBED_BATCH = 100

# Văn bản nạp ở K1 CHỈ vì một văn bản trong kho thay thế hoặc bãi bỏ nó — cả 24
# đều đã hết hiệu lực. Chúng ở DB cho tầng 1 kiểm trích dẫn cũ và cho chuỗi thay
# thế, KHÔNG làm nguồn truy hồi (quyết định 2026-09-28 mục 8: văn bản hết hiệu
# lực giữ ẩn, không hiện, không trích như luật đang áp dụng).
#   * 17 dòng đầu: nguyên văn văn bản trong kho bãi bỏ chúng, nhưng `effectivity`
#     dán `can_doi_chieu_tay` (cạnh nối hai tiêu đề khác chủ đề, guard
#     `cung_chu_de`), mà assemble chỉ lọc `bi_thay_the`/`het_hieu_luc` khỏi văn
#     xuôi — câu trả lời lao động viết từ nghị định 2013-2015 đã bãi bỏ.
#   * 7 dòng sau: nhãn đúng và assemble lọc khỏi văn xuôi, nhưng vẫn chiếm chỗ
#     ứng viên. Đo golden 77 khi chúng còn trong chỉ mục: trúng dẫn 56,8% so với
#     62,7-64,0% trước K1; 28/2020 (112 chunk) nằm trong top-10 hybrid của 7/13
#     câu đổi kết quả.
# Đo 2026-09-28: 24 văn bản, 536 chunk voyage.
# ponytail: bảng tay; quy tắc hiển thị K7 thay nó bằng một quy tắc chung.
KHONG_DANH_CHI_MUC: dict[str, str] = {
    "33381": "03/2014/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm a",
    "32526": "44/2013/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm b",
    "48298": "05/2015/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm b",
    "131643": "148/2018/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm b",
    "132028": "149/2018/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm d",
    "30466": "49/2013/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm đ",
    "131010": "121/2018/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm đ",
    "30460": "45/2013/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm e",
    "84922": "85/2015/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm g",
    "34095": "27/2014/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm h",
    "30467": "46/2013/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm i",
    "30472": "41/2013/NĐ-CP — 145/2020/NĐ-CP Điều 114 khoản 2 điểm k",
    "36843": "73/2014/NĐ-CP — 29/2019/NĐ-CP Điều 28 khoản 2",
    "37502": "01/2014/TT-BLĐTBXH — 29/2019/NĐ-CP Điều 28 khoản 2",
    "43992": "40/2014/TT-NHNN — 29/2019/NĐ-CP Điều 28 khoản 2",
    "43821": "10/2013/TT-BLĐTBXH — 09/2020/TT-BLĐTBXH Điều 13 khoản 2 điểm a",
    "43819": "11/2013/TT-BLĐTBXH — 09/2020/TT-BLĐTBXH Điều 13 khoản 2 điểm b",
    "154245": "38/2022/NĐ-CP — het_hieu_luc; 74/2024/NĐ-CP Điều 5 khoản 2",
    "141147": "28/2020/NĐ-CP — bi_thay_the, 12/2022/NĐ-CP",
    "94345": "54/2015/TT-BLĐTBXH — bi_thay_the (suy luận), 18/2021/TT-BLĐTBXH",
    "30475": "55/2013/NĐ-CP — het_hieu_luc; 29/2019/NĐ-CP Điều 28 khoản 2",
    "179969": "07/2025/UBTVQH15 — het_hieu_luc (effTo MOJ 01/7/2026)",
    "12807": "14/2008/QH12 — bi_thay_the, 67/2025/QH15",
    "14832": "78/2006/QH11 — bi_thay_the, 38/2019/QH14 Điều 151 khoản 3",
}


def run(
    model: str | None = None, dry_run: bool = False, chi_moi: bool = False, chi_id: frozenset[str] | None = None
) -> dict:
    """`chi_moi`: chỉ embed chunk (provision_id, noi_dung_embed) CHƯA có cho
    `model` và xoá chunk không còn khớp chunker — kết quả bằng một lần chạy
    đầy đủ, nhưng chunk cũ giữ id và vector (số đo truy hồi trước/sau nạp thêm
    văn bản vẫn so được với nhau).

    `chi_id` (chỉ đi cùng `chi_moi`): chỉ xét các văn bản này — chunk của văn bản
    khác không embed, không xoá. K6 cần nó: 60 hàng ngoài kho chèn nhầm 2026-09-29
    chưa có chunk, và bản khôi phục K8 xoá chúng với điều kiện 0 chunk."""
    if chi_id is not None and not chi_moi:
        raise ValueError("chi_id chỉ đi cùng chi_moi: lượt đầy đủ xoá chunk của mọi văn bản khác")
    s = get_settings()
    run_migrations()
    model = model or s.openrouter_embedding_model_name

    provisions = [
        p
        for p in load_provisions(get_engine())
        if p["document_id"] not in KHONG_DANH_CHI_MUC and (chi_id is None or p["document_id"] in chi_id)
    ]
    chunks = build_chunks(provisions, s.chunk_max_tokens)
    if not chunks:
        raise ValueError("0 chunk — provisions rỗng hoặc chunker lỗi")
    # Văn bản tầng sâu không có chunk nào thì vô hình với truy hồi mà mọi phép đếm
    # chunk vẫn xanh (14681, 24312 sau K6). Dừng TRƯỚC khi embed.
    van_ban_cua = {p["id"]: p["document_id"] for p in provisions}
    co_chunk = {van_ban_cua[c.provision_id] for c in chunks}
    if thieu := sorted({p["document_id"] for p in provisions if p["depth"] == "deep"} - co_chunk):
        raise ValueError(f"văn bản tầng sâu không sinh chunk nào: {thieu}")

    info = {
        "provisions": len(provisions),
        "chunks": len(chunks),
        "model": model,
        "tokens": sum(c.token_count for c in chunks),
    }
    thua: list[int] = []
    if chi_moi:
        with get_engine().connect() as conn:
            co = {
                (r[0], r[1]): r[2]
                for r in conn.execute(
                    text("SELECT provision_id, noi_dung_embed, id FROM chunks WHERE embedding_model = :m"), {"m": model}
                )
            }
        if chi_id is not None:
            cua_tap = {p["id"] for p in provisions}
            co = {k: i for k, i in co.items() if k[0] in cua_tap}
        dung = {(c.provision_id, c.noi_dung_embed) for c in chunks}
        thua = [i for k, i in co.items() if k not in dung]
        chunks = [c for c in chunks if (c.provision_id, c.noi_dung_embed) not in co]
        info |= {"moi": len(chunks), "thua": len(thua), "tokens_moi": sum(c.token_count for c in chunks)}
    if dry_run:
        return info

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url, model=model, dim=s.openrouter_embedding_dim
    )
    embedder.batch = _EMBED_BATCH

    print(f"embed {len(chunks)} chunk (~{info.get('tokens_moi', info['tokens']):,} token) bằng {model} …")
    vectors = embedder.embed([c.noi_dung_embed for c in chunks])
    if len(vectors) != len(chunks):
        raise ValueError(f"{len(vectors)} vector cho {len(chunks)} chunk")

    rows = [
        {"p": c.provision_id, "t": c.noi_dung_embed, "v": str(v), "m": model, "d": embedder.dim, "n": c.token_count}
        for c, v in zip(chunks, vectors, strict=True)
    ]
    with get_engine().begin() as conn:
        if chi_moi:
            conn.execute(text("DELETE FROM chunks WHERE id = ANY(:ids)"), {"ids": thua})
        else:
            conn.execute(text("DELETE FROM chunks WHERE embedding_model = :m"), {"m": model})
        if rows:
            conn.execute(
                text(
                    "INSERT INTO chunks (provision_id, noi_dung_embed, embedding,"
                    " embedding_model, embedding_dim, token_count)"
                    " VALUES (:p, :t, CAST(:v AS vector), :m, :d, :n)"
                ),
                rows,
            )
    return info


if __name__ == "__main__":
    # tách flag ("--dry-run") khỏi model — sys.argv[1] có thể LÀ "--dry-run"
    # nếu không lọc, model sẽ bị gán nhầm thành chuỗi "--dry-run"
    # `--chi-id=TỆP`: tệp id văn bản, cách nhau bằng khoảng trắng (đi cùng --chi-moi).
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    mdl = positional[0] if positional else None
    tep = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--chi-id=")), None)
    ids = frozenset(open(tep, encoding="utf-8").read().split()) if tep else None
    print(run(model=mdl, dry_run="--dry-run" in sys.argv, chi_moi="--chi-moi" in sys.argv, chi_id=ids))
