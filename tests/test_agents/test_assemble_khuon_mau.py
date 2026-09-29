"""Lời đáp 0 token cho bản thảo trên khuôn mẫu — thiết kế `khuon-mau-thiet-ke.md` §6
"Answer". Chỉ gọi tên phép CÓ trong phiên bản đã lưu (owner: không bao giờ nói đã điền
khi chưa điền); không bao giờ "tệp bạn tải lên", không bao giờ dấu nội bộ ⟦n⟧.
"""

from src.agents.nodes.assemble import TRAN_KY_TU, ResultType, assemble
from src.agents.nodes.route import Intent


def _bt(**kw) -> dict:
    bt = {
        "id": "b1",
        "loai": "tong_quat",
        "ten": "Hợp đồng thuê tài sản",
        "phien_ban": 1,
        "document": "# HỢP ĐỒNG THUÊ TÀI SẢN\n",
        "clauses": [
            {"key": None, "ten": "Giá thuê", "doan": ["x"]},
            {"key": "luong", "ten": "Mức lương", "doan": ["……"], "chen": True},
        ],
        "audit_report": {
            "khung": {
                "bo_cuc": "hop_dong",
                "can_cu": [
                    {"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015.", "doc_id": "95942"}
                ],
            }
        },
        "facts": {},
        "doi_so_voi_truoc": [],
        "viec_id": "v1",
        "phep_sua": [{"loai": "dien", "don_vi": 3, "cho_trong": 0, "gia_tri": " Nguyễn Văn An"}],
        "khuon": {
            "viec_id": "v1",
            "dinh_dang": "docx",
            "so_trang": 2,
            "nguon": "khuon_mau",
            "can_cu": [],
            "cho_trong": [
                {"don_vi": 3, "so": 0, "kieu": "tab", "nhan": "Họ và tên", "gia_tri": " Nguyễn Văn An"},
                {"don_vi": 4, "so": 0, "kieu": "tab", "nhan": "Ngày sinh", "gia_tri": None},
            ],
        },
    }
    bt.update(kw)
    return bt


def _dap(bt: dict, x: dict | None = None) -> dict:
    st = {
        "query": "soạn hợp đồng",
        "intent": Intent.soan_thao,
        "user_sub": "s",
        "muc_dich_tai_lieu": "tao_van_ban",
        "ban_thao_ket": bt,
        "khuon_mau_tong_quat": x or {},
    }
    return assemble(st, {}, None, "")


def test_loi_dap_goi_ten_dung_cho_da_dien_con_trong_va_can_cu():
    ket = _dap(_bt(), {"da_dien": 1})
    a = ket["answer"]
    assert ket["result_type"] == ResultType.ban_thao and ket["ban_thao"]["khuon"]["nguon"] == "khuon_mau"
    assert "Đã điền 1 chỗ trống từ lời bạn nói" in a and "Còn trống: «Ngày sinh»" in a
    assert "Căn cứ: Bộ luật Dân sự số 91/2015/QH13" in a and "Điều còn trống vì luật đòi: «Mức lương»" in a
    assert "(2 trang)" in a and "tệp bạn tải lên" not in a and "⟦" not in a
    assert "Thể thức theo tập quán" in a and len(a) <= TRAN_KY_TU


def test_khong_dien_gi_thi_khong_noi_da_dien():
    bt = _bt(phep_sua=[])
    bt["khuon"]["cho_trong"] = [{**o, "gia_tri": None} for o in bt["khuon"]["cho_trong"]]
    a = _dap(bt)["answer"]
    assert "Đã điền" not in a and "Còn trống: «Họ và tên», «Ngày sinh»" in a


def test_chi_noi_da_dien_cho_luot_nay_dien_khong_dem_gia_tri_mang_sang():
    """Owner: không bao giờ nói đã điền khi chưa điền. Phiên bản có một chỗ đã điền (mang
    sang hay điền trên trang), lượt này không điền gì: không câu "Đã điền"."""
    a = _dap(_bt(), {"da_dien": 0})["answer"]
    assert "Đã điền" not in a
    a = _dap(_bt(), {"da_dien": 1, "co_san": True})["answer"]
    assert "giữ nguyên" in a and "Đã điền" not in a


def test_gia_tri_chua_dat_duoc_va_ghi_chu_duoc_ke():
    a = _dap(_bt(), {"khong_dat": ["Lê Văn C"], "ghi_chu": ["Bỏ 1 đoạn ở Điều 2 vì dẫn số điều luật"]})["answer"]
    assert "Chưa đặt được: «Lê Văn C»" in a and "Bỏ 1 đoạn ở Điều 2" in a


def test_ban_dang_co_giu_nguyen_khong_noi_da_cap_nhat():
    a = _dap(_bt(), {"co_san": True, "ghi_chu": ["Tôi chưa xác định được điều cần sửa — hãy nêu số hoặc tên điều."]})[
        "answer"
    ]
    assert "giữ nguyên" in a and "đã cập nhật" not in a and "điều cần sửa" in a


def test_ban_thao_checklist_tren_khuon_mau_cung_loi_dap():
    st = {
        "query": "x",
        "intent": Intent.soan_thao,
        "user_sub": "s",
        "soan_thao_dang_mo": {"loai": "hdld", "facts": {}},
        "ban_thao_ket": _bt(loai="hdld"),
    }
    a = assemble(st, {}, None, "")["answer"]
    assert "Bấm vào chỗ trống trên trang để điền" in a and "sửa từng mục" not in a
    # Đường checklist không biết chỗ nào lượt này điền: nói tổng của phiên bản, không nguồn.
    assert "Đã điền 1/2 chỗ trống." in a and "từ lời bạn nói" not in a


def test_xem_ban_thao_khuon_mau_khong_noi_tep_tai_len():
    from src.agents.nodes.assemble import xem_ban_thao_khuon

    bt = {**_bt(), "ten_tep": "Hợp đồng thuê tài sản.docx", "audit": {}}
    a = xem_ban_thao_khuon(bt)["answer"]
    assert a.startswith("Đây là bản thảo «Hợp đồng thuê tài sản» (phiên bản 1): đã điền 1/2 chỗ trống")
    assert "tải lên" not in a
