"""`eval/run_cau_le.py` với đồ thị giả: bộ câu, nhãn lượt, lịch sử hội thoại, lượt lỗi —
0 lượt gọi mô hình, không mạng."""

import json
from pathlib import Path

from eval.run_cau_le import chay, doc_bo

KHO_LUAT = Path(__file__).resolve().parents[2] / "eval" / "results" / "kho-luat"


def _luot(bo: list[dict]) -> list[str]:
    return [c for m in bo for c in ([m["cau_hoi"]] if isinstance(m["cau_hoi"], str) else m["cau_hoi"])]


def test_bo_live_giu_dung_thu_tu_luot_do_da_ghi():
    bo = doc_bo("live")
    assert _luot(bo) == [h["cau_hoi"] for h in json.loads((KHO_LUAT / "bm-live.json").read_text(encoding="utf-8"))]
    nhom = [m["nhom"] for m in bo]
    assert (nhom.count("noi_bo"), nhom.count("hai_luot"), nhom.count("hop_le")) == (11, 1, 6)


def test_bo_dat_la_cau_cua_ket_qua_da_ghi():
    bo = doc_bo("dat")
    assert _luot(bo) == [json.loads((KHO_LUAT / "bm-nha-dat.json").read_text(encoding="utf-8"))["cau_hoi"]]


class _DoThiGia:
    def __init__(self):
        self.vao: list[dict] = []

    async def ainvoke(self, x):
        self.vao.append(x)
        if x["query"] == "hỏng":
            raise RuntimeError("429")
        return {
            "result_type": "gioi_thieu",
            "answer": f"đáp {x['query']}",
            "intent": "gioi_thieu",
            "queries": [x["query"]],
            "traces": {"route_token_in": 7, "route_cost_usd": 0.001},
        }


async def test_chay_hoi_thoai_mang_lich_su_va_luot_loi_khong_lam_mat_bo():
    g = _DoThiGia()
    bo = [
        {"nhom": "noi_bo", "cau_hoi": "hỏng"},
        {"nhom": "hai_luot", "cau_hoi": ["một", "hai"]},
        {"nhom": "hop_le", "cau_hoi": "ba"},
    ]
    hang = await chay(g, bo)
    assert [h["nhom"] for h in hang] == ["noi_bo", "hai_luot_1", "hai_luot_2", "hop_le"]
    assert hang[0]["error_type"] == "RuntimeError" and "nguoi_dung_thay" not in hang[0]
    assert g.vao[2]["lich_su"] == [{"cau_hoi": "một", "tra_loi": "đáp một", "duong_dan": []}]
    assert g.vao[3]["lich_su"] == [], "câu đơn luôn bắt đầu trạng thái mới"
    h = hang[3]
    assert h["nguoi_dung_thay"]["answer"] == "đáp ba" and h["nguoi_dung_thay"]["result_type"] == "gioi_thieu"
    assert h["noi_bo"] | {"latency_s": 0} == {
        "intent": "gioi_thieu",
        "queries": ["ba"],
        "token_in": 7,
        "token_out": 0,
        "cost_usd": 0.001,
        "goi_chat": 0,
        "goi_embedding_http": 0,
        "latency_s": 0,
    }
