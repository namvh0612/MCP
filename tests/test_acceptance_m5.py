"""The docs/ACCEPTANCE_M5.md scenario, end to end on a copy of the golden project."""

import shutil

from eae_mcp.hmi import dotnet_edit as de
from eae_mcp.hmi import ehmi_edit as ee
from eae_mcp.hmi.reader import load_hmi
from eae_mcp.io import xmlrt
from eae_mcp.model import Event, Interface, Var
from eae_mcp.project import cat_edit, opcua_edit
from eae_mcp.project import network_edit as ne
from eae_mcp.project.solution import load_solution
from eae_mcp.project.validate import validate_solution


def test_acceptance_scenario(golden_dir, library_store, tmp_path):
    root = tmp_path / "EAE_MCP_M5"
    shutil.copytree(golden_dir, root)

    def sol():
        return load_solution(root, library_store=library_store)

    changed: set[str] = set()

    def do(cs):
        assert not [w for w in cs.warnings if w.startswith("error")], cs.warnings
        changed.update(cs.changes)
        cs.apply()

    hmi = Interface(event_inputs=[Event("REQ", with_vars=["Value"])], event_outputs=[Event("CMD", with_vars=["Start"])],
                    input_vars=[Var("Value", "INT")], output_vars=[Var("Start", "BOOL")])
    do(cat_edit.create_cat(sol(), "catPump", hmi=hmi, folder=".M5"))                       # D1
    do(ne.add_fb(sol(), "catPump", "FB1", "fbTest"))                                       # D2
    for a, b in (("INIT", "FB1.INIT"), ("REQ", "FB1.REQ"), ("FB1.CNF", "IThis.REQ"), ("FB1.OUT1", "IThis.Value"),
                 ("IThis.INITO", "INITO")):
        do(ne.connect(sol(), "catPump", a, b))
    do(ne.add_fb(sol(), "catPump", "Sub1", "catTest"))                                     # D3
    do(cat_edit.add_symbol(sol(), "catPump", "sBig"))                                      # D4
    do(cat_edit.add_symbol(sol(), "catPump", "fMain", faceplate=True))
    do(cat_edit.add_symbol(sol(), "catPump", "seBig", "ehmi"))
    do(ne.add_fb(sol(), "APP1", "PUMP1", "catPump"))                                       # D5
    do(ne.map_to_resource(sol(), "PUMP1", "EcoRT_0/RES0"))
    do(opcua_edit.set_exposed(sol(), "PUMP1.IThis.Value"))                                 # D6
    do(ee.create_canvas(sol(), "EcoRT_0", "Pumps"))                                        # D7
    do(ee.place_symbol(sol(), "EcoRT_0/Pumps", "PUMP1"))
    do(de.create_canvas(sol(), "Pumps"))                                                   # D8
    do(de.place_symbol(sol(), "Pumps", "PUMP1", x=40, y=40))
    do(de.update_object(sol(), "Canvas1", "CAT1", x=200, y=100))                           # D9

    s = sol()                                                                              # D10
    report = validate_solution(s)
    assert report["counts"]["error"] == 0, report
    cat = s.cats["Main.catPump"]
    assert [x.name for x in cat.symbols] == ["sDefault", "sBig", "fMain", "seDefault", "seBig"]
    assert [x.name for x in cat.sub_cats] == ["Sub1"]
    pump_id = next(i.id for i in s.systems[0].applications[0].layers[0].network.instances if i.name == "PUMP1")
    exposed = [o for sy in s.systems for o in sy.opcua if o.exposed]
    assert any(o.context.startswith(pump_id + ".") for o in exposed)  # layer side
    assert len(exposed) == 4  # CAT1 and PUMP1, each in the layer and the resource
    idx = load_hmi(s)
    bound = {(d.technology, d.name) for d in idx.documents if any(o.tag_name == pump_id for o in d.objects)}
    assert bound == {("hmi", "Pumps"), ("ehmi", "Pumps")}
    for rel in changed:
        if rel.endswith((".xml", ".fbt", "proj", ".cfg", ".syslay", ".sysres")) and (root / rel).stat().st_size:
            assert xmlrt.roundtrips(root / rel), rel
