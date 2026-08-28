"""Test scripts/compare_embeddings.py — Task 10 (Plan 2): bảng so sánh model
embedding trên golden_qa, ràng buộc bởi chunks.embedding vector(1024) cố định.

Test THUẦN (không DB, không API — mọi I/O monkeypatch) kiểm bốn nhánh dễ sai âm thầm:
- model chiều != 1024 bị bỏ qua CÓ BÁO CÁO, không tự truncate/pad, không dừng cả sweep.
- model đã có sẵn trong DB (chunks.embedding_model đã có dữ liệu) thì KHÔNG embed lại —
  đây là trần chi phí (yêu cầu #10 của Task 10: bge-m3 đã có sẵn, đừng embed lại).
- vượt trần MAX_MODELS thì bỏ qua có báo cáo, không lặng lẽ chạy tiếp và tốn tiền.
- lỗi build/evaluate giữa chừng hiện rõ trong hàng đó (không swallow), các model
  khác trong sweep vẫn chạy tiếp.

Test integration (gọi OpenRouter thật, KHÔNG chạm DB) kiểm probe_dim() — cơ chế PHÁT
HIỆN chiều thật của model trước khi embed cả corpus, không phải tin theo mô tả catalog.
"""

import pytest

from scripts import compare_embeddings as ce


def test_kiem_tra_chieu_khop_thi_khong_bao_loi():
    assert ce._kiem_tra_chieu(1024) is None


def test_kiem_tra_chieu_khac_1024_bi_bao_ro():
    msg = ce._kiem_tra_chieu(1536)
    assert msg is not None
    assert "1536" in msg
    assert "1024" in msg


def test_model_chieu_sai_bi_bo_qua_khong_lam_dung_sweep(monkeypatch):
    monkeypatch.setattr(ce, "CANDIDATES", [("m-sai", 0.02), ("m-dung", 0.01)])
    monkeypatch.setattr(ce, "probe_dim", lambda m: 1536 if m == "m-sai" else 1024)
    monkeypatch.setattr(ce, "_da_co_trong_db", lambda engine, m: {"chunks": 10, "tokens": 100})
    monkeypatch.setattr(ce, "_dat_model_hien_hanh", lambda m: None)
    monkeypatch.setattr(
        ce,
        "evaluate",
        lambda name: {"recall@5": 0.5, "mrr@5": 0.4, "ndcg@5": 0.3, "commit_hash": "abc", "n_ok": 1, "n_queries": 1},
    )
    monkeypatch.setattr(ce, "get_engine", lambda: None)

    rows = ce.compare()

    assert rows[0]["model"] == "m-sai"
    assert rows[0]["dim"] == 1536
    assert rows[0]["bo_qua"].startswith("không so được")
    assert "recall@5" in rows[1]


def test_model_da_co_san_khong_goi_build_lai(monkeypatch):
    goi_build: list[dict] = []
    monkeypatch.setattr(ce, "CANDIDATES", [("m1", 0.01)])
    monkeypatch.setattr(ce, "probe_dim", lambda m: 1024)
    monkeypatch.setattr(ce, "_da_co_trong_db", lambda engine, m: {"chunks": 5, "tokens": 50})
    monkeypatch.setattr(ce, "_dat_model_hien_hanh", lambda m: None)
    monkeypatch.setattr(ce, "build", lambda **kw: goi_build.append(kw) or {"chunks": 999, "tokens": 999})
    monkeypatch.setattr(
        ce,
        "evaluate",
        lambda name: {"recall@5": 1.0, "mrr@5": 1.0, "ndcg@5": 1.0, "commit_hash": "abc", "n_ok": 1, "n_queries": 1},
    )
    monkeypatch.setattr(ce, "get_engine", lambda: None)

    rows = ce.compare()

    assert goi_build == [], "model đã có trong DB không được embed lại"
    assert rows[0]["chi_phi"] == 0.0
    assert rows[0]["chunks"] == 5  # từ _da_co_trong_db, không phải build()


def test_vuot_tran_max_models_bi_bo_qua(monkeypatch):
    monkeypatch.setattr(ce, "CANDIDATES", [("m1", 0.01), ("m2", 0.01), ("m3", 0.01), ("m4", 0.01)])
    monkeypatch.setattr(ce, "probe_dim", lambda m: 1024)
    monkeypatch.setattr(ce, "_da_co_trong_db", lambda engine, m: {"chunks": 1, "tokens": 1})
    monkeypatch.setattr(ce, "_dat_model_hien_hanh", lambda m: None)
    monkeypatch.setattr(
        ce,
        "evaluate",
        lambda name: {"recall@5": 0.1, "mrr@5": 0.1, "ndcg@5": 0.1, "commit_hash": "abc", "n_ok": 1, "n_queries": 1},
    )
    monkeypatch.setattr(ce, "get_engine", lambda: None)

    rows = ce.compare(max_models=2)

    assert sum("recall@5" in r for r in rows) == 2
    bo_qua = [r for r in rows if "bo_qua" in r]
    assert any("trần" in r["bo_qua"] for r in bo_qua)


def test_loi_build_giua_chung_khong_lam_dung_ca_sweep(monkeypatch):
    monkeypatch.setattr(ce, "CANDIDATES", [("m-loi", 0.01), ("m-ok", 0.01)])
    monkeypatch.setattr(ce, "probe_dim", lambda m: 1024)
    monkeypatch.setattr(ce, "_da_co_trong_db", lambda engine, m: None)
    monkeypatch.setattr(ce, "_dat_model_hien_hanh", lambda m: None)

    def _build(model, dry_run=False):
        if model == "m-loi":
            raise RuntimeError("API sập")
        return {"chunks": 10, "tokens": 100}

    monkeypatch.setattr(ce, "build", _build)
    monkeypatch.setattr(
        ce,
        "evaluate",
        lambda name: {"recall@5": 0.9, "mrr@5": 0.9, "ndcg@5": 0.9, "commit_hash": "abc", "n_ok": 1, "n_queries": 1},
    )
    monkeypatch.setattr(ce, "get_engine", lambda: None)

    rows = ce.compare()

    assert rows[0]["model"] == "m-loi"
    assert rows[0]["loi"] == "API sập"
    assert rows[1]["recall@5"] == 0.9


def test_dry_run_khong_goi_evaluate(monkeypatch):
    goi_evaluate: list[str] = []
    monkeypatch.setattr(ce, "CANDIDATES", [("m1", 0.01)])
    monkeypatch.setattr(ce, "probe_dim", lambda m: 1024)
    monkeypatch.setattr(ce, "_da_co_trong_db", lambda engine, m: None)
    monkeypatch.setattr(ce, "_dat_model_hien_hanh", lambda m: None)
    monkeypatch.setattr(ce, "build", lambda model, dry_run=False: {"chunks": 10, "tokens": 100})
    monkeypatch.setattr(ce, "evaluate", lambda name: goi_evaluate.append(name) or {})
    monkeypatch.setattr(ce, "get_engine", lambda: None)

    rows = ce.compare(dry_run=True)

    assert goi_evaluate == [], "dry-run không được gọi evaluate() (tốn tiền query embedding)"
    assert "recall@5" not in rows[0]
    assert rows[0]["chunks"] == 10


def test_render_markdown_co_canh_bao_chua_duyet_va_bang():
    rows = [
        {
            "model": "m1",
            "dim": 1024,
            "$/1M": 0.01,
            "chunks": 10,
            "tokens": 100,
            "chi_phi": 0.001,
            "ghi_chu": "đã có sẵn",
            "recall@5": 0.5,
            "mrr@5": 0.4,
            "ndcg@5": 0.3,
            "commit_hash": "abc123",
            "n_ok": 77,
            "n_queries": 77,
        }
    ]
    md = ce.render_markdown(rows)

    assert "da_review" in md or "duyệt tay" in md
    assert "m1" in md
    assert "0.5" in md
    assert "abc123" in md


def test_render_markdown_hien_model_bo_qua_va_loi():
    rows = [
        {"model": "m-sai-chieu", "dim": 1536, "bo_qua": "không so được vì chiều 1536 ≠ 1024"},
        {"model": "m-loi", "dim": 1024, "loi": "boom"},
    ]
    md = ce.render_markdown(rows)

    assert "BỎ QUA" in md
    assert "1536" in md
    assert "LỖI" in md
    assert "boom" in md


@pytest.mark.integration
def test_probe_dim_that_tra_dung_chieu_bge_m3():
    assert ce.probe_dim("baai/bge-m3") == 1024
