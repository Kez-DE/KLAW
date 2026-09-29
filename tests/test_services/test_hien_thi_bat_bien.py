"""Bất biến: MỌI truy vấn đọc `documents`/`provisions`/`chunks`/`"references"`
trong `src/` hoặc lọc bằng tập văn bản được hiện, hoặc được miễn có lý do.

Thẩm quyền: `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`
mục 8 — "một văn bản chỉ được hiện cho người dùng (kho, tìm kiếm, bộ lọc, trang
văn bản, trích dẫn) khi đồng thời còn hiệu lực …, đã xác định được tình trạng …
và có link chính thống đã kiểm", văn bản ẩn "giữ trong DB" để chỉ ra văn bản
thay thế và kiểm trích dẫn cũ.

Phạm vi: mọi chuỗi SQL (hằng số, chuỗi ghép `+`, f-string) trong `src/`, quét
bằng AST — không chạy truy vấn nào, 0 DB. Hợp lệ: chuỗi mang `:hien` (tham số
tập được hiện, `services/hien_thi.tap_hien_thi`). Ngoại lệ: `DUOC_MIEN`, mỗi
dòng một lý do; loại `sau_chan` còn bị kiểm thêm là MỌI hàm dùng nó phải gọi
cổng tương ứng (`chan_neu_an` cho trang một văn bản).
"""

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
THAM_QUYEN = "docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md mục 8"

# `anh_van_ban`: ảnh trang 1 bản đã ký (migration 040) là nội dung của MỘT văn bản.
_RE_DOC = re.compile(r'\b(?:FROM|JOIN)\s+(?:documents|provisions|chunks|"references"|anh_van_ban)\b')

# Lý do miễn — một chỗ để đọc cả danh sách ngoại lệ.
DO_THI = "đồ thị hiệu lực: văn bản ẩn PHẢI còn ở đây để chỉ ra văn bản thay thế (mục 8)"
KIEM_CHUNG = "kiểm chứng đầu ra mô hình; trích dẫn hiện ra chỉ đến từ tập căn cứ đã lọc"
TIEN_DE = "phép kiểm tiền đề 'Điều N của Bộ luật X có tồn tại' — kiểm trích dẫn cũ, không hiện nội dung"
TRUNG_GIAN = "chỉ ra id trung gian; tập cuối đã lọc ở truy vấn mang :hien của cùng đường"
TAP_HIEN = "chính phép tính tập được hiện / câu trả lời cho văn bản ẩn được nêu tên"
DAU_CACHE = "dấu vân tay corpus cho khoá cache, không trả dòng nào"
NAP = "nạp dữ liệu / kiểm toàn vẹn lúc khởi động, không phải đường đọc của người dùng"
SOAN_THAO = "tập điều khoản của checklist (lru_cache); mọi bề mặt người đọc lọc qua `chi_van_ban_hien`"

# (file tương đối `src/`, tên hằng số hoặc hàm) → (lý do, hàm cổng bắt buộc | None)
DUOC_MIEN: dict[tuple[str, str], tuple[str, str | None]] = {
    **{
        ("services/effectivity.py", n): (DO_THI, None)
        for n in (
            "_SQL_DOC",
            "_SQL_CANH",
            "_SQL_UNG_VIEN",
            "_SQL_SUA_DOI",
            "_SQL_SUA_DOI_VAN_BAN",
            "_SQL_DOC_TAT_CA",
            "_SQL_CANH_TAT_CA",
        )
    },
    ("agents/nodes/verify_tier1.py", "_SQL_CAY"): (KIEM_CHUNG, None),
    ("agents/graph_tra_cuu.py", "_db_provisions"): (KIEM_CHUNG, None),
    ("agents/nodes/verify_tier1.py", "tien_de_cau_hoi_sai"): (TIEN_DE, None),
    **{
        ("agents/nodes/expand.py", n): (TRUNG_GIAN, None)
        for n in ("_SQL_PARENT", "_SQL_CHILDREN", "_SQL_NEO_SUA", "_SQL_THEO_DUONG_DAN")
    },
    ("services/retrieval.py", "provision_ids"): (TRUNG_GIAN, None),
    ("services/retrieval.py", "linh_vuc_cua"): (TRUNG_GIAN, None),
    **{
        ("services/hien_thi.py", n): (TAP_HIEN, None)
        for n in ("_SQL_UNG_VIEN", "_SQL_VAN_BAN_NEU", "_SQL_DOC", "_SQL_THEO_SO")
    },
    ("services/kho.py", "_SQL_KHO"): ("mỗi dòng mang cờ `hien`; mọi con số và danh sách lọc bằng nó", "gan_hien_thi"),
    ("agents/graph_soan_thao.py", "_SQL_PROVISIONS_BY_DUONG_DAN"): (SOAN_THAO, None),
    ("agents/graph_soan_thao.py", "_SQL_DOCUMENTS_BY_ID"): (SOAN_THAO, None),
    ("agents/graph_soan_thao.py", "_SQL_VAN_BAN_CAN_CU"): ("khối Căn cứ", "chi_van_ban_hien"),
    ("services/cache_tra_loi.py", "_SQL_CHECKSUM"): (DAU_CACHE, None),
    ("services/checklist.py", "kiem_tra_can_cu_ton_tai"): (NAP, None),
    ("services/rules.py", "kiem_tra_can_cu_ton_tai"): (NAP, None),
    ("services/chunker.py", "load_provisions"): (NAP, None),
    ("services/xref.py", "resolve_all"): (NAP, None),
    # Trang MỘT văn bản: đọc theo `doc_id` SAU cổng 404 `khong_hien_thi`.
    **{
        ("api/routes.py", n): ("trang một văn bản", "chan_neu_an")
        for n in (
            "_SQL_VAN_BAN_DOC",
            "_SQL_VAN_BAN_MUC_LUC",
            "_SQL_VAN_BAN_DIEU_PHANG",
            "_SQL_VAN_BAN_DIEU_BY_SO_HIEU",
            "_SQL_VAN_BAN_PROVISION_GOC",
            "_SQL_VAN_BAN_DIEU_CHA",
            "_SQL_VAN_BAN_DIEU_TRUOC",
            "_SQL_VAN_BAN_DIEU_SAU",
            "_SQL_VAN_BAN_CAY_DIEU",
            "_SQL_DIEU_TRONG_CHUONG",
        )
    },
    **{
        ("api/routes_van_ban.py", n): ("trang một văn bản", "chan_neu_an")
        for n in ("_SQL_DOC", "_SQL_LIEN_QUAN", "_SQL_NOI_BO", "_SQL_ANH_XEM_TRUOC")
    },
    **{
        ("api/routes_tim_kiem.py", n): ("trang một văn bản", "chan_neu_an")
        for n in ("_SQL_TIM_TRONG_VB", "_SQL_TIM_TRONG_VB_DEM", "_SQL_TIM_TRONG_VB_TRANG", "_SQL_DOC_TOI_THIEU")
    },
}


def _chuoi(node: ast.AST, ten: dict[str, str]) -> str | None:
    """Giá trị tĩnh của một biểu thức chuỗi; phần không suy được coi là rỗng."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.Name):
        return ten.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _chuoi(node.left, ten), _chuoi(node.right, ten)
        return None if a is None and b is None else (a or "") + (b or "")
    return None


def quet(goc: Path) -> list[tuple[str, int, str, str]]:
    """`(file, dòng, tên chủ, sql)` cho mọi chuỗi SQL đọc bảng được canh."""
    ra = []
    for f in sorted(goc.rglob("*.py")):
        cay = ast.parse(f.read_text(encoding="utf-8"))
        docstring = {
            id(n.body[0].value)
            for n in ast.walk(cay)
            if isinstance(n, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and n.body
            and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        ten: dict[str, str] = {}
        for n in cay.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                v = n.value.args[0] if isinstance(n.value, ast.Call) and n.value.args else n.value
                if (s := _chuoi(v, ten)) is not None:
                    ten[n.targets[0].id] = s
        cha = {id(c): n for n in ast.walk(cay) for c in ast.iter_child_nodes(n)}

        def chu(n: ast.AST) -> str:
            p = cha.get(id(n))
            while p is not None:
                if isinstance(p, ast.FunctionDef | ast.AsyncFunctionDef):
                    return p.name
                if isinstance(p, ast.Assign) and isinstance(cha.get(id(p)), ast.Module):
                    return p.targets[0].id if isinstance(p.targets[0], ast.Name) else "?"
                p = cha.get(id(p))
            return "<module>"

        for n in ast.walk(cay):
            if not isinstance(n, ast.Constant | ast.BinOp | ast.JoinedStr) or id(n) in docstring:
                continue
            if isinstance(cha.get(id(n)), ast.BinOp | ast.JoinedStr):
                continue  # chỉ xét biểu thức chuỗi LỚN NHẤT
            if (s := _chuoi(n, ten)) and _RE_DOC.search(s):
                ra.append((str(f.relative_to(goc)), n.lineno, chu(n), s))
    return ra


def _ham_dung(cay: ast.Module, ten: str) -> list[ast.FunctionDef]:
    return [
        f
        for f in ast.walk(cay)
        if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(isinstance(x, ast.Name) and x.id == ten for x in ast.walk(f))
    ]


def _goi(f: ast.AST, ten: str) -> bool:
    return any(
        isinstance(x, ast.Call) and (getattr(x.func, "id", None) == ten or getattr(x.func, "attr", None) == ten)
        for x in ast.walk(f)
    )


def vi_pham(goc: Path, mien: dict) -> list[str]:
    loi = []
    thay = set()
    for file, dong, chu, sql in quet(goc):
        if ":hien" in sql:
            continue
        khoa = (file, chu)
        if khoa not in mien:
            loi.append(
                f"src/{file}:{dong} `{chu}` đọc documents/provisions/chunks mà không lọc tập văn bản được hiện "
                f"(`:hien`) — {THAM_QUYEN}. Lọc bằng `d.id = ANY(CAST(:hien AS text[]))` với "
                "`services/hien_thi.tap_hien_thi`, hoặc thêm vào DUOC_MIEN kèm lý do nếu đây không phải "
                "đường đọc của người dùng."
            )
            continue
        thay.add(khoa)
    for (file, chu), (_ly_do, cong) in mien.items():
        if (file, chu) not in thay and (goc / file).exists():
            loi.append(f"DUOC_MIEN có `{file}:{chu}` nhưng không còn truy vấn nào ở đó — gỡ dòng miễn cũ.")
        if cong and (goc / file).exists():
            cay = ast.parse((goc / file).read_text(encoding="utf-8"))
            for f in _ham_dung(cay, chu):
                if not _goi(f, cong):
                    loi.append(
                        f"src/{file}: hàm `{f.name}` dùng `{chu}` mà không gọi `{cong}` — {THAM_QUYEN}: văn bản ẩn "
                        f"phải bị chặn trước khi đọc. Gọi `{cong}` trước truy vấn."
                    )
    return loi


def test_moi_duong_doc_van_ban_deu_loc_tap_duoc_hien_hoac_duoc_mien_co_ly_do():
    assert vi_pham(SRC, DUOC_MIEN) == []


def test_duong_tra_loi_truyen_tap_duoc_hien_vao_truy_hoi_va_mo_rong():
    """`Retriever.hybrid`/`expand` nhận `hien=None` để đo truy hồi thô (eval); đường
    trả lời thì PHẢI truyền tập được hiện — thiếu nó là văn bản ẩn thành căn cứ."""
    cay = ast.parse((SRC / "agents/graph_tra_cuu.py").read_text(encoding="utf-8"))
    goi = [x for x in ast.walk(cay) if isinstance(x, ast.Call)]
    hybrid = [x for x in goi if getattr(x.func, "attr", None) == "hybrid"]
    expand = [x for x in goi if getattr(x.func, "id", None) == "expand"]
    assert hybrid and all(len(x.args) + len(x.keywords) >= 2 for x in hybrid), "retriever.hybrid(q, hien)"
    assert expand and all(len(x.args) + len(x.keywords) >= 5 for x in expand), "expand(..., hien)"


# ─────────────────────────────────── chứng minh hai chiều (encoding-invariants §4)


def test_CHUNG_MINH_AM_bat_duoc_truy_van_moi_khong_loc(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "moi.py").write_text(
        'from sqlalchemy import text\n_SQL_MOI = text("SELECT id, ten FROM documents WHERE loai_van_ban = :l")\n',
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {})
    assert "src/api/moi.py:2 `_SQL_MOI`" in loi and "mục 8" in loi and ":hien" in loi, loi


def test_CHUNG_MINH_AM_bat_duoc_anh_van_ban_doc_khong_qua_cong(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "anh.py").write_text(
        'from sqlalchemy import text\n_SQL_ANH = text("SELECT png FROM anh_van_ban WHERE doc_id = :i")\n',
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {})
    assert "src/api/anh.py:2 `_SQL_ANH`" in loi, loi


def test_CHUNG_MINH_AM_bat_duoc_trang_van_ban_bo_qua_cong(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "trang.py").write_text(
        "from sqlalchemy import text\n"
        '_SQL_DOC = text("SELECT ten FROM documents WHERE id = :i")\n'
        "def xem(engine, i):\n"
        "    with engine.connect() as c:\n"
        "        return c.execute(_SQL_DOC, {'i': i}).one()\n",
        encoding="utf-8",
    )
    (loi,) = vi_pham(tmp_path, {("api/trang.py", "_SQL_DOC"): ("trang một văn bản", "chan_neu_an")})
    assert "hàm `xem` dùng `_SQL_DOC` mà không gọi `chan_neu_an`" in loi, loi


@pytest.mark.parametrize(
    "sql",
    [
        '"SELECT d.id FROM documents d WHERE d.id = ANY(CAST(:hien AS text[]))"',
        '"SELECT count(*) FROM documents" + _LOC',
    ],
)
def test_CHUNG_MINH_DUONG_truy_van_loc_bang_hien_thi_qua(tmp_path, sql):
    (tmp_path / "m.py").write_text(
        f'from sqlalchemy import text\n_LOC = " WHERE id = ANY(CAST(:hien AS text[]))"\n_SQL = text({sql})\n',
        encoding="utf-8",
    )
    assert vi_pham(tmp_path, {}) == []
