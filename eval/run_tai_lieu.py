"""Đo việc rút dữ kiện từ tài liệu người dùng — SC-001 và SC-002 của spec 2026-09-15.

Chạy: `python -m eval.run_tai_lieu [--bo <manifest.yaml>]`

Hai cột của bảng kết quả trả lời hai câu hỏi khác nhau:

* **trich_khop** (SC-001) — trong số dữ kiện hiện ra cho người dùng, bao nhiêu
  phần có đoạn trích tra ngược được. Con số này phải là **1.0 theo kiến trúc**:
  `neo_du_kien.loc_co_neo` đã loại phần còn lại từ trong node. Nó nằm trong bảng
  không phải để hy vọng cao, mà để **một ngày nào đó nếu nó tụt xuống thì có
  người thấy** — tụt nghĩa là ai đó đã mở một đường vòng qua phép kiểm.
* **truong_dung** (SC-002) — trong số trường bắt buộc của loại văn bản, bao
  nhiêu phần rút đúng. Đây là số đo chất lượng thật, có ngưỡng 80%.

Tập mẫu do chủ dự án duyệt tay, cùng khuôn `golden_qa.yaml`: tài liệu tự dựng,
không dùng giấy tờ thật của người dùng, vì giấy tờ thật chứa thông tin cá nhân
của bên thứ ba và không đưa vào kho mã được.
"""

import argparse
import json
import re
import subprocess
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import yaml

BO_MAC_DINH = Path("eval/datasets/tai_lieu_mau/manifest.yaml")
NGUONG_TRUONG_DUNG = 0.80

_KHOANG = re.compile(r"\s+")
_PHAN_CACH_SO = re.compile(r"(?<=\d)[.,\s](?=\d)")


def bang_nhau(a: str, b: str) -> bool:
    """Hai giá trị có phải cùng một dữ kiện không.

    Bỏ qua CÁCH VIẾT, không bỏ qua GIÁ TRỊ. "20.000.000" và "20000000" là cùng
    một mức lương — dấu chấm ở đây là phân cách hàng nghìn, không phải nội dung.
    Nhưng dấu tiếng Việt thì KHÔNG được bỏ, cùng lý do `verify_tier1.normalize`
    không bỏ: trong tiếng Việt dấu là chữ, và "Phạt tiền" với "phat tien" là hai
    thứ khác nhau.

    Hoa thường được bỏ qua ở đây (khác tầng 1) vì đây là so GIÁ TRỊ ĐÃ RÚT với
    NHÃN người duyệt gõ tay, không phải so một trích dẫn với văn bản gốc.
    """

    def chuan(s: str) -> str:
        s = unicodedata.normalize("NFC", str(s or "")).strip().lower()
        s = _KHOANG.sub(" ", s)
        return _PHAN_CACH_SO.sub("", s)

    return chuan(a) == chuan(b)


def diem_trich(du_kien: list[dict]) -> float:
    """SC-001 — tỉ lệ dữ kiện hiện ra mà đoạn trích tra ngược được.

    Không có dữ kiện nào thì là 1.0, không phải 0: "không hiện gì" không vi phạm
    lời hứa "mọi thứ hiện ra đều có bằng chứng". Chia cho 0 ở đây sẽ biến một
    tài liệu trống thành một lỗi nghiêm trọng giả.
    """
    if not du_kien:
        return 1.0
    ok = sum(1 for d in du_kien if str(getattr(d["neo"], "ly_do", d["neo"])) == "ok")
    return ok / len(du_kien)


def diem_truong(du_doan: dict, nhan: dict) -> float:
    """SC-002 — tỉ lệ trường trong nhãn được rút đúng.

    Mẫu số là NHÃN, không phải phần rút được: bỏ trường thiếu ra khỏi mẫu số sẽ
    thưởng cho việc rút được ít, và một hệ thống rút đúng một trường rồi im lặng
    sẽ đạt 100%. Trường rút thừa không có trong nhãn thì không được tính điểm,
    nhưng cũng không bị phạt ở cột này — nó là một phép đo khác.
    """
    if not nhan:
        return 1.0
    dung = sum(1 for k, v in nhan.items() if bang_nhau(du_doan.get(k, ""), v))
    return dung / len(nhan)


def _commit_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "khong-ro"


def chay(manifest: Path) -> dict:
    """Chạy toàn bộ tập mẫu qua đường thật: đọc tệp -> rút -> neo."""
    from src.agents.nodes.rut_du_kien import rut_du_kien
    from src.services import llm as llm_svc
    from src.services.doc_tai_lieu import doc

    bo = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    muc = bo.get("items") or []
    goc = manifest.parent
    llm, model = llm_svc.from_settings(), llm_svc.generate_model()

    hang = []
    for m in muc:
        tep = goc / m["tep"]
        tai_lieu = doc(tep.name, tep.read_bytes())
        ra = rut_du_kien(m["loai"], tai_lieu, llm, model)
        du_doan = {f["key"]: f["gia_tri"] for f in ra["du_kien"]}
        hang.append(
            {
                "id": m["id"],
                "loai": m["loai"],
                "trich_khop": diem_trich(ra["du_kien"]),
                "truong_dung": diem_truong(du_doan, m.get("nhan") or {}),
                "so_bo": ra["traces"]["rut_du_kien_so_bo"],
                "chi_phi_usd": ra["traces"]["rut_du_kien_cost_usd"],
            }
        )

    n = len(hang) or 1
    return {
        "commit_hash": _commit_hash(),
        "chay_luc": datetime.now(UTC).isoformat(),
        "manifest": str(manifest),
        "so_tai_lieu": len(hang),
        "da_nguoi_duyet": bool(bo.get("da_nguoi_duyet")),
        "trich_khop": sum(h["trich_khop"] for h in hang) / n,
        "truong_dung": sum(h["truong_dung"] for h in hang) / n,
        "chi_phi_usd": sum(h["chi_phi_usd"] for h in hang),
        "hang": hang,
    }


def _in_bang(kq: dict) -> None:
    print(f"\ncommit {kq['commit_hash']} · {kq['so_tai_lieu']} tài liệu · "
          f"nhãn người duyệt: {'có' if kq['da_nguoi_duyet'] else 'CHƯA'}")
    print(f"{'id':<24} {'loại':<12} {'trích khớp':>11} {'trường đúng':>12} {'bỏ':>4}")
    for h in kq["hang"]:
        print(f"{h['id']:<24} {h['loai']:<12} {h['trich_khop']:>11.3f} {h['truong_dung']:>12.3f} {h['so_bo']:>4}")
    print(f"{'TỔNG':<24} {'':<12} {kq['trich_khop']:>11.3f} {kq['truong_dung']:>12.3f}")
    if kq["trich_khop"] < 1.0:
        print("\n‼️  trích khớp < 1.0 — có dữ kiện ra tới người dùng mà không tra ngược được. "
              "Đây là lỗi nghiêm trọng nhất tính năng này có thể mắc, không phải một điểm số thấp.")
    if kq["truong_dung"] < NGUONG_TRUONG_DUNG:
        print(f"\n⚠️  trường đúng {kq['truong_dung']:.1%} < ngưỡng {NGUONG_TRUONG_DUNG:.0%} (SC-002).")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bo", type=Path, default=BO_MAC_DINH)
    p.add_argument("--json", type=Path, help="ghi kết quả ra tệp JSON")
    a = p.parse_args()

    if not a.bo.exists():
        raise SystemExit(
            f"Chưa có tập mẫu ở {a.bo}. Xem eval/datasets/tai_lieu_mau/README.md để biết cách dựng."
        )
    kq = chay(a.bo)
    _in_bang(kq)
    if a.json:
        a.json.write_text(json.dumps(kq, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
