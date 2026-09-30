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
import re
import time
import unicodedata
import uuid
from pathlib import Path

from fastapi import HTTPException

from src.agents import graph_soan_thao as gst
from src.config import as_of_hieu_luc, get_settings
from src.services import ban_thao, bao_ve, khuon_mau
from src.services import tai_lieu as tl
from src.services.ban_thao import LOAI_TONG_QUAT
from src.services.db import get_engine
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
# Lượt sửa trên khuôn gốc đã XIN đổi mà mọi phép bị phép kiểm bỏ: không lên một
# phiên bản giống hệt (mỗi phiên bản tốn một lần của `TRAN_SUA`), và nói LOẠI lỗi
# — không bao giờ giá trị. Lượt không xin đổi gì (người dùng chỉ xin lại chính tệp:
# "soạn thảo văn bản này" lần hai, hay sau "Điền biểu mẫu") không tới đây: nó trả
# CHÍNH bản đang có (`khuon_tong_quat.co_san`, lời đáp ở `assemble`), không đòi giá
# trị (owner 2026-09-27 bác đúng loại lời đó). `tao_lai` không bao giờ tới đây: node
# đọc đã bỏ mọi phép của nó, nên tạo mới là phiên bản 1 đúng tệp tải lên; trên bản đã
# có thì bản đúng tệp là bản có sẵn, bản đã điền lên một phiên bản phép rỗng.
KHONG_DOI_KHUON = (
    "Lượt này tôi chưa áp được thay đổi nào bạn xin ({ly_do}), nên bản thảo trên tệp bạn tải lên giữ nguyên: "
    "mở bản thảo để xem, {tai}. Muốn điền, hãy nói giá trị cần điền hoặc bấm vào chỗ trống trên trang."
)
_LY_DO_BO = {
    # Luật owner 2026-09-27: chữ in sẵn của tài liệu không phải nguồn điền.
    "khong_nguon": "giá trị không có trong lời bạn nói hay hồ sơ",
    "bo_nho": "giá trị lấy từ điều tôi nhớ mà lượt này bạn không nhắc tới",
    "khong_khop_nhan": "giá trị không hợp với nhãn của chỗ trống",
    "dieu_luat": "thêm số Điều, Khoản chưa được kiểm pháp lý",
    "vung_trong": "giá trị chỉ là dãy chấm",
    "da_viet_lai": "chỗ trống đó thuộc dòng đã được viết lại hay đã xoá ở phiên bản trước",
}
_LY_DO_KHAC = "chỗ cần sửa không có trên tệp, sai chỗ hoặc sai dạng"


def khong_doi_khuon(khuon: dict) -> str:
    """`KHONG_DOI_KHUON` với các LOẠI lỗi của `bo_qua` (mã → câu, không giá trị)."""
    ly_do = dict.fromkeys(_LY_DO_BO.get(b.get("ly_do"), _LY_DO_KHAC) for b in khuon.get("bo_qua") or [])
    tai = "tải PDF" if khuon.get("dinh_dang") == "pdf" else "tải Word hoặc PDF"
    return KHONG_DOI_KHUON.format(ly_do="; ".join(ly_do), tai=tai)


# Owner 2026-09-28 ("không bao giờ nói đã điền khi chưa điền"): lượt trên khuôn gốc mà
# ai đó tưởng là lượt điền — mô hình, router hay một phép đề xuất — nhưng không áp gì
# (`hieu_tai_lieu._quyet_khuon`) đáp CÂU NÀY thay cho lời của mô hình ("Tôi đã điền … ⟦0⟧"
# đo được trong hội thoại a99dfda8…). Không bản thảo nào đổi ở lượt đó.
CHUA_DIEN_KHUON = (
    "Lượt này tôi chưa điền gì vào «{ten}»: {ly_do}. {khong_dat}"
    "Hãy nói rõ giá trị cần điền, hoặc bấm vào chỗ trống trên trang."
)


def chua_dien_khuon(ten_tep: str, bo: list[dict], co_phep: bool, co_de_xuat: bool, khong_dat: list[str]) -> str:
    """`CHUA_DIEN_KHUON` với lý do bằng lời thường: phép qua kiểm mà lượt không phải lời
    xin điền, các LOẠI lỗi của phép bị bỏ (không giá trị), phép trùng bản đang có, hay
    không có phép nào; cộng giá trị người hỏi đưa mà chưa đặt được (chuỗi con lời họ)."""
    if co_phep:
        ly_do = "tôi đọc câu của bạn là một câu hỏi, không phải lời xin điền hay sửa"
    elif bo:
        ly_do = "; ".join(dict.fromkeys(_LY_DO_BO.get(b.get("ly_do"), _LY_DO_KHAC) for b in bo))
    elif co_de_xuat:
        ly_do = "những giá trị đó đã có sẵn trong bản thảo"
    else:
        ly_do = "tôi chưa thấy giá trị nào trong câu của bạn để đặt vào chỗ trống"
    ke = ", ".join(f"«{v}»" for v in khong_dat[:4]) + (
        f" và {len(khong_dat) - 4} giá trị khác" if len(khong_dat) > 4 else ""
    )
    return CHUA_DIEN_KHUON.format(ten=ten_tep, ly_do=ly_do, khong_dat=f"Chưa đặt được: {ke}. " if ke else "")


# Lượt xin một văn bản KHÁC dựa trên tệp tải lên (`yeu_cau="van_ban_khac"`): văn
# bản khác là việc của đường checklist (quyết định 2026-09-26 mục 3), nên không
# dựng gì và chỉ sang đó. Không đòi giá trị điền: người hỏi không xin điền tệp này.
KHONG_DIEN_KHUON = (
    "Bạn đang xin một văn bản khác dựa trên tệp bạn tải lên, nên tôi không dựng bản thảo trên "
    "chính tệp đó. Để soạn văn bản mới (ví dụ một lá đơn), bạn vào Soạn thảo và chọn loại văn bản. "
    'Nếu bạn cần chính tệp đó, cứ nói "soạn thảo văn bản này".'
)


# Khuôn mẫu đang mở + lượt mang ẢNH (hay tệp trước 036) xin điền/sửa (thiết kế §4):
# giá trị trong ảnh không phải nguồn điền (Open decision 8, như `_nguon_nguoi`), và
# đường HTML không bao giờ ghi lên khuôn mẫu. Không lưu gì, không tốn hạn mức.
KHONG_DIEN_TU_ANH = (
    "Bản thảo «{ten}» là tệp Word; giá trị trong ảnh chưa được điền thẳng vào đó. Hãy gõ giá trị trong chat "
    "(ví dụ «họ tên bên B là …») hoặc bấm vào chỗ trống trên trang để điền."
)


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
            # Lề trang nguồn (`w:pgMar`, 2026-09-18) — sự thật của cả TÀI LIỆU
            # chứ không của mục này, chép lên mọi mục vì `clauses` là kênh duy
            # nhất ra giao diện; `mucTuBanThao` đọc lại ở mục đầu. `.get`, cùng
            # luật ba khoá trên: một `muc` viết tay (test, fixture) không có nó.
            "le_trang": m.get("le_trang") or [],
            # Trang nguồn và ảnh nguồn (`lam_sach_van_ban`), `xuat-tep.ts` đọc
            # lại `c.trang`/`c.anh`. Từng bị rơi ở đây nên mọi bản thảo hiện
            # trên MỘT tờ và mất ảnh. Chỉ CÓ MẶT khi mục mang chúng — cùng luật
            # phía đọc: vắng `trang` là trang 1, vắng `anh` là không ảnh.
            **({"trang": m["trang"]} if m.get("trang") else {}),
            **({"anh": m["anh"]} if m.get("anh") else {}),
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


def _nhan_cho(khuon: dict) -> dict[tuple, str]:
    return {(c["don_vi"], c["so"]): c["nhan"] for c in khuon.get("cho_trong") or []}


def ket_ban_thao_khuon(khuon: dict, phep_sua: list[dict]) -> dict:
    """Bản thảo trên KHUÔN GỐC (P4b) — cùng bộ khoá `ket_ban_thao` cộng `viec_id`
    và `phep_sua` (TRỌN danh sách của phiên bản mới, đã gộp và khử trùng).

    `clauses` rỗng: văn bản là chính tệp người hỏi tải lên cộng các phép sửa,
    không có mục nào do KLAW dựng. `document` chỉ tóm tắt những gì đã điền (tiêu
    đề + mỗi chỗ trống đã điền một dòng "nhãn: giá trị") — nó là thứ lượt sửa
    sau thấy trong "# Bản thảo đang có", và là Markdown cho mọi nơi đọc cũ.
    """
    nhan = _nhan_cho(khuon)
    # Nhãn của biểu mẫu thường đã kết bằng dấu hai chấm ("Fax:") — không nhân đôi.
    dong = [
        f"- {(nhan.get((p['don_vi'], p['cho_trong'])) or 'Chỗ trống').rstrip(': ')}: {p['gia_tri'].strip()}"
        for p in phep_sua
        if p.get("loai") == "dien"
    ]
    tieu_de = Path(khuon.get("ten_tep") or "").stem or "Biểu mẫu"
    return {
        "document": f"# {tieu_de}\n" + ("\n" + "\n".join(dong) + "\n" if dong else ""),
        "clauses": [],
        "audit_report": {
            "dat": None,
            "completeness": None,
            "so_dieu_khoan": 0,
            "self_audit": False,
            "findings": [],
            "muc_kiem": MUC_KIEM,
        },
        "viec_id": khuon["viec_id"],
        "phep_sua": phep_sua,
    }


def doi_cho_dien(cu: list[dict], moi: list[dict], khuon: dict) -> list[str]:
    """Nhãn các chỗ trống đổi giá trị so với phiên bản trước, theo thứ tự đọc —
    `doi_muc` của bản thảo khuôn gốc (không có mục nào để so)."""

    def _gia_tri(ds: list[dict]) -> dict[tuple, str]:
        return {(p["don_vi"], p["cho_trong"]): p["gia_tri"] for p in ds if p.get("loai") == "dien"}

    truoc, sau, nhan = _gia_tri(cu), _gia_tri(moi), _nhan_cho(khuon)
    return list(
        dict.fromkeys(
            nhan.get(k) or "Chỗ trống" for k in sorted(truoc.keys() | sau.keys()) if truoc.get(k) != sau.get(k)
        )
    )


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

    `viec_id`/`phep_sua` lấy từ DÒNG đã lưu, không từ `ket`: `ban_thao` ghi
    `viec_id` qua truy vấn con kiểm chủ, một id lạ ra NULL (bản thảo HTML).
    `khuon` (khuôn gốc + chỗ trống kèm giá trị) do service tính từ dòng —
    `assemble` chuyển nguyên sang `BanThaoOut.khuon`; `None` cho bản thảo HTML.
    `ten` qua `ban_thao.ten_ban_thao`, cùng luật `routes_ban_thao` (tên tệp tải lên
    cho bản khuôn gốc), nên thẻ chat và lần tải lại gọi bản thảo cùng một tên.
    """
    return {
        "viec_id": bt.get("viec_id"),
        "phep_sua": bt.get("phep_sua"),
        "khuon": bt.get("khuon"),
        "id": bt["id"],
        "loai": LOAI_TONG_QUAT,
        "ten": ban_thao.ten_ban_thao(bt, ten),
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
    khuon = state.get("khuon_tong_quat")
    sub, hoi_thoai_id = state.get("user_sub"), state.get("hoi_thoai_id")
    if sub is None or hoi_thoai_id is None:
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": None}
    if state.get("khuon_mau_tong_quat"):
        return dung_khuon_mau(state, sub, str(hoi_thoai_id))
    mo = state.get("khuon_mau_dang_mo")
    if mo and not khuon and _xin_dien_sua(state.get("cau_hoi_goc") or state.get("query") or ""):
        ten = ((mo.get("audit") or {}).get("khung") or {}).get("tieu_de") or "đang mở"
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_DIEN_TU_ANH.format(ten=ten)}
    ket = None if khuon else ket_ban_thao(state.get("van_ban_tong_quat") or {})
    if khuon and khuon.get("yeu_cau") == "van_ban_khac":
        # Văn bản KHÁC tệp tải lên: không dựng, không sửa bản đang có, không chạm
        # hạn mức — trước cả phép kiểm hạn mức, vì lượt này không lưu gì.
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_DIEN_KHUON}
    la_sua = state.get("muc_dich_tai_lieu") == "sua_ban_thao"
    tao_lai = bool(khuon) and khuon.get("yeu_cau") == "tao_lai"
    cu = None
    if khuon:
        # Sửa hay dựng mới quyết định bằng DỮ LIỆU, không bằng nhãn của mô hình:
        # hội thoại đã có bản thảo mà phiên bản đang sống nằm trên ĐÚNG khuôn gốc
        # này thì lượt này là một phiên bản mới của nó (mô hình gán `tao_van_ban`
        # cho một lời xin sửa sẽ không mở bản thứ hai chỉ mang phần thay đổi), kể
        # cả khi một bản HTML hay bản trên khuôn khác mới hơn. Không có thì dựng
        # bản MỚI, chịu hạn mức dựng lần đầu.
        cu = ban_thao.moi_nhat_cua_hoi_thoai(sub, str(hoi_thoai_id), LOAI_TONG_QUAT, viec_id=khuon["viec_id"])
        la_sua = cu is not None
        if khuon.get("xin_dien_rong") and not la_sua:
            # Lời xin điền mà không phép nào qua kiểm (G7): không dựng phiên bản 1 nào,
            # không hạn mức; nói thật. Giá trị chưa đặt được do `assemble` kể tiếp.
            loi = chua_dien_khuon(khuon.get("ten_tep") or "", khuon.get("bo_qua") or [], False, False, [])
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": loi}
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
    if khuon:
        # Lượt sửa mang THAY ĐỔI; phiên bản mới là phép đang có gộp với chúng, và
        # không đổi gì thì không lên một phiên bản giống hệt. Lượt TẠO luôn dựng
        # phiên bản 1 (owner 2026-09-27), kể cả phép rỗng: bản thảo là chính tệp
        # tải lên, tải về ngay được, điền tiếp ở lượt sau hay ở khung điền.
        cu_phep = ((cu or {}).get("phep_sua") or []) if la_sua else []
        # `thay` theo đoạn chỉ gỡ ô của chính đoạn đó: `cho_trong` của lượt mang `doan`.
        doan = {(c["don_vi"], c["so"]): c["doan"] for c in khuon.get("cho_trong") or [] if "doan" in c}
        # `tao_lai` ("bảo soạn thảo văn bản ra thì phải đúng 100%", owner 2026-09-27):
        # bản thảo của lượt là ĐÚNG tệp tải lên, kể cả trên bản đã điền — không gộp.
        # Bản đã đúng tệp là lượt không đổi gì (`co_san` bên dưới); bản đã điền lên
        # một phiên bản phép rỗng, giá trị cũ còn ở phiên bản trước (Lùi).
        gop = [] if tao_lai else ban_thao.gop_phep_sua(cu_phep, khuon["phep_sua"], doan)
        # `dien` vào đơn vị/đoạn đã bị `thay`/`xoa` bị gộp gỡ đi: đó là một giá trị
        # người hỏi vừa nói, nên nó vào `bo_qua` (mã, không giá trị) chứ không mất lặng.
        con = {(p["don_vi"], p["cho_trong"]) for p in gop if p["loai"] == "dien"}
        if nuot := [
            {"don_vi": p["don_vi"], "cho_trong": p["cho_trong"], "ly_do": "da_viet_lai"}
            for p in khuon["phep_sua"]
            if p["loai"] == "dien" and p["gia_tri"].strip() and (p["don_vi"], p["cho_trong"]) not in con
        ]:
            khuon = {**khuon, "bo_qua": [*(khuon.get("bo_qua") or []), *nuot]}
            state = {**state, "khuon_tong_quat": khuon}
        ket = ket_ban_thao_khuon(khuon, gop)
        if la_sua and ket["phep_sua"] == cu_phep:
            if khuon.get("bo_qua"):
                return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": khong_doi_khuon(khuon)}
            # Không xin đổi gì: CHÍNH bản đang có là bản thảo của lượt — chat hiện
            # thẻ của nó; không phiên bản mới, không hạn mức, không traces.
            return {
                **state,
                "khuon_tong_quat": {**khuon, "co_san": True},
                "ban_thao_ket": _ket_state(cu, TEN_TONG_QUAT, []),
                "ban_thao_tong_quat_loi": None,
            }
    if ket is None:
        return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_SOAN_DUOC}

    # `ten` trả lời "bản thảo này THUỘC LOẠI gì" (BanThaoOut.ten) — CỐ ĐỊNH cho
    # bản HTML, không phải tiêu đề riêng của văn bản: gán `tieu_de` vào đây làm
    # `ten` đổi giá trị giữa lượt vừa soạn (SSE) và lần tải lại trang sau đó —
    # đúng kiểu lẫn lộn Phase 7 R4 cấm. Tiêu đề riêng đi qua `document` (dòng H1
    # đầu). Bản trên khuôn gốc mang tên tệp tải lên (owner 2026-09-28), qua CÙNG
    # `ban_thao.ten_ban_thao` ở `_ket_state` và ở mọi route tải lại.
    ten = TEN_TONG_QUAT
    if la_sua:
        # Bản HTML (`viec_id=None`): một bản khuôn gốc mới hơn không hút lượt sửa này.
        cu = cu or ban_thao.moi_nhat_cua_hoi_thoai(sub, str(hoi_thoai_id), LOAI_TONG_QUAT, viec_id=None)
        if cu is None:
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_CO_BAN_THAO}
        # `tao_lai` không sửa gì bằng mô hình (như lưu ô điền, B6): không tính `TRAN_SUA`
        # và không bị trần chặn — bản đầy trần vẫn trở về được đúng tệp tải lên.
        if not tao_lai:
            try:
                ban_thao.kiem_tran_sua(cu)
            except ValueError as e:
                return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": str(e)}
        bt = ban_thao.sua(sub, cu["id"], {}, ket, tang=0 if tao_lai else 1)
        if bt is None:
            # Bị xoá giữa chừng (đua với một lượt xoá khác) — cùng hợp đồng
            # "không tìm thấy" của cả service, không spread `None`.
            return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": KHONG_CO_BAN_THAO}
        doi = (
            doi_cho_dien(cu.get("phep_sua") or [], ket["phep_sua"], khuon)
            if khuon
            else doi_muc(cu["clauses"], ket["clauses"])
        )
        return {**state, "ban_thao_ket": _ket_state(bt, ten, doi), "ban_thao_tong_quat_loi": None}

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


# ═══ Khuôn mẫu — tạo và sửa một tệp .docx (thiết kế `khuon-mau-thiet-ke.md` §4 bước 5) ═══


def _xin_dien_sua(cau: str) -> bool:
    # Nhập trễ: `hieu_tai_lieu` nhập module này ở đầu tệp.
    from src.agents.nodes.hieu_tai_lieu import xin_dien_sua

    return xin_dien_sua(cau)


def _loi(state: dict, loi: str) -> dict:
    return {**state, "ban_thao_ket": None, "ban_thao_tong_quat_loi": loi}


def _clauses(dieu: list[dict], ng: dict, cu: list[dict] | None = None) -> list[dict]:
    """Điều đã làm sạch → `clauses` của phiên bản khuôn mẫu, căn cứ từng điều theo mục
    checklist (`khuon_mau_ngu_canh.muc`); một điều giữ khoá của bản cũ giữ căn cứ của nó."""
    theo_muc = {m["key"]: m.get("can_cu") for m in ng.get("muc") or []}
    theo_cu = {c.get("key"): c.get("can_cu") for c in cu or [] if c.get("key")}
    return [
        {
            "key": d.get("key"),
            "ten": d.get("ten") or "",
            "doan": list(d.get("doan") or []),
            "can_cu": theo_muc.get(d.get("key")) or theo_cu.get(d.get("key")) if d.get("key") else None,
            **({"chen": d["chen"]} if d.get("chen") else {}),
        }
        for d in dieu
    ]


def _ap_sua_dieu(cu: list[dict], ops: list[dict], ng: dict) -> list[dict]:
    """Thao tác theo SỐ ĐIỀU HIỆN TẠI của bản cũ: `thay`, `xoa`, `them_sau` (0 là đầu).
    Điều không nhắc tới giữ NGUYÊN từng byte (§6)."""
    o = [[c] for c in cu]
    dau: list = []
    for op in ops:
        n = op["dieu"]
        if op["thao_tac"] == "xoa":
            o[n - 1][0] = None
            continue
        moi = _clauses([op], ng, cu)[0]
        if op["thao_tac"] == "thay":
            goc = cu[n - 1]
            moi = {**moi, "key": moi["key"] or goc.get("key"), "can_cu": moi["can_cu"] or goc.get("can_cu")}
            o[n - 1][0] = moi
        else:
            (dau if n == 0 else o[n - 1]).append(moi)
    return dau + [c for khe in o for c in khe if c is not None]


def _dieu_doi(cu: list[dict], moi: list[dict]) -> list[str]:
    """Tên các Điều đổi (theo số mới) và điều đã bỏ — `doi` của phiên bản."""
    truoc = [(c.get("key"), c.get("ten"), tuple(c.get("doan") or [])) for c in cu]
    ra = [
        f"Điều {i}. {c.get('ten') or ''}".strip()
        for i, c in enumerate(moi, 1)
        if (c.get("key"), c.get("ten"), tuple(c.get("doan") or [])) not in truoc
    ]
    con = {(c.get("key"), c.get("ten")) for c in moi}
    return ra + [f"Bỏ «{c.get('ten') or 'một điều'}»" for c in cu if (c.get("key"), c.get("ten")) not in con]


def _ben_doi(khung_cu: dict, khung: dict) -> dict[str, str]:
    """Bên tuỳ loại của khung registry đổi loại giữa hai phiên bản: `{khoa: "Bên thuê:
    tổ chức"}` — loại HIỆU LỰC qua `khuon_mau.chon_ben`, nên khung cũ không ghi loại là
    `mac_dinh`."""
    loai = khung.get("loai")
    if loai not in khuon_mau.cac_loai():
        return {}
    entry = khuon_mau.nap(loai)
    cu, moi = (
        {
            b["khoa"]: (b.get("vai") or b.get("tieu_de"), b.get("loai"))
            for b in khuon_mau.chon_ben(entry, k.get("ben"))["ben"]
        }
        for k in (khung_cu, khung)
    )
    return {
        k: f"{vai or k}: {'tổ chức' if lo == 'to_chuc' else 'cá nhân'}"
        for k, (vai, lo) in moi.items()
        if lo in khuon_mau.LOAI_BEN and cu.get(k, (None, None))[1] != lo
    }


def _kiem_gia_tri(
    state: dict, x: dict, o: list[dict], don_vi_goc: list, dang_co: list[dict]
) -> tuple[list, list, list]:
    """`gia_tri` của mô hình → phép `dien` lên đúng chỗ trống của tệp, qua CÙNG phép
    kiểm của khuôn gốc (`kiem_phep_sua`: chỉ lời người hỏi và hồ sơ, nhãn khớp, tách
    ngày). Trả `(giữ, bỏ, chưa đặt được)` — chưa đặt được là chuỗi con lời người hỏi."""
    from src.agents.nodes.hieu_tai_lieu import _lay_khong_dat, _loi_nguoi_hoi, kiem_phep_sua

    theo = {(g["ben"], g["truong"]): g["gia_tri"] for g in x.get("gia_tri") or []}
    phep = ban_thao.phep_tu_gia_tri(o, theo)
    loi = state.get("cau_hoi_goc") or state.get("query") or ""
    giu, bo, gia_tri_bo = kiem_phep_sua(
        phep,
        {"don_vi": don_vi_goc, "dinh_dang": "docx"},
        x.get("nguon_gia_tri") or "",
        x.get("cam") or [],
        dang_co,
        loi,
    )
    giu = _khong_doi_ben(giu, o, dang_co, (x.get("khung") or {}).get("ben") or [], loi)
    co_cho = {(z["ben"], z["truong"]) for z in o}
    khong_cho = [v for k, v in theo.items() if k not in co_cho]
    # Đã đặt là trên CẢ phiên bản: giá trị mang sang hay điền trên trang từ trước vẫn nằm
    # trên trang, dù lượt này không đặt lại nó (phép y hệt bị bỏ qua).
    khong_dat = _lay_khong_dat(
        [*gia_tri_bo, *khong_cho, *(x.get("khong_dat") or [])],
        _loi_nguoi_hoi(state),
        ban_thao.gop_phep_sua(dang_co, giu),
    )
    return giu, bo, khong_dat


# Định danh một bên: hai bên của cùng văn bản không bao giờ cùng một giá trị ở đây.
_DINH_DANH = ("ho_ten", "so_dinh_danh", "ten_to_chuc", "ma_so_doanh_nghiep")


def _goi_vai(vai: str | None) -> list[str]:
    """Cách người hỏi gọi một bên, đọc từ `vai` của khung (viết thường): "bên cho thuê";
    tiêu đề khối "1. BÊN A: NGƯỜI SỬ DỤNG LAO ĐỘNG" → "bên a", "người sử dụng lao động"."""
    s = re.sub(r"\([^)]*\)", " ", unicodedata.normalize("NFC", vai or "").casefold())
    s = re.sub(r"^\s*(?:[ivx]+|\d+)\.\s*", "", s)
    return [c for p in re.split(r"[:—]", s) if (c := " ".join(p.split()))]


def _neu_vai(loi: str, ben: str, goi: dict[str, list[str]]) -> bool:
    """Câu `loi` (viết thường) gọi vai của `ben`. Cụm của bên khác chứa cụm của bên này
    ("bên thuê vận chuyển" ⊃ "bên thuê") được xoá trước khi tìm."""
    cua = goi.get(ben) or []
    for k, ds in goi.items():
        for c in ds:
            if k != ben and any(x in c for x in cua):
                loi = loi.replace(c, " ")
    return any(re.search(rf"(?<!\w){re.escape(c)}(?!\w)", loi) for c in cua)


def _khong_doi_ben(giu: list[dict], o: list[dict], dang_co: list[dict], ben: list[dict], loi: str) -> list[dict]:
    """Lượt sửa không DỜI giá trị giữa các bên (app thật 2026-09-30, v3 của bản 91c288d5:
    "Sửa Điều 3: giá thuê …" mà mô hình chép lại tên hai bên đảo chỗ). Một giá trị bên
    khác đang giữ chỉ sang bên này khi CHÍNH câu gõ lượt này gọi vai bên này ("bên cho
    thuê là …") — nhắc tên một người không đủ; và hai bên không bao giờ cùng một định danh
    (`_DINH_DANH`). Phép bị bỏ lặng lẽ như cổng `loi_luot` của `kiem_phep_sua`: không
    phải điều lượt này xin. Chỉ các bên của khung; trường của cả văn bản không có vai.
    ponytail: vai gọi ở đâu trong câu cũng được, không buộc đi liền giá trị — buộc khi đo
    thấy mô hình đảo bên dù câu gọi đúng vai."""
    goi = {b["khoa"]: _goi_vai(b.get("vai")) for b in ben if isinstance(b, dict) and b.get("khoa")}
    cua = {(z["don_vi"], z["so"]): (z["ben"], z["truong"]) for z in o if z.get("ben") in goi}

    def _v(p: dict) -> str:
        return str(p.get("gia_tri") or "").strip().casefold()

    dang = {(p["don_vi"], p["cho_trong"]): v for p in dang_co if p.get("loai") == "dien" and (v := _v(p))}
    if not dang:
        return giu
    loi = unicodedata.normalize("NFC", loi).casefold()
    ra = []
    for p in giu:
        b, v = cua.get((p["don_vi"], p["cho_trong"])), _v(p)
        dang_giu = {cua[s][0] for s, x in dang.items() if x == v and s in cua}
        if not (b and v and dang_giu - {b[0]} and not _neu_vai(loi, b[0], goi)):
            ra.append(p)
    sau = {**dang, **{(p["don_vi"], p["cho_trong"]): _v(p) for p in ra}}
    cac_ben: dict[tuple, set] = {}
    for s, x in sau.items():
        if s in cua and x and cua[s][1] in _DINH_DANH:
            cac_ben.setdefault((cua[s][1], x), set()).add(cua[s][0])
    return [
        p for p in ra if not ((b := cua.get((p["don_vi"], p["cho_trong"]))) and len(cac_ben.get((b[1], _v(p)), ())) > 1)
    ]


def _moi_dien(giu: list[dict], truoc: list | None) -> int:
    """Số chỗ trống LƯỢT NÀY điền (hay đổi giá trị) từ lời người hỏi — giá trị mang sang
    hay điền trên trang từ trước không tính (owner: không nói đã điền khi chưa điền)."""
    cu = {(p.get("don_vi"), p.get("cho_trong"), str(p.get("gia_tri") or "").strip()) for p in truoc or []}
    return sum(1 for p in giu if (p["don_vi"], p["cho_trong"], str(p["gia_tri"]).strip()) not in cu)


def _audit(x: dict, khung: dict, clauses: list[dict], *, tao: bool) -> dict:
    """`audit` của phiên bản khuôn mẫu: mức kiểm `tong_quat` (chưa qua rule), mục
    luật đòi còn thiếu là PHÁT HIỆN lúc sửa (lúc tạo nó đã được chèn trống), và `khung`.
    Lúc sửa, thiếu và completeness tính lại trên CHÍNH điều khoản của phiên bản — cả
    loại checklist lẫn loại chỉ có `muc` trong mục registry, cả đường `sua_dieu`."""
    loai = khung.get("loai")
    hoan_thanh = x.get("hoan_thanh") or {}
    findings = []
    if loai and not tao:
        _, hoan_thanh = khuon_mau.them_dieu_bat_buoc(clauses, loai, tao=False)
    if hoan_thanh.get("thieu") and not tao:
        if loai in gst.cac_loai():
            cl = gst.load_checklist_cached(loai)
            muc, muc_do = cl.muc, cl.muc_do_thieu
        else:
            # Mục `bat_buoc` của registry là nội dung luật đòi phải có: cùng mức mặc định
            # của `Checklist.muc_do_thieu`.
            muc, muc_do = khuon_mau.nap(loai)["muc"], "chan"
        ten = {m["key"]: m["ten"] for m in muc}
        findings = [
            {
                "loai": "thieu_noi_dung",
                "muc_do": muc_do,
                "thong_diep": f"Thiếu nội dung bắt buộc: {ten.get(k, k)}",
                "dieu_khoan_lien_quan": None,
                "can_cu": None,
                "rule_id": None,
                "doc_id": None,
                "khop_tai_id": None,
                "khong_kiem_duoc": False,
            }
            for k in hoan_thanh["thieu"]
        ]
    return {
        "dat": None,
        "completeness": hoan_thanh.get("completeness"),
        "so_dieu_khoan": len(clauses),
        "self_audit": False,
        "findings": findings,
        "muc_kiem": MUC_KIEM,
        "khung": khung,
    }


def _ghi_trace_soan(sub: str, bat_dau: float) -> None:
    try:
        _ghi_traces(
            str(uuid.uuid4()),
            bao_ve.EP_SOAN_THAO,
            LOAI_TONG_QUAT,
            get_settings().eval_config_name,
            # Cùng lý do đường HTML: chi phí đã ghi ở dòng `/tra-cuu` của lượt; dòng này ĐẾM.
            {"result_type": "ban_thao", "traces": {}},
            int((time.monotonic() - bat_dau) * 1000),
            user_sub=sub,
        )
    except Exception:
        logger.exception("dung_ban_thao_tong_quat: không ghi được traces (khuôn mẫu)")


def dung_khuon_mau(state: dict, sub: str, hoi_thoai_id: str) -> dict:
    """Lượt soạn trên khuôn mẫu: tạo (`ban_moi`) hay sửa (`sua_ban_dang_co`) một tệp.

    Tạo: hạn mức `EP_SOAN_THAO` → dựng + lưu tệp (một lượt LibreOffice) → giá trị các
    bên thành phép `dien` đã kiểm → `ban_thao.tao` → dòng traces. Sửa: đọc lại bản đang
    có (`moi_nhat_khuon_mau`) dưới `TRAN_SUA`; điều khoản đổi thì DỰNG LẠI tệp mới và
    mang phép điền sang, chỉ giá trị đổi thì cùng tệp, không đổi gì thì bản đang có là
    thẻ của lượt. Tệp không dựng được hay quá trần trang: không lưu gì, không tốn hạn mức."""
    x = state["khuon_mau_tong_quat"]
    ng = state.get("khuon_mau_ngu_canh") or {}
    if x["muc_tieu"] == "sua_ban_dang_co":
        return _sua_khuon_mau(state, x, ng, sub, hoi_thoai_id)
    if not x.get("dieu"):
        return _loi(state, KHONG_SOAN_DUOC)
    try:
        bao_ve.kiem_han_muc(sub, bao_ve.plan_hieu_luc(sub), bao_ve.EP_SOAN_THAO)
    except HTTPException as e:
        return _loi(state, str(e.detail))
    bat_dau = time.monotonic()
    khung = {k: v for k, v in x["khung"].items() if k != "can_cu_so"}
    if khung.get("loai") is None:
        # Tự soạn: căn cứ mô hình nêu bằng số hiệu, tra qua CÙNG bộ lọc hiện/hiệu lực.
        khung["can_cu"] = gst.can_cu_theo_so_hieu(
            get_engine(), x["khung"].get("can_cu_so") or [], as_of_hieu_luc(state.get("as_of_date"))
        )
    clauses = _clauses(x["dieu"], ng)
    try:
        moi = ban_thao.dung_khuon_mau(sub, hoi_thoai_id, khung, clauses)
    except ban_thao.KhuonMauChuaDungError as e:
        return _loi(state, str(e))
    giu, bo, khong_dat = _kiem_gia_tri(state, x, moi["o"], moi["don_vi_goc"], [])
    phep = ban_thao.gop_phep_sua([], giu, ban_thao.doan_cua_cho(moi["don_vi"]))
    khung = {**khung, "o": moi["o"], "thuoc": moi["thuoc"]}
    khuon = {"cho_trong": ban_thao.cho_trong_khuon("docx", moi["don_vi"], phep, moi["o"])}
    ket = {
        "document": ban_thao.tom_tat_khuon_mau(khung, clauses, khuon),
        "clauses": clauses,
        "audit_report": _audit(x, khung, clauses, tao=True),
        "viec_id": moi["viec_id"],
        "phep_sua": phep,
    }
    bt = ban_thao.tao(sub, hoi_thoai_id, LOAI_TONG_QUAT, {}, ket)
    _ghi_trace_soan(sub, bat_dau)
    return {
        **state,
        "khuon_mau_tong_quat": {
            **x,
            "bo_qua": bo,
            "khong_dat": khong_dat,
            "so_trang": moi["so_trang"],
            "da_dien": _moi_dien(giu, []),
        },
        "ban_thao_ket": _ket_state(bt, TEN_TONG_QUAT, []),
        "ban_thao_tong_quat_loi": None,
    }


def _sua_khuon_mau(state: dict, x: dict, ng: dict, sub: str, hoi_thoai_id: str) -> dict:
    cu = ban_thao.moi_nhat_khuon_mau(sub, hoi_thoai_id)
    if cu is None:
        return _loi(state, KHONG_CO_BAN_THAO)
    try:
        ban_thao.kiem_tran_sua(cu)
    except ValueError as e:
        return _loi(state, str(e))
    khung_cu = (cu.get("audit") or {}).get("khung") or {}
    clauses_cu = list(cu.get("clauses") or [])
    if x.get("dieu") is not None:
        clauses = _clauses(x["dieu"], ng, clauses_cu)
    elif x.get("sua_dieu"):
        clauses = _ap_sua_dieu(clauses_cu, x["sua_dieu"], ng)
    else:
        clauses = clauses_cu
    khung = {k: khung_cu.get(k) for k in ("loai", "bo_cuc", "tieu_de", "trich_yeu", "ben", "can_cu")}
    khung["ben"] = (x.get("khung") or {}).get("ben") or khung["ben"]
    # Một bên tuỳ loại đổi cá nhân ↔ tổ chức: khối các bên và ô ký đổi, dựng lại tệp.
    ben_doi = _ben_doi(khung_cu, khung)
    doi = [*ben_doi.values(), *_dieu_doi(clauses_cu, clauses)]
    bo_mang: list = []
    if doi:
        try:
            moi = ban_thao.dung_khuon_mau(sub, hoi_thoai_id, khung, clauses)
        except ban_thao.KhuonMauChuaDungError as e:
            return _loi(state, str(e))
        mang, bo_mang = ban_thao.mang_phep_sang(
            ban_thao.don_vi_khuon(sub, cu.get("viec_id")),
            moi["don_vi"],
            cu.get("phep_sua"),
            khung_cu.get("thuoc"),
            moi["thuoc"],
        )
        # Giá trị cũ không sang khối của bên vừa đổi loại: họ tên một người không phải
        # tên người đại diện của công ty thay chỗ người ấy.
        cua_ben_doi = {(z["don_vi"], z["so"]) for z in moi["o"] if z["ben"] in ben_doi}
        bo_mang += [p for p in mang if (p["don_vi"], p["cho_trong"]) in cua_ben_doi]
        mang = [p for p in mang if (p["don_vi"], p["cho_trong"]) not in cua_ben_doi]
        giu, bo, khong_dat = _kiem_gia_tri(state, x, moi["o"], moi["don_vi_goc"], mang)
        da_dien = _moi_dien(giu, mang)
        phep = ban_thao.gop_phep_sua(mang, giu, ban_thao.doan_cua_cho(moi["don_vi"]))
        viec_id, o, thuoc, don_vi = moi["viec_id"], moi["o"], moi["thuoc"], moi["don_vi"]
    else:
        viec_id, o, thuoc = cu.get("viec_id"), khung_cu.get("o") or [], khung_cu.get("thuoc")
        don_vi = ban_thao.don_vi_khuon(sub, viec_id)
        don_vi_goc = tl.don_vi_cua(get_engine(), viec_id, sub) or []
        giu, bo, khong_dat = _kiem_gia_tri(state, x, o, don_vi_goc, cu.get("phep_sua") or [])
        da_dien = _moi_dien(giu, cu.get("phep_sua"))
        phep = ban_thao.gop_phep_sua(cu.get("phep_sua"), giu, ban_thao.doan_cua_cho(don_vi))
        if phep == (cu.get("phep_sua") or []):
            # Không đổi gì áp được: CHÍNH bản đang có là thẻ của lượt — không phiên bản
            # mới, không tốn lượt sửa. `assemble` nói điều chưa làm được.
            return {
                **state,
                "khuon_mau_tong_quat": {**x, "co_san": True, "bo_qua": bo, "khong_dat": khong_dat, "da_dien": 0},
                "ban_thao_ket": _ket_state(cu, TEN_TONG_QUAT, []),
                "ban_thao_tong_quat_loi": None,
            }
    khung = {**khung, "o": o, "thuoc": thuoc}
    khuon = {"cho_trong": ban_thao.cho_trong_khuon("docx", don_vi, phep, o)}
    ket = {
        "document": ban_thao.tom_tat_khuon_mau(khung, clauses, khuon),
        "clauses": clauses,
        "audit_report": _audit(x, khung, clauses, tao=False),
        "viec_id": viec_id,
        "phep_sua": phep,
    }
    nhan = {(z["don_vi"], z["so"]): z for z in khuon["cho_trong"]}
    doi_o = [
        f"{nhan[(p['don_vi'], p['cho_trong'])]['nhan'] or 'Chỗ trống'}: {p['gia_tri'].strip()}"
        for p in giu
        if (p["don_vi"], p["cho_trong"]) in nhan
    ]
    bt = ban_thao.sua(sub, cu["id"], {}, ket, doi=[*doi, *doi_o])
    if bt is None:
        return _loi(state, KHONG_CO_BAN_THAO)
    return {
        **state,
        "khuon_mau_tong_quat": {
            **x,
            "bo_qua": bo,
            "khong_dat": khong_dat,
            "khong_mang_sang": len(bo_mang),
            "da_dien": da_dien,
        },
        "ban_thao_ket": _ket_state(bt, TEN_TONG_QUAT, [*doi, *doi_o]),
        "ban_thao_tong_quat_loi": None,
    }
