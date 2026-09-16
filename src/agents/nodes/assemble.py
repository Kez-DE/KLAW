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
ấy đã bị gỡ có chủ ý, không phải bỏ sót. Cái KHÔNG đổi: LLM hành văn vẫn không
bao giờ được gọi trên một ngõ cụt (`test_*_KHONG_goi_LLM_hanh_van`) — một lượt
không có căn cứ tuyệt đối không được dựng ra văn xuôi giải thích pháp luật.

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
nghị định đã bị thay thế là "còn hiệu lực". Task 2 sửa được cả 4 và
`Effectivity.ly_do` nêu đích danh văn bản thay thế — nên khi verdict rơi vào
`CANH_BAO_NHAN`, nguyên văn `ly_do` phải lên tới người dùng, không phải chỉ
nằm trong traces.
"""

import json
import logging
import re
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from src.agents.graph_soan_thao import cac_loai, load_checklist_cached
from src.agents.nodes.gioi_thieu import cau_gioi_thieu
from src.agents.nodes.hoi_lai import duoi_hoi_them, hoi_lai
from src.agents.nodes.verify_tier1 import normalize, van_ban_neo_boi_ten
from src.models.schemas import Bang
from src.services.bao_ve import LOI_SOAN_THAO_DANG_NHAP
from src.services.bo_nho import ho_so_da_dung, khoi_tinh_huong
from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import hien_van_ban
from src.services.llm import Usage
from src.services.prompts import messages

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
    cột migration 019; NULL đi nguyên qua để giao diện bỏ dòng đó."""
    return [
        {
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
# Giá trị CHỈ LÀ NHÃN NGẮN để phân loại — câu cảnh báo THẬT ghép nhãn với
# `eff.ly_do` NGUYÊN VĂN (xem chỗ dùng bên dưới), không phải chính câu cảnh
# báo. `ly_do` mới là nơi nêu ĐÍCH DANH văn bản thay thế (spec, yêu cầu #1) —
# một nhãn chung chung như "Văn bản này đã bị thay thế." xoá mất đúng thông
# tin đó, nên KHÔNG được dùng làm toàn bộ câu cảnh báo.
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


# Spec 2026-09-16 §2.6/§3.5/FR-007 — ba nhánh KHÔNG đọc `ho_so` để dựng câu trả
# lời, nên trả `ho_so_da_dung=[]` trong `_base`: hiện mảng này ("Dựa trên") thì
# là provenance sai, dù state có hồ sơ.
_KHONG_DUNG_HO_SO = frozenset({ResultType.gioi_thieu, ResultType.hoi_ve_kho, ResultType.out_of_scope})


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


def _ly_do_moi_nguon_bi_thay(qua_loc: list) -> str:
    """coverage_note khi TOÀN BỘ citation dùng-được-cho-prose đã bị lọc — nêu
    ĐÍCH DANH văn bản hiện hành (rút từ `ly_do`, không phải một câu chung
    chung). Không có `ly_do` nào nêu được kế nhiệm (Mức 1 hết hiệu lực không
    cạnh) thì nói rõ không xác định được, không bịa tên."""
    ke_nhiem = sorted({m for r in qua_loc for m in [_van_ban_ke_nhiem(r.effectivity.ly_do)] if m})
    if ke_nhiem:
        return (f"Những gì tôi tìm được cho câu hỏi này đều đã bị thay thế. Văn bản đi thay "
                f"là {', '.join(ke_nhiem)}, và nội dung của nó thì tôi chưa nạp vào kho, "
                f"nên tôi chưa đọc được để nói với bạn nó quy định thế nào.")
    return ("Những gì tôi tìm được cho câu hỏi này đều đã bị thay thế hoặc đã hết hiệu lực, "
            "và từ những gì tôi đang có thì tôi chưa xác định được văn bản nào đi thay.")


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


def _ngo_cut(state: dict, llm, model: str, rt: ResultType, ghi_chu: str | None = None,
             usage: Usage | None = None, degraded: bool = False, **kw: object) -> dict:
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
    """
    ho_so = state.get("ho_so") or {}
    da_biet = frozenset(k for k, v in ho_so.items() if isinstance(v, dict) and v.get("gia_tri"))
    hl = hoi_lai(state.get("query", ""), llm, model, da_biet=da_biet)
    ket = _base(
        state,
        rt,
        usage=_gop_usage(usage, hl.usage),
        degraded=degraded,
        coverage_note="\n\n".join(x for x in (ghi_chu or KHONG_TIM_DUOC, hl.cau) if x),
        **kw,
    )
    ket["traces"]["assemble_hoi_lai"] = hl.nguon
    return ket


# Câu trả lời cho `intent == gioi_thieu` sống ở `nodes/gioi_thieu.py`, KHÔNG ở
# đây. Trước 2026-09-02 nó là một hằng số `GIOI_THIEU` duy nhất, và hai câu hỏi
# khác nhau ("bạn làm được những gì" 09:21:36, "model của bạn là gì" 09:22:22 —
# bảng `traces`) nhận về đúng cùng 1.104 ký tự đó, từng chữ một. Nay câu hỏi được
# tách thành dạng bằng quy tắc; đây vẫn là MỘT `result_type`, chỉ `answer` đổi.


# Lời đáp khi router đoán ĐÚNG là `soan_thao` nhưng KHÔNG đoán được LOẠI văn
# bản nào (`state["soan_thao_dang_mo"]` rỗng sau `gom_du_kien` — xem nhánh
# `if not sd` bên dưới). Trước Task 19 đây là toàn bộ câu trả lời cho MỌI yêu
# cầu soạn thảo, vì assemble không tự soạn — giờ vẫn đúng ở CHÍNH nhánh này
# (không biết soạn gì thì không có dữ kiện nào để gom), nhưng khi loại ĐÃ biết
# thì lượt đi tiếp qua `gom_du_kien`/`dung_ban_thao` (graph_tra_cuu) và có thể
# dựng được một bản thảo thật ngay trong hội thoại — xem hai nhánh
# `soan_thao_hoi`/`ban_thao` ở dưới.
#
# CỐ Ý không liệt kê các loại soạn được ở đây. Tên hiển thị của chúng sống ở
# `mau-van-ban.ts` phía FE, và một bản sao thứ hai trong chuỗi Python này sẽ
# lệch pha đúng vào ngày ai đó thêm mẫu mới — màn soạn thảo tự liệt kê được.
HUONG_DAN_SOAN_THAO = (
    "Việc này tôi soạn được, nhưng không phải ở ô hỏi này.\n"
    "\n"
    "Để mỗi điều khoản trong bản thảo neo được vào một căn cứ pháp lý riêng, tôi "
    "cần biết loại văn bản và các dữ kiện cụ thể — các bên, thời hạn, mức lương, "
    "công việc. Một câu văn xuôi không cho tôi đủ, và tôi không muốn dựng cho bạn "
    "một văn bản mà chính tôi không chứng minh được nó dựa vào đâu.\n"
    "\n"
    "Bạn bấm Chọn loại văn bản bên dưới rồi điền biểu mẫu. Tôi dựng bản thảo "
    "kèm căn cứ cho từng điều khoản, đối chiếu lại nó với luật trong kho, rồi bạn "
    "tải về .docx hoặc .pdf."
)


# Spec soạn-thảo-trong-chat §4.2 — lời đáp khi router (v2) đã đoán được loại.
# Không nêu số Điều ở đây: căn cứ nằm trong từng mục của checklist, hiện ở khung
# soạn thảo, không phải trong câu mời.
GOI_Y_SOAN_THAO = (
    "Tôi hiểu bạn cần {ten}: {ly_do}\n"
    "\n"
    "Bạn điền dữ kiện ở khung bên cạnh, tôi dựng bản thảo kèm căn cứ cho từng mục, "
    "soát lại theo luật trong kho, rồi bạn tải .docx hoặc .pdf ngay tại đây."
)
GOI_Y_SOAN_THAO_CHUA_CO = "Kho mẫu của tôi chưa có loại văn bản này. {gan_nhat}"
GAN_NHAT_CO = "Gần nhất là {ten_thay_the} — bạn chọn một loại để tôi mở biểu mẫu."
GAN_NHAT_KHONG = (
    "Bạn mô tả rõ hơn văn bản cần soạn — ai lập, gửi cho ai, về việc gì — hoặc bấm Chọn loại văn bản bên dưới."
)
LY_DO_MAC_DINH = "đây là loại văn bản khớp với điều bạn mô tả."


def _ten_loai(loai: str) -> str:
    """Tên tiếng Việt của loại văn bản; `loai` không tra được checklist (YAML bị gỡ
    hay đổi tên sau khi phiên đã mở bản thảo loại đó) rơi về CHÍNH mã loại. Cùng
    lý do `route._dang_soan`: một câu trả lời hơi thô còn hơn một HTTP 500 ở node
    cuối, và đường hành văn của `assemble` vốn đã suy biến chứ không nổ."""
    try:
        return load_checklist_cached(loai).ten
    except ValueError:
        return loai


def _goi_y_soan_thao(tho: dict | None) -> tuple[dict | None, str]:
    """Kiểm 0 token gợi ý của router rồi dựng `soan_thao_goi_y` + `answer`.
    `loai` phải là checklist THẬT trên đĩa; `thay_the` lọc còn loại thật, khác
    `loai`, tối đa hai. Không có gợi ý (route v1) → lời hướng dẫn cũ."""
    if tho is None:
        return None, HUONG_DAN_SOAN_THAO
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
        gan = GAN_NHAT_CO.format(ten_thay_the=" hoặc ".join(t["ten"] for t in thay_the)) if thay_the else GAN_NHAT_KHONG
        return (
            {"loai": None, "ten": None, "ly_do": ly_do, "thay_the": thay_the, "ho_tro": False},
            GOI_Y_SOAN_THAO_CHUA_CO.format(gan_nhat=gan),
        )
    ten = _ten_loai(loai)
    return (
        {"loai": loai, "ten": ten, "ly_do": ly_do, "thay_the": thay_the, "ho_tro": True},
        GOI_Y_SOAN_THAO.format(ten=ten, ly_do=ly_do or LY_DO_MAC_DINH),
    )


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


def assemble(state: dict, db_provisions: dict[int, dict], llm, model: str, prompt_path: Path | None = None) -> dict:
    if state.get("intent") == "soan_thao":
        # Task 19 — lượt đã đi qua `gom_du_kien` (và, khi đủ dữ kiện và có tài
        # khoản, `dung_ban_thao`) TRƯỚC KHI tới đây (`graph_tra_cuu._re_sau_route`,
        # KHÔNG còn qua `_RE_TAT`). `assemble` KHÔNG tự soạn gì ở đây — nó chỉ ĐỌC
        # những gì hai node đó đã tính (`soan_thao_dang_mo`/`ban_thao_ket`) và DỰNG
        # LỜI cho đúng bốn tình huống: chưa biết loại văn bản (gợi ý cũ, đường sang
        # biểu mẫu đứng riêng); biết loại nhưng thiếu dữ kiện, hoặc chưa đăng nhập,
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
        if not sd:  # router không đoán được loại
            goi_y, answer = _goi_y_soan_thao(state.get("soan_thao_goi_y"))
            return _base(state, ResultType.huong_dan_soan_thao, answer=answer, soan_thao_goi_y=goi_y)
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
                nguon.append({"doc_id": doc_id, "so_ky_hieu": so, "bo_luat": ten_vb})
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
        return _ngo_cut(state, llm, model, ResultType.abstain)

    tier1 = state.get("tier1") or []
    tier2 = {v.claim_index: v for v in (state.get("tier2") or [])}
    qua_t1 = [r for r in tier1 if r.ok]

    if not tier1 or not qua_t1:
        return _ngo_cut(state, llm, model, ResultType.abstain)

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
    verified = [r for pos, r in enumerate(qua_t1) if (v := tier2.get(pos)) is not None and v.supported]
    ty_le = len(verified) / len(tier1)
    if not verified or ty_le < float(state.get("abstain_threshold", ABSTAIN_THRESHOLD_DEFAULT)):
        return _ngo_cut(state, llm, model, ResultType.abstain)

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
    for r in verified:
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
        })
        if eff and eff.verdict in CANH_BAO_NHAN:
            # `ly_do` NGUYÊN VĂN, không viết lại: nó nêu đích danh văn bản thay
            # thế (vd. "bị 38/2022/NĐ-CP thay thế từ ..."), một nhãn chung
            # chung như "đã bị thay thế" không mang thông tin đó.
            # Nhãn ĐỌC ĐƯỢC, không phải khoá dữ liệu: `so_ky_hieu` thật thì đi
            # qua nguyên vẹn, còn 'Không số' rơi về tên văn bản (`hien_van_ban`).
            # `citations[].so_ky_hieu` ngay trên thì GIỮ NGUYÊN giá trị DB — nó
            # là khoá, và `_neo_vao_van_ban` bên dưới so trên chính giá trị đó.
            so_hien, ten_hien = hien_van_ban(so_ky_hieu, p.get("ten") or "")
            msg = f"{so_hien or ten_hien} {CANH_BAO_NHAN[eff.verdict]}: {eff.ly_do}"
            if msg not in warnings:
                warnings.append(msg)

        if eff and eff.verdict in _VERDICT_BI_THAY and not _neo_vao_van_ban(state.get("query", ""), so_ky_hieu):
            nguon_bi_loc.append(so_ky_hieu)
        else:
            dung_cho_prose.append(r)
            citations_dung_cho_prose.append(citations[-1])

    # Toàn bộ nguồn dùng-được-cho-prose đã bị lọc (mọi citation đều bi_thay_the/
    # het_hieu_luc và câu hỏi không neo văn bản nào) → KHÔNG dựng câu trả lời
    # tự tin. LLM HÀNH VĂN không được gọi ở đây: đã biết trước không có gì hợp
    # lệ để hành văn. (Câu hỏi lại trong `_ngo_cut` là một lượt gọi KHÁC, với
    # schema khác, và nó không dựng khẳng định pháp luật nào.)
    if not dung_cho_prose:
        ket = _ngo_cut(state, llm, model, ResultType.abstain,
                       ghi_chu=_ly_do_moi_nguon_bi_thay(verified))
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
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
    for so, c in enumerate(citations_dung_cho_prose, start=1):
        c["k"] = so
    documents = _dung_documents(citations_dung_cho_prose, db_provisions)

    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    # Template có `{van_ban}` là template biết thẻ (v2): căn cứ đánh số [K] để
    # mô hình đặt `cite:K`. Template v1 giữ NGUYÊN định dạng cũ — A/B v1-v2
    # phải đo đúng prompt cũ, không phải một v1 đã bị đổi ruột.
    if "{van_ban}" in mau:
        claims_txt = "\n".join(
            f"[{c['k']}] {c['duong_dan']} — {c['bo_luat']}\n    {r.claim.text}"
            for r, c in zip(dung_cho_prose, citations_dung_cho_prose, strict=True)
        )
    else:
        claims_txt = "\n".join(
            f"- {r.claim.text}\n  (căn cứ: {c['duong_dan']} — {c['bo_luat']})"
            for r, c in zip(dung_cho_prose, citations_dung_cho_prose, strict=True)
        )
    prompt = mau.format(
        cau_hoi=state.get("query", ""),
        # `lich_su or tom_tat`: cùng định nghĩa "phiên đã có ngữ cảnh" mà
        # `graph_tra_cuu._vao_giai_nghia` đang dùng. Chỉ xét `lich_su` thì một
        # phiên vừa bị rút gọn lịch sử về rỗng sẽ bị chào lại như người lạ.
        mo_dau=MO_DAU_NOI_TIEP if (state.get("lich_su") or state.get("tom_tat")) else MO_DAU_LUOT_DAU,
        van_ban=_khoi_van_ban(citations_dung_cho_prose, db_provisions),
        claims=claims_txt,
        tinh_huong=khoi_tinh_huong(state.get("ho_so") or {}),
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
    duoi = duoi_hoi_them(state.get("ho_so") or {}, (state.get("traces") or {}).get("suy_dien_chu_the"))
    if duoi:
        ket["coverage_note"] = "\n\n".join(x for x in (ket.get("coverage_note"), duoi) if x)
    # Ý định PHỤ (router v3, spec 2026-09-09 §7.4): câu hỏi vừa hỏi luật vừa
    # nhờ soạn — KHÔNG hijack `answer` (nó vẫn là câu trả lời tra cứu bình
    # thường), chỉ đính kèm gợi ý soạn thảo, cùng hàm dựng đã dùng cho nhánh
    # `huong_dan_soan_thao`. Bỏ `answer` thứ hai mà `_goi_y_soan_thao` trả về:
    # đây không phải một câu trả lời KHÔNG có căn cứ như nhánh soạn thảo riêng.
    if state.get("y_dinh_phu") == "soan_thao":
        goi_y, _ = _goi_y_soan_thao(state.get("soan_thao_goi_y"))
        ket["soan_thao_goi_y"] = goi_y
    return ket
