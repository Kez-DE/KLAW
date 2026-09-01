"""Ràng buộc chung cho MỌI mẫu soạn thảo — một test parametrize trên
`config/checklist_*.yaml`, không một file test nào cho mỗi mẫu.

Thêm một mẫu là thêm một file YAML; file này tự phủ nó ngay, nên không có mẫu
nào có thể vào kho mà bỏ qua phép kiểm. Đây là lý do nó tồn tại thay vì
`test_checklist_noi_quy.py`, `test_checklist_nda.py`, …

Bốn điều mọi mẫu phải đúng:

1. `loai` khớp tên file — `load_checklist_cached` tra file theo `loai` đến từ
   HTTP, nên một file khai `loai` khác tên nó nghĩa là request hỏi loại A mà
   được soát bằng checklist loại B.
2. `loai` nằm trong `LoaiVanBan` — thiếu là 422 ở tầng Pydantic dù file đã có
   trên đĩa, tức một mẫu dựng xong nhưng không ai gọi tới được.
3. Mỗi `rules:` id có thật trong config/rules.yaml, và mỗi mục có
   `key`/`ten`/`can_cu`/`tu_khoa`. `tu_khoa` KHÔNG được rỗng: `extract_clauses`
   map clause về mục CHỈ bằng từ khoá, nên một mục không từ khoá là một mục
   `POST /soat` không bao giờ tìm thấy — completeness sẽ báo thiếu vĩnh viễn
   một nội dung thực ra có mặt.
4. (integration) Mọi `can_cu` phân giải được thành một `provisions.duong_dan`
   CÓ THẬT. Đây là cổng chặn một mẫu bịa căn cứ, cùng khuôn
   `kiem_tra_can_cu_ton_tai` của rules.py/checklist.py và phép kiểm lúc khởi
   động trong `src/main.py`.
"""

from pathlib import Path
from typing import get_args

import pytest
from sqlalchemy import text

from src.agents.graph_soan_thao import (
    cac_loai,
    duong_dan_checklist,
    extract_clauses,
    load_checklist_cached,
    rules_cho,
)
from src.models.schemas import LoaiVanBan
from src.services.checklist import cac_can_cu
from src.services.db import get_engine

MOI_LOAI = sorted(cac_loai())


def test_co_it_nhat_mot_mau():
    assert MOI_LOAI, "không tìm thấy config/checklist_*.yaml nào — glob sai thư mục?"


@pytest.mark.parametrize("loai", MOI_LOAI)
def test_loai_khop_ten_file_va_nam_trong_enum(loai):
    cl = load_checklist_cached(loai)
    assert cl.loai == loai
    assert duong_dan_checklist(loai) == Path(f"config/checklist_{loai}.yaml")
    assert loai in get_args(LoaiVanBan), (
        f"config/checklist_{loai}.yaml có trên đĩa nhưng {loai!r} không nằm trong "
        "LoaiVanBan — Pydantic sẽ trả 422 và không ai gọi tới mẫu này được"
    )


@pytest.mark.parametrize("loai", MOI_LOAI)
def test_ten_va_tieu_de_la_van_ban_nguoi_doc_duoc(loai):
    cl = load_checklist_cached(loai)
    # `ten` đi vào prompt ("Soạn {loai_van_ban}…") nên phải là cụm tiếng Việt,
    # không phải mã enum; `tieu_de` là dòng tiêu đề Markdown nên viết hoa.
    assert cl.ten and cl.ten == cl.ten.strip()
    assert cl.ten != loai, f"{loai}: `ten` vẫn là mã enum, prompt sẽ đọc như máy"
    assert cl.tieu_de == cl.tieu_de.upper(), f"{loai}: `tieu_de` phải viết hoa"


@pytest.mark.parametrize("loai", MOI_LOAI)
def test_moi_muc_du_truong_va_co_tu_khoa(loai):
    cl = load_checklist_cached(loai)
    assert cl.muc, f"{loai}: checklist rỗng"
    for m in cl.muc:
        for truong in ("key", "ten", "can_cu", "tu_khoa"):
            assert m.get(truong), f"{loai}: mục {m.get('key', m)!r} thiếu {truong!r}"
        assert isinstance(m["tu_khoa"], list) and all(m["tu_khoa"]), (
            f"{loai}: mục {m['key']!r} có tu_khoa rỗng — POST /soat không bao giờ khớp được nó"
        )


@pytest.mark.parametrize("loai", MOI_LOAI)
def test_rules_khai_bao_deu_co_that(loai):
    # `rules_cho` tự raise nếu một id không có trong rules.yaml — gọi là đủ.
    for r in rules_cho(loai):
        assert r.id in load_checklist_cached(loai).rules


@pytest.mark.integration
@pytest.mark.parametrize("loai", MOI_LOAI)
def test_MOI_can_cu_TON_TAI_trong_DB(loai):
    """Cổng chặn mẫu bịa căn cứ. Một mẫu sinh ra văn bản trích dẫn điều luật
    không tồn tại phản bội chính đóng góp trung tâm của hệ thống, nên nó phải
    chết ở đây chứ không lọt tới người dùng.
    """
    with get_engine().connect() as conn:
        co_that = {r[0] for r in conn.execute(text("SELECT duong_dan FROM provisions")).all()}
    thieu = sorted(cac_can_cu(load_checklist_cached(loai)) - co_that)
    assert not thieu, f"config/checklist_{loai}.yaml dẫn can_cu không có trong provisions: {thieu}"


@pytest.mark.parametrize("loai", MOI_LOAI)
def test_soan_ra_roi_soat_lai_tach_dung_tung_muc(loai):
    """Đường soạn-rồi-soát: dựng đúng khuôn Markdown mà `_render_markdown` sinh
    ra, rồi cho `extract_clauses` đọc lại. Mỗi mục phải quay về ĐÚNG key của nó.

    Hai hỏng hóc test này chặn, cả hai đều im lặng khi xảy ra:

    * Tách sai — `_split_dieu` không nhận tiền tố "## " của Markdown, hoặc
      `don_vi_muc` của checklist không khớp đơn vị `_render_markdown` in ra, thì
      cả văn bản gộp thành một khối và completeness sập về gần 0 trên chính
      văn bản hệ thống vừa chấm 1.0.
    * Va chạm từ khoá — `extract_clauses` lấy mục ĐẦU TIÊN khớp, nên một từ khoá
      quá rộng ở mục trên sẽ nuốt điều khoản của mục dưới, và mục dưới bị báo
      thiếu vĩnh viễn dù nó có mặt.
    """
    cl = load_checklist_cached(loai)
    van_ban = f"# {cl.tieu_de}\n\n" + "\n".join(
        f"## {cl.don_vi_muc} {i}. {m['ten']}\n\n{m['tu_khoa'][0]} — nội dung điều khoản.\n"
        for i, m in enumerate(cl.muc, 1)
    )
    clauses = extract_clauses(van_ban, cl, {})
    assert [c.key for c in clauses] == [m["key"] for m in cl.muc], (
        f"{loai}: soạn ra rồi soát lại không trả về đúng thứ tự mục — "
        f"tách sai hoặc từ khoá chồng lấn"
    )
