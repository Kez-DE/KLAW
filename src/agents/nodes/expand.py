"""Node expand — mở rộng tập provision đã retrieve TRƯỚC khi đưa cho generate_claims.

Ba việc (xem task-7-brief.md):

  1. Khoản/Điểm → Điều cha — khớp ở Khoản thì đưa cả Điều cho model đọc, MỘT
     CHIỀU (con → cha), KHÔNG lan ngược xuống các Khoản anh em. 72,1-73,6% số
     Điều trong corpus có `noi_dung` chỉ là tiêu đề (xem `verify_tier1._cay_con`
     — cùng con số, đo độc lập ở Task 4/5); không đưa Điều cha thì model không
     biết Khoản vừa khớp thuộc điều luật nào.
  2. Reference N hop qua `"references"` (`from_provision_id`/`to_provision_id`,
     1.500 cạnh cấp điều khoản, Plan 2 Task 1) — N = `hops`
     (`Settings.expand_reference_hops`, mặc định 1). Frontier-BFS có visited-set
     nên vòng lặp trong đồ thị dẫn chiếu không lặp vô hạn và không truy vấn lại
     node đã thấy.
  3. Tách deep vs shallow theo `documents.depth`. CHỈ hai giá trị 'deep' và
     'shallow' được giữ; 'metadata' (36 văn bản sửa đổi ngoài corpus, Plan 3
     Task 1 — hiện KHÔNG có provisions nào trỏ vào, đã đo) hay bất kỳ giá trị
     lạ nào khác bị loại khỏi CẢ HAI danh sách một cách TƯỜNG MINH, không rơi
     vào 'deep' qua một nhánh `else` ngầm — không dựa vào bất biến "metadata
     không có provisions" giữ mãi qua các lần nạp dữ liệu sau.

Hiệu lực là ĐÁNH DẤU, không LỌC: `effectivity` chỉ được đính kèm vào mỗi
provision (tái dùng `effectivity_qua_provision` của Task 5, đi qua
`danh_gia_theo_id` — KHÔNG đọc thẳng `documents.tinh_trang`, xem
`src/services/effectivity.py`), không provision nào bị loại vì hiệu lực. Tầng 1
(phép kiểm 4) cần THẤY cả điều luật hết hiệu lực để WARN; loại nó ở đây là làm
mù tầng 1 trước khi nó kịp cảnh báo, và xoá mất câu trả lời "điều này đã bị
thay bởi X".

KHÔNG gọi LLM (Global Constraint — expand chạy trước tầng 1, tầng 1 cũng không
gọi LLM): thuần SQL + Python.
"""

from datetime import date

from sqlalchemy import Engine, text

from src.agents.nodes.verify_tier1 import effectivity_qua_provision

_SQL_PROV = text(
    "SELECT p.id, p.document_id, p.parent_id, p.cap, p.so_hieu_cap, p.tieu_de,"
    " p.noi_dung, p.duong_dan, d.so_ky_hieu, d.depth"
    " FROM provisions p JOIN documents d ON d.id = p.document_id"
    " WHERE p.id = ANY(:ids)"
)

_SQL_PARENT = text(
    "SELECT DISTINCT parent_id FROM provisions"
    " WHERE id = ANY(:ids) AND parent_id IS NOT NULL AND cap IN ('khoan', 'diem')"
)

_SQL_HOP = text(
    'SELECT DISTINCT to_provision_id FROM "references"'
    " WHERE from_provision_id = ANY(:ids) AND to_provision_id IS NOT NULL"
)


def expand(provision_ids: list[int], engine: Engine, as_of: date, hops: int) -> tuple[list[dict], list[dict]]:
    """`(expanded_deep, hits_shallow)` — xem docstring module.

    `hits_shallow` chỉ để tầng phát hiện ranh giới dùng (PARTIAL_COVERAGE);
    KHÔNG trộn vào `expanded_deep` đưa cho generate_claims.
    """
    if not provision_ids:
        return [], []

    uu_tien = {pid: i for i, pid in enumerate(provision_ids)}
    ids = set(provision_ids)

    with engine.connect() as conn:
        # 1 — Khoản/Điểm → Điều cha
        parents = conn.execute(_SQL_PARENT, {"ids": list(ids)}).scalars().all()
        ids.update(p for p in parents if p is not None)

        # 2 — reference N hop, frontier-BFS (visited = `ids`, chống vòng + trùng)
        frontier = set(ids)
        for _ in range(hops):
            if not frontier:
                break
            targets = conn.execute(_SQL_HOP, {"ids": list(frontier)}).scalars().all()
            frontier = {t for t in targets if t not in ids}
            ids.update(frontier)

        rows = [dict(r) for r in conn.execute(_SQL_PROV, {"ids": list(ids)}).mappings().all()]

    db_provisions = {r["id"]: r for r in rows}
    eff = effectivity_qua_provision(engine, db_provisions, as_of)

    deep: list[dict] = []
    shallow: list[dict] = []
    for r in rows:
        r["effectivity"] = eff(r["id"])
        depth = r.get("depth")
        if depth == "deep":
            deep.append(r)
        elif depth == "shallow":
            shallow.append(r)
        # else: 'metadata' hoặc giá trị lạ khác — loại khỏi CẢ HAI (xem docstring #3)

    deep.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    shallow.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    return deep, shallow
