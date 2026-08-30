"""Node expand — mở rộng tập provision đã retrieve TRƯỚC khi đưa cho generate_claims.

Bốn việc (xem task-7-brief.md; việc #2 thêm SAU khi review Task 7 đo trên
đường chạy thật — xem "Sửa 2026-08-31" cuối docstring):

  1. Khoản/Điểm → Điều cha — khớp ở Khoản thì đưa cả Điều cho model đọc, MỘT
     CHIỀU (con → cha). 72,1-73,6% số Điều trong corpus có `noi_dung` chỉ là
     tiêu đề (xem `verify_tier1._cay_con` — cùng con số, đo độc lập ở
     Task 4/5); không đưa Điều cha thì model không biết Khoản vừa khớp thuộc
     điều luật nào.
  2. Điều (hoặc bất kỳ cấp nào đang có con TRONG TẬP) → TOÀN BỘ Khoản/Điểm
     con — CHIỀU NGƯỢC LẠI của #1, chạy SAU #1 nên cha vừa được thêm ở #1
     cũng được lan xuống con. Đo trên đường chạy thật: Plan 2 neo 3.093 chunk
     ở cấp `dieu`, chỉ 190 ở `khoan` — nghĩa là tập truy hồi thật hầu như
     toàn Điều chỉ-tiêu-đề, và NẾU CHỈ CÓ chiều #1 thì `expand` gặp toàn cha,
     không có con nào để kéo lên, nên KHÔNG THÊM GÌ (đo được: 5 Điều → 5,
     0 Khoản/Điểm). Bị CHẶN Ở HAI MỨC — con trực tiếp rồi cháu trực tiếp,
     KHÔNG đệ quy tới lá bất kể cây sâu tới đâu (Điều→Khoản→Điểm đã đủ; đồ thị
     `parent_id` sâu bất thường không được phép làm phình tập).
  3. Reference N hop qua `"references"` (`from_provision_id`/`to_provision_id`,
     1.500 cạnh cấp điều khoản, Plan 2 Task 1) — N = `hops`
     (`Settings.expand_reference_hops`, mặc định 1, CHẶN TRÊN `le=3`: một giá
     trị sweep vô ý (vd. 10) không còn cách nào làm phình tập không kiểm soát
     được). Frontier-BFS có visited-set nên vòng lặp trong đồ thị dẫn chiếu
     không lặp vô hạn và không truy vấn lại node đã thấy. Chạy SAU #1/#2 —
     hop không tự lan xuống con của provision nó vừa kéo về (xem giới hạn ở
     dưới).
  4. Tách deep vs shallow theo `documents.depth`. CHỈ hai giá trị 'deep' và
     'shallow' được giữ; 'metadata' (36 văn bản sửa đổi ngoài corpus, Plan 3
     Task 1 — hiện KHÔNG có provisions nào trỏ vào, đã đo) hay bất kỳ giá trị
     lạ nào khác bị loại khỏi CẢ HAI danh sách một cách TƯỜNG MINH, không rơi
     vào 'deep' qua một nhánh `else` ngầm — không dựa vào bất biến "metadata
     không có provisions" giữ mãi qua các lần nạp dữ liệu sau.

Giới hạn đã biết (cố ý, không phải thiếu sót): #3 (reference hop) chạy SAU
#2 nên một provision được hop-kéo vào KHÔNG được lan xuống con của chính nó —
nếu nó cũng là Điều chỉ-tiêu-đề thì vẫn thiếu thân điều luật. Không làm vì
brief chỉ yêu cầu thêm chiều cha→con làm MỘT bước, và lặp cha→con sau mỗi hop
sẽ nhân số bước phình lên đúng thứ mục "đừng đệ quy vô hạn" muốn tránh — nâng
cấp khi có ca đo được cần nó.

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

# `d.ten` CHỈ để hiển thị cho người đọc ("Bộ luật Lao động" cạnh trích dẫn
# 45/2019/QH14 — người dùng chưa chắc nhận ra so_ky_hieu là văn bản nào), KHÔNG
# phải định danh: `so_ky_hieu` vẫn là khoá định danh DUY NHẤT (Global
# Constraint) vì `ten` một mình có thể mơ hồ (vd. doc_id 96117 → "Hàng hải").
# Ràng buộc "không định danh bằng ten/title" chỉ cấm dùng ten LÀM KHOÁ, không
# cấm mang nó theo để hiển thị (task-9 ruling, 2026-08-31).
_SQL_PROV = text(
    "SELECT p.id, p.document_id, p.parent_id, p.cap, p.so_hieu_cap, p.tieu_de,"
    " p.noi_dung, p.duong_dan, d.so_ky_hieu, d.ten, d.depth"
    " FROM provisions p JOIN documents d ON d.id = p.document_id"
    " WHERE p.id = ANY(:ids)"
)

_SQL_PARENT = text(
    "SELECT DISTINCT parent_id FROM provisions"
    " WHERE id = ANY(:ids) AND parent_id IS NOT NULL AND cap IN ('khoan', 'diem')"
)

_SQL_CHILDREN = text("SELECT id FROM provisions WHERE parent_id = ANY(:ids)")

_SQL_HOP = text(
    'SELECT DISTINCT to_provision_id FROM "references"'
    " WHERE from_provision_id = ANY(:ids) AND to_provision_id IS NOT NULL"
)


# ══ Logic THUẦN (silent-failure review — CRITICAL 2) ═════════════════════════
# expand.py trước bản này gộp SQL và Python trong một hàm, nên 0% được unit
# test (cả 10 test của test_expand.py đều @pytest.mark.integration, bị lệnh CI
# `-m "not integration"` loại sạch — trên một clone sạch, KHÔNG dòng nào của
# node này được kiểm). Ba hàm dưới đây nhận dữ liệu ĐÃ LẤY SẴN (list/dict
# thường), không chạm DB — tách theo đúng khuôn `verify_tier1`/`effectivity.py`
# đã dùng (hàm thuần tách khỏi lớp DB).


def _mo_rong_cha(ids: set[int], cha_moi: list[int]) -> set[int]:
    """Bước 1 THUẦN (module docstring #1): hợp nhất cha mới tìm được (Khoản/
    Điểm → Điều cha) vào `ids`, khử trùng qua set. `cha_moi` là kết quả THÔ
    của `_SQL_PARENT` (đã lấy sẵn) — có thể chứa `None` nếu caller không lọc
    trước, nên vẫn lọc lại ở đây cho an toàn."""
    return set(ids) | {p for p in cha_moi if p is not None}


def _mo_rong_con_hai_muc(ids: set[int], con_muc1: list[int], con_muc2: list[int]) -> set[int]:
    """Bước 2 THUẦN (module docstring #2): Điều → con (`con_muc1`) → cháu
    (`con_muc2`) — CHẶN Ở HAI MỨC, không đệ quy tới lá bất kể cây sâu tới đâu.
    `con_muc1`/`con_muc2` là kết quả THÔ của `_SQL_CHILDREN` gọi hai lượt (lượt
    hai truy vấn con của `con_muc1`) — đã lấy sẵn, không chạm DB ở đây."""
    return set(ids) | set(con_muc1) | set(con_muc2)


def _chia_deep_shallow(rows: list[dict], eff, uu_tien: dict[int, int]) -> tuple[list[dict], list[dict]]:
    """Bước 4 THUẦN (module docstring #4): đánh dấu hiệu lực — KHÔNG LỌC, mọi
    provision đều được gắn `effectivity` kể cả `het_hieu_luc`/`bi_thay_the` —
    rồi chia deep/shallow theo `depth`, sắp theo độ ưu tiên ban đầu. `metadata`
    hay giá trị lạ khác bị loại khỏi CẢ HAI danh sách một cách tường minh.
    `eff` là callable `provision_id -> Effectivity` đã có sẵn (test truyền
    hàm giả) — không chạm DB ở đây.
    """
    deep: list[dict] = []
    shallow: list[dict] = []
    for r in rows:
        r = {**r, "effectivity": eff(r["id"])}
        depth = r.get("depth")
        if depth == "deep":
            deep.append(r)
        elif depth == "shallow":
            shallow.append(r)
        # else: 'metadata' hoặc giá trị lạ khác — loại khỏi CẢ HAI (xem docstring #4)
    deep.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    shallow.sort(key=lambda p: uu_tien.get(p["id"], 10**6))
    return deep, shallow


def expand(provision_ids: list[int], engine: Engine, as_of: date, hops: int) -> tuple[list[dict], list[dict]]:
    """`(expanded_deep, hits_shallow)` — xem docstring module. Chỉ lo TRUY VẤN;
    logic gộp cha/con/chia deep-shallow nằm ở ba hàm thuần phía trên.

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
        ids = _mo_rong_cha(ids, parents)

        # 2 — Điều (kể cả cha vừa thêm ở #1) → con, CHẶN Ở HAI MỨC (con rồi
        # cháu trực tiếp) — không đệ quy tới lá.
        children = conn.execute(_SQL_CHILDREN, {"ids": list(ids)}).scalars().all()
        grandchildren = conn.execute(_SQL_CHILDREN, {"ids": list(children)}).scalars().all() if children else []
        ids = _mo_rong_con_hai_muc(ids, children, grandchildren)

        # 3 — reference N hop, frontier-BFS (visited = `ids`, chống vòng + trùng)
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
    return _chia_deep_shallow(rows, eff, uu_tien)
