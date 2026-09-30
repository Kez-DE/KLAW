"""Deterministic meta guard over the LLM router (production 2026-09-16: the
sample meta question was routed tra_cuu and answered partial_coverage)."""

import json

import pytest

from src.agents.nodes.gioi_thieu import chac_chan_meta, hoi_he_thong_phap_luat
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


# ══ Legal-system guard (decision 2026-09-29 item 4) ══════════════════════════
#
# Production 2026-09-29 (traces 91b11532, 4ef333fb, b2c84968): the LLM labelled
# "pháp luật Việt Nam chia thành những gì" `hoi_ve_kho`, and the user got the
# KLAW introduction. A question about Vietnamese law is answered from statute
# (tra_cuu); only questions about KLAW or the kho stay meta.


class LlmY:
    def __init__(self, intent: str):
        self.intent = intent

    def chat(self, model, messages, json_schema=None):
        return json.dumps({"intent": self.intent}), Usage(1, 1, 0.0)


def _route(cau: str, llm, tmp_path) -> dict:
    mau = tmp_path / "route.md"
    mau.write_text("{cau_hoi}", encoding="utf-8")
    return route({"query": cau}, llm, "m", prompt_path=mau)


HOI_HE_THONG = [
    # the traced questions, as typed and as giai_nghia restated them
    "hiện tại pháp luật việt nam chia thành những gì",
    "Hiện tại pháp luật Việt Nam được chia thành những gì?",
    "Hiện tại pháp luật Việt Nam chia thành những gì?",
    "pháp luật việt nam có những gì",
    "Pháp luật Việt Nam có những gì",
    # the phrasings named by the decision
    "hệ thống văn bản quy phạm pháp luật gồm những gì",
    "có những loại văn bản pháp luật nào",
    "văn bản quy phạm pháp luật gồm những loại nào",
    "hệ thống pháp luật việt nam có bao nhiêu loại văn bản",
    "pháp luật VN chia thành những gì",
    "có những ngành luật nào",
    # a vocative or a polite preamble is not a question about KLAW; "em" is
    # usually the user speaking of themselves
    "bạn ơi, pháp luật việt nam chia thành những gì",
    "bạn cho mình hỏi hệ thống pháp luật gồm những gì",
    "cho em hỏi pháp luật việt nam chia thành những gì",
    "cho em hỏi hệ thống pháp luật việt nam là gì",
    "chào bạn, mình muốn hỏi hệ thống pháp luật việt nam gồm những gì",
    "bạn có thể cho mình biết pháp luật việt nam chia thành mấy ngành không",
    "em chào anh, em muốn hỏi các ngành luật ở việt nam",
    "hệ thống pháp luật việt nam là gì vậy bạn",
    # synonyms, "ở Việt Nam", the abbreviation, no diacritics
    "luật pháp việt nam là gì",
    "luật pháp việt nam chia thành những gì",
    "thứ bậc hiệu lực của văn bản pháp luật ở việt nam",
    "nguồn của luật ở việt nam gồm những gì",
    "các loại vbqppl hiện nay",
    "phap luat viet nam chia thanh nhung gi",
    "hien phap viet nam la gi",
    "hiến pháp việt nam là gì",
    # "văn bản nào" / "bao nhiêu điều kiện" are not corpus markers
    "văn bản nào có hiệu lực cao nhất trong hệ thống pháp luật việt nam",
    "hệ thống pháp luật việt nam quy định bao nhiêu điều kiện thành lập doanh nghiệp",
]


@pytest.mark.parametrize("y_dinh", ["hoi_ve_kho", "gioi_thieu"])
@pytest.mark.parametrize("cau", HOI_HE_THONG)
def test_cau_hoi_ve_he_thong_phap_luat_di_tra_cuu(cau, y_dinh, tmp_path):
    assert hoi_he_thong_phap_luat(cau)
    st = _route(cau, LlmY(y_dinh), tmp_path)
    assert st["intent"] is Intent.tra_cuu
    assert st["traces"]["route_ep_luat"] is True
    assert st["traces"]["route_ep_meta"] is False


HOI_VE_KHO_HAY_KLAW = [
    "kho có bao nhiêu văn bản pháp luật việt nam",
    "KLAW có những văn bản pháp luật Việt Nam nào",
    "bạn có những văn bản pháp luật việt nam nào",
    "trong KLAW có bao nhiêu điều luật",
    "có bao nhiêu văn bản pháp luật, chia thành những loại nào",
    "pháp luật việt nam có bao nhiêu văn bản",
    "có Hiến pháp 2013 không",
    "có Luật Ban hành văn bản quy phạm pháp luật không",
    "có bao nhiêu văn bản pháp luật",
    # trace fa18ddce, typo kept as typed
    "có bao nhiêu điều luật , chia thành các loại naoif",
    "hiện có bao nhiêu bộ luật",
    "Bộ luật Hàng hải Việt Nam có hiệu lực không",
    # addressed to KLAW without "bạn"/"klaw", or naming the kho data
    "klaw có tra được luật việt nam không",
    "có tra cứu được luật việt nam không",
    "trợ lý này có hiểu hệ thống pháp luật việt nam không",
    "app này hỗ trợ những ngành luật nào",
    "dữ liệu có những luật việt nam nào",
    "trong dữ liệu có những ngành luật nào",
]


@pytest.mark.parametrize("y_dinh", ["hoi_ve_kho", "gioi_thieu"])
@pytest.mark.parametrize("cau", HOI_VE_KHO_HAY_KLAW)
def test_cau_hoi_ve_kho_hay_klaw_giu_nguyen_y_dinh(cau, y_dinh, tmp_path):
    assert not hoi_he_thong_phap_luat(cau)
    st = _route(cau, LlmY(y_dinh), tmp_path)
    assert st["intent"] is Intent(y_dinh)
    assert st["traces"]["route_ep_luat"] is False


def test_hoi_danh_sach_bo_luat_van_tra_so_lieu_kho(tmp_path):
    """Listing documents ("có những bộ luật nào") is a count over the kho: no
    statute enumerates the codes, so a meta verdict on it stays on the kho list.
    Decision 2026-09-30 item 2: without an anchor naming KLAW or the kho the guard
    no longer PINS it — the router decides."""
    cau = "pháp luật việt nam có những bộ luật nào"
    assert not chac_chan_meta(cau)
    st = _route(cau, LlmY("hoi_ve_kho"), tmp_path)
    assert st["intent"] is Intent.hoi_ve_kho
    assert st["traces"]["route_ep_meta"] is False and st["traces"]["route_ep_luat"] is False
    st = _route("bạn có những bộ luật nào", LlmTraCuu(), tmp_path)
    assert st["intent"] is Intent.gioi_thieu and st["traces"]["route_ep_meta"] is True


def test_guard_khong_dung_toi_cau_router_da_cho_tra_cuu(tmp_path):
    st = _route("hiện tại pháp luật việt nam chia thành những gì", LlmTraCuu(), tmp_path)
    assert st["intent"] is Intent.tra_cuu
    assert st["traces"]["route_ep_luat"] is False
