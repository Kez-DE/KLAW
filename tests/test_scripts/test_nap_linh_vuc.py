"""`linh_vuc_tu_hang` — quy tắc suy `linh_vuc` từ một hàng `metadata.parquet`
(T1, 8 lĩnh vực): ưu tiên cột `linh_vuc`, rỗng/NaN/"Chưa phân loại" thì lấy
`nganh`, cả hai rỗng → None. Test thuần bằng dict, không cần dựng
`metadata.parquet` thật.
"""

import math

from scripts.nap_linh_vuc import linh_vuc_tu_hang


def test_uu_tien_cot_linh_vuc():
    assert linh_vuc_tu_hang({"linh_vuc": "Đất đai", "nganh": "Tài nguyên và Môi trường"}) == "Đất đai"


def test_roi_xuong_nganh_khi_linh_vuc_rong_hoac_NaN():
    assert linh_vuc_tu_hang({"linh_vuc": None, "nganh": "Công Thương"}) == "Công Thương"
    assert linh_vuc_tu_hang({"linh_vuc": math.nan, "nganh": "Công Thương"}) == "Công Thương"
    assert linh_vuc_tu_hang({"linh_vuc": "   ", "nganh": "Công Thương"}) == "Công Thương"


def test_None_khi_ca_hai_deu_rong():
    assert linh_vuc_tu_hang({"linh_vuc": None, "nganh": None}) is None
    assert linh_vuc_tu_hang({}) is None


def test_chua_phan_loai_coi_nhu_rong():
    """'Chưa phân loại' là placeholder MẶC ĐỊNH của nguồn cho văn bản chưa gắn
    lĩnh vực — không phải một lĩnh vực thật (T1 finding 2). Rơi xuống `nganh`
    như mọi giá trị rỗng khác; cả hai đều 'Chưa phân loại'/rỗng → None."""
    assert linh_vuc_tu_hang({"linh_vuc": "Chưa phân loại", "nganh": "Tài chính"}) == "Tài chính"
    assert linh_vuc_tu_hang({"linh_vuc": "Chưa phân loại", "nganh": None}) is None
    assert linh_vuc_tu_hang({"linh_vuc": "Chưa phân loại", "nganh": "Chưa phân loại"}) is None
