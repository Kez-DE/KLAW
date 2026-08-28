"""Sinh câu hỏi ỨNG VIÊN từ cụm Lao động — người phải review trước khi dùng.

KHÔNG ghi trực tiếp vào golden_qa.yaml. Ghi ra *_candidates.yaml với
da_review: false, người đọc từng câu, loại câu lộ đáp án, viết lại giọng dân
sinh, rồi mới chuyển sang golden_qa.yaml. Tỉ lệ loại phải báo cáo (spec 11.1).

Nguồn câu hỏi là `chunks JOIN provisions`, KHÔNG phải `provisions` trực tiếp:
provision_id ghi ra phải là thứ retrieval thật sự có thể trả về
(`chunks.provision_id`, xem `src/services/retrieval.py::hybrid_provisions`).
Nhiều Điều quan trọng nhất (Điều 97, 105, 35 BLLĐ) có `provisions.noi_dung`
ngắn ở cấp Điều vì nội dung thật nằm ở Khoản con — lọc theo độ dài ở cấp Điều
(cách bản nháp đầu của brief làm) sẽ loại nhầm đúng những Điều đó.
"""

import json
import random
import sys
from pathlib import Path

import httpx
import yaml
from sqlalchemy import text

from src.config import get_settings
from src.services.db import get_engine

# Cụm Lao động — spec 11.1, xác minh qua bảng `documents` thật và đối chiếu
# `scripts/fetch_moj.py::DOC_IDS`.
LAO_DONG_SO_KY_HIEU = [
    "45/2019/QH14", "84/2015/QH13", "145/2020/NĐ-CP", "12/2022/NĐ-CP",
    "135/2020/NĐ-CP", "29/2019/NĐ-CP", "90/2019/NĐ-CP", "74/2024/NĐ-CP",
    "293/2025/NĐ-CP", "337/2025/NĐ-CP", "122/2015/NĐ-CP", "141/2017/NĐ-CP",
    "157/2018/NĐ-CP", "09/2020/TT-BLĐTBXH", "10/2020/TT-BLĐTBXH", "18/2021/TT-BLĐTBXH",
]

PROMPT = """Bạn nhận nguyên văn một điều luật Việt Nam. Hãy viết {n} câu hỏi mà
NGƯỜI DÂN THƯỜNG sẽ hỏi, và điều luật này trả lời được.

Bắt buộc:
- Dùng ngôn ngữ đời thường. TUYỆT ĐỐI KHÔNG dùng thuật ngữ pháp lý.
- TUYỆT ĐỐI KHÔNG nêu số điều, số khoản, tên văn bản.
- Mỗi câu là một tình huống cụ thể, không phải câu hỏi định nghĩa.

Trả về JSON: {{"cau_hoi": ["...", "..."]}}

Điều luật:
{noi_dung}
"""


def _lay_chunks_lao_dong() -> list[dict]:
    """provision_id + duong_dan + toàn văn (đã gom Khoản con) của cả cụm."""
    with get_engine().connect() as c:
        rows = c.execute(text(
            "SELECT c.provision_id AS id, p.duong_dan, c.noi_dung_embed AS noi_dung"
            " FROM chunks c JOIN provisions p ON p.id = c.provision_id"
            " JOIN documents d ON d.id = p.document_id"
            " WHERE d.so_ky_hieu = ANY(:ma)"
        ), {"ma": LAO_DONG_SO_KY_HIEU}).mappings().all()
    return list(rows)


def gen(n_dieu: int = 25, n_moi_dieu: int = 2, seed: int = 7) -> Path:
    s = get_settings()
    random.seed(seed)
    rows = _lay_chunks_lao_dong()
    mau = random.sample(rows, min(n_dieu, len(rows)))

    http = httpx.Client(
        base_url=s.openrouter_base_url, timeout=120,
        headers={"Authorization": f"Bearer {s.openrouter_api_key}"})
    items: list[dict] = []
    for i, r in enumerate(mau):
        body = {"model": s.openrouter_generate_model_name,
                "temperature": s.llm_temperature,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": PROMPT.format(
                    n=n_moi_dieu, noi_dung=r["noi_dung"])}]}
        resp = http.post("/chat/completions", json=body)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        try:
            cau_hoi = json.loads(raw)["cau_hoi"]
        except (json.JSONDecodeError, KeyError):
            print(f"bỏ qua {r['duong_dan']}: JSON hỏng từ model — {raw[:120]!r}")
            continue
        for j, q in enumerate(cau_hoi):
            items.append({"id": f"lao-{i:03d}-{j}", "cau_hoi": q,
                          "provision_ids": [r["id"]], "duong_dan": [r["duong_dan"]],
                          "bo_luat": "Lao động", "nguon": "llm-gen", "da_review": False})

    out = Path(s.eval_dataset_dir) / "golden_qa_candidates.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"items": items}, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    print(f"{len(items)} ứng viên → {out}")
    print("BƯỚC TIẾP THEO LÀ VIỆC CỦA NGƯỜI: review từng câu, loại câu lộ đáp án,")
    print("viết lại giọng dân sinh, đặt da_review: true, chuyển sang golden_qa.yaml.")
    print("Ghi lại tỉ lệ loại — spec 11.1 yêu cầu báo cáo con số này.")
    return out


if __name__ == "__main__":
    gen(n_dieu=int(sys.argv[1]) if len(sys.argv) > 1 else 25)
