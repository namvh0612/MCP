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


def test_generator_handles_agile_cats(solar_dir, tmp_path):
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    design = sb.SymbolDesign("FT", [sb.ElementSpec("value", "IX", range=(0, 10))])
    cs = sa_tools.build_symbol(load_solution(root), "bcFlowTransmitter_v1_0", design, technology="hmi")
    designer = next(c.new for r, c in cs.changes.items() if r.endswith("_sSA.cnv.Designer.cs")).decode("utf-8-sig")
    assert 'TagName = "IX"' in designer and "HMI_Indication_Real_v1_0.sValChanged" in designer
    with pytest.raises(EditError, match="neither an IThis input"):
        sa_tools.build_symbol(load_solution(root), "bcFlowTransmitter_v1_0",
                              sb.SymbolDesign("FT", [sb.ElementSpec("value", "NOPE")]))


def test_agile_suggest_walks_nested_blocks(solar_dir):
    from eae_mcp.hmi import agile_blocks as ab
    sol = load_solution(solar_dir)
    cat = next(c for q, c in sol.cats.items() if q.endswith("acFlowTransmitter_v1_0"))
    draft = ab.suggest(sol, cat, "FT-101")
    kinds = {e["var"]: e["kind"] for e in draft["elements"]}
    assert kinds["Equipment.IX"] == "value" and kinds["Equipment.ISIM"] == "state"
    assert kinds["Equipment.TOT.I"] == "value"  # two levels of nesting
    assert kinds["Equipment.CPHH"] == "setpoint"  # HMI_Control_Real → operator setpoint
    assert {"path": "Equipment.Mode", "type": "ModeSelector_v1_0"} in draft["not_drawn"]
    sa_tools.build_symbol(sol, "acFlowTransmitter_v1_0",
                          sb.SymbolDesign("FT-101", [sb.ElementSpec("value", "Equipment.TOT.I", range=(0, 100))]),
                          technology="hmi")


def test_agile_cat_create_and_extend(solar_dir, tmp_path):
    from eae_mcp.project import agile_edit as ag
    from eae_mcp.project.validate import validate_type
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    sigs = [ag.AgileSignal("FLOW", "indication", "real", 0, 120, "m3/h", 1),
            ag.AgileSignal("RUN", "indication", "bool"),
            ag.AgileSignal("SP", "control", "real", 0, 120, "m3/h", 1, default="50.0")]
    ag.create_agile_cat(load_solution(root), "acPump_v1_0", sigs).apply()
    sol = load_solution(root)
    cat = sol.cats["Main.acPump_v1_0"]
    assert [(s.name, s.type) for s in cat.sub_cats] == [("FLOW", "HMI_Indication_Real_v1_0"),
                                                        ("RUN", "HMI_Indication_Bool_v1_0"),
                                                        ("SP", "HMI_Control_Real_v1_0")]
    logic = sol.types["Main.fbPump_v1_0"]
    assert {(a.name, a.role) for a in logic.interface.adapter_inputs + logic.interface.adapter_outputs} == \
        {("FLOW", "plug"), ("RUN", "plug"), ("SP", "socket")}
    issues = [i["message"] for q in ("Main.acPump_v1_0", "Main.fbPump_v1_0")
              for i in validate_type(sol.types[q], sol) if i["severity"] != "info"]
    assert all("EVENTCHAIN" in m for m in issues)  # runtime type: needs the library catalog
    net = sol.types["Main.acPump_v1_0"].network
    adapters = {(c.source, c.destination) for c in net.connections if c.kind == "adapter"}
    # HMI_INIT chain Register → FLOW → RUN → SP → Register (pins with an ID are referenced by ID)
    assert ("$Register.24", "$FLOW.HMI_INIT") in adapters and ("$SP.HMI_INITO", "$Register.HMI_INIT") in adapters
    fb = next(i for i in net.instances if i.name == "FLOW")
    assert {p.lstrip("$"): v for p, v in fb.parameters.items()}["Units"] == "'m3/h'"

    cs = ag.add_signals(load_solution(root), "acPump_v1_0", [ag.AgileSignal("TEMP", "indication", "real", 0, 150, "degC")])
    assert not [x for x in cs.warnings if x.startswith("warning") and "EVENTCHAIN" not in x]
    cs.apply()
    sol = load_solution(root)
    net = sol.types["Main.acPump_v1_0"].network
    adapters = {(c.source, c.destination) for c in net.connections if c.kind == "adapter"}
    assert ("$SP.HMI_INITO", "$TEMP.HMI_INIT") in adapters and ("$TEMP.31", "$Register.HMI_INIT") in adapters
    assert sum(1 for c in adapters if c[1] == "$Register.HMI_INIT") == 1
    design = sb.SymbolDesign("P-101", [sb.ElementSpec("value", "TEMP", range=(0, 150), unit="degC"),
                                       sb.ElementSpec("state", "RUN", states={"false": "Stopped", "true": "Running"})])
    sa_tools.build_symbol(sol, "acPump_v1_0", design, technology="both").apply()
    with pytest.raises(EditError, match="not an Agile CAT"):
        ag.add_signals(load_solution(root), "ElectricPriceUpdate", [ag.AgileSignal("X")])
