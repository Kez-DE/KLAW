"""Mức đã dùng của khoá OpenRouter — gác trước mỗi lượt đo tốn phí.

    python -m eval.kiem_tran_chi [TRAN_USD]

In một dòng `<thời điểm> usage_usd … limit … limit_remaining …` (GET `/key`, không tốn
phí). Có `TRAN_USD` mà mức đã dùng vượt nó thì thoát mã 3, để lệnh tốn phí nối sau bằng
`&&` không bắt đầu; gọi không được hay thiếu số liệu cũng thoát khác 0 (đóng khi lỗi).
Chênh `usage_usd` giữa hai lần gọi trước và sau một lượt đo là chi phí thật của lượt đó
(cận trên nếu cùng lúc có lượt khác dùng chung khoá).
"""

import argparse
import sys
from datetime import datetime

import httpx

from src.config import get_settings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tran_usd", type=float, nargs="?", help="trần mức đã dùng (USD) để được bắt đầu")
    a = ap.parse_args(argv)
    s = get_settings()
    r = httpx.get(
        f"{s.openrouter_base_url}/key", headers={"Authorization": f"Bearer {s.openrouter_api_key}"}, timeout=30
    )
    r.raise_for_status()
    d = r.json()["data"]
    print(
        f"{datetime.now().isoformat(timespec='seconds')} usage_usd {d.get('usage')} "
        f"limit {d.get('limit')} limit_remaining {d.get('limit_remaining')}"
    )
    if a.tran_usd is not None and float(d["usage"]) > a.tran_usd:
        print(f"usage {d['usage']} vượt trần {a.tran_usd}: không bắt đầu", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
