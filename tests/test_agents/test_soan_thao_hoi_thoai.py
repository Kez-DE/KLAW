from src.agents.nodes import assemble as as_mod
from src.models.schemas import TraCuuResponse


def test_result_type_co_hai_gia_tri_moi_va_response_biet():
    assert as_mod.ResultType.soan_thao_hoi.value == "soan_thao_hoi" and as_mod.ResultType.ban_thao.value == "ban_thao"
    r = TraCuuResponse(
        result_type="soan_thao_hoi",
        answer="a",
        citations=[],
        warnings=[],
        coverage_note=None,
        trace_id="t",
        config_name="c",
        soan_thao_hoi={
            "loai": "hdld",
            "ten": "hợp đồng lao động",
            "da_co": {},
            "con_thieu": [],
            "chip": {},
            "het_han_muc": None,
            "can_dang_nhap": False,
        },
    )
    assert r.soan_thao_hoi.loai == "hdld" and r.ban_thao is None


def test_assemble_soan_thao_hoi_hoi_mot_lan_toi_da_sau_truong():
    thieu = [
        {
            "key": f"k{i}",
            "nhan": f"Nhãn {i}",
            "kieu": "str",
            "bat_buoc": True,
            "lua_chon": ["a", "b"] if i == 0 else None,
        }
        for i in range(8)
    ]
    st = {
        "intent": "soan_thao",
        "traces": {},
        "user_sub": "u",
        "soan_thao_dang_mo": {
            "loai": "hdld",
            "facts": {"x": "1"},
            "ban_thao_id": None,
            "so_lan_sua": 0,
            "con_thieu": thieu[:6],
            "du": False,
            "cu_soan": False,
        },
    }
    ket = as_mod.assemble(st, {}, None, "m")
    assert ket["result_type"] == as_mod.ResultType.soan_thao_hoi
    assert ket["answer"].count("\n- ") == 6 and "Nhãn 0" in ket["answer"] and "Nhãn 6" not in ket["answer"]
    assert ket["soan_thao_hoi"]["chip"] == {"k0": ["a", "b"]} and ket["soan_thao_hoi"]["da_co"] == {"x": "1"}


def test_assemble_khach_chua_dang_nhap_moi_dang_nhap():
    st = {
        "intent": "soan_thao",
        "traces": {},
        "user_sub": None,
        "soan_thao_dang_mo": {
            "loai": "hdld",
            "facts": {},
            "ban_thao_id": None,
            "so_lan_sua": 0,
            "con_thieu": [],
            "du": True,
            "cu_soan": False,
        },
    }
    ket = as_mod.assemble(st, {}, None, "m")
    assert ket["result_type"] == as_mod.ResultType.soan_thao_hoi and ket["soan_thao_hoi"]["can_dang_nhap"] is True


def test_assemble_ban_thao_tra_ket_da_dung():
    bt = {
        "id": "b1",
        "loai": "hdld",
        "ten": "hợp đồng lao động",
        "phien_ban": 2,
        "document": "# HĐ",
        "clauses": [],
        "audit_report": {},
        "facts": {"x": "1"},
        "doi_so_voi_truoc": ["x"],
    }
    st = {
        "intent": "soan_thao",
        "traces": {},
        "user_sub": "u",
        "ban_thao_ket": bt,
        "soan_thao_dang_mo": {
            "loai": "hdld",
            "facts": {"x": "1"},
            "ban_thao_id": "b1",
            "so_lan_sua": 1,
            "con_thieu": [],
            "du": True,
            "cu_soan": False,
        },
    }
    ket = as_mod.assemble(st, {}, None, "m")
    assert ket["result_type"] == as_mod.ResultType.ban_thao and ket["ban_thao"]["phien_ban"] == 2
    assert "phiên bản 2" in ket["answer"] and "đã đổi" in ket["answer"]
