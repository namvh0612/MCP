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
    assert {"HP-04", "HP-09"} <= by["hmi canvas ControlPage"]
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
