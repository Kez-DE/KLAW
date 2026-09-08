from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class LuotTruoc(BaseModel):
    """Một lượt hỏi-đáp ĐÃ XONG, do client gửi lên để giải nghĩa câu nối tiếp.

    Cả ba trường đã có sẵn trong `LuotDaXong` phía giao diện
    (`frontend/src/routes/dung-thu.tsx`) — lịch sử vốn nằm ở client, nó chỉ chưa
    được gửi lên. Có danh tính thì máy chủ tự nạp từ phiên
    (`hoi_thoai.lich_su_gan_nhat`) và bỏ qua trường client gửi; ẩn danh vẫn gửi từ
    client. Lịch sử chỉ dùng để làm câu hỏi TỰ ĐỨNG ĐƯỢC, nó không chống đỡ khẳng
    định nào, nên một lịch sử bịa cũng chỉ tạo ra một câu hỏi khác — câu đó vẫn
    phải qua đủ hai tầng kiểm chứng (xem docstring `agents/nodes/giai_nghia.py`).

    `tra_loi` cần vì `"liệt kê bảng cho tôi"` phải biết câu trả lời trước CÓ một
    cái bảng; `duong_dan` là thứ định danh chính xác điều khoản lượt trước đã
    dẫn. Cả hai bị cắt còn `giai_nghia.TOI_DA_TRA_LOI` ký tự khi dựng prompt —
    trần ở đây chỉ để một body dị thường không đi xa hơn biên HTTP.
    """

    # `min_length=1` cùng khuôn `TraCuuRequest.query`: `cau_hoi=""` từng hợp lệ,
    # nên một `lich_su` toàn rỗng vẫn truthy → kích hoạt `giai_nghia` và tắt cache
    # dù không có nội dung thật nào.
    cau_hoi: str = Field(..., min_length=1, max_length=2000)  # cùng trần với `query`
    tra_loi: str = Field("", max_length=2000)
    # `max_length` trên `list[str]` giới hạn SỐ PHẦN TỬ, KHÔNG giới hạn độ dài
    # từng chuỗi. ĐO ĐƯỢC 2026-09-02 (review): `duong_dan=["A"*2_000_000]*50`
    # được chấp nhận — ~100 MB đi thẳng vào prompt `giai_nghia`, không qua bước
    # cắt nào (`ngu_canh` cắt `tra_loi` mà không cắt trường này). Trần 500 vì một
    # `duong_dan` thật dài nhất trong corpus dưới 100 ký tự.
    duong_dan: list[Annotated[str, StringConstraints(max_length=500)]] = Field(default_factory=list, max_length=50)


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
    # Ba lượt gần nhất, không hơn. `max_length` (⇒ 422) chứ không cắt im lặng:
    # một client gửi 20 lượt đang hiểu sai hợp đồng, và cắt lặng lẽ thì nó chạy
    # tiếp mãi với một ngữ cảnh khác cái nó tưởng — cùng lựa chọn với `query`
    # (422 khi quá 2000 ký tự, không truncate).
    lich_su: list[LuotTruoc] = Field(default_factory=list, max_length=3)
    # Spec 2026-09-07 §5.2: phiên hội thoại để máy chủ nạp `lich_su` và ghi lượt. Chỉ
    # có ý nghĩa khi có danh tính; ẩn danh thì bị bỏ qua.
    hoi_thoai_id: UUID | None = None


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
    # Số thứ tự căn cứ trong văn xuôi (thẻ `cite:K`, spec 2026-09-06 §3). None =
    # trích dẫn nằm trong vết kiểm toán nhưng KHÔNG được dùng để hành văn (bị
    # phép kiểm thứ bảy lọc) — hoặc payload cache ghi trước khi trường này có.
    k: int | None = None


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


class LinkVanBanOut(BaseModel):
    """Ba cổng luật, mỗi cột NULL khi chưa có link đã kiểm (migration 019).
    Mô hình không bao giờ thấy các URL này — backend điền từ `documents`."""

    vbpl: str | None = None
    chinhphu: str | None = None
    tvpl: str | None = None


class DocumentOut(BaseModel):
    """Văn bản được dùng để hành văn — đúng tập mô hình được phép đặt thẻ `doc`.

    KHÔNG mang `ngay_ban_hanh`/`ngay_hieu_luc` (quyết định Q2, spec §2): nhãn
    hiệu lực cạnh trích dẫn là nơi duy nhất nói về hiệu lực.
    """

    doc_id: str
    ten: str
    so_ky_hieu: str
    loai_van_ban: str
    links: LinkVanBanOut = LinkVanBanOut()


class LoaiGoiYOut(BaseModel):
    loai: str
    ten: str


class SoanThaoGoiYOut(BaseModel):
    """Gợi ý loại văn bản cho `result_type == huong_dan_soan_thao` (spec
    2026-09-06 soạn thảo trong chat §4.3). `loai` là mã checklist trên đĩa
    (`graph_soan_thao.cac_loai()`), None khi router không chắc hoặc loại
    không có mẫu; FE mở khung soạn thảo theo `loai`, chip theo `thay_the`."""

    loai: str | None
    ten: str | None
    ly_do: str
    thay_the: list[LoaiGoiYOut] = []
    ho_tro: bool


class Bang(BaseModel):
    """Một bảng dữ liệu CÓ KIỂU — trả kèm `answer` khi câu hỏi về kho xin trình
    bày dạng bảng (`services/kho.dung_bang`), để giao diện dựng bảng thật thay
    vì người dùng tự bẻ gạch đầu dòng ra thành cột.

    `dong[i]` phải cùng độ dài với `cot`: một bảng lệch cột là lỗi hiện ra
    thành giao diện méo (ô rỗng hoặc dồn sai cột), không thành exception nào ở
    tầng Python nếu không chặn — validator dưới đây chặn nó ở BIÊN, trước khi
    rời khỏi tầng thuần của `kho.py`.
    """

    tieu_de: str
    cot: list[str]
    dong: list[list[str]]

    @model_validator(mode="after")
    def _dong_khop_so_cot(self) -> "Bang":
        so_cot = len(self.cot)
        lech = [i for i, hang in enumerate(self.dong) if len(hang) != so_cot]
        if lech:
            i = lech[0]
            raise ValueError(
                f"bảng '{self.tieu_de}': hàng {i} có {len(self.dong[i])} ô, "
                f"cần {so_cot} (khớp `cot`) — {len(lech)} hàng lệch"
            )
        return self


class TraCuuResponse(BaseModel):
    # Phải khớp ĐỦ `ResultType` ở `assemble.py`. Một loại có ở enum mà thiếu ở
    # đây thì graph dựng đúng kết quả rồi chết ở khâu tuần tự hoá — đã xảy ra
    # với `gioi_thieu` 2026-09-01. `test_response_model_biet_moi_gia_tri_cua_ResultType`
    # so hai tập nên lần sau nó đỏ ngay.
    result_type: Literal[
        "answer",
        "partial_coverage",
        "abstain",
        "out_of_scope",
        "gioi_thieu",
        "huong_dan_soan_thao",
        "hoi_ve_kho",
    ]
    answer: str | None
    citations: list[CitationOut]
    nguon: list[NguonOut] = []
    warnings: list[str]
    coverage_note: str | None
    # Trình bày `hoi_ve_kho` dạng BẢNG khi câu hỏi xin (`services/kho.
    # xin_dang_bang`) — `list[Bang]`, KHÔNG `Bang | None`: một câu trả lời về
    # kho tự nhiên có HAI bảng (phân theo loại văn bản, phân theo lĩnh vực).
    # Mặc định `[]`: rỗng cho mọi `result_type` khác, cho `hoi_ve_kho` khi câu
    # hỏi không xin bảng, VÀ giữ tuần tự hoá được cho mọi payload cache đã ghi
    # TRƯỚC field này tồn tại (payload không có khoá `bang` — cùng lý do với
    # `cau_hoi_day_du` ngay dưới).
    bang: list[Bang] = []
    # Văn bản mô hình được phép gắn thẻ `doc:ID` + link cổng luật từ DB. Mặc
    # định `[]` cùng lý do `bang`: payload cache cũ không có khoá này.
    documents: list[DocumentOut] = []
    # Chỉ nhánh `huong_dan_soan_thao` điền; mặc định None cùng lý do `bang`/
    # `documents` (payload cache cũ không có khoá).
    soan_thao: SoanThaoGoiYOut | None = None
    # Câu hỏi sau khi giải nghĩa tham chiếu từ `lich_su`. `None` ở lượt đầu và
    # khi không giải nghĩa được. Giao diện ghi một dòng "Mình hiểu câu hỏi của
    # bạn là: …" CHỈ khi nó khác câu người dùng gõ.
    #
    # Bắt buộc phải trả ra, không phải một trường tiện lợi: giải nghĩa sai là chế
    # độ hỏng chắc chắn xảy ra, và không có trường này thì người dùng nhận câu
    # trả lời cho một câu HỌ KHÔNG HỎI mà không có cách nào biết, cũng không có
    # cách nào sửa. Mặc định `None` để một dòng cache ghi trước bản này (payload
    # không có khoá này) vẫn tuần tự hoá được.
    cau_hoi_day_du: str | None = None
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
    # `hang_bang` = MỘT HÀNG dữ liệu của bảng (migrations/017). `noi_dung` của
    # nó là đúng một dòng markdown `| ô | ô | ô |`; hàng TIÊU ĐỀ ở lại
    # `noi_dung` của Khoản cha, nên FE dựng lại bảng bằng: lấy dòng `|…|` cuối
    # trong `noi_dung` của cha làm tên cột, rồi mỗi con `hang_bang` là một hàng.
    #
    # `Literal` chứ không phải `str`: nó là hợp đồng với FE, và một cấp mới lọt
    # ra API mà FE chưa biết render thì tốt nhất là nổ ở biên. Đã nổ thật —
    # 500 trên `GET /van-ban/183939?so_dieu=3` ngay sau khi ingest 13 dòng
    # `hang_bang` đầu tiên, trước khi dòng này được thêm.
    cap: Literal["dieu", "khoan", "diem", "hang_bang"]
    so_hieu_cap: str
    # Quan hệ cha–con TƯỜNG MINH. Trước `hang_bang` thứ tự trả về là đủ để FE
    # suy ra cây (Điều → Khoản → Điểm, mỗi cấp một lần); với hàng bảng thì FE
    # phải GOM đúng các hàng vào đúng Khoản để dựng lại một cái bảng, và suy ra
    # từ thứ tự là một quy ước ngầm sẽ vỡ im lặng khi thứ tự đổi.
    parent_id: int | None = None
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
    "ban_tu_khai",
    "bien_ban_hop_hdqt",
    "cong_van",
    "don_khieu_nai",
    "don_khoi_kien",
    "don_xin_nghi_viec",
    "don_yeu_cau",
    "giay_uy_quyen",
    "hdld",
    "hop_dong_dich_vu",
    "hop_dong_hop_tac",
    "hop_dong_gia_cong",
    "hop_dong_mua_ban",
    "hop_dong_mua_ban_tai_san",
    "hop_dong_nguyen_tac",
    "hop_dong_thu_viec",
    "hop_dong_thue_tai_san",
    "hop_dong_uy_quyen",
    "hop_dong_vay",
    "noi_quy",
    "quyet_dinh_bo_nhiem",
    "quyet_dinh_cham_dut_hdld",
    "quyet_dinh_hdqt",
    "quy_che_dan_chu",
    "quy_che_noi_bo",
    "quyet_dinh_ky_luat",
    "thoa_thuan_bao_mat",
    "thoa_thuan_cham_dut_hdld",
    "van_ban_giai_trinh",
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
    can_cu: str | None = None  # duong_dan — CHUỖI (không phải dict brief gốc, theo ràng buộc #3)
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
    document: str  # Markdown
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


class MucMauOut(BaseModel):
    """Một mục của checklist, đủ để frontend dựng khung văn bản KHÔNG gọi LLM."""

    stt: int
    key: str
    ten: str
    can_cu: str
    # Suy từ `khong_bat_buoc.keys` của chính checklist, KHÔNG phải một cột thứ
    # hai trong YAML: hai nguồn sẽ lệch vào ngày ai đó thêm một mục vào khối
    # ngoại lệ mà quên đổi cột. Đây cũng đúng tập mà `check_completeness` dùng
    # làm mẫu số, nên khung frontend dựng và con số /soat trả về nói cùng một
    # chuyện.
    bat_buoc: bool


class CauTrucMauOut(BaseModel):
    """Cấu trúc một loại văn bản — ĐỌC THẲNG từ `config/checklist_<loai>.yaml`,
    cùng file mà `/soan-thao` và `/soat` dùng. Không có bản mô tả thứ hai.

    ĐỦ ĐỂ DỰNG LẠI ĐÚNG THỨ `/soan-thao` TRẢ VỀ. `_render_markdown` của
    routes.py sinh đúng hai thứ và không gì khác:

        # {tieu_de}
        ## {don_vi_muc} {i}. {muc[i].ten}

    Không có khối "khung" nào khác — không quốc hiệu, không khối ký, không khối
    hai bên — vì backend không có thẩm quyền nào để dựng chúng. Với `cong_van`
    và ba mẫu thể thức khác, quốc hiệu / nơi nhận / chữ ký CHÍNH LÀ các `muc`
    (chín thành phần NĐ 30/2020 Đ8.2). Với `hdld` chúng KHÔNG có mặt, vì BLLĐ
    Đ21 không đòi — nên bất kỳ khối "BÊN A / BÊN B / Mã số thuế" nào frontend
    vẽ thêm là phát minh của frontend, không phải yêu cầu của luật, và tuyệt
    đối không được dựng cho một loại văn bản không phải hợp đồng.
    """

    ten: str
    tieu_de: str
    don_vi_muc: str
    muc_do_thieu: str
    # "noi_dung" | "the_thuc" — xem `PHAM_VI_SOAT` ở src/services/checklist.py.
    pham_vi_soat: str
    # TRẢ LỜI THẲNG câu "mẫu này có chỉ soát thể thức không". Tính ở server để
    # frontend không phải tự ghép `pham_vi_soat == "the_thuc" and not facts` và
    # ghép sai. `quyet_dinh_bo_nhiem` là mẫu LAI: pham_vi_soat="the_thuc" nhưng
    # có rule nhiệm kỳ, nên cờ này là False và nhãn phải nói cả hai vế.
    chi_soat_the_thuc: bool
    # `True` khi mẫu dựng trên chế định HỢP ĐỒNG (BLDS Đ385). Chỉ khi đó văn
    # bản mới có giải phẫu hai bên + chỗ ký.
    #
    # KHÔNG suy được ở phía bên gọi, đã đo: `can_cu_goc` không phân biệt được
    # (91/2015/QH13 chứa cả Đ430 hợp đồng mua bán lẫn Đ138 giấy uỷ quyền;
    # 45/2019/QH14 chứa cả Đ21 HĐLĐ lẫn Đ118 nội quy), và suy từ `muc` sai cả
    # hai chiều — `giay_uy_quyen` có `ben_uy_quyen`/`ben_duoc_uy_quyen` nhưng là
    # hành vi MỘT bên (đúng lý do nó không được ánh xạ sang `hop_dong_uy_quyen`),
    # còn `hdld`, `hop_dong_thu_viec`, `thoa_thuan_bao_mat`, `hop_dong_mua_ban`
    # không có mục nào nhắc "bên".
    la_hop_dong: bool
    # Khối các bên + chỗ ký, kèm can_cu thật (Đ385, Đ400.4). `None` khi
    # `la_hop_dong=False`.
    #
    # TÁCH KHỎI `muc` CÓ CHỦ Ý: hai khối này KHÔNG nằm trong mẫu số của
    # `check_completeness`. Gộp chúng vào `muc` sẽ làm tỷ lệ hiển thị lệch khỏi
    # con số `/soat` trả về trên cùng một văn bản.
    #
    # Phục vụ ở đây thay vì để frontend viết cứng hai chuỗi can_cu: một can_cu
    # nằm trong frontend không bao giờ đi qua cổng phân giải
    # `provisions.duong_dan` — mà đó là bất biến trung tâm của cả dự án.
    khung_hop_dong: list[MucMauOut] | None
    can_cu_goc: str
    can_cu_chi_tiet: str | None
    muc: list[MucMauOut]


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
    # THÊM MỚI, không phá hợp đồng cũ: `loai_van_ban`, `ho_tro`, `facts` giữ
    # nguyên hình dạng. `None` khi `ho_tro=False` — không có checklist thì không
    # có cấu trúc, và một `cau_truc` rỗng sẽ trông y hệt một mẫu hợp lệ không có
    # mục nào.
    cau_truc: CauTrucMauOut | None = None


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


# ══ GET /van-ban — danh sách văn bản theo bộ lọc (duyệt kho, không từ khoá) ═══
class VanBanTomTat(BaseModel):
    """Một dòng của `GET /van-ban`. `hieu_luc` là phán quyết KLAW cấp văn bản
    (`effectivity.danh_gia_toan_bo`), KHÔNG PHẢI `documents.tinh_trang`."""

    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    loai_van_ban: str
    co_quan_ban_hanh: str | None
    ngay_ban_hanh: date | None
    hieu_luc: HieuLucOut


class DanhSachVanBanResponse(BaseModel):
    # `tong` của TOÀN tập khớp bộ lọc, không phải của trang — trang Tra cứu hiện
    # "696 văn bản · Nghị định" và phải trùng số cạnh ô tick của `/bo-loc`.
    tong: int
    limit: int
    offset: int
    sap_xep: str
    ket_qua: list[VanBanTomTat]


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


class MucHanMuc(BaseModel):
    khoa: str
    nhan: str
    da_dung: int
    han_muc: int  # >= 100000 nghĩa là không giới hạn
    dat_lai_luc: datetime | None


class PhienHanMuc(BaseModel):
    luot_toi_da: int | None


class HanMucResponse(BaseModel):
    """Hạn mức của người gọi (spec 2026-09-07 §6.1). `ap_dung=False` khi Supabase chưa
    cấu hình: không đếm theo ai, `muc` rỗng — không bịa số 0."""

    ap_dung: bool
    plan: str | None
    ten_goi: str | None
    mui_gio: str
    muc: list[MucHanMuc]
    phien: PhienHanMuc
    het_han_luc: datetime | None
    bi_khoa: bool = False
    ghi_chu: str


class NguoiDungResponse(BaseModel):
    sub: str
    email: str | None
    plan: str


# ══ /hoi-thoai — phiên hội thoại theo tài khoản (spec 2026-09-07 §5.3) ═════════
class PhienTomTatOut(BaseModel):
    id: str
    tieu_de: str
    so_luot: int
    tao_luc: datetime
    cap_nhat_luc: datetime


class DanhSachPhienResponse(BaseModel):
    plan: str
    luot_moi_phien: int
    tong: int
    items: list[PhienTomTatOut]


class LuotDaLuuOut(BaseModel):
    thu_tu: int
    cau_hoi: str
    tra_loi: dict  # nguyên payload TraCuuResponse lúc trả lời
    trace_id: str | None
    tao_luc: datetime


class ChiTietPhienResponse(BaseModel):
    id: str
    tieu_de: str
    tao_luc: datetime
    cap_nhat_luc: datetime
    luot: list[LuotDaLuuOut]


class DoiTenPhienRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tieu_de: str = Field(..., min_length=1, max_length=120)


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


# ══ /han-muc v2, /ho-so, /nang-goi, /hoi-thoai/nhap (spec 2026-09-07 §6-8) ══


class HoatDongNgay(BaseModel):
    ngay: date
    so_luot: int


class PhanLoai(BaseModel):
    khoa: str
    nhan: str
    so: int


class HoSoResponse(BaseModel):
    email: str | None
    plan: str
    ten_goi: str
    tao_luc: datetime
    het_han_luc: datetime | None
    so_phien: int
    tong_hoi_dap: int
    tong_ban_thao: int
    hoat_dong: list[HoatDongNgay]
    phan_loai: list[PhanLoai]


class YeuCauNangGoiRequest(BaseModel):
    goi_muon: str = Field(..., min_length=1, max_length=32)


class YeuCauNangGoiOut(BaseModel):
    id: int
    loai: str
    goi_hien_tai: str
    goi_muon: str
    trang_thai: str
    tao_luc: datetime
    xu_ly_luc: datetime | None
    ly_do: str | None = None


class LuotNhap(BaseModel):
    cau_hoi: str = Field(..., min_length=1, max_length=2000)
    tra_loi: TraCuuResponse
    # `max_length` chứ không `str` trần: giá trị này đi thẳng vào JSONB, và một
    # `trace_id` dài 2 MB là 2 MB đĩa cho một trường vốn là một UUID.
    trace_id: str | None = Field(default=None, max_length=64)


# 256 KB. Mười lượt THẬT (câu hỏi ≤ 2000 ký tự + `TraCuuResponse` kèm trích dẫn)
# nằm dưới mức này rất xa — đo trên payload thật của `/hoi-thoai/nhap` là vài
# chục KB. Trần tồn tại vì `TraCuuResponse` có `answer`, `nguon`, `documents`,
# `bang` không giới hạn độ dài: `max_length=10` chặn SỐ lượt chứ không chặn
# KÍCH THƯỚC, nên trước trần này một tài khoản đã đăng nhập ghi được ~10 × 2 MB
# JSONB tuỳ ý cho mỗi request, ở nhịp của hạn mức tài khoản.
NHAP_PHIEN_TOI_DA_BYTE = 256 * 1024


class NhapPhienRequest(BaseModel):
    luot: list[LuotNhap] = Field(..., min_length=1, max_length=10)

    @model_validator(mode="after")
    def _kiem_kich_thuoc(self) -> "NhapPhienRequest":
        """Chặn ở BIÊN, không ở tầng ghi: 422 nói đúng rằng body sai, và không
        byte nào của nó chạm Postgres."""
        co = len(self.model_dump_json().encode("utf-8"))
        if co > NHAP_PHIEN_TOI_DA_BYTE:
            raise ValueError(
                f"Lịch sử gửi lên nặng {co // 1024} KB, vượt trần "
                f"{NHAP_PHIEN_TOI_DA_BYTE // 1024} KB. Gửi ít lượt hơn hoặc lượt ngắn hơn."
            )
        return self


class NhapPhienResponse(BaseModel):
    id: str


# ══ /admin — đường quản trị (spec 2026-09-08 cms-quan-ly-tai-khoan §5.3) ═════════
class LyDoRequest(BaseModel):
    ly_do: str = Field(..., min_length=1, max_length=500)


class DatGoiRequest(BaseModel):
    plan: str = Field(..., min_length=1, max_length=32)
    so_ngay: int | None = Field(default=None, ge=1, le=3650)  # None + gói trả phí = vô thời hạn


class DaDocRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=200)


class KetQuaGoiOut(BaseModel):
    sub: str
    plan: str
    plan_het_han: datetime | None


class YeuCauAdminOut(BaseModel):
    id: int
    user_sub: str
    email: str | None
    loai: str
    goi_hien_tai: str
    goi_muon: str
    trang_thai: str
    tao_luc: datetime
    xu_ly_luc: datetime | None
    xu_ly_boi: str | None
    ly_do: str | None
    plan_hieu_luc: str
    khoa_luc: datetime | None


class DanhSachYeuCauOut(BaseModel):
    tong: int
    items: list[YeuCauAdminOut]


class TaiKhoanTomTatOut(BaseModel):
    sub: str
    email: str | None
    plan: str  # gói HIỆU LỰC
    plan_het_han: datetime | None
    khoa_luc: datetime | None
    tao_luc: datetime
    so_phien: int
    luot_30_ngay: int


class DanhSachTaiKhoanOut(BaseModel):
    tong: int
    items: list[TaiKhoanTomTatOut]


class TaiKhoanChiTietOut(HoSoResponse):
    sub: str
    khoa_luc: datetime | None
    khoa_ly_do: str | None
    yeu_cau: list[YeuCauNangGoiOut]


class NhatKyOut(BaseModel):
    id: int
    hanh_dong: str
    doi_tuong: str | None
    chi_tiet: dict
    boi: str
    tac_nhan_loai: str
    ip: str | None
    tao_luc: datetime


class DanhSachNhatKyOut(BaseModel):
    tong: int
    items: list[NhatKyOut]


class TongQuanOut(BaseModel):
    tong_tai_khoan: int
    dang_ca_nhan: int
    cho_duyet: int
    het_han_7_ngay: int
    moi_7_ngay: int
    dang_khoa: int
    hoi_dap_hom_nay: int


class GoiOut(BaseModel):
    ma: str
    ten: str
    han_muc: dict[str, int]


class DanhSachGoiOut(BaseModel):
    goi: list[GoiOut]
    goi_mac_dinh: str
    chu_ky_pro_ngay: int


class ThongBaoOut(BaseModel):
    id: int
    loai: str
    tieu_de: str
    noi_dung: str
    duong_dan: str
    da_doc: bool
    tao_luc: datetime


class DanhSachThongBaoOut(BaseModel):
    so_chua_doc: int
    items: list[ThongBaoOut]
