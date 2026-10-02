import datetime as dt
import json
import re
import shutil

import pytest

from eae_mcp.hmi import ehmi_edit as ee
from eae_mcp.hmi.reader import load_hmi
from eae_mcp.io import jsonrt, xmlrt
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution

DEV = "42ac64b9-b75e-4884-96b3-c103347b1d7f"
CANVAS = f"WEB/{DEV}/Canvas1.cnv.json"


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def test_json_layout_roundtrips(golden_dir, solar_dir):
    files = [f for root in (golden_dir, solar_dir) for f in root.rglob("*.json")
             if f.name.endswith((".cnv.json", ".sym.json"))]
    assert len(files) > 10
    for f in files:
        assert jsonrt.dumps(jsonrt.load(f)) == f.read_bytes(), f


def test_remove_and_place_symbol_like_eae(golden_copy, golden_dir):
    ee.remove_object(load_solution(golden_copy), "Canvas1", "symbol1").apply()
    assert json.loads((golden_copy / CANVAS).read_text(encoding="utf-8-sig"))["objects"] == []
    cs = ee.place_symbol(load_solution(golden_copy), "EcoRT_0/Canvas1", "CAT1", left=7.88, top=13, width=151, height=102)
    assert not cs.warnings  # CAT1 is mapped to EcoRT_0
    cs.apply()
    assert (golden_copy / CANVAS).read_bytes() == (golden_dir / CANVAS).read_bytes()


def test_place_symbol_defaults_and_errors(golden_copy):
    sol = load_solution(golden_copy)
    cs = ee.place_symbol(sol, "Canvas1", "CAT1")
    obj = json.loads(cs.changes[CANVAS].new.decode("utf-8-sig"))["objects"][-1]
    assert obj["name"] == "symbol2" and obj["top"] == 125 and (obj["width"], obj["height"]) == (600, 400)
    with pytest.raises(EditError, match="no eHMI symbol 'nope'"):
        ee.place_symbol(sol, "Canvas1", "CAT1", symbol="nope")
    with pytest.raises(EditError, match="No eHMI canvas"):
        ee.place_symbol(sol, "Nope", "CAT1")
    with pytest.raises(EditError, match="already has an object"):
        ee.place_symbol(sol, "Canvas1", "CAT1", name="symbol1")


def test_create_canvas(golden_copy):
    now = dt.datetime(2026, 10, 2, 12, 45)
    cs = ee.create_canvas(load_solution(golden_copy), "EcoRT_0", "Canvas2", now=now)
    cs.apply()
    base = golden_copy / "WEB" / DEV
    gold_ts = (base / "Canvas1.cnv.ts").read_bytes().replace(b"Canvas1", b"Canvas2")
    assert (base / "Canvas2.cnv.ts").read_bytes() == gold_ts
    assert (base / "Canvas2.user.cs").read_bytes() == (base / "Canvas1.user.cs").read_bytes().replace(b"Canvas1", b"Canvas2")
    assert json.loads((base / "Canvas2.cnv.json").read_text(encoding="utf-8-sig"))["width"] == 1024
    res = (base / "WebCanvasesResolutionList.xml").read_text()
    assert '<Canvas Name="Canvas2" Title="" Tooltip="" Instance="WEB.Main.Canvases.Canvas2">' in res
    assert xmlrt.roundtrips(base / "WebCanvasesResolutionList.xml")
    proj = (golden_copy / "WEB/WEB.htmlproj").read_text(encoding="utf-8-sig")
    assert re.search(rf'<None Include="{DEV}\\Canvas2.cnv.ts">\s*<Canvas>true</Canvas>', proj)
    idx = load_hmi(load_solution(golden_copy))
    assert {d.name for d in idx.documents if d.kind == "canvas" and d.technology == "ehmi"} >= {"Canvas1", "Canvas2"}
    assert any("Canvas2" in r.canvases for r in idx.resolutions if r.technology == "ehmi")
    with pytest.raises(EditError, match="already has a canvas"):
        ee.create_canvas(load_solution(golden_copy), "EcoRT_0", "Canvas2")


def test_update_object(golden_copy):
    cs = ee.update_object(load_solution(golden_copy), "Canvas1", "symbol1", {"left": 40, "width": None})
    obj = json.loads(cs.changes[CANVAS].new.decode("utf-8-sig"))["objects"][0]
    assert obj["left"] == 40 and "width" not in obj and obj["tagName"] == "3811CA558F6E3EFC"
    with pytest.raises(EditError, match="cannot be changed"):
        ee.update_object(load_solution(golden_copy), "Canvas1", "symbol1", {"type": "x"})
