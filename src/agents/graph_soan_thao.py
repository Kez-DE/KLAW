"""Graph soạn thảo (Task 5) — collect → retrieve_requirements → draft_generate
→ draft_audit.

`retrieve_requirements` tra CHÍNH XÁC các provision theo `duong_dan` mà
checklist (Task 3) + rules (Task 2) đã dẫn — KHÔNG retrieval ngữ nghĩa, vì căn
cứ pháp lý của một HĐLĐ đã biết trước (Điều 21 BLLĐ, Điều 25/26/127/17...),
khác hẳn graph tra cứu (`graph_tra_cuu.py`) nơi câu hỏi tự do cần truy hồi.

Một loại văn bản = MỘT file `config/checklist_<loai>.yaml`. `cac_loai()` suy
tập loại được hỗ trợ THẲNG từ những file đang có trên đĩa — không một danh sách
viết tay nào trong Python có thể lệch khỏi sự thật, và thêm một mẫu soạn thảo
là thêm một file YAML. Một `loai` không có file phải bị từ chối trung thực
(501) thay vì áp nhầm checklist của loại khác lên nó: một audit report trông
hợp lệ nhưng soát sai loại văn bản tệ hơn hẳn việc không soát.
"""

import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import Engine, text

from src.agents.nodes.draft_audit import draft_audit
from src.agents.nodes.draft_generate import DraftClause, draft_generate
from src.agents.nodes.verify_tier1 import normalize
from src.config import as_of_hieu_luc
from src.services.checklist import Checklist, cac_can_cu, load_checklist
from src.services.db import get_engine
from src.services.effectivity import danh_gia_theo_id
from src.services.hien_thi import hien_thi_luc
from src.services.llm import from_settings as llm_from_settings
from src.services.llm import generate_model
from src.services.rules import Rule, load_facts_meta, load_rules
from src.services.trich_dan import khoi_can_cu_co_id

RULES_PATH = Path("config/rules.yaml")
CONFIG_DIR = Path("config")
_TIEN_TO_CHECKLIST = "checklist_"


def cac_loai() -> frozenset[str]:
    """Tập `loai` được hỗ trợ — suy từ `config/checklist_*.yaml` đang có, KHÔNG
    một danh sách viết tay nào. Cũng là hàng rào duy nhất giữa một chuỗi từ
    HTTP và một đường dẫn file: `duong_dan_checklist` chỉ dựng path sau khi
    `loai` đã được đối chiếu với tập này, nên không có `../` nào đi xa được.
    """
    return frozenset(p.stem[len(_TIEN_TO_CHECKLIST):] for p in CONFIG_DIR.glob(f"{_TIEN_TO_CHECKLIST}*.yaml"))


def duong_dan_checklist(loai: str) -> Path:
    if loai not in cac_loai():
        raise ValueError(f"loai không có checklist: {loai!r} (có: {sorted(cac_loai())})")
    return CONFIG_DIR / f"{_TIEN_TO_CHECKLIST}{loai}.yaml"


class SoanThaoState(TypedDict, total=False):
    # `loai` là MÃ enum ("hdld"), `loai_van_ban` là NHÃN tiếng Việt tự nhiên
    # ("hợp đồng lao động") mà n_collect đặt vào cho prompt draft_generate. Hai
    # khoá tách bạch vì n_collect ghi đè `loai_van_ban`, nên các node sau nó
    # không còn cách nào biết mã enum để tra đúng checklist/rules.
    loai: str
    loai_van_ban: str
    facts: dict
    nganh: str
    muc: list[dict]
    expanded: list[dict]
    db_provisions: dict[int, dict]
    # Khối "Căn cứ" của bản thảo (quyết định 2026-09-28) — `n_retrieve` dựng,
    # `ban_thao.tu_state_soan_thao` đặt vào `document`. Không vào prompt nào.
    can_cu_van_ban: list[str]
    # Cùng khối, mỗi dòng kèm `doc_id` (`can_cu_van_ban_co_id`) — khuôn mẫu cần để
    # trang bản thảo mở được văn bản của từng dòng (`ban_thao.dat_khuon_mau`).
    can_cu_co_id: list[dict]
    clauses: list[DraftClause]
    schema_error: bool
    usage_generate: object
    self_audit: bool
    audit_report: object
    # BẮT BUỘC khai báo: LangGraph LỌC key không có trong schema state, nên
    # thiếu dòng này thì `traces` do `n_generate` đặt bị vứt im lặng và
    # `_ghi_traces` lại ghi $0 như trước.
    traces: dict


# ── Nạp rules/checklist + tra sẵn provision chúng cần — MỘT LẦN cho cả tiến
# trình (lru_cache), dùng chung bởi lifespan (kiểm can_cu lúc boot),
# build_graph_soan_thao() (/soan-thao), và route /soat (gọi draft_audit trực
# tiếp, không qua graph, vì không có bước sinh văn bản). ─────────────────────

_SQL_PROVISIONS_BY_DUONG_DAN = text(
    "SELECT id, document_id, duong_dan, tieu_de, noi_dung FROM provisions WHERE duong_dan = ANY(:paths)"
)
_SQL_DOCUMENTS_BY_ID = text("SELECT id, so_ky_hieu, ten FROM documents WHERE id = ANY(:ids)")
# Riêng cho khối "Căn cứ", KHÔNG gộp vào `_SQL_DOCUMENTS_BY_ID`: dòng của câu
# trên đi vào `build_context` của `draft_generate`, và thêm `loai_van_ban` vào
# đó là đổi prompt của mô hình (nó in `loai_van_ban` khi có).
_SQL_VAN_BAN_CAN_CU = text(
    "SELECT id, so_ky_hieu, ten, loai_van_ban, ngay_ban_hanh, co_quan_ban_hanh FROM documents WHERE id = ANY(:ids)"
)


@lru_cache
def load_rules_cached() -> list[Rule]:
    """MỌI rule trong config/rules.yaml — thư viện đầy đủ, chưa lọc theo loại
    văn bản. Chỉ đọc YAML, KHÔNG chạm DB, để validate facts ở biên HTTP (ràng
    buộc #1) và GET /api/v1/mau/{loai} (ràng buộc #4) không kéo theo một
    round-trip Postgres không cần thiết. Người gọi theo loại dùng `rules_cho`.
    """
    return load_rules(RULES_PATH)


@lru_cache
def load_checklist_cached(loai: str) -> Checklist:
    cl = load_checklist(duong_dan_checklist(loai))
    if cl.loai != loai:
        raise ValueError(f"checklist_{loai}.yaml khai `loai: {cl.loai}` — tên file và nội dung phải khớp")
    return cl


def rules_cho(loai: str) -> list[Rule]:
    """Rule áp dụng cho `loai`, theo danh sách id mà checklist của nó khai báo.

    Một id không có trong rules.yaml là LỖI NẠP, không phải một rule bị bỏ qua
    im lặng: checklist khai "văn bản này phải chịu rule X" mà X không tồn tại
    nghĩa là một phép kiểm người viết TIN là đang chạy thì thực ra không —
    cùng hạng lỗi với một `can_cu` trỏ vào điều luật không có thật.
    """
    theo_id = {r.id: r for r in load_rules_cached()}
    khai_bao = load_checklist_cached(loai).rules
    thieu = sorted(set(khai_bao) - set(theo_id))
    if thieu:
        raise ValueError(f"checklist_{loai}.yaml khai rule không có trong {RULES_PATH}: {thieu}")
    return [theo_id[i] for i in khai_bao]


@lru_cache
def load_facts_meta_cached() -> dict[str, dict[str, str]]:
    return load_facts_meta(RULES_PATH)


def _requirement_provisions(engine: Engine, duong_dan: set[str]) -> dict[int, dict]:
    """`provisions.id` -> dòng (kèm `so_ky_hieu`/`ten` văn bản), cho MỌI
    `can_cu` mà checklist + rules đã dẫn. Đây là toàn bộ "văn bản nguồn" đưa
    vào prompt `draft_generate` (qua `build_context`, cùng hàm graph tra cứu
    dùng) VÀ là tập đích hợp lệ cho phép kiểm citation của `draft_audit` —
    một `can_cu_provision_id` mà draft_generate trả về chỉ hợp lệ nếu nó nằm
    trong đúng tập điều luật đã được cho xem, cùng nguyên tắc phép kiểm 2 của
    verify_tier1.
    """
    if not duong_dan:
        return {}
    with engine.connect() as c:
        rows = c.execute(_SQL_PROVISIONS_BY_DUONG_DAN, {"paths": list(duong_dan)}).mappings().all()
    doc_ids = {r["document_id"] for r in rows}
    with engine.connect() as c:
        docs = {r["id"]: {"so_ky_hieu": r["so_ky_hieu"], "ten": r["ten"]}
                for r in c.execute(_SQL_DOCUMENTS_BY_ID, {"ids": list(doc_ids)}).mappings().all()}
    return {r["id"]: {**dict(r), **docs.get(r["document_id"], {})} for r in rows}


def load_requirements(engine: Engine, loai: str) -> tuple[list[Rule], Checklist, dict[int, dict]]:
    rules = rules_cho(loai)
    checklist = load_checklist_cached(loai)
    can_cu_all = cac_can_cu(checklist) | {r.can_cu for r in rules}
    return rules, checklist, _requirement_provisions(engine, can_cu_all)


@lru_cache
def requirements(loai: str) -> tuple[list[Rule], Checklist, dict[int, dict]]:
    return load_requirements(get_engine(), loai)


class KhongSoanDuocError(ValueError):
    """Căn cứ gốc của checklist thuộc văn bản ẩn: dừng TRƯỚC lượt LLM trả phí.
    `ValueError` để các cửa đã bắt lời từ chối soạn (`dung_lai`, nhánh sửa của
    chat) nhận luôn câu này; câu là lời thường cho người đọc, không số hiệu."""


def chi_van_ban_hien(db_provisions: dict[int, dict], hien: frozenset[str]) -> dict[int, dict]:
    """Điều khoản của văn bản được HIỆN (`services/hien_thi`, quyết định
    2026-09-28 mục 8). Lọc ở đây, không trong `requirements` (lru_cache cả tiến
    trình): tập được hiện đổi theo ngày và theo lần nạp link, tập điều khoản thì không."""
    return {pid: r for pid, r in db_provisions.items() if r["document_id"] in hien}


def can_cu_van_ban_co_id(engine: Engine, db_provisions: dict[int, dict], as_of: date) -> list[dict]:
    """Khối "Căn cứ" `[{dong, doc_id}]` từ các văn bản mà `can_cu` của checklist +
    rules dẫn tới — chỉ văn bản được HIỆN (tình trạng, hiệu lực, link chính thống —
    cùng tập mọi đường đọc dùng) và còn hiệu lực TẠI `as_of`, phán bằng
    `danh_gia_theo_id`, đúng hàm mà câu trả lời dùng (`effectivity_qua_provision`).
    `doc_id` để trang bản thảo mở được văn bản của từng dòng (khuôn mẫu, §5). KHÔNG
    `lru_cache` như `requirements`: hiệu lực đổi theo ngày, còn tập điều khoản thì không."""
    ids = sorted({r["document_id"] for r in chi_van_ban_hien(db_provisions, hien_thi_luc(engine, as_of)).values()})
    if not ids:
        return []
    with engine.connect() as c:
        van_ban = [dict(r) for r in c.execute(_SQL_VAN_BAN_CAN_CU, {"ids": ids}).mappings().all()]
    return khoi_can_cu_co_id(van_ban, lambda i: danh_gia_theo_id(engine, i, as_of).verdict)


def can_cu_van_ban(engine: Engine, db_provisions: dict[int, dict], as_of: date) -> list[str]:
    """Các dòng của `can_cu_van_ban_co_id`."""
    return [x["dong"] for x in can_cu_van_ban_co_id(engine, db_provisions, as_of)]


_SQL_VAN_BAN_THEO_SO = text(
    "SELECT id, so_ky_hieu, ten, loai_van_ban, ngay_ban_hanh, co_quan_ban_hanh FROM documents"
    " WHERE so_ky_hieu = ANY(:so) AND id = ANY(CAST(:hien AS text[]))"
)


def can_cu_theo_so_hieu(engine: Engine, so_hieu: list[str], as_of: date) -> list[dict]:
    """Căn cứ mà một bản thảo TỔNG QUÁT nêu bằng số hiệu (khuôn mẫu, §2) → `[{dong,
    doc_id}]` qua CÙNG bộ lọc hiện/hiệu lực của `can_cu_van_ban_co_id`. Số hiệu
    không có trong kho, văn bản ẩn hay hết hiệu lực không in gì — không bao giờ một
    dòng căn cứ thiếu số."""
    so = list(dict.fromkeys(s.strip() for s in so_hieu if isinstance(s, str) and s.strip()))[:8]
    if not so:
        return []
    hien = sorted(hien_thi_luc(engine, as_of))
    with engine.connect() as c:
        van_ban = [dict(r) for r in c.execute(_SQL_VAN_BAN_THEO_SO, {"so": so, "hien": hien}).mappings().all()]
    return khoi_can_cu_co_id(van_ban, lambda i: danh_gia_theo_id(engine, i, as_of).verdict)


# ── /soan-thao — graph 4 node ────────────────────────────────────────────────


def build_graph_soan_thao():
    """Graph dùng CHUNG cho mọi loại văn bản. Checklist/rules/provision được tra
    theo `st["loai"]` TRONG node, không bắt sẵn lúc build: một graph bắt sẵn
    checklist HĐLĐ sẽ soạn mọi loại văn bản bằng checklist HĐLĐ, và `_graph_soan_thao`
    là một global dựng một lần cho cả tiến trình. `requirements` có lru_cache
    nên tra trong node vẫn là một lần cho mỗi loại.
    """
    llm = llm_from_settings()

    def n_collect(st: SoanThaoState) -> SoanThaoState:
        checklist = load_checklist_cached(st["loai"])
        return {
            **st,
            "muc": checklist.muc,
            "nganh": st.get("nganh") or "thuong_mai",
            "loai_van_ban": checklist.ten,
        }

    def n_retrieve(st: SoanThaoState) -> SoanThaoState:
        # Mốc hiệu lực của bản thảo: bản thảo không có `as_of` riêng, nên theo
        # đúng quy tắc của request tra cứu (settings → hôm nay). Chỉ điều khoản
        # của văn bản được hiện vào nguồn soạn: một căn cứ người đọc không mở
        # được thì không được là căn cứ của bản thảo.
        as_of = as_of_hieu_luc(None)
        _, checklist, tat_ca = requirements(st["loai"])
        db_provisions = chi_van_ban_hien(tat_ca, hien_thi_luc(get_engine(), as_of))
        # Căn cứ gốc (điều luật buộc các mục phải có) bị ẩn thì bản thảo không
        # có căn cứ nào người đọc mở được — đo 2026-09-28: 7/29 mẫu mất trọn
        # nguồn, `thoa_thuan_bao_mat` mất căn cứ gốc. Dừng ở đây, 0 lượt LLM.
        if not any(r["duong_dan"] == checklist.can_cu_goc for r in db_provisions.values()):
            raise KhongSoanDuocError(
                f"Hiện chưa soạn được {checklist.ten}: văn bản luật làm căn cứ cho loại văn bản này"
                " chưa có trong phạm vi tra cứu."
            )
        can_cu = can_cu_van_ban_co_id(get_engine(), db_provisions, as_of)
        return {
            **st,
            "expanded": list(db_provisions.values()),
            "db_provisions": db_provisions,
            "can_cu_van_ban": [x["dong"] for x in can_cu],
            "can_cu_co_id": can_cu,
        }

    def n_generate(st: SoanThaoState) -> SoanThaoState:
        """Nối usage của lượt LLM này vào `state["traces"]` — chỗ DUY NHẤT mà
        `_tong_hop_traces` biết đọc.

        `draft_generate` trả usage ở `state["usage_generate"]` (một `Usage`),
        KHÔNG vào `state["traces"]`, nên `traces.cost_usd` của mọi request
        `/soan-thao` là 0 — đo được trên DB: 32/32 dòng `/api/v1/soan-thao`
        đang là $0,00000 dù mỗi request tốn một lượt LLM thật. Trần chi phí ngày
        (Plan 4) đọc CHÍNH cột đó, nên không có ba khoá dưới đây thì trần KHÔNG
        THẤY một trong hai endpoint tiêu tiền. Nối tại đây chứ không sửa
        `draft_generate`: node đó đã được test, và `usage_generate` vẫn là
        hình dạng state mà nơi khác đọc.
        """
        moi = draft_generate(st, llm, generate_model())
        u = moi.get("usage_generate")
        if u is None:  # lượt LLM không chạy → không có gì để cộng (không phải 0 bịa ra)
            return moi
        return {**moi, "traces": {
            **(st.get("traces") or {}),
            "draft_generate_token_in": u.token_in,
            "draft_generate_token_out": u.token_out,
            "draft_generate_cost_usd": u.cost_usd,
        }}

    def n_audit(st: SoanThaoState) -> SoanThaoState:
        rules, checklist, _ = requirements(st["loai"])
        return draft_audit(st, rules, checklist, st.get("db_provisions") or {})

    g = StateGraph(SoanThaoState)
    g.add_node("collect", n_collect)
    g.add_node("retrieve_requirements", n_retrieve)
    g.add_node("draft_generate", n_generate)
    g.add_node("draft_audit", n_audit)
    g.set_entry_point("collect")
    g.add_edge("collect", "retrieve_requirements")
    g.add_edge("retrieve_requirements", "draft_generate")
    g.add_edge("draft_generate", "draft_audit")
    g.add_edge("draft_audit", END)
    return g.compile()


@lru_cache
def graph_soan_thao_cached():
    """Bản ĐÃ COMPILE, dựng MỘT LẦN cho cả tiến trình — dùng bởi node
    `dung_ban_thao` (Task 19, soạn thảo trong chat) để không dựng lại graph mỗi
    lượt hội thoại, cùng lý do `_g_soan_thao()` của `routes.py` (`/soan-thao`)
    giữ nó ở một biến global thay vì gọi `build_graph_soan_thao()` mỗi request."""
    return build_graph_soan_thao()


# ── /soat — tách clause từ text dán vào, KHÔNG gọi LLM ──────────────────────

@lru_cache
def _re_dau_muc(don_vi: str) -> re.Pattern[str]:
    """Dòng mở đầu một mục: "Điều 3." / "Mục 3." / "## Điều 3.".

    `#*` KHÔNG thừa: `_render_markdown` sinh tiêu đề mục dưới dạng "## Điều N."
    nên nếu không nhận tiền tố Markdown thì soạn ra rồi dán lại vào `POST /soat`
    tách được ĐÚNG MỘT khối cho cả văn bản — completeness sập về gần 0 trên
    chính văn bản hệ thống vừa chấm 1.0. Đường soạn-rồi-soát là đường người dùng
    đi nhiều nhất, và trước bản này nó hỏng im lặng.
    """
    return re.compile(rf"(?m)^[ \t]*#*[ \t]*{re.escape(don_vi)}\s+\d+\.")


def _split_dieu(van_ban: str, don_vi: str = "Điều") -> list[str]:
    """Cắt `van_ban` theo từng dòng mở đầu một mục — giữ nguyên tiêu đề trong
    cùng khối với thân mục, vì tiêu đề thường mang từ khoá cần cho việc map
    `key` bên dưới (vd. "Điều 1. Công việc..." → khớp "công việc").
    """
    diem_bat_dau = [m.start() for m in _re_dau_muc(don_vi).finditer(van_ban)]
    if not diem_bat_dau:
        return [van_ban.strip()] if van_ban.strip() else []
    diem_bat_dau.append(len(van_ban))
    return [
        van_ban[a:b].strip()
        for a, b in zip(diem_bat_dau, diem_bat_dau[1:])
        if van_ban[a:b].strip()
    ]


def extract_clauses(van_ban: str, checklist: Checklist, db_provisions: dict[int, dict]) -> list[DraftClause]:
    """Tách `van_ban` (văn bản người dùng dán vào) thành `DraftClause`, map
    `key` bằng từ khoá (`checklist.muc[*].tu_khoa`, YAML — KHÔNG hardcode
    trong Python, cùng nguyên tắc rules.yaml). Không khớp được từ khoá nào
    thì `key=None` — `check_completeness` coi mục đó là THIẾU, đúng hành vi
    mong muốn (task-5-brief.md), không phải lỗi.

    `can_cu_provision_id`: người dùng dán văn bản thô, không tự đánh số
    provision_id nào — không có gì để phép kiểm 4 của `draft_audit` xác minh.
    Gán căn cứ TỔNG của checklist (`can_cu_goc`, BLLĐ Điều 21 Khoản 1 — điều
    luật buộc các mục này phải có mặt) cho MỌI clause: đây là một khẳng định
    THẬT ("mục này thuộc phạm vi Điều 21.1"), không phải trích dẫn bịa, nên
    phép kiểm citation không bao giờ báo sai cho một hợp đồng viết tay không
    tự trích dẫn provision — phép kiểm đó tồn tại để bắt MÔ HÌNH bịa trích
    dẫn (draft_generate), không phải để đòi người dùng tự đánh số điều luật.
    """
    can_cu_provision_id = next(
        (pid for pid, row in db_provisions.items() if row["duong_dan"] == checklist.can_cu_goc), 0
    )
    # Chuẩn hoá từ khoá MỘT LẦN, không mỗi chunk một lần.
    ung_vien = [
        (m["key"], m["ten"], [normalize(tk).lower() for tk in (m.get("tu_khoa") or [])])
        for m in checklist.muc
    ]

    clauses: list[DraftClause] = []
    for chunk in _split_dieu(van_ban, checklist.don_vi_muc):
        dong_tieu_de = chunk.splitlines()[0]
        key, ten = None, dong_tieu_de[:80]
        # DÒNG TIÊU ĐỀ TRƯỚC, thân điều sau. Tiêu đề là lời tự khai của người
        # soạn về chủ đề của điều khoản; thân điều nhắc tới nhiều chủ đề khác
        # nhân thể. Đo được: một điều "Điều kiện chấm dứt hợp tác" có thân nhắc
        # "hết thời hạn hợp tác" từng bị gán cho mục "Mục đích, thời hạn hợp
        # tác" — mục chấm dứt báo thiếu trong khi nó là chính điều vừa bị cướp.
        # Chỉ khi KHÔNG mục nào khớp tiêu đề mới đọc tới thân, nên văn bản
        # không có tiêu đề vẫn khớp đúng như trước.
        for nguon in (dong_tieu_de, chunk):
            chuan_hoa = normalize(nguon).lower()
            # KHỚP DÀI NHẤT thắng, KHÔNG phải mục đứng trước trong checklist.
            # Từ khoá của các mục chồng nhau theo kiểu bao hàm là chuyện bình
            # thường, không phải lỗi soạn checklist: tiêu đề "Mục đích sử dụng
            # tài sản vay" chứa cả "mục đích sử dụng" (mục 6) lẫn "tài sản vay"
            # (mục 1), và cụm DÀI HƠN là cụm nói đúng chủ đề của điều khoản.
            # Ưu tiên theo thứ tự sẽ luôn trao nó cho mục 1 và buộc người viết
            # checklist phải cố tình làm què từ khoá của mình để né.
            khop = [
                (len(tk), muc_key, muc_ten)
                for muc_key, muc_ten, tu_khoa in ung_vien
                for tk in tu_khoa
                if tk in chuan_hoa
            ]
            if khop:
                _, key, ten = max(khop, key=lambda x: x[0])
                break
        # ponytail: key=None hợp lệ tại runtime dù type hint DraftClause.key
        # là `str` (dataclass thường không ép kiểu) — đúng ý brief "không map
        # được thì để None". Nâng cấp nếu DraftClause đổi sang pydantic dataclass.
        clauses.append(DraftClause(key=key, ten=ten, noi_dung=chunk, can_cu_provision_id=can_cu_provision_id))
    return clauses
