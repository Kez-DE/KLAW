"""Node `dung_ban_thao_tong_quat` — biến văn bản `hieu_tai_lieu` vừa soạn thành
một bản thảo THẬT, lưu được, sửa được, tải về được (plan `tai-lieu-tong-quat.md`
§Bản thảo tổng quát S6, CONTEXT.md "bản thảo tổng quát", "mức kiểm").

Ba điều định hình file:

**0 token.** Lượt hành văn đã xảy ra ở `hieu_tai_lieu`, nơi duy nhất thấy chữ
của tài liệu — và nơi duy nhất mọi giá trị trong văn bản đã được tra ngược về
nguồn (`lam_sach_van_ban`). Ở đây chỉ còn đánh số mục, dựng Markdown và ghi
xuống bảng. Không mô hình nào được gọi lần thứ hai cho cùng một bản thảo.

**Đúng bảng cũ, đúng hàm cũ.** `ban_thao.tao`/`sua` là đường DUY NHẤT — nên
phiên bản, `phien_ban_truoc`, trần sửa và `lui` không có bản thứ hai để trôi
lệch. `loai="tong_quat"` chỉ là một giá trị mới của một cột đã có; không
migration nào ở lát cắt này.

**`muc_kiem="tong_quat"` — bản ghi nói thật.** Bản thảo này chưa qua checklist,
chưa qua rule, chưa qua audit. `audit_report` mang `dat=None`/`completeness=None`
chứ KHÔNG mang `dat=True`: một dấu tích xanh ở đây là lời hứa chưa ai kiểm.
Phase 14 (owner D14-A) bỏ NHÃN "chưa kiểm pháp lý" khỏi lời đáp và giao diện;
giá trị trong bản ghi giữ nguyên để hệ thống, trace và mọi lần soát sau còn
phân biệt được bản thảo đã kiểm với bản thảo chưa kiểm.
"""

import logging
import time
import uuid

from fastapi import HTTPException

from src.config import get_settings
from src.services import ban_thao, bao_ve
from src.services.ban_thao import LOAI_TONG_QUAT
from src.services.traces import _ghi_traces

logger = logging.getLogger(__name__)

# `LOAI_TONG_QUAT` (nhập lại từ `ban_thao` — cột `loai` là của bảng đó) KHÔNG
# phải một mã checklist, nên mọi nơi tra checklist theo `loai` phải có nhánh
# cho nó: `ban_thao._render_markdown`, `ban_thao.dung_lai`, `GET /mau/{loai}`.
MUC_KIEM = "tong_quat"
TEN_TONG_QUAT = "Bản thảo tổng quát"

# Không nói "từ tài liệu": từ Phase 14 lượt soạn có thể không có tài liệu nào.
KHONG_SOAN_DUOC = "Lượt này tôi chưa soạn được mục nào. Bạn nói rõ cần văn bản gì và gồm mục nào."
KHONG_CO_BAN_THAO = "Cuộc trò chuyện này chưa có bản thảo tổng quát nào để sửa. Bạn nói rõ cần soạn văn bản gì."


def _khoi_thanh_van_ban(khoi: list[dict]) -> str:
    """Khối (Phase 8 R1) → một đoạn Markdown thuần, chỉ để `document` (Markdown
    của bản thảo) có gì đó để hiện — `document` KHÔNG có nơi đọc nào, backend
    lẫn frontend (Phase 7 concern #4, vẫn đúng ở Phase 8): panel render từ
    `clauses` (D6), và hàm này chỉ giữ cho `ban_thao._render_markdown` không
    nổ `KeyError` trên một `clauses` không còn `noi_dung` cấp mục nữa.

    HAI điều kiện ĐỘC LẬP (review round 1 [IMPORTANT]), không `elif`: một khối
    lẽ ra chỉ có MỘT trong hai (`hieu_tai_lieu._khoi_sach` tách khối nào có cả
    hai từ Phase 8 fix round 1 trở đi), nhưng hàm này không được TIN điều đó —
    một khối vẫn có cả hai (hàng cũ, hoặc gọi trực tiếp ngoài đường đó) thì
    phải giữ cả hai, không được âm thầm bỏ một bên như `elif` từng làm."""
    phan = []
    for k in khoi:
        if k.get("noi_dung"):
            phan.append(k["noi_dung"])
        if k.get("bang"):
            phan.append("\n".join(" | ".join(hang) for hang in k["bang"]))
    return "\n\n".join(phan)


def clauses_tu(van_ban: dict) -> list[dict]:
    """`{tieu_de, muc:[{ten, vung, khoi}]}` → `clauses` đúng hình dạng
    `BanThaoOut`.

    `key` đánh theo VỊ TRÍ (`muc_1`, `muc_2`) chứ không theo tên mục: tên do mô
    hình đặt, có dấu, dài, và đổi giữa hai phiên bản của cùng một bản thảo —
    dùng nó làm khoá là để `doi_muc` báo "đã đổi" cho một mục chỉ sửa chính tả
    tiêu đề. Vị trí là thứ ổn định duy nhất ở đây.

    `khoi` (Phase 8 R1, thay `noi_dung`/`bang` cố định của Phase 7), `vung`
    (Phase 8 R2) và `ten_that` (Phase 9 U1) dùng `.get`, không chỉ số:
    `van_ban["muc"]` đã qua `lam_sach_van_ban` nên LUÔN có ba khoá này, nhưng
    một `muc` viết tay (test, fixture cũ) thì không — `.get(...) or …`/mặc
    định `True` giữ MỘT hình dạng clause cho cả ba, không migration nào cần
    cho `clauses` (JSONB). Hàng ĐÃ LƯU trước Phase 8/9 (chỉ `noi_dung`, hoặc
    `noi_dung`+`bang` kiểu Phase 7, không `ten_that`) không đi qua hàm này lần
    nữa — chúng giữ nguyên hình dạng cũ trong DB, và phía đọc
    (`frontend/src/lib/xuat-tep.ts::khoiTuClause`/`mucTuBanThao`) là nơi hiểu
    cả các hình dạng cũ, không phải ở đây. `ten_that` mặc định `True` (giữ
    tên) khi vắng mặt: một clause cũ không biết KLAW đặt tên đó hay tài liệu
    đặt tên đó thì hiện tên ra vẫn an toàn hơn ẩn oan một tiêu đề thật.
    """
    return [
        {
            "key": f"muc_{i}",
            "ten": m["ten"],
            "ten_that": m.get("ten_that", True),
            "vung": m.get("vung") or "than",
            "khoi": m.get("khoi") or [],
        }
        for i, m in enumerate((van_ban or {}).get("muc") or [], 1)
    ]


def ket_ban_thao(van_ban: dict) -> dict | None:
    """`{document, clauses, audit_report}` — đúng bộ khoá `ban_thao.tao`/`sua`
    đòi, cùng hình dạng `ban_thao.tu_state_soan_thao` trả cho đường checklist.

    `None` khi không còn mục nào: lưu một bản thảo RỖNG là để người dùng mở ra
    một trang trắng mang số phiên bản 1, rồi `lui` về nó sau này.
    """
    clauses = clauses_tu(van_ban)
    if not clauses:
        return None
    # `_render_markdown` (ban_thao.py) đọc `c["noi_dung"]` — hình dạng CŨ, và
    # đổi nó theo `clauses` mới sẽ chạm một file dùng chung cho cả đường
    # checklist (rủi ro không cần, xem `_khoi_thanh_van_ban`). Dựng một danh
    # sách hiển thị RIÊNG cho lệnh gọi này, không lưu, không đi đâu khác.
    hien_thi = [{"ten": c["ten"], "noi_dung": _khoi_thanh_van_ban(c["khoi"])} for c in clauses]
    return {
        "document": ban_thao._render_markdown(LOAI_TONG_QUAT, hien_thi, (van_ban or {}).get("tieu_de")),
        "clauses": clauses,
        # `dat`/`completeness` là None chứ không phải True/1.0: chưa rule nào
        # chạy trên bản thảo này. `findings` rỗng vì KHÔNG có phát hiện, không
        # phải vì đã soát xong — `muc_kiem` là chỗ nói ra điều đó.
        "audit_report": {
            "dat": None,
            "completeness": None,
            "so_dieu_khoan": len(clauses),
            "self_audit": False,
            "findings": [],
            "muc_kiem": MUC_KIEM,
        },
    }


def doi_muc(cu: list[dict], moi: list[dict]) -> list[str]:
    """Tên các mục đổi nội dung so với phiên bản trước — để lời đáp GỌI TÊN
    được cái vừa đổi.

    Không dùng `ban_thao.doi_so_voi` (so `facts`): bản thảo tổng quát không có
    `facts` nào, nội dung của nó nằm thẳng ở `clauses`. So `khoi` (Phase 8),
    không còn `noi_dung` cấp mục — so cả danh sách khối là so ĐÚNG nội dung
    mục đó có, kể cả khi chỉ thứ tự khối đổi.
    """
    truoc = {c.get("key"): c.get("khoi") for c in (cu or [])}
    return [c["ten"] for c in (moi or []) if truoc.get(c["key"]) != c.get("khoi")]


def _ket_state(bt: dict, ten: str, doi: list[str]) -> dict:
    """Một dòng `ban_thao` → `state["ban_thao_ket"]`. Song sinh với
    `graph_tra_cuu._ban_thao_ket` (đường checklist) và bị ghim bởi cùng một hợp
    đồng, `schemas.BanThaoOut` — cột DB tên `audit`, trường ra tên `audit_report`.
    """
    return {
        "id": bt["id"],
        "loai": LOAI_TONG_QUAT,
        "ten": ten,
        "phien_ban": bt["phien_ban"],
        "document": bt["document"],
        "clauses": bt["clauses"],
        "audit_report": bt["audit"],
        "facts": bt["facts"],
        "doi_so_voi_truoc": doi,
    }


def dung_ban_thao_tong_quat(state: dict) -> dict:
    """Lưu văn bản vừa soạn thành bản thảo mới, hoặc sửa bản thảo tổng quát gần
    nhất của hội thoại.

    Khác các node "thuần" của thư mục này, node này CHẠM DB — qua `ban_thao`
    (bảng bản thảo), `bao_ve` (hạn mức) và `traces` (hàng đo hạn mức đếm),
    tức đúng ba biên mà `graph_tra_cuu.n_dung_ban_thao` chạm cho đường
    checklist. Cùng ba, không phải một tập khác: hai đường soạn phải chịu
    cùng một cổng, nếu không đường rẻ hơn thành lối vòng qua cổng kia. Đổi lại, `graph_tra_cuu` chỉ phải
    thêm một wrapper ba dòng, và toàn bộ luật của bản thảo tổng quát nằm trong
    MỘT file đọc hết được.

    Khách chưa đăng nhập không bao giờ tới chỗ lưu: không `user_sub` thì hàm
    trả về ngay, và `assemble` dựng lời mời đăng nhập đúng hình dạng
    `soan_thao_hoi` đã có. (Tài liệu vốn đã đòi đăng nhập, nên đây là lớp thứ
    hai — chỗ để chặn khi lớp thứ nhất bị nới.)
    """
    ket = ket_ban_thao(state.get("van_ban_tong_quat") or {})
    sub, hoi_thoai_id = state.get("user_sub"), state.get("hoi_thoai_id")
    if sub is None or hoi_thoai_id is None:
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": None}
    la_sua = state.get("muc_dich_tai_lieu") == "sua_ban_thao"
    if not la_sua:
        # Hạn mức DỰNG LẦN ĐẦU — CÙNG giỏ `EP_SOAN_THAO` mà đường checklist
        # kiểm ở `graph_tra_cuu.n_dung_ban_thao`, không phải một giỏ thứ hai.
        # Từ Phase 14 đây là đường soạn MẶC ĐỊNH của chat, nên thiếu phép kiểm
        # này thì soạn thảo trong hội thoại không tính vào hạn mức nào cả: hàm
        # này không gọi `kiem_han_muc` và cũng không ghi dòng `traces` mà
        # `bao_ve.dem_luot` đếm, tức cổng vừa không đóng vừa không đo.
        # Lượt SỬA không kiểm ở đây (đúng như nhánh `la_sua` của
        # `n_dung_ban_thao`): trần của nó là `TRAN_SUA` trên chính bản thảo.
        #
        # Đo được và CHẤP NHẬN: lượt gọi mô hình đã xảy ra ở `hieu_tai_lieu`
        # TRƯỚC khi tới đây, nên người hết hạn mức vẫn tốn của hệ thống một
        # lượt rồi mới nhận lời từ chối. Chặn sớm hơn đòi một phép tra DB ngay
        # trong routing, mà `_re_sau_route` là hàm THUẦN — đổi lấy đúng chỗ
        # này, nơi MỌI lời lưu bản thảo tổng quát đi qua.
        try:
            bao_ve.kiem_han_muc(sub, bao_ve.plan_hieu_luc(sub), bao_ve.EP_SOAN_THAO)
        except HTTPException as e:
            # Hết hạn mức phải nói RA con số và lúc mở lại (`_cau_429`), không
            # rơi về `KHONG_SOAN_DUOC` — người dùng hết lượt mà đọc "hãy thử
            # lại" sẽ thử lại, tốn thêm một lượt mô hình cho cùng lời từ chối.
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": str(e.detail)}
    if ket is None:
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_SOAN_DUOC}

    # `ten` trả lời "bản thảo này THUỘC LOẠI gì" (BanThaoOut.ten) — CỐ ĐỊNH,
    # không phải tiêu đề riêng của văn bản. `routes_ban_thao._ten_loai` đã trả
    # cố định TEN_TONG_QUAT cho loai này ở mọi lần tải lại; gán `tieu_de` vào
    # đây làm `ten` đổi giá trị giữa lượt vừa soạn (SSE) và lần tải lại trang
    # sau đó — đúng kiểu lẫn lộn Phase 7 R4 cấm. Tiêu đề riêng đi qua
    # `document` (dòng H1 đầu, `_render_markdown` bên dưới), phía client tự
    # đọc ra từ đó.
    ten = TEN_TONG_QUAT
    if la_sua:
        cu = ban_thao.moi_nhat_cua_hoi_thoai(sub, str(hoi_thoai_id), LOAI_TONG_QUAT)
        if cu is None:
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_CO_BAN_THAO}
        try:
            ban_thao.kiem_tran_sua(cu)
        except ValueError as e:
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": str(e)}
        bt = ban_thao.sua(sub, cu["id"], {}, ket)
        if bt is None:
            # Bị xoá giữa chừng (đua với một lượt xoá khác) — cùng hợp đồng
            # "không tìm thấy" của cả service, không spread `None`.
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_CO_BAN_THAO}
        return {
            **state,
            "ban_thao_ket": _ket_state(bt, ten, doi_muc(cu["clauses"], ket["clauses"])),
            "ban_thao_tong_quat_loi": None,
        }

    bat_dau = time.monotonic()
    bt = ban_thao.tao(sub, str(hoi_thoai_id), LOAI_TONG_QUAT, {}, ket)
    try:
        _ghi_traces(
            str(uuid.uuid4()),
            bao_ve.EP_SOAN_THAO,
            LOAI_TONG_QUAT,
            get_settings().eval_config_name,
            # `traces` RỖNG CÓ CHỦ Ý: chi phí của lượt hành văn nằm ở
            # `hieu_tai_lieu` và đã được ghi trên dòng `/api/v1/tra-cuu` của
            # chính lượt này — chép lại vào đây là đếm đôi cùng một đồng. Dòng
            # này tồn tại để ĐẾM lượt cho hạn mức (`dem_luot` đếm SỐ DÒNG), y
            # như dòng `n_dung_ban_thao` ghi cho một bản thảo checklist.
            {"result_type": "ban_thao", "traces": {}},
            int((time.monotonic() - bat_dau) * 1000),
            user_sub=sub,
        )
    except Exception:
        # Best-effort như mọi nơi ghi trace khác: không chặn bản thảo đã lưu
        # thật chỉ vì hàng đo đếm không ghi được.
        logger.exception("dung_ban_thao_tong_quat: không ghi được traces")
    return {**state, "ban_thao_ket": _ket_state(bt, ten, []), "ban_thao_tong_quat_loi": None}
