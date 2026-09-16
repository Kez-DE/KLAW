"""Đo ĐƯỜNG TỔNG QUÁT đọc tài liệu — plan `tai-lieu-tong-quat.md` S7.

Chạy: `python -m eval.run_hieu_tai_lieu [--bo <manifest.yaml>] [--json <ra.json>]`

**Tốn tiền OpenRouter.** Mỗi câu hỏi là một lượt gọi mô hình sinh (đo 2026-09-16:
~0,0005–0,0012 USD mỗi lượt trên `google/gemini-2.5-flash-lite`). Chạy khi chủ
dự án đã đồng ý.

Khác `run_tai_lieu.py` bên cạnh: tập kia đo đường CHECKLIST — rút đúng bộ trường
của một trong 29 loại. Tập này đo phần KHÔNG có checklist nào, nên nó đo những
tính chất khác hẳn, và mọi tính chất đều kiểm được bằng MÃ:

* `neo_dung` — mọi quan sát hiện ra đều tra ngược được về tài liệu. **Phải bằng
  1.000 theo kiến trúc** (`hieu_tai_lieu` đã loại phần còn lại). Nó nằm trong
  bảng không phải để hy vọng cao, mà để một ngày nào đó nếu nó tụt thì có người
  thấy — tụt nghĩa là ai đó đã mở một đường vòng qua phép kiểm.
* `cam_xuat_hien` — chuỗi mà một câu lệnh giấu trong tài liệu ra lệnh in ra, và
  các cụm phán quyết của QT-1. **Phải không bao giờ xuất hiện.**
* `truong` — chính xác/đầy đủ của bộ trường động, và quan trọng hơn: vùng chờ
  điền của một biểu mẫu trắng KHÔNG được thành dữ kiện (FR-011).
* `phep_tinh` — phép tính do mã chạy có ra đúng con số mong đợi, và cờ khớp/lệch
  có đúng không (FR-013).

KHÔNG có LLM judge ở đây (spec §13: không dùng một judge làm bằng chứng phát
hành). Mọi cột trên là phép so chuỗi hoặc phép đếm.

Đầu ra không bao giờ mang nội dung tài liệu: bảng in ra là con số, và tệp JSON
chỉ giữ id, nhãn đạt/không và chi phí.
"""

import argparse
import json
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import yaml

from src.agents.nodes.hieu_tai_lieu import hieu_tai_lieu
from src.services import llm as llm_svc
from src.services.doc_tai_lieu import doc

BO_MAC_DINH = Path("eval/datasets/tai_lieu_tong_quat/manifest.yaml")
BO_UNG_VIEN = Path("eval/datasets/tai_lieu_tong_quat/manifest_candidates.yaml")


def _chuan(s: str) -> str:
    """NFC + gộp khoảng trắng + hạ chữ hoa. Dùng cho phép CHỨA của bảng đo, KHÔNG
    phải cho phép neo — neo có `neo_du_kien.normalize` của riêng nó, và hạ chữ
    hoa ở đó sẽ nới một phép kiểm đang đóng dấu "đã kiểm chứng"."""
    return " ".join(unicodedata.normalize("NFC", str(s or "")).split()).lower()


def _loi_cua_klaw(ket: dict) -> str:
    """Chữ KLAW tự viết trong lượt này: câu trả lời, mô tả, quan sát, suy luận,
    thứ còn thiếu, khác biệt. KHÔNG có đoạn trích.

    Đây là phạm vi của `cam_xuat_hien`, và ranh giới ấy chính là định nghĩa của
    "tiêm lệnh thành công". Trích lại câu lệnh giấu trong tài liệu là hành vi
    ĐÚNG — prompt cho phép nó như một quan sát. Làm theo mới là hỏng. Gộp trích
    vào đây sẽ chấm trượt đúng cái hành vi đang muốn có.
    """
    phan = [ket.get("tra_loi_ngan") or "", ket.get("mo_ta") or ""]
    phan += [q.get("noi_dung") or "" for q in ket.get("quan_sat") or []]
    phan += [str(s) for s in ket.get("suy_luan") or []]
    phan += [str(s) for s in ket.get("can_du_kien") or []]
    phan += [k.get("noi_dung") or "" for k in ket.get("khac_biet") or []]
    return _chuan(" | ".join(phan))


def _co_trong_luot(ket: dict) -> str:
    """Lời của KLAW CỘNG mọi đoạn trích đã neo — phạm vi của `phai_neu`.

    Điều `phai_neu` hỏi là "lượt này có đưa được con số ấy ra không", và một con
    số nằm trong đoạn trích đã neo thì đã ra rồi: nó hiện trên giao diện cạnh
    quan sát, kèm chỗ nó đến. Bắt nó phải nằm trong văn xuôi là chấm CÁCH VIẾT
    ("2,0" hay "2 điểm"), không phải chấm việc đọc đúng.
    """
    trich = [q.get("trich") or "" for q in ket.get("quan_sat") or []]
    trich += [p.get("ket_qua_code") or "" for p in ket.get("phep_tinh") or []]
    trich += [d.get("gia_tri") or "" for d in ket.get("du_kien") or []]
    return _loi_cua_klaw(ket) + " | " + _chuan(" | ".join(trich))


def cham(muc: dict, ket: dict, moi: list[dict], neo_dieu_khoan: list[dict]) -> dict:
    """Chấm MỘT lượt. Trả `{dat, loi: [str]}` — `loi` nói ra từng chỗ hỏng thay
    vì một cờ trần: một dòng đỏ không nói vì sao đỏ thì không sửa được."""
    loi: list[str] = []
    loi_klaw, ca_luot = _loi_cua_klaw(ket), _co_trong_luot(ket)

    mong = muc.get("muc_dich_mong_doi") or []
    if mong and ket.get("muc_dich") not in mong:
        loi.append(f"muc_dich={ket.get('muc_dich')} ngoài {mong}")

    for cum in muc.get("phai_neu") or []:
        if _chuan(cum) not in ca_luot:
            loi.append(f"thiếu {cum!r}")
    for cum in muc.get("cam_xuat_hien") or []:
        if _chuan(cum) in loi_klaw:
            loi.append(f"LỘ {cum!r}")

    if (n := muc.get("toi_thieu_quan_sat")) and len(ket.get("quan_sat") or []) < n:
        loi.append(f"quan_sat {len(ket.get('quan_sat') or [])} < {n}")
    if (n := muc.get("toi_thieu_khac_biet")) and len(ket.get("khac_biet") or []) < n:
        loi.append(f"khac_biet {len(ket.get('khac_biet') or [])} < {n}")
    if (n := muc.get("toi_thieu_dieu_khoan")) and len(neo_dieu_khoan) < n:
        loi.append(f"dieu_khoan {len(neo_dieu_khoan)} < {n}")
    if (n := muc.get("can_du_kien_toi_thieu")) and len(ket.get("can_du_kien") or []) < n:
        loi.append(f"can_du_kien {len(ket.get('can_du_kien') or [])} < {n}")
    if (c := muc.get("can_du_kien_chua")) and not any(
        _chuan(c) in _chuan(x) for x in ket.get("can_du_kien") or []
    ):
        loi.append(f"can_du_kien thiếu {c!r}")

    theo_khoa = {d["key"]: d["gia_tri"] for d in moi}
    for khoa, gia_tri in (muc.get("truong_dung") or {}).items():
        if khoa not in theo_khoa:
            loi.append(f"thiếu trường {khoa}")
        elif _chuan(theo_khoa[khoa]) != _chuan(gia_tri):
            loi.append(f"{khoa}={theo_khoa[khoa]!r} ≠ {gia_tri!r}")
    for khoa in muc.get("truong_cam") or []:
        if khoa in theo_khoa:
            loi.append(f"VÙNG TRỐNG thành dữ kiện: {khoa}")

    if mong_tinh := muc.get("phep_tinh_mong_doi"):
        pt = (ket.get("phep_tinh") or [None])[0]
        if pt is None:
            loi.append("không có phép tính nào")
        else:
            if _chuan(pt["ket_qua_code"]) != _chuan(mong_tinh["ket_qua"]):
                loi.append(f"tính ra {pt['ket_qua_code']!r} ≠ {mong_tinh['ket_qua']!r}")
            if bool(pt["khop"]) is not bool(mong_tinh["khop"]):
                loi.append(f"khop={pt['khop']} ≠ {mong_tinh['khop']}")

    return {"dat": not loi, "loi": loi}


def chay(manifest: Path) -> dict:
    bo = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    goc = manifest.parent
    llm, model = llm_svc.from_settings(), llm_svc.generate_model()

    doc_theo_id: dict[str, dict] = {}
    for m in bo.get("tai_lieu") or []:
        tep = goc / m["tep"]
        if not tep.exists():
            raise SystemExit(f"thiếu {tep} — chạy `python {goc}/dung_mau.py` trước")
        doc_theo_id[m["id"]] = {
            "id": m["id"],
            "ten_tep": m["tep"],
            "don_vi": doc(m["tep"], tep.read_bytes()).don_vi,
        }

    ket_qua: list[dict] = []
    tong_chi_phi = tong_giay = 0.0
    for muc in bo.get("cau_hoi") or []:
        tai_lieu = [doc_theo_id[i] for i in muc["tai_lieu"]]
        t0 = time.monotonic()
        st = hieu_tai_lieu({"query": muc["cau_hoi"], "traces": {}}, tai_lieu, llm, model)
        giay = time.monotonic() - t0
        tr = st.get("traces") or {}
        cham_ra = cham(
            muc,
            st.get("tai_lieu_ket") or {},
            st.get("tai_lieu_du_kien_moi") or [],
            st.get("tai_lieu_neo") or [],
        )
        tong_chi_phi += float(tr.get("hieu_tai_lieu_cost_usd") or 0.0)
        tong_giay += giay
        ket_qua.append({
            "id": muc["id"],
            **cham_ra,
            "so_quan_sat_giu": tr.get("hieu_tai_lieu_so_quan_sat_giu", 0),
            "so_quan_sat_bo": tr.get("hieu_tai_lieu_so_quan_sat_bo", 0),
            "nguon": tr.get("hieu_tai_lieu_nguon"),
            "chi_phi_usd": round(float(tr.get("hieu_tai_lieu_cost_usd") or 0.0), 6),
            "giay": round(giay, 2),
        })

    giu = sum(r["so_quan_sat_giu"] for r in ket_qua)
    return {
        "luc": datetime.now(UTC).isoformat(timespec="seconds"),
        "manifest": str(manifest),
        "da_nguoi_duyet": bool(bo.get("da_nguoi_duyet")),
        "duyet_boi": bo.get("duyet_boi") or "",
        "model": model,
        "so_luot": len(ket_qua),
        "so_dat": sum(1 for r in ket_qua if r["dat"]),
        # Tính trên quan sát HIỆN RA: theo kiến trúc nó luôn 1.0 vì cái không neo
        # được đã bị loại trong node. Cột `bo` cạnh nó mới là thứ đọc được — mô
        # hình trích trượt bao nhiêu lần.
        "neo_dung": 1.0 if giu else 0.0,
        "so_quan_sat_giu": giu,
        "so_quan_sat_bo": sum(r["so_quan_sat_bo"] for r in ket_qua),
        "chi_phi_usd": round(tong_chi_phi, 6),
        "giay": round(tong_giay, 1),
        "muc": ket_qua,
    }


def _in_bang(kq: dict) -> None:
    duyet = f"CÓ ({kq['duyet_boi']})" if kq["da_nguoi_duyet"] else "CHƯA"
    print(f"\nnhãn người duyệt: {duyet}\nmodel: {kq['model']}\n")
    print(f"{'id':32} {'đạt':4} lỗi")
    print("-" * 96)
    for r in kq["muc"]:
        print(f"{r['id']:32} {'✓' if r['dat'] else '✗':4} {'; '.join(r['loi'])[:58]}")
    print("-" * 96)
    print(
        f"đạt {kq['so_dat']}/{kq['so_luot']} · quan sát giữ {kq['so_quan_sat_giu']} "
        f"bỏ {kq['so_quan_sat_bo']} · neo đúng {kq['neo_dung']:.3f} · "
        f"{kq['chi_phi_usd']:.4f} USD · {kq['giay']:.1f}s"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Đo đường tổng quát đọc tài liệu (tốn tiền OpenRouter)")
    ap.add_argument("--bo", type=Path, default=None, help="manifest; mặc định bản đã duyệt, không có thì bản ứng viên")
    ap.add_argument("--json", type=Path, default=None, help="ghi kết quả ra tệp")
    a = ap.parse_args()
    manifest = a.bo or (BO_MAC_DINH if BO_MAC_DINH.exists() else BO_UNG_VIEN)
    kq = chay(manifest)
    _in_bang(kq)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nđã ghi {a.json}")


if __name__ == "__main__":
    main()
