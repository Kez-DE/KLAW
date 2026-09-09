from types import SimpleNamespace

from src.agents.nodes.assemble import dung_bang_tu_luan_diem


def _r(text, hang, k):
    return SimpleNamespace(claim=SimpleNamespace(text=text, hang=hang)), {
        "k": k,
        "duong_dan": f"45/2019/QH14 > Điều {k}",
    }


def test_dung_bang_hai_doi_tuong_ba_tieu_chi():
    cap = [
        _r("Có khi làm đủ 12 tháng", {"doi_tuong": "Trợ cấp thôi việc", "tieu_chi": "Điều kiện"}, 1),
        _r("Có khi mất việc do thay đổi cơ cấu", {"doi_tuong": "Trợ cấp mất việc", "tieu_chi": "Điều kiện"}, 2),
        _r("Nửa tháng lương mỗi năm", {"doi_tuong": "Trợ cấp thôi việc", "tieu_chi": "Mức hưởng"}, 3),
        _r("Một tháng lương mỗi năm, ít nhất hai tháng", {"doi_tuong": "Trợ cấp mất việc", "tieu_chi": "Mức hưởng"}, 4),
        _r("Không có hàng", None, 5),
    ]
    bang = dung_bang_tu_luan_diem([c for c, _ in cap], [ct for _, ct in cap])
    assert bang.cot == ["Tiêu chí", "Trợ cấp thôi việc", "Trợ cấp mất việc"]
    assert bang.dong[0][0] == "Điều kiện" and bang.dong[0][1].endswith("[Điều 1](cite:1)")
    assert bang.dong[1][2].endswith("[Điều 4](cite:4)")
    assert all(len(d) == 3 for d in bang.dong)


def test_khong_du_hai_doi_tuong_thi_none():
    cap = [_r("a", {"doi_tuong": "X", "tieu_chi": "Điều kiện"}, 1), _r("b", None, 2)]
    assert dung_bang_tu_luan_diem([c for c, _ in cap], [ct for _, ct in cap]) is None
