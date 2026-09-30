"""Wiring contracts for the meta answer (ex.md §3.3, FR-014; decision 2026-09-30
item 1: one model call from the fact sheet, the sheet's lines as fallback)."""

import json

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.gioi_thieu import (
    TOI_DA_LINH_VUC,
    bang_du_kien,
    cau_gioi_thieu,
    chi_hoi_kho,
    khia_canh,
    khia_canh_kho,
)
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage


def _vb(so, ten, loai="Luật", depth="deep", linh_vuc=None):
    return {"so_ky_hieu": so, "ten": ten, "loai_van_ban": loai, "depth": depth,
            "hieu_luc": Effectivity(V.con_hieu_luc, "cao", "x"), "linh_vuc": linh_vuc}


def test_chi_hoi_kho_quyet_dinh_duong_cu_hay_ghep():
    assert chi_hoi_kho(khia_canh("kho có những bộ luật nào"))
    assert chi_hoi_kho(khia_canh("có bao nhiêu văn bản"))
    assert not chi_hoi_kho(khia_canh("bạn làm được gì và kho có gì"))
    assert not chi_hoi_kho(khia_canh("bạn làm được gì"))


# Trace fa18ddce (2026-09-29), typo kept as typed.
HOI_DIEU_LUAT = "có bao nhiêu điều luật , chia thành các loại naoif"


def test_cau_khong_khop_khia_canh_nao_nhan_mac_dinh_cua_chu_goi():
    """A `hoi_ve_kho` turn that names no facet must keep the kho verdict, not
    inherit the gioi_thieu default (the KLAW introduction)."""
    cau = "pháp luật việt nam có những gì"
    assert khia_canh(cau) == ["nang_luc"]
    assert khia_canh_kho(cau) == ["kho"] and chi_hoi_kho(khia_canh_kho(cau))
    # a question that addresses KLAW keeps its own facet
    assert khia_canh_kho("bạn làm được gì") == ["nang_luc"]


def test_hoi_ve_kho_chi_giu_khia_canh_ve_klaw_khi_cau_hoi_noi_voi_klaw():
    """Decision 2026-09-29 item 4: the KLAW introduction is for questions about
    KLAW itself. "là gì" / "làm gì" in a question that does not address KLAW are
    not the ban_chat / nang_luc facets of a kho turn."""
    for cau in (
        "luật pháp việt nam là gì",
        "cho em hỏi hệ thống pháp luật việt nam là gì",
        "hệ thống pháp luật việt nam hoạt động thế nào",
    ):
        assert khia_canh_kho(cau) == ["kho"], cau
    assert khia_canh_kho("bạn là gì, kho có bao nhiêu văn bản") == ["ban_chat", "kho"]
    assert khia_canh_kho("dữ liệu lấy từ đâu") == ["nguon"]


def test_dem_dieu_luat_la_khia_canh_kho():
    for cau in (HOI_DIEU_LUAT, "trong KLAW có bao nhiêu điều luật"):
        assert khia_canh(cau) == ["kho"], cau
    # "bao nhiêu điều kiện" counts conditions, not the kho
    assert "kho" not in khia_canh("cần bao nhiêu điều kiện")


class _ModelHong:
    """The meta writer failing: the reader gets the sheet's own lines."""

    def chat(self, *a, **k):
        raise RuntimeError("OpenRouter 429")


def _graph_hoi_ve_kho(monkeypatch, kho, llm=None):
    """The real graph with the router pinned to `hoi_ve_kho` and a fixture kho:
    no DB, no paid call."""
    from src.agents import graph_tra_cuu as g
    from src.agents.nodes.route import Intent

    monkeypatch.setattr(g, "get_engine", lambda: None)
    monkeypatch.setattr(g, "llm_from_settings", lambda: llm or _ModelHong())
    monkeypatch.setattr(g, "embedder_from_settings", lambda: None)
    monkeypatch.setattr(g, "Retriever", lambda *a, **k: None)
    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {**st, "intent": Intent.hoi_ve_kho})
    monkeypatch.setattr(g, "nap_kho", lambda engine, as_of: kho)
    return g.build_graph_tra_cuu()


def test_hoi_ve_kho_khong_khop_khia_canh_tra_so_lieu_kho_theo_loai(monkeypatch):
    from src.services.kho import CAU_GIOI_HAN

    kho = [
        _vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật"),
        _vb("145/2020/NĐ-CP", "Nghị định 145/2020/NĐ-CP", loai="Nghị định"),
    ]
    for cau in (HOI_DIEU_LUAT, "pháp luật việt nam có những gì"):
        st = _graph_hoi_ve_kho(monkeypatch, kho).invoke({"query": cau})
        assert st["result_type"] == ResultType.hoi_ve_kho, cau
        assert "Phân theo loại văn bản" in st["answer"], cau
        assert "- Nghị định: 1" in st["answer"] and CAU_GIOI_HAN in st["answer"], cau
        assert bang_du_kien(cau, kho)["viec"] not in st["answer"], cau
        assert st["traces"]["gioi_thieu_khia_canh"] == ["kho"], cau


def test_hoi_ve_kho_khong_noi_voi_klaw_khong_nhan_bai_gioi_thieu(monkeypatch):
    """The router's observed verdict for a legal-system question is `hoi_ve_kho`.
    When the route guard misses it, "là gì" must not bring back the nature lines."""
    kho = [_vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật")]
    for cau in ("luật pháp việt nam là gì", "cho em hỏi hệ thống pháp luật việt nam là gì"):
        bang = bang_du_kien(cau, kho)
        st = _graph_hoi_ve_kho(monkeypatch, kho).invoke({"query": cau})
        assert st["result_type"] == ResultType.hoi_ve_kho, cau
        assert "Phân theo loại văn bản" in st["answer"], cau
        assert bang["ban_chat"] not in st["answer"] and bang["viec"] not in st["answer"], cau


def test_hoi_ve_kho_noi_voi_klaw_van_ghep_khia_canh_klaw(monkeypatch):
    kho = [_vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật")]
    cau = "bạn là gì, kho có bao nhiêu văn bản"
    st = _graph_hoi_ve_kho(monkeypatch, kho).invoke({"query": cau})
    assert st["result_type"] == ResultType.hoi_ve_kho
    assert bang_du_kien(cau, kho)["ban_chat"] in st["answer"] and "Phân theo loại văn bản" in st["answer"]


class _VietLai:
    def __init__(self):
        self.prompts = []

    def chat(self, model, messages, json_schema=None):
        self.prompts.append(messages[-1]["content"])
        return json.dumps({"tra_loi": "Tôi đọc được 1 văn bản pháp luật Việt Nam."}), Usage(9, 3, 0.0)


def test_graph_dua_bang_co_so_lieu_that_cho_model(monkeypatch):
    """The node loads the kho once and hands the sheet to the one model call; the
    model's sentence survives because the sheet carries the count."""
    kho = [_vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật")]
    llm = _VietLai()
    st = _graph_hoi_ve_kho(monkeypatch, kho, llm).invoke({"query": "kho có bao nhiêu văn bản"})
    assert len(llm.prompts) == 1 and bang_du_kien("kho có bao nhiêu văn bản", kho)["kho"] in llm.prompts[0]
    assert st["answer"].startswith("Tôi đọc được 1 văn bản pháp luật Việt Nam.")
    assert st["traces"]["assemble_token_in"] == 9 and st["traces"]["gioi_thieu_nguon"] == "llm"


def test_assemble_dung_bang_do_graph_dung_san():
    bang = {**bang_du_kien("bạn làm được gì", None), "viec": "- Tra cứu pháp luật GHÉP SẴN."}
    st = assemble({"query": "bạn làm được gì", "intent": "gioi_thieu", "bang_du_kien": bang,
                   "khia_canh_meta": ["nang_luc"]}, {}, None, "")
    assert st["result_type"] == ResultType.gioi_thieu and "GHÉP SẴN" in st["answer"]
    # Without the prepared sheet the kho-less answer still comes back.
    st2 = assemble({"query": "bạn làm được gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st2["answer"] and "tra cứu" in st2["answer"].lower()


def test_linh_vuc_qua_nhieu_thi_nem_sau_ten_va_dem_phan_con_lai():
    """Real corpus has 55 MOJ labels: name the six largest, count the rest."""
    kho = [_vb(f"{i}/2020/QH14", f"Luật {i}", linh_vuc=f"Lĩnh vực {i:02d}") for i in range(9)]
    kho += [_vb("99/2020/QH14", "Luật lớn", linh_vuc="Lĩnh vực 00")]  # 2 docs → sorted first
    ans = cau_gioi_thieu("kho có những lĩnh vực nào và bạn làm được gì", kho=kho)
    assert ans.count("Lĩnh vực ") == TOI_DA_LINH_VUC
    assert "Lĩnh vực 00" in ans and "và 3 lĩnh vực khác" in ans
    kho_it = kho[:3]
    assert "lĩnh vực khác" not in cau_gioi_thieu("kho có những lĩnh vực nào và bạn là ai", kho=kho_it)
