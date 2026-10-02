import shutil

import pytest

from eae_mcp.io import xmlrt
from eae_mcp.model import Event, Interface, Var
from eae_mcp.project import network_edit as ne
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution, resolve_reference
from eae_mcp.project.validate import validate_solution

from test_write import _normalize


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def load(path, library_store):
    return load_solution(path, library_store=library_store)


def names(sol, td_name):
    td = sol.find_type(td_name)
    return {(c.kind, str(resolve_reference(c.source, td.network, sol, td)),
             str(resolve_reference(c.destination, td.network, sol, td))) for c in td.network.connections}


def test_rebuild_cfbtest_like_eae(golden_copy, library_store, golden_dir):
    """Create a composite and wire it with the tools; compare with EAE's cfbTest."""
    sol = load(golden_copy, library_store)
    itf = Interface(event_inputs=[Event("REQ", comment="Normal Execution Request", with_vars=["X"])],
                    event_outputs=[Event("CNF", comment="Execution Confirmation", with_vars=["Y"])],
                    input_vars=[Var("X", "INT")], output_vars=[Var("Y", "INT")])
    ne.create_composite(sol, "cfbNew", itf).apply()
    steps = [
        lambda s: ne.add_fb(s, "cfbNew", "FB1", "fbTest", parameters={"IN2": "5"}),
        lambda s: ne.add_fb(s, "cfbNew", "FB2", "E_DELAY", parameters={"DT": "T#1s"}),
        lambda s: ne.connect(s, "cfbNew", "REQ", "FB1.REQ"),
        lambda s: ne.connect(s, "cfbNew", "FB2.EO", "CNF"),
        lambda s: ne.connect(s, "cfbNew", "FB1.CNF", "FB2.START"),
        lambda s: ne.connect(s, "cfbNew", "X", "FB1.IN1"),
        lambda s: ne.connect(s, "cfbNew", "FB1.OUT1", "Y"),
    ]
    for step in steps:
        step(load(golden_copy, library_store)).apply()
    sol = load(golden_copy, library_store)
    assert names(sol, "cfbNew") == names(sol, "cfbTest")
    new = (golden_copy / "IEC61499" / "cfbNew.fbt").read_bytes()
    gold = (golden_dir / "IEC61499" / "cfbTest.fbt").read_bytes().replace(b'Name="cfbTest"', b'Name="cfbNew"')
    import re
    refs = lambda b: re.sub(rb"\$[0-9A-F]{6,16}", b"$*", _normalize(b))  # noqa: E731 - generated IDs differ
    assert refs(new) == refs(gold)
    assert xmlrt.roundtrips(golden_copy / "IEC61499" / "cfbNew.fbt")
    assert validate_solution(sol, "cfbNew")["counts"]["error"] == 0
    text = (golden_copy / "IEC61499" / "IEC61499.dfbproj").read_text(encoding="utf-8-sig")
    assert '<Compile Include="cfbNew.fbt">' in text and '<None Include="cfbNew.composite.offline.xml">' in text


def test_connect_rules(golden_copy, library_store):
    sol = load(golden_copy, library_store)
    with pytest.raises(EditError, match="already exists"):
        ne.connect(sol, "cfbTest", "FB1.OUT1", "Y")
    with pytest.raises(EditError, match="already has a source"):
        ne.connect(sol, "cfbTest", "X", "Y")  # Y is already driven by FB1.OUT1
    assert ne.connect(sol, "cfbTest", "X", "Y", replace=True).changes
    with pytest.raises(EditError, match="Cannot connect event"):
        ne.connect(sol, "cfbTest", "FB1.CNF", "FB2.DT")
    with pytest.raises(EditError, match="goes from an output"):
        ne.connect(sol, "cfbTest", "FB1.REQ", "FB2.START")
    with pytest.raises(EditError, match="no pin"):
        ne.connect(sol, "cfbTest", "FB1.NOPE", "FB2.START")
    with pytest.raises(EditError, match="already exists"):
        ne.connect(sol, "cfbTest", "FB2.START", "FB1.CNF")  # reversed order is understood


def test_application_add_connect_map_and_remove(golden_copy, library_store):
    sol = load(golden_copy, library_store)
    ne.add_fb(sol, "APP1", "Delay1", "E_DELAY", parameters={"DT": "T#500ms"}).apply()
    sol = load(golden_copy, library_store)
    ne.connect(sol, "APP1", "CAT1.CNF", "Delay1.START").apply()
    sol = load(golden_copy, library_store)
    ne.map_to_resource(sol, "Delay1", "EcoRT_0/RES0").apply()
    sol = load(golden_copy, library_store)
    res = sol.systems[0].devices[0].resources[0]
    copy = next(i for i in res.network.instances if i.name == "Delay1")
    layer = sol.systems[0].applications[0].layers[0]
    assert copy.mapping == next(i.id for i in layer.network.instances if i.name == "Delay1")
    assert copy.parameters == {"$DT": "T#500ms"}
    # CAT1 and Delay1 now share RES0, so the connection is copied with the resource IDs.
    conns = {(str(resolve_reference(c.source, res.network, sol)), str(resolve_reference(c.destination, res.network, sol)))
             for c in res.network.connections}
    assert ("CAT1.CNF", "Delay1.START") in conns

    ne.set_param(sol, "APP1", "Delay1", "DT", "T#2s").apply()
    sol = load(golden_copy, library_store)
    res = sol.systems[0].devices[0].resources[0]
    assert next(i for i in res.network.instances if i.name == "Delay1").parameters == {"$DT": "T#2s"}

    ne.disconnect(sol, "APP1", "CAT1.CNF", "Delay1.START").apply()
    sol = load(golden_copy, library_store)
    assert not sol.systems[0].devices[0].resources[0].network.connections

    ne.remove_fb(sol, "APP1", "Delay1").apply()
    sol = load(golden_copy, library_store)
    assert [i.name for i in sol.systems[0].devices[0].resources[0].network.instances] == ["CAT1"]
    assert validate_solution(sol)["counts"]["error"] == 0


def test_remove_instance_shown_on_hmi_is_refused(golden_copy, library_store):
    sol = load(golden_copy, library_store)
    with pytest.raises(EditError, match="shown on"):
        ne.remove_fb(sol, "APP1", "CAT1")


def test_unmap(golden_copy, library_store):
    sol = load(golden_copy, library_store)
    ne.unmap(sol, "CAT1").apply()
    sol = load(golden_copy, library_store)
    assert sol.systems[0].devices[0].resources[0].network.instances == []
    ne.map_to_resource(sol, "CAT1", "EcoRT_0/RES0").apply()
    assert load(golden_copy, library_store).systems[0].devices[0].resources[0].network.instances[0].name == "CAT1"


def test_create_subapp_in_application(golden_copy, library_store):
    sol = load(golden_copy, library_store)
    ne.create_subapp(sol, "subLine", "APP1", "LINE1",
                     Interface(event_inputs=[Event("START")], event_outputs=[Event("DONE")])).apply()
    sol = load(golden_copy, library_store)
    td = sol.find_type("subLine")
    assert td.kind == "subapp" and [e.name for e in td.interface.event_inputs] == ["START"]
    layer = sol.systems[0].applications[0].layers[0]
    assert ("LINE1", "SubApp") in {(i.name, i.kind) for i in layer.network.instances}
    ne.add_fb(sol, "subLine", "D1", "E_DELAY").apply()
    ne.connect(load(golden_copy, library_store), "subLine", "START", "D1.START").apply()
    ne.connect(load(golden_copy, library_store), "subLine", "D1.EO", "DONE").apply()
    sol = load(golden_copy, library_store)
    assert names(sol, "subLine") == {("event", "START", "D1.START"), ("event", "D1.EO", "DONE")}
    text = (golden_copy / "IEC61499" / "IEC61499.dfbproj").read_text(encoding="utf-8-sig")
    assert '<Folder Include="subLine" />' in text and "<IEC61499Type>CAT_OFFLINE</IEC61499Type>" in text


def test_unknown_library_type_needs_catalog(golden_copy):
    sol = load_solution(golden_copy)  # no library store
    with pytest.raises(EditError, match="eae_catalog_build"):
        ne.add_fb(sol, "APP1", "D", "E_DELAY")
