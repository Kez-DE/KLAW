"""Graph tra cứu (spec mục 6) — nối các node đã build thành một đồ thị chạy được.

[giai_nghia] → suy_dien → route → tien_de → rewrite_query → retrieve_hybrid
             → expand → generate_claims → verify_tier1 → verify_tier2 → assemble
                      ↘ hieu_tai_lieu → dung_ban_thao_tong_quat → assemble (soan_thao — mô hình soạn)
             ↘ gom_du_kien → [dung_ban_thao] → assemble   (soan_thao, checklist đang mở dở)
             ↘ hieu_tai_lieu → assemble                            (tài liệu đính kèm)
                             ↘ tien_de → … (đường pháp lý)         (đối chiếu luật)

`giai_nghia` chạy khi `lich_su` khác rỗng HOẶC phiên đã có `tom_tat` (K lượt
nguyên văn đã cuộn hết vào tóm tắt không có nghĩa hội thoại chưa từng có lượt
nào — xem `_vao_graph`), nên lượt đầu THẬT của mỗi hội thoại không tốn thêm một
token nào. `suy_dien` (QT-5) LUÔN chạy khi tới được `route` — 0 token, suy vai
người hỏi từ câu hỏi khi hồ sơ chưa có.

Ba đường rẽ tắt, tất cả đổ về `assemble`:
* `ngoai_pham_vi`/`gioi_thieu`/`hoi_ve_kho` — rẽ ngay sau `route` (`soan_thao`
  KHÔNG còn ở đây từ Task 19: nó có đường riêng, xem `_re_sau_route`);
* `tien_de_sai` — phép kiểm thứ sáu, rẽ trước rewrite/retrieve;
* `cau_hoi_day_du is None` — không giải nghĩa được câu nối tiếp, rẽ ngay sau
  `giai_nghia` vào đúng đường ngõ cụt đã có.
"""

import logging
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from langgraph.graph import END, StateGraph
from sqlalchemy import Engine, text
from starlette.concurrency import run_in_threadpool

from src.agents.graph_soan_thao import KhongSoanDuocError, graph_soan_thao_cached, load_checklist_cached
from src.agents.nodes.assemble import LOAI_BAO_VAN_BAN_AN, assemble, gan_van_ban_khong_hien_thi
from src.agents.nodes.dung_ban_thao_tong_quat import dung_ban_thao_tong_quat
from src.agents.nodes.expand import expand
from src.agents.nodes.generate_claims import generate_claims
from src.agents.nodes.giai_nghia import giai_nghia
from src.agents.nodes.gioi_thieu import can_kho, cau_gioi_thieu, chi_hoi_kho, khia_canh
from src.agents.nodes.gom_du_kien import gom_du_kien
from src.agents.nodes.hieu_tai_lieu import MUC_DICH_SOAN, co_khuon, hieu_tai_lieu
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.route import Intent, route
from src.agents.nodes.suy_dien import suy_dien
from src.agents.nodes.verify_tier1 import nap_provisions, tien_de_cau_hoi_sai, verify_tier1
from src.agents.nodes.verify_tier2 import verify_tier2_and_trace
from src.agents.state import KLawState
from src.config import as_of_hieu_luc, get_settings
from src.services import ban_thao, bao_ve, bo_nho_tai_khoan
from src.services import tai_lieu as tl
from src.services.db import get_engine
from src.services.effectivity import Effectivity, EffectivityVerdict
from src.services.embedding import from_settings as embedder_from_settings
from src.services.hien_thi import hien_thi_luc, van_ban_an_duoc_nhac
from src.services.kho import dung_bang, loi_dan_bang, nap_kho, tra_loi_ve_kho, xin_dang_bang
from src.services.llm import from_settings as llm_from_settings
from src.services.llm import generate_model, judge_model, router_model
from src.services.retrieval import Retriever, cong_diem_linh_vuc, loc_theo_linh_vuc
from src.services.traces import _ghi_traces

logger = logging.getLogger(__name__)


def _db_provisions(ids: list[int], engine: Engine) -> dict[int, dict]:
    """`provisions.id` → dòng, DÙNG CHUNG cho tier1/tier2/assemble — MỘT hình
    dạng thay vì ba, để `khop_tai` (có thể là Khoản/Điểm con của claim) luôn có
    mặt trong kết quả ở cả ba nơi dùng nó.

    Tier 1 (`verify_tier1._cay_con`) duyệt `parent_id` XUỐNG để so quote — cần
    TOÀN BỘ hậu duệ, không chỉ đúng id được claim dẫn. Dùng lại
    `nap_provisions` (đệ quy, Task 5, đã test) thay vì tự viết SQL phẳng: một
    bản phẳng không kèm hậu duệ sẽ loại NHẦM claim hợp lệ trên 73,6% số Điều
    chỉ-tiêu-đề (xem docstring `verify_tier1._cay_con`) — và còn khiến
    `assemble` không bao giờ hiển thị đúng dòng `khop_tai` (luôn rơi về
    `claim.provision_id`, tức hiển thị tiêu đề rỗng nội dung thay vì Khoản/Điểm
    thật chứa quote).

    Tier 2/assemble cần thêm `so_ky_hieu`/`ten` (hiển thị citation) mà
    `nap_provisions` không mang (nó chỉ chọn cột của `provisions`) — join thêm
    `documents` Ở ĐÂY thay vì sửa `nap_provisions` (đã test ở Task 5, không đụng
    module đã verify).
    """
    goc = nap_provisions(engine, ids)
    if not goc:
        return {}
    doc_ids = {r["document_id"] for r in goc.values()}
    with engine.connect() as c:
        docs = {
            r["id"]: {
                "so_ky_hieu": r["so_ky_hieu"],
                "ten": r["ten"],
                "loai_van_ban": r["loai_van_ban"],
                "link_vbpl": r["link_vbpl"],
                "link_chinhphu": r["link_chinhphu"],
                "link_tvpl": r["link_tvpl"],
                # Trích dẫn đầy đủ (quyết định 2026-09-28): `assemble` dựng câu
                # trích và link từ đây. NULL = chưa biết, đi nguyên.
                "co_quan_ban_hanh": r["co_quan_ban_hanh"],
                "ngay_ban_hanh": r["ngay_ban_hanh"],
                "ngay_hieu_luc": r["ngay_hieu_luc"],
            }
            for r in c.execute(
                text(
                    "SELECT id, so_ky_hieu, ten, loai_van_ban, link_vbpl, link_chinhphu, link_tvpl,"
                    " co_quan_ban_hanh, ngay_ban_hanh, ngay_hieu_luc"
                    " FROM documents WHERE id = ANY(:ids)"
                ),
                {"ids": list(doc_ids)},
            )
            .mappings()
            .all()
        }
    return {pid: {**row, **docs.get(row["document_id"], {})} for pid, row in goc.items()}


# Mọi ý định KHÔNG cần tra cứu gì để trả lời. Chúng rẽ tắt ngay sau `route`,
# bỏ qua truy hồi, mở rộng, sinh luận điểm và hai tầng kiểm chứng.
#
# ĐO ĐƯỢC 2026-09-02: trước bản này chỉ `ngoai_pham_vi` rẽ tắt, còn `gioi_thieu`
# đi hết graph rồi mới bị `assemble` chuyển hướng — **8.975 token vào, 15 luận
# điểm qua cả hai tầng, vứt sạch**. Đắt hơn `out_of_scope` 65 lần. Nhánh đó có
# chú thích "0 TOKEN" và chú thích ấy đúng về `assemble` mà sai về thứ người đọc
# hiểu: `assemble` là node CUỐI.
#
# `hoi_ve_kho` rẽ tắt vì cùng lý do, không phải vì rẻ: câu trả lời về kho là một
# phép tra bảng trên `documents` (xem `services/kho.py`), nên một lượt truy hồi
# NỘI DUNG luật không đóng góp gì cho nó — nó chỉ tìm được những văn bản có chữ
# "Luật" trong tiêu đề, đúng cách lỗi 30-điều-khoản-0-luận-điểm đã xảy ra.
#
# `tra_cuu` và mọi giá trị lạ đi đường đầy đủ — mặc định an toàn là tra cứu.
#
# `Intent.soan_thao` KHÔNG còn ở đây (Task 19, bo-nho-tinh-cach-soan-thao): rẽ
# thẳng sang `assemble` từng đúng khi soạn thảo chỉ có MỘT câu trả lời cố định
# (gợi ý mở biểu mẫu). Nay một lượt soạn thảo cần GOM DỮ KIỆN qua nhiều lượt và
# có thể DỰNG bản thảo thật ngay trong hội thoại, nên nó có đường riêng —
# xem `_re_sau_route`.
_RE_TAT = frozenset({Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.hoi_ve_kho})


def _re_sau_route(st: dict) -> str:
    """`soan_thao` là ý định CHÍNH mà `route` vừa đoán cho LƯỢT NÀY — chỉ vậy —
    quyết định lượt có phải soạn thảo hay không. Ba ý định của `_RE_TAT` vẫn rẽ
    tắt như cũ.

    CỐ Ý không để trạng thái phiên (`soan_thao_dang_mo`,
    `ban_thao_tong_quat_dang_mo`) ĐÈ lên ý định (state coordinator review, sau
    lượt đầu triển khai): `route.v3+` đã được cấp `{dang_soan}` để tự phân biệt
    câu trả lời dữ kiện/yêu cầu sửa với một câu hỏi luật thật, và đó là NGUỒN
    SỰ THẬT DUY NHẤT cho quyết định ấy. Xét trạng thái phiên TRƯỚC `intent` có
    nghĩa một câu hỏi luật thật giữa lúc đang soạn sẽ bị hỏi lại dữ kiện, và
    một ý định RẼ TẮT cũng bị kéo vào đường soạn chỉ vì có draft đang mở.
    Trạng thái phiên chỉ được đọc SAU KHI `intent` đã là `soan_thao`, để chọn
    GIỮA hai đường soạn.

    Phase 14 (owner D14-B): mô hình soạn; checklist không còn là cổng của đường
    chat. Một yêu cầu soạn thảo MỚI đi `hieu_tai_lieu` — node đó đã biết dựng
    `van_ban` (`muc_dich = tao_van_ban`/`sua_ban_thao`) và tự làm sạch mọi giá
    trị không có nguồn — rồi `dung_ban_thao_tong_quat` lưu. Đúng cả khi router
    nhận ra một trong 29 mẫu: `assemble` MỜI biểu mẫu một câu (R3), không chặn.
    Trước bản này lượt ấy đi `gom_du_kien`, và một loại văn bản không có
    checklist rơi vào ngõ cụt "chưa có loại này" owner đã gặp bốn lần.

    `gom_du_kien` chỉ còn phục vụ một checklist ĐANG mở dở (`soan_thao_dang_mo`
    — vào từ `/tai-lieu/hoi-thoai/{id}/sang-soan-thao`, hoặc từ trước Phase 14):
    người dùng đang trả lời dữ kiện cho đúng mẫu đó, cắt ngang sang mô hình soạn
    là vứt những gì họ đã cho. Nhánh Phase 3 (`ban_thao_tong_quat_dang_mo` →
    `hieu_tai_lieu`) nay là trường hợp riêng của đường chung, không cần xét tên
    nữa — `hieu_tai_lieu` vẫn đọc trường đó để thấy bản thảo đang có (R4).

    Khách chưa đăng nhập rẽ thẳng `assemble` (0 token): không có chỗ lưu bản
    thảo thì trả tiền một lượt soạn chỉ để nói "bạn cần đăng nhập" là vô ích —
    `assemble._ban_thao_tong_quat` đã có sẵn lời mời đăng nhập cho đúng ca này.
    """
    if st.get("intent") == Intent.soan_thao:
        if not st.get("user_sub"):
            return "assemble"
        return "gom_du_kien" if st.get("soan_thao_dang_mo") else "hieu_tai_lieu"
    if st.get("intent") == Intent.tai_lieu:
        return "hieu_tai_lieu"
    return "assemble" if st.get("intent") in _RE_TAT else "tien_de"


def _re_sau_gom_du_kien(st: dict) -> str:
    """Đủ dữ kiện (`du`) VÀ có tài khoản (`user_sub`) thì dựng bản thảo thật;
    thiếu một trong hai thì `assemble` chỉ hỏi thêm (`soan_thao_hoi`) — khách
    chưa đăng nhập không bao giờ chạm `dung_ban_thao` dù đã đủ dữ kiện.

    `gom_du_kien` XOÁ `soan_thao_dang_mo` khi không biết loại nào
    (`gom_du_kien_nguon = "khong_ro_loai"`). Sau khi xoá, lượt này ĐÚNG là
    "soạn thảo, không có checklist mở dở" — nên nó phải đi lại đúng nhánh
    `_re_sau_route` đã định cho ca đó (`hieu_tai_lieu` → mô hình soạn), không
    rơi thẳng vào `assemble`, nơi `_ban_thao_tong_quat` không có `ban_thao_ket`
    nào để đọc và trả về "Lượt này tôi chưa soạn được mục nào." — ngõ cụt R1 đã
    gỡ, vào lại bằng cửa sau. GỌI LẠI `_re_sau_route` chứ không chép quyết định
    của nó: khách chưa đăng nhập, ý định rẽ tắt và mọi luật khác ở đó vẫn đúng
    y nguyên cho lượt này.
    """
    sd = st.get("soan_thao_dang_mo")
    if not sd:
        return _re_sau_route(st)
    return "dung_ban_thao" if sd.get("du") and st.get("user_sub") else "assemble"


def _vao_graph(st: dict) -> str:
    """Lượt ĐẦU (lịch sử rỗng) vào thẳng `suy_dien` rồi `route` — không tốn thêm
    một token nào.

    Lượt nối tiếp đi qua `giai_nghia` TRƯỚC `route`, vì routing dựa trên câu ĐÃ
    giải nghĩa: "còn model nào khác" sau một lượt `gioi_thieu` là câu hỏi về trợ
    lý, không phải một câu tra cứu — và `route` chỉ thấy được điều đó khi tham
    chiếu đã được giải.

    `tom_tat` (bộ nhớ phiên) cũng rẽ vào đây dù `lich_su` rỗng: K lượt nguyên
    văn đã cuộn hết vào tóm tắt không có nghĩa hội thoại chưa từng có lượt nào.

    Lượt ĐÍNH KÈM tài liệu rẽ thẳng `hieu_tai_lieu`, 0 token: người hỏi vừa gửi
    một tệp cùng câu hỏi thì không còn gì để một mô hình phân loại đoán — chi
    một lượt gọi cho `route` (và một lượt nữa cho `giai_nghia`) ở đây là trả
    tiền để biết lại điều request đã nói thẳng (quyết định chủ sở hữu Q4).

    Phase 3 Half B, fix round 1 — MỘT bản mở rộng ở đây (rẽ TẤT ĐỊNH khi
    `tai_lieu_phien` khác rỗng, bất kể `intent`) đã bị RÚT LẠI sau khi review
    chỉ ra nó vô hiệu hoá `route`/`giai_nghia`/`_RE_TAT` cho TOÀN BỘ phần đời
    còn lại của một hội thoại từng nhận một tài liệu — một câu hỏi luật thật
    ("nghỉ việc phải báo trước bao nhiêu ngày") không còn tới được
    `tien_de`→truy hồi→hai tầng kiểm nữa, mất đúng thứ sản phẩm này tồn tại để
    hứa (trích dẫn đã kiểm chứng). Coordinator xác nhận đó là lỗi của chính
    ruling, không phải của việc triển khai, và SỬA ruling: tài liệu phải CÓ
    MẶT cho một lượt cần tới nó, không được CƯỚP đường đi của lượt đó.

    Cơ chế đúng đã có sẵn TRƯỚC lát cắt này, không cần dựng mới: `route.v4`
    (mặc định, `config.route_prompt`) đã tự chào ý định `Intent.tai_lieu` cho
    model MỖI KHI hội thoại giữ tài liệu (`schema_v4(co_tai_lieu=...)`,
    `{tai_lieu_trong_phien}` — chính comment ở `config.py` nói thẳng nó được
    bật mặc định VÌ đúng lý do này: "lượt NỐI TIẾP hỏi về tài liệu đã gửi
    không có đường nào tới `hieu_tai_lieu`"). Một câu hỏi VỀ tài liệu ở lượt
    nối tiếp đã có đường qua `route()` → `Intent.tai_lieu` →
    `_re_sau_route` (nhánh có TỪ TRƯỚC lát cắt này) → `hieu_tai_lieu`, không
    đụng gì tới `giai_nghia`/`_RE_TAT`/truy hồi của các ý định khác. Sự cố
    owner báo không phải "không có đường" — nó là model gán `soan_thao` thay
    vì `tai_lieu` cho "đây là đơn gì" (một lỗi phân loại có sẵn của model,
    không phải một khoảng trống kiến trúc); và trước lát cắt này, MỘT khi đã
    gán `soan_thao`, `_re_sau_route` đẩy thẳng vào `gom_du_kien` (không có
    checklist cho bản thảo tổng quát) — đó là ngõ cụt THẬT sự cần sửa. Xem
    `_re_sau_route`'s nhánh mới cho đúng chỗ sửa hẹp, không đụng gì ở đây.
    """
    if st.get("tai_lieu_ids"):
        return "hieu_tai_lieu"
    return "giai_nghia" if (st.get("lich_su") or st.get("tom_tat")) else "suy_dien"


def _re_sau_giai_nghia(st: dict) -> str:
    """Không giải nghĩa được → `assemble`, tức ĐƯỜNG NGÕ CỤT ĐÃ CÓ (`_ngo_cut` +
    `hoi_lai`: nói cái đã biết rồi hỏi lại đúng dữ kiện còn thiếu). Không dựng
    đường thứ hai cho cùng một việc.

    Rẽ đường đó cũng bỏ qua truy hồi, và đấy là nửa còn lại của giá trị: một câu
    rỗng nội dung pháp lý ("liệt kê bảng cho tôi") đi vào truy hồi thì khớp
    NHIỄU — đo được 2026-09-02: Luật Phòng chống ma túy và Luật Thương mại.

    Giải nghĩa được → `suy_dien` (QT-5, 0 token), không thẳng `route`: vai người
    hỏi cần đọc câu ĐÃ giải nghĩa, cùng lý do `route` đọc câu đó thay vì câu gốc.
    """
    return "suy_dien" if st.get("cau_hoi_day_du") else "assemble"


# Đúng bộ khoá của `routes_tai_lieu.DuKienOut`: giao diện đọc dữ kiện trong một
# lượt trả lời BẰNG CÙNG thành phần đọc dữ kiện của `GET /tai-lieu/{id}`, nên
# hai chỗ phải ra cùng một hình dạng. Cột nội bộ (`viec_id`, `offset_dau`,
# `tao_luc`) không đi ra: chúng không nói gì với người đọc.
_COT_DU_KIEN_RA = ("khoa", "nhan", "gia_tri", "nguon", "trich", "trich_goc", "trang",
                   "chi_so_don_vi", "do_tin")


def _ghi_du_kien_tai_lieu(engine, st: dict) -> dict:
    """Ghi dữ kiện MỚI rút được trong lượt, rồi đọc lại tập dữ kiện của hội thoại.

    Đây là nửa DB của `hieu_tai_lieu` (node thuần không chạm DB, đúng hợp đồng
    `assemble` đã lập). Đọc LẠI sau khi ghi chứ không ghép tại chỗ vì hai lý do:
    dòng chỉ có `id` sau khi Postgres sinh nó — mà không có `id` thì người dùng
    không sửa/xoá được qua `PATCH/DELETE /tai-lieu/du-kien/{id}` — và một lượt
    trước đó có thể đã rút dữ kiện mà lượt này phải thấy.

    Ghi theo TỪNG việc đọc: `du_kien_tai_lieu.viec_id` trỏ về tài liệu, nên hai
    tài liệu trong một lượt là hai lần ghi, không phải một.
    """
    moi = st.get("tai_lieu_du_kien_moi") or []
    sub, hoi_thoai_id = st.get("user_sub"), st.get("hoi_thoai_id")
    if not (moi and sub and hoi_thoai_id):
        # Khách chưa đăng nhập không có chỗ để lưu (tài liệu vốn đã đòi đăng
        # nhập); không có dữ kiện mới thì cũng không có gì để đọc lại.
        return st
    theo_viec: dict[str, list[dict]] = {}
    for d in moi:
        theo_viec.setdefault(str(d["tai_lieu_id"]), []).append(d)
    for viec_id, hang in theo_viec.items():
        tl.luu_du_kien(engine, viec_id, str(hoi_thoai_id), hang)

    ket = st.get("tai_lieu_ket") or {}
    trong_luot = {str(t["id"]) for t in (ket.get("tai_lieu_da_dung") or [])}
    du_kien = [
        {"id": str(r["id"]), **{c: r.get(c) for c in _COT_DU_KIEN_RA}}
        for r in tl.du_kien_cua_hoi_thoai(engine, str(hoi_thoai_id), sub)
        if str(r["viec_id"]) in trong_luot
    ]
    # `tai_lieu_du_kien_moi` rỗng lại: đã ghi rồi thì nó không còn là việc chờ,
    # và một state còn mang nó là một đường ghi lần hai.
    return {**st, "tai_lieu_ket": {**ket, "du_kien": du_kien}, "tai_lieu_du_kien_moi": []}


def _nap_bo_nho(st: dict) -> dict:
    """Ký ức tài khoản cho lượt này — MỘT `SELECT` theo `user_sub`, chạy TRƯỚC
    node thuần vì node đó không chạm DB (cùng hợp đồng `_ghi_du_kien_tai_lieu`).

    Khách chưa đăng nhập không có ký ức nào, và không có chỗ để có: `liet_ke`
    lọc theo `user_sub` nên một `sub` rỗng không được phép thành một truy vấn.
    """
    sub = st.get("user_sub")
    if not sub:
        return st
    return {**st, "bo_nho_tai_khoan": bo_nho_tai_khoan.liet_ke(sub)}


def _ghi_bo_nho(st: dict) -> dict:
    """Ghi điều người hỏi vừa tự khai, rồi để lại NHÃN của cái THẬT SỰ mới hay
    đổi — `assemble` nói "đã nhớ" đúng những cái đó (R3).

    `ghi` trả `"giu"` khi giá trị y hệt cái đang có: không nhãn nào cho ca ấy,
    vì nói "đã nhớ" mỗi lần người ta nhắc lại tên mình là một thông báo rỗng
    nghĩa mà người đọc sẽ học cách bỏ qua — rồi bỏ qua luôn lần nó thật.

    Best-effort như mọi lượt ghi phụ khác ở file này (`_ghi_traces`): một bản
    thảo đã soạn xong không được hỏng vì một dòng ký ức không ghi được.
    """
    moi, sub = st.get("bo_nho_moi") or [], st.get("user_sub")
    if not (moi and sub):
        return st
    nhan: list[str] = []
    for d in moi:
        try:
            if bo_nho_tai_khoan.ghi(sub, d["loai"], d["khoa"], d["gia_tri"], st.get("hoi_thoai_id")) != "giu":
                nhan.append(bo_nho_tai_khoan.NHAN_KHOA.get(d["khoa"], d["khoa"]))
        except Exception as e:
            # Fix round 1 (review MED) — KHÔNG `logger.exception`. Nó kèm
            # `exc_info`, và `StatementError.__str__` của SQLAlchemy nối thêm
            # `[SQL: …] [parameters: …]`; `src/services/db.py` dựng engine không
            # có `hide_parameters=True`, nên tham số ở đây LÀ `gia_tri` — họ tên
            # và mã sinh viên của người dùng đi vào log mỗi lần DB chập một
            # nhịp. KHOÁ (tên trường, không phải giá trị) cộng TÊN LOẠI lỗi đủ
            # để lần ra sự cố mà không mang theo dữ liệu cá nhân nào.
            logger.warning("ghi_bo_nho: không ghi được khoá %s (%s)",
                           d.get("khoa"), type(e).__name__)
    # `bo_nho_moi` rỗng lại: đã ghi rồi thì nó không còn là việc chờ, và một
    # state còn mang nó là một đường ghi lần hai.
    return {**st, "bo_nho_da_nho": nhan, "bo_nho_moi": []}


def _nap_tai_lieu(engine: Engine, ids: list, ten: dict[str, str], sub: str | None) -> list[dict]:
    """Tài liệu của lượt THEO CHỦ, mỗi cái kèm cờ khuôn gốc (P4b) — phần DB của
    `hieu_tai_lieu`, để node đó thuần.

    `don_vi_cua` tra bằng `(viec_id, user_sub)` và trả `None` khi không thuộc
    người gọi: id của người khác không đọc được ở đây kể cả khi nó lọt qua biên
    HTTP. `khuon_goc_nhe` cùng luật, và không kéo bytes của tệp.
    """
    ra = []
    for vid in map(str, ids):
        don_vi = tl.don_vi_cua(engine, vid, sub)
        if not don_vi:
            continue
        k = tl.khuon_goc_nhe(engine, vid, sub) or {}
        ra.append(
            {
                "id": vid,
                "viec_id": vid,
                "ten_tep": ten.get(vid, ""),
                "don_vi": don_vi,
                "co_khuon_goc": bool(k),
                "dinh_dang": k.get("dinh_dang"),
                "so_trang": k.get("so_trang"),
            }
        )
    return ra


def _nap_ban_thao_dang_mo(st: dict, tai_lieu: list[dict]) -> dict:
    """Nền "# Bản thảo đang có" của lượt theo CÙNG luật với đích lưu
    (`dung_ban_thao_tong_quat` → `moi_nhat_cua_hoi_thoai(viec_id=…)`): bản trên
    khuôn gốc của tài liệu lượt này đọc, hoặc bản HTML (`None`) khi lượt không
    có khuôn gốc. `_chuan_bi_phien` đọc bản mới nhất của hội thoại, bất kể loại
    — trùng loại thì dùng lại, không đọc thêm; lệch thì một lượt HTML sẽ dựng
    lại bản HTML từ tóm tắt biểu mẫu, và một lượt khuôn không thấy giá trị ô.

    ponytail: khuôn gốc ĐẦU TIÊN của lượt; mô hình chọn khuôn khác trong lượt
    nhiều khuôn thì nền lệch — đọc theo `khuon.tai_lieu` khi ca đó có thật.
    """
    viec = next((t["viec_id"] for t in tai_lieu if co_khuon(t)), None)
    if not st.get("user_sub") or (st.get("ban_thao_tong_quat_dang_mo") or {}).get("viec_id") == viec:
        return st
    return {
        **st,
        "ban_thao_tong_quat_dang_mo": ban_thao.ban_thao_tong_quat_dang_mo_nhe(
            st["user_sub"], str(st["hoi_thoai_id"]), viec_id=viec
        ),
    }


def _re_sau_hieu_tai_lieu(st: dict) -> str:
    """Đối chiếu luật đi tiếp vào ĐƯỜNG PHÁP LÝ ĐÃ CÓ (`tien_de` → rewrite →
    retrieve → expand → generate → hai tầng kiểm → assemble), không một đường
    thứ hai nào: một điều khoản của người hỏi chỉ đáng đặt cạnh điều luật khi
    điều luật ấy đã qua đúng bộ kiểm chứng mà mọi câu trả lời khác phải qua.

    Gác thêm `tai_lieu_neo`, không chỉ mục đích: xin đối chiếu mà không điều
    khoản nào tra ngược được thì lượt này KHÔNG có dữ kiện để đối chiếu, và
    `hieu_tai_lieu` đã hạ nó về `hoi` (xem `DOI_CHIEU_KHONG_NEO`). Đẩy nó sang
    đường pháp lý sẽ tiêu một lượt truy hồi + hai tầng kiểm để trả về một bài
    giảng luật chung chung mà người hỏi không xin.

    `tao_van_ban`/`sua_ban_thao` rẽ sang `dung_ban_thao_tong_quat` (S6), KHÔNG
    gác thêm `van_ban_tong_quat` hay `user_sub`: node đó là nơi DUY NHẤT biết
    cách nói "chưa soạn được mục nào" / "bạn cần đăng nhập" cho lượt soạn, và
    bỏ qua nó sẽ trả về một bản tóm tắt tài liệu cho người vừa xin một văn bản.
    """
    if st.get("muc_dich_tai_lieu") == "doi_chieu_luat" and st.get("tai_lieu_neo"):
        return "tien_de"
    if st.get("muc_dich_tai_lieu") in MUC_DICH_SOAN:
        return "dung_ban_thao_tong_quat"
    return "assemble"


def build_graph_tra_cuu():
    s = get_settings()
    llm = llm_from_settings()
    engine = get_engine()
    retriever = Retriever(engine, embedder_from_settings(), s)

    def n_giai_nghia(st: KLawState) -> KLawState:
        # Model ROUTE (`gemini-2.5-flash-lite`, đo 1,56s), không phải model
        # generate: đây là một phép biến đổi câu hỏi có ràng buộc chặt, cùng
        # hạng việc với `route`/`rewrite_query`, không phải một lượt hành văn.
        return giai_nghia(st, llm, router_model())

    def n_suy_dien(st: KLawState) -> KLawState:
        return suy_dien(st)

    def n_route(st: KLawState) -> KLawState:
        return route(st, llm, router_model(), prompt_path=Path(s.route_prompt))

    async def n_hieu_tai_lieu(st: KLawState) -> KLawState:
        """Nạp đơn vị văn bản (và cờ khuôn gốc) THEO CHỦ — `_nap_tai_lieu` — rồi
        giao cho node đọc. Kiểm chủ ở tầng dữ liệu, cùng nguyên tắc
        `ban_thao`/`hoi_thoai`, không phải một phép kiểm thứ hai ở tầng API.

        Lượt NỐI TIẾP (router chọn `tai_lieu`, không đính kèm gì) đọc tài liệu
        MỚI NHẤT của hội thoại: `tai_lieu_cua_hoi_thoai` trả mới-trước, và
        "phiếu này" trong một câu hỏi tiếp theo gần như luôn là tệp vừa gửi.
        """
        ids = list(st.get("tai_lieu_ids") or [])
        if not ids:
            ids = [r["id"] for r in (st.get("tai_lieu_phien") or [])[:1]]
        ten = {str(r["id"]): r.get("ten_tep") or "" for r in (st.get("tai_lieu_phien") or [])}
        tai_lieu = await run_in_threadpool(_nap_tai_lieu, engine, ids, ten, st.get("user_sub"))
        st = await run_in_threadpool(_nap_ban_thao_dang_mo, st, tai_lieu)
        # Ký ức tài khoản vào TRƯỚC (prompt cần nó), điều vừa khai ghi ra SAU —
        # hai phép DB kẹp lấy node thuần, đúng hình dạng `_ghi_du_kien_tai_lieu`.
        st = await run_in_threadpool(_nap_bo_nho, st)
        ra = hieu_tai_lieu(st, tai_lieu, llm, generate_model())
        ra = await run_in_threadpool(_ghi_du_kien_tai_lieu, engine, ra)
        return await run_in_threadpool(_ghi_bo_nho, ra)

    async def n_dung_ban_thao_tong_quat(st: KLawState) -> KLawState:
        # `run_in_threadpool` vì hàm kia gọi `ban_thao` (SQLAlchemy đồng bộ) —
        # cùng cách mọi node chạm DB khác ở file này giữ event loop rảnh.
        return await run_in_threadpool(dung_ban_thao_tong_quat, st)

    def n_gom_du_kien(st: KLawState) -> KLawState:
        return gom_du_kien(st, llm, router_model())

    def _ban_thao_ket(loai: str, bt: dict, ten: str, doi: list[str]) -> dict:
        """Hình dạng chung của `state["ban_thao_ket"]`, dựng từ MỘT dòng `ban_thao`
        (cột `audit`, không phải `audit_report`) — dùng chung cho nhánh tạo VÀ
        nhánh sửa, để đổi hình dạng chỉ phải sửa một chỗ."""
        return {
            "id": bt["id"],
            "loai": loai,
            "ten": ten,
            "phien_ban": bt["phien_ban"],
            "document": bt["document"],
            "clauses": bt["clauses"],
            "audit_report": bt["audit"],
            "facts": bt["facts"],
            "doi_so_voi_truoc": doi,
            "can_cu_van_ban": ban_thao.can_cu_tu_document(bt["document"]),
        }

    async def n_dung_ban_thao(st: KLawState) -> KLawState:
        """Đủ dữ kiện: kiểm hạn mức soạn thảo, chạy graph_soan_thao, lưu bản thảo (tạo hoặc sửa), ghi trace.

        Nhánh sửa (`la_sua`) đi qua `ban_thao.dung_lai` — CÙNG hàm mà endpoint
        `POST /ban-thao/{id}/dung` của drawer xếp chồng (Task 25) gọi — nên trần
        sửa, cách chạy graph và cách ghi trace chỉ có MỘT bản, không phải một bản
        ở đây và một bản ở service. Guard `so_lan_sua` cũ (đếm theo phiên hội
        thoại đang mở) đã bị bỏ: `dung_lai` tự kiểm trần trên CHÍNH bộ đếm đơn
        điệu của bản thảo (`so_lan_sua`, migration 025), nên một bản thảo đã sửa đủ
        `TRAN_SUA` lần bị chặn dù người dùng mở một phiên hội thoại mới.
        """
        sd = st["soan_thao_dang_mo"]
        sub = st["user_sub"]
        la_sua = bool(sd.get("ban_thao_id"))
        if la_sua:
            try:
                bt = await ban_thao.dung_lai(sub, sd["ban_thao_id"], sd["facts"], st.get("hoi_thoai_id"))
            except ValueError as e:
                return {**st, "soan_thao_dang_mo": {**sd, "het_han_muc": str(e)}}
            if bt is None:
                return {**st, "soan_thao_dang_mo": {**sd, "het_han_muc": ban_thao.LOI_KHONG_THAY}}
            ban_thao_ket = _ban_thao_ket(sd["loai"], bt, bt["ten"], bt["doi_so_voi_truoc"])
            return {
                **st,
                "ban_thao_ket": ban_thao_ket,
                "soan_thao_dang_mo": {**sd, "ban_thao_id": bt["id"], "so_lan_sua": int(sd.get("so_lan_sua") or 0) + 1},
            }

        plan = await run_in_threadpool(bao_ve.plan_hieu_luc, sub)
        try:
            await run_in_threadpool(bao_ve.kiem_han_muc, sub, plan, bao_ve.EP_SOAN_THAO)
        except HTTPException as e:
            return {**st, "soan_thao_dang_mo": {**sd, "het_han_muc": str(e.detail)}}
        bat_dau = time.monotonic()
        try:
            ket_st = await graph_soan_thao_cached().ainvoke(
                {"loai": sd["loai"], "loai_van_ban": sd["loai"], "facts": sd["facts"], "nganh": "thuong_mai"}
            )
        except KhongSoanDuocError as e:
            # Cùng lối nói với nhánh sửa (`dung_lai` ném cùng lỗi này): 0 lượt LLM.
            return {**st, "soan_thao_dang_mo": {**sd, "het_han_muc": str(e)}}
        ket = ban_thao.tu_state_soan_thao(ket_st)
        bt = await run_in_threadpool(ban_thao.tao, sub, st.get("hoi_thoai_id"), sd["loai"], sd["facts"], ket)
        try:
            await run_in_threadpool(
                _ghi_traces,
                str(uuid.uuid4()),
                bao_ve.EP_SOAN_THAO,
                sd["loai"],
                s.eval_config_name,
                {"result_type": "ban_thao", "traces": ket_st.get("traces") or {}},
                int((time.monotonic() - bat_dau) * 1000),
                user_sub=sub,
            )
        except Exception:
            logger.exception("dung_ban_thao: không ghi được traces")
        ban_thao_ket = _ban_thao_ket(sd["loai"], bt, load_checklist_cached(sd["loai"]).ten, [])
        return {
            **st,
            "ban_thao_ket": ban_thao_ket,
            "soan_thao_dang_mo": {**sd, "ban_thao_id": bt["id"], "so_lan_sua": int(sd.get("so_lan_sua") or 0)},
        }

    def n_tien_de(st: KLawState) -> KLawState:
        # Phép kiểm thứ sáu (0 token) — TRƯỚC rewrite/retrieve/generate, để
        # không tốn một token nào cho một câu hỏi đã biết tiền đề sai.
        return {**st, "tien_de_sai": tien_de_cau_hoi_sai(st["query"], engine)}

    def n_rewrite(st: KLawState) -> KLawState:
        return rewrite_query(st, llm, router_model(), prompt_path=Path(s.rewrite_prompt))

    def n_retrieve(st: KLawState) -> KLawState:
        # Quy tắc hiển thị (`services/hien_thi`) — MỘT lần mỗi lượt, `expand`
        # dùng lại: văn bản ẩn không bao giờ được truy hồi làm căn cứ.
        hien = hien_thi_luc(engine, as_of_hieu_luc(st.get("as_of_date")))
        ids: list[int] = []
        for q in st.get("queries") or [st["query"]]:
            ids += retriever.provision_ids(retriever.hybrid(q, hien))
        ids = list(dict.fromkeys(ids))
        # Spec 2026-09-06 §6 — cộng điểm mềm theo lĩnh vực mô hình đoán. Mặc
        # định `linh_vuc_bonus = 0` (tắt) cho tới khi đo được trên golden.
        if s.linh_vuc_bonus > 0 and st.get("linh_vuc_du_doan"):
            ids = cong_diem_linh_vuc(ids, retriever.linh_vuc_cua(ids), st["linh_vuc_du_doan"], s.linh_vuc_bonus)
        # Khoanh vùng CỨNG theo lĩnh vực (spec 2026-09-09 §7.4) — khác nhánh
        # cộng điểm mềm ngay trên, nhánh này LOẠI khỏi tập truy hồi, nên phải
        # fail open: `loc_theo_linh_vuc` tự mở lại toàn kho khi lọc còn quá ít.
        mo_rong = False
        if s.linh_vuc_loc and st.get("linh_vuc_du_doan"):
            ids, mo_rong = loc_theo_linh_vuc(ids, retriever.linh_vuc_cua(ids), st["linh_vuc_du_doan"])
        return {**st, "retrieved": ids, "hien_thi": sorted(hien),
                "traces": {**(st.get("traces") or {}), "retrieve_mo_rong": mo_rong}}

    def n_expand(st: KLawState) -> KLawState:
        # MỘT chủ sở hữu cho quy tắc "mốc hiệu lực" (`config.as_of_hieu_luc`):
        # khoá cache câu trả lời phải ghi nhớ ĐÚNG cái ngày mà node này lọc
        # theo. Hai bản sao của quy tắc = cache khoá theo một ngày, graph lọc
        # hiệu lực theo ngày khác, không tầng nào báo lỗi — chỉ trả hiệu lực sai.
        as_of = as_of_hieu_luc(st.get("as_of_date"))
        before = st.get("retrieved") or []
        # `hien_thi` vắng chỉ khi lượt không qua `retrieve` (không có gì để mở
        # rộng) — tính lại chứ không mở cửa cho văn bản ẩn.
        hien = frozenset(st["hien_thi"]) if "hien_thi" in st else hien_thi_luc(engine, as_of)
        deep, shallow = expand(before, engine, as_of, s.expand_reference_hops, hien)
        prior_traces = st.get("traces") or {}
        # Kích thước tập TRƯỚC/SAU expand — dữ liệu chương đánh giá (đo đóng góp
        # của bước mở rộng, xem task-7-report.md). `after` = len(deep): đây là
        # tập THẬT SỰ đưa cho generate_claims — `shallow` không chảy xuống hạ
        # nguồn nên không tính vào "đóng góp" của bước mở rộng.
        return {**st, "expanded": deep, "hits_shallow": shallow, "traces": {
            **prior_traces, "expand_before": len(before), "expand_after": len(deep),
        }}

    def n_generate(st: KLawState) -> KLawState:
        if not st.get("expanded"):
            return {**st, "draft_claims": [], "insufficient_evidence": True}
        return generate_claims(st, llm, generate_model(), prompt_path=Path(s.generate_prompt))

    def n_tier1(st: KLawState) -> KLawState:
        claims = st.get("draft_claims") or []
        dbp = _db_provisions([c.provision_id for c in claims], engine)
        # expand() ĐÃ tính effectivity cho từng provision (đi qua cạnh đi vào
        # thật của Task 2) — DÙNG LẠI. Tính lại ở đây bằng cách gọi
        # effectivity_qua_provision(engine, dbp, as_of) sẽ ăn `canh_di_vao` RỖNG
        # (dbp ở đây không mang cạnh đồ thị) và luôn ra con_hieu_luc — Mức 2
        # không bao giờ kích hoạt, làm nhóm bẫy "văn bản đã bị thay" của
        # trap.yaml fail im lặng (xem
        # test_effectivity_tu_expand_duoc_dung_KHONG_tinh_lai_voi_canh_rong).
        eff_map = {p["id"]: p["effectivity"] for p in (st.get("expanded") or []) if p.get("effectivity") is not None}
        # `chua_xac_dinh`, KHÔNG PHẢI `con_hieu_luc` (silent-failure review):
        # effectivity.py quy định dứt khoát — không biết → chua_xac_dinh,
        # KHÔNG BAO GIỜ mặc định còn hiệu lực. Nhánh này hiện KHÔNG đến được
        # qua graph thật (trong_context và eff_map cùng dựng từ st["expanded"],
        # và expand() gán effectivity cho MỌI dòng) — nhưng chỉ cần một tối ưu
        # tương lai làm hai list lệch nhau là một điều luật CHƯA TỪNG được
        # đánh giá sẽ hiện ra "còn hiệu lực, không cảnh báo": đúng chế độ hỏng
        # nguy hiểm nhất của cả đề tài, xảy ra ở chính điểm mặc định an toàn
        # phải chặn.
        mac_dinh = Effectivity(EffectivityVerdict.chua_xac_dinh, "thap",
                               "không có trong tập expanded — không đánh giá được hiệu lực")
        return {**st, "tier1": verify_tier1(claims, st.get("expanded") or [], dbp,
                                             lambda pid: eff_map.get(pid, mac_dinh))}

    def n_tier2(st: KLawState) -> KLawState:
        if not s.verify_tier2_enabled:
            return {**st, "tier2": []}
        t1 = st.get("tier1") or []
        dbp = _db_provisions([r.claim.provision_id for r in t1 if r.ok], engine)
        verdicts, traces = verify_tier2_and_trace(
            t1, dbp, llm, judge_model(), st.get("traces"),
            prompt_path=Path(s.tier2_prompt), khung_yeu_cau=st.get("khung_yeu_cau"), cau_hoi=st["query"],
        )
        return {**st, "tier2": verdicts, "traces": traces}

    def n_assemble(st: KLawState) -> KLawState:
        # ex.md §3.2–3.3: one facet pass for both meta intents. Corpus-only
        # questions keep the existing `hoi_ve_kho` text/table path below;
        # anything naming the assistant composes from one `nap_kho` snapshot
        # (FR-014), loaded only when a corpus facet is present.
        y_dinh = st.get("intent")
        if y_dinh in (Intent.gioi_thieu, Intent.hoi_ve_kho):
            cau_hoi_meta = st.get("cau_hoi_day_du") or st["query"]
            cac = khia_canh(cau_hoi_meta)
            if not (y_dinh == Intent.hoi_ve_kho and chi_hoi_kho(cac)):
                kho = nap_kho(engine, as_of_hieu_luc(st.get("as_of_date"))) if can_kho(cac) else None
                tra_loi = cau_gioi_thieu(
                    cau_hoi_meta, kho=kho, luot_dau=not (st.get("lich_su") or st.get("tom_tat"))
                )
                st = {**st, "tra_loi_gioi_thieu": tra_loi, "tra_loi_kho": tra_loi, "tra_loi_kho_bang": [],
                      "traces": {**(st.get("traces") or {}), "gioi_thieu_khia_canh": cac}}
                if y_dinh == Intent.gioi_thieu:
                    return assemble(st, {}, llm, generate_model(), prompt_path=Path(s.assemble_prompt))
        if y_dinh == Intent.hoi_ve_kho and "tra_loi_gioi_thieu" not in st:
            # SQL cho câu hỏi về kho chạy Ở ĐÂY, không trong `assemble`.
            #
            # `assemble` KHÔNG có `engine` — và đúng ra là không nên có: nó đã
            # nhận `db_provisions` do chính node này nạp sẵn, tức hợp đồng hiện
            # hành là "node lo phần DB, assemble lo phần dựng lời". Đưa chuỗi
            # đã tính vào state là CÙNG hình dạng với `db_provisions`; truyền
            # thêm `engine` xuống thì đổi chữ ký mà hơn 40 chỗ gọi `assemble`
            # trong test đang dùng, để phục vụ đúng một nhánh. Chọn cách không
            # đụng chữ ký nào.
            #
            # `as_of_hieu_luc` chứ không phải `date.today()`: cùng một chủ sở
            # hữu quy tắc mốc hiệu lực với `n_expand` và với khoá cache (xem
            # chú thích ở `n_expand`) — số Bộ luật "đang dùng" phụ thuộc mốc
            # thời gian, nên hai bản sao của quy tắc sẽ cho hai con số khác
            # nhau mà không tầng nào báo lỗi.
            as_of = as_of_hieu_luc(st.get("as_of_date"))
            # Ý "xin bảng" (T4) chạy trên câu ĐÃ GIẢI NGHĨA khi có — một lượt
            # nối tiếp như "cho tôi dạng bảng" chỉ tự đứng được sau bước đó;
            # lượt đầu không qua `giai_nghia` nên `cau_hoi_day_du` luôn None,
            # rơi về `query`.
            cau_hoi = st.get("cau_hoi_day_du") or st["query"]
            if xin_dang_bang(cau_hoi):
                # `nap_kho` MỘT LẦN, y hệt `tra_loi_ve_kho` bên dưới — nhánh
                # nào chạy cũng chỉ một truy vấn kho, không phải hai.
                bang = dung_bang(cau_hoi, nap_kho(engine, as_of))
                tra_loi = loi_dan_bang()
            else:
                bang = []
                # `st["query"]` NGUYÊN VĂN, không phải `cau_hoi` ở trên: đổi
                # biến ở đây đổi luôn văn xuôi mà ba mươi test của
                # `test_kho.py` đang canh — một hồi quy không nhánh bảng nào
                # đòi hỏi.
                tra_loi = tra_loi_ve_kho(engine, st["query"], as_of)
            # Pydantic → dict THUẦN trước khi vào state, cùng quy ước
            # `_state_vao` đã lập cho `LuotTruoc` (`lich_su`): LangGraph state
            # là dữ liệu thuần, và một `Bang` lẫn vào đó không tuần tự hoá
            # được thẳng bằng `json.dumps` ở tầng cache (`cache_tra_loi`).
            st = {**st, "tra_loi_kho": tra_loi,
                  "tra_loi_kho_bang": [b.model_dump() for b in bang]}
        ids = [r.claim.provision_id for r in (st.get("tier1") or [])]
        ket = assemble(
            {**st, "abstain_threshold": s.abstain_threshold},
            _db_provisions(ids, engine),
            llm,
            generate_model(),
            prompt_path=Path(s.assemble_prompt),
        )
        # Câu hỏi NÊU TÊN một văn bản ẩn ("Nghị định 90/2019 còn hiệu lực không")
        # — quyết định 2026-09-28 mục 8: nói thẳng nó không còn hiệu lực, nêu
        # văn bản thay thế. 0 token; 0 truy vấn khi câu hỏi không có số hiệu.
        if ket.get("result_type") not in LOAI_BAO_VAN_BAN_AN:
            return ket
        cau_hoi = st.get("cau_hoi_day_du") or st["query"]
        return gan_van_ban_khong_hien_thi(
            ket, van_ban_an_duoc_nhac(engine, cau_hoi, as_of_hieu_luc(st.get("as_of_date"))))

    g = StateGraph(KLawState)
    # Thứ tự khai node = thứ tự `get_graph().nodes`, mà `routes.BUOC_TRA_CUU`
    # được khoá khớp với nó (`test_BUOC_TRA_CUU_khop_dung_node_cua_graph_da_compile`)
    # — nên `giai_nghia` đứng đầu ở cả hai chỗ.
    for name, fn in (
        ("giai_nghia", n_giai_nghia),
        ("suy_dien", n_suy_dien),
        ("route", n_route),
        ("hieu_tai_lieu", n_hieu_tai_lieu),
        ("dung_ban_thao_tong_quat", n_dung_ban_thao_tong_quat),
        ("gom_du_kien", n_gom_du_kien),
        ("dung_ban_thao", n_dung_ban_thao),
        ("tien_de", n_tien_de),
        ("rewrite", n_rewrite),
        ("retrieve", n_retrieve),
        ("expand", n_expand),
        ("generate", n_generate),
        ("tier1", n_tier1),
        ("tier2", n_tier2),
        ("assemble", n_assemble),
    ):
        g.add_node(name, fn)

    # Nhánh vào có ĐIỀU KIỆN, không phải một node luôn chạy rồi tự bỏ qua: lượt
    # đầu của mỗi hội thoại không được ghé qua `giai_nghia` một lần nào, kể cả
    # một lần không gọi LLM (nó vẫn là một bước trong thanh tiến trình SSE nói
    # rằng có việc đã làm, trong khi không có việc nào).
    g.set_conditional_entry_point(_vao_graph)
    g.add_conditional_edges("giai_nghia", _re_sau_giai_nghia)
    g.add_edge("suy_dien", "route")
    g.add_conditional_edges("route", _re_sau_route)
    g.add_conditional_edges("hieu_tai_lieu", _re_sau_hieu_tai_lieu)
    g.add_edge("dung_ban_thao_tong_quat", "assemble")
    g.add_conditional_edges("gom_du_kien", _re_sau_gom_du_kien)
    g.add_edge("dung_ban_thao", "assemble")
    g.add_conditional_edges("tien_de", lambda st: (
        "assemble" if st.get("tien_de_sai") else "rewrite"))
    for a, b in (("rewrite", "retrieve"), ("retrieve", "expand"), ("expand", "generate"),
                 ("generate", "tier1"), ("tier1", "tier2"), ("tier2", "assemble")):
        g.add_edge(a, b)
    g.add_edge("assemble", END)
    return g.compile()
