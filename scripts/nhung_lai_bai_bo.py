"""Nhúng lại ĐÚNG các chunk còn mang chữ điều khoản bị bãi bỏ (quyết định 2026-09-30 mục 9(e)).

    python -m scripts.nhung_lai_bai_bo        # dry-run (mặc định, hay --dry-run): 0 ghi, 0 gọi API
    python -m scripts.nhung_lai_bai_bo --ghi  # nhúng lại các chunk đó, UPDATE tại chỗ (giữ id)

Chunk neo ở một điều khoản còn hiệu lực gom cả chữ của khoản/điểm con; con bị bãi bỏ thì chữ đó
vẫn góp vào điểm BM25/dense của neo cha. `chunker.build_chunks(…, an)` bỏ chữ đó; script này
dựng lại chunk hai lần (có/không `an`), chỉ nhúng lại chunk đổi chữ, và báo số chunk, token,
US$ ước tính trước khi trả tiền.

Tập bị ẩn đọc từ SEED `data/seed/bai_bo_dieu_khoan.yaml` (cùng luật `effectivity._SQL_BAI_BO` +
`bai_bo_tai`), nên dry-run thấy cả dòng seed chưa nạp. `--ghi` chỉ chạy khi bảng
`bai_bo_dieu_khoan` đã khớp seed (`hien_thi.dieu_khoan_an`): không thì chunk mất chữ của điều
khoản app còn hiện. Chạy lại sau khi xong là không làm gì (chunk đã mang chữ mới).
"""

import sys
from datetime import date

from sqlalchemy import text

from scripts.build_chunks import _EMBED_BATCH, KHONG_DANH_CHI_MUC
from scripts.compare_embeddings import CANDIDATES
from scripts.nap_bai_bo_dieu_khoan import doc_seed
from src.config import as_of_hieu_luc, get_settings
from src.services.chunker import ChunkRow, build_chunks, load_provisions
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.hien_thi import dieu_khoan_an


def an_tu_seed(provisions: list[dict], hang: list[dict], as_of: date) -> frozenset[int]:
    """Điều khoản của dòng seed đã tới ngày tại `as_of`, cùng mọi hậu duệ trong cùng văn bản
    (`duong_dan` = nó + " > …") — đúng tập `dieu_khoan_an` trả khi bảng khớp seed."""
    goc = {(h["van_ban_id"], x) for h in hang if h["tu_ngay"] <= as_of for x in h["dieu_khoan"]}
    ra = set()
    for p in provisions:
        cap = p["duong_dan"].partition(" > ")[2].split(" > ")
        if any((p["document_id"], " > ".join(cap[:k])) in goc for k in range(1, len(cap) + 1)):
            ra.add(p["id"])
    return frozenset(ra)


def chunk_doi(provisions: list[dict], max_tokens: int, an: frozenset[int]) -> list[tuple[ChunkRow, ChunkRow]]:
    """(chunk dựng không biết bãi bỏ, chunk dựng lại không kèm chữ bị bãi bỏ) — chỉ chunk đổi chữ."""
    cu = build_chunks(provisions, max_tokens)
    moi = {c.provision_id: c for c in build_chunks(provisions, max_tokens, an)}
    if set(moi) != {c.provision_id for c in cu}:
        raise ValueError("neo chunk đổi khi bỏ chữ bị bãi bỏ — chunker phải giữ neo (`build_chunks` docstring)")
    return [(c, moi[c.provision_id]) for c in cu if moi[c.provision_id] != c]


def run(ghi: bool = False) -> dict:
    s = get_settings()
    e = get_engine()
    as_of = as_of_hieu_luc(None)
    model = s.openrouter_embedding_model_name
    provisions = [p for p in load_provisions(e) if p["document_id"] not in KHONG_DANH_CHI_MUC]
    an = an_tu_seed(provisions, doc_seed(), as_of)
    ids = {p["id"] for p in provisions}
    khop_bang = {i for i in dieu_khoan_an(e, as_of) if i in ids} == an
    with e.connect() as c:
        co = {
            (p, t): i
            for i, p, t in c.execute(
                text("SELECT id, provision_id, noi_dung_embed FROM chunks WHERE embedding_model = :m"), {"m": model}
            )
        }
    viec, xong, lech = [], 0, []
    for cu, moi in chunk_doi(provisions, s.chunk_max_tokens, an):
        if (i := co.get((cu.provision_id, cu.noi_dung_embed))) is not None:
            viec.append((i, cu, moi))
        elif (moi.provision_id, moi.noi_dung_embed) in co:
            xong += 1
        else:
            lech.append(cu.provision_id)
    token = sum(m.token_count for _, _, m in viec)
    gia = dict(CANDIDATES).get(model)  # US$/1M token, catalog OpenRouter
    info = {
        "model": model,
        "as_of": as_of,
        "an": len(an),
        "khop_bang": khop_bang,
        "viec": viec,
        "da_xong": xong,
        "lech": lech,
        "token": token,  # `dem_token` (từ × 1,3), cùng ước lượng `build_chunks` in ra
        "usd": gia and token * gia / 1e6,
        # Trần tuyệt đối: tokenizer không sinh nhiều token hơn số byte UTF-8.
        "usd_tran": gia and sum(len(m.noi_dung_embed.encode()) for _, _, m in viec) * gia / 1e6,
    }
    if not ghi:
        return info
    if lech:
        raise ValueError(
            f"{len(lech)} chunk trong DB lệch chunker (neo {lech[:10]}) — xem `build_chunks --chi-moi --dry-run`"
        )
    if not khop_bang:
        raise ValueError("bảng bai_bo_dieu_khoan lệch seed — nạp trước: python -m scripts.nap_bai_bo_dieu_khoan --ghi")
    if not viec:
        return info

    embedder = EmbeddingClient(
        api_key=s.openrouter_api_key, base_url=s.openrouter_base_url, model=model, dim=s.openrouter_embedding_dim
    )
    embedder.batch = _EMBED_BATCH
    vectors = embedder.embed([m.noi_dung_embed for _, _, m in viec])
    if len(vectors) != len(viec):
        raise ValueError(f"{len(vectors)} vector cho {len(viec)} chunk")
    with e.begin() as c:
        for (i, cu, moi), v in zip(viec, vectors, strict=True):
            r = c.execute(
                text(
                    "UPDATE chunks SET noi_dung_embed = :t, embedding = CAST(:v AS vector), token_count = :n"
                    " WHERE id = :i AND noi_dung_embed = :cu"
                ),
                {"i": i, "t": moi.noi_dung_embed, "v": str(v), "n": moi.token_count, "cu": cu.noi_dung_embed},
            )
            if r.rowcount != 1:
                raise ValueError(f"chunk {i} đổi giữa lúc đọc và lúc ghi — không ghi gì")
    return info


if __name__ == "__main__":
    ghi = "--ghi" in sys.argv
    info = run(ghi=ghi)
    for i, cu, moi in info["viec"]:
        print(f"  chunk {i:>7}  {moi.noi_dung_embed.split(chr(10), 1)[0]}  token {cu.token_count} → {moi.token_count}")
    print(
        {k: v for k, v in info.items() if k != "viec"} | {"chunk": len(info["viec"])},
        "" if ghi else "DRY-RUN — 0 ghi, 0 gọi API",
    )
