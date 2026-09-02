"""Đo độ phủ từ khoá (rò rỉ) giữa câu hỏi golden_qa và điều luật gold.

TẠI SAO CÓ FILE NÀY: `docs/duyet-golden-qa.md` đã in một con số "độ phủ từ
khoá" cho từng câu nhưng KHÔNG commit cách tính. Thử khôi phục bằng cách khớp
một tập hư từ (greedy trên toàn bộ 77 câu) chỉ hạ được sai số xuống ~4,6
điểm phần trăm/câu với 127 "hư từ" gồm cả từ nội dung ("khoản", "bệnh",
"xe") — tức không tái lập được. Một con số không tái lập được thì không trích
dẫn được trong khóa luận. File này định nghĩa MỘT cách tính, chạy được.

CÁCH TÍNH — không tự chế tokenizer thứ hai:
    do_phu(q) = |L(q) ∩ T(gold)| / |L(q)|
  * L(q)  = lexeme của `to_tsvector('simple', unaccent(loc_hu_tu(q)))`
            — ĐÚNG tập lexeme mà nhánh lexical mang đi truy vấn
            (`src/services/retrieval.py::Retriever.bm25`, mặc định
            `bm25_strip_stopwords=True`).
  * T(gold) = hợp của `chunks.tsv` trên mọi chunk có `provision_id` ∈ gold.
            Gold neo bằng `duong_dan`; id được phân giải ngay lúc chạy bằng
            chính `eval.run.phan_giai_gold` (BIGSERIAL dịch mỗi lần nạp lại).

Vì vậy con số này KHÔNG phải một phép "giống nhau về ngữ nghĩa" chung chung:
nó đúng bằng tỉ lệ từ khoá mà câu hỏi ĐƯA SẴN cho nhánh BM25. Rò rỉ cao =
câu hỏi chép lại từ ngữ điều luật = truy hồi được điểm mà không cần hiểu gì.

Cột `--raw` bỏ bước lọc hư từ (đối chứng, không phải số chính).

Chạy:  .venv/bin/python -m scripts.do_phu_tu_khoa [--raw] [--tsv]
"""

import argparse
import statistics
from pathlib import Path

import yaml
from sqlalchemy import text

from eval.run import phan_giai_gold
from src.config import get_settings
from src.services.db import get_engine
from src.services.retrieval import loc_hu_tu

_LEX_Q = text("SELECT lexeme FROM unnest(to_tsvector('simple', unaccent(:q)))")
_GOLD_Q = text("SELECT DISTINCT lexeme FROM chunks, unnest(tsv) WHERE provision_id = ANY(:ids)")


def do_phu(conn, cau_hoi: str, provision_ids: list[int], loc: bool = True) -> tuple[float, int]:
    """Trả (độ phủ, số lexeme của câu hỏi). Câu hỏi không sinh lexeme → (0.0, 0)."""
    q = loc_hu_tu(cau_hoi) if loc else cau_hoi
    lex = {r[0] for r in conn.execute(_LEX_Q, {"q": q})}
    if not lex:
        return 0.0, 0
    gold = {r[0] for r in conn.execute(_GOLD_Q, {"ids": provision_ids})}
    return len(lex & gold) / len(lex), len(lex)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", action="store_true", help="không lọc hư từ (đối chứng)")
    ap.add_argument("--tsv", action="store_true", help="in TSV thay vì bảng phân bố")
    a = ap.parse_args()

    p = Path(get_settings().eval_dataset_dir) / "golden_qa.yaml"
    items = phan_giai_gold(get_engine(), yaml.safe_load(p.read_text(encoding="utf-8"))["items"])

    out: list[tuple[str, float, int]] = []
    with get_engine().connect() as c:
        for it in items:
            v, n = do_phu(c, it["cau_hoi"], it["provision_ids"], loc=not a.raw)
            out.append((it["id"], v, n))

    if a.tsv:
        for i, v, n in out:
            print(f"{i}\t{v:.4f}\t{n}")
        return

    vals = sorted(v for _, v, _ in out)
    print(f"n={len(vals)}  trung vị={statistics.median(vals):.3f}  "
          f"trung bình={statistics.fmean(vals):.3f}  max={vals[-1]:.3f}  min={vals[0]:.3f}")
    print("phân bố:")
    canh = [(0.9, 1.01), (0.8, 0.9), (0.7, 0.8), (0.6, 0.7), (0.5, 0.6), (0.0, 0.5)]
    for lo, hi in canh:
        n = sum(1 for v in vals if lo <= v < hi)
        print(f"  [{lo:.1f}, {hi:.2f})  {n:2}  {'█' * n}")
    print("cao nhất:")
    for i, v, _ in sorted(out, key=lambda r: -r[1])[:12]:
        print(f"  {i:14} {v:.3f}")


if __name__ == "__main__":
    main()
