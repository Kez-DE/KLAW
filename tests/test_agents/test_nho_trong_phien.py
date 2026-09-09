"""Bộ nhớ vào node đúng chỗ và đúng vai (dữ liệu, không phải căn cứ) — spec 2026-09-09 §6.3."""

import json

from src.agents.nodes import assemble as as_mod
from src.agents.nodes import generate_claims, giai_nghia, hoi_lai, rewrite_query
from src.services.llm import Usage


class LlmGia:
    def __init__(self, tra: dict):
        self.tra, self.da_goi = tra, []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append(messages)
        return json.dumps(self.tra, ensure_ascii=False), Usage(token_in=1, token_out=1, cost_usd=0.0)


HO_SO = {
    "chu_the": {"gia_tri": "người lao động", "nguon": "suy_dien"},
    "loai_hop_dong": {"gia_tri": "không xác định thời hạn", "nguon": "nguoi_noi"},
}
LICH_SU = [{"cau_hoi": "a", "tra_loi": "b", "duong_dan": []}]


def test_ngu_canh_gom_tom_tat_va_dinh_danh_bia_doi_chieu_ca_tom_tat():
    khoi = giai_nghia.ngu_canh(LICH_SU, tom_tat="Trước đó đã bàn về việc nghỉ.")
    assert khoi.startswith("Tóm tắt các lượt trước: Trước đó đã bàn về việc nghỉ.")
    # Điều 35 nằm trong tóm tắt → không bị coi là bịa khi câu giải nghĩa nhắc lại.
    assert (
        giai_nghia.dinh_danh_bia(
            "báo trước theo Điều 35 thế nào", "báo trước thế nào", LICH_SU, tom_tat="đã bàn Điều 35"
        )
        == []
    )
    assert giai_nghia.dinh_danh_bia("báo trước theo Điều 35 thế nào", "báo trước thế nào", LICH_SU) == ["Điều 35"]


def test_hoi_lai_bo_chieu_da_biet():
    llm = LlmGia(
        {"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}, {"ma": "tham_nien", "cau": "Bạn làm bao lâu rồi?"}]}
    )
    ket = hoi_lai.hoi_lai("tôi bị trừ lương", llm, "m", da_biet=frozenset({"chu_the"}))
    assert "Bạn làm bao lâu rồi?" in ket.cau and "phía nào" not in ket.cau
    prompt = llm.da_goi[0][-1]["content"]
    assert "`chu_the`" not in prompt and "`tham_nien`" in prompt
    # So với chính hằng số, không chép lại câu chữ (Task 14 đổi lời `chu_the`):
    # sửa câu chữ ở `CHIEU` không làm test này đỏ oan.
    assert hoi_lai.CHIEU["chu_the"] not in hoi_lai.dung_cau_hoi_lai([], da_biet=frozenset({"chu_the"}))
    assert hoi_lai.dung_cau_hoi_lai([], da_biet=frozenset(hoi_lai.CHIEU)) == ""


def test_generate_va_rewrite_nhan_khoi_tinh_huong():
    st = {
        "query": "báo trước bao nhiêu ngày",
        "ho_so": HO_SO,
        "expanded": [
            {
                "id": 1,
                "document_id": "d",
                "so_ky_hieu": "45/2019/QH14",
                "loai_van_ban": "Bộ luật",
                "duong_dan": "45/2019/QH14 > Điều 35",
                "noi_dung": "x",
                "hieu_luc": "con_hieu_luc",
            }
        ],
    }
    llm = LlmGia({"claims": [], "insufficient_evidence": True})
    generate_claims.generate_claims(st, llm, "m")
    assert "Vai của bạn: người lao động (tôi đoán)" in llm.da_goi[0][-1]["content"]
    llm2 = LlmGia({"queries": []})
    rewrite_query.rewrite_query(st, llm2, "m")
    assert "Loại hợp đồng: không xác định thời hạn" in llm2.da_goi[0][-1]["content"]


def test_base_mang_ho_so_da_dung():
    ket = as_mod._base({"ho_so": HO_SO, "traces": {}}, as_mod.ResultType.abstain)
    assert [d["khoa"] for d in ket["ho_so_da_dung"]] == ["chu_the", "loai_hop_dong"]
    assert ket["ho_so_da_dung"][0]["gia_dinh"] is True
    assert as_mod._base({"traces": {}}, as_mod.ResultType.abstain)["ho_so_da_dung"] == []
