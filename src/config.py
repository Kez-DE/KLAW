from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # `.env.local` là bản chạy trên máy (gitignored) và THẮNG `.env`: pydantic
        # đọc theo thứ tự, file sau ghi đè file trước. Trước bản này chỉ đọc
        # `.env` — file đó không tồn tại trong repo nên MỌI biến rơi về mặc định
        # trong code (sai DATABASE_URL, không có API key) mà không một dòng lỗi nào.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        # Các field cổng bảo vệ dùng `validation_alias="KLAW_*"`. KHÔNG có cờ
        # này, một alias làm field chỉ nhận được từ tên env — và
        # `Settings(_env_file=None, tran_chi_phi_ngay_usd=2.0)` (dạng mọi test
        # trong repo đang dùng) sẽ âm thầm giữ mặc định. Đúng chế độ hỏng mà
        # `__init__` dưới đây tồn tại để chặn, chỉ ở một cửa khác.
        populate_by_name=True,
    )

    def __init__(self, **kw: object) -> None:
        """`extra="ignore"` là CỐ Ý cho `.env` (nó chứa key của công cụ khác —
        LANGCHAIN_*, COHERE_API_KEY… — chặn chúng thì app không khởi động nổi),
        nhưng kwargs thì phải NỔ. `Settings(rrf_K=5)` từng lặng lẽ giữ mặc định
        `rrf_k=60`: đúng kịch bản sweep `rrf_k` qua `overlay_settings(**preset)`
        — một lần gõ nhầm là bốn hàng ablation bằng nhau và kết luận sai
        "rrf_k không ảnh hưởng". Kwargs `_`-prefixed là của pydantic (`_env_file`…).
        """
        la = {k for k in kw if not k.startswith("_")} - set(type(self).model_fields)
        if la:
            raise ValueError(f"Settings: field không tồn tại: {sorted(la)}")
        super().__init__(**kw)

    # App
    app_name: str = "KLAW API"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # OpenRouter — MỘT key, ba endpoint (spec 7b.1, 8.1)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_name: str = "mistralai/mistral-nemo"
    openrouter_generate_model_name: str = "google/gemini-2.5-flash-lite"
    openrouter_judge_model_name: str = "mistralai/mistral-small-3.2-24b-instruct"
    # `voyage-4-lite`, KHÔNG `bge-m3` (đo lại 2026-09-01 trên corpus 36.710 điều
    # khoản): Recall@5 0,7273 vs 0,5974. Cộng với bm25_topk=0 dưới đây, mặc định
    # cũ (`hybrid` + `bge-m3`) đo được 0,4740 — tức tổ hợp TỆ NHẤT trong bốn ô.
    openrouter_embedding_model_name: str = "voyageai/voyage-4-lite"
    openrouter_embedding_dim: int = Field(default=1024, gt=0)
    openrouter_rerank_model_name: str = "cohere/rerank-4-fast"
    openrouter_rerank_enabled: bool = False

    # temperature 0.0 — spec 8.1: bảng ablation phải tái lập được
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # Database
    database_url: str = "postgresql://klaw:klaw@localhost:5432/klaw"

    # Retrieval & chunking
    chunk_max_tokens: int = Field(default=1500, gt=0)
    # ge=0 (không phải gt=0): eval ablation (Task 9) tắt hẳn một nhánh bằng 0
    # để đo bm25_only/dense_only — 0 là giá trị hợp lệ, không phải lỗi cấu hình.
    # `0` = TẮT nhánh từ vựng. Không phải phỏng đoán: `scripts/sweep_fusion.py`
    # cho cực đại đúng tại `bm25_topk=0`, và CHỈ MỘT ứng viên từ vựng đã kéo
    # MRR@5 từ 0,4286 xuống 0,2604. `rrf` cộng đều (không có alpha để chỉnh),
    # nên không có cách "pha loãng" nhánh này — chỉ bật hoặc tắt.
    #
    # Vì sao tin được hướng này dù bộ golden chưa ai duyệt: bỏ rò rỉ từ vựng
    # khỏi golden làm nhánh lexical XẤU ĐI, tức nó CỦNG CỐ kết luận chứ không
    # tạo ra kết luận. Con số tuyệt đối vẫn chờ người duyệt 77 câu.
    retrieve_bm25_topk: int = Field(default=0, ge=0)
    retrieve_dense_topk: int = Field(default=20, ge=0)
    rrf_k: int = Field(default=60, gt=0)
    # ts_rank normalization bitmask (0=không chuẩn hoá, 1=chia 1+log(len),
    # 2=chia len, 4=mean harmonic distance, 32=rank/(rank+1); cộng dồn được).
    # Mặc định 0 của Postgres KHÔNG chuẩn hoá độ dài → top-k toàn chunk dài.
    # =1 chọn THEO ĐO, không đoán: sweep 5 giá trị × 2 (xem `scripts/sweep_bm25.py`,
    # bảng trong `eval/results/report.md`) cho 1 và 33 tốt nhất (Recall@5 0,2143 so
    # với 0,1299 của 0), 2 sụp hẳn (0,013 — chia thẳng độ dài phạt quá tay điều
    # luật dài). Lấy 1 chứ không 33 vì 32 chỉ chia rank+1: biến đổi đơn điệu, đổi
    # THANG ĐIỂM chứ không đổi THỨ TỰ, nên 33 cho y hệt 1 mà khó giải thích hơn.
    bm25_rank_normalization: int = Field(default=1, ge=0, le=63)
    # Bỏ hư từ tiếng Việt khỏi TRUY VẤN trước khi dựng tsquery — 'simple' không
    # có stopword list tiếng Việt nên hư từ thành lexeme và nối OR biến truy hồi
    # thành xếp hạng gần như cả corpus. Cũng chọn theo đo: bật cho +50% tương đối
    # ở MỌI mức normalization (0,2143 → 0,3117 tại normalization=1).
    bm25_strip_stopwords: bool = True
    retrieve_final_topk: int = Field(default=10, gt=0)
    # le=3: một giá trị sweep vô ý (Task 9 ablation) không còn cách nào làm
    # phình tập expand() không kiểm soát được (task-7 review, 2026-08-31).
    expand_reference_hops: int = Field(default=1, ge=0, le=3)

    # Verifier
    verify_tier2_enabled: bool = True
    abstain_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    # assemble.v2 là mặc định (đo 2026-09-06, eval.run_trap 51 câu — xem
    # cost-management.md). rewrite v2 còn TẮT (bật qua env REWRITE_PROMPT):
    # judge tầng 2 (verify_tier2) bị cắt JSON trên trap-soul-04 khi bật.
    assemble_prompt: str = "prompts/assemble.v2.md"
    rewrite_prompt: str = "prompts/rewrite_query.v1.md"
    # Router v2 trả thêm loại văn bản khi ý định là soạn thảo. Đổi qua env
    # `ROUTE_PROMPT=prompts/route.v2.md` để A/B; đổi mặc định sau khi bẫy xanh.
    route_prompt: str = "prompts/route.v1.md"
    # Cộng điểm mềm theo lĩnh vực sau RRF (spec §6). 0 = TẮT. Chỉ bật mặc định
    # sau một lượt đo graph-thật cho thấy Recall@10 không tụt.
    linh_vuc_bonus: float = Field(default=0.0, ge=0.0)
    as_of_date: date | None = None

    @field_validator("as_of_date", mode="before")
    @classmethod
    def _rong_la_hom_nay(cls, v):
        """`AS_OF_DATE=` để trống = dùng ngày hôm nay — đúng như `.env.example`
        ghi. Không có chỗ này, cách dùng ĐƯỢC TÀI LIỆU HOÁ lại làm app chết ngay
        lúc khởi động: pydantic nhận chuỗi rỗng từ dotenv và `date | None` không
        ép '' về None. Lỗi hiện ra là ValidationError khó đọc ở tầng Settings,
        không phải một câu nói rõ biến nào sai.
        """
        return None if isinstance(v, str) and not v.strip() else v

    # Eval
    eval_config_name: str = "full"
    eval_dataset_dir: str = "./eval/datasets"
    eval_result_dir: str = "./eval/results"

    # Data & ingest
    data_raw_dir: str = "./data/raw"
    data_seed_dir: str = "./data/seed"
    moj_api_base: str = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public"
    moj_rate_limit_sleep: float = Field(default=1.5, ge=0.0)

    # ══ Cổng bảo vệ (Plan 4) — tiền tố KLAW_ để tách khỏi họ biến cũ ═════════
    # Mặc định chọn theo SỐ ĐO trên DB thật, không theo cảm tính. Xem
    # `migrations/010_cong_bao_ve.sql` và `hardening-report.md` cho phép tính.

    # Rỗng = MỞ (dev local). Có giá trị = BẮT BUỘC header `X-API-Key` khớp trên
    # các endpoint tốn LLM. Ai là người dùng / đăng ký thế nào / phân quyền ra
    # sao là quyết định SẢN PHẨM chưa chốt — nên đây cố ý KHÔNG phải user/session.
    api_key: str = Field(default="", validation_alias="KLAW_API_KEY")

    # $2,00/ngày ≈ 10× ngày cao nhất đã đo ($0,18329 / 118 request, 2026-08-30)
    # ≈ 272 request ở mức đắt nhất đã ghi nhận ($0,00735). 0 = TẮT (cần cho
    # eval sweep chạy hàng trăm request qua HTTP) — phải đặt TAY, không phải
    # mặc định: mặc định vô hạn là đúng thứ rà soát bảo mật đã liệt kê.
    tran_chi_phi_ngay_usd: float = Field(
        default=2.0, ge=0.0, validation_alias="KLAW_TRAN_CHI_PHI_NGAY_USD"
    )

    # 10 lượt/60s/IP: `/tra-cuu` có p50 10s (đo trên 204 dòng traces) nên một
    # người dùng thật không vượt ~6 lượt/phút; 10 là 1,7× mức đó. Một vòng
    # `curl` bị hãm còn 10/phút = $4,41/giờ ở mức đắt nhất — trần ngày ở trên
    # dừng nó sau ~27 phút. Hai cổng CHỒNG nhau chứ không thay nhau.
    rate_limit_so_luot: int = Field(default=10, ge=0, validation_alias="KLAW_RATE_LIMIT_SO_LUOT")
    rate_limit_cua_so_giay: int = Field(
        default=60, gt=0, validation_alias="KLAW_RATE_LIMIT_CUA_SO_GIAY"
    )

    # Giỏ RIÊNG cho lá chắn chạy TRƯỚC xác thực (xem `bao_ve.cong_bao_ve`).
    # Nó có một việc: chặn lụt token rác, mỗi token `kid` lạ ép một round-trip
    # JWKS và giữ một luồng threadpool 5 giây (anyio mặc định 40 luồng). Nó
    # KHÔNG phải hạn mức của người dùng — hạn mức đó là `rate_limit_so_luot`,
    # đếm theo `sub` sau khi đã biết danh tính.
    #
    # Vì vậy nó phải RỘNG hơn nhiều: giỏ này đếm theo IP, mà một văn phòng sau
    # NAT là NHIỀU người trên MỘT IP — siết nó bằng hạn mức cá nhân là để người
    # thứ hai bị hãm vì lưu lượng của người thứ nhất (dự án đã có test khoá đúng
    # tính chất này). 60/60s: cần ~480/phút từ MỘT IP mới giữ nổi 40 luồng, nên
    # 60 hạ trần một-IP xuống ~5 luồng mà không chạm lưu lượng thật.
    #
    # `rate_limit_so_luot = 0` TẮT luôn cả giỏ này — MỘT công tắc cho cả tầng
    # nhịp, để `eval/run.py` không phải nhớ hai biến (quên một biến là bão 429
    # giữa một lượt đo).
    rate_limit_ip_so_luot: int = Field(
        default=60, ge=0, validation_alias="KLAW_RATE_LIMIT_IP_SO_LUOT"
    )

    # False = KHÔNG tin `X-Forwarded-For`. Bật CHỈ KHI thật sự có reverse proxy
    # đặt header đó: nếu tin mà không có proxy, bất kỳ ai cũng gửi một IP giả
    # mỗi request và rate limit theo IP trở thành trang trí.
    tin_proxy_header: bool = Field(default=False, validation_alias="KLAW_TIN_PROXY_HEADER")

    # Số proxy TIN CẬY đứng trước ứng dụng. Chỉ có nghĩa khi `tin_proxy_header`
    # bật. Mỗi proxy NỐI THÊM địa chỉ nó thấy vào CUỐI `X-Forwarded-For`, nên
    # phần tử ĐẦU là phần kẻ gọi tự viết và không được tin bao giờ; client thật
    # nằm ở vị trí thứ N từ PHẢI với N = số hop này. Đặt sai theo hướng LỚN hơn
    # thực tế thì `ip_goi` rơi về địa chỉ peer (chặn), đặt sai theo hướng NHỎ
    # hơn thì nó đọc trúng địa chỉ một proxy — cả hai đều không cho kẻ gọi tự
    # chọn giỏ đếm của mình, khác hẳn việc lấy phần tử đầu.
    so_hop_proxy_tin_cay: int = Field(
        default=1, ge=1, validation_alias="KLAW_SO_HOP_PROXY_TIN_CAY"
    )

    # 7 ngày. 0 = TẮT — bắt buộc phải có: `eval/run.py` đo latency/chi phí thật
    # thì không được đo qua cache.
    cache_ttl_ngay: int = Field(default=7, ge=0, validation_alias="KLAW_CACHE_TTL_NGAY")
    # 90 ngày: đủ dài để điều tra một sự cố hiệu năng hay chi phí bất thường
    # (cửa sổ dài nhất từng cần trong phiên đo là vài ngày), đủ ngắn để không
    # giữ câu hỏi GẮN TÊN của người dùng hàng năm trời. `0` = TẮT, theo đúng
    # quy ước của các bộ đếm khác trong file này.
    traces_an_danh_sau_ngay: int = Field(
        default=90, ge=0, validation_alias="KLAW_TRACES_AN_DANH_SAU_NGAY"
    )

    # ══ Auth Supabase (Plan 4b) ══════════════════════════════════════════════
    # Supabase chỉ làm AUTH (Google + Microsoft); dữ liệu ở lại Postgres này.
    #
    # RỖNG = auth TẮT, hệ thống hoạt động ĐÚNG NHƯ TRƯỚC. Đây là công tắc bảo vệ
    # số liệu khoá luận: `eval/run.py` chạy hàng trăm lượt và không được cần một
    # tài khoản Supabase. Có giá trị (`https://<ref>.supabase.co`) ⇒ `/tra-cuu`
    # và `/soan-thao` BẮT BUỘC `Authorization: Bearer <JWT>`, và hạn mức chuyển
    # từ theo-IP sang theo-NGƯỜI.
    #
    # `iss` và URL JWKS SUY RA từ đây (`xac_thuc.issuer`/`jwks_url`), không phải
    # hai biến riêng: hai biến phải-khớp-nhau là một biến cộng một cách cấu hình
    # sai (pin `iss` sang project khác project đang phát khoá → từ chối tất cả).
    supabase_url: str = Field(default="", validation_alias="KLAW_SUPABASE_URL")

    # `aud` của access token Supabase là `authenticated` cho người đã đăng nhập
    # (`anon` là token KHÁCH — cố ý không chấp nhận). Để cấu hình được vì đây là
    # giá trị của nhà cung cấp, không phải bất biến của dự án này.
    supabase_jwt_aud: str = Field(
        default="authenticated", validation_alias="KLAW_SUPABASE_JWT_AUD"
    )

    # 600s = đúng TTL cache JWKS ở tầng edge của Supabase, để không dựng một tầng
    # cache lệch pha với nhà cung cấp. Ngắn hơn = khoá bị thu hồi lan nhanh hơn
    # nhưng thêm round-trip trên đường request nóng.
    supabase_jwks_ttl_giay: int = Field(
        default=600, gt=0, validation_alias="KLAW_SUPABASE_JWKS_TTL_GIAY"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def as_of_hieu_luc(yeu_cau: date | None) -> date:
    """Mốc thời gian TÍNH HIỆU LỰC cho một request: request → settings → hôm nay.

    MỘT chỗ duy nhất quyết định quy tắc này, dùng bởi cả `graph_tra_cuu.n_expand`
    (nơi mốc được ÁP DỤNG) và khoá cache (nơi mốc được GHI NHỚ). Hai bản sao của
    quy tắc là cách chắc chắn để cache bắn nhầm: cache khoá theo một ngày, graph
    lọc hiệu lực theo một ngày khác, và không tầng nào báo lỗi — chỉ trả về hiệu
    lực sai. Cùng lý do `verify_tier1.normalize` được TÁI DÙNG chứ không viết lại.
    """
    return yeu_cau or get_settings().as_of_date or date.today()
