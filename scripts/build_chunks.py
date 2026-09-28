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

# Văn bản ĐÃ HẾT HIỆU LỰC theo nguyên văn của một văn bản trong kho, nhưng
# `effectivity` chưa dán được nhãn chết: cạnh chấm dứt nối hai tiêu đề khác chủ
# đề nên guard `cung_chu_de` hạ nó xuống `can_doi_chieu_tay`, mà assemble chỉ
# lọc `bi_thay_the`/`het_hieu_luc` khỏi văn xuôi. Nằm trong chỉ mục là câu trả
# lời lao động được viết từ nghị định 2013-2015 đã bãi bỏ. Provisions vẫn ở DB
# cho tầng 1 kiểm trích dẫn cũ và chỉ ra văn bản thay thế (quyết định
# 2026-09-28 mục 8). Đo 2026-09-28: 17 văn bản, 237 chunk voyage.
# ponytail: bảng tay; bỏ dòng khi `effectivity` có lớp cạnh đọc-từ-nguyên-văn
# (cần chủ dự án duyệt) hoặc quy tắc hiển thị K7 phủ truy hồi.
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
}


def run(model: str | None = None, dry_run: bool = False, chi_moi: bool = False) -> dict:
    """`chi_moi`: chỉ embed chunk (provision_id, noi_dung_embed) CHƯA có cho
    `model` và xoá chunk không còn khớp chunker — kết quả bằng một lần chạy
    đầy đủ, nhưng chunk cũ giữ id và vector (số đo truy hồi trước/sau nạp thêm
    văn bản vẫn so được với nhau)."""
    s = get_settings()
    run_migrations()
    model = model or s.openrouter_embedding_model_name

    provisions = [p for p in load_provisions(get_engine())
                  if p["document_id"] not in KHONG_DANH_CHI_MUC]
    chunks = build_chunks(provisions, s.chunk_max_tokens)
    if not chunks:
        raise ValueError("0 chunk — provisions rỗng hoặc chunker lỗi")

    info = {
        "provisions": len(provisions),
        "chunks": len(chunks),
        "model": model,
        "tokens": sum(c.token_count for c in chunks),
    }
    thua: list[int] = []
    if chi_moi:
        with get_engine().connect() as conn:
            co = {(r[0], r[1]): r[2] for r in conn.execute(text(
                "SELECT provision_id, noi_dung_embed, id FROM chunks WHERE embedding_model = :m"
            ), {"m": model})}
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
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    mdl = positional[0] if positional else None
    print(run(model=mdl, dry_run="--dry-run" in sys.argv, chi_moi="--chi-moi" in sys.argv))
