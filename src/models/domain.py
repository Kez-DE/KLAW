from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Cap(StrEnum):
    phan = "phan"
    chuong = "chuong"
    muc = "muc"
    tieu_muc = "tieu_muc"
    dieu = "dieu"
    khoan = "khoan"
    diem = "diem"
    # Nội dung đuôi (Phụ lục, khối chữ ký) — cấp TÀI LIỆU, không phải cấp trong
    # cây quy phạm. Đứng CUỐI enum để `bac` của 7 cấp trên không dịch; nó không
    # bao giờ vào stack nên `bac` của nó không có nghĩa thứ bậc.
    phu_luc = "phu_luc"
    # Lời mở đầu (tiêu ngữ, số hiệu, tên văn bản, chuỗi "Căn cứ …") — ĐỐI XỨNG
    # với `phu_luc`: chữ nằm TRƯỚC thẻ prov-* đầu tiên, cũng là cấp TÀI LIỆU và
    # cũng không trích dẫn được. Cùng lý do đứng cuối enum.
    mo_dau = "mo_dau"

    @property
    def bac(self) -> int:
        """Bậc trong cây; dùng để pop stack khi parse HTML phẳng."""
        return list(Cap).index(self)


class DocumentRow(BaseModel):
    id: str = Field(..., min_length=1)
    so_ky_hieu: str = Field(..., min_length=1)
    loai_van_ban: str = Field(..., min_length=1)
    ten: str = ""
    co_quan_ban_hanh: str | None = None
    ngay_ban_hanh: date | None = None
    ngay_hieu_luc: date | None = None
    ngay_het_hieu_luc: date | None = None
    tinh_trang: str = Field(..., min_length=1)
    depth: Literal["deep", "shallow"] = "deep"
    nguon_url: str | None = None
    checksum: str = Field(..., min_length=1)


class ProvisionRow(BaseModel):
    local_id: int
    parent_local_id: int | None
    cap: Cap
    so_hieu_cap: str
    tieu_de: str = ""
    noi_dung: str = ""
    duong_dan: str = Field(..., min_length=1)
    source_node_id: str | None = None
    thu_tu: int


class ReferenceRow(BaseModel):
    from_document_id: str
    to_document_id: str | None = None
    loai: int
    raw_text: str | None = None
