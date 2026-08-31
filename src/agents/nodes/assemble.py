"""Node assemble — quyết định một trong BỐN loại kết quả (spec 6.2). Đây là nơi
mọi thứ hội tụ thành câu trả lời người dùng đọc, và là nơi lời hứa của khoá
luận (nguồn gốc + nguyên văn, KHÔNG bảo đảm là bản hiện hành) hiện ra hoặc bị
phản bội.

answer            : có claim qua cả hai tầng, tỉ lệ verified ≥ ngưỡng
partial_coverage  : chỉ trúng tầng nông → nêu luật, KHÔNG diễn giải. 0 TOKEN
abstain           : không đủ căn cứ. HÀNH VI ĐÚNG, không phải lỗi
out_of_scope      : route xác định ngoài phạm vi. 0 TOKEN

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

from src.agents.nodes.verify_tier1 import normalize, van_ban_neo_boi_ten
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/assemble.v1.md")

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


def _base(state: dict, rt: ResultType, usage: Usage | None = None, degraded: bool = False, **kw: object) -> dict:
    """Khung chung cho cả bốn loại kết quả — MỌI nhánh đều ghi `traces`
    (Global Constraint), kể cả ba nhánh 0 token: `assemble_token_*=0` không chỉ
    là giá trị mặc định, nó là BẰNG CHỨNG đo được cho tuyên bố "0 TOKEN" trong
    docstring module, không phải một lời khẳng định suông.
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
    chung "không đủ căn cứ"). Không có `ly_do` nào nêu được kế nhiệm (Mức 1
    hết hiệu lực không cạnh) thì nói rõ không xác định được, không bịa tên."""
    ke_nhiem = sorted({m for r in qua_loc for m in [_van_ban_ke_nhiem(r.effectivity.ly_do)] if m})
    if ke_nhiem:
        return (f"Mọi nguồn tìm được đều đã bị thay thế; văn bản hiện hành là "
                f"{', '.join(ke_nhiem)}, nội dung của nó không có trong corpus.")
    return ("Mọi nguồn tìm được đều đã bị thay thế hoặc hết hiệu lực; không xác định được "
            "văn bản hiện hành từ dữ liệu sẵn có.")


def assemble(state: dict, db_provisions: dict[int, dict], llm, model: str) -> dict:
    if state.get("intent") == "ngoai_pham_vi":
        return _base(
            state, ResultType.out_of_scope,
            coverage_note="Câu hỏi ngoài phạm vi hệ thống: 6 Bộ luật của Việt Nam; "
                          "soạn thảo chỉ trong lĩnh vực lao động.",
        )

    # Phép kiểm thứ sáu (coordinator, ở tầng ĐẦU VÀO — verify_tier1.tien_de_cau_hoi_sai,
    # chạy TRƯỚC rewrite/retrieve/generate trong graph). Câu hỏi tự nêu một
    # "Điều N [văn bản]" không có thật: KHÔNG được âm thầm trả lời một câu hỏi
    # khác rồi để tiền đề sai đứng nguyên — coverage_note nêu ĐÍCH DANH vấn đề
    # (vd. "Bộ luật Lao động không có Điều 999"), không phải một câu chung
    # chung "không đủ căn cứ".
    if state.get("tien_de_sai"):
        return _base(state, ResultType.abstain, coverage_note=state["tien_de_sai"])

    deep = state.get("expanded") or []
    shallow = state.get("hits_shallow") or []

    # PARTIAL_COVERAGE — nhánh xác định, KHÔNG gọi LLM: chỉ trúng tầng nông thì
    # nêu luật liên quan chứ không được diễn giải nội dung chưa được kiểm chứng.
    if not deep and shallow:
        luat = sorted({f"{p['so_ky_hieu']} ({p.get('ten') or ''})".strip() for p in shallow})
        dieu = ", ".join(p["duong_dan"] for p in shallow[:3])
        # Gộp theo doc_id: nhiều Điều của cùng một văn bản là MỘT nguồn. Không
        # có doc_id thì bỏ qua dòng đó — thà thiếu một link còn hơn dựng một
        # link hỏng, và giao diện đã có `coverage_note` nêu tên văn bản.
        nguon: list[dict] = []
        for p in shallow:
            doc_id = str(p.get("document_id") or "")
            if doc_id and not any(n["doc_id"] == doc_id for n in nguon):
                nguon.append({"doc_id": doc_id, "so_ky_hieu": p.get("so_ky_hieu", ""),
                              "bo_luat": p.get("ten") or ""})
        return _base(state, ResultType.partial_coverage, nguon=nguon, coverage_note=(
            f"Câu hỏi thuộc {'; '.join(luat)} — liên quan {dieu}. "
            "KLAW phủ sâu 6 Bộ luật và các văn bản hướng dẫn về lao động; "
            "chưa phủ nghị định/thông tư hướng dẫn lĩnh vực này nên không diễn giải chi tiết."
        ))

    if state.get("insufficient_evidence"):
        return _base(state, ResultType.abstain)

    tier1 = state.get("tier1") or []
    tier2 = {v.claim_index: v for v in (state.get("tier2") or [])}
    qua_t1 = [r for r in tier1 if r.ok]

    if not tier1 or not qua_t1:
        return _base(state, ResultType.abstain)

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
        return _base(state, ResultType.abstain)

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
        })
        if eff and eff.verdict in CANH_BAO_NHAN:
            # `ly_do` NGUYÊN VĂN, không viết lại: nó nêu đích danh văn bản thay
            # thế (vd. "bị 38/2022/NĐ-CP thay thế từ ..."), một nhãn chung
            # chung như "đã bị thay thế" không mang thông tin đó.
            msg = f"{so_ky_hieu} {CANH_BAO_NHAN[eff.verdict]}: {eff.ly_do}"
            if msg not in warnings:
                warnings.append(msg)

        if eff and eff.verdict in _VERDICT_BI_THAY and not _neo_vao_van_ban(state.get("query", ""), so_ky_hieu):
            nguon_bi_loc.append(so_ky_hieu)
        else:
            dung_cho_prose.append(r)
            citations_dung_cho_prose.append(citations[-1])

    # Toàn bộ nguồn dùng-được-cho-prose đã bị lọc (mọi citation đều bi_thay_the/
    # het_hieu_luc và câu hỏi không neo văn bản nào) → KHÔNG dựng câu trả lời
    # tự tin. 0 TOKEN: không gọi LLM khi đã biết trước không có gì hợp lệ để
    # hành văn.
    if not dung_cho_prose:
        ket = _base(state, ResultType.abstain, coverage_note=_ly_do_moi_nguon_bi_thay(verified))
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
        return ket

    claims_txt = "\n".join(f"- {r.claim.text}" for r in dung_cho_prose)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state.get("query", ""), claims=claims_txt)
    usage: Usage | None = None
    degraded = False
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=ANSWER_SCHEMA)
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
        ket = _base(state, ResultType.abstain, usage=usage, degraded=degraded)
        ket["traces"]["assemble_dieu_bi_loai"] = dieu_bi_loai
        ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
        return ket

    ket = _base(state, ResultType.answer, usage=usage, degraded=degraded,
                answer=answer, citations=citations, warnings=warnings)
    ket["traces"]["assemble_dieu_bi_loai"] = []
    ket["traces"]["assemble_nguon_bi_loc_khoi_prose"] = nguon_bi_loc
    return ket
