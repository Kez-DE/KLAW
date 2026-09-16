"""Deterministic meta guard over the LLM router (production 2026-09-16: the
sample meta question was routed tra_cuu and answered partial_coverage)."""

import json

import pytest

from src.agents.nodes.gioi_thieu import chac_chan_meta
from src.agents.nodes.route import Intent, route
from src.services.llm import Usage


class LlmTraCuu:
    def chat(self, model, messages, json_schema=None):
        return json.dumps({"intent": "tra_cuu"}), Usage(1, 1, 0.0)


@pytest.mark.parametrize("cau", [
    "bạn làm được gì, có những bộ luật gì, có những lĩnh vực pháp luật gì",
    "bạn làm được gì và kho có luật nào?",
    "dữ liệu lấy từ đâu, hiện có những lĩnh vực gì?",
    "KLAW là gì, có soạn hợp đồng được không?",
    "bạn là ai",
    "model của bạn là gì",
    "kho của bạn có bao nhiêu văn bản",
])
def test_cau_hoi_ve_tro_ly_hoac_kho_bi_ep_gioi_thieu(cau, tmp_path):
    assert chac_chan_meta(cau)
    mau = tmp_path / "route.md"
    mau.write_text("{cau_hoi}", encoding="utf-8")
    st = route({"query": cau}, LlmTraCuu(), "m", prompt_path=mau)
    assert st["intent"] is Intent.gioi_thieu
    assert st["traces"]["route_ep_meta"] is True


@pytest.mark.parametrize("cau", [
    "bạn tôi bị sa thải có được bồi thường không",
    "công ty trừ lương thì bị phạt bao nhiêu",
    "Điều 35 Bộ luật Lao động nói gì về báo trước",
    "kho có Nghị định 145/2020 không",          # số hiệu → đường hoi_ve_kho của router, không ép
    "thử việc tối đa bao lâu",
    "tôi làm được gì khi công ty nợ lương",     # "tôi", không phải "bạn"
])
def test_cau_hoi_luat_khong_bi_ep(cau, tmp_path):
    assert not chac_chan_meta(cau)
    mau = tmp_path / "route.md"
    mau.write_text("{cau_hoi}", encoding="utf-8")
    st = route({"query": cau}, LlmTraCuu(), "m", prompt_path=mau)
    assert st["intent"] is Intent.tra_cuu
    assert st["traces"]["route_ep_meta"] is False
