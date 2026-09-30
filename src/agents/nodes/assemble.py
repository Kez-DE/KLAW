"""Node assemble — quyết định một trong BỐN loại kết quả (spec 6.2). Đây là nơi
mọi thứ hội tụ thành câu trả lời người dùng đọc, và là nơi lời hứa của khoá
luận (nguồn gốc + nguyên văn, KHÔNG bảo đảm là bản hiện hành) hiện ra hoặc bị
phản bội.

answer            : có claim qua cả hai tầng, tỉ lệ verified ≥ ngưỡng
partial_coverage  : chỉ trúng tầng nông → nêu luật, không dựng lời giải thích
abstain           : không có căn cứ dùng được. HÀNH VI ĐÚNG, không phải lỗi
out_of_scope      : route xác định ngoài phạm vi. 0 TOKEN

Từ 2026-09-02 mọi ngõ cụt đi qua `_ngo_cut` và có HAI NỬA: nửa đầu nói cái ĐÃ
biết (tên văn bản chi phối, vị trí điều khoản đọc được), nửa sau hỏi lại đúng
dữ kiện tình huống còn thiếu (`hoi_lai.py`). Trước đó `abstain` trả về
`answer=None`, `coverage_note=None`, `nguon=[]` — một MÀN HÌNH TRẮNG, đo được
trên câu "Hiện tại có bao nhiêu bộ luật?" với `deep=30`, `claims=0`.

Đổi này làm `partial_coverage` và các nhánh abstain KHÔNG còn 0 token: mỗi ngõ
cụt nay tiêu MỘT lượt gọi để sinh câu hỏi lại. Chú thích "0 TOKEN" ở hai nhánh
ấy đã bị gỡ có chủ ý, không phải bỏ sót. Cái KHÔNG đổi: LLM HÀNH VĂN — vai dựng
câu trả lời có trích dẫn — vẫn không bao giờ được gọi trên một ngõ cụt
(`test_*_KHONG_goi_LLM_hanh_van`).

Phase 14 (R6, quyết định owner) thêm một vai THỨ BA cho các ngõ cụt "truy hồi
không cho gì kiểm chứng được": `giai_thich_chung` — mô hình giải thích CHUNG
bằng kiến thức của nó (khái niệm là gì, thủ tục thường ra sao), KHÔNG một số
Điều/Khoản/số hiệu/mốc pháp lý nào (lưới 0 token loại cả lời khi vướng, dùng
lại `hoi_lai.bi_loai` — xem chú thích ở `giai_thich_chung`), đi vào `answer`
trong khi `result_type` vẫn là `abstain`. Nới điều được NÓI, không nới điều
được TRÍCH DẪN: một trích dẫn chỉ có thể là một neo đã qua hai tầng kiểm.

Và cái tuyệt đối không đổi: pha này đổi LỜI của abstain, KHÔNG đổi KHI NÀO
abstain. `abstain_threshold` và mọi điều kiện quyết định `result_type` giữ
nguyên từng chữ — việc hệ thống dừng lại khi thiếu căn cứ là đóng góp trung tâm
của đề tài, và một lời lẽ dễ nghe hơn không được phép mua bằng cách nới nó.

`intent == soan_thao` KHÔNG có nhánh riêng — nó rơi vào đúng pipeline
tra_cuu-shaped bên dưới (chỉ `ngoai_pham_vi` mới lập tức ra out_of_scope):
coverage_note của out_of_scope tự nói "soạn thảo chỉ trong lĩnh vực lao động",
nghĩa là soạn thảo vẫn cần câu trả lời được neo bằng trích dẫn đã kiểm chứng
giống hệt tra cứu, không phải một tính năng tách rời.

Cảnh báo hiệu lực PHẢI chịu tải: Plan 1 đo được cả 6 nghị định lương tối thiểu
liên quan trên MOJ chỉ có PDF scan (`hasContent: false`), và MOJ tự đánh 4/6
nghị định đã bị thay thế là "còn hiệu lực". Task 2 sửa được cả 4, và khi verdict
rơi vào `CANH_BAO_NHAN` người dùng phải thấy cảnh báo cạnh trích dẫn, nêu đích
danh văn bản sửa đổi/thay thế. Từ quyết định 2026-09-28 (mục 10) câu đó là LỜI
CHO NGƯỜI ĐỌC (`hien_thi.canh_bao`), không phải `ly_do` nguyên văn: không mã
tình trạng, không "độ tin cậy", không ngày ISO.
"""

import json
import logging
import re
from enum import StrEnum
from pathlib import Path, PurePath
from typing import TypedDict

from src.agents.graph_soan_thao import cac_loai, load_checklist_cached
from src.agents.nodes.dung_ban_thao_tong_quat import KHONG_SOAN_DUOC, LOAI_TONG_QUAT, TEN_TONG_QUAT, _ket_state
from src.agents.nodes.gioi_thieu import cau_gioi_thieu
from src.agents.nodes.hieu_tai_lieu import CHO_TRONG, MUC_DICH_SOAN
from src.agents.nodes.hoi_lai import bi_loai, cau_hoi_lai_tu_khung, duoi_hoi_them, duoi_tu_khung, hoi_lai
from src.agents.nodes.verify_tier1 import normalize, van_ban_neo_boi_ten
from src.models.schemas import Bang
from src.services import khuon_mau
from src.services.bao_ve import LOI_SOAN_THAO_DANG_NHAP
from src.services.bo_nho import ho_so_da_dung, khoi_tinh_huong
from src.services.effectivity import EffectivityVerdict as V
from src.services.hien_thi import canh_bao, cau_van_ban_an
from src.services.kho import hien_van_ban, moi_so_hieu_trong
from src.services.khuon_mau import can_cu_hien
from src.services.llm import Usage
from src.services.prompts import messages
from src.services.trich_dan import truong_trich_dan

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/assemble.v1.md")

# Trần hình dạng (spec 2026-09-16 §FR-006/FR-007/FR-019/FR-020). Cưỡng chế 0
# token: gọi lại mô hình để viết ngắn hơn là thêm một lượt gọi trong đường
# thành công thường, thứ `cai_thien.md` §11 cấm.
TRAN_GACH = 4
TRAN_KY_TU = 900

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}

# Khớp mặc định của Settings.abstain_threshold (src/config.py) — GIẢ ĐỊNH cần
# xác nhận, KHÔNG được tinh chỉnh trên tập báo cáo (chỉ trên tập dev tách
# riêng). state["abstain_threshold"] ghi đè được cho graph thật; hằng số này
# chỉ là fallback khi state không mang nó (vd. gọi assemble() đơn lẻ).
ABSTAIN_THRESHOLD_DEFAULT = 0.5

# Spec 2026-09-06 §5.3 — hai lời mở cho `{mo_dau}` của assemble.v2. Chào chỉ ở
# lượt đầu; bẫy `chao_dung_luot` (eval/run_trap) đo điều này.
MO_DAU_LUOT_DAU = (
    "Đây là lượt đầu của cuộc trò chuyện: mở bằng một cụm chào ngắn, tự nhiên "
    '("Chào bạn,") nối LIỀN vào câu trả lời thẳng — không thành câu riêng, không '
    '"rất vui được hỗ trợ".'
)
MO_DAU_NOI_TIEP = "Đây là lượt nối tiếp: KHÔNG chào, vào thẳng câu trả lời."

# ══ GĐ3 (cai_thien.md §6) — vai trò căn cứ và mức chắc ══════════════════════
# Thứ tự ưu tiên khi xếp căn cứ vào lời nhắc hành văn: kết luận trước, rồi điều
# kiện, ngoại lệ, chế tài; claim KHÔNG mang vai trò (prompt sinh v2) xếp cuối và
# KHÔNG kích hoạt đường này (xem `_chon_cho_prose`).
_HANG_VAI_TRO = {"ket_luan": 0, "dieu_kien": 1, "ngoai_le": 2, "che_tai": 3}

# Nhãn ĐỌC ĐƯỢC của vai trò, chỉ dùng trong lời nhắc hành văn (prompt v6 in ra
# "(kết luận)"). Mã máy (`ket_luan`) không bao giờ tới mắt mô hình.
_VAI_TRO_HIEN = {"ket_luan": "kết luận", "dieu_kien": "điều kiện",
                 "ngoai_le": "ngoại lệ", "che_tai": "chế tài"}

# Chế tài chỉ vào văn xuôi khi người hỏi hỏi hậu quả (cai_thien.md §6 GĐ3 quy
# tắc 4) — hoặc khi bỏ nó đi thì còn quá ít căn cứ để trả lời.
_RE_HOI_CHE_TAI = re.compile(r"phạt|xử lý|chế tài|hậu quả|vi phạm|bị gì|trách nhiệm", re.IGNORECASE)

# Trần claim vào LỜI NHẮC hành văn (§6 GĐ3 quy tắc 7). Khác `TRAN_GACH` (trần
# GẠCH của câu trả lời phát hành): mô hình được thấy nhiều hơn số nó được viết ra.
TOI_DA_CLAIM_PROSE = 6

# Hai mức chắc — TÍNH BẰNG MÃ từ vai trò claim và dữ kiện quyết định còn thiếu,
# không phải điểm tự tin của mô hình (CONTEXT.md, glossary "mức chắc"). Chuỗi đi
# vào prompt là LỜI DẶN GIỌNG, không phải mã máy.
MUC_CHAC_LOI = {
    "chac": "CHẮC — nói khẳng định.",
    "co_dieu_kien": ("CÓ ĐIỀU KIỆN — mở kết luận bằng điều kiện hoặc 'Nếu … thì …'; "
                     "không viết như đã chắc."),
}

# Nửa đầu của ngõ cụt khi MỌI căn cứ đã kiểm chứng đều bị tầng 2 chấm là lạc đề.
# KHÔNG dùng `_ly_do_moi_nguon_bi_thay` cho ca này: nguồn ở đây còn hiệu lực,
# cái thiếu là nó không trả lời đúng điều được hỏi — nói "đã bị thay thế" là nói sai.
LAC_DE = ("Những gì tôi tìm được cùng chủ đề với câu hỏi, nhưng không trả lời đúng điều "
          "bạn cần, nên tôi không dựng câu trả lời từ đó.")


def _van_ban_dung_cho_prose(citations_prose: list[dict], db: dict[int, dict]) -> list[tuple[dict, dict]]:
    """`(citation, dòng db)` của văn bản ĐẦU TIÊN xuất hiện theo `doc_id`, khử
    trùng, giữ thứ tự — tập mô hình được phép đặt thẻ `doc`."""
    ra, da = [], set()
    for c in citations_prose:
        if c["doc_id"] in da:
            continue
        da.add(c["doc_id"])
        ra.append((c, db[c["khop_tai_id"]]))
    return ra


def _khoi_van_ban(citations_prose: list[dict], db: dict[int, dict]) -> str:
    """Khối `{van_ban}`: `[doc:ID] tên — số hiệu — loại văn bản`. KHÔNG có ngày
    (Q2) — ngày hiệu lực của văn bản gốc đứng cạnh nhãn `bi_sua_doi` gây hiểu
    nhầm, và nhãn cạnh trích dẫn đã nói đủ."""
    return "\n".join(
        f"[doc:{c['doc_id']}] {c['bo_luat']} — {c['so_ky_hieu']} — {p.get('loai_van_ban') or ''}"
        for c, p in _van_ban_dung_cho_prose(citations_prose, db)
    )


def _dung_documents(citations_prose: list[dict], db: dict[int, dict]) -> list[dict]:
    """`documents[]` của response (khớp `schemas.DocumentOut`). Link lấy từ ba
    cột migration 019; NULL đi nguyên qua để giao diện bỏ dòng đó. Trường trích
    dẫn đầy đủ (quyết định 2026-09-28) ở cấp VĂN BẢN — không có vị trí điều khoản."""
    return [
        {
            **truong_trich_dan(p),
            "doc_id": c["doc_id"],
            "ten": c["bo_luat"],
            "so_ky_hieu": c["so_ky_hieu"],
            "loai_van_ban": p.get("loai_van_ban") or "",
            "links": {"vbpl": p.get("link_vbpl"), "chinhphu": p.get("link_chinhphu"), "tvpl": p.get("link_tvpl")},
        }
        for c, p in _van_ban_dung_cho_prose(citations_prose, db)
    ]


# Ba verdict brief đòi hỏi tường minh (bi_thay_the/het_hieu_luc/mot_phan_khong_xac_dinh)
# cộng chua_hieu_luc (chưa có hiệu lực — người hỏi cần biết), can_doi_chieu_tay
# (nghi lỗi dữ liệu MOJ), và chua_xac_dinh (RULING 2026-08-31: im lặng ở đây bị
# đọc thành "ổn" — với một hệ thống bảo đảm nguồn gốc/nguyên văn nhưng KHÔNG bảo
# đảm bản hiện hành, "tôi không biết còn hiệu lực không" PHẢI nói ra, không được
# giấu bằng cách rơi vào nhánh im lặng). KHÔNG gồm con_hieu_luc — đúng nghĩa của
# nó là "không có tín hiệu chấm dứt nào", không cảnh báo.
#
# Giá trị CHỈ LÀ NHÃN NGẮN để phân loại — câu cảnh báo THẬT là
# `hien_thi.canh_bao` (quyết định 2026-09-28 mục 10), nêu đích danh văn bản sửa
# đổi/thay thế từ `Effectivity.van_ban`, không bao giờ `ly_do` nguyên văn.
CANH_BAO_NHAN = {
    V.mot_phan_khong_xac_dinh: "hết hiệu lực một phần",
    # Mức 4 — bản đồ sửa đổi cấp điều khoản (VBHN của Công báo). Đây là bản
    # CHÍNH XÁC HƠN của `mot_phan_khong_xac_dinh` ngay trên: nó nêu đích danh
    # điều khoản nào, bị văn bản nào sửa, từ ngày nào. Bảng này là WHITELIST nên
    # verdict mới mặc định IM LẶNG — thiếu dòng này thì đúng những điều khoản ta
    # biết rõ nhất lại thành những điều khoản duy nhất không cảnh báo gì, tức
    # một cải tiến biến thành hồi quy.
    V.bi_sua_doi: "đã bị sửa đổi",
    V.bi_thay_the: "đã bị thay thế",
    V.het_hieu_luc: "đã hết hiệu lực",
    V.chua_hieu_luc: "chưa có hiệu lực",
    V.can_doi_chieu_tay: "cần đối chiếu tay",
    V.chua_xac_dinh: "chưa xác định được hiệu lực",
}


class ResultType(StrEnum):
    answer = "answer"
    partial_coverage = "partial_coverage"
    abstain = "abstain"
    out_of_scope = "out_of_scope"
    # Loại thứ NĂM. Bốn loại kia mô tả điều gì đã xảy ra với một lượt TRA CỨU;
    # loại này nói rằng câu hỏi không phải một lượt tra cứu. Tách ra thay vì
    # mượn `out_of_scope` vì hai câu dưới đây đáng nhận hai lời đáp khác nhau:
    #   "Thuế thu nhập cá nhân tính thế nào?" → ngoài phạm vi thật, từ chối đúng
    #   "bạn làm được những gì"               → hỏi về trợ lý, phải trả lời
    gioi_thieu = "gioi_thieu"
    # Xin SOẠN một văn bản. Trước bản này `intent == soan_thao` không có nhánh
    # riêng nên rơi thẳng vào đường tra cứu, và người hỏi "soạn cho tôi hợp
    # đồng lao động" nhận về một bài giảng về Điều 20 — đúng luật, và không
    # phải thứ họ xin.
    # Phase 14: không lượt nào sinh ra loại này nữa (mô hình soạn thay vì chỉ
    # sang biểu mẫu, xem `_ban_thao_tong_quat`); giữ giá trị để payload cache
    # cũ và giao diện còn hợp lệ.
    huong_dan_soan_thao = "huong_dan_soan_thao"
    # Câu hỏi về CHÍNH KHO. Cùng lý do tách như `gioi_thieu` ngay trên: nó
    # không phải một lượt tra cứu, và câu trả lời là một phép TRA BẢNG xác
    # định (`services/kho.py`) chứ không phải một luận điểm cần hai tầng kiểm.
    hoi_ve_kho = "hoi_ve_kho"
    # Loại thứ SÁU và thứ BẢY (Task 19, soạn thảo trong chat) — hai nửa của
    # đúng MỘT hội thoại soạn thảo, không phải hai tính năng riêng: hoặc còn
    # thiếu dữ kiện (hay chưa đăng nhập, hay hết hạn mức) và phải hỏi thêm
    # (`soan_thao_hoi`), hoặc đã đủ và `dung_ban_thao` đã dựng xong một bản
    # thảo thật để trả về (`ban_thao`). Tách khỏi `huong_dan_soan_thao` (vẫn
    # còn, dùng khi router không đoán được LOẠI văn bản nào) vì FE cần biết
    # có nên vẽ khung "hỏi thêm"/"xem bản thảo" hay khung "chọn loại" cũ.
    soan_thao_hoi = "soan_thao_hoi"
    ban_thao = "ban_thao"
    # Loại thứ TÁM (plan `tai-lieu-tong-quat.md`) — lượt nói về TÀI LIỆU của
    # người hỏi, không về nội dung pháp luật. Tách khỏi `answer` vì nó không
    # mang một trích dẫn điều luật nào: bằng chứng của nó là neo về chính tài
    # liệu vừa đọc, và gộp hai thứ lại là để một câu trả lời không có căn cứ
    # pháp lý trông y hệt một câu trả lời đã qua hai tầng kiểm chứng.
    tai_lieu = "tai_lieu"


# Spec 2026-09-16 §2.6/§3.5/FR-007 — bốn nhánh KHÔNG đọc `ho_so` để dựng câu trả
# lời, nên trả `ho_so_da_dung=[]` trong `_base`: hiện mảng này ("Dựa trên") thì
# là provenance sai, dù state có hồ sơ. `tai_lieu` cùng lý do: câu trả lời dựng
# từ chữ trong tài liệu, không từ hồ sơ tình huống.
_KHONG_DUNG_HO_SO = frozenset({ResultType.gioi_thieu, ResultType.hoi_ve_kho, ResultType.out_of_scope,
                               ResultType.tai_lieu})


class Citation(TypedDict):
    """Dict thường (TypedDict chỉ để gõ kiểu) — test tra bằng `c["so_ky_hieu"]`.

    `provision_id` và `khop_tai_id` có thể trỏ HAI DÒNG KHÁC NHAU (coordinator
    review 2026-08-31): `provision_id` là điều luật claim ĐÃ DẪN
    (`claim.provision_id`); `khop_tai_id` là dòng THẬT chứa quote khớp được —
    và `duong_dan`/`bo_luat`/`so_ky_hieu` LUÔN hiển thị theo `khop_tai_id`, không
    phải theo `provision_id`. Khi `khop_tai_id != provision_id`: mô hình dẫn
    Điều cha còn căn cứ nằm ở Khoản con — HÀNH VI BÌNH THƯỜNG, không phải lỗi,
    vì 73,6% số Điều trong corpus có `noi_dung` chỉ là tiêu đề (xem
    verify_tier1.py `_cay_con`). Trước bản này chỉ có `provision_id`, khiến
    chuỗi `duong_dan` hiển thị và trường dùng để tra cứu lệch nhau mà không
    trường nào trong citation nói cho người tiêu thụ (Plan 4/5) biết.
    """

    provision_id: int
    khop_tai_id: int
    # `documents.id` (TEXT). FE dựng URL click-to-verify từ đây:
    # `GET /api/v1/van-ban/{doc_id}?around={khop_tai_id}`. Không có nó, citation
    # chỉ có `so_ky_hieu` — không đủ để mở panel đối chiếu.
    doc_id: str
    duong_dan: str
    bo_luat: str
    so_ky_hieu: str
    quote: str
    hieu_luc: str | None
    tin_cay: str | None
    # Số thứ tự căn cứ trong văn xuôi (thẻ `cite:K`) — khớp `schemas.CitationOut.k`.
    k: int | None


def _base(state: dict, rt: ResultType, usage: Usage | None = None, degraded: bool = False, **kw: object) -> dict:
    """Khung chung cho mọi loại kết quả — MỌI nhánh đều ghi `traces` (Global
    Constraint), kể cả các nhánh 0 token: `assemble_token_*=0` không chỉ là giá
    trị mặc định, nó là BẰNG CHỨNG đo được cho tuyên bố "0 TOKEN" trong docstring
    module, không phải một lời khẳng định suông.

    Bốn nhánh còn 0 token sau Pha 2: `out_of_scope`, `gioi_thieu`,
    `huong_dan_soan_thao`, `hoi_ve_kho`. Các ngõ cụt (`abstain`,
    `partial_coverage`) nay tiêu một lượt sinh câu hỏi lại — xem `_ngo_cut`.
    """
    prior_traces = state.get("traces") or {}
    return {
        **state,
        "result_type": rt,
        "answer": None,
        "citations": [],
        # `nguon` KHÁC `citations`: citations là trích dẫn ĐÃ QUA hai tầng kiểm,
        # nguon chỉ là "văn bản nào chi phối câu hỏi này" — đủ để mở mục lục,
        # không kèm quote vì chưa có gì được kiểm chứng để trích. Chỉ nhánh
        # `partial_coverage` điền; các nhánh khác giữ rỗng.
        "nguon": [],
        "warnings": [],
        "coverage_note": None,
        # rt in _KHONG_DUNG_HO_SO never reads the profile, so showing "Dựa
        # trên" would be false provenance (ex.md FR-007).
        "ho_so_da_dung": [] if rt in _KHONG_DUNG_HO_SO else ho_so_da_dung(state.get("ho_so") or {}),
        "traces": {
            **prior_traces,
            "assemble_result_type": rt.value,
            "assemble_degraded": degraded,
            "assemble_token_in": usage.token_in if usage else 0,
            "assemble_token_out": usage.token_out if usage else 0,
            "assemble_cost_usd": usage.cost_usd if usage else 0.0,
        },
        **kw,
    }


# Phép kiểm THỨ NĂM (coordinator, sau khi đo tập bẫy — task-10 round 3): bốn
# phép kiểm của verify_tier1 xác minh CITATION OBJECT (provision_id/quote),
# không cái nào nhìn vào chính văn xuôi `answer`. Đo được trên
# `trap-nonexist-09`: assemble lấy đúng nội dung đã verify từ Điều 363-365
# nhưng viết prose gán cho "Điều 550" — số Điều BỊA ngay trong câu hỏi, không
# phải từ citation. Đo lại 6 lần trên 3 câu: GIÁN ĐOẠN (1/6), không hệ thống —
# nguy hiểm hơn một lỗi luôn xảy ra vì không hiện đều trong test.
#
# Vẫn là TRA BẢNG, 0 TOKEN: rút số Điều trong `answer` bằng regex, so với tập
# số Điều có trong `citations` ĐÃ QUA CẢ HAI TẦNG — không suy luận ngữ nghĩa.
LY_DO_DIEU_KHONG_CHONG_DO = "dieu_nhac_trong_answer_khong_co_trong_citation_da_xac_minh"

_RE_DIEU = re.compile(r"[Đđ]iều\s+(\d+)")


def _so_dieu_trong(text: str) -> set[str]:
    """Tập số Điều (chuỗi) nhắc trong `text`, sau CHUẨN HOÁ (`normalize` của
    verify_tier1 — corpus có `Ð` U+00D0 và không thuần NFC). Dùng CHUNG cho cả
    `answer` (văn xuôi) và `citations[].duong_dan` (định danh có cấu trúc, vd.
    "45/2019/QH14 > Điều 35 > Khoản 1"), để hai phía so được bằng đúng MỘT quy
    tắc trích số — không phải hai cách đọc khác nhau."""
    return set(_RE_DIEU.findall(normalize(text or "")))


def _dieu_khong_duoc_chong_do(answer: str, citations: list) -> list[str]:
    """Số Điều nào NHẮC trong `answer` mà KHÔNG nằm trong tập số Điều của các
    `citations` đã qua tầng 1+2. Rỗng nghĩa là mọi số Điều trong answer đều có
    căn cứ, HOẶC answer không nhắc số Điều nào — cả hai đều AN TOÀN (xem test).

    Cố ý so THEO SỐ, không theo (văn bản, số) — đúng nguyên văn yêu cầu của
    coordinator ("mọi số điều nhắc trong answer phải nằm trong tập trích dẫn
    đã xác minh"). Giới hạn đã biết: hai văn bản khác nhau trùng số Điều sẽ
    khiến một câu trả lời đúng-mã-sai-nguồn lọt qua — chưa đo được ca này xảy
    ra trong tập bẫy, nâng cấp lên cặp (văn bản, số) nếu có ca đo được cần nó.
    """
    trong_answer = _so_dieu_trong(answer)
    if not trong_answer:
        return []
    trong_citation: set[str] = set()
    for c in citations:
        trong_citation |= _so_dieu_trong(c.get("duong_dan", ""))
    return sorted(trong_answer - trong_citation, key=int)


# ══ Phép kiểm thứ TÁM và thứ CHÍN (spec 2026-09-06 §5.4) — thẻ và URL ═════════
# Mô hình chỉ đặt `[chữ](doc:ID)` / `[chữ](cite:K)`; backend tra bảng rằng ID
# nằm trong tập văn bản đã dùng, K nằm trong [1, n] và "Điều N" trong chữ hiển
# thị trùng Điều của chính căn cứ K. Một URL trong `answer` LUÔN là lỗi: đường
# dẫn cổng luật do DB điền vào `documents[].links`, không bao giờ do mô hình.
# Vẫn 0 token, vẫn tra bảng — không suy luận ngữ nghĩa.
LY_DO_THE_KHONG_HOP_LE = "the_hoac_url_trong_answer_khong_hop_le"

_RE_THE = re.compile(r"\[([^\]]+)\]\((doc|cite):([^)\s]+)\)")
_RE_URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:vn|com|net|org|gov)\b", re.I)


def cat_gach_thua(answer: str, tran: int = TRAN_GACH) -> tuple[str, int]:
    """Bỏ gạch cấp một thứ `tran`+1 trở đi, kèm dòng lồng của chính chúng.

    Trả `(văn bản, số gạch đã bỏ)`. KHÔNG cắt theo ký tự: một lát cắt giữa câu
    sẽ chặt đứt thẻ `[...](cite:n)` đang mở và biến một câu trả lời hợp lệ thành
    một câu có thẻ hỏng — tệ hơn hẳn một câu dài. Trần ký tự vì thế chỉ được GHI
    NHẬN (`traces.assemble_hinh_dang`), không cưỡng chế bằng kéo.

    Chỉ dòng BẮT ĐẦU bằng `- ` mới tính là gạch: một dấu gạch nối giữa câu
    ("người lao động - theo Điều 26 - được biết") không phải một gạch đầu dòng.
    """
    giu: list[str] = []
    bo = so_gach = 0
    dang_bo = False
    for dong in (answer or "").split("\n"):
        if dong.startswith("- "):
            so_gach += 1
            dang_bo = so_gach > tran
            if dang_bo:
                bo += 1
                continue
        elif dang_bo and dong.strip() and dong[:1].isspace():
            continue  # dòng lồng thuộc về gạch vừa bị bỏ
        else:
            dang_bo = False
        giu.append(dong)
    return "\n".join(giu), bo


def _the_khong_hop_le(answer: str, citations_prose: list[dict], doc_ids: set[str]) -> list[str]:
    """Danh sách lỗi; rỗng = hợp lệ. Mỗi mục là nhãn tra được trong traces:
    `url`, `doc:<ID>`, `cite:<K>`, `cite:<K>≠[<Điều của căn cứ K>]`."""
    loi: list[str] = []
    van = answer or ""
    if _RE_URL.search(van):
        loi.append("url")
    for chu, loai, khoa in _RE_THE.findall(van):
        if loai == "doc":
            if khoa not in doc_ids:
                loi.append(f"doc:{khoa}")
            continue
        if not khoa.isdecimal() or not 1 <= int(khoa) <= len(citations_prose):
            loi.append(f"cite:{khoa}")
            continue
        dieu_the = _so_dieu_trong(chu)
        dieu_can_cu = _so_dieu_trong(citations_prose[int(khoa) - 1].get("duong_dan", ""))
        if dieu_the and not dieu_the <= dieu_can_cu:
            loi.append(f"cite:{khoa}≠{sorted(dieu_can_cu, key=int)}")
    return loi


# ══ GĐ5 — điều khoản của người hỏi trong khối tình huống ═════════════════════
# Điều khoản đi vào ĐÚNG ô `{tinh_huong}` mà mọi prompt hành văn đã gắn sẵn nhãn
# "dữ kiện họ cung cấp …, KHÔNG phải căn cứ". Không thêm một ô mới, và không sửa
# một prompt đã phát hành nào: một ô thứ hai cho cùng loại nội dung là cơ hội để
# một bản prompt sau quên mất nhãn, và chính cái nhãn ấy là toàn bộ lời hứa của
# nhánh đối chiếu — tài liệu của người hỏi không bao giờ là căn cứ pháp lý.
NHAN_DIEU_KHOAN_TAI_LIEU = "Điều khoản trong tài liệu của người hỏi (dữ kiện, KHÔNG phải căn cứ):"
# Đủ để nhận ra điều khoản, không đủ để một tài liệu dài đẩy căn cứ ra khỏi tầm
# chú ý của mô hình. Cắt ở đây là cắt thứ ĐI VÀO lời nhắc; `tai_lieu_neo` phát
# hành ra giao diện vẫn mang đoạn trích đầy đủ.
TRICH_DIEU_KHOAN_TOI_DA = 200


def khoi_tinh_huong_doi_chieu(ho_so: dict, tai_lieu_neo: list[dict]) -> str:
    """`{tinh_huong}` của một lượt đối chiếu: hồ sơ tình huống như mọi lượt, cộng
    các điều khoản ĐÃ NEO dưới một nhãn nói rõ chúng là dữ kiện.

    Không có điều khoản nào (mọi lượt khác) thì trả về đúng chuỗi cũ, từng ký tự
    — các prompt đang được đo không được đổi nội dung vì một nhánh chúng không
    chạy qua.
    """
    khoi = khoi_tinh_huong(ho_so or {})
    dong = [
        f'- "{t[:TRICH_DIEU_KHOAN_TOI_DA]}"'
        for n in (tai_lieu_neo or [])
        if (t := " ".join(str(n.get("trich") or "").split()))
    ]
    return "\n".join([khoi, "", NHAN_DIEU_KHOAN_TAI_LIEU, *dong]) if dong else khoi


# ══ Phép kiểm thứ MƯỜI MỘT (QT-1) — văn xuôi không được phán quyết ═══════════
# `docs/bo-luat-agent.md` QT-1: nêu điều luật và điều kiện luật đặt ra, KHÔNG nói
# bên nào thắng, không nói điều khoản hợp pháp hay không. Lượt đối chiếu là nơi
# lời hứa đó chịu tải nặng nhất — người hỏi vừa đưa hợp đồng của chính họ và câu
# họ thật sự muốn nghe là một phán quyết, nên một câu trả lời trượt sang phán
# quyết sẽ đọc như đúng thứ họ xin, kèm trích dẫn đã kiểm chứng đứng sau.
#
# Vẫn TRA BẢNG, 0 TOKEN: một danh sách cụm, so trên chính văn xuôi. Cụm dài đứng
# TRƯỚC cụm ngắn chứa nó ("không hợp pháp" trước "hợp pháp") để nhãn ghi vào
# traces là cụm cụ thể nhất, không phải mảnh chung của nó.
LY_DO_PHAN_QUYET = "answer_ra_phan_quyet_thay_vi_neu_luat"

# Đo toàn tuyến HTTP 2026-09-16: câu trả lời thật viết "mức thử việc 90 ngày
# bạn nêu trong hợp đồng có thể KHÔNG ĐÚNG QUY ĐỊNH PHÁP LUẬT" — đúng kết luận
# QT-1 cấm, chỉ nói vòng và thêm "có thể", và không cụm nào trong danh sách khi
# ấy khớp. Một danh sách bỏ sót cách nói phổ biến nhất thì nó chỉ dạy mô hình
# nói vòng. Các cụm dưới đây là CÙNG MỘT KẾT LUẬN viết bằng chữ khác nhau.
CUM_PHAN_QUYET = (
    "không hợp pháp", "hợp pháp", "trái pháp luật", "trái luật", "vô hiệu",
    "không đúng quy định", "không đúng với quy định", "sai quy định",
    "không phù hợp với quy định", "không phù hợp quy định",
    "vi phạm pháp luật", "vi phạm quy định", "không hợp lệ", "hợp lệ",
    "có lợi", "bất lợi", "chắc chắn thắng", "thắng kiện", "sẽ thắng", "được bồi thường",
)

# Nửa đầu của ngõ cụt khi văn xuôi bị chặn: nói đúng cái hệ thống làm được thay
# cho cái nó vừa toan làm. Danh sách luật + điều khoản ghép ngay sau câu này.
PHAN_QUYET_MO_DAU = (
    "Tôi không kết luận điều khoản này hợp pháp hay không — kết luận đó thuộc cơ quan có "
    "thẩm quyền, và nó phụ thuộc cả những thứ nằm ngoài văn bản bạn gửi. Điều tôi nói được "
    "là luật yêu cầu gì và chỗ nào trong tài liệu của bạn khác với yêu cầu ấy:"
)


def cau_phan_quyet(answer: str, citations: list[dict] | None = None) -> str | None:
    """Cụm phán quyết đầu tiên trong `answer`, hoặc `None` khi văn xuôi sạch.

    Miễn trừ đúng MỘT đường: cụm nằm nguyên trong `quote` của một căn cứ ĐÃ QUA
    hai tầng kiểm thì được phép. Chính kho nói "hợp đồng lao động vô hiệu" (Điều
    49 BLLĐ), nên chặn cụm ấy vô điều kiện là cấm trợ lý đọc lại điều luật nó vừa
    dẫn — và một quy tắc buộc người ta viết sai luật để lách phép kiểm thì sẽ bị
    lách, không được tuân thủ.

    `normalize` (cùng hàm của tầng 1) cộng `lower`: so trên NỘI DUNG, không trên
    cách gõ. Ở đây hạ chữ hoa là an toàn — khác tầng 1, phép so này không đóng
    dấu "đã kiểm chứng" cho gì cả, nó chỉ chặn.
    """
    van = normalize(answer or "").lower()
    trich = " ".join(normalize(c.get("quote") or "").lower() for c in (citations or []))
    return next((cum for cum in CUM_PHAN_QUYET if cum in van and cum not in trich), None)


def _neu_luat_thay_phan_quyet(dung_cho_prose: list, citations_prose: list[dict],
                              tai_lieu_neo: list[dict]) -> str:
    """Nửa đầu của ngõ cụt khi phán quyết bị chặn — nêu LUẬT rồi nêu ĐIỀU KHOẢN,
    hai danh sách cạnh nhau, không câu nào nối chúng thành một kết luận.

    Dựng từ chính các khẳng định đã qua tầng 1+2 và các đoạn trích đã neo: không
    một chữ mới nào được sinh ra ở đây, nên không có chỗ cho phán quyết thứ hai
    lọt vào qua đúng cái cửa vừa đóng.
    """
    luat = [f"- Luật: {r.claim.text} ({c['duong_dan']})"
            for r, c in zip(dung_cho_prose, citations_prose, strict=True)][:TRAN_GACH]
    tai_lieu = [f'- Trong tài liệu của bạn: "{t[:TRICH_DIEU_KHOAN_TOI_DA]}"'
                for n in (tai_lieu_neo or [])
                if (t := " ".join(str(n.get("trich") or "").split()))]
    return "\n".join([PHAN_QUYET_MO_DAU, *luat, *tai_lieu])


# ══ Phép kiểm thứ bảy (coordinator, sau khi tự kiểm phép kiểm 6) ════════════
# Đo được: "mức lương tối thiểu vùng I HIỆN NAY" gộp bốn nghị định của BỐN NĂM
# khác nhau (90/2019, 157/2018, 141/2017 — tất cả bi_thay_the) thành các
# "phương án song song" trong VĂN XUÔI, dù mỗi citation đã được đánh dấu hiệu
# lực ĐÚNG. Lỗi nằm ở TẦNG CAO HƠN phép kiểm hiệu lực một bậc: khâu hành văn
# gộp nhiều phiên bản đã bị thay thế lại, không phải một citation sai riêng
# lẻ nào. Vẫn TRA BẢNG trên `Effectivity.verdict`, 0 TOKEN.
#
# Có neo (câu hỏi nêu đích danh văn bản, vd. "theo Nghị định 90/2019") →
# KHÔNG lọc — người dùng hỏi cụ thể văn bản đó, trả lời đúng nội dung của nó
# kèm cảnh báo vẫn là hành vi ĐÚNG (hành vi hiện tại, giữ nguyên).
LY_DO_NGUON_DEU_BI_THAY_THE = "moi_nguon_dung_cho_prose_da_bi_thay_the_khong_neo_van_ban"

_VERDICT_BI_THAY = frozenset({V.bi_thay_the, V.het_hieu_luc})

_RE_SO_KY_HIEU = re.compile(r"\d+/\d{4}/[A-ZĐ][\w-]*")


def _neo_vao_van_ban(query: str, so_ky_hieu: str) -> bool:
    """Câu hỏi có nêu ĐÍCH DANH `so_ky_hieu` không — tái dùng bộ nhận diện của
    phép kiểm thứ sáu (`van_ban_neo_boi_ten`, khớp tên/viết tắt 6 Bộ luật)
    CỘNG một quy tắc chung cho nghị định/thông tư: số hiệu dạng SỐ/NĂM xuất
    hiện nguyên văn ("90/2019" khớp "90/2019/NĐ-CP" dù người dùng không gõ đủ
    hậu tố loại văn bản — đúng cách viết thật trong trap.yaml)."""
    so_rut_gon = "/".join(so_ky_hieu.split("/")[:2])
    if so_rut_gon and so_rut_gon in normalize(query):
        return True
    return van_ban_neo_boi_ten(query, so_ky_hieu)


def _van_ban_ke_nhiem(ly_do: str) -> str | None:
    """Số hiệu văn bản KẾ NHIỆM nhắc trong `Effectivity.ly_do` — Mức 2a/2b đều
    nêu nó (dạng "bị X thay thế" hoặc "suy luận cùng chủ đề: X..."); Mức 1
    (hết hiệu lực đơn thuần, không cạnh kế nhiệm) không có gì để rút, trả None."""
    m = _RE_SO_KY_HIEU.search(ly_do or "")
    return m.group(0) if m else None


def _ten_ke_nhiem(e) -> list[str]:
    """Văn bản đi thay. Phán quyết chết có bằng chứng (ngày hoặc cạnh đồ thị,
    `tin_cay` cao) chỉ nêu `Effectivity.van_ban` — đã đi hết chuỗi tới văn bản
    còn sống (quyết định 2026-09-28 mục 12); nhánh cụt thì không nêu ai, dù
    `ly_do` còn nhắc văn bản thay trực tiếp đã chết. Suy luận Mức 2b không có
    văn bản làm chứng nên đọc số hiệu trong `ly_do` như cũ."""
    if e.verdict in _VERDICT_BI_THAY and e.tin_cay == "cao":
        return [v.so_ky_hieu for v in e.van_ban]
    m = _van_ban_ke_nhiem(e.ly_do)
    return [m] if m else []


def _ly_do_moi_nguon_bi_thay(qua_loc: list) -> str:
    """coverage_note khi TOÀN BỘ citation dùng-được-cho-prose đã bị lọc — nêu
    ĐÍCH DANH văn bản hiện hành (`_ten_ke_nhiem`, không phải một câu chung
    chung). Không phán quyết nào nêu được kế nhiệm thì nói rõ không xác định
    được, không bịa tên."""
    ke_nhiem = sorted({m for r in qua_loc for m in _ten_ke_nhiem(r.effectivity)})
    if ke_nhiem:
        return (f"Những gì tôi tìm được cho câu hỏi này đều đã bị thay thế. Văn bản đi thay "
                f"là {', '.join(ke_nhiem)}, và nội dung của nó thì tôi chưa có, "
                f"nên tôi chưa đọc được để nói với bạn nó quy định thế nào.")
    return ("Những gì tôi tìm được cho câu hỏi này đều đã bị thay thế hoặc đã hết hiệu lực, "
            "và từ những gì tôi đang có thì tôi chưa xác định được văn bản nào đi thay.")


# Loại kết quả của một lượt TRA CỨU — chỉ ở đó câu hỏi nêu tên văn bản ẩn mới
# nhận câu "không còn hiệu lực" (lượt về kho tự nói, xem `kho._khoi_mot_so`).
LOAI_BAO_VAN_BAN_AN = frozenset({ResultType.answer, ResultType.abstain, ResultType.partial_coverage})


def gan_van_ban_khong_hien_thi(ket: dict, an: list[dict]) -> dict:
    """Câu hỏi NÊU TÊN văn bản ẩn (quyết định 2026-09-28 mục 8): nói thẳng nó
    không có trong phạm vi tra cứu và vì sao, nêu văn bản thay thế — ở
    `van_ban_khong_hien_thi` (có link; giao diện vẽ nó ở `TheKetQua`) và
    `warnings[]` (eval, trace). KHÔNG chép vào `coverage_note`: giao diện đã vẽ
    trường trên, chép thêm là người đọc thấy cùng một câu hai lần. Không trích
    một chữ nào của văn bản ẩn. 0 token: `an` do `hien_thi.van_ban_an_duoc_nhac`
    tra bảng."""
    if not an or ket.get("result_type") not in LOAI_BAO_VAN_BAN_AN:
        return ket
    cau = [cau_van_ban_an(v["thong_diep"], (t["so_ky_hieu"] for t in v["thay_the"])) for v in an]
    return {
        **ket,
        "warnings": [*cau, *(w for w in ket.get("warnings") or [] if w not in cau)],
        "van_ban_khong_hien_thi": an,
    }


# `intent == ngoai_pham_vi`. HẰNG SỐ để phép quét giọng (`test_giong_tra_loi`)
# nhìn thấy được — một chuỗi viết thẳng vào lời gọi `_base` thì không hằng số
# nào tồn tại để quét.
NGOAI_PHAM_VI = ("Câu hỏi này nằm ngoài phạm vi tôi phủ: tôi chỉ tra được 6 Bộ luật của "
                 "Việt Nam, và chỉ soạn thảo trong lĩnh vực lao động.")

# Nửa đầu MẶC ĐỊNH của mọi abstain không mang `ghi_chu` riêng (Task 14). Trước
# bản này chỗ này gọi `_da_biet` (đã gỡ), liệt kê tên các văn bản khớp TỪ NGỮ
# trước khi hỏi lại — đúng hai điều chủ đề tài phàn nàn: trích dẫn sai thứ, và
# không đoán ra khách cần gì. Câu ở đây chỉ nói thẳng KHÔNG tìm được, không còn
# danh mục văn bản nào kèm theo. Đổi ở đây là LỜI của một ngõ cụt, không phải
# bằng chứng cho phép `answer` khẳng định điều gì — mọi claim vẫn phải qua đủ
# hai tầng kiểm chứng như trước.
KHONG_TIM_DUOC = "Tôi chưa tìm được điều khoản trả lời chắc cho câu này."

# Nửa đầu khi câu hỏi NỐI TIẾP không giải nghĩa được (`giai_nghia` trả None, rẽ
# thẳng vào đây). Nhánh đó chưa chạy truy hồi, nên nửa đầu MẶC ĐỊNH
# (`KHONG_TIM_DUOC`) sẽ nói "kho không có văn bản nào khớp" — một câu SAI: kho
# chưa được tra lần nào, và cái thiếu là mình chưa biết câu hỏi trỏ vào đâu.
# Cùng lớp lỗi với "văn bản chi phối" ở `_phu_mot_phan`, chỉ khác chiều.
CHUA_GIAI_NGHIA_DUOC = (
    "Câu hỏi này của bạn nối tiếp câu trước, mà tôi chưa chắc nó đang trỏ về phần nào "
    "trong những gì tôi vừa nói, nên tôi không đi tra vội — tra theo một phỏng đoán "
    "thì tôi sẽ trả lời một câu bạn không hỏi mà bạn cũng không có cách nào biết."
)


def _nhan_van_ban(so_ky_hieu: str, ten: str) -> str:
    """`"<số hiệu> (<tên>)"` — dạng hiển thị của module này, dựng từ cặp đã được
    `hien_van_ban` làm sạch. Rỗng khi không còn gì nói được về văn bản đó."""
    so, ten = hien_van_ban(so_ky_hieu, ten)
    return f"{so} ({ten})" if so and ten else (so or ten)


def _van_ban_va_vi_tri(hits: list[dict]) -> tuple[list[str], list[str]]:
    """`(tên văn bản, vị trí điều khoản)` — nửa đầu của mọi ngõ cụt, rút từ
    chính các dòng đang cầm.

    Bỏ dòng `cap == 'mo_dau'` khỏi phần vị trí: migration 016 chèn cho MỖI văn
    bản `shallow` đúng một hàng mang `duong_dan = '<số hiệu> > Mở đầu'`, nên nêu
    nó ra cho người hỏi vừa vô nghĩa vừa GỢI SAI — nó trông như một vị trí điều
    khoản trong khi văn bản đó chưa có điều khoản nào được nạp.

    Nhãn văn bản đi qua `hien_van_ban` (`services/kho.py`, xem docstring ở đó):
    `so_ky_hieu = 'Không số'` từng ra tới màn hình thành "Không số (Luật Thương
    mại số Không số)". Bỏ hẳn dòng không còn nhãn nào — thà thiếu một tên còn
    hơn in ra một chuỗi rỗng đội lốt định danh.
    """
    ten = sorted({nhan for p in hits
                  if (nhan := _nhan_van_ban(p.get("so_ky_hieu") or "", p.get("ten") or ""))})
    vi_tri = list(dict.fromkeys(p["duong_dan"] for p in hits
                                if p.get("duong_dan") and p.get("cap") != "mo_dau"))[:3]
    return ten, vi_tri


def _gop_usage(*us: Usage | None) -> Usage | None:
    """Cộng token của lượt hành văn và lượt sinh câu hỏi lại vào MỘT `usage`.

    Cố ý KHÔNG thêm khoá `hoi_lai_cost_usd` riêng: trần chi phí ngày
    (`bao_ve.tong_chi_phi_hom_nay`) đọc `traces.cost_usd`, mà cột đó do
    `traces._COST_KEYS` cộng từ một danh sách khoá CỐ ĐỊNH — một khoá mới không
    có trong danh sách ấy là một lượt gọi LLM vô hình với trần chi phí, đúng lớp
    lỗi mà chú thích ở `traces.py:62` đã ghi lại một lần.
    """
    co = [u for u in us if u is not None]
    if not co:
        return None
    return Usage(token_in=sum(u.token_in for u in co), token_out=sum(u.token_out for u in co),
                 cost_usd=sum(u.cost_usd for u in co))


# ══ Phase 14 R6 — giải thích CHUNG khi truy hồi không cho gì kiểm chứng được ══
# Owner: "ko bị giới hạn chỉ tham chiếu mỗi data base, agent có thể trả lời được
# thực tế dựa vào database". Vai THỨ BA của mô hình trong node này (sau hành
# văn và hỏi lại), prompt riêng và lược đồ riêng — khoá `giai_thich`, không
# phải `answer`, để trace và test phân biệt được nó với lượt hành văn có trích
# dẫn (`test_assemble.FakeLlm` đếm theo đúng danh tính lược đồ).
#
# Ranh giới không nhượng bộ: lời giải thích KHÔNG mang số Điều/Khoản/Điểm, số
# hiệu, thẻ hay URL — ở đây không có trích dẫn đã kiểm nào để đối chiếu, nên
# mọi số Điều đều là bịa; lưới 0 token bên dưới loại cả lời khi vướng.
# `abstain_threshold` và mọi điều kiện quyết định `result_type` giữ nguyên từng
# chữ — lượt vẫn là `abstain`, chỉ `answer` không còn trống, và giao diện dán
# nhãn "giải thích chung" cho đúng ca `abstain` có `answer`.
GIAI_THICH_PATH = Path("prompts/giai_thich_chung.v1.md")
GIAI_THICH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["giai_thich"],
    "properties": {"giai_thich": {"type": "string"}},
}
# Lưới của lời giải thích dùng lại ĐÚNG những bộ nhận diện đã có, không dựng
# bản thứ hai của cùng quy tắc — chính quy tắc `giai_nghia.dinh_danh_bia` đã
# ghi cho mình ("mỗi họ định danh dùng lại bộ nhận diện ĐÃ CÓ").
#
# * `bi_loai` (`hoi_lai`) — "câu này có phát biểu một quy tắc pháp luật không".
#   Nó đang được áp cho câu hỏi lại của CHÍNH lượt abstain này, nên lời giải
#   thích của cùng lượt không có lý do gì được đi qua một lưới lỏng hơn. Bản
#   chép tay trước đây (`_RE_DIEU` ở file này) hụt ở đúng những chỗ `bi_loai`
#   đã vá: `Ðiều` U+00D0, `Điều47` không khoảng trắng, và MỐC PHÁP LÝ ("60
#   ngày", "ba mươi ngày") — một phát biểu luật không mang số Điều nào nhưng
#   cũng không có neo nào chống đỡ.
# * `kho.moi_so_hieu_trong` — bản LỎNG của số hiệu, bắt cả "145/2020" viết
#   thiếu đuôi loại văn bản (đúng cách người ta thật sự gõ), chỗ
#   `_RE_SO_KY_HIEU` (đòi đủ hậu tố) và `bi_loai` (đòi dấu `/` thứ hai) đều hụt.
# * `_RE_KHOAN_DIEM` ở lại: `Khoản N`/`Điểm x` đứng một mình cũng là một trích
#   dẫn (R6) và KHÔNG họ nào ở trên phủ nó.
# * `_RE_THE`/`_RE_URL` — thẻ trích dẫn và đường dẫn, như cũ.
#
# GIÁ phải trả, chấp nhận CÓ CHỦ Ý theo hướng đóng: `bi_loai` cố ý THÔ, nên
# một lời giải thích đúng mực nhưng có "khoảng hai tuần" hay "trong ba ngày"
# cũng bị bỏ CẢ LỜI — tỉ lệ rơi cao hơn hẳn, kể cả với văn xuôi dè dặt hợp lệ.
# Đổi lại: không một mốc/số Điều không có neo nào tới được người đọc, và không
# định danh bịa nào được `dinh_danh_bia` bạch hoá ở lượt sau qua `tra_loi` đã
# lưu của lượt này. Mất một câu giải thích là rơi về abstain trơ; để lọt một
# mốc bịa là đúng chế độ hỏng cả khoá luận tồn tại để chống.
_RE_KHOAN_DIEM = re.compile(r"[Kk]hoản\s+\d|[Đđ]iểm\s+[a-zđ]\b")


def giai_thich_chung(cau_hoi: str, llm, model: str) -> tuple[str | None, Usage | None, str]:
    """`(lời giải thích | None, usage, nguon)` — `nguon` ∈ {"llm", "bi_loc", "loi"}.

    KHÔNG BAO GIỜ raise (cùng hợp đồng `hoi_lai`): đây là phần THÊM vào một ngõ
    cụt, không quyết định hạ nguồn nào phụ thuộc nó — hỏng thì lượt là abstain
    trơ như trước Phase 14, không phải HTTP 500. `usage` trả về kể cả khi hỏng:
    tiền đã trả cho provider phải vào trace.
    """
    prompt = GIAI_THICH_PATH.read_text(encoding="utf-8").format(cau_hoi=cau_hoi, toi_da=TRAN_KY_TU)
    usage: Usage | None = None
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=GIAI_THICH_SCHEMA)
        loi_giai_thich = str(json.loads(raw)["giai_thich"]).strip()
    except Exception as e:
        logger.warning("giai_thich_chung: không sinh được (%s: %s) — abstain trơ như trước",
                       type(e).__name__, e, exc_info=True)
        return None, usage, "loi"
    if not loi_giai_thich:
        return None, usage, "loi"
    # `normalize` TRƯỚC khi lọc, cùng lý do `verify_tier1` dùng nó ở cả hai
    # phía: mô hình sinh được NFD và `Ð` U+00D0, và một chữ chỉ khác cách biểu
    # diễn không được là đường vòng qua lưới.
    chuan = normalize(loi_giai_thich)
    if (bi_loai(chuan) or moi_so_hieu_trong(chuan) or _RE_KHOAN_DIEM.search(chuan)
            or _RE_THE.search(chuan) or _RE_URL.search(chuan)):
        # Ghi CẢ LỜI (cắt ngắn) chứ không chỉ cụm khớp: `bi_loai` trả bool, và
        # tần suất lưới này nổ là số liệu cần đọc được — xem `hoi_lai._cau_dung_duoc`.
        logger.warning("giai_thich_chung: lời giải thích phát biểu quy tắc pháp luật hay dẫn nguồn "
                       "— loại cả lời, không tới người đọc: %r", chuan[:200])
        return None, usage, "bi_loc"
    return loi_giai_thich, usage, "llm"


def _ngo_cut(state: dict, llm, model: str, rt: ResultType, ghi_chu: str | None = None,
             usage: Usage | None = None, degraded: bool = False, giai_thich: bool = False, **kw: object) -> dict:
    """MỌI nhánh không có câu trả lời đi qua đây — hai nửa, không có ngoại lệ.

    Một lối vào duy nhất chứ không phải một câu vá ở từng nhánh: sáu chỗ trong
    hàm `assemble` từng trả về `_base(state, ResultType.abstain)` trơ, và một
    nhánh thứ bảy thêm sau này sẽ lại là màn hình trắng nếu việc ghép hai nửa
    nằm rải ở từng chỗ gọi.

    `ghi_chu` là nửa đầu RIÊNG của nhánh (tiền đề sai, mọi nguồn đã bị thay,
    chỉ có tầng nông) — nhánh nào không có thì rơi về `KHONG_TIM_DUOC` (Task 14:
    câu nói thẳng không tìm được, không còn liệt kê tên văn bản). `out_of_scope`
    KHÔNG đi qua đây: câu hỏi nằm ngoài kho thì thêm dữ kiện tình huống cũng
    không đưa nó vào trong, và nhánh đó giữ 0 token.

    `da_biet` (bộ nhớ phiên) là những chiều hồ sơ ĐÃ có giá trị — `hoi_lai` bỏ
    chúng khỏi câu hỏi lại, để không hỏi lại một dữ kiện người hỏi đã cho biết
    hoặc máy đã đoán được.

    `giai_thich` (Phase 14 R6) — bốn ngõ cụt "truy hồi không cho gì kiểm chứng
    được" bật cờ này: `answer` mang lời giải thích chung của mô hình (không
    trích dẫn, xem `giai_thich_chung`), hai nửa `coverage_note` vẫn y nguyên.
    Tiền đề sai, câu nối tiếp chưa giải nghĩa được, và hai lần HẠ vì answer
    dẫn thẻ/số Điều không kiểm được (lưới cuối, R4) KHÔNG bật — chúng không
    phải "chưa tìm được", và một lượt gọi thêm để "cứu" câu bị hạ là mở lại
    đúng cửa lưới ấy vừa đóng.
    """
    ho_so = state.get("ho_so") or {}
    da_biet = frozenset(k for k, v in ho_so.items() if isinstance(v, dict) and v.get("gia_tri"))
    # Khung yêu cầu (GĐ2) đã bám vào chính vụ việc, nên khi nó hỏi được thì lượt
    # `hoi_lai` là tiền tiêu cho một câu hỏi kém cụ thể hơn — 0 token và cụ thể
    # hơn thắng. Rỗng (rewrite v2 mặc định, hoặc mọi dữ kiện đã biết) ⇒ đường cũ.
    tu_khung = cau_hoi_lai_tu_khung(state.get("khung_yeu_cau"), da_biet)
    hl = None if tu_khung else hoi_lai(state.get("query", ""), llm, model, da_biet=da_biet)
    cau = tu_khung or hl.cau
    gt, gt_usage, gt_nguon = (
        giai_thich_chung(state.get("query", ""), llm, model) if giai_thich else (None, None, None)
    )
    ket = _base(
        state,
        rt,
        usage=_gop_usage(usage, hl.usage if hl else None, gt_usage),
        degraded=degraded,
        coverage_note="\n\n".join(x for x in (ghi_chu or KHONG_TIM_DUOC, cau) if x),
        # `answer` chỉ khác None khi có lời giải thích đã qua lưới — giao diện
        # đọc đúng dấu hiệu "abstain có answer" để dán nhãn giải thích chung.
        **({"answer": gt} if gt else {}),
        **kw,
    )
    ket["traces"]["assemble_hoi_lai"] = "khung" if tu_khung else hl.nguon
    if giai_thich:
        ket["traces"]["assemble_giai_thich"] = gt_nguon
    return ket


# Câu trả lời cho `intent == gioi_thieu` sống ở `nodes/gioi_thieu.py`, KHÔNG ở
# đây. Trước 2026-09-02 nó là một hằng số `GIOI_THIEU` duy nhất, và hai câu hỏi
# khác nhau ("bạn làm được những gì" 09:21:36, "model của bạn là gì" 09:22:22 —
# bảng `traces`) nhận về đúng cùng 1.104 ký tự đó, từng chữ một. Nay câu hỏi được
# tách thành dạng bằng quy tắc; đây vẫn là MỘT `result_type`, chỉ `answer` đổi.


# Phase 14 (owner D14-B) — không còn lời đáp nào chỉ người dùng sang biểu mẫu
# hay nói "chưa có loại văn bản này": một lượt `soan_thao` đi `hieu_tai_lieu`
# → `dung_ban_thao_tong_quat`, mô hình soạn (xem `graph_tra_cuu._re_sau_route`).
# `soan_thao_goi_y` chỉ còn là LỜI MỜI biểu mẫu (R3, "móc leo" owner muốn giữ)
# — đính kèm bản thảo vừa dựng, hay câu trả lời tra cứu có ý định phụ soạn
# thảo — không thay câu nào và không chặn gì. Nêu tên mẫu, không nêu số Điều:
# căn cứ nằm trong từng mục của checklist, hiện ở khung soạn thảo.
MOI_BIEU_MAU = (
    " Tôi cũng có sẵn biểu mẫu {ten} với căn cứ pháp lý cho từng mục — cần thì mở khung soạn thảo bên cạnh."
)

# Phase 12 part B (R3) — người dùng phải biết NGAY trong lượt rằng KLAW vừa nhớ
# một điều về họ: một ký ức chỉ hiện trong màn hình tài khoản là một ký ức họ
# không có lý do nào để đi tìm mà xoá, và đây là dữ liệu cá nhân (có cả mã sinh
# viên). Chỉ dựng khi `ghi` trả `"moi"`/`"doi"` — `graph_tra_cuu._ghi_bo_nho` đã
# lọc sẵn, nên nhắc lại y hệt một giá trị cũ không sinh dòng nào.
DA_NHO = " Tôi đã nhớ {nhan} cho những lần sau — xem hoặc xoá trong phần Tài khoản."


def _cau_da_nho(state: dict) -> str:
    nhan = state.get("bo_nho_da_nho") or []
    return DA_NHO.format(nhan=", ".join(nhan)) if nhan else ""


def _ten_loai(loai: str) -> str:
    """Tên tiếng Việt của loại văn bản; `loai` không tra được checklist (YAML bị gỡ
    hay đổi tên sau khi phiên đã mở bản thảo loại đó) rơi về CHÍNH mã loại. Cùng
    lý do `route._dang_soan`: một câu trả lời hơi thô còn hơn một HTTP 500 ở node
    cuối, và đường hành văn của `assemble` vốn đã suy biến chứ không nổ."""
    try:
        return load_checklist_cached(loai).ten
    except ValueError:
        return loai


def _goi_y_soan_thao(tho: dict | None) -> dict | None:
    """Kiểm 0 token gợi ý của router rồi dựng `soan_thao_goi_y` (`SoanThaoGoiYOut`).
    `loai` phải là checklist THẬT trên đĩa; `thay_the` lọc còn loại thật, khác
    `loai`, tối đa hai. Không có gợi ý (route v1) → None. Phase 14: hàm không
    còn dựng lời đáp nào — mời biểu mẫu là việc của nơi gọi (`MOI_BIEU_MAU`)."""
    if tho is None:
        return None
    co = cac_loai()
    loai = tho.get("loai") if tho.get("loai") in co else None
    thay_the = [
        {"loai": t, "ten": _ten_loai(t)} for t in dict.fromkeys(tho.get("thay_the") or []) if t in co and t != loai
    ][:2]
    ly_do = " ".join(str(tho.get("ly_do") or "").split())[:300]
    # ly_do là văn xuôi LLM duy nhất né phép kiểm 8/9 — không có bề mặt bấm được,
    # nhưng một URL hay thẻ trong đó vẫn HIỆN ra dạng chữ, trái quy tắc SOUL.
    if _RE_URL.search(ly_do) or _RE_THE.search(ly_do):
        ly_do = ""
    if loai is None:
        return {"loai": None, "ten": None, "ly_do": ly_do, "thay_the": thay_the, "ho_tro": False}
    return {"loai": loai, "ten": _ten_loai(loai), "ly_do": ly_do, "thay_the": thay_the, "ho_tro": True}


def dung_bang_tu_luan_diem(verified: list, citations: list[dict]) -> Bang | None:
    """Bảng so sánh từ luận điểm ĐÃ QUA hai tầng kiểm: cột = đối tượng, hàng = tiêu chí, mỗi ô
    kết bằng thẻ `cite` của chính luận điểm đó nên bấm kiểm chứng được như văn xuôi."""
    o: dict[str, dict[str, str]] = {}
    doi_tuong: list[str] = []
    for r, c in zip(verified, citations, strict=True):
        h = getattr(r.claim, "hang", None)
        # Review round 1, finding 2: mô hình có thể trả `hang` KHÔNG PHẢI mapping
        # (chuỗi, số, list — vẫn truthy) dù schema strict đòi object|null; `.get`
        # trên một giá trị như vậy nổ AttributeError ở bước CUỐI của một câu trả
        # lời đã qua cả hai tầng kiểm. `isinstance` trước, cùng tinh thần phòng
        # thủ hình dạng LLM trả về mà `generate_claims.py` đã áp cho cả JSON.
        if not isinstance(h, dict):
            continue
        dt_raw, tc_raw = h.get("doi_tuong"), h.get("tieu_chi")
        if not isinstance(dt_raw, str) or not isinstance(tc_raw, str) or not dt_raw.strip() or not tc_raw.strip():
            continue
        dt, tc = dt_raw.strip(), tc_raw.strip()
        if dt not in doi_tuong:
            doi_tuong.append(dt)
        so_dieu = c["duong_dan"].rsplit("Điều ", 1)[-1].split(" ")[0]
        # Cùng (đối tượng, tiêu chí) xuất hiện hai lần (hai luận điểm trùng ô) —
        # BẢN SAU ghi đè bản trước, có chủ đích (review round 1, finding 3):
        # `verified`/`citations` không mang thứ tự "đáng tin hơn" nào giữa hai
        # luận điểm cùng một ô, và một cell hai câu nối lại sẽ dài hơn không rõ
        # ích lợi gì hơn — giữ bản GẦN NHẤT là hành vi ĐƠN GIẢN nhất còn quyết
        # định được, ghim bằng test, không phải bỏ ngỏ.
        o.setdefault(tc, {})[dt] = f"{r.claim.text} [Điều {so_dieu}](cite:{c['k']})"
    # Review round 1, finding 1: hai đối tượng + đủ hai ô KHÔNG đủ nếu chúng rơi
    # vào hai TIÊU CHÍ KHÁC NHAU — mỗi hàng khi đó chỉ có một ô, còn lại toàn dấu
    # gạch, tức một bảng TRÔNG như so sánh nhưng KHÔNG hàng nào thực sự so sánh
    # hai đối tượng với nhau. Đòi ÍT NHẤT một hàng có từ hai ô trở lên.
    if len(doi_tuong) < 2 or sum(len(v) for v in o.values()) < 2 or not any(len(v) >= 2 for v in o.values()):
        return None
    return Bang(
        tieu_de="So sánh theo tiêu chí",
        # Ô thiếu để CHUỖI RỖNG, KHÔNG PHẢI dấu gạch: cùng quy ước "không có dữ
        # liệu" mà bảng kho (`services/kho.dung_bang`) đã dùng, để `BangKetQua`
        # áp ĐÚNG MỘT đường hiển thị ô trống có khả năng truy cập (màu mờ + câu
        # `sr-only`) cho cả hai loại bảng thay vì bảng so sánh tự bịa một quy ước
        # thứ hai mà component chưa biết (Minor, review round 1).
        cot=["Tiêu chí", *doi_tuong],
        dong=[[tc, *[o[tc].get(dt, "") for dt in doi_tuong]] for tc in o],
    )


def _chuan_text(t: str) -> str:
    """Khoá khử trùng của một khẳng định: thường hoá, gộp khoảng trắng, bỏ dấu
    câu cuối. Hai claim khác số Điều nhưng CÙNG một câu là một ý lặp — quy tắc 6
    của cai_thien.md §6 GĐ3, và là thứ prompt một mình không ép được."""
    return " ".join((t or "").lower().split()).rstrip(" .,;:!?")


def _chon_cho_prose(prose: list, cits: list[dict], query: str) -> tuple[list, list[dict]]:
    """Xếp — bỏ chế tài lạc — khử trùng — cắt trần, cho tập claim vào lời nhắc
    hành văn (cai_thien.md §6 GĐ3 quy tắc 1–7).

    CHỈ được gọi khi có ít nhất một claim mang `vai_tro`: với prompt sinh v2
    (mặc định) mọi vai trò là None, không có gì để xếp, và tập claim phải đi qua
    y nguyên — baseline đang đo trên đúng thứ tự đó.

    Hai danh sách đi CẶP suốt hàm (`strict=True`): `citations_dung_cho_prose[i]`
    phải luôn là trích dẫn của `dung_cho_prose[i]`, nếu không thẻ `cite:K` sẽ trỏ
    một khẳng định khác — bất biến mà phần còn lại của hàm dựa vào.
    """
    cap = list(zip(prose, cits, strict=True))
    if not _RE_HOI_CHE_TAI.search(normalize(query or "")):
        khac = [x for x in cap if x[0].claim.vai_tro != "che_tai"]
        # Giữ chế tài khi bỏ đi thì còn dưới hai căn cứ: một câu trả lời dựng
        # trên một căn cứ duy nhất thì thà kém gọn còn hơn thiếu.
        if len(khac) >= 2:
            cap = khac
    cap.sort(key=lambda x: _HANG_VAI_TRO.get(x[0].claim.vai_tro, len(_HANG_VAI_TRO)))
    giu: list[tuple] = []
    da: set[str] = set()
    for r, c in cap:
        khoa = _chuan_text(r.claim.text)
        if khoa in da:
            continue
        da.add(khoa)
        giu.append((r, c))
    giu = giu[:TOI_DA_CLAIM_PROSE]
    return [r for r, _ in giu], [c for _, c in giu]


def _du_kien_quyet_dinh_thieu(khung_yeu_cau: dict | None, ho_so: dict | None) -> list[dict]:
    """Dữ kiện LÀM ĐỔI KẾT LUẬN mà người hỏi chưa nói. Một khoá đã có giá trị
    trong `ho_so` thắng mọi suy đoán của model, kể cả khi model vẫn đòi hỏi lại."""
    da_biet = {k for k, v in (ho_so or {}).items() if isinstance(v, dict) and v.get("gia_tri")}
    return [m for m in (khung_yeu_cau or {}).get("du_kien_quyet_dinh_con_thieu") or []
            if isinstance(m, dict) and m.get("lam_doi_ket_luan") and str(m.get("ma") or "") not in da_biet]


def tinh_muc_chac(dung_cho_prose: list, khung_yeu_cau: dict | None, ho_so: dict | None) -> str:
    """`"chac"` | `"co_dieu_kien"` — TÍNH BẰNG MÃ, không hỏi mô hình.

    Hai lý do hạ giọng, cả hai đều tra bảng được:
    * còn một dữ kiện quyết định chưa biết ⇒ kết luận phụ thuộc nó;
    * biết vai trò các căn cứ mà KHÔNG có căn cứ `ket_luan` nào ⇒ ta chỉ đang
      cầm điều kiện/ngoại lệ, và cai_thien.md §6 GĐ3 cấm ghép chúng thành một
      kết luận.

    KHÔNG có mức thứ ba ở đây: "chưa đủ" là `abstain`, một `result_type`, và
    pha này không đổi KHI NÀO abstain.
    """
    if _du_kien_quyet_dinh_thieu(khung_yeu_cau, ho_so):
        return "co_dieu_kien"
    vai = [r.claim.vai_tro for r in dung_cho_prose]
    if any(vai) and "ket_luan" not in vai:
        return "co_dieu_kien"
    return "chac"


# Bản thảo trên KHUÔN GỐC (P4b): lời đáp nói số chỗ đã điền và gọi tên chỗ còn
# trống; phép bị phép kiểm bỏ đi thì `coverage_note` gọi tên chúng. Trần tên
# dùng lại `TRAN_GACH` (bốn mục người đọc còn nắm được), trần ghi chú 160 ký tự.
TRAN_GHI_CHU_KHUON = 160
# Giá trị người hỏi đưa mà mô hình chưa đặt được (`khuon.khong_dat`, B3): câu riêng,
# danh sách tối đa 160 ký tự; phần nó chiếm trừ vào trần 320 của "Còn trống" nên lời
# đáp dài nhất vẫn dài như trước (≤ 900 ký tự, `TRAN_KY_TU`).
TRAN_KHONG_DAT = 160
DUOI_KHONG_DAT = " — hãy nói rõ chỗ cần điền hoặc bấm vào chỗ trống trên trang."


def _liet_ke(
    dau: str, ten: list[str], tran_ky_tu: int, loai: str = "chỗ", so: list[int] | None = None, tong: int | None = None
) -> str:
    """`dau` + tối đa `TRAN_GACH` tên, cắt để vừa `tran_ky_tu`; phần cắt nói bằng SỐ.
    `so`: mỗi tên đứng cho bao nhiêu thứ (mặc định 1); `tong`: tổng số thứ, kể cả thứ
    không tên nào gọi (mặc định tổng `so`)."""
    so = so or [1] * len(ten)
    tong = sum(so) if tong is None else tong
    for n in range(min(len(ten), TRAN_GACH), -1, -1):
        du = tong - sum(so[:n])
        s = dau + ", ".join(ten[:n]) + ((" và " if n else "") + f"{du} {loai} khác" if du else "")
        if len(s) <= tran_ky_tu:
            return s
    return dau[:tran_ky_tu]


def _cau_khong_dat(khuon: dict) -> str:
    """Câu "Chưa đặt được: «…» — …" cho giá trị người hỏi đưa mà chưa có chỗ; rỗng
    khi không có. Giá trị là chuỗi con lời người hỏi (`hieu_tai_lieu._lay_khong_dat`)."""
    ten = [f"«{v}»" for v in khuon.get("khong_dat") or []]
    return _liet_ke("Chưa đặt được: ", ten, TRAN_KHONG_DAT, "giá trị") + DUOI_KHONG_DAT if ten else ""


def _ban_thao_khuon(state: dict, bt: dict) -> dict:
    """Lời đáp 0 token cho một bản thảo khuôn gốc — đọc `bt["phep_sua"]` (TRỌN phép
    của phiên bản vừa lưu) và `khuon_tong_quat` (chỗ trống, phép đã bỏ) của lượt."""
    khuon = state.get("khuon_tong_quat") or {}
    tai = "tải PDF" if khuon.get("dinh_dang") == "pdf" else "tải Word hoặc PDF"
    khong_dat = _cau_khong_dat(khuon)
    if khuon.get("co_san"):
        # Lượt không xin đổi gì trên bản thảo đã có (`dung_ban_thao_tong_quat`):
        # thẻ là CHÍNH bản đang có, không phiên bản mới.
        return _base(
            state,
            ResultType.ban_thao,
            answer=f"Bản thảo trên tệp bạn tải lên đã có sẵn (phiên bản {bt['phien_ban']}): mở bản thảo để xem, "
            f"{tai}. Muốn điền, hãy nói giá trị cần điền hoặc bấm vào chỗ trống trên trang."
            + (" " + khong_dat if khong_dat else "")
            + _cau_da_nho(state),
            ban_thao=bt,
            soan_thao_goi_y=None,
        )
    phep = bt.get("phep_sua") or []
    # Đơn vị đã thay/xoá (hay ĐOẠN đã thay theo `doan`) không còn dãy chấm — cùng
    # luật `ban_thao.cho_trong_khuon`.
    theo_doan = {
        (p.get("don_vi"), p.get("doan")) for p in phep if p.get("loai") == "thay" and p.get("doan") is not None
    }
    da_doi = {
        p.get("don_vi") for p in phep if p.get("loai") == "xoa" or (p.get("loai") == "thay" and p.get("doan") is None)
    }
    cho = [
        c
        for c in khuon.get("cho_trong") or []
        if c["don_vi"] not in da_doi and (c["don_vi"], c.get("doan", 0)) not in theo_doan
    ]
    nhan = {(c["don_vi"], c["so"]): c["nhan"] or "chỗ trống" for c in cho}
    da = {(p.get("don_vi"), p.get("cho_trong")) for p in phep if p.get("loai") == "dien"}
    so_doan = sum(1 for p in phep if p.get("loai") != "dien")
    con = [f"«{nhan[k]}»" for k in nhan if k not in da]
    doi = [f"«{x}»" for x in bt.get("doi_so_voi_truoc") or []]
    tran_con = 320 - len(khong_dat)
    tao_lai = khuon.get("yeu_cau") == "tao_lai"
    if not phep and (not doi or tao_lai):
        # Phiên bản chưa có phép nào (owner 2026-09-27): bản thảo LÀ tệp tải lên —
        # `tao_lai` luôn tới đây, kể cả khi nó vừa gỡ các giá trị của bản đã điền
        # (`doi`): chúng còn ở phiên bản trước. Khuôn PDF không có bản Word
        # (`routes_ban_thao.tai_xuong`).
        so_trang = khuon.get("so_trang")
        answer = (
            "Tôi đã dựng lại văn bản đúng như tệp bạn tải lên"
            + (f" ({so_trang} trang)" if so_trang else "")
            + f": mở bản thảo để xem, {tai} ngay. "
            + (
                _liet_ke("Còn trống: ", con, tran_con)
                + ". Muốn điền, hãy nói giá trị cần điền hoặc bấm vào chỗ trống trên trang."
                if con
                else "Muốn đổi gì cứ nói với tôi."
            )
            + (" Giá trị đã điền trước đó vẫn ở phiên bản trước: bấm Lùi để lấy lại." if doi else "")
            + (" " + khong_dat if khong_dat else "")
            + _cau_da_nho(state)
        )
    else:
        answer = (
            f"Bản thảo phiên bản {bt['phien_ban']} là chính biểu mẫu bạn tải lên: đã điền "
            f"{len(da & nhan.keys())}/{len(nhan)} chỗ trống"
            + (f" và sửa {so_doan} đoạn" if so_doan else "")
            + ("; " + _liet_ke("đã đổi: ", doi, 160) if doi else "")
            + ". "
            + (_liet_ke("Còn trống: ", con, tran_con) + ". " if con else "")
            + (khong_dat + " " if khong_dat else "")
            # Luật owner 2026-09-27: chữ của chính tài liệu không còn là nguồn điền.
            + "Tôi chỉ điền điều bạn đã nói hoặc có trong hồ sơ; chỗ chưa có giá trị giữ nguyên dãy chấm. "
            + "Bạn xem, bấm vào chỗ trống trên trang để sửa, hoặc tải về; muốn đổi gì cứ nói với tôi."
            + _cau_da_nho(state)
        )
    bo = khuon.get("bo_qua") or []
    # Tên chỗ trống từ TRỌN danh sách (cả chỗ của đoạn đã viết lại), không bao giờ số
    # đơn vị: "đoạn 29" là chỉ số nội bộ người đọc không thấy ở đâu (G5).
    ten = {(c["don_vi"], c["so"]): c["nhan"] or "chỗ trống" for c in khuon.get("cho_trong") or []}
    ten_bo = list(
        dict.fromkeys(
            f"«{ten[k]}»" if (k := (b.get("don_vi"), b.get("cho_trong"))) in ten else "một thay đổi" for b in bo
        )
    )
    ghi_chu = (
        _liet_ke(f"Không áp {len(bo)} thay đổi (thiếu nguồn hoặc sai chỗ): ", ten_bo, TRAN_GHI_CHU_KHUON)
        if bo
        else None
    )
    return _base(state, ResultType.ban_thao, answer=answer, ban_thao=bt, soan_thao_goi_y=None, coverage_note=ghi_chu)


# Khuôn mẫu (thiết kế `khuon-mau-thiet-ke.md` §6 "Answer"): lời đáp 0 token, chỉ gọi
# tên phép CÓ trong phiên bản đã lưu (owner: không bao giờ nói đã điền khi chưa điền).
_RE_TEN_CAN_CU = re.compile(r"^Căn cứ\s+(.+?)(?:\s+ngày\s+\d.*)?[;.]?$")


def _ten_can_cu(dong: str) -> str:
    """Tên văn bản của một dòng căn cứ: "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20
    tháng 11 năm 2019;" → "Bộ luật Lao động số 45/2019/QH14"."""
    m = _RE_TEN_CAN_CU.match(dong.strip())
    return (m[1] if m else dong).strip().rstrip(";.")


def _cau_the_thuc(khung: dict) -> str:
    """Câu thể thức cuối lời đáp. Mẫu ban hành kèm văn bản pháp luật (NĐ 124/2020 Mẫu 01,
    Mẫu 23-DS…) là mẫu của CHÍNH văn bản ấy, không phải "tập quán" — nói đúng nguồn.
    Văn bản hành chính: NĐ 30/2020 chỉ buộc cơ quan, tổ chức nhà nước và doanh nghiệp
    nhà nước (Đ2.1) — với doanh nghiệp khác là tập quán, không phải luật đòi (quyết định
    2026-09-29, "Consequences"). Còn lại là tập quán."""
    nguon = (khuon_mau.nap(khung["loai"]) if khung.get("loai") in khuon_mau.cac_loai() else {}).get("nguon") or {}
    if nguon.get("loai") == "mau_chinh_thuc" and khung.get("bo_cuc") != "hanh_chinh":
        return f" Trình bày theo {nguon['van_ban']}."
    if khung.get("bo_cuc") == "hanh_chinh":
        return (
            " Thể thức theo Phụ lục I Nghị định 30/2020/NĐ-CP: bắt buộc với cơ quan, tổ chức nhà nước và doanh"
            " nghiệp nhà nước; với doanh nghiệp, tổ chức khác là tập quán."
        )
    return " Thể thức theo tập quán, tham khảo Phụ lục I Nghị định 30/2020/NĐ-CP."


def _cau_con_trong(cho: list[dict], khung: dict) -> str:
    """Câu "Còn trống: «…»." gọi tên chỗ người đọc hiểu: trường của các bên trước (`khung.o`),
    rồi trường của văn bản, rồi chỗ có nhãn chữ; MỘT tên cho mọi bản sao. Ô không nhãn và
    nhãn là mảnh dòng mẫu ("/QĐ-", "ngày", "… (sau -)") chỉ vào số "N chỗ khác". Rỗng khi
    không còn chỗ trống."""
    con = [o for o in cho if not (o.get("gia_tri") or "").strip()]
    if not con:
        return ""
    ben = {(x.get("don_vi"), x.get("so")): x.get("ben") for x in khung.get("o") or []}

    def hang(o: dict) -> int:
        b = ben.get((o["don_vi"], o["so"]))
        return 2 if b is None else 1 if b == khuon_mau.BEN_VAN_BAN else 0

    dem: dict[str, int] = {}
    for o in sorted(con, key=hang):
        n = (o.get("nhan") or "").strip()
        if n[:1].isupper() and "(sau " not in n:
            dem[n] = dem.get(n, 0) + 1
    if not dem:
        return f"Còn trống {len(con)} chỗ. "
    return _liet_ke("Còn trống: ", [f"«{t}»" for t in dem], 200, so=list(dem.values()), tong=len(con)) + ". "


def _ban_thao_khuon_mau(state: dict, bt: dict) -> dict:
    """Lời đáp cho một bản thảo trên KHUÔN MẪU (tệp .docx KLAW dựng), đọc thẳng từ
    phiên bản vừa lưu (`bt`: `khuon`, `audit_report.khung`, `clauses`) và ghi chú của
    lượt (`khuon_mau_tong_quat`)."""
    x = state.get("khuon_mau_tong_quat") or {}
    k = bt.get("khuon") or {}
    ten = bt.get("ten") or "văn bản"
    khung = (bt.get("audit_report") or {}).get("khung") or {}
    cho = k.get("cho_trong") or []
    # Lượt chat (`khuon_mau_tong_quat.da_dien`): chỉ chỗ LƯỢT NÀY điền từ lời người hỏi.
    # Đường checklist không có số đó: nói tổng của phiên bản, không nói nguồn.
    if "da_dien" in x:
        dien = f"Đã điền {x['da_dien']} chỗ trống từ lời bạn nói. " if x["da_dien"] and not x.get("co_san") else ""
    else:
        da = sum(1 for o in cho if (o.get("gia_tri") or "").strip())
        dien = f"Đã điền {da}/{len(cho)} chỗ trống. " if da else ""
    can_cu = [_ten_can_cu(c["dong"]) for c in can_cu_hien(khung.get("can_cu") or [], bt.get("clauses") or [])]
    # Văn bản chuyên ngành kho chưa có toàn văn (`_nap_khuon_mau`, lượt tạo): nói thẳng,
    # cạnh dòng căn cứ — tên văn bản không được ngầm nói điều khoản đã theo luật đó.
    thieu_luat = (state.get("khuon_mau_ngu_canh") or {}).get("thieu_luat") or []
    chen = [f"«{c.get('ten')}»" for c in bt.get("clauses") or [] if c.get("chen")]
    khong_dat = _cau_khong_dat({"khong_dat": x.get("khong_dat") or []})
    ghi = list(x.get("ghi_chu") or [])
    if x.get("khong_mang_sang"):
        ghi.append(f"{x['khong_mang_sang']} chỗ đã điền nằm ở đoạn vừa viết lại nên không mang sang: hãy điền lại")
    if x.get("co_san"):
        dau = f"Bản thảo «{ten}» (phiên bản {bt['phien_ban']}) giữ nguyên: lượt này không có thay đổi nào áp được. "
    elif bt.get("doi_so_voi_truoc"):
        dau = (
            f"Bản thảo «{ten}» đã cập nhật (phiên bản {bt['phien_ban']}"
            + (f", {k['so_trang']} trang" if k.get("so_trang") else "")
            + "); "
            + _liet_ke("đã đổi: ", [f"«{d}»" for d in bt["doi_so_voi_truoc"]], 200)
            + ". "
        )
    else:
        dau = (
            f"Bản thảo «{ten}»"
            + (f" ({k['so_trang']} trang)" if k.get("so_trang") else "")
            + " đã sẵn sàng: mở bản thảo để xem, tải Word hoặc PDF. "
        )
    phan = [
        dau,
        dien,
        (
            _liet_ke("Căn cứ: ", can_cu, 220, "văn bản") + ". Bấm «Căn cứ» trên trang để xem nguyên văn. "
            if can_cu
            else ""
        )
        + (
            f"Kho chưa có toàn văn {', '.join(thieu_luat)}, nên các điều khoản chỉ dựa trên căn cứ"
            " đang có — chưa đối chiếu với luật đó. "
            if thieu_luat
            else ""
        ),
        (_liet_ke("Điều còn trống vì luật đòi: ", chen, 160, "điều") + ". " if chen else ""),
        _cau_con_trong(cho, khung),
        (" ".join(g.rstrip(".") + "." for g in ghi[:3]) + " " if ghi else ""),
        (khong_dat + " " if khong_dat else ""),
        "Bấm vào chỗ trống trên trang để điền; muốn sửa điều nào cứ nói với tôi.",
        _cau_the_thuc(khung),
    ]
    answer = "".join(phan)
    if len(answer) > TRAN_KY_TU:
        answer = "".join(p for i, p in enumerate(phan) if i not in (4, 5))[:TRAN_KY_TU]
    return _base(state, ResultType.ban_thao, answer=answer + _cau_da_nho(state), ban_thao=bt, soan_thao_goi_y=None)


def xem_ban_thao_khuon(bt: dict) -> dict:
    """Lời xin XEM bản đã điền (owner 2026-09-28, Q3): kết quả `ban_thao` 0 token cho
    bản thảo khuôn gốc mới nhất của hội thoại — không graph, không phiên bản mới. `bt`
    là dòng `ban_thao` kèm `khuon` và `ten_tep` (`ban_thao.moi_nhat_tren_khuon`)."""
    k = bt.get("khuon") or {}
    cho, phep = k.get("cho_trong") or [], bt.get("phep_sua") or []
    tai = "tải PDF" if k.get("dinh_dang") == "pdf" else "tải Word hoặc PDF"
    ten, n = bt.get("ten_tep") or "tệp bạn tải lên", bt["phien_ban"]
    if k.get("nguon") == "khuon_mau":
        # Khuôn mẫu KLAW dựng: không có "tệp bạn tải lên" nào (thiết kế khuôn mẫu §6).
        da = sum(1 for c in cho if (c.get("gia_tri") or "").strip())
        answer = (
            f"Đây là bản thảo «{PurePath(ten).stem}» (phiên bản {n}): đã điền {da}/{len(cho)} chỗ trống. "
            f"Bấm vào chỗ trống trên trang để điền, hoặc {tai}."
        )
    elif not phep:
        answer = (
            f"Đây là bản thảo (phiên bản {n}) đúng như tệp bạn tải lên «{ten}»: chưa điền chỗ trống nào. "
            f"Bấm vào chỗ trống trên trang để điền, hoặc {tai}."
        )
    else:
        da = sum(1 for c in cho if (c.get("gia_tri") or "").strip())
        so_doan = sum(1 for p in phep if p.get("loai") != "dien")
        answer = (
            f"Đây là bản đã điền (phiên bản {n}) của «{ten}»: đã điền {da}/{len(cho)} chỗ trống"
            + (f" và sửa {so_doan} đoạn" if so_doan else "")
            + f". Bấm vào chỗ trống trên trang để sửa, hoặc {tai}."
        )
    return _base(
        {"traces": {}},
        ResultType.ban_thao,
        answer=answer,
        ban_thao=_ket_state(bt, TEN_TONG_QUAT, []),
        soan_thao_goi_y=None,
    )


def _ban_thao_tong_quat(state: dict) -> dict:
    """Lượt SOẠN từ tài liệu (S6) — `dung_ban_thao_tong_quat` đã chạy xong.

    0 token, và `assemble` không soạn gì ở đây: nó chỉ chọn một trong ba lời đáp
    theo những gì node kia để lại. Phase 14 (owner D14-A): lời đáp KHÔNG dán
    nhãn "chưa kiểm pháp lý" nữa — bản ghi (`audit_report.muc_kiem`,
    `dung_ban_thao_tong_quat.ket_ban_thao`) vẫn nói thật, chỉ nhãn hiển thị bỏ.
    Từ Phase 14 đây cũng là lời đáp cho MỌI lượt `soan_thao` không có checklist
    mở dở (kể cả lượt không có tài liệu nào), nên nguồn soạn phải nói đúng thứ
    đã dùng.
    """
    bt = state.get("ban_thao_ket")
    if bt and (bt.get("khuon") or {}).get("nguon") == "khuon_mau":
        return _ban_thao_khuon_mau(state, bt)
    if bt and bt.get("viec_id"):
        return _ban_thao_khuon(state, bt)
    if bt:
        doi = bt.get("doi_so_voi_truoc") or []
        co_tai_lieu = bool((state.get("tai_lieu_ket") or {}).get("tai_lieu_da_dung"))
        # R3 — router nhận ra một trong 29 mẫu thì MỜI một câu và đưa `loai`
        # ra payload để giao diện vẽ nút; không mẫu thật thì không mời gì.
        goi_y = _goi_y_soan_thao(state.get("soan_thao_goi_y"))
        if goi_y is not None and not goi_y["ho_tro"]:
            goi_y = None
        answer = (
            f"Bản thảo phiên bản {bt['phien_ban']} đã sẵn sàng"
            + (f", đã đổi: {', '.join(doi)}" if doi else "")
            + (". Tôi soạn từ nội dung tài liệu và những gì bạn nói" if co_tai_lieu else ". Tôi soạn từ những gì bạn nói")
            # Hai hình dạng chỗ trống, không một: từ 2026-09-19 một văn bản soạn
            # từ đầu vẽ chỗ điền thành dòng chấm như biểu mẫu, còn `[…]` thu hẹp
            # lại thành "KLAW cố ý không điền" (xem `hieu_tai_lieu._duong_dien`).
            # Nói đúng cả hai thay vì nêu một cái mà người đọc có thể không thấy.
            + f"; chỗ nào chưa có dữ kiện tôi chừa trống (dòng chấm hoặc {CHO_TRONG}). "
            + "Bạn xem, sửa từng mục hoặc tải về ở bên cạnh; "
            + "muốn đổi gì cứ nói với tôi."
            + (MOI_BIEU_MAU.format(ten=goi_y["ten"]) if goi_y else "")
            + _cau_da_nho(state)
        )
        return _base(state, ResultType.ban_thao, answer=answer, ban_thao=bt, soan_thao_goi_y=goi_y)
    # Hỏng thì HỎI LẠI, không im lặng: `soan_thao_hoi` là hình dạng đã có cho
    # đúng tình huống "chưa dựng được, đây là lý do" — không dựng loại thứ chín.
    can_dang_nhap = state.get("user_sub") is None
    loi = state.get("ban_thao_tong_quat_loi")
    # Khuôn gốc: giá trị người hỏi đưa mà chưa đặt được vẫn được kể (G5), kể cả khi
    # lượt không lưu gì — điền trên trang không tốn hạn mức nào.
    khong_dat = _cau_khong_dat(state.get("khuon_tong_quat") or {}) if loi else ""
    # Lượt soạn HỎNG (hết hạn mức chẳng hạn) vẫn có thể đã nhớ: `hieu_tai_lieu`
    # chạy TRƯỚC `dung_ban_thao_tong_quat`, nên điều họ vừa khai đã ghi rồi. Im
    # lặng ở đây là giấu đúng cái R3 bắt phải nói ra.
    return _base(
        state,
        ResultType.soan_thao_hoi,
        answer=(LOI_SOAN_THAO_DANG_NHAP if can_dang_nhap else (loi or KHONG_SOAN_DUOC))
        + (" " + khong_dat if khong_dat and not can_dang_nhap else "")
        + _cau_da_nho(state),
        soan_thao_goi_y=None,
        soan_thao_hoi={
            "loai": LOAI_TONG_QUAT,
            "ten": TEN_TONG_QUAT,
            "da_co": {},
            "con_thieu": [],
            "chip": {},
            "het_han_muc": None if can_dang_nhap else loi,
            "can_dang_nhap": can_dang_nhap,
        },
    )


def assemble(state: dict, db_provisions: dict[int, dict], llm, model: str, prompt_path: Path | None = None) -> dict:
    # Nhánh SOẠN VĂN BẢN từ tài liệu (S6) đứng trước nhánh tài liệu ngay dưới:
    # lượt này cũng mang `tai_lieu_ket` và cũng có `intent` trống, nhưng thứ
    # người hỏi xin là một BẢN THẢO, không phải một bản tóm tắt tài liệu.
    if state.get("muc_dich_tai_lieu") in MUC_DICH_SOAN:
        return _ban_thao_tong_quat(state)

    # Nhánh TÀI LIỆU đứng TRƯỚC mọi nhánh khác, và 0 TOKEN: lượt hành văn đã
    # xảy ra ở node `hieu_tai_lieu` (nơi duy nhất thấy chữ của tài liệu), nên
    # `assemble` chỉ dán kết quả đã có vào hình dạng response.
    #
    # Gác trên `tai_lieu_ket` CHỨ KHÔNG chỉ trên `intent`: lượt ĐÍNH KÈM rẽ tất
    # định ở `graph_tra_cuu._vao_graph` và không đi qua `route` một lần nào, nên
    # `intent` của nó trống. Xét cả hai là cách duy nhất hai đường vào cùng ra
    # một loại kết quả.
    # `tai_lieu_neo` rỗng là điều kiện THỨ BA, không phải một chi tiết: lượt đối
    # chiếu luật cũng mang `tai_lieu_ket` (node đọc tài liệu luôn dựng nó) và
    # cũng có `intent` trống, nhưng nó đã đi hết đường pháp lý trước khi tới đây
    # — trả về nhánh tài liệu ở đó là vứt bỏ một câu trả lời đã qua hai tầng
    # kiểm để thay bằng một bản tóm tắt tài liệu, đúng thứ người hỏi không xin.
    ket = state.get("tai_lieu_ket")
    if ket and state.get("intent") in (None, "tai_lieu") and not state.get("tai_lieu_neo"):
        return _base(state, ResultType.tai_lieu, answer=ket.get("tra_loi_ngan") or None,
                     tai_lieu=ket, tai_lieu_neo=state.get("tai_lieu_neo") or [])

    if state.get("intent") == "soan_thao":
        # Task 19 — lượt đã đi qua `gom_du_kien` (và, khi đủ dữ kiện và có tài
        # khoản, `dung_ban_thao`) TRƯỚC KHI tới đây (`graph_tra_cuu._re_sau_route`,
        # KHÔNG còn qua `_RE_TAT`). `assemble` KHÔNG tự soạn gì ở đây — nó chỉ ĐỌC
        # những gì hai node đó đã tính (`soan_thao_dang_mo`/`ban_thao_ket`) và DỰNG
        # LỜI cho đúng bốn tình huống: không có checklist mở dở (Phase 14 — lượt
        # đã đi đường mô hình soạn, đọc kết quả ở `_ban_thao_tong_quat`); biết
        # loại nhưng thiếu dữ kiện, hoặc chưa đăng nhập,
        # hoặc đã hết hạn mức soạn thảo (hỏi lại — `soan_thao_hoi`); và đã có bản
        # thảo thật (`ban_thao`). Mọi điều khoản của bản thảo đó vẫn neo bằng đúng
        # con đường checklist/rules/graph_soan_thao cũ — không văn xuôi tự do nào
        # được sinh thành điều khoản pháp lý ở đây.
        #
        # CỐ Ý gác CHỈ trên `intent` (state coordinator review, sau khi lượt đầu
        # triển khai): một `soan_thao_dang_mo` còn ở phiên KHÔNG được tự nó kéo
        # nhánh này vào, kể cả khi `intent` lượt này là `gioi_thieu`/`hoi_ve_kho`/
        # `ngoai_pham_vi` (rẽ tắt thẳng tới đây từ `_RE_TAT`, không qua
        # `gom_du_kien`) hay `tra_cuu` (đi hết đường tra cứu, không rẽ tắt) — cả
        # hai đường đó phải rơi đúng vào các nhánh CỦA CHÍNH intent đó bên dưới,
        # không phải bị hớt tay trên bởi một draft cũ. `route.v3.md` đã có
        # `{dang_soan}` để tự phân biệt câu trả lời dữ kiện với một câu hỏi luật
        # thật — đây là nơi DUY NHẤT tôn trọng phán đoán đó.
        sd = state.get("soan_thao_dang_mo")
        if not sd:
            # Phase 14 (R1) — không có checklist mở dở thì lượt này đã đi
            # `hieu_tai_lieu`/`dung_ban_thao_tong_quat` (hoặc là khách, rẽ
            # thẳng từ `route`): đọc kết quả của đường đó — bản thảo, lời mời
            # đăng nhập, hay lý do chưa soạn được — không còn lời chỉ sang
            # "Chọn loại văn bản".
            return _ban_thao_tong_quat(state)
        ten = _ten_loai(sd["loai"])
        # `soan_thao_goi_y=None` tường minh trong CẢ BỐN nhánh dưới đây (khác
        # nhánh `not sd` ngay trên, nơi nó CHÍNH LÀ kết quả): `route()` đã đặt
        # `state["soan_thao_goi_y"]` thành một dict CHƯA ĐỦ khoá cho
        # `SoanThaoGoiYOut` (`loai`/`ly_do`/`thay_the`, thiếu `ten`/`ho_tro`)
        # bất cứ khi nào intent là `soan_thao` — trước Task 19, `assemble` LUÔN
        # đi qua `_goi_y_soan_thao()` (hàm ngay trên) nên khoá đó luôn được GHI
        # ĐÈ bằng bản đủ. Bốn nhánh này không gọi hàm đó, nên nếu không dọn,
        # dict thiếu khoá của `route()` lọt thẳng ra `_payload_cache["soan_thao"]`
        # rồi vỡ `pydantic.ValidationError` ở `tra_cuu_response` — ĐO ĐƯỢC bằng
        # chính bộ test đầu-cuối của task này trước khi có dòng sửa này.
        if ((state.get("ban_thao_ket") or {}).get("khuon") or {}).get("nguon") == "khuon_mau":
            # Bản thảo checklist trên khuôn mẫu (§3): cùng lời đáp của bản tổng quát.
            return _ban_thao_khuon_mau(state, state["ban_thao_ket"])
        if state.get("ban_thao_ket"):
            bt = state["ban_thao_ket"]
            doi = bt.get("doi_so_voi_truoc") or []
            answer = (
                f"Bản thảo {ten} phiên bản {bt['phien_ban']} đã sẵn sàng"
                + (f", đã đổi: {', '.join(doi)}" if doi else "")
                + ". Bạn xem, sửa từng mục hoặc tải về ở bên cạnh; muốn đổi gì cứ nói với tôi."
            )
            return _base(state, ResultType.ban_thao, answer=answer, ban_thao=bt, soan_thao_goi_y=None)
        if state.get("user_sub") is None:
            return _base(
                state,
                ResultType.soan_thao_hoi,
                answer=LOI_SOAN_THAO_DANG_NHAP,
                soan_thao_goi_y=None,
                soan_thao_hoi={
                    "loai": sd["loai"],
                    "ten": ten,
                    "da_co": sd["facts"],
                    "con_thieu": [],
                    "chip": {},
                    "het_han_muc": None,
                    "can_dang_nhap": True,
                },
            )
        if sd.get("het_han_muc"):
            return _base(
                state,
                ResultType.soan_thao_hoi,
                answer=sd["het_han_muc"],
                soan_thao_goi_y=None,
                soan_thao_hoi={
                    "loai": sd["loai"],
                    "ten": ten,
                    "da_co": sd["facts"],
                    "con_thieu": [],
                    "chip": {},
                    "het_han_muc": sd["het_han_muc"],
                    "can_dang_nhap": False,
                },
            )
        thieu = sd.get("con_thieu") or []
        chip = {t["key"]: t["lua_chon"] for t in thieu if t.get("lua_chon")}
        answer = (
            f"Để soạn {ten}, tôi cần thêm:"
            + "".join(f"\n- {t['nhan']}" for t in thieu)
            + '\n\nBạn trả lời tự nhiên trong một tin là đủ; thiếu gì cứ nói "cứ soạn", tôi để trống chỗ đó để bạn điền sau.'
        )
        return _base(
            state,
            ResultType.soan_thao_hoi,
            answer=answer,
            soan_thao_goi_y=None,
            soan_thao_hoi={
                "loai": sd["loai"],
                "ten": ten,
                "da_co": sd["facts"],
                "con_thieu": thieu,
                "chip": chip,
                "het_han_muc": None,
                "can_dang_nhap": False,
            },
        )

    if state.get("intent") == "gioi_thieu":
        # Xem chú thích ở nhánh `soan_thao` ngay trên: rẻ được là nhờ đường rẽ
        # tắt trong `graph_tra_cuu`, không nhờ riêng khâu này không gọi LLM.
        # ĐO ĐƯỢC 2026-09-02, TRƯỚC khi có đường rẽ: nhánh này tiêu 8.975 token
        # và dựng 15 luận điểm qua cả hai tầng rồi vứt sạch.
        #
        # `cau_gioi_thieu` chọn lời đáp theo DẠNG câu hỏi bằng quy tắc — vẫn 0
        # token, và cố ý KHÔNG nhận `llm`: model không biết nó đang chạy trên
        # model nào hay kho có gì, nên để nó tự sinh câu trả lời về chính mình
        # là mời đúng loại ảo giác hai tầng kiểm không bắt được (không có trích
        # dẫn nào để đối chiếu).
        #
        # `.get(...) or ""` chứ không phải `state["query"]`: câu rỗng rơi về bài
        # năng lực — mặc định an toàn — thay vì nổ ở một nhánh vốn không cần
        # truy vấn gì. Khác `tra_loi_kho` ngay dưới, nơi khoá thiếu LÀ lỗi nối
        # dây và một `answer` rỗng chính là chế độ hỏng cần nổ ra.
        # `tra_loi_gioi_thieu` is composed in `graph_tra_cuu.n_assemble` (it
        # owns the engine and the one `nap_kho`); direct callers without it
        # still get the kho-less answer.
        return _base(state, ResultType.gioi_thieu,
                     answer=state.get("tra_loi_gioi_thieu") or cau_gioi_thieu(state.get("query") or ""))

    if state.get("intent") == "hoi_ve_kho":
        # Chuỗi do `graph_tra_cuu.n_assemble` tính SẴN bằng SQL — khâu này chỉ
        # dán nó vào `answer`. Xem chú thích ở `n_assemble` để biết vì sao SQL
        # nằm ở đó chứ không ở đây (tóm lại: `assemble` không có `engine`, và
        # hợp đồng hiện hành đã là "node lo phần DB, assemble lo phần dựng lời"
        # — `db_provisions` cũng do node nạp sẵn).
        #
        # `state["tra_loi_kho"]` chứ không phải `.get(...) or ""`: thiếu khoá
        # này là một lỗi NỐI DÂY, và một `answer` rỗng chính là chế độ hỏng mà
        # cả nhánh này tồn tại để bỏ đi. Thà nổ ra một KeyError nhìn thấy được
        # còn hơn trả lại đúng cái màn hình trắng cũ.
        #
        # `bang` (T4) NGƯỢC LẠI dùng `.get(...) or []`: khác `answer`, một
        # `bang` rỗng là giá trị ĐÚNG cho phần lớn lượt hỏi về kho (câu hỏi
        # không xin bảng) — thiếu khoá không phải chế độ hỏng cần nổ ra, và
        # test cũ gọi `assemble()` với state chưa mang khoá này (trước T4)
        # vẫn phải chạy được.
        return _base(state, ResultType.hoi_ve_kho, answer=state["tra_loi_kho"],
                     bang=state.get("tra_loi_kho_bang") or [])

    if state.get("intent") == "ngoai_pham_vi":
        return _base(state, ResultType.out_of_scope, coverage_note=NGOAI_PHAM_VI)

    # Phép kiểm thứ sáu (coordinator, ở tầng ĐẦU VÀO — verify_tier1.tien_de_cau_hoi_sai,
    # chạy TRƯỚC rewrite/retrieve/generate trong graph). Câu hỏi tự nêu một
    # "Điều N [văn bản]" không có thật: KHÔNG được âm thầm trả lời một câu hỏi
    # khác rồi để tiền đề sai đứng nguyên — coverage_note nêu ĐÍCH DANH vấn đề
    # (vd. "Bộ luật Lao động không có Điều 999"), không phải một câu chung
    # chung "không đủ căn cứ".
    if state.get("tien_de_sai"):
        return _ngo_cut(state, llm, model, ResultType.abstain, ghi_chu=state["tien_de_sai"])

    # Câu hỏi nối tiếp không giải nghĩa được — cùng hình dạng với `tien_de_sai`
    # ngay trên: một vấn đề ở tầng ĐẦU VÀO, biết trước khi tra, và nhánh này chỉ
    # cấp một nửa đầu ĐÚNG cho ngõ cụt.
    #
    # Phải kiểm CẢ `lich_su`: `cau_hoi_day_du is None` một mình cũng đúng cho
    # lượt ĐẦU (nó không chạy `giai_nghia` bao giờ), và một lượt đầu không tìm
    # được gì thì `KHONG_TIM_DUOC` mới là câu đúng.
    #
    # KHÔNG đổi `result_type` và không thêm loại mới: pha này đổi LỜI của ngõ
    # cụt, không đổi KHI NÀO ngõ cụt.
    if state.get("lich_su") and state.get("cau_hoi_day_du") is None:
        return _ngo_cut(state, llm, model, ResultType.abstain, ghi_chu=CHUA_GIAI_NGHIA_DUOC)

    deep = state.get("expanded") or []
    shallow = state.get("hits_shallow") or []

    # PARTIAL_COVERAGE — KHÔNG gọi LLM hành văn: chỉ trúng tầng nông thì nêu luật
    # liên quan chứ không được dựng lời giải thích từ nội dung chưa kiểm chứng.
    #
    # Nửa đầu KHÔNG nêu `duong_dan` nữa: mọi dòng tầng nông đều là hàng `mo_dau`
    # của migration 016, nên câu cũ in ra "liên quan 84/2015/QH13 > Mở đầu" —
    # một vị trí không tồn tại như một vị trí. Xem `_van_ban_va_vi_tri`.
    #
    # Và nửa đầu KHÔNG còn nói "Câu hỏi của bạn nằm trong X". ĐO ĐƯỢC
    # 2026-09-02: "liệt kê bảng cho tôi" khớp NHIỄU hai văn bản `shallow` —
    # 120/2025/QH15 (Luật Phòng chống ma túy) và 8532 (Luật Thương mại) — và
    # người hỏi nhận về một câu khẳng định rằng câu hỏi của họ nằm trong Luật
    # Phòng chống ma túy. Đó là một lời nói SAI, không phải một lời nói mềm.
    #
    # Điều đúng được nói ra thay: mấy văn bản này KHỚP TỪ NGỮ trong câu hỏi, và
    # mình chưa có toàn văn để đọc. KHÔNG dựng bộ phân loại "câu hỏi có nội dung
    # pháp lý hay không" để chặn khớp nhiễu ở gốc — đó lại là một danh sách từ
    # khoá pháp lý cần thẩm quyền domain, đúng thứ đã bị từ chối cho bộ lọc
    # `hoi_lai`. Và điểm RRF không tới được tầng này: `KLawState.retrieved` là
    # `list[int]`, `Retriever.provision_ids()` bỏ điểm.
    def _phu_mot_phan() -> dict:
        ten, _ = _van_ban_va_vi_tri(shallow)
        # Gộp theo doc_id: nhiều Điều của cùng một văn bản là MỘT nguồn. Không
        # có doc_id thì bỏ qua dòng đó — thà thiếu một link còn hơn dựng một
        # link hỏng, và giao diện đã có `coverage_note` nêu tên văn bản.
        #
        # `so_ky_hieu`/`bo_luat` đi qua `hien_van_ban`: hai trường này là thứ
        # giao diện IN RA cạnh nút mở văn bản gốc, còn khoá dựng URL là `doc_id`
        # — nên làm sạch chúng không đụng tới đường tra cứu nào.
        nguon: list[dict] = []
        for p in shallow:
            doc_id = str(p.get("document_id") or "")
            if doc_id and not any(n["doc_id"] == doc_id for n in nguon):
                so, ten_vb = hien_van_ban(p.get("so_ky_hieu") or "", p.get("ten") or "")
                nguon.append({**truong_trich_dan(p), "doc_id": doc_id, "so_ky_hieu": so, "bo_luat": ten_vb})
        return _ngo_cut(state, llm, model, ResultType.partial_coverage, nguon=nguon, ghi_chu=(
            f"Tôi tìm được {'; '.join(ten)} khớp từ ngữ với câu hỏi của bạn. "
            f"{'Văn bản này' if len(ten) == 1 else 'Những văn bản này'} tôi mới có tên, "
            "số hiệu và tình trạng hiệu lực — chưa có toàn văn tới từng điều khoản, nên "
            "tôi chưa đọc được nội dung để nói với bạn điều gì chắc chắn, và cũng chưa "
            "chắc được nó có đúng là chỗ trả lời câu hỏi của bạn hay không. Bạn mở được "
            "văn bản gốc ngay dưới đây."
        ))

    # Gọi khi truy hồi CHỈ chạm tầng nông.
    if not deep and shallow:
        return _phu_mot_phan()

    if state.get("insufficient_evidence"):
        # ĐO ĐƯỢC 2026-09-01: "Nghị định 95/2026 quy định gì?" truy hồi 18 kết
        # quả — 16 tầng sâu KHÔNG LIÊN QUAN và 2 tầng nông ĐÚNG. Điều kiện
        # `not deep` ở trên thấy `deep` khác rỗng nên bỏ qua, rồi
        # `generate_claims` sinh 0 luận điểm từ 16 nguồn kia, và người hỏi nhận
        # một `abstain` trơ — trong khi hệ thống đang cầm đúng tên văn bản chi
        # phối câu hỏi.
        #
        # Nhánh này chỉ NÂNG CẤP một `abstain`. Nó không thể chen chỗ một câu
        # trả lời thật: mọi đường có luận điểm dùng được đều nằm phía dưới và
        # không đi qua đây.
        if shallow:
            return _phu_mot_phan()
        return _ngo_cut(state, llm, model, ResultType.abstain, giai_thich=True)

    tier1 = state.get("tier1") or []
    tier2 = {v.claim_index: v for v in (state.get("tier2") or [])}
    qua_t1 = [r for r in tier1 if r.ok]

    if not tier1 or not qua_t1:
        return _ngo_cut(state, llm, model, ResultType.abstain, giai_thich=True)

    # RULING 2026-08-31 (task-9 review) — brief gốc có một nhánh
    # `if tier2 else not tier2` khiến "tier2 rỗng toàn bộ" mặc định COI NHƯ ĐÃ
    # VERIFIED cho mọi claim qua tầng 1. Nhánh đó đã bị BỎ CÓ CHỦ Ý —
    # ĐỪNG khôi phục lại cho khớp brief.
    #
    # Khớp tier2 theo VỊ TRÍ trong qua_t1 (claim_index của Tier2Verdict được đánh
    # số lại từ 0 trên chính tập đã qua tầng 1 — xem verify_tier2._build_prompt).
    # Thiếu verdict cho một vị trí ⇒ KHÔNG verified, vô điều kiện — không có
    # nhánh "tier2 rỗng toàn bộ thì coi như đã qua": verify_tier2 luôn trả đúng
    # len(qua_t1) verdict khi qua_t1 khác rỗng (kể cả lỗi JSON, nó default
    # supported=False chứ không trả rỗng), nên tier2 rỗng trong khi qua_t1 khác
    # rỗng chỉ có thể là caller QUÊN nối tầng 2 — coi đó là "đã verified" sẽ âm
    # thầm tắt cả tầng 2 cho toàn bộ batch, đúng lớp lỗi mà cả dự án chống: mặc
    # định an toàn khi THIẾU bộ kiểm phải là CHƯA kiểm chứng, không phải đã kiểm
    # chứng — cùng quy tắc "mặc định false khi không chắc" mà verify_tier2 đã lập.
    #
    # GĐ3 giữ verdict đi KÈM claim (`verified_v`): `relevant`/`overstated` là bộ
    # lọc VĂN XUÔI ở vòng lặp dưới, KHÔNG phải phép kiểm quyết định abstain — tỉ
    # lệ và ngưỡng ở ngay dưới đây tính trên đúng tập `supported` như trước.
    verified_v = [(r, v) for pos, r in enumerate(qua_t1) if (v := tier2.get(pos)) is not None and v.supported]
    verified = [r for r, _ in verified_v]
    ty_le = len(verified) / len(tier1)
    if not verified or ty_le < float(state.get("abstain_threshold", ABSTAIN_THRESHOLD_DEFAULT)):
        return _ngo_cut(state, llm, model, ResultType.abstain, giai_thich=True)

    citations: list[Citation] = []
    warnings: list[str] = []
    # Phép kiểm thứ bảy: chỉ những claim ở đây mới được nạp vào lời nhắc hành
    # văn (`claims_txt` bên dưới) — citations vẫn liệt kê ĐỦ mọi claim đã qua
    # tầng 1+2, kể cả cái bị loại khỏi prose (kèm `hieu_luc` để phân biệt).
    dung_cho_prose: list = []
    nguon_bi_loc: list[str] = []
    # N1 (silent-failure review round 2): phép kiểm thứ năm phải so `answer`
    # với tập citation THỰC SỰ dùng để dựng văn xuôi, không phải toàn bộ
    # `citations` — nếu không, một số Điều tới từ nguồn VỪA BỊ LOẠI (bi_thay_the/
    # het_hieu_luc, không neo) vẫn được coi là "có căn cứ" vì nó tình cờ có mặt
    # ở đâu đó trong `citations`, dù chính prompt hành văn chưa từng thấy nó.
    citations_dung_cho_prose: list = []
    # Chỉ số (trong `citations`) của những căn cứ ĐÚNG LUẬT nhưng LẠC ĐỀ — tầng 2
    # (prompt v2) chấm `relevant=False`/`overstated=True`. Chúng ở lại `citations`
    # với `k=None`, y như nguồn bị lọc vì hiệu lực: vết kiểm toán không được mất.
    lac_de: list[int] = []
    for i, (r, v2) in enumerate(verified_v):
        # row_id = dòng THẬT hiển thị (xem docstring `Citation`) — ghi lại
        # NGUYÊN VẸN vào citation dưới tên `khop_tai_id`, tường minh, thay vì
        # đổi ngầm chỉ trong duong_dan/bo_luat/so_ky_hieu. Rơi về
        # claim.provision_id khi khop_tai vắng (None, hoặc trỏ tới id không có
        # trong db_provisions) — khi đó khop_tai_id == provision_id, đúng
        # nghĩa "không có Khoản con nào khác để tách".
        khop_tai = r.khop_tai
        row_id = khop_tai if khop_tai is not None and khop_tai in db_provisions else r.claim.provision_id
        # KHÔNG `.get(row_id, {})`: một id thiếu ở đây là bất biến bị vỡ, không
        # phải dữ liệu vắng. Rơi về `{}` phát ra citation `duong_dan`/`so_ky_hieu`
        # RỖNG nhưng vẫn đếm là "đã kiểm chứng" — nó vào tỉ lệ quyết định abstain
        # và hiện ra cạnh một `quote` thật. Trên sản phẩm này, một trích dẫn rỗng
        # đội lốt đã-kiểm-chứng là kiểu hỏng tệ nhất có thể có, nên nó phải NỔ.
        if row_id not in db_provisions:
            raise KeyError(
                f"db_provisions thiếu provisions.id={row_id} mà claim đã qua tầng 1 đang dẫn "
                f"(provision_id={r.claim.provision_id}, khop_tai={r.khop_tai}) — bất biến vỡ"
            )
        p = db_provisions[row_id]
        eff = r.effectivity
        so_ky_hieu = p.get("so_ky_hieu", "")
        citations.append({
            # Quyết định 2026-09-28: tên đầy đủ, cơ quan, ngày, link chính thống
            # và câu trích theo mẫu luật — dựng theo ĐÚNG dòng hiển thị (`p`).
            **truong_trich_dan(p, p.get("duong_dan")),
            "provision_id": r.claim.provision_id,
            "khop_tai_id": row_id,
            "doc_id": str(p.get("document_id") or ""),
            "duong_dan": p.get("duong_dan", ""),
            "bo_luat": p.get("ten", ""),
            "so_ky_hieu": so_ky_hieu,
            "quote": r.claim.quote,
            "hieu_luc": eff.verdict.value if eff else None,
            "tin_cay": eff.tin_cay if eff else None,
            # Spec 2026-09-06 §3: gán số sau vòng lặp, chỉ cho căn cứ dùng hành văn.
            "k": None,
            # GĐ3 — vai trò của căn cứ (kết luận/điều kiện/ngoại lệ/chế tài).
            # `None` với prompt sinh v2; giao diện nhóm được căn cứ khi có.
            "vai_tro": r.claim.vai_tro,
            "canh_bao": None,
        })
        if eff and eff.verdict in CANH_BAO_NHAN:
            # Lời cho người đọc (`hien_thi.canh_bao`), nêu đích danh văn bản sửa
            # đổi/thay thế khi phán quyết có văn bản làm chứng — không `ly_do`,
            # không mã nội bộ (quyết định 2026-09-28 mục 10).
            # Nhãn ĐỌC ĐƯỢC, không phải khoá dữ liệu: `so_ky_hieu` thật thì đi
            # qua nguyên vẹn, còn 'Không số' rơi về tên văn bản (`hien_van_ban`).
            # `citations[].so_ky_hieu` ngay trên thì GIỮ NGUYÊN giá trị DB — nó
            # là khoá, và `_neo_vao_van_ban` bên dưới so trên chính giá trị đó.
            so_hien, ten_hien = hien_van_ban(so_ky_hieu, p.get("ten") or "")
            msg = canh_bao(so_hien or ten_hien, eff)
            # Cùng câu, gắn vào CHÍNH trích dẫn: `warnings[]` giữ nguyên hình
            # dạng cho mọi bên đang đọc nó.
            citations[-1]["canh_bao"] = msg
            if msg not in warnings:
                warnings.append(msg)

        if eff and eff.verdict in _VERDICT_BI_THAY and not _neo_vao_van_ban(state.get("query", ""), so_ky_hieu):
            nguon_bi_loc.append(so_ky_hieu)
        elif v2.relevant is False or v2.overstated is True:
            # Tầng 2 nói điều luật CHỐNG ĐỠ khẳng định, nhưng khẳng định không
            # trả lời điều được hỏi (hoặc nói rộng hơn điều luật cho phép). Đây
            # là bộ lọc VĂN XUÔI, không phải một phép kiểm chứng thứ ba: trích
            # dẫn vẫn ở lại `citations`, chỉ không được dựng thành câu.
            lac_de.append(i)
        else:
            dung_cho_prose.append(r)
            citations_dung_cho_prose.append(citations[-1])

    # Toàn bộ nguồn dùng-được-cho-prose đã bị lọc (mọi citation đều bi_thay_the/
    # het_hieu_luc và câu hỏi không neo văn bản nào) → KHÔNG dựng câu trả lời
    # tự tin. LLM HÀNH VĂN không được gọi ở đây: đã biết trước không có gì hợp
    # lệ để hành văn. (Câu hỏi lại trong `_ngo_cut` là một lượt gọi KHÁC, với
    # schema khác, và nó không dựng khẳng định pháp luật nào.)
    if not dung_cho_prose:
        # Hai lý do khác nhau, hai câu khác nhau: nguồn đã bị thay thế (nói tên
        # văn bản đi thay), hay nguồn còn sống mà lạc đề (`LAC_DE`). Nói nhầm lý
        # do là nói sai với người hỏi, không phải một sắc thái.
        ket = _ngo_cut(state, llm, model, ResultType.abstain, giai_thich=True,
                       ghi_chu=_ly_do_moi_nguon_bi_thay(verified) if nguon_bi_loc else LAC_DE)
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
        ket["traces"]["assemble_lac_de"] = lac_de
        return ket

    # Kèm `duong_dan` ĐÃ XÁC MINH của từng khẳng định: prompt hành văn nay cho
    # phép dẫn số Điều ngay trong lời văn (giọng luật sư), và cách duy nhất để
    # việc đó an toàn là mô hình chỉ nhìn thấy đúng những số Điều đã qua tầng
    # 1+2. `_dieu_khong_duoc_chong_do` vẫn là lưới cuối: nhắc một số Điều ngoài
    # tập này thì cả câu trả lời bị hạ xuống abstain.
    #
    # `strict=True` khoá bất biến hai danh sách khớp chỉ số — chúng được append
    # cùng một nhánh `else` ở vòng lặp trên, và nếu ai đó tách chúng ra thì lỗi
    # phải nổ ở đây chứ không phải hiện thành một trích dẫn gắn nhầm khẳng định.
    #
    # GĐ3: xếp/khử trùng/cắt trần CHẠY TRƯỚC khi đánh số `k` — `k` là số thứ tự
    # mô hình sẽ gõ vào thẻ `cite:K`, nên nó phải đánh trên ĐÚNG tập cuối cùng.
    # Gác bằng "có claim nào mang vai trò không": prompt sinh v2 (mặc định) không
    # có vai trò nào, tập claim đi qua y nguyên như trước.
    co_vai_tro = any(r.claim.vai_tro for r in dung_cho_prose)
    if co_vai_tro:
        dung_cho_prose, citations_dung_cho_prose = _chon_cho_prose(
            dung_cho_prose, citations_dung_cho_prose, state.get("query", "")
        )
    for so, c in enumerate(citations_dung_cho_prose, start=1):
        c["k"] = so
    documents = _dung_documents(citations_dung_cho_prose, db_provisions)

    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    # Template có `{van_ban}` là template biết thẻ (v2): căn cứ đánh số [K] để
    # mô hình đặt `cite:K`. Template v1 giữ NGUYÊN định dạng cũ — A/B v1-v2
    # phải đo đúng prompt cũ, không phải một v1 đã bị đổi ruột.
    #
    # Template có `{muc_chac}` là template BIẾT VAI TRÒ (v6): mỗi căn cứ in kèm
    # vai trò của nó để mô hình xếp đúng tầng. Không có vai trò nào (prompt sinh
    # v2) thì giữ nguyên hai định dạng cũ — v6 vẫn chạy được, chỉ không có nhãn.
    if "{muc_chac}" in mau and co_vai_tro:
        claims_txt = "\n".join(
            f"[{c['k']}] ({_VAI_TRO_HIEN.get(r.claim.vai_tro) or 'không rõ'}) "
            f"{c['duong_dan']} — {c['bo_luat']}\n    {r.claim.text}"
            for r, c in zip(dung_cho_prose, citations_dung_cho_prose, strict=True)
        )
    elif "{van_ban}" in mau:
        claims_txt = "\n".join(
            f"[{c['k']}] {c['duong_dan']} — {c['bo_luat']}\n    {r.claim.text}"
            for r, c in zip(dung_cho_prose, citations_dung_cho_prose, strict=True)
        )
    else:
        claims_txt = "\n".join(
            f"- {r.claim.text}\n  (căn cứ: {c['duong_dan']} — {c['bo_luat']})"
            for r, c in zip(dung_cho_prose, citations_dung_cho_prose, strict=True)
        )
    khung = state.get("khung_yeu_cau") or {}
    ho_so = state.get("ho_so") or {}
    muc_chac = tinh_muc_chac(dung_cho_prose, khung, ho_so)
    thieu = _du_kien_quyet_dinh_thieu(khung, ho_so)
    prompt = mau.format(
        cau_hoi=state.get("query", ""),
        # `lich_su or tom_tat`: cùng định nghĩa "phiên đã có ngữ cảnh" mà
        # `graph_tra_cuu._vao_giai_nghia` đang dùng. Chỉ xét `lich_su` thì một
        # phiên vừa bị rút gọn lịch sử về rỗng sẽ bị chào lại như người lạ.
        mo_dau=MO_DAU_NOI_TIEP if (state.get("lich_su") or state.get("tom_tat")) else MO_DAU_LUOT_DAU,
        van_ban=_khoi_van_ban(citations_dung_cho_prose, db_provisions),
        claims=claims_txt,
        # Lượt đối chiếu: điều khoản đã neo đi kèm hồ sơ tình huống, dưới nhãn
        # "KHÔNG phải căn cứ" của chính ô này. Lượt khác: đúng chuỗi cũ.
        tinh_huong=khoi_tinh_huong_doi_chieu(state.get("ho_so") or {}, state.get("tai_lieu_neo") or []),
        # GĐ2–GĐ4. Kwargs THỪA với v1/v3/v5 — `str.format` bỏ qua chúng, nên các
        # prompt đang đo không đổi một ký tự nào.
        muc_tieu=khung.get("muc_tieu") or state.get("query", ""),
        cau_hoi_phap_ly=khung.get("cau_hoi_phap_ly") or "",
        muc_chac=MUC_CHAC_LOI[muc_chac],
        # `bi_loai` chạy trên chuỗi ĐI VÀO prompt (không phải trên phép tính
        # `muc_chac`): một dữ kiện còn thiếu vẫn phải hạ giọng kể cả khi câu hỏi
        # của nó bị loại, nhưng một câu tự phát biểu mốc pháp lý thì không được
        # vào ngữ cảnh của người viết — đó là mốc không trích dẫn nào chống đỡ.
        du_kien_thieu="; ".join(m["cau"] for m in thieu
                                if m.get("cau") and not bi_loai(m["cau"])) or "(không)",
        # Lượt nối tiếp: mô hình trả lời PHẦN MỚI trong câu vừa gõ, còn câu đã
        # giải nghĩa chỉ để hiểu ngữ cảnh (cai_thien.md §6 GĐ4).
        cau_hoi_goc=state.get("cau_hoi_goc") or state.get("query", ""),
        cau_hoi_day_du=state.get("cau_hoi_day_du") or state.get("query", ""),
    )
    usage: Usage | None = None
    degraded = False
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=ANSWER_SCHEMA)
        answer = json.loads(raw)["answer"]
    except Exception as e:
        # Suy biến AN TOÀN, không phải lỗi im lặng: nội dung fallback là chính
        # các claim ĐÃ qua cả hai tầng verify, nên không phải rủi ro ảo giác —
        # chỉ kém trau chuốt hơn. Khác `route.py` (lỗi hạ tầng phải nổ vì đó là
        # quyết định định tuyến): đây là bước hành văn CUỐI CÙNG, không còn
        # quyết định hạ nguồn nào phụ thuộc vào nó. Vẫn ĐẾM qua traces/log —
        # không được vô hình, cùng khuôn rewrite_query.py.
        logger.warning(
            "assemble: lỗi khi gọi LLM hành văn (%s: %s) — fallback nối các claim đã kiểm chứng, "
            "không bịa câu trả lời",
            type(e).__name__, e,
        )
        answer = " ".join(r.claim.text for r in verified)
        degraded = True

    # Phép kiểm thứ tám + chín — chạy trên CẢ đường LLM và đường fallback (fallback
    # nối claim.text không có thẻ, nhưng phép kiểm không giả định đường nào an toàn).
    the_loi = _the_khong_hop_le(answer, citations_dung_cho_prose, {c["doc_id"] for c in citations_dung_cho_prose})
    if the_loi:
        logger.warning(
            "assemble: thẻ/URL không hợp lệ trong answer — hạ xuống abstain (%s): %s",
            LY_DO_THE_KHONG_HOP_LE,
            the_loi,
        )
        ket = _ngo_cut(state, llm, model, ResultType.abstain, usage=usage, degraded=degraded)
        ket["traces"]["assemble_the_loi"] = the_loi
        ket["traces"]["assemble_dieu_bi_loai"] = []
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
        ket["traces"]["assemble_lac_de"] = lac_de
        return ket

    # Phép kiểm thứ năm — xem docstring `_dieu_khong_duoc_chong_do`. Chạy SAU
    # khi có `answer` thật (kể cả đường fallback ở trên): fallback nối
    # nguyên văn claim.text nên về lý thuyết không tự bịa số Điều, nhưng kiểm
    # vẫn chạy trên CẢ HAI đường — phép kiểm không được giả định đường nào
    # "chắc chắn an toàn". So với `citations_dung_cho_prose`, KHÔNG PHẢI
    # `citations` đầy đủ (N1, silent-failure review round 2): `citations` còn
    # chứa cả nguồn đã bị phép kiểm thứ bảy loại khỏi văn xuôi (bi_thay_the/
    # het_hieu_luc, không neo) — so với tập đó sẽ cho một số Điều đến từ nguồn
    # VỪA BỊ LOẠI vẫn qua sạch, dù chính prompt hành văn chưa từng thấy nó.
    dieu_bi_loai = _dieu_khong_duoc_chong_do(answer, citations_dung_cho_prose)
    if dieu_bi_loai:
        logger.warning(
            "assemble: answer nhắc Điều %s không có trong citations đã xác minh — hạ xuống abstain (%s)",
            ", ".join(dieu_bi_loai), LY_DO_DIEU_KHONG_CHONG_DO,
        )
        ket = _ngo_cut(state, llm, model, ResultType.abstain, usage=usage, degraded=degraded)
        ket["traces"]["assemble_dieu_bi_loai"] = dieu_bi_loai
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
        ket["traces"]["assemble_the_loi"] = []
        ket["traces"]["assemble_lac_de"] = lac_de
        return ket

    # Phép kiểm thứ MƯỜI MỘT (QT-1) — chỉ gác lượt ĐỐI CHIẾU LUẬT, tức lượt duy
    # nhất mà người hỏi đặt tài liệu của chính họ lên bàn và câu họ muốn nghe là
    # một phán quyết. Gác bằng `tai_lieu_neo`: nó khác rỗng đúng khi và chỉ khi
    # `_re_sau_hieu_tai_lieu` đã đẩy lượt này sang đường pháp lý.
    if state.get("tai_lieu_neo"):
        cum = cau_phan_quyet(answer, citations_dung_cho_prose)
        if cum:
            logger.warning(
                "assemble: answer ra phán quyết (%r) trên lượt đối chiếu — hạ xuống ngõ cụt (%s)",
                cum, LY_DO_PHAN_QUYET,
            )
            # Chặn VĂN XUÔI, KHÔNG chặn CĂN CỨ. Đo toàn tuyến 2026-09-16: bản
            # trước hạ cả lượt xuống `abstain` với `citations: []`, và người hỏi
            # mất luôn `45/2019/QH14 > Điều 25 > Khoản 2` đã qua hai tầng kiểm —
            # tức mất đúng thứ sản phẩm này tồn tại để đưa ra. Chỉ câu kết luận
            # là sai; căn cứ thì không. `abstain` cũng nói sai sự thật: nó nghĩa
            # là KHÔNG đủ căn cứ (PRODUCT.md), mà ở đây căn cứ có và đã kiểm.
            #
            # Văn xuôi phát hành dựng TỪ chính các luận điểm đã kiểm
            # (`_neu_luat_thay_phan_quyet`), nên mọi số Điều trong nó đã nằm sẵn
            # trong `citations` — hai phép kiểm thẻ và số Điều ở trên vẫn đúng
            # mà không phải chạy lại.
            ket = _base(
                state, ResultType.answer, usage=usage, degraded=degraded,
                answer=_neu_luat_thay_phan_quyet(dung_cho_prose, citations_dung_cho_prose,
                                                 state.get("tai_lieu_neo") or []),
                citations=citations, warnings=warnings, documents=documents,
            )
            ket["traces"]["assemble_phan_quyet_bi_chan"] = cum
            ket["traces"]["assemble_dieu_bi_loai"] = []
            ket["traces"]["assemble_the_loi"] = []
            ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
            ket["traces"]["assemble_lac_de"] = lac_de
            return ket

    # Phép kiểm thứ mười — hình dạng, 0 token. Chạy SAU hai phép kiểm thẻ và số
    # Điều: cắt bớt nội dung chỉ có thể LOẠI thẻ chứ không sinh thẻ mới, nên thứ
    # phát hành ra vẫn là tập con của văn bản đã qua kiểm. Làm ngược lại thì một
    # gạch mang thẻ hỏng có thể bị cắt đi và thoát khỏi lưới.
    do_dai_truoc = len(answer)
    answer, gach_bo = cat_gach_thua(answer)
    # `do_dai_truoc` là độ dài mô hình VIẾT RA, `do_dai` là độ dài PHÁT HÀNH. Giữ
    # cả hai để một lượt đo duy nhất nói được cả hiệu quả của prompt lẫn hiệu quả
    # của phép cắt — không cần một lượt đo riêng cho bản chưa có phép cắt.
    hinh_dang = {"gach_bo": gach_bo, "do_dai_truoc": do_dai_truoc,
                 "do_dai": len(answer), "vuot_tran": len(answer) > TRAN_KY_TU}
    if gach_bo or hinh_dang["vuot_tran"]:
        logger.warning(
            "assemble: hình dạng vượt trần (bỏ %d gạch, %d ký tự) — ghi nhận, KHÔNG xén chữ",
            gach_bo, hinh_dang["do_dai"],
        )

    ket = _base(state, ResultType.answer, usage=usage, degraded=degraded,
                answer=answer, citations=citations, warnings=warnings, documents=documents)
    ket["traces"]["assemble_hinh_dang"] = hinh_dang
    ket["traces"]["assemble_dieu_bi_loai"] = []
    ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
    ket["traces"]["assemble_the_loi"] = []
    ket["traces"]["assemble_lac_de"] = lac_de
    ket["traces"]["assemble_muc_chac"] = muc_chac
    # Task 15: bảng so sánh chỉ dựng khi router (v3) đã đoán người hỏi xin so
    # sánh (`dang_tra_loi == "bang"`) — dựng TỪ `dung_cho_prose`/
    # `citations_dung_cho_prose`, tức đúng tập claim ĐÃ qua cả hai tầng kiểm
    # VÀ chưa bị phép kiểm thứ bảy loại khỏi văn xuôi. `[]` khi không đủ đối
    # tượng/tiêu chí để dựng bảng — KHÔNG phải lỗi, coi như câu hỏi này chỉ trả
    # lời được bằng văn xuôi.
    if state.get("dang_tra_loi") == "bang":
        b = dung_bang_tu_luan_diem(dung_cho_prose, citations_dung_cho_prose)
        ket["bang"] = [b.model_dump()] if b else []
    # Task 14: một câu trả lời ĐÃ CÓ luận điểm được phép mang thêm đúng MỘT đuôi
    # hỏi thêm ngắn (QT-5), 0 token — KHÔNG spliced vào `answer` (nó vẫn phải
    # sạch markdown và chỉ chứa điều đã có căn cứ), mà đi vào `coverage_note`,
    # cùng trường FE đã dùng để hiện nửa sau của một ngõ cụt.
    # Chỉ hỏi lại thứ lượt này vừa ĐOÁN (spec 2026-09-16 §FR-011). Tín hiệu là
    # kết quả suy diễn của chính lượt, không phải hồ sơ còn trống.
    # GĐ4: khung yêu cầu hỏi TRƯỚC — nó nêu được dữ kiện quyết định của chính vụ
    # việc (lý do chấm dứt, hành vi vi phạm), thứ sáu chiều hồ sơ chung không có
    # từ vựng để hỏi. `or` giữ bất biến "nhiều nhất MỘT đuôi": khung im thì mới
    # tới đuôi cũ, và khung im là mặc định (rewrite v2 không dựng khung).
    duoi = (duoi_tu_khung(khung, ho_so)
            or duoi_hoi_them(ho_so, (state.get("traces") or {}).get("suy_dien_chu_the")))
    if duoi:
        ket["coverage_note"] = "\n\n".join(x for x in (ket.get("coverage_note"), duoi) if x)
    # Ý định PHỤ (router v3, spec 2026-09-09 §7.4): câu hỏi vừa hỏi luật vừa
    # nhờ soạn — KHÔNG hijack `answer` (nó vẫn là câu trả lời tra cứu bình
    # thường), chỉ đính kèm gợi ý soạn thảo, cùng hàm dựng `_ban_thao_tong_quat`
    # dùng cho lời mời biểu mẫu (R3).
    if state.get("y_dinh_phu") == "soan_thao":
        ket["soan_thao_goi_y"] = _goi_y_soan_thao(state.get("soan_thao_goi_y"))
    return ket
