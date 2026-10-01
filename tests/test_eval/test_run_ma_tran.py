"""`eval/run_ma_tran.py`: McNemar chính xác + Holm so với số tính tay, dựng lại bảng ma
trận và kiểm định từ một bộ chỉ số nhỏ, nối nhánh truy hồi, chỉ mục bge-m3 từ cache và
bộ câu hai cách hỏi. Không CSDL, không mạng, 0 lượt gọi mô hình."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from eval.run_ma_tran import (
    BGE,
    CAC_O,
    CAU_HINH,
    bao_cao,
    bo_cau_hoi,
    chi_muc_bge,
    holm,
    mcnemar,
    p_hai_phia,
    so_ky_hieu_loi21,
    tong_hop,
    truy_hoi,
)


def test_p_hai_phia_khop_nhi_thuc_tinh_tay():
    assert p_hai_phia(0, 0) == 1.0
    assert p_hai_phia(5, 0) == 2 / 2**5  # 0,0625
    assert p_hai_phia(9, 1) == 2 * (1 + 10) / 2**10  # 2·(C(10,0) + C(10,1))/2¹⁰
    assert p_hai_phia(4, 1) == 2 * (1 + 5) / 2**5  # 0,375
    assert p_hai_phia(3, 3) == 1.0, "p bị chặn trên ở 1"
    assert p_hai_phia(1, 9) == p_hai_phia(9, 1), "hai phía: đối xứng"


def test_mcnemar_dem_cap_lech_theo_gia_tri():
    """Câu hai neo 1 → 0,5 là xấu đi; câu không đổi không vào cặp lệch."""
    assert mcnemar([1, 1, 0, 0.5, 1], [0, 1, 1, 0, 0.5]) == {"xau_di": 3, "tot_len": 1, "p": 2 * (1 + 4) / 2**4}
    with pytest.raises(ValueError):
        mcnemar([1, 0], [1])


def test_holm_khop_so_tinh_tay():
    assert holm([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert holm([]) == []
    assert holm([0.6, 0.6]) == [1.0, 1.0], "nhân m rồi chặn ở 1"


def test_ho_chinh_m8_cua_luot_do_2026_10_01():
    """B (mở kho) và D (đổi cách hỏi) × bốn cấu hình gốc — số xấu/tốt của lượt đo."""
    dem = [(5, 0), (6, 0), (9, 1), (7, 0), (4, 1), (7, 1), (6, 1), (9, 0)]
    got = holm([p_hai_phia(x, t) for x, t in dem])
    assert got == pytest.approx([0.25, 0.15625, 0.12890625, 0.109375, 0.375, 0.25, 0.25, 0.03125])


def _bo_nho():
    """a, b, c trong bộ 74 (a, b người duyệt; a, c có neo tới được ở lõi), d bị loại."""
    items = [
        {"id": "a", "trong_74": True, "duyet_boi": "nguoi", "gold_toi_duoc_loi21": True},
        {"id": "b", "trong_74": True, "duyet_boi": "nguoi", "gold_toi_duoc_loi21": False},
        {"id": "c", "trong_74": True, "duyet_boi": "may", "gold_toi_duoc_loi21": True},
        {"id": "d", "trong_74": False, "duyet_boi": "nguoi", "gold_toi_duoc_loi21": True},
    ]
    gia = {(o, cfg): [1.0, 1.0, 1.0, 1.0] for o in CAC_O for cfg in CAU_HINH}
    gia[("kho-dt", "lexical")] = [0.0, 0.0, 1.0, 1.0]  # D4: xấu đi ở a, b
    gia[("kho-kt", "dense_bge")] = [0.5, 1.0, 0.0, 1.0]  # B2: xấu đi ở a, c; K1: voyage tốt lên ở a, c
    ket = {
        o: {
            cfg: [
                {
                    "id": it["id"],
                    **dict.fromkeys(("recall@5", "recall@10", "mrr@5", "mrr@10", "ndcg@5", "ndcg@10"), v),
                    "retrieved": [],
                }
                for it, v in zip(items, gia[(o, cfg)], strict=True)
            ]
            for cfg in CAU_HINH
        }
        for o in CAC_O
    }
    return items, ket


def test_tong_hop_dung_lai_bang_va_phep_so():
    items, ket = _bo_nho()
    kq = tong_hop(items, ket)
    s = kq["summary"]["kho-dt"]["lexical"]
    assert s["74"] == {k: 0.3333 for k in s["74"] if k != "n"} | {"n": 3}
    assert (s["77"]["recall@5"], s["77"]["n"]) == (0.5, 4)
    assert (s["duyet_boi_nguoi"]["recall@5"], s["duyet_boi_nguoi"]["n"]) == (0.0, 2)
    t = {x["ma"]: x for x in kq["mcnemar"]}
    assert t["D"]["theo_cau_hinh"]["lexical"] == {"xau_di": 2, "tot_len": 0, "p": 0.5, "n": 3}
    assert t["B"]["n"] == 2 and t["B"]["theo_cau_hinh"]["dense_bge"] == {"xau_di": 2, "tot_len": 0, "p": 0.5, "n": 2}
    assert t["B"]["gop"] == {"xau_di": 2, "tot_len": 0, "p": 0.5}
    k1 = next(
        r for r in kq["mcnemar_cau_hinh"] if (r["o"], r["tu"], r["sang"]) == ("kho-kt", "dense_bge", "dense_voyage")
    )
    assert (k1["xau_di"], k1["tot_len"], k1["n"]) == (0, 2, 3)
    assert kq["n_gold_trong_loi21_74"] == 2


def test_tong_hop_mot_phan_khong_co_phep_so():
    items, ket = _bo_nho()
    kq = tong_hop(items, {"kho-dt": {"dense_voyage": ket["kho-dt"]["dense_voyage"]}})
    assert list(kq["summary"]) == ["kho-dt"] and kq["mcnemar"] == [] and kq["mcnemar_cau_hinh"] == []


def test_bao_cao_doc_lai_tu_tep_va_tinh_lai_p_holm():
    items, ket = _bo_nho()
    kq = tong_hop(items, ket)
    txt = bao_cao(json.loads(json.dumps(kq)))
    assert txt == bao_cao(kq), "đọc từ tệp hay từ bộ nhớ phải ra cùng một bảng"
    dong = txt.splitlines()
    assert dong.index("### n=74") < dong.index("### n=77") < dong.index("### n=2 (duyet_boi_nguoi)")
    assert "| kho-dt | lexical | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.3333 | 0.3333 | n=3" in dong
    d4 = next(x for x in dong if x.startswith("| D4 |"))
    assert "| lexical | 2/0 | 0.5 | 1 | 1 |" in d4, "m = 8: 8 × 0,5 chặn ở 1; trong khối m = 4: cũng 1"
    k1 = next(x for x in dong if x.startswith("| K1 |"))
    assert k1.endswith("| dense_bge -> dense_voyage | 0/2 | 0.5 | 1 | 1 |")
    assert sum(x.startswith("| L") for x in dong) == 10
    # p tính lại từ số xấu/tốt, không đọc p đã ghi.
    kq["mcnemar"][0]["theo_cau_hinh"]["dense_voyage"]["p"] = 0.123
    assert bao_cao(kq) == txt


def test_truy_hoi_noi_nhanh_theo_cau_hinh():
    class _R:
        def bm25(self, q, k, hien, bai_bo):
            return [1, 2, 3]

        def dense(self, q, k, hien, bai_bo):
            return [3, 4]

        def provision_ids(self, ids):
            return [i * 10 for i in ids]

    s = SimpleNamespace(retrieve_bm25_topk=20, retrieve_dense_topk=20, rrf_k=60, retrieve_final_topk=2)
    rong = frozenset()
    assert truy_hoi(_R(), s, "lexical", "q", rong, rong, None) == [10, 20]
    assert truy_hoi(_R(), s, "dense_voyage", "q", rong, rong, None) == [30, 40]
    assert truy_hoi(_R(), s, "hybrid_voyage", "q", rong, rong, None) == [30, 10], "3 có ở cả hai nhánh"
    assert truy_hoi(_R(), s, "dense_bge", "q", rong, rong, lambda q: [7, 8]) == [70, 80]
    assert truy_hoi(_R(), s, "hybrid_bge", "q", rong, rong, lambda q: [2]) == [20, 10]


def test_chi_muc_bge_tu_cache_loc_theo_muc_kho(tmp_path):
    doan = [SimpleNamespace(id=i, document_id=d, token_count=1) for i, d in ((11, "x"), (12, "y"), (13, "y"))]
    kho = {"doan": doan, "hien": {"loi21": frozenset({"y"}), "kho": frozenset({"x", "y"})}}
    cache = tmp_path / "bge.npy"
    np.save(cache, np.array([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]], dtype=np.float32))
    cache.with_suffix(".ids.json").write_text(json.dumps([11, 12, 13]))
    bge = chi_muc_bge(None, kho, {BGE: {"q": [3.0, 0.1]}}, 2, cache, False, {})
    assert bge("q", "kho") == [11, 13], "cosin, không phải tích vô hướng thô"
    assert bge("q", "loi21") == [13, 12], "mức lõi chỉ xét đoạn của văn bản lõi"
    cache.with_suffix(".ids.json").write_text(json.dumps([11, 12]))
    with pytest.raises(SystemExit):
        chi_muc_bge(None, kho, {}, 2, cache, False, {})


def test_bo_cau_hoi_hai_cach_hoi():
    items = bo_cau_hoi()
    assert len(items) == 77 and len({i["id"] for i in items}) == 77
    trong = [i for i in items if i["trong_74"]]
    assert len(trong) == 74
    assert sum(i["viet_lai"] for i in items) == 16 and sum(i["viet_lai"] for i in trong) == 15
    assert sum(i["duyet_boi"] == "nguoi" for i in trong) == 55
    for i in items:
        assert (i["cau_hoi_ky_thuat"] != i["cau_hoi_doi_thuong"]) == i["viet_lai"], i["id"]
        assert i["duong_dan"], i["id"]


def test_so_ky_hieu_loi21_doc_tu_corpus_cu_sql():
    s = so_ky_hieu_loi21()
    assert len(s) == len(set(s)) == 21 and "45/2019/QH14" in s and "122/2015/NĐ-CP" in s
