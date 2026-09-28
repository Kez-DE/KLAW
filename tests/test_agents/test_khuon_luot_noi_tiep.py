"""Lượt NỐI TIẾP trên tài liệu có khuôn gốc (owner 2026-09-28, G7).

Hội thoại thật a99dfda8… (BM.ĐT.18.11 có khuôn gốc, một bản thảo rỗng từ nút
"Điền biểu mẫu"): ba lượt 'soạn thảo lại văn bản này cho tôi', 'Điền họ và tên …
mã số …', 'cho tôi xem văn bản mới sau khi điền' đều ra `tai_lieu`/`hoi`, không bản
thảo nào, và lời của mô hình ("Tôi đã điền … ⟦0⟧ …") đi thẳng tới người dùng: router
gọi mọi lượt đó là `tai_lieu`, và gác `_muc_dich_soan_da_xac_nhan` hạ mọi lượt soạn
về `hoi`. Khoá ở đây, tất cả bằng mô hình GIẢ (0 lượt gọi thật):

1. Trên tài liệu có khuôn gốc, lượt điền/sửa/dựng lại quyết định bằng chứng cứ tất
   định — động từ trong lời người hỏi, phép đã qua `kiem_phep_sua` — không bằng
   `intent` của router (Q4). Câu hỏi thật vẫn là hỏi đáp; tài liệu không khuôn gốc
   vẫn chịu gác cũ.
2. Lời xin XEM bản đã điền trả bản thảo khuôn gốc mới nhất của hội thoại, 0 lượt gọi
   mô hình, không phiên bản mới (Q3).
3. Lượt soạn không áp được gì không bao giờ nói "Tôi đã điền"; dấu nội bộ ⟦n⟧/¶n
   không bao giờ tới người đọc.
"""

import json
from pathlib import Path

import pytest

from src.agents.graph_tra_cuu import _re_sau_hieu_tai_lieu
from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent
from src.api import routes
from src.models.schemas import TraCuuRequest
from src.services import ban_thao, bao_ve
from src.services.doc_tai_lieu import doc
from src.services.tai_lieu import _hang_don_vi
from tests.test_services.test_dung_trang import docx_that

V = "cccccccc-0000-0000-0000-00000000000c"
BM_18_11 = Path("/Users/kenz_de/giấy tờ thực tập") / (
    "BM.ĐT.18.11. Phiếu đánh giá quá trình thực tập tốt nghiệp của sinh viên tại cơ sở thực tập Ver 02 (1).docx"
)
TEN = "Nguyễn Văn Ánh"
MA = "22010123"
DIEN = f"Điền họ và tên {TEN} mã số {MA}"
XEM = "cho tôi xem văn bản mới sau khi điền"
HOI = "ô Mã số dùng để làm gì?"


# ───────────────────────────────────────────────────────────── bộ nhận câu


@pytest.mark.parametrize(
    "cau",
    [
        DIEN,
        "dien ho ten Nguyen Van Anh",
        "dien ho ten Nguyễn Văn Ánh",
        "ĐIỀN GIÚP TÔI mã số 22010123",
        "ghi tên tôi vào ô họ tên",
        "sửa mã số thành 22010124",
        "đổi ngành thành Luật kinh tế",
        "bổ sung khoa Luật",
        "xoá dòng ghi chú",
        "xóa ô khoa",
        "thêm tên giảng viên vào",
        "cập nhật mã số",
        "thay tên khoa bằng Khoa Luật",
    ],
)
def test_nhan_ra_loi_xin_dien_hay_sua(cau):
    assert h.xin_dien_sua(cau)


@pytest.mark.parametrize(
    "cau",
    [
        HOI,
        "số điện thoại của cơ sở là gì",  # điện ≠ điền: so dấu trên đúng chữ đã gõ
        "ai đại diện ký phiếu này",
        "người ký thay mặt nhà trường là ai",
        "soạn thảo lại văn bản này cho tôi",
        XEM,  # lời xin XEM, "sau khi điền" không phải lời xin điền
    ],
)
def test_khong_nhan_nham_loi_xin_dien(cau):
    assert not h.xin_dien_sua(cau)


@pytest.mark.parametrize(
    "cau",
    [
        "soạn thảo lại văn bản này cho tôi",
        "soạn thảo văn bản này cho tôi",
        "soạn lại giúp tôi",
        "tạo lại văn bản này",
        "dựng lại biểu mẫu",
        "xuất file này",
        "xuất tệp này ra",
        "làm lại văn bản",
        "soan thao lai van ban nay",
    ],
)
def test_nhan_ra_loi_xin_dung_lai(cau):
    assert h.xin_tao_lai(cau)


@pytest.mark.parametrize("cau", [HOI, DIEN, "dừng lại đi", "phiếu này nói gì", "Văn bản này được xuất bản năm nào?"])
def test_khong_nhan_nham_loi_xin_dung_lai(cau):
    assert not h.xin_tao_lai(cau)


# Câu hỏi có động từ dựng lại (review G7): chỉ động từ thì chưa đủ thành lượt soạn.
CAU_HOI_DUNG_LAI = [
    "Văn bản này do ai soạn thảo?",
    "Làm sao để xuất file PDF?",
    "Phiếu này soạn thảo theo quy định nào",
    "soan thao lai duoc khong",
]


@pytest.mark.parametrize("cau", CAU_HOI_DUNG_LAI)
def test_nhan_ra_cau_hoi(cau):
    assert h._la_cau_hoi(cau)


@pytest.mark.parametrize(
    "cau",
    # "không" chỉ là dấu hỏi ở cuối câu; "gỉ" có dấu khác "gì".
    ["soạn thảo lại văn bản này cho tôi", "xuất file này", "tạo lại văn bản, không cần điền", "dựng lại bản gỉ"],
)
def test_khong_nhan_nham_cau_hoi(cau):
    assert not h._la_cau_hoi(cau)


@pytest.mark.parametrize(
    "cau",
    [
        XEM,
        "mở bản đã điền",
        "xem lại bản thảo",
        "cho tôi xem bản thảo",
        "bản đã điền đâu?",
        "Xem bản mới nhé",
        "tôi muốn xem bản đã điền",
        "mở lại bản thảo giúp tôi",
        "cho toi xem ban da dien",
    ],
)
def test_nhan_ra_loi_xin_xem_ban_thao(cau):
    assert h.xin_xem_ban_thao(cau)


@pytest.mark.parametrize(
    "cau",
    [
        "cho tôi xem biểu mẫu này nói gì",
        "điền họ tên A rồi cho tôi xem bản mới",
        "xem giúp tôi ô Mã số",
        HOI,
        "soạn thảo lại văn bản này cho tôi",
    ],
)
def test_khong_nhan_nham_loi_xin_xem(cau):
    assert not h.xin_xem_ban_thao(cau)


def test_prompt_v2_cam_dau_noi_bo_trong_moi_truong_chu():
    p = h.PROMPT_KHUON_PATH.read_text(encoding="utf-8")
    assert "Không bao giờ viết chúng vào bất\nkỳ trường chữ nào (`tra_loi_ngan`, `mo_ta`" in p


def test_bo_dau_noi_bo_khoi_chu_mo_hinh():
    assert h.bo_dau_noi_bo("Tôi đã điền vào chỗ trống số 0 ⟦0⟧ và ⟦1=«22010123»⟧.") == (
        "Tôi đã điền vào chỗ trống số 0 và 22010123."
    )
    assert h.bo_dau_noi_bo("¶0 TÊN CƠ QUAN ¶2 Số ⟦0⟧/⟦1⟧") == "TÊN CƠ QUAN Số /"
    assert h.bo_dau_noi_bo("dòng một ⟦3\ndòng hai ⟧") == "dòng một\ndòng hai"
    assert h.bo_dau_noi_bo("Không có dấu nào.") == "Không có dấu nào."


# ───────────────────────────────────────────── ba lượt thật của hội thoại


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra=None):
        self.ra, self.so_lan_goi = ra, 0

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.so_lan_goi += 1
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


class _No:
    def chat(self, *a, **k):  # pragma: no cover
        raise AssertionError("assemble không gọi mô hình ở lượt này")


class _Kho:
    """`ban_thao` trong bộ nhớ cho MỘT hội thoại: phiên bản là TRỌN danh sách phép,
    `khuon` tính bằng chính `ban_thao.cho_trong_khuon` trên hàng đã lưu."""

    def __init__(self, ten_tep: str, hang: list[dict]):
        self.ten_tep, self.hang, self.dong = ten_tep, hang, []

    def _ra(self, r: dict) -> dict:
        cho = ban_thao.cho_trong_khuon("docx", self.hang, r["phep_sua"])
        khuon = {"viec_id": r["viec_id"], "dinh_dang": "docx", "so_trang": 1, "cho_trong": cho}
        return {**r, "ten_tep": self.ten_tep, "khuon": khuon}

    def tao(self, sub, pid, loai, facts, ket):
        r = {
            "id": f"bt-{len(self.dong) + 1}",
            "loai": loai,
            "phien_ban": 1,
            "so_lan_sua": 0,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "facts": facts,
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
        }
        self.dong.append(r)
        return self._ra(r)

    def sua(self, sub, id, facts, ket, *, tang=1):
        r = next(x for x in self.dong if x["id"] == id)
        r.update(
            phien_ban=r["phien_ban"] + 1,
            so_lan_sua=r["so_lan_sua"] + tang,
            document=ket["document"],
            clauses=ket["clauses"],
            audit=ket["audit_report"],
            viec_id=ket.get("viec_id"),
            phep_sua=ket.get("phep_sua"),
        )
        return self._ra(r)

    def moi_nhat(self, sub, pid, loai, *, viec_id):
        r = next((x for x in reversed(self.dong) if x["viec_id"] == viec_id), None)
        return self._ra(r) if r else None

    def moi_nhat_tren_khuon(self, sub, *, hoi_thoai_id=None, viec_id=None):
        r = next((x for x in reversed(self.dong) if x["viec_id"] and viec_id in (None, x["viec_id"])), None)
        return self._ra(r) if r else None

    def nhe(self) -> dict | None:
        r = self.dong[-1] if self.dong else None
        return {k: r[k] for k in ("document", "audit", "viec_id", "phep_sua")} if r else None

    def anh_chup(self) -> list[tuple]:
        return [(r["id"], r["phien_ban"], json.dumps(r["phep_sua"])) for r in self.dong]


def _mau(duong: Path | None) -> tuple[bytes, str, list, list[dict], int]:
    """BM.ĐT.18.11 thật, hoặc một bản dựng cùng dòng «Họ và tên sinh viên … Mã số …»
    (CI không có tệp của chủ dự án): bytes, tên tệp, đơn vị, hàng jsonb, đơn vị họ tên."""
    if duong is None:
        ten = "BM.ĐT.18.11. Phiếu đánh giá (bản dựng).docx"
        goc = docx_that(
            "PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP TỐT NGHIỆP",
            "Họ và tên sinh viên: ………………………………………. Mã số: ………………..",
            "Khoa: ……………………………………….. Ngành: ……………………………...",
        )
    else:
        ten, goc = duong.name, duong.read_bytes()
    dv = doc(ten, goc).don_vi
    hang = json.loads(json.dumps([_hang_don_vi(x) for x in dv], ensure_ascii=False))
    o = next(x.chi_so for x in dv if x.noi_dung.startswith("Họ và tên sinh viên:"))
    return goc, ten, dv, hang, o


MAU = [
    pytest.param(None, id="ban_dung"),
    pytest.param(
        BM_18_11,
        id="BM_DT_18_11_that",
        marks=pytest.mark.skipif(not BM_18_11.exists(), reason="biểu mẫu thật của chủ dự án không có trên máy này"),
    ),
]


@pytest.fixture
def kho(monkeypatch):
    def _dung(ten_tep: str, hang: list[dict]) -> _Kho:
        k = _Kho(ten_tep, hang)
        monkeypatch.setattr(ban_thao, "moi_nhat_cua_hoi_thoai", k.moi_nhat)
        monkeypatch.setattr(ban_thao, "moi_nhat_tren_khuon", k.moi_nhat_tren_khuon)
        monkeypatch.setattr(ban_thao, "tao", k.tao)
        monkeypatch.setattr(ban_thao, "sua", k.sua)
        monkeypatch.setattr(bao_ve, "plan_hieu_luc", lambda sub: "free")
        monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **k: None)
        monkeypatch.setattr(d, "_ghi_traces", lambda *a, **k: None)
        return k

    return _dung


def _ra(phep=(), muc_dich="hoi", yeu_cau="dien_sua", tra_loi="Được.", **ghi_de) -> dict:
    return {
        "muc_dich": muc_dich,
        "mo_ta": "Phiếu đánh giá ¶0 thực tập ⟦0⟧",
        "tra_loi_ngan": tra_loi,
        "quan_sat": [],
        "suy_luan": ["Chỗ ⟦0⟧ là họ tên sinh viên."],
        "can_du_kien": ["giá trị cho ⟦1⟧"],
        "phep_tinh": [],
        "truong": [],
        "khac_biet": [],
        "dieu_khoan": [],
        "khuon": {"tai_lieu": "A", "yeu_cau": yeu_cau, "phep_sua": list(phep), "khong_dat": []},
        **ghi_de,
    }


def _dien(don_vi: int, so: int, gia_tri: str) -> dict:
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": so, "gia_tri": gia_tri, "noi_dung": None, "doan": None}


def _luot(k: _Kho, tl: list[dict], cau: str, ra_mo_hinh: dict, intent=Intent.tai_lieu) -> tuple[dict, _LLM]:
    """Một lượt đi đúng các cạnh của graph sau `route` (`_re_sau_hieu_tai_lieu`)."""
    llm = _LLM(ra_mo_hinh)
    st = {
        "query": cau,
        "cau_hoi_goc": cau,
        "intent": intent,
        "user_sub": "u",
        "hoi_thoai_id": "p",
        "ban_thao_tong_quat_dang_mo": k.nhe(),
    }
    ra = h.hieu_tai_lieu(st, tl, llm, "m")
    if _re_sau_hieu_tai_lieu(ra) == "dung_ban_thao_tong_quat":
        ra = d.dung_ban_thao_tong_quat(ra)
    return assemble(ra, {}, _No(), "m"), llm


def _tl(ten: str, dv: list) -> list[dict]:
    return [
        {"id": V, "viec_id": V, "ten_tep": ten, "don_vi": dv, "co_khuon_goc": True, "dinh_dang": "docx", "so_trang": 1}
    ]


def _chu_nguoi_doc(out: dict) -> str:
    """Mọi chữ người đọc thấy của một lượt (lời đáp, ghi chú, thẻ tài liệu, thẻ bản thảo)."""
    return json.dumps(
        {x: out.get(x) for x in ("answer", "coverage_note", "tai_lieu", "ban_thao")}, ensure_ascii=False, default=str
    )


def _xem(k: _Kho, monkeypatch, cau: str = XEM, **kw) -> tuple[dict, _LLM, list]:
    """Lượt XEM qua `chay_tra_cuu` — graph giả gọi mô hình nếu bị chạy tới."""
    import asyncio

    llm = _LLM(_ra())

    class _Graph:
        async def ainvoke(self, st, *a, **k):
            llm.chat("m", [{"content": ""}])
            return {"result_type": ResultType.tai_lieu, "answer": "đường thường", "traces": {}}

    ghi: list = []
    monkeypatch.setattr(routes, "_g", lambda: _Graph())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **kw: ghi.append(a))
    req = TraCuuRequest(query=cau, **kw.get("req", {}))
    nhe = kw["nhe"] if "nhe" in kw else k.nhe()
    payload, _ = asyncio.run(routes.chay_tra_cuu(req, "u", "t", hoi_thoai_id="p", ban_thao_tong_quat=nhe))
    return payload, llm, ghi


@pytest.mark.parametrize("duong", MAU)
@pytest.mark.parametrize("co_ban_rong", [True, False], ids=["sau_nut_dien_bieu_mau", "chua_co_ban_thao"])
def test_ba_luot_that_dung_lai_dien_roi_xem_ban_da_dien(kho, monkeypatch, duong, co_ban_rong):
    goc, ten, dv, hang, o = _mau(duong)
    k = kho(ten, hang)
    tl = _tl(ten, dv)
    if co_ban_rong:  # nút "Điền biểu mẫu": phiên bản 1 phép rỗng, 0 lượt mô hình
        k.tao("u", "p", ban_thao.LOAI_TONG_QUAT, {}, d.ket_ban_thao_khuon({"viec_id": V, "ten_tep": ten}, []))

    # Lượt 3 — router nói `tai_lieu`, mô hình đọc là `hoi`: động từ "soạn thảo lại" quyết định.
    out, _ = _luot(k, tl, "soạn thảo lại văn bản này cho tôi", _ra(tra_loi="Tôi đã soạn lại ⟦0⟧."))
    assert out["result_type"] is ResultType.ban_thao, out["answer"]
    bt = out["ban_thao"]
    assert (bt["id"], bt["phien_ban"], bt["phep_sua"]) == ("bt-1", 1, [])
    tai, bc = ban_thao.ap_phep_sua("docx", goc, hang, bt["phep_sua"])
    assert tai == goc and bc["bo_qua"] == [], "dựng lại = đúng từng byte tệp tải lên"
    assert "Tôi đã soạn lại" not in out["answer"]

    # Lượt 4 — đầu ra mô hình mà cuộc điều tra thấy: `dien` vào «Họ và tên sinh viên»/«Mã số».
    out, _ = _luot(
        k,
        tl,
        DIEN,
        _ra(
            [_dien(o, 0, TEN), _dien(o, 1, MA)],
            tra_loi=f"Tôi đã điền {TEN} vào chỗ trống số 0 ⟦0⟧ và {MA} vào ⟦1⟧.",
        ),
    )
    assert out["result_type"] is ResultType.ban_thao, out["answer"]
    bt = out["ban_thao"]
    assert (bt["id"], bt["phien_ban"]) == ("bt-1", 2), "một phiên bản MỚI của đúng bản thảo đó"
    assert bt["phep_sua"] == [
        {"loai": "dien", "don_vi": o, "cho_trong": 0, "gia_tri": TEN},
        {"loai": "dien", "don_vi": o, "cho_trong": 1, "gia_tri": MA},
    ]
    assert out["answer"].startswith("Bản thảo phiên bản 2 là chính biểu mẫu bạn tải lên: đã điền 2/")
    chu = _chu_nguoi_doc(out)
    assert "⟦" not in chu and "¶" not in chu
    moi, bc = ban_thao.ap_phep_sua("docx", goc, hang, bt["phep_sua"])
    assert bc["bo_qua"] == []
    assert doc(ten, moi).don_vi[o].noi_dung.startswith(f"Họ và tên sinh viên: {TEN}")
    assert f"Mã số: {MA}" in doc(ten, moi).don_vi[o].noi_dung

    # Lượt 5 — lời xin XEM: 0 lượt gọi mô hình, không phiên bản mới, bản đã điền.
    truoc = k.anh_chup()
    payload, llm, ghi = _xem(k, monkeypatch)
    assert llm.so_lan_goi == 0, "graph (giai_nghia, route, hieu_tai_lieu) không được chạy"
    assert k.anh_chup() == truoc
    assert payload["result_type"] == "ban_thao"
    bt = payload["ban_thao"]
    assert (bt["id"], bt["phien_ban"]) == ("bt-1", 2)
    gia_tri = {(c["don_vi"], c["so"]): c["gia_tri"] for c in bt["khuon"]["cho_trong"]}
    assert (gia_tri[(o, 0)], gia_tri[(o, 1)]) == (TEN, MA)
    tong = len(bt["khuon"]["cho_trong"])
    assert payload["answer"] == (
        f"Đây là bản đã điền (phiên bản 2) của «{ten}»: đã điền 2/{tong} chỗ trống. "
        "Bấm vào chỗ trống trên trang để sửa, hoặc tải Word hoặc PDF."
    )
    assert bt["ten"] == Path(ten).stem, "tên bản thảo khuôn gốc là tên tệp tải lên"
    resp = routes.tra_cuu_response(payload, "t", "cfg")
    assert resp.ban_thao.khuon["viec_id"] == V and resp.ban_thao.ten == Path(ten).stem
    # Cùng dòng traces của một lượt 0 mô hình hôm nay (cache): không trừ hạn mức.
    assert len(ghi) == 1 and ghi[0][4]["result_type"] == "ban_thao" and ghi[0][6] is True


def test_xem_ban_thao_chua_dien_gi_noi_dung_la_tep_tai_len(kho, monkeypatch):
    _, ten, _, hang, _ = _mau(None)
    k = kho(ten, hang)
    k.tao("u", "p", ban_thao.LOAI_TONG_QUAT, {}, d.ket_ban_thao_khuon({"viec_id": V, "ten_tep": ten}, []))
    payload, llm, _ = _xem(k, monkeypatch, "mở bản thảo")
    assert llm.so_lan_goi == 0 and payload["ban_thao"]["phien_ban"] == 1
    assert payload["answer"] == (
        f"Đây là bản thảo (phiên bản 1) đúng như tệp bạn tải lên «{ten}»: chưa điền chỗ trống nào. "
        "Bấm vào chỗ trống trên trang để điền, hoặc tải Word hoặc PDF."
    )


def test_xem_phat_mot_buoc_rieng_tren_luong_SSE(kho, monkeypatch):
    import asyncio

    from src.api.routes_luong import _NHAN

    _, ten, _, hang, _ = _mau(None)
    k = kho(ten, hang)
    k.tao("u", "p", ban_thao.LOAI_TONG_QUAT, {}, d.ket_ban_thao_khuon({"viec_id": V, "ten_tep": ten}, []))
    monkeypatch.setattr(routes, "_g", lambda: None)  # nổ nếu graph bị gọi
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **kw: None)
    buoc: list = []

    async def phat(ten_buoc, chi_tiet):
        buoc.append(ten_buoc)

    asyncio.run(
        routes.chay_tra_cuu(TraCuuRequest(query=XEM), "u", "t", phat, hoi_thoai_id="p", ban_thao_tong_quat=k.nhe())
    )
    assert buoc == ["xem_ban_thao"] and _NHAN["xem_ban_thao"] == "Mở bản thảo đã có"


@pytest.mark.parametrize(
    "tinh_huong",
    ["khong_co_ban_khuon", "ban_html_moi_hon", "dinh_kem_tuoi", "cau_khac"],
)
def test_xem_roi_ve_duong_thuong_khi_khong_du_dieu_kien(kho, monkeypatch, tinh_huong):
    _, ten, _, hang, _ = _mau(None)
    k = kho(ten, hang)
    if tinh_huong != "khong_co_ban_khuon":
        k.tao("u", "p", ban_thao.LOAI_TONG_QUAT, {}, d.ket_ban_thao_khuon({"viec_id": V, "ten_tep": ten}, []))
    html = {"nhe": {"document": "# Đơn", "audit": {}, "viec_id": None, "phep_sua": None}}
    kw = {
        "khong_co_ban_khuon": html,
        # Bản mới nhất của hội thoại là bản HTML (lá đơn soạn SAU khi điền phiếu): "xem
        # bản thảo" không được mở bản khuôn gốc cũ hơn.
        "ban_html_moi_hon": html,
        "dinh_kem_tuoi": {"req": {"tai_lieu_ids": [V]}},
        "cau_khac": {},
    }[tinh_huong]
    payload, llm, ghi = _xem(k, monkeypatch, "phiếu này nói gì" if tinh_huong == "cau_khac" else XEM, **kw)
    assert llm.so_lan_goi == 1 and payload["answer"] == "đường thường"
    assert ghi[0][6] is False


# ─────────────────────────────────────── câu hỏi thật, gác cũ, lời không bịa


@pytest.fixture
def mau_dung(kho):
    goc, ten, dv, hang, o = _mau(None)
    k = kho(ten, hang)
    k.tao("u", "p", ban_thao.LOAI_TONG_QUAT, {}, d.ket_ban_thao_khuon({"viec_id": V, "ten_tep": ten}, []))
    return k, _tl(ten, dv), ten, o


def test_cau_hoi_that_van_la_hoi_dap_va_khong_con_dau_noi_bo(mau_dung):
    k, tl, _, _ = mau_dung
    truoc = k.anh_chup()
    out, _ = _luot(k, tl, HOI, _ra(tra_loi="Ô Mã số ⟦1⟧ ghi mã số sinh viên."))
    assert out["result_type"] is ResultType.tai_lieu
    assert out["answer"] == "Ô Mã số ghi mã số sinh viên."
    ket = out["tai_lieu"]
    assert ket["mo_ta"] == "Phiếu đánh giá thực tập" and ket["suy_luan"] == ["Chỗ là họ tên sinh viên."]
    assert ket["can_du_kien"] == ["giá trị cho"]
    assert k.anh_chup() == truoc, "một câu hỏi không bao giờ đổi bản thảo"


def _dien_hai(k: _Kho, tl: list[dict], o: int) -> None:
    out, _ = _luot(k, tl, DIEN, _ra([_dien(o, 0, TEN), _dien(o, 1, MA)]))
    assert out["ban_thao"]["phien_ban"] == 2


@pytest.mark.parametrize(
    "cau",
    [
        "Văn bản này do ai soạn thảo?",
        "Làm sao để xuất file PDF?",
        "Văn bản này được xuất bản năm nào?",
        "Phiếu này soạn thảo theo quy định nào?",
    ],
)
def test_cau_hoi_co_dong_tu_dung_lai_khong_xoa_gia_tri_da_dien(mau_dung, cau):
    """Review G7: câu hỏi chứa "soạn thảo"/"xuất file" mà router và mô hình đều đọc là
    hỏi thì là hỏi đáp — không phiên bản mới, giá trị đã điền còn nguyên, lời đáp của
    mô hình đi ra."""
    k, tl, _, o = mau_dung
    _dien_hai(k, tl, o)
    truoc = k.anh_chup()
    out, _ = _luot(k, tl, cau, _ra(tra_loi="Câu trả lời thật của mô hình."))
    assert out["result_type"] is ResultType.tai_lieu
    assert out["answer"] == "Câu trả lời thật của mô hình."
    assert k.anh_chup() == truoc


def test_cau_hoi_xuat_file_khi_chua_co_ban_khong_dung_phien_ban_1(kho, monkeypatch):
    _, ten, dv, hang, _ = _mau(None)
    k = kho(ten, hang)
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **kw: pytest.fail("câu hỏi không tiêu hạn mức"))
    out, _ = _luot(k, _tl(ten, dv), "Làm sao để xuất file PDF?", _ra(tra_loi="Bấm nút Tải PDF."))
    assert out["result_type"] is ResultType.tai_lieu and out["answer"] == "Bấm nút Tải PDF."
    assert k.dong == []


def test_loi_xin_dung_lai_dang_cau_hoi_theo_cach_doc_cua_mo_hinh(mau_dung):
    """Lời xin lịch sự "… được không?" có dạng câu hỏi: mô hình đọc là soạn thì vẫn
    dựng lại đúng tệp tải lên (giá trị cũ ở phiên bản trước, bấm Lùi)."""
    k, tl, _, o = mau_dung
    _dien_hai(k, tl, o)
    out, _ = _luot(
        k, tl, "soạn thảo lại văn bản này cho tôi được không?", _ra(muc_dich="sua_ban_thao", yeu_cau="tao_lai")
    )
    assert out["result_type"] is ResultType.ban_thao
    assert (out["ban_thao"]["phien_ban"], out["ban_thao"]["phep_sua"]) == (3, [])


BIA = _ra([_dien(1, 0, "Trần Văn Bịa")], muc_dich="sua_ban_thao", tra_loi="Tôi đã điền Trần Văn Bịa ⟦0⟧.")
KHONG_NGUON = "giá trị không có trong lời bạn nói hay hồ sơ"


@pytest.mark.parametrize(
    "cau,ra_mo_hinh,ly_do",
    [
        # Gác cũ hạ một `sua_ban_thao` của mô hình về `hoi`: lời "đã điền" của nó không đi ra.
        (HOI, _ra(muc_dich="sua_ban_thao", tra_loi="Tôi đã điền mã số vào ⟦1⟧."), "tôi chưa thấy giá trị nào"),
        # Mô hình nói `hoi`, không phép nào, nhưng lời của nó vẫn khẳng định đã điền.
        ("phiếu này gồm mấy mục?", _ra(tra_loi="Tôi đã điền họ tên cho bạn."), "tôi chưa thấy giá trị nào"),
    ],
    ids=["bi_gac_ha_ve_hoi", "loi_khang_dinh_khong_co_phep"],
)
def test_luot_hoi_dap_khong_bao_gio_noi_da_dien(mau_dung, cau, ra_mo_hinh, ly_do):
    k, tl, ten, _ = mau_dung
    truoc = k.anh_chup()
    out, _ = _luot(k, tl, cau, ra_mo_hinh)
    assert out["result_type"] is ResultType.tai_lieu
    assert out["answer"].startswith(f"Lượt này tôi chưa điền gì vào «{ten}»: {ly_do}")
    assert out["answer"].endswith("Hãy nói rõ giá trị cần điền, hoặc bấm vào chỗ trống trên trang.")
    assert "Tôi đã điền" not in _chu_nguoi_doc(out) and "⟦" not in _chu_nguoi_doc(out)
    assert k.anh_chup() == truoc, "không phiên bản mới, không bản thảo mới"


def test_loi_xin_dien_khong_phep_nao_qua_tren_ban_da_co_giu_nguyen_ban_va_noi_ly_do(mau_dung):
    """Bản thảo đã có: lượt xin điền mà mọi phép bị bỏ đi đúng đường `KHONG_DOI_KHUON`
    đã có — câu cố định nói LOẠI lỗi, không phiên bản mới, không lời của mô hình."""
    k, tl, _, _ = mau_dung
    truoc = k.anh_chup()
    out, _ = _luot(k, tl, "Điền họ và tên giúp tôi", BIA)
    assert out["result_type"] is ResultType.soan_thao_hoi
    assert out["answer"].startswith(f"Lượt này tôi chưa áp được thay đổi nào bạn xin ({KHONG_NGUON})")
    assert "Tôi đã điền" not in _chu_nguoi_doc(out) and "⟦" not in _chu_nguoi_doc(out)
    assert k.anh_chup() == truoc


def test_loi_xin_dien_khong_phep_nao_qua_khi_chua_co_ban_khong_dung_phien_ban_1(kho, monkeypatch):
    """Chưa có bản thảo: lời xin điền không áp được gì thì KHÔNG dựng phiên bản 1 (khác
    lời xin dựng lại), không tiêu hạn mức; giá trị người hỏi đưa mà chưa đặt được vẫn
    được kể."""
    _, ten, dv, hang, _ = _mau(None)
    k = kho(ten, hang)
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a, **kw: pytest.fail("không dựng thì không kiểm hạn mức"))
    ra = _ra([_dien(1, 0, "Trần Văn Bịa")], muc_dich="tao_van_ban", tra_loi="Tôi đã điền ⟦0⟧.")
    ra["khuon"]["khong_dat"] = ["Khoa Luật"]
    out, _ = _luot(k, _tl(ten, dv), "điền khoa là Khoa Luật", ra, intent=None)
    assert out["result_type"] is ResultType.soan_thao_hoi and k.dong == []
    assert out["answer"].startswith(f"Lượt này tôi chưa điền gì vào «{ten}»: {KHONG_NGUON}. Hãy nói rõ")
    assert "Chưa đặt được: «Khoa Luật»" in out["answer"]
    assert "Tôi đã điền" not in _chu_nguoi_doc(out) and "⟦" not in _chu_nguoi_doc(out)


def test_dong_tu_dien_ep_luot_soan_ke_ca_khi_router_va_mo_hinh_noi_hoi(mau_dung):
    """Q4: có phép qua kiểm và lời người hỏi là một lời xin điền — lượt soạn, dù router
    nói `tai_lieu` và mô hình nói `hoi`; `yeu_cau` của mô hình (`tao_lai`) không được
    vứt phép người hỏi vừa xin."""
    k, tl, _, o = mau_dung
    out, _ = _luot(k, tl, DIEN, _ra([_dien(o, 0, TEN)], yeu_cau="tao_lai"))
    assert out["result_type"] is ResultType.ban_thao and out["ban_thao"]["phien_ban"] == 2
    assert out["ban_thao"]["phep_sua"] == [{"loai": "dien", "don_vi": o, "cho_trong": 0, "gia_tri": TEN}]


def test_van_ban_khac_cua_mo_hinh_khong_bi_dong_tu_de(mau_dung):
    """Lời xin văn bản KHÁC mà mô hình đã đọc ra (`van_ban_khac`) giữ đường chỉ sang
    checklist, dù câu có "sửa": bộ nhận câu không phân biệt được văn bản nào."""
    k, tl, _, _ = mau_dung
    truoc = k.anh_chup()
    out, _ = _luot(
        k,
        tl,
        "dựa vào phiếu này soạn đơn xin nghỉ, sửa cho trang trọng",
        _ra(muc_dich="tao_van_ban", yeu_cau="van_ban_khac"),
        intent=Intent.soan_thao,
    )
    assert out["answer"].startswith(d.KHONG_DIEN_KHUON) and k.anh_chup() == truoc


def test_tai_lieu_khong_khuon_goc_van_chiu_gac_cu():
    """Gác `_muc_dich_soan_da_xac_nhan` giữ nguyên cho tài liệu KHÔNG có khuôn gốc:
    lời xin điền ở đó không mở đường soạn nào trái ý router."""
    tl = [{"id": V, "ten_tep": "don.docx", "don_vi": _mau(None)[2]}]
    llm = _LLM({**_ra(muc_dich="sua_ban_thao", tra_loi="Đây là phiếu đánh giá."), "van_ban": {}})
    ra = h.hieu_tai_lieu({"query": DIEN, "cau_hoi_goc": DIEN, "intent": Intent.tai_lieu}, tl, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "hoi" and ra["khuon_tong_quat"] is None
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == "Đây là phiếu đánh giá."


@pytest.mark.parametrize(
    "tra_loi,ra_nguoi_doc",
    [
        ("Tôi đã sửa mục 2 như bạn yêu cầu.", h.CHUA_THAY_DOI),
        ("Tôi đã ghi nhận: mục 2 nói về thời gian thực tập.", "Tôi đã ghi nhận: mục 2 nói về thời gian thực tập."),
    ],
    ids=["tu_nhan_da_sua", "ghi_nhan_khong_phai_thay_doi"],
)
def test_luot_ha_ve_hoi_tren_tai_lieu_khong_khuon_khong_bao_gio_noi_da_sua(tra_loi, ra_nguoi_doc):
    """Gác cũ (bản HTML) hạ `sua_ban_thao` về `hoi`: lời "Tôi đã sửa …" của mô hình là
    bịa, câu cố định thay nó; lời không tự nhận thay đổi nào đi ra nguyên."""
    tl = [{"id": V, "ten_tep": "don.docx", "don_vi": _mau(None)[2]}]
    llm = _LLM({**_ra(muc_dich="sua_ban_thao", tra_loi=tra_loi), "van_ban": {}})
    cau = "sửa mục 2 cho trang trọng"
    ra = h.hieu_tai_lieu({"query": cau, "cau_hoi_goc": cau, "intent": Intent.tai_lieu}, tl, llm, "m")
    assert ra["muc_dich_tai_lieu"] == "hoi"
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == ra_nguoi_doc


def test_hai_khuon_khong_ro_tai_lieu_nao_thi_hoi_lai_khong_noi_da_dien():
    """Hai biểu mẫu có khuôn gốc, mô hình không nêu biểu mẫu nào: không áp gì, và lời
    "Tôi đã điền" của nó không đi ra — hỏi lại điền vào biểu mẫu nào."""
    dv = _mau(None)[2]
    v2 = "dddddddd-0000-0000-0000-00000000000d"
    tl = [
        {"id": v, "viec_id": v, "ten_tep": ten, "don_vi": dv, "co_khuon_goc": True, "dinh_dang": "docx", "so_trang": 1}
        for v, ten in ((V, "a.docx"), (v2, "b.docx"))
    ]
    ra_m = _ra(muc_dich="sua_ban_thao", tra_loi="Tôi đã điền họ tên ⟦0⟧.")
    ra_m["khuon"]["tai_lieu"] = ""
    st = {"query": DIEN, "cau_hoi_goc": DIEN, "intent": Intent.tai_lieu, "user_sub": "u", "hoi_thoai_id": "p"}
    ra = h.hieu_tai_lieu(st, tl, _LLM(ra_m), "m")
    assert ra["muc_dich_tai_lieu"] == "hoi" and ra["khuon_tong_quat"] is None
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == (
        "Lượt này tôi chưa điền gì: bạn có 2 biểu mẫu («a.docx», «b.docx») và tôi chưa rõ bạn muốn "
        "điền vào biểu mẫu nào. Hãy nói tên biểu mẫu cùng giá trị cần điền, hoặc bấm vào chỗ trống trên trang."
    )
