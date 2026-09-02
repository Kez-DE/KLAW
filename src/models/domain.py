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
    # MỘT HÀNG DỮ LIỆU của bảng nằm trong Khoản/Điểm. Cấp TRÍCH DẪN ĐƯỢC thứ tư,
    # thêm 2026-09-02 theo quyết định của chủ dự án.
    #
    # Vì sao cần một cấp riêng thay vì mượn `diem`: nhà làm luật tới `90/2019/
    # NĐ-CP` tự đánh nhãn `a) b) c) d)` cho bốn vùng lương, rồi từ `74/2024` đổi
    # sang dàn trang bảng và BỎ nhãn — nội dung vẫn là bốn vùng đó. Gán lại
    # `a)…d)` là bịa nhãn cho bản mới; đọc `Vùng I` từ cột 1 là đọc thứ nguồn tự
    # ghi. Hai việc khác nhau, nên hai cấp khác nhau.
    #
    # ĐỨNG NGAY SAU `diem` để `bac` giữ đúng thứ bậc cây (`_don_vi`/stack của
    # parser pop theo `bac`). `phu_luc`/`mo_dau` dịch một bậc — vô hại, chúng
    # không bao giờ vào stack nên `bac` của chúng không mang nghĩa thứ bậc.
    hang_bang = "hang_bang"
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
    # `documentIssues[].personName`/`jobTitleName` của response MOJ — đã tải
    # sẵn từ lần `fetch_moj` đầu, lấy lại là 0 request phát sinh (migration
    # 015). None cho văn bản không khai người ký; CHECK của DB chặn chuỗi rỗng.
    nguoi_ky: str | None = None
    chuc_danh_nguoi_ky: str | None = None
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
