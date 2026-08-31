#!/usr/bin/env python
"""Ẩn danh hoá `traces` quá hạn. Chạy định kỳ (cron/scheduler) lúc deploy.

    python -m scripts.an_danh_traces            # dùng KLAW_TRACES_AN_DANH_SAU_NGAY
    python -m scripts.an_danh_traces --ngay 30  # ghi đè cho một lượt

Chạy bằng `-m` theo đúng quy ước các script khác trong `scripts/` (có
`__init__.py`); gọi trực tiếp `python scripts/...` thì `src` không nằm trên path.

Idempotent: chạy lại ngay sau đó trả 0 dòng.
"""

import argparse
import sys

from src.config import get_settings
from src.services.db import get_engine
from src.services.traces_an_danh import an_danh_traces


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ngay", type=int, default=None, help="ghi đè thời hạn (ngày); 0 = tắt")
    a = p.parse_args()
    sau_ngay = a.ngay if a.ngay is not None else get_settings().traces_an_danh_sau_ngay
    if sau_ngay <= 0:
        print("Ẩn danh hoá traces đang TẮT (sau_ngay <= 0) — không sửa dòng nào.")
        return 0
    n = an_danh_traces(get_engine(), sau_ngay)
    print(f"Đã ẩn danh {n} dòng traces cũ hơn {sau_ngay} ngày (bỏ query + user_sub, giữ số liệu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
