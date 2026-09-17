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

**`muc_kiem="tong_quat"`, và nói ra.** Bản thảo này chưa qua checklist, chưa
qua rule, chưa qua audit. `audit_report` mang `dat=None`/`completeness=None`
chứ KHÔNG mang `dat=True`: một dấu tích xanh ở đây là lời hứa chưa ai kiểm
(cùng lý lẽ `soat.trangThaiSoat` ở giao diện).
"""

import logging

from src.services import ban_thao
from src.services.ban_thao import LOAI_TONG_QUAT

logger = logging.getLogger(__name__)

# `LOAI_TONG_QUAT` (nhập lại từ `ban_thao` — cột `loai` là của bảng đó) KHÔNG
# phải một mã checklist, nên mọi nơi tra checklist theo `loai` phải có nhánh
# cho nó: `ban_thao._render_markdown`, `ban_thao.dung_lai`, `GET /mau/{loai}`.
MUC_KIEM = "tong_quat"
TEN_TONG_QUAT = "Bản thảo tổng quát"
# Nhãn mức kiểm, hiện trên MỌI bề mặt của bản thảo này (CONTEXT.md "mức kiểm").
NHAN_MUC_KIEM = "Bản thảo tổng quát — chưa kiểm pháp lý"

KHONG_SOAN_DUOC = "Lượt này tôi chưa soạn được mục nào từ tài liệu. Bạn nói rõ cần văn bản gì và gồm mục nào."
KHONG_CO_BAN_THAO = "Cuộc trò chuyện này chưa có bản thảo tổng quát nào để sửa. Bạn nói rõ cần soạn văn bản gì."


def clauses_tu(van_ban: dict) -> list[dict]:
    """`{tieu_de, muc:[{ten, noi_dung, bang}]}` → `clauses` đúng hình dạng
    `BanThaoOut`.

    `key` đánh theo VỊ TRÍ (`muc_1`, `muc_2`) chứ không theo tên mục: tên do mô
    hình đặt, có dấu, dài, và đổi giữa hai phiên bản của cùng một bản thảo —
    dùng nó làm khoá là để `doi_muc` báo "đã đổi" cho một mục chỉ sửa chính tả
    tiêu đề. Vị trí là thứ ổn định duy nhất ở đây.

    `bang` (Phase 7 R1) dùng `.get`, không chỉ số: `van_ban["muc"]` đã qua
    `lam_sach_van_ban` nên LUÔN có khoá này, nhưng fixture cũ và test có sẵn
    (viết tay, trước bản vá này) thì không — `.get(...) or []` giữ MỘT hình
    dạng clause cho cả hai, không migration nào cần cho `clauses` (JSONB).
    """
    return [
        {"key": f"muc_{i}", "ten": m["ten"], "noi_dung": m["noi_dung"], "bang": m.get("bang") or []}
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
    return {
        "document": ban_thao._render_markdown(LOAI_TONG_QUAT, clauses, (van_ban or {}).get("tieu_de")),
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
    `facts` nào, nội dung của nó nằm thẳng ở `clauses`.
    """
    truoc = {c.get("key"): c.get("noi_dung") for c in (cu or [])}
    return [c["ten"] for c in (moi or []) if truoc.get(c["key"]) != c["noi_dung"]]


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

    Khác các node "thuần" của thư mục này, node này CHẠM DB — nhưng chỉ qua
    `ban_thao`, tức đúng biên dữ liệu của bảng đó, cùng cách `graph_tra_cuu.
    n_dung_ban_thao` làm cho đường checklist. Đổi lại, `graph_tra_cuu` chỉ phải
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
    if state.get("muc_dich_tai_lieu") == "sua_ban_thao":
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

    bt = ban_thao.tao(sub, str(hoi_thoai_id), LOAI_TONG_QUAT, {}, ket)
    return {**state, "ban_thao_ket": _ket_state(bt, ten, []), "ban_thao_tong_quat_loi": None}
