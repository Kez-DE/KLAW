"""Graph tra cứu (spec mục 6) — nối chín node đã build (Task 1-9) thành một
đồ thị chạy được.

route → rewrite_query → retrieve_hybrid → expand → generate_claims
      → verify_tier1 → verify_tier2 → assemble

`ngoai_pham_vi` rẽ thẳng từ route sang assemble (0 token cho mọi bước sau).
"""

from datetime import date

from langgraph.graph import END, StateGraph
from sqlalchemy import Engine, text

from src.agents.nodes.assemble import assemble
from src.agents.nodes.expand import expand
from src.agents.nodes.generate_claims import generate_claims
from src.agents.nodes.rewrite_query import rewrite_query
from src.agents.nodes.route import Intent, route
from src.agents.nodes.verify_tier1 import nap_provisions, verify_tier1
from src.agents.nodes.verify_tier2 import verify_tier2_and_trace
from src.agents.state import KLawState
from src.config import get_settings
from src.services.db import get_engine
from src.services.effectivity import Effectivity, EffectivityVerdict
from src.services.embedding import from_settings as embedder_from_settings
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
            r["id"]: {"so_ky_hieu": r["so_ky_hieu"], "ten": r["ten"]}
            for r in c.execute(
                text("SELECT id, so_ky_hieu, ten FROM documents WHERE id = ANY(:ids)"),
                {"ids": list(doc_ids)},
            ).mappings().all()
        }
    return {pid: {**row, **docs.get(row["document_id"], {})} for pid, row in goc.items()}


def build_graph_tra_cuu():
    s = get_settings()
    llm = llm_from_settings()
    engine = get_engine()
    retriever = Retriever(engine, embedder_from_settings(), s)

    def n_route(st: KLawState) -> KLawState:
        return route(st, llm, router_model())

    def n_rewrite(st: KLawState) -> KLawState:
        return rewrite_query(st, llm, router_model())

    def n_retrieve(st: KLawState) -> KLawState:
        ids: list[int] = []
        for q in st.get("queries") or [st["query"]]:
            ids += retriever.provision_ids(retriever.hybrid(q))
        return {**st, "retrieved": list(dict.fromkeys(ids))}

    def n_expand(st: KLawState) -> KLawState:
        as_of = st.get("as_of_date") or s.as_of_date or date.today()
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
        mac_dinh = Effectivity(EffectivityVerdict.con_hieu_luc, "thap",
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
        ids = [r.claim.provision_id for r in (st.get("tier1") or [])]
        return assemble({**st, "abstain_threshold": s.abstain_threshold},
                        _db_provisions(ids, engine), llm, generate_model())

    g = StateGraph(KLawState)
    for name, fn in (("route", n_route), ("rewrite", n_rewrite), ("retrieve", n_retrieve),
                     ("expand", n_expand), ("generate", n_generate), ("tier1", n_tier1),
                     ("tier2", n_tier2), ("assemble", n_assemble)):
        g.add_node(name, fn)

    g.set_entry_point("route")
    g.add_conditional_edges("route", lambda st: (
        "assemble" if st.get("intent") == Intent.ngoai_pham_vi else "rewrite"))
    for a, b in (("rewrite", "retrieve"), ("retrieve", "expand"), ("expand", "generate"),
                 ("generate", "tier1"), ("tier1", "tier2"), ("tier2", "assemble")):
        g.add_edge(a, b)
    g.add_edge("assemble", END)
    return g.compile()
