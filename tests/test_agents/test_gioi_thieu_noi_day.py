"""Wiring contracts for the composed meta answer (ex.md §3.3, FR-014)."""

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.gioi_thieu import TOI_DA_LINH_VUC, cau_gioi_thieu, chi_hoi_kho, khia_canh, khia_canh_kho
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V


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


def _graph_hoi_ve_kho(monkeypatch, kho):
    """The real graph with the router pinned to `hoi_ve_kho` and a fixture kho:
    no DB, no model call."""
    from src.agents import graph_tra_cuu as g
    from src.agents.nodes.route import Intent
    from src.services.kho import dung_cau_tra_loi

    class KhongGoi:
        def chat(self, *a, **k):
            raise AssertionError("a meta turn makes no model call")

    monkeypatch.setattr(g, "get_engine", lambda: None)
    monkeypatch.setattr(g, "llm_from_settings", lambda: KhongGoi())
    monkeypatch.setattr(g, "embedder_from_settings", lambda: None)
    monkeypatch.setattr(g, "Retriever", lambda *a, **k: None)
    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {**st, "intent": Intent.hoi_ve_kho})
    monkeypatch.setattr(g, "nap_kho", lambda engine, as_of: kho)
    monkeypatch.setattr(g, "tra_loi_ve_kho", lambda engine, cau, as_of: dung_cau_tra_loi(cau, kho))
    return g.build_graph_tra_cuu()


def test_hoi_ve_kho_khong_khop_khia_canh_tra_so_lieu_kho_theo_loai(monkeypatch):
    from src.agents.nodes.gioi_thieu import NANG_LUC
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
        assert NANG_LUC not in st["answer"], cau
        assert st["traces"]["assemble_token_in"] == 0


def test_hoi_ve_kho_khong_noi_voi_klaw_khong_nhan_bai_gioi_thieu(monkeypatch):
    """The router's observed verdict for a legal-system question is `hoi_ve_kho`.
    When the route guard misses it, "là gì" must not bring back BAN_CHAT."""
    from src.agents.nodes.gioi_thieu import BAN_CHAT, NANG_LUC

    kho = [_vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật")]
    for cau in ("luật pháp việt nam là gì", "cho em hỏi hệ thống pháp luật việt nam là gì"):
        st = _graph_hoi_ve_kho(monkeypatch, kho).invoke({"query": cau})
        assert st["result_type"] == ResultType.hoi_ve_kho, cau
        assert "Phân theo loại văn bản" in st["answer"], cau
        assert BAN_CHAT not in st["answer"] and NANG_LUC not in st["answer"], cau


def test_hoi_ve_kho_noi_voi_klaw_van_ghep_khia_canh_klaw(monkeypatch):
    from src.agents.nodes.gioi_thieu import BAN_CHAT

    kho = [_vb("45/2019/QH14", "Bộ luật Lao động", loai="Bộ luật")]
    st = _graph_hoi_ve_kho(monkeypatch, kho).invoke({"query": "bạn là gì, kho có bao nhiêu văn bản"})
    assert st["result_type"] == ResultType.hoi_ve_kho
    assert BAN_CHAT in st["answer"] and "Phân theo loại văn bản" in st["answer"]


def test_assemble_uu_tien_cau_tra_loi_da_ghep_o_graph():
    st = assemble({"query": "bạn làm được gì, có bộ luật gì", "intent": "gioi_thieu",
                   "tra_loi_gioi_thieu": "GHÉP SẴN"}, {}, None, "")
    assert st["result_type"] == ResultType.gioi_thieu and st["answer"] == "GHÉP SẴN"
    assert st["traces"]["assemble_token_in"] == 0
    # Without the composed text the kho-less answer still comes back.
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
