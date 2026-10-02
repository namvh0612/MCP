"""Situation-awareness HMI generation: symbols and displays from a design, verified end to end."""

import shutil
import subprocess
from pathlib import Path

import pytest

from eae_mcp import services
from eae_mcp.config import Config
from eae_mcp.hmi import designer as ds
from eae_mcp.hmi import sa_builder as sb
from eae_mcp.hmi import sa_tools
from eae_mcp.model import Event, Interface, Var
from eae_mcp.project import cat_edit
from eae_mcp.project import network_edit as ne
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution

HERE = Path(__file__).parent
HMI = Interface(event_inputs=[Event("REQ", with_vars=["Flow", "Running", "State", "Alarm", "Name"])],
                input_vars=[Var("Flow", "REAL"), Var("Running", "BOOL"), Var("State", "INT"), Var("Alarm", "INT"),
                            Var("Name", "STRING")])
DESIGN = sb.SymbolDesign("Pump P-101", [
    sb.ElementSpec("alarm", "Alarm"),
    sb.ElementSpec("value", "Flow", unit="m3/h", range=(0, 120), normal=(40, 90), limits=(20, 105)),
    sb.ElementSpec("state", "State", states={"0": "Stopped", "1": "Running", "2": "Fault"}, abnormal=["2"], priority=1),
    sb.ElementSpec("state", "Running", label="Run", states={"true": "On", "false": "Off"}),
    sb.ElementSpec("text", "Name", label="Tag")])


@pytest.fixture()
def plant(golden_dir, library_store, tmp_path):
    root = tmp_path / "g"
    shutil.copytree(golden_dir, root)
    cat_edit.create_cat(load_solution(root, library_store=library_store), "catPump", hmi=HMI).apply()
    return root


def _sol(root, library_store):
    return load_solution(root, library_store=library_store)


def test_symbol_build_both_technologies(plant, library_store, tmp_path):
    cs = sa_tools.build_symbol(_sol(plant, library_store), "catPump", DESIGN)
    cs.apply()
    sol = _sol(plant, library_store)
    assert [s.name for s in sol.cats["Main.catPump"].symbols] == ["sDefault", "sSA", "seDefault", "seSA"]
    designer = (plant / "HMI/catPump/catPump_sSA.cnv.Designer.cs").read_bytes().decode("utf-8-sig")
    d = ds.parse(designer)
    assert {"valFlow", "ptrFlow", "nrmFlow", "limFlowL", "limFlowH", "staState", "almAlarm", "txtName"} <= set(d.objects)
    assert 'this.valFlow.TagName = "Flow";' in designer and "this.xFlow.ValueChanged +=" in designer
    assert "this.SymbolSize = new System.Drawing.Size(240," in designer
    event_cs = (plant / "HMI/catPump/catPump.event.cs").read_text()
    assert "partial class sSA" in event_cs
    ws = services.Workspace(Config(roots=[]))
    s = ws.open(str(plant))
    for name in ("sSA", "seSA"):
        assert services.hmi_review(s, ws, name=name)["displays"][0]["findings"] == []
    # Build checks of the generated code (when the compilers are available).
    if shutil.which("mcs"):
        out = subprocess.run(["mcs", "-target:library", "-nowarn:67,169,414,649", f"-out:{tmp_path / 's.dll'}",
                              str(HERE / "stubs/eae_stubs.cs"), str(plant / "HMI/catPump/catPump_sSA.cnv.Designer.cs"),
                              str(plant / "HMI/catPump/catPump_sSA.cnv.cs")], capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
    if shutil.which("tsc"):
        ts = tmp_path / "sym.ts"
        ts.write_text((plant / "WEB/catPump/catPump_seSA.sym.ts").read_text(encoding="utf-8-sig"))
        stubs = tmp_path / "stubs.d.ts"
        stubs.write_text("declare namespace NxtControl.GuiFramework { class RuntimeSymbol { constructor(); "
                         "find(name: string): any; } }\ndeclare namespace System { function DefaultValue(v: any): any; }\n")
        out = subprocess.run(["tsc", "--noEmit", "--experimentalDecorators", "--target", "es2017", "--strict", "false",
                              "--noImplicitAny", "true", str(stubs), str(ts)],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr


def test_design_validation(plant, library_store):
    sol = _sol(plant, library_store)
    bad = [
        (sb.ElementSpec("value", "Nope"), "not an input"),
        (sb.ElementSpec("value", "Running"), "needs a number"),
        (sb.ElementSpec("value", "Flow", range=(0, 100), normal=(50, 150)), "outside range"),
        (sb.ElementSpec("value", "Flow", normal=(1, 2)), "need a range"),
        (sb.ElementSpec("state", "State"), "needs states"),
        (sb.ElementSpec("text", "Flow"), "needs a STRING"),
        (sb.ElementSpec("value", "Flow", priority=9, range=(0, 1)), "priority"),
    ]
    for el, msg in bad:
        with pytest.raises(EditError, match=msg):
            sa_tools.build_symbol(sol, "catPump", sb.SymbolDesign("X", [el]))
    sa_tools.build_symbol(sol, "catPump", DESIGN, technology="hmi").apply()
    with pytest.raises(EditError, match="overwrite"):
        sa_tools.build_symbol(_sol(plant, library_store), "catPump", DESIGN, technology="hmi")
    assert sa_tools.build_symbol(_sol(plant, library_store), "catPump", DESIGN, technology="hmi", overwrite=True).changes


def test_layout_maps_ranges_to_pixels():
    boxes, W, H = sb.layout(DESIGN)
    by = {b.name: b for b in boxes}
    trk, nrm = by["trkFlow"], by["nrmFlow"]
    assert nrm.x == pytest.approx(trk.x + 40 / 120 * trk.w) and nrm.w == pytest.approx(50 / 120 * trk.w)
    assert by["limFlowH"].x == pytest.approx(trk.x + 105 / 120 * trk.w)
    assert W == 240 and H > 100


def test_display_build_both_technologies(plant, library_store):
    sa_tools.build_symbol(_sol(plant, library_store), "catPump", DESIGN).apply()
    for n in ("P101", "P102"):
        ne.add_fb(_sol(plant, library_store), "APP1", n, "catPump").apply()
        ne.map_to_resource(_sol(plant, library_store), n, "EcoRT_0/RES0").apply()
    design = sa_tools.DisplayDesign("PumpStation", "Pump station", [sa_tools.SectionDesign("Feed pumps", ["P101", "P102"])],
                                    level=2, device="EcoRT_0")
    for tech in ("hmi", "ehmi"):
        sa_tools.build_display(_sol(plant, library_store), design, tech).apply()
    ws = services.Workspace(Config(roots=[]))
    s = ws.open(str(plant))
    r = services.hmi_review(s, ws, name="PumpStation", level=2)
    assert {d["display"] for d in r["displays"]} == {"hmi canvas PumpStation", "ehmi canvas PumpStation"}
    for d in r["displays"]:
        assert [f["rule"] for f in d["findings"]] == ["HP-10"]  # trends are the one thing left to add
    idx = ws.hmi_of(s)
    ids = {i.name: i.id for i in s.systems[0].applications[0].layers[0].network.instances}
    for doc in idx.find("PumpStation"):
        assert {ids["P101"], ids["P102"]} <= {o.tag_name for o in doc.objects}
    with pytest.raises(EditError, match="replace=true"):
        sa_tools.build_display(_sol(plant, library_store), design, "hmi")
    with pytest.raises(EditError, match="twice"):
        sa_tools.build_display(_sol(plant, library_store), sa_tools.DisplayDesign(
            "X", "X", [sa_tools.SectionDesign("a", ["P101", "P101"])]), "hmi")


def test_suggest_draft_never_invents_limits():
    draft = sb.suggest(HMI, "Pump")
    kinds = {e["var"]: e["kind"] for e in draft["elements"]}
    assert kinds == {"Alarm": "alarm", "Flow": "value", "State": "state", "Running": "state", "Name": "text"}
    flow = next(e for e in draft["elements"] if e["var"] == "Flow")
    assert flow["range"] is None and flow["limits"] is None
    assert any(q.startswith("Flow:") for q in draft["missing"])
    assert draft["elements"][0]["kind"] == "alarm"  # alarm indicators go first (title row)


def test_knowledge_has_description_workflow():
    hits = services.knowledge_search("from description to HMI", 2)
    assert any("eae_hmi_design_suggest" in h["text"] for h in hits)
