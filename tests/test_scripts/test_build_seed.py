from scripts.fetch_moj import DOC_IDS


def test_du_6_bo_luat_o_tang_sau():
    bo_luat = {"95942", "96122", "96115", "96172", "139264", "96117"}
    assert bo_luat <= set(DOC_IDS)
    assert all(DOC_IDS[d][0] == "deep" for d in bo_luat)


def test_co_hai_van_ban_bay_hieu_luc():
    # NĐ 74/2024 hết hiệu lực toàn bộ; NĐ 90/2019 MOJ đánh sai "còn hiệu lực"
    assert "168670" in DOC_IDS and "139094" in DOC_IDS


def test_moi_doc_id_co_so_ky_hieu_khong_rong():
    assert all(skh for _, skh in DOC_IDS.values()), "định danh bằng so_ky_hieu, không bằng title"


def test_khong_co_doc_id_trung():
    assert len(DOC_IDS) == len(set(DOC_IDS))
