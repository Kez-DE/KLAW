"""Test eval/run.py — harness một lệnh cho Recall@k/MRR/nDCG trên golden_qa,
và ba preset (hybrid/bm25_only/dense_only) để ablation (Task 9, Plan 2).

Test THUẦN (không DB, không API) kiểm phần logic dễ sai âm thầm nhất:
- overlay không làm bẩn Settings toàn cục (cached, dùng chung mọi nơi).
- ba preset thật sự khác nhau (yêu cầu #1) — không phải chỉ đọc được file.
- _retrieve raise rõ khi cả hai nhánh tắt, và KHÔNG đụng nhánh bị tắt.
- lỗi retrieval hiện rõ trong per_item, không bị đếm âm thầm là Recall=0
  (yêu cầu #3) — đây là bug-class nguy hiểm nhất cho bảng ablation.
- cảnh báo nhánh chết khi một preset trùng y hệt hybrid (yêu cầu #1).
- chọn câu tệ nhất loại trừ câu lỗi, không lẫn lỗi vào Recall=0.

Test integration (DB thật, `bm25_only` — KHÔNG gọi OpenRouter vì dense_topk=0)
kiểm đường ống evaluate() đầu-cuối: ghi file, đủ khoá, có cảnh báo chưa duyệt,
có commit_hash — mà không tốn tiền embedding. Số gọi API thật để đo bảng ablation
thật nằm ở lần chạy `python -m eval.run --config all` riêng, không lặp trong CI.
"""

from pathlib import Path

import pytest

from eval.run import (
    _cau_hoi_te_nhat,
    _nhanh_chet,
    _retrieve,
    _run_items,
    load_config,
    overlay_settings,
)
from src.services.retrieval import Retriever

_METRIC_KEYS = ("recall@5", "recall@10", "mrr@5", "mrr@10", "ndcg@5", "ndcg@10")


def test_config_bm25_only_tat_nhanh_dense():
    cfg = load_config("bm25_only")
    assert cfg["retrieve_dense_topk"] == 0


def test_config_dense_only_tat_nhanh_bm25():
    cfg = load_config("dense_only")
    assert cfg["retrieve_bm25_topk"] == 0


def test_config_hybrid_bat_ca_hai_nhanh():
    cfg = load_config("hybrid")
    assert cfg["retrieve_bm25_topk"] > 0
    assert cfg["retrieve_dense_topk"] > 0


def test_config_khong_ton_tai_nem_ro_rang():
    with pytest.raises(FileNotFoundError, match="khong-co-that"):
        load_config("khong-co-that")


def test_overlay_khong_sua_settings_goc():
    from src.config import get_settings

    goc = get_settings().retrieve_bm25_topk
    s2 = overlay_settings({"retrieve_bm25_topk": 999})
    assert s2.retrieve_bm25_topk == 999
    assert get_settings().retrieve_bm25_topk == goc, "overlay làm bẩn settings toàn cục"


# ---------------------------------------------------------------------------
# _retrieve — hàm thuần, engine=None hợp lệ khi raise xảy ra TRƯỚC khi chạm DB
# ---------------------------------------------------------------------------


def test_retrieve_raise_ro_rang_khi_ca_hai_nhanh_tat():
    s = overlay_settings({"retrieve_bm25_topk": 0, "retrieve_dense_topk": 0})
    r = Retriever(engine=None, embedder=None, settings=s)
    with pytest.raises(ValueError, match="tắt"):
        _retrieve(r, "q", s)


def test_retrieve_khong_dung_nhanh_bi_tat_bang_topk_0():
    """bm25_only (dense_topk=0): .dense() không được gọi — nếu gọi, nó sẽ chạm
    EmbeddingClient thật (embedder=None ở đây) và nổ AttributeError, khác hẳn
    exception mong đợi; test này chặn hồi quy nếu ai đó sau này bỏ guard topk>0."""
    s = overlay_settings({"retrieve_bm25_topk": 20, "retrieve_dense_topk": 0})
    r = Retriever(engine=None, embedder=None, settings=s)
    r.bm25 = lambda q, topk=None: [3, 1, 2]
    r.provision_ids = lambda chunk_ids: chunk_ids  # bỏ qua DB thật, không phải điểm cần test ở đây

    def _dense_khong_duoc_goi(q, topk=None):
        raise AssertionError("dense() không được gọi khi retrieve_dense_topk=0")

    r.dense = _dense_khong_duoc_goi
    assert _retrieve(r, "q", s) == [3, 1, 2]


# ---------------------------------------------------------------------------
# _run_items — yêu cầu #3: lỗi retrieval phải HIỆN RÕ, không lẫn vào Recall=0
# ---------------------------------------------------------------------------


def test_loi_retrieval_hien_ro_khong_bi_dem_am_tham_la_recall_0():
    s = overlay_settings({"retrieve_bm25_topk": 20, "retrieve_dense_topk": 0})
    r = Retriever(engine=None, embedder=None, settings=s)

    def _bm25_loi(q, topk=None):
        raise RuntimeError("DB down")

    r.bm25 = _bm25_loi
    items = [{"id": "x", "cau_hoi": "q", "provision_ids": [1], "duong_dan": ["a"]}]
    per_item, n_ok = _run_items(r, items, s)
    assert n_ok == 0
    assert per_item[0]["error_type"] == "RuntimeError"
    assert per_item[0]["error"] == "DB down"
    assert "recall@5" not in per_item[0], "lỗi không được lẫn vào như một điểm số recall"


def test_run_items_tinh_dung_metric_khi_thanh_cong():
    s = overlay_settings({"retrieve_bm25_topk": 20, "retrieve_dense_topk": 0})
    r = Retriever(engine=None, embedder=None, settings=s)
    r.bm25 = lambda q, topk=None: [1, 2, 3]
    r.provision_ids = lambda chunk_ids: chunk_ids
    items = [{"id": "x", "cau_hoi": "q", "provision_ids": [1], "duong_dan": ["a"]}]
    per_item, n_ok = _run_items(r, items, s)
    assert n_ok == 1
    assert per_item[0]["recall@5"] == 1.0
    assert per_item[0]["mrr@5"] == 1.0
    assert "error" not in per_item[0]


def test_run_items_mot_cau_loi_khong_lam_hong_cau_con_lai():
    s = overlay_settings({"retrieve_bm25_topk": 20, "retrieve_dense_topk": 0})
    r = Retriever(engine=None, embedder=None, settings=s)
    r.provision_ids = lambda chunk_ids: chunk_ids

    def _bm25(q, topk=None):
        if q == "loi":
            raise RuntimeError("boom")
        return [1]

    r.bm25 = _bm25
    items = [
        {"id": "a", "cau_hoi": "loi", "provision_ids": [9], "duong_dan": ["x"]},
        {"id": "b", "cau_hoi": "ok", "provision_ids": [1], "duong_dan": ["y"]},
    ]
    per_item, n_ok = _run_items(r, items, s)
    assert n_ok == 1
    assert "error" in per_item[0] and per_item[0]["id"] == "a"
    assert per_item[1]["recall@5"] == 1.0


# ---------------------------------------------------------------------------
# _nhanh_chet — yêu cầu #1: cảnh báo khi bm25_only/dense_only trùng y hệt hybrid
# ---------------------------------------------------------------------------


def test_canh_bao_nhanh_chet_khi_mot_preset_trung_het_hybrid():
    giong_nhau = dict.fromkeys(_METRIC_KEYS, 0.5)
    results = {
        "hybrid": giong_nhau,
        "bm25_only": dict(giong_nhau),
        "dense_only": {**giong_nhau, "recall@5": 0.1},
    }
    canh_bao = _nhanh_chet(results)
    assert len(canh_bao) == 1
    assert "bm25_only" in canh_bao[0]


def test_khong_canh_bao_khi_ba_preset_khac_nhau():
    results = {
        "hybrid": dict.fromkeys(_METRIC_KEYS, 0.5),
        "bm25_only": dict.fromkeys(_METRIC_KEYS, 0.3),
        "dense_only": dict.fromkeys(_METRIC_KEYS, 0.2),
    }
    assert _nhanh_chet(results) == []


# ---------------------------------------------------------------------------
# _cau_hoi_te_nhat — chọn worst-N cho report.md, loại câu lỗi (đã báo riêng)
# ---------------------------------------------------------------------------


def test_cau_hoi_te_nhat_loai_loi_va_sap_tang_dan():
    items = [
        {"id": "a", "recall@5": 1.0, "mrr@5": 1.0},
        {"id": "b", "recall@5": 0.0, "mrr@5": 0.0},
        {"id": "c", "error": "boom"},
        {"id": "d", "recall@5": 0.5, "mrr@5": 0.5},
    ]
    out = _cau_hoi_te_nhat(items, n=2)
    assert [it["id"] for it in out] == ["b", "d"]


# ---------------------------------------------------------------------------
# evaluate — integration, dùng bm25_only để không tốn tiền embedding trong CI
# (dense_topk=0 nên .dense()/EmbeddingClient thật không bao giờ được gọi).
# ---------------------------------------------------------------------------


def _evaluate_hoac_bo_qua(name: str) -> dict:
    from eval.run import evaluate

    if not Path("eval/datasets/golden_qa.yaml").exists():
        pytest.skip("chưa có golden_qa.yaml")
    return evaluate(name)


@pytest.mark.integration
def test_evaluate_tra_ve_du_metric_va_ghi_file():
    r = _evaluate_hoac_bo_qua("bm25_only")
    assert {"recall@5", "mrr@10", "ndcg@10", "n_queries", "config_name"} <= set(r)
    assert 0.0 <= r["recall@5"] <= 1.0
    assert Path(r["result_file"]).exists()


@pytest.mark.integration
def test_evaluate_canh_bao_golden_qa_chua_duoc_duyet():
    r = _evaluate_hoac_bo_qua("bm25_only")
    assert r["golden_qa_da_review"] is False
    assert "chưa" in r["canh_bao"].lower()


@pytest.mark.integration
def test_evaluate_ghi_commit_hash_de_tai_lap():
    r = _evaluate_hoac_bo_qua("bm25_only")
    assert r["commit_hash"] and r["commit_hash"] != "unknown"


@pytest.mark.integration
def test_evaluate_khong_dem_loi_thanh_recall_0_tren_du_lieu_that():
    """dense_topk=0 nên câu nào cũng chỉ đi qua bm25 — nếu Postgres tsvector ổn
    định như các task trước đã kiểm, không câu nào lỗi thật; n_errors phải là 0
    và n_ok phải cộng đúng với n_queries (không có câu nào bị đếm nhầm)."""
    r = _evaluate_hoac_bo_qua("bm25_only")
    assert r["n_ok"] + r["n_errors"] == r["n_queries"]


# ---------------------------------------------------------------------------
# H2 (review-final-p2) — tên file kết quả phải mang model, nếu không lần chạy
# model thứ hai GHI ĐÈ per_item của model thứ nhất (đã thực sự xảy ra)
# ---------------------------------------------------------------------------


def test_ten_file_ket_qua_khac_nhau_giua_hai_model():
    from eval.run import _ten_file_ket_qua

    a = _ten_file_ket_qua("dense_only", "baai/bge-m3", 77)
    b = _ten_file_ket_qua("dense_only", "voyageai/voyage-4-lite", 77)
    assert a != b, "hai model cùng preset không được ghi chung một file"


def test_ten_file_ket_qua_an_toan_cho_ten_file():
    from eval.run import _ten_file_ket_qua

    ten = _ten_file_ket_qua("dense_only", "voyageai/voyage-4-lite", 77)
    assert ten == "dense_only-voyageai_voyage-4-lite-77.json"
    assert "/" not in ten
