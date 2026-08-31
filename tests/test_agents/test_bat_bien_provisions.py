"""`db_provisions` thiếu một id đang cần phải NỔ, không im lặng trả rỗng.

Bất biến "mọi provision_id của claim đã qua tầng 1 đều có mặt trong
`db_provisions`, kèm hậu duệ" hiện được giữ **bằng cấu trúc** — ba lệnh gọi
`_db_provisions` trong `graph_tra_cuu.py` lấy id từ cùng một nguồn. Không có
assertion nào canh nó, và không test nào chạm nhánh rỗng.

Nếu bất biến vỡ (một lần tối ưu tương lai dùng chung dbp nhỏ hơn, hay thêm
cache), `.get(id, {})` phát ra một citation `duong_dan`/`so_ky_hieu` RỖNG nhưng
vẫn được đếm là "đã kiểm chứng" — nó vào tỉ lệ quyết định abstain, và hiện ra
với `quote` thật cạnh một địa chỉ trống. Không log, không lỗi, không test đỏ.

Trên một sản phẩm mà đóng góp trung tâm là "mọi khẳng định neo vào trích dẫn
kiểm chứng được", một trích dẫn rỗng đội lốt đã-kiểm-chứng là kiểu hỏng tệ nhất
có thể có.
"""

import pytest

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict, _dieu_luat_cho_judge
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

DB = {11: {"id": 11, "document_id": "139264", "duong_dan": "45/2019/QH14 > Điều 26",
           "so_ky_hieu": "45/2019/QH14", "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


class FakeLlm:
    def chat(self, model, messages, json_schema=None):
        import json

        from src.services.llm import Usage
        return json.dumps({"answer": "x"}), Usage(1, 1, 0.0)


def test_assemble_no_khi_db_provisions_thieu_id_dang_can():
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, EFF)
    # id thiếu là 11 (cái claim đang dẫn), không phải 99 (cái tình cờ có mặt)
    with pytest.raises(KeyError, match="provisions.id=11"):
        assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                  "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                 {99: DB[11]}, FakeLlm(), "m")


def test_judge_khong_bao_gio_nhan_dieu_luat_rong():
    """Judge chấm một khẳng định dựa trên điều luật RỖNG sẽ trả verdict vô
    nghĩa mà vẫn được tin dùng — tệ hơn không gọi judge."""
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, EFF, khop_tai=11)
    with pytest.raises(KeyError):
        _dieu_luat_cho_judge(t1, {})


def test_duong_di_binh_thuong_van_chay():
    t1 = Tier1Result(Claim("x", 11, "85%"), True, R.ok, EFF)
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [t1],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, FakeLlm(), "m")
    assert st["result_type"] is ResultType.answer
    assert st["citations"][0]["so_ky_hieu"] == "45/2019/QH14"
