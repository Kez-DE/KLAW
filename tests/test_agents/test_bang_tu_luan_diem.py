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


def test_du_hai_doi_tuong_nhung_khong_tieu_chi_nao_chung_thi_none():
    """Review round 1, finding 1: hai đối tượng, hai tiêu chí KHÁC NHAU, không
    tiêu chí nào có mặt cả hai đối tượng — mỗi hàng chỉ một ô, không hàng nào
    thực sự SO SÁNH. Một bảng như vậy tệ hơn văn xuôi, phải là None."""
    cap = [
        _r("A", {"doi_tuong": "X", "tieu_chi": "Điều kiện"}, 1),
        _r("B", {"doi_tuong": "Y", "tieu_chi": "Mức hưởng"}, 2),
    ]
    assert dung_bang_tu_luan_diem([c for c, _ in cap], [ct for _, ct in cap]) is None


def test_hang_khong_phai_dict_thi_bo_qua_khong_no_va_o_thieu_la_chuoi_rong():
    """Review round 1, finding 2 + Minor: `hang` truthy nhưng không phải mapping
    (chuỗi) không được làm nổ AttributeError — luận điểm đó bị bỏ qua như thể
    `hang=None`, còn bảng vẫn dựng được từ các luận điểm hợp lệ. Ô thiếu dữ liệu
    (Y không có "Mức hưởng") phải là chuỗi RỖNG, không phải dấu gạch — cùng quy
    ước "không có dữ liệu" của bảng kho, để `BangKetQua` áp đúng một đường hiển
    thị ô trống có khả năng truy cập cho cả hai loại bảng."""
    cap = [
        _r("Đủ điều kiện X", {"doi_tuong": "X", "tieu_chi": "Điều kiện"}, 1),
        _r("Đủ điều kiện Y", {"doi_tuong": "Y", "tieu_chi": "Điều kiện"}, 2),
        _r("Mức hưởng của X", {"doi_tuong": "X", "tieu_chi": "Mức hưởng"}, 3),
        _r("Luận điểm có hang hỏng", "khong-phai-dict", 4),
    ]
    bang = dung_bang_tu_luan_diem([c for c, _ in cap], [ct for _, ct in cap])
    assert bang is not None
    assert bang.cot == ["Tiêu chí", "X", "Y"]
    hang_muc_huong = next(dong for dong in bang.dong if dong[0] == "Mức hưởng")
    assert hang_muc_huong[2] == ""


def test_trung_doi_tuong_va_tieu_chi_thi_ban_sau_ghi_de_ban_truoc():
    """Review round 1, finding 3: quyết định CÓ CHỦ ĐÍCH — hai luận điểm cùng
    (đối tượng, tiêu chí) không có thứ tự nào "đáng tin hơn" để chọn, nên giữ
    bản GẦN NHẤT là hành vi đơn giản nhất còn quyết định được. Ghim bằng test,
    không bỏ ngỏ."""
    cap = [
        _r("Bản đầu", {"doi_tuong": "X", "tieu_chi": "Điều kiện"}, 1),
        _r("Bản sau", {"doi_tuong": "X", "tieu_chi": "Điều kiện"}, 2),
        _r("Y", {"doi_tuong": "Y", "tieu_chi": "Điều kiện"}, 3),
    ]
    bang = dung_bang_tu_luan_diem([c for c, _ in cap], [ct for _, ct in cap])
    o_x = bang.dong[0][1]
    assert "Bản sau" in o_x and "Bản đầu" not in o_x and o_x.endswith("[Điều 2](cite:2)")
