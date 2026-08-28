import math

from eval.metrics import mrr_at_k, ndcg_at_k, recall_at_k


def test_recall_dem_ty_le_relevant_tim_thay_trong_top_k():
    assert recall_at_k([1, 2, 3], {1, 4}, k=3) == 0.5
    assert recall_at_k([1, 2, 3], {1, 2}, k=3) == 1.0
    assert recall_at_k([9, 8, 1], {1}, k=2) == 0.0, "vị trí 3 không nằm trong top 2"


def test_recall_relevant_rong_tra_0_khong_chia_cho_0():
    assert recall_at_k([1, 2], set(), k=2) == 0.0


def test_mrr_lay_nghich_dao_hang_dau_tien_dung():
    assert mrr_at_k([5, 3, 1], {1}, k=3) == 1 / 3
    assert mrr_at_k([1, 3, 5], {1}, k=3) == 1.0
    assert mrr_at_k([5, 3], {1}, k=3) == 0.0
    assert mrr_at_k([9, 9, 5], {5}, k=3) == 1 / 3


def test_ndcg_hoan_hao_bang_1():
    assert abs(ndcg_at_k([1, 2], {1, 2}, k=2) - 1.0) < 1e-9
    assert abs(ndcg_at_k([1], {1}, k=1) - 1.0) < 1e-9


def test_ndcg_dung_log2_theo_vi_tri():
    # 1 relevant ở vị trí 2: DCG = 1/log2(3); IDCG = 1/log2(2) = 1
    got = ndcg_at_k([9, 1], {1}, k=2)
    assert abs(got - 1 / math.log2(3)) < 1e-9

    # cùng công thức, id khác: DCG = 1/log2(3); IDCG bị chặn bởi len(relevant)=1, không phải k=2
    got = ndcg_at_k([2, 1], {1}, k=2)
    assert abs(got - 1 / math.log2(3)) < 1e-9


def test_moi_metric_tra_0_khi_retrieved_rong():
    for f in (recall_at_k, mrr_at_k, ndcg_at_k):
        assert f([], {1}, k=5) == 0.0


def test_moi_metric_tra_0_khi_relevant_rong():
    for f in (recall_at_k, mrr_at_k, ndcg_at_k):
        assert f([1, 2, 3], set(), k=3) == 0.0


def test_k_lon_hon_do_dai_retrieved_khong_loi():
    # chỉ truy hồi được 2 kết quả mà tính @10 -> dùng những gì có, không IndexError
    assert recall_at_k([1, 2], {1, 2}, k=10) == 1.0
    assert mrr_at_k([9, 1], {1}, k=10) == 0.5
    assert abs(ndcg_at_k([9, 1], {1}, k=10) - 1 / math.log2(3)) < 1e-9


def test_id_trung_trong_retrieved_khong_dem_hai_lan():
    # recall: {1,1,4} khử trùng còn {1,4}, chỉ 1 relevant tìm thấy trong 1 relevant tổng
    assert recall_at_k([1, 1, 4], {1}, k=3) == 1.0

    # mrr: hạng đầu tiên khớp là rank 1, id lặp lại sau đó không ảnh hưởng
    assert mrr_at_k([5, 5, 9], {5}, k=3) == 1.0

    # ndcg: id=1 xuất hiện ở rank 1 và rank 2, chỉ tính điểm ở lần gặp đầu (rank 1);
    # rank 3 (id=4) là relevant còn lại, tính bình thường.
    # DCG = 1/log2(2) [id=1, rank1] + 1/log2(4) [id=4, rank3] = 1 + 0.5 = 1.5
    # IDCG bị chặn bởi len(relevant)=2: 1/log2(2) + 1/log2(3) = 1 + 1/log2(3)
    # Nếu đếm id=1 hai lần, DCG sẽ vượt IDCG (ndcg > 1.0) -> sai
    got = ndcg_at_k([1, 1, 4], {1, 4}, k=3)
    expected = 1.5 / (1.0 + 1 / math.log2(3))
    assert abs(got - expected) < 1e-9
