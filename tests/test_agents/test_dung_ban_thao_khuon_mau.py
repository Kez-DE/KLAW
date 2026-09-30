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
    assert "Đã điền 4 chỗ trống từ lời bạn nói" in ket["answer"]
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
    # Mọi mục BLLĐ Đ21.1 mà khung chưa có (các bên là khung) đều có mặt; mục thiếu chèn một
    # câu trung tính chừa chỗ điền (mục này không mang `mau`) — không bao giờ "……" trơn.
    assert khoa[0] == "cong_viec" and {"thoi_han", "luong", "bao_hiem", "dao_tao"} <= set(khoa)
    assert "nsdld" not in khoa and "nld" not in khoa
    luong = khoa.index("luong") + 1
    assert cl[0]["can_cu"]["khop_tai_id"] == 7
    ten = cl[luong - 1]["ten"]
    assert ten.startswith("Mức lương") and cl[luong - 1]["doan"] == [
        f"Các bên thỏa thuận về {ten[:1].lower()}{ten[1:]} như sau: {km.CHO}"
    ]
    assert {c["dieu"] for c in ket["ban_thao"]["khuon"]["can_cu"]} == {1, luong}
    assert "đã đặt nội dung chuẩn để bạn xem lại" in ket["answer"] and "còn trống vì luật đòi" not in ket["answer"]


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
    assert "Đã điền" not in ket["answer"], "giá trị mang sang không phải lượt này điền"


def test_chen_dieu_len_dau_gia_tri_dien_tren_trang_khong_truot_sang_dieu_khac(kho):
    ra = _ra(
        gia_tri=[],
        dieu=[
            {"key": None, "ten": "Đặt cọc", "doan": [km.CHO]},
            {"key": None, "ten": "Thời hạn thuê", "doan": [km.CHO]},
        ],
    )
    _luot(_st(), _LLM(ra))
    dv = kho.viec[kho.bt["bt-1"]["viec_id"]]["don_vi"]

    def _duoi(dv, ten):
        i = next(k for k, d in enumerate(dv) if d["noi_dung"].endswith(f". {ten}"))
        return dv[i + 1]["chi_so"]

    # Người dùng điền trên trang hai thân "……" giống hệt nhau.
    kho.bt["bt-1"]["phep_sua"] = [
        {"loai": "dien", "don_vi": _duoi(dv, "Đặt cọc"), "cho_trong": 0, "gia_tri": "50 triệu đồng"},
        {"loai": "dien", "don_vi": _duoi(dv, "Thời hạn thuê"), "cho_trong": 0, "gia_tri": "12 tháng"},
    ]
    them = {"thao_tac": "them_sau", "dieu": 0, "key": None, "ten": "Mục đích thuê", "doan": ["Bên thuê dùng để ở."]}
    ket = _luot(
        _st("thêm điều mục đích thuê lên đầu", nhe=kho.nhe()),
        _LLM(_ra(muc_tieu="sua_ban_dang_co", dieu=None, gia_tri=[], sua_dieu=[them])),
    )
    b = kho.bt["bt-1"]
    dv2 = kho.viec[b["viec_id"]]["don_vi"]
    theo = {p["don_vi"]: p["gia_tri"].strip() for p in b["phep_sua"]}
    assert theo[_duoi(dv2, "Đặt cọc")] == "50 triệu đồng" and theo[_duoi(dv2, "Thời hạn thuê")] == "12 tháng"
    assert _duoi(dv2, "Mục đích thuê") not in theo and "không mang sang" not in ket["answer"]


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
    assert "Đã điền" not in ket["answer"], "lượt không đổi gì không nói đã điền"


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
    # Sửa: loại theo khung đã lưu; tự soạn giữ các bên của khung. Router không nêu loại,
    # hay nêu một loại KHÔNG có khuôn mẫu (nó không có mã nào để gọi lại bản tự soạn):
    # vẫn là lượt trên chính bản đang mở.
    nhe = {"nguon": "khuon_mau", "audit": {"khung": {"loai": None, "ben": BEN, "tieu_de": "T"}}}
    for goi_y in ({}, {"loai": None}, {"loai": "loai_chua_co_khuon_mau"}):
        tq = g._nap_khuon_mau(None, {"soan_thao_goi_y": goi_y, "ban_thao_tong_quat_dang_mo": nhe})
        assert tq["khuon_mau_ngu_canh"]["loai"] is None and tq["khuon_mau_ngu_canh"]["sua"] is True
        assert tq["khuon_mau_ngu_canh"]["ben"] == BEN


NHE_HDLD = {
    "nguon": "khuon_mau",
    "loai_khuon": "hdld",
    "audit": {"khung": {"loai": "hdld", "ben": [], "tieu_de": "HỢP ĐỒNG LAO ĐỘNG"}},
}


@pytest.fixture
def db_nap(monkeypatch):
    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), {}))
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(g.gst, "can_cu_van_ban_co_id", lambda e, d_, a: [])


@pytest.mark.parametrize(
    "dang_mo, loai",
    [
        (NHE_HDLD, "don_khoi_kien"),
        (NHE_HDLD, "don_xin_nghi_viec"),
        ({"nguon": "khuon_mau", "loai_khuon": None, "audit": {"khung": {"loai": None, "ben": BEN}}}, "don_khoi_kien"),
    ],
    ids=["hdld-mo-xin-don-co-mau", "hdld-mo-xin-loai-chua-co-mau", "tu-soan-mo-xin-don-co-mau"],
)
def test_router_neu_loai_khac_loai_dang_mo_la_luot_tao(db_nap, dang_mo, loai):
    """Một khuôn mẫu đang mở mà router nêu một loại KHÁC: người hỏi xin văn bản MỚI —
    khung của loại router nêu (mẫu chính thức khi có), bản đang mở chỉ là tham khảo."""
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": loai}, "ban_thao_tong_quat_dang_mo": dang_mo})[
        "khuon_mau_ngu_canh"
    ]
    assert ng["sua"] is False and ng["khung_cu"] == {}
    assert ng["loai"] == (loai if loai in km.cac_loai() else None)


def test_router_neu_dung_loai_dang_mo_van_la_luot_sua(db_nap):
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "hdld"}, "ban_thao_tong_quat_dang_mo": NHE_HDLD})
    assert ng["khuon_mau_ngu_canh"]["loai"] == "hdld" and ng["khuon_mau_ngu_canh"]["sua"] is True


def test_ban_dang_mo_xin_don_khoi_kien_luu_khung_mau_don(kho, db_nap):
    """Đầu tới cuối: bản tự soạn đang mở, người hỏi xin đơn khởi kiện — bản MỚI trên
    khung Mẫu 23-DS, bản đang mở không đổi."""
    _luot(_st(), _LLM(_ra()))
    st = g._nap_khuon_mau(
        None, _st("soạn đơn khởi kiện đòi tiền lương", nhe=kho.nhe(), soan_thao_goi_y={"loai": "don_khoi_kien"})
    )
    ra = _ra(
        tieu_de=None,
        bo_cuc=None,
        ben=None,
        can_cu=None,
        gia_tri=[],
        dieu=[{"key": "yeu_cau", "ten": "", "doan": ["Buộc bị đơn trả tiền lương còn nợ."]}],
    )
    llm = _LLM(ra)
    ket = _luot(st, llm)
    assert llm.schema["properties"]["muc_tieu"]["enum"] == ["ban_moi"] and "Bản thảo cũ" in llm.prompt
    assert list(kho.bt) == ["bt-1", "bt-2"] and kho.bt["bt-1"]["phien_ban"] == 1
    assert kho.bt["bt-2"]["audit"]["khung"]["loai"] == "don_khoi_kien" and kho.luu_goi[-1]["loai"] == "don_khoi_kien"
    assert ket["ban_thao"]["id"] == "bt-2"


def _ng_thue(monkeypatch, st: dict) -> dict:
    """`_nap_khuon_mau` thật của hợp đồng thuê tài sản (registry), DB giả: một điều khoản
    bắt buộc của BLDS nên dòng căn cứ BLDS là khung."""
    db = {
        7: {
            "id": 7,
            "document_id": "95942",
            "duong_dan": "91/2015/QH13 > Điều 472",
            "noi_dung": "Hợp đồng thuê tài sản là sự thỏa thuận giữa các bên…",
        }
    }
    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), db))
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset({"95942"}))
    monkeypatch.setattr(
        g.gst,
        "can_cu_van_ban_co_id",
        lambda e, d_, a: [
            {"dong": "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015.", "doc_id": "95942"}
        ],
    )
    return g._nap_khuon_mau(None, st)["khuon_mau_ngu_canh"]


def _chu_tep(docx: bytes) -> list[str]:
    return [" ".join(d.noi_dung.split()) for d in doc("k.docx", docx).don_vi]


def test_hop_dong_registry_ben_tuy_loai_tao_roi_doi_loai_khi_sua(kho, monkeypatch):
    """Chủ dự án 2026-09-29: "khi người dùng bảo chỉnh sửa, áp dụng được". Bên thuê là
    công ty ngay lượt tạo; lượt sau "bên cho thuê là Công ty …" dựng lại khối bên cho
    thuê thành khối tổ chức, giá trị của bên kia mang sang, giá trị cũ của bên vừa đổi
    không mạo nhận chỗ mới."""
    cau = (
        "Soạn hợp đồng thuê tài sản: bên cho thuê là ông Nguyễn Văn An, điện thoại 0901234567,"
        " bên thuê là Công ty TNHH An Phát"
    )
    ng = _ng_thue(monkeypatch, {"soan_thao_goi_y": {"loai": "hop_dong_thue_tai_san"}})
    assert {b["khoa"]: b.get("loai") for b in ng["ben"]} == {"ben_cho_thue": "tuy", "ben_thue": "tuy"}
    ra = _ra(
        tieu_de=None,
        bo_cuc=None,
        can_cu=None,
        ben=[{"khoa": "ben_thue", "vai": "Bên thuê", "loai": "to_chuc"}],
        gia_tri=[
            {"ben": "ben_cho_thue", "truong": "ho_ten", "gia_tri": "Nguyễn Văn An"},
            {"ben": "ben_cho_thue", "truong": "dien_thoai", "gia_tri": "0901234567"},
            {"ben": "ben_thue", "truong": "ten_to_chuc", "gia_tri": "Công ty TNHH An Phát"},
        ],
        dieu=[
            {"key": "tai_san_thue", "ten": "Tài sản thuê", "doan": ["Bên cho thuê cho Bên thuê thuê mặt bằng tại ……"]}
        ],
    )
    llm = _LLM(ra)
    ket = _luot(_st(cau, ng=ng), llm)
    assert "ben_thue (cá nhân hay tổ chức; đang là cá nhân)" in llm.prompt
    chu = _chu_tep(kho.luu_goi[0]["docx"])
    assert kho.luu_goi[0]["loai"] == "hop_dong_thue_tai_san"
    assert chu[chu.index("II. BÊN THUÊ (sau đây gọi tắt là Bên thuê):") + 1] == "- Tên tổ chức:"
    assert chu[chu.index("I. BÊN CHO THUÊ (sau đây gọi tắt là Bên cho thuê):") + 1] == "- Họ và tên:"
    assert _gia_tri(kho) == {"Nguyễn Văn An", "0901234567", "Công ty TNHH An Phát"}
    assert "Chưa đặt được" not in ket["answer"]

    cau2 = "bên cho thuê là Công ty Cổ phần Bình Minh"
    nhe = kho.nhe()
    ng2 = _ng_thue(monkeypatch, {"ban_thao_tong_quat_dang_mo": nhe})
    assert ng2["sua"] is True and ng2["loai"] == "hop_dong_thue_tai_san"
    ra2 = _ra(
        muc_tieu="sua_ban_dang_co",
        tieu_de=None,
        bo_cuc=None,
        can_cu=None,
        ben=[{"khoa": "ben_cho_thue", "vai": "Bên cho thuê", "loai": "to_chuc"}],
        gia_tri=[{"ben": "ben_cho_thue", "truong": "ten_to_chuc", "gia_tri": "Công ty Cổ phần Bình Minh"}],
        dieu=None,
        sua_dieu=[],
    )
    ket2 = _luot(_st(cau2, nhe=nhe, ng=ng2), _LLM(ra2))
    b = kho.bt["bt-1"]
    chu2 = _chu_tep(kho.luu_goi[-1]["docx"])
    assert len(kho.luu_goi) == 2 and b["phien_ban"] == 2 and b["doi"][0] == "Bên cho thuê: tổ chức"
    assert chu2[chu2.index("I. BÊN CHO THUÊ (sau đây gọi tắt là Bên cho thuê):") + 1] == "- Tên tổ chức:"
    # Ô ký là MỘT đơn vị của bộ đọc: nhãn vai, ghi chú, chỗ tên.
    assert any(c.startswith("ĐẠI DIỆN BÊN CHO THUÊ (Ký, ghi rõ họ tên, chức vụ") for c in chu2)
    # Công ty bên thuê mang sang; họ tên, điện thoại của ông An không thành của công ty
    # vừa thay ông (dòng "- Số điện thoại:" có ở cả hai khối).
    assert _gia_tri(kho) == {"Công ty Cổ phần Bình Minh", "Công ty TNHH An Phát"}
    assert "không mang sang" in ket2["answer"]


def test_sua_trich_chu_quyet_dinh_ban_hanh_khong_sua_dieu_cua_quy_che(kho, monkeypatch):
    """Tệp hai phần (Mẫu 1.3 NĐ 30/2020 + quy chế kèm theo): "Điều 2" có ở cả hai trang.
    Prompt và "Bản thảo đang có" nói rõ hai phần. Người hỏi trích chữ khung ("Quyết định
    này có hiệu lực …") mà mô hình GIẢ vẫn `thay` Điều 2 — của quy chế: phép sửa bị bỏ,
    giá trị điền vào chỗ trống khung (ngày hiệu lực) vẫn đi, lời đáp nói điền trên trang."""
    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), {}))
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset())
    monkeypatch.setattr(g.gst, "can_cu_van_ban_co_id", lambda e, d_, a: [])
    dieu = [
        {"key": "noi_dung", "ten": "Phạm vi điều chỉnh", "doan": ["Quy chế này quy định việc quản lý tài sản."]},
        {"key": None, "ten": "Nguyên tắc quản lý tài sản", "doan": ["Tài sản phải được lập sổ theo dõi."]},
    ]
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "quy_che_noi_bo"}})["khuon_mau_ngu_canh"]
    tao = _LLM(
        _ra(tieu_de=None, trich_yeu="quản lý tài sản", bo_cuc=None, ben=None, can_cu=None, gia_tri=[], dieu=dieu)
    )
    _luot(_st("Soạn quy chế quản lý tài sản", ng=ng), tao)
    assert "Tệp gồm hai văn bản" in tao.prompt and "số Điều của quy chế nội bộ kèm theo" in tao.prompt
    nhe = kho.nhe()
    assert "khung của mẫu" in nhe["document"] and "- Điều 2. Quyết định này có hiệu lực" in nhe["document"]

    cau = "Sửa Quyết định này có hiệu lực kể từ ngày 01/10/2026"
    thay = {"thao_tac": "thay", "dieu": 2, "key": None, "ten": "Hiệu lực", "doan": [f"{cau[4:]}."]}
    gia_tri = [{"ben": "van_ban", "truong": "ngay_hieu_luc", "gia_tri": "01/10/2026"}]
    sua = _LLM(_ra(muc_tieu="sua_ban_dang_co", dieu=None, sua_dieu=[thay], gia_tri=gia_tri))
    ng2 = g._nap_khuon_mau(None, {"ban_thao_tong_quat_dang_mo": nhe})["khuon_mau_ngu_canh"]
    ket = _luot(_st(cau, nhe=nhe, ng=ng2), sua)
    b = kho.bt["bt-1"]
    assert [c["ten"] for c in b["clauses"]] == ["Phạm vi điều chỉnh", "Nguyên tắc quản lý tài sản"]
    assert b["clauses"][1]["doan"] == ["Tài sản phải được lập sổ theo dõi."], "Điều 2 của quy chế giữ nguyên"
    assert b["phien_ban"] == 2 and "01/10/2026" in _gia_tri(kho)
    assert h.KHUNG_BAN_HANH.split(":")[0] in ket["answer"]


@pytest.mark.parametrize(
    ("loai", "hoan_thanh"),
    [
        # Đường `dieu`: `hieu_tai_lieu` đã tính trên điều mô hình viết.
        ("thoa_thuan_nuoi_con", {"thieu": ["nguoi_truc_tiep_nuoi"], "completeness": 0.8}),
        # Đường `sua_dieu`: `dieu` là None nên `hieu_tai_lieu` không tính gì.
        ("thoa_thuan_nuoi_con", {"thieu": [], "completeness": None}),
        ("hdld", {"thieu": [], "completeness": None}),
    ],
    ids=["registry_dieu", "registry_sua_dieu", "checklist_sua_dieu"],
)
def test_sua_bo_dieu_bat_buoc_la_mot_phat_hien(loai, hoan_thanh):
    """§6 bước 7: lúc sửa không chèn lại gì, điều luật đòi bị bỏ là MỘT phát hiện — cho
    loại có checklist lẫn loại chỉ có `muc` trong mục registry."""
    du, _ = km.them_dieu_bat_buoc([], loai)
    bo = du[0]["key"]
    con = [c for c in du if c["key"] != bo]
    a = d._audit({"hoan_thanh": hoan_thanh}, {"loai": loai}, con, tao=False)
    assert [f["loai"] for f in a["findings"]] == ["thieu_noi_dung"]
    assert a["findings"][0]["thong_diep"] == f"Thiếu nội dung bắt buộc: {du[0]['ten']}"
    assert a["completeness"] is not None and a["completeness"] < 1
    du_ca = d._audit({"hoan_thanh": hoan_thanh}, {"loai": loai}, du, tao=False)
    assert du_ca["findings"] == [] and du_ca["completeness"] == 1.0


# ═══ Lượt sửa không dời giá trị đang có (app thật 2026-09-30, bản thảo 91c288d5) ═══
#
# Lượt 2 "Sửa Điều 3: giá thuê là 10.000.000 đồng …": câu giải nghĩa (`query`) mang lại
# tên hai bên của lượt 1, mô hình chép lại `gia_tri` ĐẢO BÊN, và phép gộp cho giá trị
# mới thắng giá trị đang có — v3 in Bên cho thuê là Trần Thị Bình (kèm ngày sinh người
# dùng điền cho ông An trên trang), Bên thuê là Nguyễn Văn An, chữ ký đảo theo.

DAO_BEN = [
    {"ben": "ben_a", "truong": "ho_ten", "gia_tri": "Trần Thị Bình"},
    {"ben": "ben_b", "truong": "ho_ten", "gia_tri": "Nguyễn Văn An"},
]


def _theo_ben(kho: _Kho, truong: str) -> dict[str, set[str]]:
    """`{ben: {giá trị}}` của một trường trên bản mới nhất — mọi bản sao (khối bên, khối ký)."""
    b = list(kho.bt.values())[-1]
    o = {(x["don_vi"], x["so"]): x["ben"] for x in b["audit"]["khung"]["o"] if x["truong"] == truong}
    ra: dict[str, set[str]] = {}
    for p in b["phep_sua"] or []:
        if k := o.get((p["don_vi"], p["cho_trong"])):
            ra.setdefault(k, set()).add(p["gia_tri"].strip())
    return ra


def _dien_tren_trang(kho: _Kho, ben: str, truong: str, gia_tri: str) -> None:
    """Người dùng bấm chỗ trống trên trang và điền (phiên bản mới cùng tệp)."""
    b = kho.bt["bt-1"]
    x = next(x for x in b["audit"]["khung"]["o"] if x["ben"] == ben and x["truong"] == truong)
    b["phep_sua"] = [*b["phep_sua"], {"loai": "dien", "don_vi": x["don_vi"], "cho_trong": x["so"], "gia_tri": gia_tri}]


def test_sua_dieu_khong_dao_ben_da_dien_du_mo_hinh_chep_lai_gia_tri_dao(kho):
    _luot(_st(), _LLM(_ra()))
    _dien_tren_trang(kho, "ben_a", "ngay_sinh", "15/03/1978")
    cau = "Sửa Điều 2: giá thuê là 10.000.000 đồng mỗi tháng"
    giai_nghia = f"{cau} của hợp đồng thuê giữa bà Trần Thị Bình và ông Nguyễn Văn An"
    thay = {"thao_tac": "thay", "dieu": 2, "key": None, "ten": "Giá thuê", "doan": ["Giá thuê là 10.000.000 đồng."]}
    ra = _ra(muc_tieu="sua_ban_dang_co", dieu=None, sua_dieu=[thay], gia_tri=DAO_BEN)
    ket = _luot(_st(cau, nhe=kho.nhe(), query=giai_nghia), _LLM(ra))
    b = kho.bt["bt-1"]
    assert b["phien_ban"] == 2 and b["clauses"][1]["doan"] == ["Giá thuê là 10.000.000 đồng."]
    assert _theo_ben(kho, "ho_ten") == {"ben_a": {"Nguyễn Văn An"}, "ben_b": {"Trần Thị Bình"}}
    assert _theo_ben(kho, "ngay_sinh") == {"ben_a": {"15/03/1978"}}
    assert b["doi"] == ["Điều 2. Giá thuê"] and "Đã điền" not in ket["answer"]


def test_chi_doi_gia_tri_khong_dao_ben_da_dien(kho):
    _luot(_st(), _LLM(_ra()))
    cau = "ngày sinh bên thuê là 02/02/1990"
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        dieu=None,
        sua_dieu=[],
        gia_tri=[*DAO_BEN, {"ben": "ben_b", "truong": "ngay_sinh", "gia_tri": "02/02/1990"}],
    )
    _luot(_st(cau, nhe=kho.nhe(), query=f"{cau} (hợp đồng giữa Trần Thị Bình và Nguyễn Văn An)"), _LLM(ra))
    assert _theo_ben(kho, "ho_ten") == {"ben_a": {"Nguyễn Văn An"}, "ben_b": {"Trần Thị Bình"}}
    assert _theo_ben(kho, "ngay_sinh") == {"ben_b": {"02/02/1990"}}


def test_nguoi_hoi_neu_ten_truong_thi_doi_duoc_gia_tri_dang_co(kho):
    _luot(_st(), _LLM(_ra()))
    cau = "Đổi lại: bên cho thuê là Trần Thị Bình, bên thuê là Nguyễn Văn An"
    ra = _ra(muc_tieu="sua_ban_dang_co", dieu=None, sua_dieu=[], gia_tri=DAO_BEN)
    ket = _luot(_st(cau, nhe=kho.nhe()), _LLM(ra))
    assert _theo_ben(kho, "ho_ten") == {"ben_a": {"Trần Thị Bình"}, "ben_b": {"Nguyễn Văn An"}}
    assert "Đã điền 4 chỗ trống từ lời bạn nói" in ket["answer"]


def test_nap_khuon_mau_noi_dung_chuan_cua_dieu_bat_buoc_la_nghia_vu_luat_dat(monkeypatch):
    """Nội dung chuẩn (`muc[].mau`) cho một điều luật đòi mà bản soạn để trống: nguyên văn
    NGHĨA VỤ luật đặt ra ("… phải …") ở căn cứ của mục — Khoản 1 khi dòng Điều chỉ là
    tiêu đề. Dòng DB thật (2026-09-30): BLDS Điều 476, 473 và Khoản 1 của chúng."""
    db = {
        256914: {"id": 256914, "document_id": "95942", "duong_dan": "91/2015/QH13 > Điều 476",
                 "tieu_de": "Điều 476. Giao tài sản thuê", "noi_dung": "Điều 476. Giao tài sản thuê"},
        256907: {"id": 256907, "document_id": "95942", "duong_dan": "91/2015/QH13 > Điều 473",
                 "tieu_de": "Điều 473. Giá thuê", "noi_dung": "Điều 473. Giá thuê"},
        256906: {"id": 256906, "document_id": "95942", "duong_dan": "91/2015/QH13 > Điều 472",
                 "tieu_de": "Điều 472. Hợp đồng thuê tài sản", "noi_dung": "Điều 472. Hợp đồng thuê tài sản Hợp đồng"
                 " thuê tài sản là sự thỏa thuận giữa các bên, theo đó bên cho thuê giao tài sản cho bên thuê để sử"
                 " dụng trong một thời hạn, bên thuê phải trả tiền thuê."},
    }  # fmt: skip
    khoan = {
        256915: {"id": 256915, "document_id": "95942", "duong_dan": "91/2015/QH13 > Điều 476 > Khoản 1",
                 "tieu_de": "Khoản 1", "noi_dung": "1. Bên cho thuê phải giao tài sản cho bên thuê đúng số lượng, chất"
                 " lượng, chủng loại, tình trạng, thời điểm, địa điểm đã thoả thuận và cung cấp thông tin cần thiết"
                 " về việc sử dụng tài sản đó."},
        256908: {"id": 256908, "document_id": "95942", "duong_dan": "91/2015/QH13 > Điều 473 > Khoản 1",
                 "tieu_de": "Khoản 1", "noi_dung": "1. Giá thuê do các bên thoả thuận hoặc do người thứ ba xác định theo"
                 " yêu cầu của các bên, trừ trường hợp luật có quy định khác."},
    }  # fmt: skip
    monkeypatch.setattr(g.gst, "requirements", lambda loai: ([], g.gst.load_checklist_cached(loai), db))
    monkeypatch.setattr(
        g.gst, "provisions_theo_duong_dan", lambda dd: {k: r for k, r in khoan.items() if r["duong_dan"] in dd}
    )
    monkeypatch.setattr(g, "hien_thi_luc", lambda engine, as_of: frozenset({"95942"}))
    monkeypatch.setattr(g.gst, "can_cu_khung", lambda *a: [])
    ng = g._nap_khuon_mau(None, {"soan_thao_goi_y": {"loai": "hop_dong_thue_tai_san"}})["khuon_mau_ngu_canh"]
    theo = {m["key"]: m for m in ng["muc"]}
    assert theo["giao_tai_san"]["mau"] == khoan[256915]["noi_dung"][3:]
    # "Giá thuê do các bên thoả thuận …" không đặt nghĩa vụ: câu trung tính của bộ chèn.
    assert "mau" not in theo["gia_thue"] and "mau" not in theo["thoi_han_thue"]
    # Định nghĩa của hợp đồng (Điều 472) có chữ "phải" nhưng không đặt nghĩa vụ cho một bên.
    assert "mau" not in theo["tai_san_thue"]
