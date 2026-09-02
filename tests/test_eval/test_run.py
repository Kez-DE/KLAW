"""Test eval/run.py — harness một lệnh cho Recall@k/MRR/nDCG trên golden_qa,
và ba preset (hybrid/lexical_only/dense_only) để ablation (Task 9, Plan 2).

Test THUẦN (không DB, không API) kiểm phần logic dễ sai âm thầm nhất:
- overlay không làm bẩn Settings toàn cục (cached, dùng chung mọi nơi).
- ba preset thật sự khác nhau (yêu cầu #1) — không phải chỉ đọc được file.
- _retrieve raise rõ khi cả hai nhánh tắt, và KHÔNG đụng nhánh bị tắt.
- lỗi retrieval hiện rõ trong per_item, không bị đếm âm thầm là Recall=0
  (yêu cầu #3) — đây là bug-class nguy hiểm nhất cho bảng ablation.
- cảnh báo nhánh chết khi một preset trùng y hệt hybrid (yêu cầu #1).
- chọn câu tệ nhất loại trừ câu lỗi, không lẫn lỗi vào Recall=0.

Test integration (DB thật, `lexical_only` — KHÔNG gọi OpenRouter vì dense_topk=0)
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


def test_config_lexical_only_tat_nhanh_dense():
    cfg = load_config("lexical_only")
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
    """lexical_only (dense_topk=0): .dense() không được gọi — nếu gọi, nó sẽ chạm
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
# _nhanh_chet — yêu cầu #1: cảnh báo khi lexical_only/dense_only trùng y hệt hybrid
# ---------------------------------------------------------------------------


def test_canh_bao_nhanh_chet_khi_mot_preset_trung_het_hybrid():
    giong_nhau = dict.fromkeys(_METRIC_KEYS, 0.5)
    results = {
        "hybrid": giong_nhau,
        "lexical_only": dict(giong_nhau),
        "dense_only": {**giong_nhau, "recall@5": 0.1},
    }
    canh_bao = _nhanh_chet(results)
    assert len(canh_bao) == 1
    assert "lexical_only" in canh_bao[0]


def test_khong_canh_bao_khi_ba_preset_khac_nhau():
    results = {
        "hybrid": dict.fromkeys(_METRIC_KEYS, 0.5),
        "lexical_only": dict.fromkeys(_METRIC_KEYS, 0.3),
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
# evaluate — integration, dùng lexical_only để không tốn tiền embedding trong CI
# (dense_topk=0 nên .dense()/EmbeddingClient thật không bao giờ được gọi).
# ---------------------------------------------------------------------------


def _evaluate_hoac_bo_qua(name: str) -> dict:
    from eval.run import evaluate

    if not Path("eval/datasets/golden_qa.yaml").exists():
        pytest.skip("chưa có golden_qa.yaml")
    return evaluate(name)


@pytest.mark.integration
def test_evaluate_tra_ve_du_metric_va_ghi_file():
    r = _evaluate_hoac_bo_qua("lexical_only")
    assert {"recall@5", "mrr@10", "ndcg@10", "n_queries", "config_name"} <= set(r)
    assert 0.0 <= r["recall@5"] <= 1.0
    assert Path(r["result_file"]).exists()


@pytest.mark.integration
def test_evaluate_co_duyet_khop_voi_du_lieu_that():
    """So cờ với DỮ LIỆU, không với một giá trị cố định.

    Bản trước khẳng định `golden_qa_da_review is False` — đúng cho tới
    2026-09-02, khi chủ dự án duyệt xong 77 câu; rồi nó thành một test canh một
    sự thật đã hết hạn. Test này đọc `duyet_boi` từ chính file dataset nên nó
    đúng ở CẢ HAI phía của cái mốc đó, và vẫn đỏ nếu cờ tuột khỏi dữ liệu.
    """
    import yaml

    from eval.run import da_nguoi_duyet

    r = _evaluate_hoac_bo_qua("lexical_only")
    items = yaml.safe_load(Path("eval/datasets/golden_qa.yaml").read_text(encoding="utf-8"))["items"]
    mong_doi = da_nguoi_duyet(items)
    assert r["golden_qa_da_review"] is mong_doi
    # Cảnh báo và cờ phải nói CÙNG một điều — một bên nói đã duyệt mà bên kia
    # vẫn in "chưa" là đúng lỗi bản này đi sửa.
    if mong_doi:
        assert r["canh_bao"] is None
    else:
        assert r["canh_bao"] and "chưa" in r["canh_bao"].lower()


@pytest.mark.integration
def test_evaluate_ghi_commit_hash_de_tai_lap():
    r = _evaluate_hoac_bo_qua("lexical_only")
    assert r["commit_hash"] and r["commit_hash"] != "unknown"


@pytest.mark.integration
def test_evaluate_khong_dem_loi_thanh_recall_0_tren_du_lieu_that():
    """dense_topk=0 nên câu nào cũng chỉ đi qua bm25 — nếu Postgres tsvector ổn
    định như các task trước đã kiểm, không câu nào lỗi thật; n_errors phải là 0
    và n_ok phải cộng đúng với n_queries (không có câu nào bị đếm nhầm)."""
    r = _evaluate_hoac_bo_qua("lexical_only")
    assert r["n_ok"] + r["n_errors"] == r["n_queries"]


# ---------------------------------------------------------------------------
# H3 (review-final-p2) — preset gõ nhầm key phải NỔ, không im lặng dùng mặc định
# ---------------------------------------------------------------------------


def test_load_config_nem_khi_yaml_co_key_khong_khop_field_nao(tmp_path, monkeypatch):
    import eval.run as run_mod

    (tmp_path / "go_nham.yaml").write_text("rrf_K: 5\nretrieve_final_topk: 10\n", encoding="utf-8")
    monkeypatch.setattr(run_mod, "CONFIG_DIR", tmp_path)
    with pytest.raises(ValueError, match="rrf_K"):
        run_mod.load_config("go_nham")


def test_load_config_van_doc_duoc_preset_dung(tmp_path, monkeypatch):
    import eval.run as run_mod

    (tmp_path / "dung.yaml").write_text("rrf_k: 5\n", encoding="utf-8")
    monkeypatch.setattr(run_mod, "CONFIG_DIR", tmp_path)
    assert run_mod.load_config("dung") == {"rrf_k": 5}


def test_overlay_settings_nem_khi_override_go_nham_ten():
    with pytest.raises(ValueError, match="rrf_K"):
        overlay_settings({"rrf_K": 5})


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


# ══ Pha 0c — cờ "người đã duyệt" phải ĐỌC TỪ DỮ LIỆU ═══════════════════════
#
# Trước bản này `summary["golden_qa_da_review"]` là hằng số `False` và câu cảnh
# báo cũng là hằng số. Sau khi chủ dự án duyệt xong 77 câu (2026-09-02,
# `duyet_boi: nguoi`), mọi báo cáo eval vẫn in "CHƯA được người duyệt tay" —
# một câu SAI SỰ THẬT in vào đúng chương đánh giá. Cờ hardcode không bao giờ
# đúng được hai lần.


def _items(*duyet: str) -> list[dict]:
    return [{"id": f"q-{i}", "duyet_boi": d} for i, d in enumerate(duyet)]


def _summary(**ghi_de) -> dict:
    """Summary tối thiểu mà `write_report` đọc được — mọi khoá metric trong
    `_BANG_METRIC_KEYS` cộng n_ok/n_queries, vì hàm dựng bảng đọc chúng bằng
    `r['...']` chứ không `.get()`."""
    goc = {k: 0.5 for k in ("recall@5", "recall@10", "mrr@5", "mrr@10", "ndcg@5", "ndcg@10")}
    return {**goc, "n_ok": 77, "n_queries": 77, "n_errors": 0, **ghi_de}


def test_da_nguoi_duyet_dung_khi_toan_bo_la_nguoi():
    from eval.run import da_nguoi_duyet

    assert da_nguoi_duyet(_items("nguoi", "nguoi", "nguoi")) is True


def test_da_nguoi_duyet_sai_khi_con_mot_cau_chi_agent_duyet():
    """MỘT câu chưa người duyệt là chưa duyệt. Không có 'gần đủ' ở đây: con số
    công bố được hay không là một bit, không phải một tỉ lệ."""
    from eval.run import da_nguoi_duyet

    assert da_nguoi_duyet(_items("nguoi", "agent", "nguoi")) is False


def test_da_nguoi_duyet_sai_khi_thieu_han_truong():
    """Thiếu trường KHÔNG được hiểu là đã duyệt — mặc định an toàn là chưa."""
    from eval.run import da_nguoi_duyet

    assert da_nguoi_duyet([{"id": "q-0"}]) is False
    assert da_nguoi_duyet([]) is False, "tập rỗng không phải 'đã duyệt hết'"


def test_report_giu_canh_bao_khi_chua_nguoi_duyet():
    from eval.run import write_report

    txt = write_report({"hybrid": _summary(golden_qa_da_review=False)})
    assert "CHƯA" in txt


def test_report_bo_canh_bao_khi_da_nguoi_duyet():
    """Cảnh báo phải BIẾN MẤT, không chỉ đổi chữ — nó tồn tại để chặn việc trích
    một con số chưa được người xác nhận, và giữ nó lại sau khi đã xác nhận thì
    lần sau không ai còn tin cảnh báo nào nữa."""
    from eval.run import write_report

    txt = write_report({"hybrid": _summary(golden_qa_da_review=True)})
    assert "CHƯA được người duyệt tay" not in txt
    assert "chưa ai, kể cả chủ dự án" not in txt


def test_report_thieu_co_thi_coi_nhu_chua_duyet():
    """Summary cũ (đã ghi ra file trước bản này) không có khoá đó — đọc lại phải
    ra 'chưa duyệt', không phải 'đã duyệt'."""
    from eval.run import write_report

    assert "CHƯA" in write_report({"hybrid": _summary()})


# ══ Cổng đo lương tối thiểu — MỘT lượt lỗi không được làm mất cả phép đo ═══


def test_chay_luong_co_lap_loi_tung_luot_khong_mat_trang():
    """ĐO ĐƯỢC 2026-09-02: cổng đo mất trắng vì đúng một lượt ăn HTTP 429.

    `eval/run_trap.py` đã học bài này (docstring của nó ghi "HAI lượt chạy 45 câu
    mất trắng vì đúng một câu ăn HTTP 429") nhưng bài học không được áp sang
    `run_luong_toi_thieu.py` — vòng `for` ở đó không có try/except, nên một 429
    giết cả 10 lượt và không ghi ra file nào. Cổng đo biến mất đúng lúc cần nó.

    Lỗi hạ tầng phải ghi RIÊNG, không cộng vào `abstain`: một lượt crash không
    phải một lượt hệ thống chọn im lặng, và gộp chúng làm con số abstain — đóng
    góp trung tâm của khoá luận — trông tệ hơn sự thật.
    """
    import asyncio

    import eval.run_luong_toi_thieu as m

    goi = {"n": 0}

    class GraphGiaLap:
        async def ainvoke(self, _):
            goi["n"] += 1
            if goi["n"] == 2:  # đúng một lượt giữa chừng nổ
                raise RuntimeError("429 giả lập")
            return {"result_type": "abstain", "citations": [], "answer": None, "warnings": []}

    goc = m.build_graph_tra_cuu
    m.build_graph_tra_cuu = lambda: GraphGiaLap()
    try:
        kq = asyncio.run(m.chay(3))
    finally:
        m.build_graph_tra_cuu = goc

    t = kq["tong_hop"]
    assert t["n"] == 3, "phải ghi lại số lượt ĐÃ ĐỊNH chạy"
    assert t["n_do_duoc"] == 2, "hai lượt chạy được phải còn nguyên, không mất trắng"
    assert t["n_loi"] == 1
    # Lượt crash KHÔNG được đếm thành abstain.
    assert t["abstain"] == 2, f"lượt lỗi bị cộng vào abstain: {t}"
    assert kq["loi"][0]["error_type"] == "RuntimeError"
