"""Quy tắc hiển thị qua ĐƯỜNG THẬT (quyết định 2026-09-28 mục 8–10): API,
chat và soạn thảo chỉ thấy văn bản được hiện; văn bản ẩn trả 404
`khong_hien_thi` kèm văn bản thay thế; câu hỏi nêu tên văn bản ẩn được trả lời
thẳng. 0 lượt LLM (mô hình giả).

Kho RIÊNG của test: bảng TẠM (`pg_temp`) cùng tên `documents`/`provisions`/…
trên MỘT kết nối (`StaticPool`). Postgres tra `pg_temp` trước `public`, nên mọi
truy vấn của route đọc kho này — không một dòng nào của DB dùng chung bị đọc hay
ghi, và dữ liệu đang được nạp song song không làm test đổi màu.
"""

import json
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.services.db import get_engine
from src.services.effectivity import xoa_cache_danh_gia_toan_bo

pytestmark = pytest.mark.integration

VBPL = "https://vbpl.vn/van-ban/chi-tiet/"
CP = "https://vanban.chinhphu.vn/?pageid=27160&docid=1"

# id, số hiệu, loại, tên, tình trạng, ngày ban hành, ngày hiệu lực, ngày hết, link_vbpl, link_chinhphu
VAN_BAN = [
    (
        "k7-song",
        "11/2020/NĐ-CP",
        "Nghị định",
        "Nghị định quy định mức lương tối thiểu vùng mới",
        "CHL",
        "2024-06-30",
        "2024-07-01",
        None,
        VBPL + "900001",
        None,
    ),
    (
        "k7-cu",
        "22/2019/NĐ-CP",
        "Nghị định",
        "Nghị định quy định mức lương tối thiểu vùng",
        "HHL",
        "2019-11-15",
        "2020-01-01",
        "2024-07-01",
        VBPL + "900002",
        None,
    ),
    (
        "k7-mot-phan",
        "33/2021/NĐ-CP",
        "Nghị định",
        "Nghị định thử nghiệm về tiền lương",
        "HHL1P",
        "2020-12-10",
        "2021-01-01",
        None,
        None,
        CP,
    ),
    (
        "k7-khong-link",
        "44/2022/NĐ-CP",
        "Nghị định",
        "Nghị định về an toàn vệ sinh nơi làm việc",
        "CHL",
        "2021-12-01",
        "2022-01-01",
        None,
        None,
        None,
    ),
    (
        "k7-chua-ro",
        "55/2023/TT-BLĐTBXH",
        "Thông tư",
        "Thông tư hướng dẫn trả lương tối thiểu",
        "chua_xac_dinh",
        "2022-12-01",
        "2023-01-01",
        None,
        VBPL + "900005",
        None,
    ),
]
HIEN = {"k7-song", "k7-mot-phan"}
AN = {"k7-cu", "k7-khong-link", "k7-chua-ro"}

# provision id, doc, số hiệu Điều, nội dung
DIEU = [
    (9_000_001, "k7-song", "3", "Mức lương tối thiểu vùng I là 4.960.000 đồng/tháng."),
    (9_000_002, "k7-cu", "3", "Mức lương tối thiểu vùng I là 4.420.000 đồng/tháng."),
    (9_000_003, "k7-mot-phan", "1", "Người lao động được trả lương không thấp hơn mức lương tối thiểu vùng."),
    (9_000_004, "k7-khong-link", "1", "Người sử dụng lao động trả lương tối thiểu và bảo đảm an toàn."),
    (9_000_005, "k7-chua-ro", "1", "Thông tư hướng dẫn cách trả lương tối thiểu vùng."),
]

CANH = [
    # 11/2020 thay 22/2019 (loai 21, đi vào) → văn bản thay thế có link, được hiện.
    ("k7-song", "k7-cu", 21, None),
    # 11/2020 sửa đổi, bổ sung Nghị định 33/2021 (loai 20, cùng thứ bậc) → `mo_ta` nêu tên nó.
    ("k7-song", "k7-mot-phan", 20, None),
    # Căn cứ (loai 3, không phải cạnh hiệu lực): một hiện, một ẩn, một ngoài kho.
    ("k7-mot-phan", "k7-song", 3, None),
    ("k7-mot-phan", "k7-cu", 3, None),
    ("k7-mot-phan", "k7-ngoai-kho", 3, "99/2099/QH99"),
]


@pytest.fixture
def kho(monkeypatch):
    from src.agents import graph_soan_thao, graph_tra_cuu
    from src.api import routes, routes_tim_kiem, routes_van_ban
    from src.services.embedding import from_settings

    e = create_engine(get_engine().url, poolclass=StaticPool)
    with e.begin() as c:
        for bang in ("documents", "provisions", "chunks", '"references"', "sua_doi_dieu_khoan"):
            c.execute(text(f"CREATE TEMP TABLE {bang} (LIKE public.{bang} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"))
        for i, so, loai, ten, tt, bh, hl, het, vbpl, cp in VAN_BAN:
            c.execute(
                text(
                    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, co_quan_ban_hanh,"
                    " ngay_ban_hanh, ngay_hieu_luc, ngay_het_hieu_luc, depth, checksum, link_vbpl, link_chinhphu)"
                    " VALUES (:i, :so, :loai, :ten, :tt, 'Chính phủ', :bh, :hl, :het, 'deep', 'k7', :vbpl, :cp)"
                ),
                {
                    "i": i,
                    "so": so,
                    "loai": loai,
                    "ten": ten,
                    "tt": tt,
                    "bh": date.fromisoformat(bh),
                    "hl": date.fromisoformat(hl),
                    "het": het and date.fromisoformat(het),
                    "vbpl": vbpl,
                    "cp": cp,
                },
            )
        so_cua = {v[0]: v[1] for v in VAN_BAN}
        for pid, doc, so_dieu, nd in DIEU:
            c.execute(
                text(
                    "INSERT INTO provisions (id, document_id, cap, so_hieu_cap, tieu_de, noi_dung, duong_dan, thu_tu)"
                    " VALUES (:p, :d, 'dieu', :s, :t, :n, :dd, 1)"
                ),
                {
                    "p": pid,
                    "d": doc,
                    "s": so_dieu,
                    "t": f"Điều {so_dieu}. Mức lương",
                    "n": nd,
                    "dd": f"{so_cua[doc]} > Điều {so_dieu}",
                },
            )
            c.execute(
                text(
                    "INSERT INTO chunks (id, provision_id, noi_dung_embed, embedding_model, embedding_dim, tsv)"
                    " VALUES (:p, :p, :n, :m, 1024, klaw_tsv(:n))"
                ),
                {"p": pid, "n": f"{so_cua[doc]} > Điều {so_dieu}\n{nd}", "m": from_settings().model},
            )
        for n, (tu, toi, loai, raw) in enumerate(CANH, 1):
            c.execute(
                text(
                    'INSERT INTO "references" (id, from_document_id, to_document_id, loai, raw_text)'
                    " VALUES (:n, :tu, :toi, :loai, :raw)"
                ),
                {"n": n, "tu": tu, "toi": toi, "loai": loai, "raw": raw},
            )
    xoa_cache_danh_gia_toan_bo()
    for m in (routes, routes_tim_kiem, routes_van_ban, graph_tra_cuu, graph_soan_thao):
        monkeypatch.setattr(m, "get_engine", lambda: e)
    yield e
    # `danh_gia_toan_bo` memo theo URL engine — cùng URL với engine thật.
    xoa_cache_danh_gia_toan_bo()
    e.dispose()


# ─────────────────────────────────────────────── danh sách, bộ lọc, tìm kiếm


async def test_danh_sach_bo_loc_tim_kiem_pham_vi_chi_dem_van_ban_duoc_hien(client, kho):
    ds = (await client.get("/api/v1/van-ban", params={"limit": 50})).json()
    assert {r["doc_id"] for r in ds["ket_qua"]} == HIEN and ds["tong"] == len(HIEN)
    for sap_xep in ("moi_nhat", "con_hieu_luc_truoc"):
        r = (await client.get("/api/v1/van-ban", params={"sap_xep": sap_xep})).json()
        assert r["tong"] == len(HIEN) and {x["doc_id"] for x in r["ket_qua"]} == HIEN

    bl = (await client.get("/api/v1/bo-loc")).json()
    assert bl["tong_van_ban"] == ds["tong"], "số cạnh bộ lọc phải bằng số dòng danh sách"
    assert sum(g["so_van_ban"] for g in bl["loai_van_ban"]) == ds["tong"]
    assert {g["gia_tri"] for g in bl["loai_van_ban"]} == {"Nghị định"}, "Thông tư chỉ có ở văn bản ẩn"
    assert (bl["nam_min"], bl["nam_max"], bl["co_quan_khong_ro"]) == (2020, 2024, 0)
    for g in bl["loai_van_ban"]:
        r = (await client.get("/api/v1/van-ban", params={"loai": g["gia_tri"]})).json()
        assert r["tong"] == g["so_van_ban"]
    assert (await client.get("/api/v1/van-ban", params={"loai": "Thông tư"})).status_code == 422, (
        "giá trị lọc chỉ văn bản ẩn mang là một chip trả rỗng — phải nói ra"
    )

    tk = (await client.get("/api/v1/tim-kiem", params={"q": "lương tối thiểu", "limit": 100})).json()
    assert {r["doc_id"] for r in tk["ket_qua"]} == HIEN
    assert (tk["tong_van_ban"], tk["tong_dieu_khoan"]) == (len(HIEN), len(tk["ket_qua"]))

    pv = (await client.get("/api/v1/pham-vi")).json()
    assert {v["doc_id"] for t in ("sau", "nong") for v in pv[t]["van_ban"]} == HIEN


async def test_nhan_hieu_luc_mang_cau_cho_nguoi_doc_va_van_ban_duoc_neu(client, kho):
    ds = (await client.get("/api/v1/van-ban")).json()
    luat = next(r for r in ds["ket_qua"] if r["doc_id"] == "k7-mot-phan")["hieu_luc"]
    assert luat["verdict"] == "mot_phan_khong_xac_dinh"
    assert luat["mo_ta"] == "Đã được sửa đổi, bổ sung bởi 11/2020/NĐ-CP."
    assert luat["van_ban_lien_quan"] == [
        {
            "doc_id": "k7-song",
            "so_ky_hieu": "11/2020/NĐ-CP",
            "ten_van_ban": "Nghị định quy định mức lương tối thiểu vùng mới",
            "lien_ket": VBPL + "900001",
        }
    ]
    hl = (await client.get("/api/v1/van-ban/k7-mot-phan/hieu-luc")).json()
    assert hl["van_ban"]["mo_ta"] == luat["mo_ta"] and hl["van_ban"]["ly_do"], "ly_do ở lại API cho eval"


# ─────────────────────────────────────────────── trang văn bản

_404_CU = {
    "ma": "khong_hien_thi",
    "thong_diep": "Văn bản này không còn hiệu lực nên không có trong phạm vi tra cứu.",
    "thay_the": [
        {
            "doc_id": "k7-song",
            "so_ky_hieu": "11/2020/NĐ-CP",
            "ten_van_ban": "Nghị định quy định mức lương tối thiểu vùng mới",
            "lien_ket": VBPL + "900001",
        }
    ],
}


@pytest.mark.parametrize(
    "duong",
    [
        "/api/v1/van-ban/{i}",
        "/api/v1/van-ban/{i}?so_dieu=3",
        "/api/v1/van-ban/{i}?around=9000002",
        "/api/v1/van-ban/{i}/tim?q=lương",
        "/api/v1/van-ban/{i}/hieu-luc",
        "/api/v1/van-ban/{i}/lien-quan",
    ],
)
async def test_van_ban_het_hieu_luc_tra_404_khong_hien_thi_kem_van_ban_thay(client, kho, duong):
    r = await client.get(duong.format(i="k7-cu"))
    assert r.status_code == 404 and r.json()["detail"] == _404_CU


@pytest.mark.parametrize("doc_id", ["k7-khong-link", "k7-chua-ro"])
async def test_van_ban_an_vi_thieu_link_hay_chua_ro_tinh_trang_KHONG_bi_goi_la_het_hieu_luc(client, kho, doc_id):
    r = await client.get(f"/api/v1/van-ban/{doc_id}")
    assert r.status_code == 404
    assert r.json()["detail"] == {
        "ma": "khong_hien_thi",
        "thay_the": [],
        "thong_diep": "Văn bản này hiện chưa có trong phạm vi tra cứu.",
    }


async def test_van_ban_khong_ton_tai_giu_404_cu_va_van_ban_hien_mo_duoc(client, kho):
    r = await client.get("/api/v1/van-ban/k7-khong-co")
    assert r.status_code == 404 and isinstance(r.json()["detail"], str)
    assert (await client.get("/api/v1/van-ban/k7-mot-phan")).status_code == 200, "HHL1P có link là được hiện"
    lq = (await client.get("/api/v1/van-ban/k7-mot-phan/lien-quan")).json()
    thay = [(g["loai"], v["doc_id"]) for g in lq["nhom"] for v in g["van_ban"]]
    assert sorted(thay) == [(3, "k7-song"), (20, "k7-song")], "văn bản ẩn và văn bản ngoài kho không được liệt kê"


# ─────────────────────────────────────────────── kho, bản thảo


def test_cau_tra_loi_ve_kho_dem_van_ban_duoc_hien_va_noi_thang_ve_van_ban_an(kho):
    from src.services.kho import dung_cau_tra_loi, nap_kho

    k = nap_kho(kho, date(2026, 9, 28))
    assert dung_cau_tra_loi("có bao nhiêu văn bản", k).startswith("Tôi hiện có 2 văn bản")
    assert dung_cau_tra_loi("có Nghị định 22/2019 không", k).startswith(
        "Nghị định số 22/2019/NĐ-CP không còn hiệu lực nên không có trong phạm vi tra cứu. "
        "Văn bản thay thế: 11/2020/NĐ-CP."
    )
    tat_ca = "\n".join(dung_cau_tra_loi(q, k) for q in ("có những gì", "có 33/2021 không", "có 44/2022 không"))
    assert "chưa xác định" not in tat_ca.lower() and "MOJ" not in tat_ca and "không rõ" not in tat_ca.lower()


def test_khoi_can_cu_chi_dan_van_ban_duoc_hien_ke_ca_khi_van_ban_kia_con_hieu_luc(kho):
    from src.agents import graph_soan_thao as gst

    db = {9_000_001: {"document_id": "k7-song"}, 9_000_004: {"document_id": "k7-khong-link"}}
    khoi = gst.can_cu_van_ban(kho, db, date(2026, 9, 28))
    assert len(khoi) == 1 and "11/2020/NĐ-CP" in khoi[0], "44/2022 còn hiệu lực nhưng thiếu link chính thống"


# ─────────────────────────────────────── chat: câu hỏi nêu tên văn bản ẩn


class _Llm:
    """Mô hình giả, ghi lại mọi lời nhắc — để chứng minh nội dung văn bản ẩn
    không bao giờ tới mô hình."""

    def __init__(self):
        self.loi_nhac: list[str] = []

    def chat(self, model, messages, json_schema=None):
        from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
        from src.services.llm import Usage

        self.loi_nhac.append(json.dumps(messages, ensure_ascii=False))
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": []}), Usage(0, 0, 0.0)
        return json.dumps({"answer": "Mức lương tối thiểu vùng I là 4.960.000 đồng/tháng.", "giai_thich": ""}), Usage(
            0, 0, 0.0
        )


@pytest.fixture
def graph_gia(kho, monkeypatch):
    import src.agents.graph_tra_cuu as g
    from src.agents.nodes.generate_claims import Claim
    from src.agents.nodes.route import Intent
    from src.agents.nodes.verify_tier2 import Tier2Verdict

    llm = _Llm()
    monkeypatch.setattr(g, "llm_from_settings", lambda: llm)
    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {**st, "intent": Intent.tra_cuu})
    monkeypatch.setattr(g, "rewrite_query", lambda st, llm, model, prompt_path=None: {**st, "queries": [st["query"]]})
    monkeypatch.setattr(g.Retriever, "dense", lambda self, q, topk=None, hien=None: [])
    monkeypatch.setattr(
        g,
        "generate_claims",
        lambda st, llm, model, prompt_path=None: {
            **st,
            "draft_claims": [Claim(f"Theo {p['so_ky_hieu']}.", p["id"], p["noi_dung"]) for p in st["expanded"]],
        },
    )
    monkeypatch.setattr(
        g,
        "verify_tier2_and_trace",
        lambda t1, *a, **k: (
            [Tier2Verdict(i, True, "ok") for i, r in enumerate([r for r in t1 if r.ok])],
            k.get("prior_traces") or {},
        ),
    )
    return g.build_graph_tra_cuu(), llm


async def test_hoi_dich_danh_van_ban_an_thi_noi_khong_con_hieu_luc_va_neu_van_ban_thay_khong_trich_no(graph_gia):
    from src.api.routes import _payload_cache, tra_cuu_response

    graph, llm = graph_gia
    st = await graph.ainvoke({"query": "mức lương tối thiểu vùng I theo Nghị định 22/2019 là bao nhiêu"})
    assert {c["doc_id"] for c in st["citations"]} <= HIEN and st["citations"], st["result_type"]
    assert not any("4.420.000" in x for x in llm.loi_nhac), "nguyên văn văn bản ẩn không được tới mô hình"
    cau = (
        "Nghị định số 22/2019/NĐ-CP không còn hiệu lực nên không có trong phạm vi tra cứu. "
        "Văn bản thay thế: 11/2020/NĐ-CP."
    )
    assert cau in st["warnings"] and cau not in (st["coverage_note"] or "")
    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    (an,) = res.van_ban_khong_hien_thi
    assert (an.so_ky_hieu, an.thay_the[0].doc_id, an.thay_the[0].lien_ket) == (
        "22/2019/NĐ-CP",
        "k7-song",
        VBPL + "900001",
    )
    doc = json.dumps(res.model_dump(mode="json"), ensure_ascii=False)
    assert "chua_xac_dinh" not in doc.replace('"verdict"', "") and "độ tin cậy" not in doc


async def test_cau_hoi_khong_neu_ten_thi_van_ban_an_im_lang_vang_mat(graph_gia):
    graph, llm = graph_gia
    st = await graph.ainvoke({"query": "mức lương tối thiểu vùng I là bao nhiêu"})
    assert {c["doc_id"] for c in st["citations"]} <= HIEN
    assert not st.get("van_ban_khong_hien_thi") and not any("22/2019" in w for w in st["warnings"])
    assert not any("4.420.000" in x or "44/2022" in x for x in llm.loi_nhac)
