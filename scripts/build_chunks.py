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


def run(model: str | None = None, dry_run: bool = False) -> dict:
    s = get_settings()
    run_migrations()
    model = model or s.openrouter_embedding_model_name

    provisions = load_provisions(get_engine())
    chunks = build_chunks(provisions, s.chunk_max_tokens)
    if not chunks:
        raise ValueError("0 chunk — provisions rỗng hoặc chunker lỗi")

    info = {
        "provisions": len(provisions),
        "chunks": len(chunks),
        "model": model,
        "tokens": sum(c.token_count for c in chunks),
    }
    if dry_run:
        return info

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url, model=model, dim=s.openrouter_embedding_dim
    )
    embedder.batch = _EMBED_BATCH

    print(f"embed {len(chunks)} chunk (~{info['tokens']:,} token) bằng {model} …")
    vectors = embedder.embed([c.noi_dung_embed for c in chunks])
    if len(vectors) != len(chunks):
        raise ValueError(f"{len(vectors)} vector cho {len(chunks)} chunk")

    rows = [
        {"p": c.provision_id, "t": c.noi_dung_embed, "v": str(v), "m": model, "d": embedder.dim, "n": c.token_count}
        for c, v in zip(chunks, vectors, strict=True)
    ]
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM chunks WHERE embedding_model = :m"), {"m": model})
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
    print(run(model=mdl, dry_run="--dry-run" in sys.argv))
