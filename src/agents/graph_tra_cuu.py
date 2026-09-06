"""Graph tra cứu (spec mục 6) — nối các node đã build thành một đồ thị chạy được.

[giai_nghia] → route → tien_de → rewrite_query → retrieve_hybrid → expand
             → generate_claims → verify_tier1 → verify_tier2 → assemble

`giai_nghia` CHỈ chạy khi `lich_su` khác rỗng (lượt hỏi nối tiếp), nên lượt đầu
của mỗi hội thoại không tốn thêm một token nào.

Ba đường rẽ tắt, tất cả đổ về `assemble`:
* `ngoai_pham_vi`/`gioi_thieu`/`soan_thao`/`hoi_ve_kho` — rẽ ngay sau `route`;
* `tien_de_sai` — phép kiểm thứ sáu, rẽ trước rewrite/retrieve;
* `cau_hoi_day_du is None` — không giải nghĩa được câu nối tiếp, rẽ ngay sau
  `giai_nghia` vào đúng đường ngõ cụt đã có.
"""

from pathlib import Path

from langgraph.graph import END, StateGraph
from sqlalchemy import Engine, text

from src.agents.nodes.assemble import assemble
from src.agents.nodes.expand import expand
from src.agents.nodes.generate_claims import generate_claims
from src.agents.nodes.giai_nghia import giai_nghia
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.route import Intent, route
from src.agents.nodes.verify_tier1 import nap_provisions, tien_de_cau_hoi_sai, verify_tier1
from src.agents.nodes.verify_tier2 import verify_tier2_and_trace
from src.agents.state import KLawState
from src.config import as_of_hieu_luc, get_settings
from src.services.db import get_engine
from src.services.effectivity import Effectivity, EffectivityVerdict
from src.services.embedding import from_settings as embedder_from_settings
from src.services.kho import dung_bang, loi_dan_bang, nap_kho, tra_loi_ve_kho, xin_dang_bang
from src.services.llm import from_settings as llm_from_settings
from src.services.llm import generate_model, judge_model, router_model
from src.services.retrieval import Retriever


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
_RE_TAT = frozenset({Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.soan_thao,
                     Intent.hoi_ve_kho})


def _re_sau_route(st: dict) -> str:
    return "assemble" if st.get("intent") in _RE_TAT else "tien_de"


def _vao_graph(st: dict) -> str:
    """Lượt ĐẦU (lịch sử rỗng) vào thẳng `route` — không tốn thêm một token nào.

    Lượt nối tiếp đi qua `giai_nghia` TRƯỚC `route`, vì routing dựa trên câu ĐÃ
    giải nghĩa: "còn model nào khác" sau một lượt `gioi_thieu` là câu hỏi về trợ
    lý, không phải một câu tra cứu — và `route` chỉ thấy được điều đó khi tham
    chiếu đã được giải.
    """
    return "giai_nghia" if st.get("lich_su") else "route"


def _re_sau_giai_nghia(st: dict) -> str:
    """Không giải nghĩa được → `assemble`, tức ĐƯỜNG NGÕ CỤT ĐÃ CÓ (`_ngo_cut` +
    `hoi_lai`: nói cái đã biết rồi hỏi lại đúng dữ kiện còn thiếu). Không dựng
    đường thứ hai cho cùng một việc.

    Rẽ đường đó cũng bỏ qua truy hồi, và đấy là nửa còn lại của giá trị: một câu
    rỗng nội dung pháp lý ("liệt kê bảng cho tôi") đi vào truy hồi thì khớp
    NHIỄU — đo được 2026-09-02: Luật Phòng chống ma túy và Luật Thương mại.
    """
    return "route" if st.get("cau_hoi_day_du") else "assemble"


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

    def n_route(st: KLawState) -> KLawState:
        return route(st, llm, router_model())

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
        return {**st, "retrieved": list(dict.fromkeys(ids))}

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
        return generate_claims(st, llm, generate_model())

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
        verdicts, traces = verify_tier2_and_trace(t1, dbp, llm, judge_model(), st.get("traces"))
        return {**st, "tier2": verdicts, "traces": traces}

    def n_assemble(st: KLawState) -> KLawState:
        if st.get("intent") == Intent.hoi_ve_kho:
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
    for name, fn in (("giai_nghia", n_giai_nghia), ("route", n_route), ("tien_de", n_tien_de),
                     ("rewrite", n_rewrite), ("retrieve", n_retrieve),
                     ("expand", n_expand), ("generate", n_generate), ("tier1", n_tier1),
                     ("tier2", n_tier2), ("assemble", n_assemble)):
        g.add_node(name, fn)

    # Nhánh vào có ĐIỀU KIỆN, không phải một node luôn chạy rồi tự bỏ qua: lượt
    # đầu của mỗi hội thoại không được ghé qua `giai_nghia` một lần nào, kể cả
    # một lần không gọi LLM (nó vẫn là một bước trong thanh tiến trình SSE nói
    # rằng có việc đã làm, trong khi không có việc nào).
    g.set_conditional_entry_point(_vao_graph)
    g.add_conditional_edges("giai_nghia", _re_sau_giai_nghia)
    g.add_conditional_edges("route", _re_sau_route)
    g.add_conditional_edges("tien_de", lambda st: (
        "assemble" if st.get("tien_de_sai") else "rewrite"))
    for a, b in (("rewrite", "retrieve"), ("retrieve", "expand"), ("expand", "generate"),
                 ("generate", "tier1"), ("tier1", "tier2"), ("tier2", "assemble")):
        g.add_edge(a, b)
    g.add_edge("assemble", END)
    return g.compile()
