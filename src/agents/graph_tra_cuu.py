"""Graph tra cứu (spec mục 6) — nối các node đã build thành một đồ thị chạy được.

[giai_nghia] → suy_dien → route → tien_de → rewrite_query → retrieve_hybrid
             → expand → generate_claims → verify_tier1 → verify_tier2 → assemble
                      ↘ gom_du_kien → [dung_ban_thao] → assemble   (intent soan_thao)
             ↘ hieu_tai_lieu → assemble                            (tài liệu đính kèm)
                             ↘ tien_de → … (đường pháp lý)         (đối chiếu luật)

`giai_nghia` chạy khi `lich_su` khác rỗng HOẶC phiên đã có `tom_tat` (K lượt
nguyên văn đã cuộn hết vào tóm tắt không có nghĩa hội thoại chưa từng có lượt
nào — xem `_vao_graph`), nên lượt đầu THẬT của mỗi hội thoại không tốn thêm một
token nào. `suy_dien` (QT-5) LUÔN chạy khi tới được `route` — 0 token, suy vai
người hỏi từ câu hỏi khi hồ sơ chưa có.

Ba đường rẽ tắt, tất cả đổ về `assemble`:
* `ngoai_pham_vi`/`gioi_thieu`/`hoi_ve_kho` — rẽ ngay sau `route` (`soan_thao`
  KHÔNG còn ở đây từ Task 19: nó đi `gom_du_kien` trước, xem `_re_sau_route`);
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

from src.agents.graph_soan_thao import graph_soan_thao_cached, load_checklist_cached
from src.agents.nodes.assemble import assemble
from src.agents.nodes.dung_ban_thao_tong_quat import dung_ban_thao_tong_quat
from src.agents.nodes.expand import expand
from src.agents.nodes.generate_claims import generate_claims
from src.agents.nodes.giai_nghia import giai_nghia
from src.agents.nodes.gioi_thieu import can_kho, cau_gioi_thieu, chi_hoi_kho, khia_canh
from src.agents.nodes.gom_du_kien import gom_du_kien
from src.agents.nodes.hieu_tai_lieu import MUC_DICH_SOAN, hieu_tai_lieu
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.route import Intent, route
from src.agents.nodes.suy_dien import suy_dien
from src.agents.nodes.verify_tier1 import nap_provisions, tien_de_cau_hoi_sai, verify_tier1
from src.agents.nodes.verify_tier2 import verify_tier2_and_trace
from src.agents.state import KLawState
from src.config import as_of_hieu_luc, get_settings
from src.services import ban_thao, bao_ve
from src.services import tai_lieu as tl
from src.services.db import get_engine
from src.services.effectivity import Effectivity, EffectivityVerdict
from src.services.embedding import from_settings as embedder_from_settings
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
            }
            for r in c.execute(
                text(
                    "SELECT id, so_ky_hieu, ten, loai_van_ban, link_vbpl, link_chinhphu, link_tvpl"
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
    đi `gom_du_kien` trước khi tới `assemble`. Ba ý định của `_RE_TAT` vẫn rẽ
    tắt như cũ.

    CỐ Ý không xét thêm `soan_thao_dang_mo` (state coordinator review, sau khi
    lượt đầu triển khai): việc phiên đang mở một bản thảo dở KHÔNG được tự nó
    ép lượt này vào `gom_du_kien` — `route.v3.md` đã được cấp `{dang_soan}` để
    tự phân biệt câu trả lời dữ kiện/yêu cầu sửa với một câu hỏi luật thật, và
    đó phải là NGUỒN SỰ THẬT DUY NHẤT cho quyết định rẽ. Xét thêm điều kiện đó
    có nghĩa ý định model vừa đoán không bao giờ được tham khảo cho quyết định
    này: một câu hỏi luật thật giữa lúc đang soạn sẽ luôn bị hỏi lại dữ kiện
    thay vì được trả lời, và một ý định RẼ TẮT (`gioi_thieu`/`hoi_ve_kho`/
    `ngoai_pham_vi`) cũng sẽ bị kéo vào `gom_du_kien` chỉ vì có draft đang mở.

    Phase 3 Half B (R5) — MỘT ngoại lệ hẹp, KHÔNG lặp lại lỗi trên: khi ý định
    đã là `soan_thao` (router đã quyết định — điều kiện trên KHÔNG đổi) và hội
    thoại này có SẴN một bản thảo TỔNG QUÁT (`ban_thao_tong_quat_dang_mo`),
    lượt đi `hieu_tai_lieu` thay vì `gom_du_kien`. Bản thảo tổng quát không có
    checklist nào để gom dữ kiện — `gom_du_kien` không thể phục vụ nó, chỉ có
    thể lặp lại đúng ngõ cụt owner báo ("Kho mẫu của tôi chưa có loại văn bản
    này…"). `hieu_tai_lieu` đã có `muc_dich = "sua_ban_thao"` cho đúng việc
    này (không qua checklist, xem `MUC_DICH_SOAN`/`_re_sau_hieu_tai_lieu`).
    Đây KHÔNG phải xét thêm state "có draft nào đang mở không" nói chung — nó
    chỉ hẹp cho MỘT loại bản thảo (tổng quát) và chỉ SAU KHI `intent` đã là
    `soan_thao`; một câu hỏi luật thật, hay một ý định rẽ tắt, không bao giờ
    được phân loại `soan_thao` để bắt đầu, nên không đi qua nhánh này. Đánh
    đổi đã biết: nếu hội thoại có bản thảo tổng quát, một yêu cầu soạn một
    loại văn bản KHÁC (checklist) trong CÙNG hội thoại đó cũng rơi vào nhánh
    này thay vì mở checklist mới — đúng yêu cầu brief ("'Chọn loại văn bản'
    không được mời trong khi đang có một bản thảo mở"), nhưng nghĩa là muốn
    soạn loại khác thì phải mở hội thoại mới.
    """
    if st.get("intent") == Intent.soan_thao:
        return "hieu_tai_lieu" if st.get("ban_thao_tong_quat_dang_mo") else "gom_du_kien"
    if st.get("intent") == Intent.tai_lieu:
        return "hieu_tai_lieu"
    return "assemble" if st.get("intent") in _RE_TAT else "tien_de"


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

    Phase 3 Half B — ruling MỞ RỘNG sau sự cố THẬT (coordinator, không phải
    suy luận của lát cắt này): KHÔNG chỉ lượt vừa đính kèm — MỌI lượt của một
    hội thoại đang GIỮ tài liệu (`tai_lieu_phien`, tính từ toàn bộ lịch sử hội
    thoại qua `tai_lieu.tai_lieu_cua_hoi_thoai`, không chỉ lượt này) cũng rẽ
    thẳng vào đây. Đo được: owner hỏi "đây là đơn gì" ở lượt SAU lượt tạo bản
    thảo — `route` không hề biết hội thoại có tài liệu nào (nó chỉ thấy câu
    chữ), nên đoán `soan_thao` và đẩy một câu HỎI vào `gom_du_kien` (không có
    checklist nào cho bản thảo tổng quát — đúng ngõ cụt "Kho mẫu của tôi chưa
    có loại văn bản này" owner báo). `hieu_tai_lieu` đã có `muc_dich = "hoi"`
    cho đúng câu hỏi này; vấn đề chưa từng ở đó, mà ở chỗ lượt không TỚI được
    nó. Rẽ ở ĐÂY (trước `giai_nghia`/`route`) thay vì dạy `route` nhận biết
    tài liệu: `route` là một lượt LLM, và sửa hành vi của nó cần đo lại bằng
    lượt gọi thật — đắt và chậm hơn một điều kiện thuần Python, đúng khuôn
    "quyết định chủ sở hữu Q4" đã áp cho lượt đính kèm ở trên.

    Đánh đổi ĐÃ BIẾT, CHẤP NHẬN ĐƯỢC theo ruling: một lượt hoàn toàn không
    liên quan tài liệu (chào tạm biệt, hỏi về KLAW) trong một hội thoại có
    tài liệu cũng bị `hieu_tai_lieu` xử lý thay vì rẽ tắt 0 token qua `_RE_TAT`
    — `hieu_tai_lieu` mặc định về `muc_dich = "hoi"` khi không chắc (rule 2,
    prompt), không phải một câu trả lời sai nghiêm trọng, và ĐÂY KHÔNG PHẢI
    đường có thể GHI (xem `_an_toan_xac_nhan_soan` — chỉ `sua_ban_thao`/
    `tao_van_ban` mới chạm `ban_thao`, và một câu không mang dấu hiệu soạn/sửa
    rõ ràng không bao giờ được coi là hai mục đích đó nữa, bất kể mô hình gán
    gì). `giai_nghia` (câu nối tiếp) cũng bị bỏ qua cho các lượt này — cùng
    đánh đổi đã có sẵn cho "lượt đính kèm tài liệu" từ trước bản vá này, không
    phải rủi ro mới.
    """
    if st.get("tai_lieu_ids") or st.get("tai_lieu_phien"):
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
        """Nạp đơn vị văn bản THEO CHỦ rồi giao cho node đọc.

        `don_vi_cua` tra bằng `(viec_id, user_sub)` và trả `None` khi không
        thuộc người gọi, nên id của người khác không đọc được ở đây kể cả khi nó
        lọt qua biên HTTP — cùng nguyên tắc "kiểm chủ ở tầng dữ liệu" của
        `ban_thao`/`hoi_thoai`, không phải một phép kiểm thứ hai ở tầng API.

        Lượt NỐI TIẾP (router chọn `tai_lieu`, không đính kèm gì) đọc tài liệu
        MỚI NHẤT của hội thoại: `tai_lieu_cua_hoi_thoai` trả mới-trước, và
        "phiếu này" trong một câu hỏi tiếp theo gần như luôn là tệp vừa gửi.

        `tl.don_vi_cua` tra qua module chứ không nhập tên: S1 đang thêm hàm này
        trong một lát cắt chạy SONG SONG, và một `from … import` ở đầu file sẽ
        làm cả API không khởi động được cho tới khi lát cắt đó xong.
        """
        ids = list(st.get("tai_lieu_ids") or [])
        if not ids:
            ids = [r["id"] for r in (st.get("tai_lieu_phien") or [])[:1]]
        ten = {str(r["id"]): r.get("ten_tep") or "" for r in (st.get("tai_lieu_phien") or [])}
        tai_lieu = []
        for vid in ids:
            don_vi = await run_in_threadpool(tl.don_vi_cua, engine, str(vid), st.get("user_sub"))
            if don_vi:
                tai_lieu.append({"id": str(vid), "ten_tep": ten.get(str(vid), ""), "don_vi": don_vi})
        ra = hieu_tai_lieu(st, tai_lieu, llm, generate_model())
        return await run_in_threadpool(_ghi_du_kien_tai_lieu, engine, ra)

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
        ket_st = await graph_soan_thao_cached().ainvoke(
            {"loai": sd["loai"], "loai_van_ban": sd["loai"], "facts": sd["facts"], "nganh": "thuong_mai"}
        )
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
        ids: list[int] = []
        for q in st.get("queries") or [st["query"]]:
            ids += retriever.provision_ids(retriever.hybrid(q))
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
        return {**st, "retrieved": ids, "traces": {**(st.get("traces") or {}), "retrieve_mo_rong": mo_rong}}

    def n_expand(st: KLawState) -> KLawState:
        # MỘT chủ sở hữu cho quy tắc "mốc hiệu lực" (`config.as_of_hieu_luc`):
        # khoá cache câu trả lời phải ghi nhớ ĐÚNG cái ngày mà node này lọc
        # theo. Hai bản sao của quy tắc = cache khoá theo một ngày, graph lọc
        # hiệu lực theo ngày khác, không tầng nào báo lỗi — chỉ trả hiệu lực sai.
        as_of = as_of_hieu_luc(st.get("as_of_date"))
        before = st.get("retrieved") or []
        deep, shallow = expand(before, engine, as_of, s.expand_reference_hops)
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
        return assemble(
            {**st, "abstain_threshold": s.abstain_threshold},
            _db_provisions(ids, engine),
            llm,
            generate_model(),
            prompt_path=Path(s.assemble_prompt),
        )

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
    # Đủ dữ kiện (`du`) VÀ có tài khoản (`user_sub`) thì dựng bản thảo thật;
    # thiếu một trong hai thì `assemble` chỉ hỏi thêm (`soan_thao_hoi`) — khách
    # chưa đăng nhập không bao giờ chạm `dung_ban_thao` dù đã đủ dữ kiện.
    g.add_conditional_edges(
        "gom_du_kien",
        lambda st: (
            "dung_ban_thao" if (st.get("soan_thao_dang_mo") or {}).get("du") and st.get("user_sub") else "assemble"
        ),
    )
    g.add_edge("dung_ban_thao", "assemble")
    g.add_conditional_edges("tien_de", lambda st: (
        "assemble" if st.get("tien_de_sai") else "rewrite"))
    for a, b in (("rewrite", "retrieve"), ("retrieve", "expand"), ("expand", "generate"),
                 ("generate", "tier1"), ("tier1", "tier2"), ("tier2", "assemble")):
        g.add_edge(a, b)
    g.add_edge("assemble", END)
    return g.compile()
