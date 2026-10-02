import pytest

from eae_mcp import services
from eae_mcp.config import Config
from eae_mcp.hmi import review as rv


def _review(path, **kw):
    ws = services.Workspace(Config(roots=[]))
    return services.hmi_review(ws.open(str(path)), ws, **kw)


def test_color_math():
    assert rv.hue_name((61, 205, 88)) == "green" and rv.saturated((61, 205, 88))
    assert rv.hue_name((230, 230, 230)) == "gray" and not rv.saturated((200, 200, 200))
    assert round(rv.contrast((0, 0, 0), (255, 255, 255)), 1) == 21.0


def test_golden_is_clean_and_alarm_classes_read(golden_dir):
    r = _review(golden_dir)
    assert all(not d["findings"] for d in r["displays"])
    assert [c["name"] for c in r["alarm_classes"]] == ["Alarm", "Warning"] and not r["alarm_findings"]
    assert r["manual_checks"]


def test_solar_findings(solar_dir):
    r = _review(solar_dir, level=2)
    by = {d["display"]: {f["rule"] for f in d["findings"]} for d in r["displays"]}
    assert {"HP-02", "HP-05", "HP-06"} <= by["hmi canvas Architecture"]
    assert "HP-04" in by["hmi canvas ControlPage"]
    # its 38 HMI_Indication_*.sValChanged objects are invisible Agile bridges, not numbers on screen
    assert "HP-09" not in by["hmi canvas ControlPage"]
    assert "HP-02" in by["ehmi canvas Architecture"]


def test_synthetic_rules():
    d = rv.Display("X", "ehmi", "x")
    d.background = rv.ColorUse((0, 160, 0), None, "background", "X")
    d.colors.append(d.background)
    for i in range(5):
        d.colors.append(rv.ColorUse((255, 0, 0), None, "fill", f"r{i}"))
    d.text_pairs.append(("lbl", rv.ColorUse((150, 150, 150), None, "text", "lbl"),
                         rv.ColorUse((170, 170, 170), None, "fill", "lbl")))
    d.fonts = [("A", 6.0)]
    rules = {f.rule for f in rv.review_display(d, {}, level=1)}
    assert {"HP-01", "HP-02", "HP-04", "HP-06", "HP-07", "HP-10"} <= rules


def test_alarm_profiles_cross_check(solar_dir, tmp_path):
    import shutil

    from eae_mcp.hmi import scripts as sc
    from eae_mcp.project.solution import load_solution
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    sol = load_solution(root)
    assert "HMI/SolarAlarmProfiles.spt.cs" in [x.file for x in sc.list_scripts(sol)]
    r = sc.alarm_profiles(sol)
    assert {p["name"] for p in r["profiles"]} >= {"PVArray", "Inverter", "OwnLoad", "Grid", "PPC"}
    by = {(f["rule"], f["where"].split(": ")[1]): f for f in r["findings"]}
    # fbOwnLoad sets bit 5 ("Energy measurement invalid") but the profile has no text for it
    assert by[("ALM-06", "OwnLoad")]["evidence"]["5"] == {"condition": "OwnLoad.ELOAD < 0.0",
                                                           "comment": "Energy measurement invalid"}
    assert ("ALM-07", "Grid") in by  # bit 2 described, never set by fbGrid
    assert ("ALM-09", "Inverter") in by
    cs = sc.add_profile_entries(sol, "OwnLoad", [(5, "Energy measurement invalid", "Energy measurement restored",
                                                  "Warning")])
    cs.apply()
    r = sc.alarm_profiles(load_solution(root))
    assert ("ALM-06", "OwnLoad") not in {(f["rule"], f["where"].split(": ")[1]) for f in r["findings"]}
    own = next(p for p in r["profiles"] if p["name"] == "OwnLoad")
    assert own["alarms"] == 6 and own["entries"][-1]["priority"] == "Warning"
    with pytest.raises(Exception, match="already described"):
        sc.add_profile_entries(load_solution(root), "OwnLoad", [(5, "x", "y", "Warning")])
    with pytest.raises(Exception, match="Helper"):
        sc.add_profile_entries(load_solution(root), "OwnLoad", [(6, "x", "y", "Critical")])
