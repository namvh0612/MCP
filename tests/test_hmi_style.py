import shutil

import pytest

from eae_mcp import services
from eae_mcp.config import Config
from eae_mcp.hmi import sa_builder as sb
from eae_mcp.hmi import sa_tools
from eae_mcp.hmi import style as hs
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution


@pytest.fixture(scope="module")
def solar(solar_dir):
    ws = services.Workspace(Config(roots=[]))
    return ws, ws.open(str(solar_dir))


def _cls(ws, sol, name):
    td = sol.find_type(name)
    return hs.classify_cat(sol, ws.hmi_of(sol), td.qualified_name)


def test_styles_are_told_apart(solar):
    ws, sol = solar
    assert _cls(ws, sol, "ElectricPriceUpdate")["style"] == "basic"
    assert _cls(ws, sol, "HMI_Indication_Real_v1_0")["style"] == "agile-block"
    agile = _cls(ws, sol, "acFlowTransmitter_v1_0")
    assert agile["style"] == "agile" and agile["bindings"]["subcat"] > 0 and agile["ithis_vars"] == ["AssetName"]


def test_agile_paths_resolve_through_nested_cats(solar):
    ws, sol = solar
    td = sol.find_type("acFlowTransmitter_v1_0")
    cat = sol.cats[td.qualified_name]
    assert hs.resolve_tag(sol, cat, "Equipment.I") == ("subcat", "Equipment.I")
    assert hs.resolve_tag(sol, cat, "AssetName") == ("ithis", "AssetName")
    assert hs.resolve_tag(sol, cat, "Equipment.Nope") is None


def test_broken_bindings_found(solar):
    ws, sol = solar
    r = _cls(ws, sol, "acBESS1_v1_0")
    broken = next(f for f in r["findings"] if f["rule"] == "BIND-01")
    assert {e["tag"] for e in broken["evidence"]} == {"SOCSP", "MODE"}


def test_review_reports_styles(solar):
    ws, sol = solar
    r = services.hmi_review(sol, ws)
    assert r["styles"]["cats"]["agile"] > 20 and r["styles"]["cats"]["basic"] >= 5
    by = {d["display"]: d.get("style") for d in r["displays"]}
    assert by["ehmi canvas ControlPage"] == "agile" and by["hmi canvas ControlPage"].startswith("mixed")


def test_golden_is_basic(golden_dir):
    ws = services.Workspace(Config(roots=[]))
    sol = ws.open(str(golden_dir))
    r = services.hmi_review(sol, ws, name="sDefault")
    assert r["displays"][0]["style"] == "basic" and r["cat_reviews"][0]["style"] == "basic"


def test_generator_explains_agile_cats(solar_dir, tmp_path):
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    design = sb.SymbolDesign("FT", [sb.ElementSpec("value", "IX", range=(0, 10))])
    with pytest.raises(EditError, match="Agile style"):
        sa_tools.build_symbol(load_solution(root), "bcFlowTransmitter_v1_0", design)
