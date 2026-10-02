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
        (sb.ElementSpec("value", "Nope"), "neither an IThis input"),
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


AGILE = sb.SymbolDesign("FT-101 Flow", [
    sb.ElementSpec("alarm", "Equipment.IA", priority=2),
    sb.ElementSpec("value", "Equipment.IX", label="Flow"),
    sb.ElementSpec("value", "Equipment.CPHH", label="HH setpoint", unit="m3/h", range=(0, 200), normal=(20, 150),
                   limits=(None, 180)),
    sb.ElementSpec("state", "Equipment.ISIM", label="Source", states={"true": "Simulated", "false": "Field"},
                   abnormal=["true"], priority=3),
    sb.ElementSpec("text", "AssetName", label="Tag")])


def _bridge_stubs(sol, cat_name, design) -> str:
    """C# stubs of the Agile bridge symbols used by a design, from what agile_blocks learned."""
    from eae_mcp.hmi import agile_blocks as ab

    cat = sol.cats[sol.find_type(cat_name).qualified_name]
    seen, out = set(), ["using System;"]
    for e in design.elements:
        br = ab.bridge(sol, cat, e.var)
        if br is None or br.net_class in seen:
            continue
        seen.add(br.net_class)
        ns, cls = br.net_class.rsplit(".", 1)
        props = " ".join(f"public {br.val_type if p in ('Val', 'ValMinimum', 'ValMaximum') else 'string' if p == 'ValUnits' else 'byte'}"
                         f" {p} {{ get; set; }}" for p in sorted(br.props))
        out.append(f"namespace {ns} {{ public class {cls} : NxtControl.GuiFramework.Shape {{ public void BeginInit() {{}} "
                   "public void EndInit() {} public NxtControl.Drawing.Matrix2D DesignMatrix { get; set; } "
                   "public uint SecurityToken { get; set; } public string TagName { get; set; } "
                   f"public event EventHandler OnValChanged; {props} "
                   + (f"public bool FireEvent_CNF({br.val_type} v) {{ return true; }} " if br.control else "")
                   + "} }")
    return "\n".join(out)


def test_agile_symbol_build(solar_dir, tmp_path):
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    sol = load_solution(root)
    cs = sa_tools.build_symbol(sol, "acFlowTransmitter_v1_0", AGILE)
    cs.apply()
    base = root / "SE.Agile/HMI/acFlowTransmitter_v1_0/acFlowTransmitter_v1_0_sSA.cnv"
    designer = Path(f"{base}.Designer.cs").read_bytes().decode("utf-8-sig")
    assert "new SE.Agile.Symbols.HMI_Indication_Real_v1_0.sValChanged()" in designer
    assert 'this.xEquipment_IX.TagName = "Equipment.IX";' in designer
    code = Path(f"{base}.cs").read_text()
    assert "xEquipment_IX.OnValChanged += xEquipment_IXValChanged;" in code and "xEquipment_IX.ValMinimum" in code
    web = (root / "SE.Agile/WEB/acFlowTransmitter_v1_0/acFlowTransmitter_v1_0_seSA.sym.json").read_text(encoding="utf-8-sig")
    assert '"type": "SE.Agile.Symbols.HMI_Control_Real_v1_0.seValControl"' in web and '"tagName": "Equipment.CPHH"' in web
    ws = services.Workspace(Config(roots=[]))
    s = ws.open(str(root))
    for name in ("sSA", "seSA"):
        r = services.hmi_review(s, ws, name=f"acFlowTransmitter_v1_0.{name}")
        assert r["displays"][0]["style"] == "agile" and r["displays"][0]["findings"] == []
        assert r["cat_reviews"][0]["style"] == "agile"
        assert not [f for f in r["cat_reviews"][0]["findings"] if f["rule"] == "BIND-01"]
    if shutil.which("mcs"):
        stubs = tmp_path / "bridges.cs"
        stubs.write_text(_bridge_stubs(sol, "acFlowTransmitter_v1_0", AGILE))
        out = subprocess.run(["mcs", "-target:library", "-nowarn:67,169,414,649,162,219", f"-out:{tmp_path / 'a.dll'}",
                              str(HERE / "stubs/eae_stubs.cs"), str(stubs), f"{base}.Designer.cs", f"{base}.cs"],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
    if shutil.which("tsc"):
        ts = tmp_path / "sym.ts"
        ts.write_text((root / "SE.Agile/WEB/acFlowTransmitter_v1_0/acFlowTransmitter_v1_0_seSA.sym.ts")
                      .read_text(encoding="utf-8-sig"))
        stub = tmp_path / "stubs.d.ts"
        stub.write_text("declare namespace NxtControl.GuiFramework { class RuntimeSymbol { constructor(); "
                        "find(name: string): any; load(options: any): this; } }\n"
                        "declare namespace System { function DefaultValue(v: any): any; }\n")
        out = subprocess.run(["tsc", "--noEmit", "--experimentalDecorators", "--target", "es2017", "--strict", "false",
                              "--noImplicitAny", "true", str(stub), str(ts)], capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr


def test_agile_paths_are_checked(solar_dir, tmp_path):
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    sol = load_solution(root)
    with pytest.raises(EditError, match="neither an IThis input"):
        sa_tools.build_symbol(sol, "acFlowTransmitter_v1_0", sb.SymbolDesign("X", [sb.ElementSpec("value", "Equipment.NOPE")]))
    with pytest.raises(EditError, match="a value element needs a number"):
        sa_tools.build_symbol(sol, "acFlowTransmitter_v1_0", sb.SymbolDesign("X", [sb.ElementSpec("value", "Equipment.IA")]))


CMD_HMI = Interface(event_inputs=[Event("REQ", with_vars=["Flow"])],
                    event_outputs=[Event("SET", with_vars=["Setpoint"]), Event("START", with_vars=["Start"]),
                                   Event("RESET")],
                    input_vars=[Var("Flow", "REAL")], output_vars=[Var("Setpoint", "REAL"), Var("Start", "BOOL")])
CMD_DESIGN = sb.SymbolDesign("Valve V-1", [
    sb.ElementSpec("value", "Flow", unit="m3/h", range=(0, 120)),
    sb.ElementSpec("setpoint", "Setpoint", label="SP", unit="m3/h"),
    sb.ElementSpec("command", "START", label="Start", value="true", confirm=True),
    sb.ElementSpec("command", "RESET", label="Reset")])


def test_basic_commands(golden_dir, library_store, tmp_path):
    root = tmp_path / "g"
    shutil.copytree(golden_dir, root)
    cat_edit.create_cat(_sol(root, library_store), "catValve", hmi=CMD_HMI).apply()
    cs = sa_tools.build_symbol(_sol(root, library_store), "catValve", CMD_DESIGN)
    assert any("NET symbol only" in w for w in cs.warnings)
    cs.apply()
    base = root / "HMI/catValve/catValve_sSA.cnv"
    designer = Path(f"{base}.Designer.cs").read_bytes().decode("utf-8-sig")
    d = ds.parse(designer)
    assert {"spSetpoint", "cmdSTART2", "cmdRESET3"} <= set(d.objects)
    assert "this.spSetpoint = new System.HMI.Symbols.Base.TextBox<float>();" in designer
    assert 'this.spSetpoint.TagName = "Setpoint";' in designer and "this.spSetpoint.IsOnlyInput = false;" in designer
    assert "this.cmdSTART2 = new NxtControl.GuiFramework.DrawnButton();" in designer
    assert "this.cmdSTART2.Click += new System.EventHandler(this.cmdSTART2Click);" in designer
    code = Path(f"{base}.cs").read_text()
    assert "FireEvent_START(true);" in code and "FireEvent_RESET();" in code and "MessageBox.Show(\"Start?\"" in code
    web = (root / "WEB/catValve/catValve_seSA.sym.json").read_text(encoding="utf-8-sig")
    assert "cmdSTART" not in web and "spSetpoint" not in web
    ws = services.Workspace(Config(roots=[]))
    s = ws.open(str(root))
    for name in ("sSA", "seSA"):
        assert services.hmi_review(s, ws, name=f"catValve.{name}")["displays"][0]["findings"] == []
    if shutil.which("mcs"):
        fire = tmp_path / "fire.cs"
        fire.write_text("namespace HMI.Main.Symbols.catValve { partial class sSA { public bool FireEvent_START(bool Start) "
                        "{ return true; } public bool FireEvent_RESET() { return true; } } }")
        out = subprocess.run(["mcs", "-target:library", "-nowarn:67,169,414,649", f"-out:{tmp_path / 'v.dll'}",
                              str(HERE / "stubs/eae_stubs.cs"), str(fire), f"{base}.Designer.cs", f"{base}.cs"],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr


def test_command_design_errors(golden_dir, library_store, tmp_path):
    root = tmp_path / "g"
    shutil.copytree(golden_dir, root)
    cat_edit.create_cat(_sol(root, library_store), "catValve", hmi=CMD_HMI).apply()
    sol = _sol(root, library_store)
    for el, msg in ((sb.ElementSpec("command", "START"), "value sent with Start"),
                    (sb.ElementSpec("command", "Flow", value="1"), "not an output event"),
                    (sb.ElementSpec("setpoint", "Start"), "needs a number"),
                    (sb.ElementSpec("setpoint", "Flow"), "not an output variable")):
        with pytest.raises(EditError, match=msg):
            sa_tools.build_symbol(sol, "catValve", sb.SymbolDesign("V", [el]), technology="hmi")


def test_agile_commands(solar_dir, tmp_path):
    from eae_mcp.project import agile_edit as ag
    root = tmp_path / "s"
    shutil.copytree(solar_dir, root)
    sigs = [ag.AgileSignal("FLOW", "indication", "real", 0, 120, "m3/h", 1),
            ag.AgileSignal("SP", "control", "real", 0, 120, "m3/h", 1, default="50.0"),
            ag.AgileSignal("ENABLE", "control", "bool"), ag.AgileSignal("MODE", "control", "integer")]
    ag.create_agile_cat(load_solution(root), "acPump_v1_0", sigs).apply()
    design = sb.SymbolDesign("P-101", [
        sb.ElementSpec("value", "FLOW", range=(0, 120), unit="m3/h"),
        sb.ElementSpec("setpoint", "SP", label="Flow SP", step=5),
        sb.ElementSpec("state", "ENABLE", label="Enabled", states={"true": "Yes", "false": "No"}),
        sb.ElementSpec("command", "ENABLE", label="Enable / disable", value="toggle", confirm=True),
        sb.ElementSpec("command", "MODE", label="Auto", value="1")])
    sol = load_solution(root)
    cs = sa_tools.build_symbol(sol, "acPump_v1_0", design)
    cs.apply()
    base = root / "HMI/acPump_v1_0/acPump_v1_0_sSA.cnv"
    code = Path(f"{base}.cs").read_text()
    assert "xSP.FireEvent_CNF((float)v);" in code and "xENABLE.FireEvent_CNF(!xENABLE.Val);" in code
    assert "xMODE.FireEvent_CNF(((short)(1)));" in code and "double lo = xSP.ValMinimum" in code
    ws = services.Workspace(Config(roots=[]))
    r = services.hmi_review(ws.open(str(root)), ws, name="acPump_v1_0.sSA")
    assert r["displays"][0]["findings"] == [] and r["cat_reviews"][0]["style"] == "agile"
    assert not [f for f in r["cat_reviews"][0]["findings"] if f["rule"] in ("AG-01", "BIND-01")]
    with pytest.raises(EditError, match="needs an HMI_Control"):
        sa_tools.build_symbol(sol, "acPump_v1_0", sb.SymbolDesign("P", [sb.ElementSpec("command", "FLOW", value="1")]),
                              technology="hmi", symbol="sX")
    with pytest.raises(EditError, match="step"):
        sa_tools.build_symbol(sol, "acPump_v1_0", sb.SymbolDesign("P", [sb.ElementSpec("setpoint", "SP")]),
                              technology="hmi", symbol="sX")
    if shutil.which("mcs"):
        stubs = tmp_path / "bridges.cs"
        stubs.write_text(_bridge_stubs(sol, "acPump_v1_0", design))
        out = subprocess.run(["mcs", "-target:library", "-nowarn:67,169,414,649,162,219", f"-out:{tmp_path / 'p.dll'}",
                              str(HERE / "stubs/eae_stubs.cs"), str(stubs), f"{base}.Designer.cs", f"{base}.cs"],
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
    if shutil.which("tsc"):
        ts = tmp_path / "sym.ts"
        ts.write_text((root / "WEB/acPump_v1_0/acPump_v1_0_seSA.sym.ts").read_text(encoding="utf-8-sig"))
        stub = tmp_path / "stubs.d.ts"
        stub.write_text("declare namespace NxtControl.GuiFramework { class RuntimeSymbol { constructor(); "
                        "find(name: string): any; load(options: any): this; } }\n"
                        "declare namespace System { function DefaultValue(v: any): any; }\n")
        out = subprocess.run(["tsc", "--noEmit", "--experimentalDecorators", "--target", "es2017", "--strict", "false",
                              "--noImplicitAny", "true", str(stub), str(ts)], capture_output=True, text=True)
        assert out.returncode == 0, out.stdout + out.stderr
