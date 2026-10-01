"""Ma trận truy hồi hai nhân tố trên kho hiện tại: Recall/MRR/nDCG @5 @10 theo cấu hình
× cách hỏi × mức kho, McNemar chính xác hai phía và hiệu chỉnh Holm.

    python -m eval.run_ma_tran [--cache-truy-van Q.json] [--cache-kho BGE.npy] [--tra-phi]
                               [--chi-o O[/CAU_HINH]] [--out PATH]
    python -m eval.run_ma_tran --tu-ket-qua PATH

Bốn ô: mức kho {`loi21`: các văn bản của `eval/corpus_cu.sql` còn được hiện, `kho`: mọi
văn bản được hiện} × cách hỏi {`kt`: kỹ thuật, `dt`: đời thường}. Bộ câu: 74 câu của
`golden_qa.yaml` + 3 câu của `golden_qa.loai-khoi-bo-chinh.yaml`. Giọng kỹ thuật là chữ
cũ của 16 câu đã được viết lại sang lời thường (chữ khác nhau giữa
`eval/results/baseline-moi/cu-cu` và `cu-moi`); các câu khác dùng chữ hiện hành ở cả hai
giọng. Năm cấu hình, tham số lấy từ `eval/configs/hybrid.yaml` (top-k 20 mỗi nhánh, RRF
k = 60, 10 đoạn nhúng đầu quy về điều khoản): dense voyage (cấu hình triển khai), dense
bge-m3, hybrid RRF bge-m3, lexical `ts_rank`, và hybrid RRF voyage (ngoài dòng gộp). Lọc
văn bản ẩn và điều khoản bị bãi bỏ đúng như đường trả lời. Dense voyage và lexical chạy
trong Postgres bằng chính `Retriever`; bge-m3 là k-NN cosin chính xác trong numpy trên
CHÍNH các đoạn nhúng đó, nhúng lại (CSDL chỉ giữ vector voyage cho chỉ mục sống; cột
`chunks.embedding` không có chỉ mục ANN nên `<=>` cũng là k-NN chính xác).

Tốn phí CHỈ khi thiếu cache VÀ có `--tra-phi`: vector truy vấn (93 câu × 2 mô hình) và
chỉ mục bge-m3 của kho (mọi đoạn nhúng được hiện). Có đủ cache thì 0 lượt gọi mô hình;
CSDL chỉ đọc. Cache chỉ mục kho là hai tệp `BGE.npy` + `BGE.ids.json`; lệch tập đoạn
nhúng hiện tại thì dừng. `--chi-o kho-dt/dense_voyage` chạy một ô (một cấu hình), không
cần chỉ mục bge-m3; chạy một phần thì không có kiểm định. Mốc hiệu lực là `AS_OF_DATE`
(mặc định hôm nay) — tập văn bản được hiện và điều khoản bị bãi bỏ phụ thuộc nó.

`--tu-ket-qua` in lại bảng từ `summary` và tính lại p, Holm từ số câu xấu đi / tốt lên
đã ghi — không CSDL, không mạng. Đọc được cả tệp của lượt đo 2026-10-01
(`eval/results/kho-luat/ma-tran-truy-hoi.json`) lẫn tệp `--out` của runner này.

Kiểm định (khai trước): McNemar chính xác trên `recall@5` từng câu, "xấu đi" = ô sau nhỏ
hơn ô trước. Họ chính m = 8: B (mở kho, giọng kỹ thuật, câu có neo tới được ở lõi) và D
(đổi cách hỏi trên toàn kho) × bốn cấu hình gốc; mỗi khối A–D còn có Holm riêng m = 4
(A, C là khối thăm dò). Họ so cấu hình m = 10 (hai ô kho × năm phép so), m = 20 khi gồm
cả hai ô lõi. Dòng gộp chỉ mô tả: hybrid bge-m3 là RRF của dense bge-m3 và lexical nên
bốn cấu hình không độc lập.
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from math import comb
from pathlib import Path

import numpy as np
import yaml
from sqlalchemy import text

from eval.run import _METRIC_FNS, _commit_hash, load_config, overlay_settings, phan_giai_gold
from src.config import as_of_hieu_luc, get_settings
from src.services.db import get_engine
from src.services.embedding import EmbeddingClient
from src.services.hien_thi import dieu_khoan_an, hien_thi_luc
from src.services.retrieval import Retriever, rrf

EVAL = Path(__file__).resolve().parent
VOYAGE, BGE = "voyageai/voyage-4-lite", "baai/bge-m3"
CAC_O = ("loi21-kt", "loi21-dt", "kho-kt", "kho-dt")
# Tên → nhánh, theo thứ tự đưa vào RRF (từ vựng trước, như `eval.run._retrieve`).
CAU_HINH = {
    "dense_voyage": ("dense",),
    "dense_bge": ("bge",),
    "hybrid_bge": ("bm25", "bge"),
    "lexical": ("bm25",),
    "hybrid_voyage": ("bm25", "dense"),
}
GOC = ("dense_voyage", "dense_bge", "hybrid_bge", "lexical")
_MO_HINH = {"dense": VOYAGE, "bge": BGE}
# (mã, nhãn, ô trước, ô sau, tập câu). Nhãn giữ đúng chữ của lượt đo 2026-10-01 để
# `--tu-ket-qua` đọc được tệp của nó.
PHEP_SO = (
    ("B", "mo kho, giong ky thuat (bao cao: cu-cu vs moi-cu)", "loi21-kt", "kho-kt", "gold trong loi21"),
    ("D", "doi cach hoi, kho hien tai (moi-cu vs moi-moi)", "kho-kt", "kho-dt", "74"),
    ("C", "mo kho, giong doi thuong", "loi21-dt", "kho-dt", "gold trong loi21"),
    ("A", "doi cach hoi, loi21 (bao cao: cu-cu vs cu-moi)", "loi21-kt", "loi21-dt", "74"),
)
HO_CHINH = ("B", "D")
# (từ, sang): "xấu / tốt" là của cấu hình `sang` so với `tu`, trên 74 câu.
SO_CAU_HINH = (
    ("dense_bge", "dense_voyage"),
    ("hybrid_voyage", "dense_voyage"),
    ("hybrid_bge", "dense_bge"),
    ("lexical", "dense_voyage"),
    ("lexical", "hybrid_bge"),
)
_SQL_DOAN = (
    "SELECT c.id, c.provision_id, p.document_id, c.token_count FROM chunks c JOIN provisions p ON p.id = c.provision_id"
    " WHERE c.embedding_model = :m AND c.embedding IS NOT NULL AND p.document_id = ANY(:h)"
    " AND NOT (p.id = ANY(:b)) ORDER BY c.id"
)


# ── Thống kê (hàm thuần) ─────────────────────────────────────────────────────


def p_hai_phia(xau: int, tot: int) -> float:
    """McNemar chính xác hai phía trên cặp lệch: p = min(1, 2·Σᵢ₌₀ᵏ C(n,i)/2ⁿ)."""
    n, k = xau + tot, min(xau, tot)
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def mcnemar(a: list[float], b: list[float]) -> dict:
    """`a`, `b`: chỉ số theo cùng thứ tự câu; xấu đi = b < a, tốt lên = b > a."""
    xau = sum(y < x for x, y in zip(a, b, strict=True))
    tot = sum(y > x for x, y in zip(a, b, strict=True))
    return {"xau_di": xau, "tot_len": tot, "p": p_hai_phia(xau, tot)}


def holm(ps: list[float]) -> list[float]:
    """Holm step-down: sắp p tăng dần, p_Holm(i) = max_{j≤i} min(1, (m − j + 1)·p(j))."""
    m, chay, ra = len(ps), 0.0, [0.0] * len(ps)
    for r, i in enumerate(sorted(range(m), key=lambda j: ps[j])):
        chay = max(chay, min(1.0, (m - r) * ps[i]))
        ra[i] = chay
    return ra


def _tb(rows: list[dict]) -> dict:
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in _METRIC_FNS} | {"n": len(rows)}


def tong_hop(items: list[dict], ket: dict[str, dict[str, list[dict]]]) -> dict:
    """Chỉ số từng câu → bảng (bộ 74, cả 77, và các câu trong bộ 74 do người duyệt — 55 ở
    lượt đo 2026-10-01) và các phép so. Phép so chỉ có khi đủ bốn ô × năm cấu hình."""
    tap = {
        "74": {i["id"] for i in items if i["trong_74"]},
        "77": {i["id"] for i in items},
        "duyet_boi_nguoi": {i["id"] for i in items if i["trong_74"] and i.get("duyet_boi") == "nguoi"},
    }
    summary = {
        o: {
            cfg: {nhan: _tb([r for r in rows if r["id"] in ids]) for nhan, ids in tap.items() if ids}
            for cfg, rows in v.items()
        }
        for o, v in ket.items()
    }
    if set(ket) != set(CAC_O) or any(set(v) != set(CAU_HINH) for v in ket.values()):
        return {"summary": summary, "mcnemar": [], "mcnemar_cau_hinh": []}
    r5 = {o: {cfg: {r["id"]: r["recall@5"] for r in rows} for cfg, rows in v.items()} for o, v in ket.items()}
    ids74 = [i["id"] for i in items if i["trong_74"]]
    toi_duoc = [i["id"] for i in items if i["trong_74"] and i["gold_toi_duoc_loi21"]]

    def so(o1: str, o2: str, c1: str, c2: str, sel: list[str]) -> dict:
        return mcnemar([r5[o1][c1][i] for i in sel], [r5[o2][c2][i] for i in sel]) | {"n": len(sel)}

    phep = []
    for ma, nhan, o1, o2, tap_cau in PHEP_SO:
        sel = ids74 if tap_cau == "74" else toi_duoc
        theo = {cfg: so(o1, o2, cfg, cfg, sel) for cfg in GOC}
        xau, tot = sum(r["xau_di"] for r in theo.values()), sum(r["tot_len"] for r in theo.values())
        phep.append(
            {
                "ma": ma,
                "hieu_ung": nhan,
                "tap": tap_cau,
                "n": len(sel),
                "theo_cau_hinh": theo,
                "gop": {"xau_di": xau, "tot_len": tot, "p": p_hai_phia(xau, tot)},
                "ngoai_gop": {"hybrid_voyage": so(o1, o2, "hybrid_voyage", "hybrid_voyage", sel)},
            }
        )
    cau_hinh = [{"o": o, "tu": a, "sang": b, **so(o, o, a, b, ids74)} for o in CAC_O for a, b in SO_CAU_HINH]
    return {"summary": summary, "mcnemar": phep, "mcnemar_cau_hinh": cau_hinh, "n_gold_trong_loi21_74": len(toi_duoc)}


def _g(p: float) -> str:
    return f"{p:.5g}"


def bao_cao(kq: dict) -> str:
    """Bảng và kiểm định từ một tệp kết quả — chỉ đọc `summary`, `mcnemar`,
    `mcnemar_cau_hinh`; p và Holm tính lại từ số câu xấu đi / tốt lên."""
    d = [f"dieu kien: {json.dumps(kq['dieu_kien'], ensure_ascii=False)}"] if "dieu_kien" in kq else []
    sm = kq["summary"]
    mau = next(iter(next(iter(sm.values())).values()))
    for nhan in mau:
        tieu_de = f"### n={nhan}" if nhan.isdigit() else f"### n={mau[nhan]['n']} ({nhan})"
        d += ["", tieu_de, "| o | cau hinh | " + " | ".join(_METRIC_FNS) + " |"]
        for o, v in sm.items():
            for cfg, s in v.items():
                x = s[nhan]
                d.append(f"| {o} | {cfg} | " + " | ".join(f"{x[k]:.4f}" for k in _METRIC_FNS) + f" | n={x['n']}")

    tests = {t["hieu_ung"]: t for t in kq.get("mcnemar") or []}
    phep = [(ma, tests[nhan]) for ma, nhan, *_ in PHEP_SO if nhan in tests]
    if phep:
        p = {
            (ma, cfg): p_hai_phia(t["theo_cau_hinh"][cfg]["xau_di"], t["theo_cau_hinh"][cfg]["tot_len"])
            for ma, t in phep
            for cfg in GOC
        }
        chinh = [k for k in p if k[0] in HO_CHINH]
        h_chinh = dict(zip(chinh, holm([p[k] for k in chinh]), strict=True))
        h_khoi: dict[tuple[str, str], float] = {}
        for ma, _t in phep:
            khoi = [(ma, cfg) for cfg in GOC]
            h_khoi |= dict(zip(khoi, holm([p[k] for k in khoi]), strict=True))
        d += [
            "",
            "### McNemar chinh xac hai phia tren recall@5 (xau di / tot len cua o sau so voi o truoc)",
            f"Holm: ho chinh m={len(chinh)} ({', '.join(HO_CHINH)} x 4 cau hinh goc); trong khoi m=4; "
            "dong gop va hybrid_voyage chi mo ta",
            "| ma | phep so | tap | n | cau hinh | xau/tot | p | p_Holm ho chinh | p_Holm trong khoi |",
        ]
        for ma, t in phep:
            dau = f"{t['hieu_ung']} | {t['tap']} | {t['n']}"
            for j, cfg in enumerate(GOC, 1):
                r = t["theo_cau_hinh"][cfg]
                hc = _g(h_chinh[(ma, cfg)]) if (ma, cfg) in h_chinh else "-"
                d.append(
                    f"| {ma}{j} | {dau} | {cfg} | {r['xau_di']}/{r['tot_len']} | {_g(p[(ma, cfg)])} | {hc} | "
                    f"{_g(h_khoi[(ma, cfg)])} |"
                )
            g = t["gop"]
            d.append(
                f"| {ma}g | {dau} | gop 4 (mo ta) | {g['xau_di']}/{g['tot_len']} | "
                f"{_g(p_hai_phia(g['xau_di'], g['tot_len']))} | - | - |"
            )
            x = t["ngoai_gop"]["hybrid_voyage"]
            d.append(
                f"| {ma}x | {dau} | hybrid_voyage (ngoai gop) | {x['xau_di']}/{x['tot_len']} | "
                f"{_g(p_hai_phia(x['xau_di'], x['tot_len']))} | - | - |"
            )

    so = {(r["o"], r["tu"], r["sang"]): r for r in kq.get("mcnemar_cau_hinh") or []}
    if so:
        # K1…K10: hai ô kho (họ m = 10); L1…L10: hai ô lõi, chỉ vào họ m = 20.
        hang = [
            (f"{tien}{2 * j + k + 1}", (o, a, b))
            for tien, oo in (("K", ("kho-kt", "kho-dt")), ("L", ("loi21-kt", "loi21-dt")))
            for j, (a, b) in enumerate(SO_CAU_HINH)
            for k, o in enumerate(oo)
        ]
        ps = [p_hai_phia(so[k]["xau_di"], so[k]["tot_len"]) for _, k in hang]
        h10 = holm(ps[:10])
        h20 = holm(ps)
        d += [
            "",
            "### So cau hinh, n=74 (xau/tot cua cau hinh sau so voi cau hinh truoc); "
            "Holm m=10 (hai o kho), m=20 (ca bon o)",
            "| ma | o | so | xau/tot | p | p_Holm m=10 | p_Holm m=20 |",
        ]
        for i, (ma, (o, a, b)) in enumerate(hang):
            r = so[(o, a, b)]
            d.append(
                f"| {ma} | {o} | {a} -> {b} | {r['xau_di']}/{r['tot_len']} | {_g(ps[i])} | "
                f"{_g(h10[i]) if i < 10 else '-'} | {_g(h20[i])} |"
            )
    return "\n".join(d)


# ── Bộ câu và kho (chỉ đọc) ──────────────────────────────────────────────────


def so_ky_hieu_loi21() -> list[str]:
    """21 số hiệu của ô "corpus cũ" — đọc từ `eval/corpus_cu.sql`, không chép lại."""
    sql = (EVAL / "corpus_cu.sql").read_text(encoding="utf-8")
    ra = re.findall(r"'([^']+)'", sql.split("WHERE d.so_ky_hieu IN (", 1)[1].split(");", 1)[0])
    if len(ra) != 21:
        raise ValueError(f"corpus_cu.sql: {len(ra)} số hiệu, phải là 21")
    return ra


def bo_cau_hoi() -> list[dict]:
    """77 câu × hai cách hỏi, theo thứ tự của ma trận 2026-08-31. Chỉ đọc tệp."""

    def chu(o: str) -> dict[str, str]:
        f = EVAL / "results" / "baseline-moi" / o / "dense_only-voyageai_voyage-4-lite-77.json"
        return {x["id"]: x["cau_hoi"] for x in json.loads(f.read_text(encoding="utf-8"))["per_item"]}

    cc, cm = chu("cu-cu"), chu("cu-moi")
    ds = EVAL / "datasets"
    hien_hanh = yaml.safe_load((ds / "golden_qa.yaml").read_text(encoding="utf-8"))["items"]
    loai = yaml.safe_load((ds / "golden_qa.loai-khoi-bo-chinh.yaml").read_text(encoding="utf-8"))["items"]
    theo_id = {i["id"]: i for i in hien_hanh + loai}
    if set(theo_id) != set(cc):
        raise ValueError(f"bộ câu lệch ma trận 2026-08-31: {sorted(set(theo_id) ^ set(cc))}")
    ids74 = {i["id"] for i in hien_hanh}
    return [
        {
            "id": i,
            "trong_74": i in ids74,
            "viet_lai": cc[i] != cm[i],
            "cau_hoi_ky_thuat": cc[i] if cc[i] != cm[i] else theo_id[i]["cau_hoi"],
            "cau_hoi_doi_thuong": theo_id[i]["cau_hoi"],
            "duong_dan": theo_id[i]["duong_dan"],
            "duyet_boi": theo_id[i].get("duyet_boi"),
        }
        for i in cc
    ]


def chuan_bi(engine) -> tuple[list[dict], dict, dict]:
    """Neo vàng phân giải về `provisions.id`, tập văn bản được hiện của hai mức kho,
    điều khoản bị bãi bỏ, và các đoạn nhúng voyage được hiện (chỉ mục của bge-m3)."""
    as_of = as_of_hieu_luc(get_settings().as_of_date)
    hien, bai_bo = hien_thi_luc(engine, as_of), dieu_khoan_an(engine, as_of)
    items = phan_giai_gold(engine, bo_cau_hoi())
    with engine.connect() as c:
        c.execute(text("SET TRANSACTION READ ONLY"))
        cu = {
            r[0]
            for r in c.execute(text("SELECT id FROM documents WHERE so_ky_hieu = ANY(:s)"), {"s": so_ky_hieu_loi21()})
        }
        doan = c.execute(text(_SQL_DOAN), {"m": VOYAGE, "h": sorted(hien), "b": sorted(bai_bo)}).all()
    if len(cu) != 21:
        raise ValueError(f"{len(cu)} văn bản khớp 21 số hiệu của corpus_cu.sql")
    loi = frozenset(cu & hien)
    pid_loi = {r.provision_id for r in doan if r.document_id in loi}
    items = [it | {"gold_toi_duoc_loi21": all(p in pid_loi for p in it["provision_ids"])} for it in items]
    kho = {"hien": {"loi21": loi, "kho": hien}, "bai_bo": bai_bo, "doan": doan}
    dieu_kien = {
        "as_of": str(as_of),
        "so_van_ban_hien": len(hien),
        "so_dieu_khoan_bai_bo": len(bai_bo),
        "so_van_ban_loi21_hien": len(loi),
        "so_doan_kho": len(doan),
        "so_doan_loi21": sum(r.document_id in loi for r in doan),
    }
    return items, kho, dieu_kien


# ── Nhúng (TRẢ PHÍ khi thiếu cache) ─────────────────────────────────────────


def _client(model: str, chi_phi: dict[str, float]) -> EmbeddingClient:
    """EmbeddingClient cộng `usage.cost` (USD) OpenRouter trả về vào `chi_phi[model]`."""
    s = get_settings()
    cl = EmbeddingClient(s.openrouter_api_key, s.openrouter_base_url, model, 1024)
    post = cl._post_with_retry

    def dem(payload: dict):
        r = post(payload)
        chi_phi[model] = chi_phi.get(model, 0.0) + float((r.json().get("usage") or {}).get("cost") or 0)
        return r

    cl._post_with_retry = dem
    return cl


def vector_truy_van(
    cau: list[str], models: list[str], cache: Path | None, tra_phi: bool, chi_phi: dict[str, float]
) -> dict[str, dict[str, list[float]]]:
    """`{model: {câu hỏi: vector}}`, đọc từ `cache`; câu thiếu chỉ được nhúng khi `tra_phi`."""
    kq = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.exists() else {}
    them = False
    for m in models:
        thieu = [q for q in cau if q not in kq.get(m, {})]
        if not thieu:
            continue
        if not tra_phi:
            sys.exit(f"thiếu vector truy vấn {m} cho {len(thieu)} câu: thêm --tra-phi để nhúng (TRẢ PHÍ)")
        kq.setdefault(m, {}).update(zip(thieu, _client(m, chi_phi).embed(thieu), strict=True))
        them = True
    if cache and them:
        cache.write_text(json.dumps(kq), encoding="utf-8")
    return kq


def chi_muc_bge(engine, kho: dict, qv: dict, topk: int, cache: Path | None, tra_phi: bool, chi_phi: dict[str, float]):
    """k-NN cosin chính xác của bge-m3 trên các đoạn nhúng được hiện → `bge(q, muc)`."""
    doan = kho["doan"]
    ids = [r.id for r in doan]
    if cache and cache.exists():
        if json.loads(cache.with_suffix(".ids.json").read_text(encoding="utf-8")) != ids:
            sys.exit(f"{cache}: tập đoạn nhúng được hiện đã đổi từ lúc nhúng — bỏ cache, chạy lại với --tra-phi")
        vec = np.load(cache)
    else:
        if not tra_phi:
            sys.exit(
                f"thiếu chỉ mục bge-m3 cho {len(ids)} đoạn (~{sum(r.token_count for r in doan):,} token theo "
                "chunks.token_count): thêm --tra-phi để nhúng (TRẢ PHÍ), --cache-kho để giữ lại"
            )
        with engine.connect() as c:
            c.execute(text("SET TRANSACTION READ ONLY"))
            noi_dung = dict(
                c.execute(text("SELECT id, noi_dung_embed FROM chunks WHERE id = ANY(:i)"), {"i": ids}).all()
            )
        # ponytail: tuần tự, ~550 lượt gọi 32 đoạn; song song hoá nếu thời gian chạy quan trọng.
        vec = np.asarray(_client(BGE, chi_phi).embed([noi_dung[i] for i in ids]), dtype=np.float32)
        if cache:
            np.save(cache, vec)
            cache.with_suffix(".ids.json").write_text(json.dumps(ids), encoding="utf-8")
    vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
    doc = np.array([r.document_id for r in doan])
    mask = {"loi21": np.isin(doc, list(kho["hien"]["loi21"])), "kho": np.ones(len(ids), dtype=bool)}

    def bge(q: str, muc: str) -> list[int]:
        v = np.asarray(qv[BGE][q], dtype=np.float32)
        sim = np.where(mask[muc], vec @ (v / np.linalg.norm(v)), -np.inf)
        return [ids[j] for j in np.argsort(-sim, kind="stable")[:topk]]

    return bge


# ── Truy hồi ────────────────────────────────────────────────────────────────


class _Vector:
    """Đứng thay EmbeddingClient cho `Retriever`: nó chỉ đọc `.model` và gọi `.embed_query`."""

    def __init__(self, model: str, vecs: dict[str, list[float]]) -> None:
        self.model, self.vecs = model, vecs

    def embed_query(self, q: str) -> list[float]:
        return self.vecs[q]


def truy_hoi(r, s, cfg: str, q: str, hien: frozenset[str], bai_bo: frozenset[int], bge) -> list[int]:
    """Một câu, một cấu hình → `provisions.id` đã khử trùng, giữ hạng (tối đa `retrieve_final_topk`)."""
    nhanh = {
        "bm25": lambda: r.bm25(q, s.retrieve_bm25_topk, hien, bai_bo),
        "dense": lambda: r.dense(q, s.retrieve_dense_topk, hien, bai_bo),
        "bge": lambda: bge(q),
    }
    fused = rrf([nhanh[n]() for n in CAU_HINH[cfg]], k=s.rrf_k)
    return r.provision_ids([c for c, _ in fused[: s.retrieve_final_topk]])


def do_o(r, s, items: list[dict], o: str, cfgs: list[str], kho: dict, bge) -> dict[str, list[dict]]:
    muc, cach = o.split("-")
    khoa = "cau_hoi_ky_thuat" if cach == "kt" else "cau_hoi_doi_thuong"
    ra: dict[str, list[dict]] = {}
    for cfg in cfgs:
        rows = []
        for it in items:
            got = truy_hoi(r, s, cfg, it[khoa], kho["hien"][muc], kho["bai_bo"], bge and (lambda q: bge(q, muc)))
            gold = set(it["provision_ids"])
            rows.append({"id": it["id"], **{k: f(got, gold) for k, f in _METRIC_FNS.items()}, "retrieved": got[:10]})
        ra[cfg] = rows
        print(
            f"{o} {cfg} recall@5 (77) {sum(x['recall@5'] for x in rows) / len(rows):.4f}", file=sys.stderr, flush=True
        )
    return ra


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tu-ket-qua", type=Path, help="tệp kết quả: in bảng, tính lại p và Holm (0 lượt gọi, không CSDL)")
    ap.add_argument("--cache-truy-van", type=Path, help="JSON {model: {câu hỏi: vector}}")
    ap.add_argument("--cache-kho", type=Path, help="chỉ mục bge-m3 dạng .npy (kèm .ids.json cùng tên)")
    ap.add_argument("--tra-phi", action="store_true", help="cho phép gọi API nhúng (TRẢ PHÍ) khi thiếu cache")
    ap.add_argument("--chi-o", help="một ô (vd kho-dt) hoặc một ô một cấu hình (vd kho-dt/dense_voyage)")
    ap.add_argument("--out", type=Path, help="ghi kết quả (summary, kiểm định, chỉ số từng câu)")
    a = ap.parse_args()
    if a.tu_ket_qua:
        print(bao_cao(json.loads(a.tu_ket_qua.read_text(encoding="utf-8"))))
        return

    o_chay, cfgs = list(CAC_O), list(CAU_HINH)
    if a.chi_o:
        o1, _, c1 = a.chi_o.partition("/")
        if o1 not in CAC_O or (c1 and c1 not in CAU_HINH):
            ap.error(f"--chi-o: ô trong {CAC_O}, cấu hình trong {tuple(CAU_HINH)}")
        o_chay, cfgs = [o1], ([c1] if c1 else cfgs)

    s = overlay_settings(load_config("hybrid"))
    engine = get_engine()
    items, kho, dieu_kien = chuan_bi(engine)
    chi_phi: dict[str, float] = {}
    can = sorted({_MO_HINH[n] for cfg in cfgs for n in CAU_HINH[cfg] if n in _MO_HINH})
    cau = sorted({it[k] for it in items for k in ("cau_hoi_ky_thuat", "cau_hoi_doi_thuong")})
    qv = vector_truy_van(cau, can, a.cache_truy_van, a.tra_phi, chi_phi)
    bge = chi_muc_bge(engine, kho, qv, s.retrieve_dense_topk, a.cache_kho, a.tra_phi, chi_phi) if BGE in can else None
    r = Retriever(engine, _Vector(VOYAGE, qv.get(VOYAGE, {})), s)
    ket = {o: do_o(r, s, items, o, cfgs, kho, bge) for o in o_chay}

    kq = {
        "dieu_kien": dieu_kien
        | {
            "tham_so": {
                k: getattr(s, k)
                for k in (
                    "retrieve_bm25_topk",
                    "retrieve_dense_topk",
                    "rrf_k",
                    "retrieve_final_topk",
                    "bm25_rank_normalization",
                    "bm25_strip_stopwords",
                )
            },
            "commit_hash": _commit_hash(),
            "ts": datetime.now(UTC).isoformat(),
            "chi_phi_nhung_usd": chi_phi,
        },
        **tong_hop(items, ket),
        "items": [
            {k: it[k] for k in ("id", "trong_74", "viet_lai", "duyet_boi", "gold_toi_duoc_loi21")} for it in items
        ],
        "per_item": ket,
    }
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf-8")
    print(bao_cao(kq))


if __name__ == "__main__":
    main()
