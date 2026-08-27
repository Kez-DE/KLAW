"""Tải 2 file parquet cần thiết từ HuggingFace (~25 MB).

KHÔNG tải data/content.parquet (784 MB): toàn văn lấy từ API MOJ, tươi hơn và
có effStatus tại thời điểm chạy. KHÔNG tải legacy/ (3,5 GB).
"""

import sys
from pathlib import Path

import httpx

BASE = "https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents/resolve/main/data"

FILES = {
    "metadata": f"{BASE}/metadata.parquet",           # 15,1 MB — tra doc_id
    "relationships": f"{BASE}/relationships.parquet",  # 9,4 MB — cạnh ĐI VÀO cho Mức 2
}


def download(dest: Path, only: list[str] | None = None) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for name, url in FILES.items():
        if only and name not in only:
            continue
        path = dest / f"{name}.parquet"
        if path.exists():
            print(f"[skip] {path} đã có ({path.stat().st_size / 1e6:.1f} MB)")
            out[name] = path
            continue
        print(f"[get ] {name} …")
        with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
            r.raise_for_status()
            with path.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        print(f"[ok  ] {path} ({path.stat().st_size / 1e6:.1f} MB)")
        out[name] = path
    return out


if __name__ == "__main__":
    from src.config import get_settings

    download(Path(get_settings().data_raw_dir))
    sys.exit(0)
