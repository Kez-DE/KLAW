"""Wiring contracts for the composed meta answer (ex.md §3.3, FR-014)."""

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.gioi_thieu import TOI_DA_LINH_VUC, cau_gioi_thieu, chi_hoi_kho, khia_canh
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
