"""Lượt soạn trên khuôn mẫu, đầu tới cuối trong một tiến trình: `hieu_tai_lieu` (v3, mô
hình GIẢ) → `dung_ban_thao_tong_quat` → `assemble` — thiết kế `khuon-mau-thiet-ke.md`
§4, §8. Không DB, không LibreOffice, 0 lượt mô hình trả phí: bộ dựng và bộ đọc THẬT,
còn chỗ lưu (`ban_thao.tao/sua/…`, việc đọc) là một kho trong bộ nhớ.
"""

import json

import pytest

from src.agents import graph_tra_cuu as g
from src.agents.nodes import dung_ban_thao_tong_quat as d
from src.agents.nodes import hieu_tai_lieu as h
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent
from src.services import ban_thao, bao_ve
from src.services import khuon_mau as km
from src.services.doc_tai_lieu import DonViVanBan, doc
from src.services.tai_lieu import _hang_don_vi

SUB, PID = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
CAU = "Soạn hợp đồng thuê tài sản giữa tôi Nguyễn Văn An là bên cho thuê và Trần Thị Bình là bên thuê"
BEN = [
    {"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan"},
    {"khoa": "ben_b", "vai": "Bên thuê", "loai": "ca_nhan"},
]
DIEU = [
    {"key": None, "ten": "Tài sản thuê", "doan": ["Bên A cho Bên B thuê căn hộ tại ……"]},
    {"key": None, "ten": "Giá thuê", "doan": ["Giá thuê …… đồng/tháng."]},
]


class _Usage:
    token_in, token_out, cost_usd = 10, 20, 0.001


class _LLM:
    def __init__(self, ra: dict):
        self.ra, self.goi, self.prompt, self.schema = ra, 0, None, None

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        self.goi += 1
        self.prompt, self.schema = messages[-1]["content"], json_schema
        return json.dumps(self.ra, ensure_ascii=False), _Usage()


def _ra(**kw) -> dict:
    ra = {
        "muc_tieu": "ban_moi",
        "tieu_de": "Hợp đồng thuê tài sản",
        "trich_yeu": None,
        "bo_cuc": "hop_dong",
        "ben": BEN,
        "can_cu": ["91/2015/QH13"],
        "gia_tri": [
            {"ben": "ben_a", "truong": "ho_ten", "gia_tri": "Nguyễn Văn An"},
            {"ben": "ben_b", "truong": "ho_ten", "gia_tri": "Trần Thị Bình"},
            # Mô hình bịa: không có trong lời người hỏi.
            {"ben": "ben_b", "truong": "dien_thoai", "gia_tri": "0987654321"},
        ],
        "dieu": DIEU,
        "sua_dieu": None,
        "khong_dat": [],
    }
    ra.update(kw)
    return ra


class _Kho:
    """Chỗ lưu giả: việc đọc (tệp khuôn mẫu) và bản thảo, đủ hình dạng của `ban_thao`."""

    def __init__(self):
        self.viec: dict[str, dict] = {}
        self.bt: dict[str, dict] = {}
        self.traces = 0
        self.luu_goi: list[dict] = []

    def luu(self, sub, pid, loai, tieu_de, docx):
        vid = f"viec-{len(self.viec) + 1}"
        dl = doc("k.docx", docx)
        self.viec[vid] = {
            "don_vi": [_hang_don_vi(x) for x in dl.don_vi],
            "goc": dl.don_vi,
            "loai": loai,
            "nguon": "khuon_mau",
            "ten_tep": ban_thao._ten_tep_khuon_mau(tieu_de),
        }
        self.luu_goi.append({"loai": loai, "tieu_de": tieu_de, "docx": docx})
        v = self.viec[vid]
        return {"viec_id": vid, "don_vi": v["don_vi"], "don_vi_goc": v["goc"], "so_trang": 1, "ten_tep": v["ten_tep"]}

    def _dong(self, id: str) -> dict:
        r = dict(self.bt[id])
        v = self.viec.get(r.get("viec_id") or "")
        k = (
            {"dinh_dang": "docx", "so_trang": 1, "don_vi": v["don_vi"], "ten_tep": v["ten_tep"], "nguon": "khuon_mau"}
            if v
            else None
        )
        return {
            **r,
            "khuon": ban_thao._khuon_tu(k, r.get("viec_id"), r.get("phep_sua"), r),
            "ten_tep": (v or {}).get("ten_tep"),
        }

    def tao(self, sub, pid, loai, facts, ket):
        id = f"bt-{len(self.bt) + 1}"
        self.bt[id] = {
            "id": id,
            "hoi_thoai_id": pid,
            "loai": loai,
            "facts": facts,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "phien_ban": 1,
            "so_lan_sua": 0,
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
        }
        return self._dong(id)

    def sua(self, sub, id, facts, ket, *, tang=1, doi=None):
        cu = self.bt[id]
        self.bt[id] = {
            **cu,
            "document": ket["document"],
            "clauses": ket["clauses"],
            "audit": ket["audit_report"],
            "phien_ban": cu["phien_ban"] + 1,
            "so_lan_sua": cu["so_lan_sua"] + tang,
            "viec_id": ket.get("viec_id"),
            "phep_sua": ket.get("phep_sua"),
            "doi": doi,
        }
        return self._dong(id)

    def moi_nhat(self, sub, pid):
        ds = [b for b in self.bt.values() if b.get("viec_id") in self.viec]
        return self._dong(ds[-1]["id"]) if ds else None

    def nhe(self) -> dict | None:
        """Dòng nhẹ `ban_thao_tong_quat_dang_mo` của bản mới nhất."""
        if not self.bt:
            return None
        b = list(self.bt.values())[-1]
        v = self.viec.get(b.get("viec_id") or "") or {}
        return {
            "document": b["document"],
            "audit": b["audit"],
            "viec_id": b.get("viec_id"),
            "phep_sua": b.get("phep_sua"),
            "nguon": v.get("nguon"),
            "loai_khuon": v.get("loai"),
        }


@pytest.fixture
def kho(monkeypatch):
    k = _Kho()
    monkeypatch.setattr(ban_thao, "luu_khuon_mau", k.luu)
    monkeypatch.setattr(ban_thao, "tao", k.tao)
    monkeypatch.setattr(ban_thao, "sua", k.sua)
    monkeypatch.setattr(ban_thao, "moi_nhat_khuon_mau", k.moi_nhat)
    monkeypatch.setattr(ban_thao, "don_vi_khuon", lambda sub, vid: k.viec[vid]["don_vi"])
    monkeypatch.setattr(d.tl, "don_vi_cua", lambda engine, vid, sub: k.viec[vid]["goc"])
    monkeypatch.setattr(d, "get_engine", lambda: None)
    monkeypatch.setattr(bao_ve, "plan_hieu_luc", lambda sub: "free")
    monkeypatch.setattr(bao_ve, "kiem_han_muc", lambda *a: None)
    monkeypatch.setattr(d, "_ghi_traces", lambda *a, **kw: setattr(k, "traces", k.traces + 1))
    monkeypatch.setattr(
        d.gst,
        "can_cu_theo_so_hieu",
        lambda engine, so, as_of: (
            [{"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015.", "doc_id": "95942"}]
            if "91/2015/QH13" in so
            else []
        ),
    )
    return k


def _st(cau: str = CAU, nhe: dict | None = None, ng: dict | None = None, **kw) -> dict:
    sua = (nhe or {}).get("nguon") == "khuon_mau"
    return {
        "query": cau,
        "cau_hoi_goc": cau,
        "intent": Intent.soan_thao,
        "user_sub": SUB,
        "hoi_thoai_id": PID,
        "ban_thao_tong_quat_dang_mo": nhe,
        "khuon_mau_ngu_canh": ng
        or {
            "loai": None,
            "sua": sua,
            "khung_cu": ((nhe or {}).get("audit") or {}).get("khung") or {} if sua else {},
            "muc": [],
            "khoa": [],
            "can_cu": [],
            "bat_buoc": [],
            "ben": [],
        },
        **kw,
    }


def _luot(st: dict, llm) -> dict:
    ra = h.hieu_tai_lieu(st, [], llm, "m")
    assert g._re_sau_hieu_tai_lieu(ra) == "dung_ban_thao_tong_quat"
    ra = d.dung_ban_thao_tong_quat(ra)
    return assemble(ra, {}, None, "")


def _gia_tri(kho: _Kho) -> set[str]:
    b = list(kho.bt.values())[-1]
    return {p["gia_tri"].strip() for p in b["phep_sua"] or []}


def test_tao_luu_viec_khuon_mau_va_phien_ban_1_voi_phep_dien(kho):
    llm = _LLM(_ra())
    ket = _luot(_st(), llm)
    assert llm.goi == 1 and "prompts/hieu_tai_lieu.v3.md" and "Bạn soạn NỘI DUNG ĐIỀU KHOẢN" in llm.prompt
    assert ket["result_type"] == ResultType.ban_thao
    bt = ket["ban_thao"]
    assert bt["khuon"]["nguon"] == "khuon_mau" and bt["phien_ban"] == 1 and kho.traces == 1
    assert kho.luu_goi[0]["loai"] is None and kho.luu_goi[0]["tieu_de"] == "HỢP ĐỒNG THUÊ TÀI SẢN"
    # Tên các bên điền ở khối thông tin VÀ dưới khối ký; số điện thoại bịa bị bỏ.
    assert _gia_tri(kho) == {"Nguyễn Văn An", "Trần Thị Bình"}
    assert sum(1 for p in kho.bt["bt-1"]["phep_sua"] if p["gia_tri"].strip() == "Nguyễn Văn An") == 2
    assert "0987654321" not in ket["answer"]
    assert bt["khuon"]["can_cu"][0]["doc_id"] == "95942"


def test_khuon_mau_co_checklist_moi_dieu_mang_can_cu_mo_duoc(kho):
    ng = {
        "loai": "hdld",
        "sua": False,
        "tieu_de": "HỢP ĐỒNG LAO ĐỘNG",
        "bo_cuc": "hop_dong",
        "ben": [{"khoa": "nsdld", "vai": "BÊN A"}, {"khoa": "nld", "vai": "BÊN B"}],
        "khoa": ["cong_viec", "luong"],
        "bat_buoc": ["cong_viec", "luong"],
        "can_cu": [],
        "muc": [
            {
                "key": "cong_viec",
                "ten": "Công việc",
                "trich": "",
                "can_cu": {
                    "duong_dan": "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm c",
                    "doc_id": "139264",
                    "khop_tai_id": 7,
                },
            },
            {
                "key": "luong",
                "ten": "Mức lương",
                "trich": "",
                "can_cu": {
                    "duong_dan": "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm đ",
                    "doc_id": "139264",
                    "khop_tai_id": 8,
                },
            },
        ],
    }
    ra = _ra(
        tieu_de=None,
        bo_cuc=None,
        ben=None,
        can_cu=None,
        gia_tri=[],
        dieu=[{"key": "cong_viec", "ten": "Công việc", "doan": ["Làm lập trình viên."]}],
    )
    ket = _luot(_st("soạn hợp đồng lao động", ng=ng), _LLM(ra))
    cl = kho.bt["bt-1"]["clauses"]
    khoa = [c["key"] for c in cl]
    # Mọi mục BLLĐ Đ21.1 mà khung chưa có (các bên là khung) đều có mặt; mục thiếu chèn trống.
    assert khoa[0] == "cong_viec" and {"thoi_han", "luong", "bao_hiem", "dao_tao"} <= set(khoa)
    assert "nsdld" not in khoa and "nld" not in khoa
    luong = khoa.index("luong") + 1
    assert cl[0]["can_cu"]["khop_tai_id"] == 7 and cl[luong - 1]["doan"] == [km.CHO]
    assert {c["dieu"] for c in ket["ban_thao"]["khuon"]["can_cu"]} == {1, luong}
    assert "Điều còn trống vì luật đòi" in ket["answer"]


def test_sua_dieu_dung_lai_tep_moi_mang_phep_dien_sang(kho):
    _luot(_st(), _LLM(_ra()))
    v1 = kho.bt["bt-1"]["viec_id"]
    them = {
        "thao_tac": "them_sau",
        "dieu": 2,
        "key": None,
        "ten": "Phạt vi phạm",
        "doan": ["Bên vi phạm chịu phạt theo thỏa thuận."],
    }
    ket = _luot(
        _st("thêm điều về phạt vi phạm", nhe=kho.nhe()),
        _LLM(_ra(muc_tieu="sua_ban_dang_co", dieu=None, gia_tri=[], sua_dieu=[them])),
    )
    b = kho.bt["bt-1"]
    assert b["viec_id"] != v1 and b["phien_ban"] == 2 and b["so_lan_sua"] == 1
    assert [c["ten"] for c in b["clauses"]] == ["Tài sản thuê", "Giá thuê", "Phạt vi phạm"]
    assert b["clauses"][:2] == kho.bt["bt-1"]["clauses"][:2]
    assert _gia_tri(kho) == {"Nguyễn Văn An", "Trần Thị Bình"}, "giá trị các bên mang sang tệp mới"
    assert "Phạt vi phạm" in ket["answer"]


def test_chi_doi_gia_tri_giu_nguyen_tep(kho):
    _luot(_st(), _LLM(_ra(gia_tri=[])))
    v1 = kho.bt["bt-1"]["viec_id"]
    cau = "địa chỉ bên thuê là 12 Lý Thường Kiệt, Hà Nội"
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        dieu=None,
        sua_dieu=[],
        gia_tri=[{"ben": "ben_b", "truong": "noi_cu_tru", "gia_tri": "12 Lý Thường Kiệt, Hà Nội"}],
    )
    _luot(_st(cau, nhe=kho.nhe()), _LLM(ra))
    b = kho.bt["bt-1"]
    assert b["viec_id"] == v1 and b["phien_ban"] == 2 and _gia_tri(kho) == {"12 Lý Thường Kiệt, Hà Nội"}


def test_khong_doi_gi_la_ban_dang_co_khong_phien_ban_moi(kho):
    _luot(_st(), _LLM(_ra()))
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        dieu=None,
        gia_tri=[],
        sua_dieu=[{"thao_tac": "thay", "dieu": 9, "key": None, "ten": "x", "doan": ["y."]}],
    )
    ket = _luot(_st("sửa điều 9", nhe=kho.nhe()), _LLM(ra))
    assert kho.bt["bt-1"]["phien_ban"] == 1
    assert h.CHUA_RO_DIEU.rstrip(".") in ket["answer"]


def test_ban_html_cu_chi_la_tham_khao_tao_ban_moi(kho):
    html = {
        "document": "# ĐƠN\n\n## 1. Nội dung\n\nTôi xin nghỉ.\n",
        "audit": {"muc_kiem": "tong_quat"},
        "viec_id": None,
        "phep_sua": None,
        "nguon": None,
        "loai_khuon": None,
    }
    llm = _LLM(_ra())
    _luot(_st(nhe=html), llm)
    assert llm.schema["properties"]["muc_tieu"]["enum"] == ["ban_moi"] and llm.schema["properties"]["sua_dieu"] == {
        "type": "null"
    }
    assert "Bản thảo cũ (chỉ để tham khảo)" in llm.prompt
    assert list(kho.bt) == ["bt-1"] and kho.bt["bt-1"]["viec_id"] == "viec-1"


def test_qua_tran_trang_khong_luu_khong_traces(kho, monkeypatch):
    def _dai(*a):
        raise ban_thao.KhuonMauChuaDungError(
            ban_thao.LOI_KHUON_MAU_DAI.format(so=12, tran=10, dieu="bản thảo"), so_trang=12
        )

    monkeypatch.setattr(ban_thao, "luu_khuon_mau", _dai)
    ket = _luot(_st(), _LLM(_ra()))
    assert kho.bt == {} and kho.traces == 0
    assert ket["result_type"] == ResultType.soan_thao_hoi and "«Điều" in ket["answer"] and "12 trang" in ket["answer"]


def test_luot_anh_khi_khuon_mau_dang_mo_xin_dien_KHONG_DIEN_TU_ANH(kho):
    _luot(_st(), _LLM(_ra()))
    nhe = kho.nhe()
    anh = [
        {
            "id": "anh-1",
            "viec_id": "anh-1",
            "ten_tep": "cccd.jpg",
            "co_khuon_goc": False,
            "don_vi": [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Họ và tên: Lê Văn C")],
        }
    ]
    st = g._nap_ban_thao_dang_mo(
        {**_st("điền thông tin theo ảnh này vào hợp đồng", nhe=nhe), "khuon_mau_ngu_canh": None}, anh
    )
    assert st["ban_thao_tong_quat_dang_mo"] is None and st["khuon_mau_dang_mo"] == nhe
    ra = d.dung_ban_thao_tong_quat(
        {
            **st,
            "muc_dich_tai_lieu": "tao_van_ban",
            "van_ban_tong_quat": {
                "tieu_de": "X",
                "muc": [{"ten": "a", "vung": "than", "khoi": [{"noi_dung": "b", "bang": []}]}],
            },
        }
    )
    assert ra["ban_thao_ket"] is None and ra["ban_thao_tong_quat_loi"].startswith(
        "Bản thảo «Hợp đồng thuê tài sản» là tệp Word"
    )
    assert list(kho.bt) == ["bt-1"] and kho.bt["bt-1"]["phien_ban"] == 1 and kho.bt["bt-1"]["viec_id"] == "viec-1"


def test_nap_khuon_mau_chuan_bi_muc_can_cu_va_nen(monkeypatch):
    """Phần DB của lượt v3 (`graph_tra_cuu._nap_khuon_mau`): loại từ router khi tạo, từ
    khung đã lưu khi sửa; mục checklist trừ khung (các bên); căn cứ từng mục mở được."""
    cl = g.gst.load_checklist_cached("hdld")
    db = {
        7: {
            "id": 7,
            "document_id": "139264",
            "duong_dan": "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm c",
            "noi_dung": "c) Công việc và địa điểm làm việc;",
        }
    }
    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), db))
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset({"139264"}))
    monkeypatch.setattr(g.gst, "can_cu_van_ban_co_id", lambda e, d_, a: [{"dong": "Căn cứ X.", "doc_id": "139264"}])
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "hdld"}})["khuon_mau_ngu_canh"]
    assert ng["loai"] == "hdld" and ng["sua"] is False and ng["can_cu"][0]["doc_id"] == "139264"
    assert "nld" not in ng["khoa"] and set(ng["bat_buoc"]) == set(ng["khoa"]) == {m["key"] for m in cl.muc} - {
        "nsdld",
        "nld",
    }
    cv = next(m for m in ng["muc"] if m["key"] == "cong_viec")
    assert cv["can_cu"] == {"duong_dan": db[7]["duong_dan"], "doc_id": "139264", "khop_tai_id": 7}
    assert cv["trich"].startswith("c) Công việc")
    # Đơn: chỉ mục cố định của mẫu; các bên, ngày, Tòa án là khung.
    don = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "don_khoi_kien"}})["khuon_mau_ngu_canh"]
    assert don["khoa"] == ["tai_lieu", "thong_tin_khac", "yeu_cau"] and don["co_dieu"] is False
    assert set(don["bat_buoc"]) == {"yeu_cau", "tai_lieu"}
    # Sửa: loại theo khung đã lưu, không theo router; tự soạn giữ các bên của khung.
    nhe = {"nguon": "khuon_mau", "audit": {"khung": {"loai": None, "ben": BEN, "tieu_de": "T"}}}
    tq = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "hdld"}, "ban_thao_tong_quat_dang_mo": nhe})
    assert tq["khuon_mau_ngu_canh"]["loai"] is None and tq["khuon_mau_ngu_canh"]["sua"] is True
    assert tq["khuon_mau_ngu_canh"]["ben"] == BEN
