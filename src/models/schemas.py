from datetime import date, datetime
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
    # Phải khớp ĐỦ `ResultType` ở `assemble.py`. Một loại có ở enum mà thiếu ở
    # đây thì graph dựng đúng kết quả rồi chết ở khâu tuần tự hoá — đã xảy ra
    # với `gioi_thieu` 2026-09-01. `test_response_model_biet_moi_gia_tri_cua_ResultType`
    # so hai tập nên lần sau nó đỏ ngay.
    result_type: Literal[
        "answer", "partial_coverage", "abstain", "out_of_scope", "gioi_thieu"
    ]
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
    # `'dieu'` được nhận từ 2026-09-01, cho 11/47 văn bản KHÔNG có Chương/Mục
    # nào (sáu nghị định lương tối thiểu nằm trong đó). Với chúng, cấu trúc
    # duyệt được của văn bản CHÍNH LÀ danh sách Điều; loại nó ra chỉ khiến
    # người mở thấy trang trắng.
    #
    # Bất biến thật mà model này giữ KHÔNG PHẢI là "cap không bao giờ là dieu"
    # — mà là **mục lục không bao giờ mang `noi_dung`**, tức dạng không tham số
    # luôn lazy. Bất biến đó được cưỡng chế bằng thứ mạnh hơn một Literal:
    # `noi_dung` không phải là trường của model này, nên không truy vấn nào
    # nhét được nội dung Điều vào đây dù `cap` nhận giá trị gì.
    id: int
    cap: Literal["phan", "chuong", "muc", "tieu_muc", "dieu"]
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


class VanBanMetaMixin(BaseModel):
    """Metadata dùng chung cho CẢ BA dạng lazy của `GET /van-ban/{doc_id}`.

    FE đi thẳng vào `?so_dieu=` khi mở một liên kết chia sẻ; nếu chỉ dạng mục
    lục mang metadata thì trang đó hiện tiêu đề trống cho tới khi người dùng
    bấm ngược lên mục lục.

    KHÔNG có `tinh_trang`, dù nó nằm cùng dòng `documents` và thêm vào là một
    dòng code. Đó là dòng code khiến trang đọc văn bản dán nhãn "Còn hiệu lực"
    lên bốn nghị định lương tối thiểu đã bị thay. Hiệu lực đi qua
    `GET /van-ban/{doc_id}/hieu-luc`, chỗ duy nhất `effectivity.py` chạy.
    """

    # `doc_id` là TEXT ở DB (`documents.id`, moj doc_id — vd "95942"), KHÔNG
    # PHẢI int: ép int sẽ vỡ nếu MOJ từng cấp một id không thuần số.
    doc_id: str
    so_ky_hieu: str
    bo_luat: str  # = documents.ten — HIỂN THỊ, không phải khoá định danh (xem assemble.py)
    loai_van_ban: str
    # NULL trên đúng 79/126 dòng (tầng metadata nạp từ parquet, không có trường
    # nào tương ứng). NULL = KHÔNG BIẾT, không phải "không có".
    co_quan_ban_hanh: str | None = None
    ngay_ban_hanh: date | None = None
    ngay_hieu_luc: date | None = None
    # NULL trên 95/126 dòng: phần lớn văn bản chưa có ngày hết hiệu lực. Đây là
    # trường của CHÍNH CSDL quốc gia và tin được (Mức 1 của `effectivity.py`
    # dùng đúng nó) — khác hẳn `tinh_trang`, thứ sai 4/6 trên chuỗi nghị định
    # lương tối thiểu.
    ngay_het_hieu_luc: date | None = None
    # Từ `documentIssues[]` của response MOJ đã tải sẵn (migration 015).
    nguoi_ky: str | None = None
    chuc_danh_nguoi_ky: str | None = None


class VanBanMucLucResponse(VanBanMetaMixin):
    muc_luc: list[MucLucItem]


class VanBanProvisionsResponse(VanBanMetaMixin):
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

# PHẢI khớp tập `config/checklist_*.yaml` — tests/test_services/test_moi_mau.py
# khoá hai chiều: một file không có tên ở đây thì Pydantic trả 422 và không ai
# gọi tới mẫu đó được, một tên ở đây không có file thì route trả 501.
LoaiVanBan = Literal[
    "bien_ban_hop_hdqt",
    "don_khoi_kien",
    "don_yeu_cau",
    "hdld",
    "hop_dong_dich_vu",
    "hop_dong_hop_tac",
    "hop_dong_gia_cong",
    "hop_dong_mua_ban",
    "hop_dong_thu_viec",
    "hop_dong_thue_tai_san",
    "hop_dong_uy_quyen",
    "hop_dong_vay",
    "noi_quy",
    "quyet_dinh_cham_dut_hdld",
    "quyet_dinh_ky_luat",
    "thoa_thuan_bao_mat",
]


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
    # `facts: []` một mình MƠ HỒ: nó vừa là "loại này chưa có checklist" vừa là
    # "loại này có checklist nhưng không rule nào cần fact" (thoả thuận bảo mật,
    # biên bản họp — completeness là toàn bộ phép soát, không có ngưỡng số nào
    # để kiểm). Frontend đọc rỗng thành "chưa có backend" sẽ giấu mất một mẫu
    # đã dựng xong. `ho_tro` nói thẳng, không bắt bên gọi suy từ một danh sách
    # rỗng.
    ho_tro: bool
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


# ══ GET /bo-loc, GET /tim-kiem (Pha 2) ══════════════════════════════════════
# Cùng lý lẽ với `PhamViResponse`: giao diện không được viết cứng thứ nó không
# đo được. FE Lovable hardcode 11 loại văn bản / 8 cơ quan / 10 lĩnh vực; DB
# thật có 8 loại, 3 cơ quan (+79 văn bản KHÔNG có cơ quan) và KHÔNG CÓ cột lĩnh
# vực nào. Ba con số bịa, và mỗi cái bịa ra một chip bấm vào trả về rỗng.


class GiaTriLoc(BaseModel):
    gia_tri: str
    so_van_ban: int


class BoLocResponse(BaseModel):
    """Từ vựng bộ lọc, ĐẾM TỪ DB. Không khoá `linh_vuc` (không có cột), không
    khoá `tinh_trang` (lọc theo tuyên bố sai của MOJ là đúng lỗi Mức 2 mà dự án
    tồn tại để chữa — lọc hiệu lực đi qua `sap_xep`, xem `TimKiemRequest`)."""

    tong_van_ban: int
    loai_van_ban: list[GiaTriLoc]
    co_quan_ban_hanh: list[GiaTriLoc]
    # Số văn bản KHÔNG khai cơ quan. Nói ra thay vì lặng lẽ bỏ qua: 79/126 văn
    # bản tầng metadata rơi vào đây, nên tổng theo cơ quan KHÔNG bằng tổng
    # corpus và giao diện phải biết điều đó trước khi vẽ biểu đồ tròn.
    co_quan_khong_ro: int
    nam_min: int | None
    nam_max: int | None
    sap_xep: list[str]


class HieuLucOut(BaseModel):
    """Phán quyết của KLAW (`effectivity.Effectivity`), KHÔNG PHẢI
    `documents.tinh_trang`. Tên `verdict` giữ nguyên chuỗi của `EffectivityVerdict`
    để FE `switch` trên nó và để nhãn mới rơi vào `default` an toàn."""

    verdict: str
    tin_cay: str
    ly_do: str


class KetQuaTimKiem(BaseModel):
    provision_id: int
    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    loai_van_ban: str
    co_quan_ban_hanh: str | None
    ngay_ban_hanh: date | None
    cap: str
    so_hieu_cap: str
    duong_dan: str
    tieu_de: str
    trich: str
    score: float
    hieu_luc: HieuLucOut


class TimKiemResponse(BaseModel):
    q: str
    # Của TOÀN tập khớp, không phải của trang — "N điều khoản trong M văn bản".
    tong_dieu_khoan: int
    tong_van_ban: int
    limit: int
    offset: int
    sap_xep: str
    ket_qua: list[KetQuaTimKiem]


# ══ GET /van-ban/{doc_id}/hieu-luc (Pha 2) ══════════════════════════════════
# KHÔNG có trường `tinh_trang` ở bất kỳ đâu trong nhóm model này, và đó là
# quyết định thiết kế chính: CSDL quốc gia đánh bốn nghị định lương tối thiểu
# đã bị thay là "còn hiệu lực", FE Lovable render trường đó ở 11 vị trí, và
# một trường JSON là đủ để lật ngược đóng góp trung tâm của hệ thống.


class SuaBoiOut(BaseModel):
    """Một điểm sửa, có CẤU TRÚC — không phải một câu văn xuôi để FE tự bóc.

    `vi_tri` là vị trí VBHN nêu ("Điều 154 > Khoản 8a"), có thể KHÁC
    `duong_dan` của điều khoản mang nhãn: khoản mới thêm ("8a") phân giải về
    Điều cha vì nó chưa tồn tại trong bản gốc.
    """

    vi_tri: str
    so_ky_hieu: str | None
    duong_dan: str | None
    tu_ngay: date | None
    nguon: str
    do_tin_cay: str


class DieuKhoanHieuLucOut(BaseModel):
    provision_id: int
    duong_dan: str
    cap: str
    so_hieu_cap: str
    tieu_de: str
    hieu_luc: HieuLucOut
    sua_boi: list[SuaBoiOut]


class VanBanHieuLucResponse(BaseModel):
    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    as_of: date
    # Mức 1/2/3 — `effectivity.danh_gia`.
    van_ban: HieuLucOut
    # Mức 4 — chỉ những điều khoản CÓ bằng chứng cấp điều khoản. Rỗng là kết
    # quả HỢP LỆ (19.131/19.135 điều khoản không có bản ghi nào), không phải lỗi.
    dieu_khoan: list[DieuKhoanHieuLucOut]


# ══ GET /van-ban/{doc_id}/lien-quan (Pha 2) ═════════════════════════════════
# Bản đồ ĐIỀU HƯỚNG, KHÔNG phải phán quyết. Hiệu lực đi qua
# `/van-ban/{doc_id}/hieu-luc` — đó là chỗ duy nhất `effectivity.py` chạy.


class VanBanLienQuanOut(BaseModel):
    # None khi văn bản đối diện KHÔNG có trong corpus (273/626 cạnh cấp văn
    # bản). `so_ky_hieu` vẫn có (MOJ khai) nên vẫn nêu được định danh; `doc_id`
    # None là thứ nói với FE rằng đừng dựng link — link đó sẽ ra 404.
    doc_id: str | None
    so_ky_hieu: str
    bo_luat: str | None
    trong_corpus: bool


class NhomLienQuanOut(BaseModel):
    loai: int
    nhan: str
    # `di_ra` = văn bản này đứng ở đầu `from` của cạnh; `di_vao` = ở đầu `to`.
    chieu: Literal["di_ra", "di_vao"]
    # Chiều NGỮ NGHĨA đã đo hay chưa. False cho mã MOJ: "Thay thế" trong danh
    # sách của X có thể là "X thay thế Y" hoặc ngược lại, và 242 dòng đó chưa
    # ai đo (xem `effectivity.TAC_DONG`). Hiển thị một nhãn quan hệ pháp lý có
    # 50% khả năng ngược mà không nói ra là một khẳng định không kiểm chứng được.
    chieu_da_do: bool
    so_luong: int
    van_ban: list[VanBanLienQuanOut]


class DanChieuNoiBoOut(BaseModel):
    so_luong: int
    ghi_chu: str


class VanBanLienQuanResponse(BaseModel):
    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    nhom: list[NhomLienQuanOut]
    # ĐO ĐƯỢC 2.971/2.971 dẫn chiếu cấp điều khoản nằm TRONG cùng một văn bản —
    # chúng không phải "văn bản liên quan", và trộn vào `nhom` là chôn 8 quan hệ
    # thật dưới 120 dòng trỏ về chính văn bản đang mở.
    dan_chieu_noi_bo: DanChieuNoiBoOut


# ══ GET /han-muc, POST /nguoi-dung (Pha 2) ══════════════════════════════════


class HanMucResponse(BaseModel):
    """Hạn mức tháng CÒN LẠI của người đang đăng nhập.

    `ap_dung=False` khi Supabase chưa cấu hình: hệ thống không đếm theo người,
    nên bốn trường số là None chứ KHÔNG phải 0 — 0 đọc thành "bạn chưa dùng lượt
    nào", một khẳng định sai về một thứ không hề được đo.
    """

    ap_dung: bool
    plan: str | None
    han_muc: int | None
    da_dung: int | None
    con_lai: int | None
    # Có cả khi `ap_dung=False`: mốc reset là thuộc tính của LỊCH, không phải
    # của người dùng, và giao diện vẫn cần nó để nói "đặt lại vào ngày…".
    dat_lai_luc: datetime
    ghi_chu: str


class NguoiDungResponse(BaseModel):
    sub: str
    email: str | None
    plan: str


# ══ GET /van-ban/{doc_id}/tim (Pha 2) ═══════════════════════════════════════


class DongTimTrongVanBan(BaseModel):
    provision_id: int
    cap: str
    so_hieu_cap: str
    duong_dan: str
    tieu_de: str
    trich: str
    # Thứ tự trong cây — FE cuộn tới đúng chỗ và giữ được vị trí người đọc đang
    # đứng. Cũng là khoá sắp xếp: đây là mục lục, không phải bảng xếp hạng.
    thu_tu: int


class TimTrongVanBanResponse(BaseModel):
    doc_id: str
    so_ky_hieu: str
    q: str
    tong: int
    limit: int
    ket_qua: list[DongTimTrongVanBan]
