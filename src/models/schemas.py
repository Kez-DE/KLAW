from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TraCuuRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    # `date`, KHÔNG PHẢI `str`: pydantic tự parse ISO ("2026-08-31") thành
    # `date` VÀ tự trả 422 cho chuỗi sai định dạng — endpoint không được nuốt
    # lỗi (Global Constraint). Nếu field này là `str`, `date` object mà
    # `n_expand`/`danh_gia` cần so sánh (`hl <= as_of`) sẽ nhận một chuỗi và
    # nổ TypeError ở giữa graph thay vì bị chặn sạch ở biên bởi FastAPI.
    as_of_date: date | None = None
    # `max_length`, KHÔNG PHẢI danh sách enum cố định (FastAPI review, MEDIUM):
    # đây là nhãn ablation (Task 9 có "full"/"hybrid"/"lexical_only"/
    # "dense_only"/"bm25_only", và danh sách còn mở rộng) — trước bản này là
    # field DUY NHẤT không ràng buộc gì, trong khi `query` có min/max_length
    # và `as_of_date` là `date`.
    config_name: str | None = Field(default=None, max_length=100)


class CitationOut(BaseModel):
    provision_id: int
    # `khop_tai_id` THIẾU ở đây từng làm pydantic (`extra="ignore"` mặc định)
    # âm thầm vứt field này tại biên HTTP (silent-failure review): response
    # ghép provision_id với duong_dan/so_ky_hieu của DÒNG KHÁC (khop_tai) mà
    # không trường nào nói ra — đúng ca THƯỜNG, không phải ca biên (73,6% số
    # Điều chỉ có tiêu đề, xem verify_tier1._cay_con), và đúng lệch mà
    # assemble.py (commit 4d46a3f) đã tách bạch ở tầng trong.
    khop_tai_id: int
    # Thiếu field này thì pydantic (`extra="ignore"`) vứt nó ở biên HTTP đúng
    # như đã xảy ra với `khop_tai_id` — và FE mất khoá duy nhất dựng được URL
    # `GET /van-ban/{doc_id}?around=`. `str` vì `documents.id` là TEXT.
    doc_id: str
    duong_dan: str
    bo_luat: str
    so_ky_hieu: str
    quote: str
    hieu_luc: str | None = None
    tin_cay: str | None = None


class NguonOut(BaseModel):
    """Văn bản chi phối câu hỏi, KHÔNG phải trích dẫn đã kiểm chứng.

    Chỉ `partial_coverage` điền. Nó tồn tại vì nhánh đó luôn có `citations: []`
    theo thiết kế (chưa kiểm chứng được thì không dựng trích dẫn) — mà nếu
    response chỉ còn `coverage_note` dạng văn xuôi thì giao diện không mở nổi
    văn bản đang nói tới, và FE buộc phải parse chuỗi để bịa link. `doc_id` đủ
    để mở mục lục qua `GET /van-ban/{doc_id}`.
    """

    doc_id: str
    so_ky_hieu: str
    bo_luat: str


class TraCuuResponse(BaseModel):
    result_type: Literal["answer", "partial_coverage", "abstain", "out_of_scope"]
    answer: str | None
    citations: list[CitationOut]
    nguon: list[NguonOut] = []
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
    config_name: str


# ══ GET /van-ban/{doc_id} (Task 7 step 2) — ba dạng lazy ═════════════════════
# BLDS (doc_id 95942) có 689 Điều: không dạng nào dưới đây được kéo cả cây.
# Tên field khớp NGUYÊN VĂN hợp đồng FE (fe-contract.md) — FE đang xây song
# song theo shape này, đổi tên trường ở đây là lỗi tích hợp câm.


class MucLucItem(BaseModel):
    # Chỉ 4 cấp TÀI LIỆU-cấu-trúc — KHÔNG BAO GIỜ 'dieu' (đó là lý do dạng
    # không tham số lazy: mục lục không kéo nội dung Điều). Ràng buộc kiểu ở
    # đây là lớp kiểm THỨ HAI, độc lập với `WHERE cap IN (...)` trong SQL —
    # nếu SQL từng nới lỏng sai, response vẫn bị chặn ở biên pydantic.
    id: int
    cap: Literal["phan", "chuong", "muc", "tieu_muc"]
    so_hieu_cap: str
    tieu_de: str
    thu_tu: int


class ProvisionOut(BaseModel):
    id: int
    cap: Literal["dieu", "khoan", "diem"]
    so_hieu_cap: str
    duong_dan: str
    tieu_de: str
    noi_dung: str
    # True cho Điều đang hỏi (`so_dieu`/`around`) VÀ mọi Khoản/Điểm con của
    # nó; False cho tối đa 4 Điều lân cận (dạng `around`) và con của chúng.
    la_tam: bool


class VanBanMucLucResponse(BaseModel):
    # `doc_id` là TEXT ở DB (`documents.id`, moj doc_id — vd "95942"), KHÔNG
    # PHẢI int: ép int sẽ vỡ nếu MOJ từng cấp một id không thuần số.
    doc_id: str
    so_ky_hieu: str
    bo_luat: str  # = documents.ten — HIỂN THỊ, không phải khoá định danh (xem assemble.py)
    muc_luc: list[MucLucItem]


class VanBanProvisionsResponse(BaseModel):
    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    provisions: list[ProvisionOut]


# ══ POST /soan-thao, POST /soat, GET /mau/{loai} (Task 5) ═══════════════════
# Request/response field names dùng NGUYÊN VĂN task-5-brief.md — FE đang dựng
# song song theo đó. `FindingOut` là ngoại lệ có chủ đích: hợp nhất
# `FindingOut` là ngoại lệ có chủ đích: brief gốc đặt tên `mo_ta` +
# `dieu_khoan_lien_quan`, ràng buộc điều phối #3 đặt `thong_diep` + `vi_tri`.
# Bản đầu giữ CẢ BỐN khoá (mỗi cặp cùng một giá trị) — điều phối gỡ bỏ trùng
# lặp: khoá trùng trong một API công khai là nợ chắc chắn mục, một cái được
# cập nhật còn cái kia không, rồi bên tiêu thụ chia đôi.
# Giữ `thong_diep` (chuỗi hiển thị cho người dùng — đúng hơn `mo_ta`) và
# `dieu_khoan_lien_quan`. BỎ `vi_tri`: giá trị của nó là `noi_dung[:120]` của
# điều khoản, tức một TRÍCH ĐOẠN, không phải một vị trí — `vi_tri` nói dối về
# thứ nó chứa. Tên nội bộ (`AuditFinding.mo_ta`) không đổi.

LoaiVanBan = Literal["hdld", "noi_quy", "quyet_dinh_ky_luat"]


class SoanThaoRequest(BaseModel):
    loai_van_ban: LoaiVanBan
    facts: dict
    nganh: str = "thuong_mai"
    config_name: str | None = None


class SoatRequest(BaseModel):
    loai_van_ban: LoaiVanBan
    # `max_length` BẮT BUỘC: `extract_clauses`/`draft_audit` chạy đồng bộ, và
    # một payload vài chục MB treo cả tiến trình uvicorn (một worker) cho MỌI
    # người dùng khác. 500k ký tự ~ dài gấp nhiều lần Bộ luật Lao động.
    text: str = Field(..., min_length=20, max_length=500_000)
    facts: dict = Field(default_factory=dict)
    nganh: str = "thuong_mai"


class FindingOut(BaseModel):
    loai: str
    muc_do: str
    thong_diep: str
    dieu_khoan_lien_quan: str | None = None
    can_cu: str | None = None             # duong_dan — CHUỖI (không phải dict brief gốc, theo ràng buộc #3)
    rule_id: str | None = None
    # Ràng buộc #3: thiếu hai trường này thì panel đối chiếu phía FE không mở
    # được (can_cu một mình chỉ là chuỗi duong_dan). None cho
    # citation_khong_hop_le — chính bản thân can_cu đó không tồn tại nên
    # không có gì để mở.
    doc_id: str | None = None
    khop_tai_id: int | None = None
    # True = rule KHÔNG được kiểm (thiếu fact), KHÔNG phải văn bản sai. Trước
    # bản này giao diện phải suy lại từ chuỗi `thong_diep`, nên một rule chưa hề
    # được kiểm từng đeo nhãn "Trái quy định" — nói với người dùng rằng văn bản
    # của họ SAI LUẬT trong khi máy chỉ thiếu dữ liệu.
    khong_kiem_duoc: bool = False


class AuditReportOut(BaseModel):
    dat: bool
    completeness: float
    so_dieu_khoan: int
    self_audit: bool
    findings: list[FindingOut]


class SoanThaoResponse(BaseModel):
    document: str                    # Markdown
    clauses: list[dict]
    audit_report: AuditReportOut
    trace_id: str


class SoatResponse(BaseModel):
    audit_report: AuditReportOut
    trace_id: str


class FactFieldOut(BaseModel):
    """Một trường của form nhập fact — sinh từ config/rules.yaml
    (rules.mo_ta_facts), KHÔNG hardcode danh sách trường (ràng buộc #4)."""

    key: str
    nhan: str
    kieu: str
    bat_buoc: bool
    lua_chon: list[str] | None = None


class MauResponse(BaseModel):
    loai_van_ban: str
    facts: list[FactFieldOut]


# ══ GET /api/v1/pham-vi ══════════════════════════════════════════════════════
# Trang /pham-vi bị CẤM viết cứng "21 văn bản / 19.135 điều khoản" vào JSX. Một
# con số viết cứng sai ngay lần seed sau, và dự án này tồn tại để chống đúng
# loại khẳng định không kiểm chứng được đó.


class VanBanPhamViOut(BaseModel):
    doc_id: str
    so_ky_hieu: str  # ĐỊNH DANH (Global Constraint)
    bo_luat: str  # = documents.ten — chỉ để hiển thị
    loai_van_ban: str
    so_dieu_khoan: int
    # `tinh_trang_moj`, KHÔNG phải `tinh_trang`: đây là tuyên bố của CSDL quốc
    # gia, không phải phán quyết của KLAW. MOJ đánh 4 nghị định lương tối thiểu
    # đã bị thay thế là "còn hiệu lực"; KLAW sửa cả 4. Tên trần sẽ khiến người
    # đọc tưởng KLAW xác nhận con số này.
    tinh_trang_moj: str | None = None


class TangPhamViOut(BaseModel):
    so_van_ban: int
    so_dieu_khoan: int
    van_ban: list[VanBanPhamViOut]


class PhamViResponse(BaseModel):
    """Hai tầng, vì corpus thật có hai tầng.

    `sau` — có toàn văn, trả lời được thành `answer`.
    `nong` — chỉ metadata; CHÍNH LÀ thứ sinh ra `partial_coverage`. Giấu tầng
    này đi là mô tả sai sản phẩm.
    """

    sau: TangPhamViOut
    nong: TangPhamViOut
