import json
import shutil

import pytest

from eae_mcp import services
from eae_mcp.config import Config
from eae_mcp.io import xmlrt
from eae_mcp.model import (Algorithm, DataTypeDef, ECAction, ECState, ECTransition, EnumValue, Event, Interface,
                           Var)
from eae_mcp.project import edit
from eae_mcp.project.solution import load_solution, resolve_reference
from eae_mcp.project.types import children
from eae_mcp.project.validate import validate_solution


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def basic_spec():
    itf = Interface(
        event_inputs=[Event("INIT", with_vars=["QI"]), Event("REQ", with_vars=["SP", "PV"])],
        event_outputs=[Event("INITO", with_vars=["QO"]), Event("CNF", with_vars=["OUT"])],
        input_vars=[Var("QI", "BOOL"), Var("SP", "REAL"), Var("PV", "REAL")],
        output_vars=[Var("QO", "BOOL"), Var("OUT", "REAL")],
    )
    states = [ECState("Init", actions=[ECAction("Init", "INITO")]), ECState("Run", actions=[ECAction("Calc", "CNF")])]
    transitions = [ECTransition("START", "Init", "INIT"), ECTransition("Init", "START", "1"),
                   ECTransition("START", "Run", "REQ"), ECTransition("Run", "START", "1")]
    algorithms = [Algorithm("Init", "QO := QI;"), Algorithm("Calc", "OUT := Kp * (SP - PV);")]
    return itf, [Var("Kp", "REAL", initial_value="1.0")], states, transitions, algorithms


def test_dry_run_writes_nothing(golden_copy):
    sol = load_solution(golden_copy)
    before = sorted(p.name for p in (golden_copy / "IEC61499").iterdir())
    cs = edit.create_adapter(sol, "aNew", Interface(event_inputs=[Event("REQ")]))
    assert {c["file"] for c in cs.summary()} == {
        "IEC61499/aNew.adp", "IEC61499/aNew.doc.xml", "IEC61499/IEC61499.dfbproj"}
    assert "+    <Compile Include=\"aNew.adp\">" in cs.diff()
    assert sorted(p.name for p in (golden_copy / "IEC61499").iterdir()) == before


def test_recreated_adapter_registration_matches_eae_byte_for_byte(golden_copy):
    """Remove aTest's registration, re-create it with the tool: the .dfbproj must equal EAE's."""
    proj = golden_copy / "IEC61499" / "IEC61499.dfbproj"
    original = proj.read_bytes()
    xf = xmlrt.load(proj)
    for group in children(xf.root, "ItemGroup"):
        for item in children(group):
            if item.get("Include") in ("aTest.adp", "aTest.doc.xml"):
                xmlrt.remove_child(item)
    xmlrt.save(xf)
    (golden_copy / "IEC61499" / "aTest.adp").unlink()
    (golden_copy / "IEC61499" / "aTest.doc.xml").unlink()

    sol = load_solution(golden_copy)
    itf = Interface(
        event_inputs=[Event("REQ", comment="Request from Socket", with_vars=["ReqValue"])],
        event_outputs=[Event("CNF", comment="Confirmation from Plug", with_vars=["CnfValue"])],
        input_vars=[Var("ReqValue", "INT")], output_vars=[Var("CnfValue", "INT")],
    )
    cs = edit.create_adapter(sol, "aTest", itf, folder=".Core")
    cs.changes.pop("General/Folders.xml", None)  # EAE left Folders.xml stale here (C7b quirk)
    cs.apply()
    assert proj.read_bytes() == original
    doc = golden_copy / "IEC61499" / "aTest.doc.xml"
    assert doc.read_bytes() == (load_solution.__globals__["Path"](__file__).parent / "fixtures/golden/IEC61499/aTest.doc.xml").read_bytes()


def test_create_basic_fb_end_to_end(golden_copy):
    sol = load_solution(golden_copy)
    cs = edit.create_basic(sol, "fbPI", *basic_spec(), folder=".Control")
    assert not [w for w in cs.warnings if w.startswith("error")]
    cs.apply()
    sol = load_solution(golden_copy)
    fb = sol.find_type("fbPI")
    assert fb.kind == "basic" and fb.folder == ".Control"
    assert [s.name for s in fb.states] == ["START", "Init", "Run"]
    assert fb.algorithms[1].text == "OUT := Kp * (SP - PV);"
    assert fb.internal_vars[0].initial_value == "1.0"
    assert (golden_copy / "IEC61499" / "fbPI.meta.xml").read_bytes() == xmlrt.BOM
    assert xmlrt.roundtrips(golden_copy / "IEC61499" / "fbPI.fbt")
    assert xmlrt.roundtrips(golden_copy / "IEC61499" / "IEC61499.dfbproj")
    folders = (golden_copy / "General" / "Folders.xml").read_text(encoding="utf-8")
    assert '<Folder Type="Basic" Name=".Control">' in folders
    assert validate_solution(sol, "fbPI")["counts"]["error"] == 0


def test_create_datatypes(golden_copy):
    sol = load_solution(golden_copy)
    edit.create_datatype(sol, "dtMode", DataTypeDef("enum", base_type="USINT",
                                                    values=[EnumValue("Off_", "0"), EnumValue("Auto", "1")])).apply()
    sol = load_solution(golden_copy)
    edit.create_datatype(sol, "dtPoint", DataTypeDef("struct", members=[Var("X", "REAL"), Var("Y", "REAL")])).apply()
    sol = load_solution(golden_copy)
    assert [v.name for v in sol.find_type("dtMode").datatype.values] == ["Off_", "Auto"]
    assert sol.find_type("dtPoint").path == "IEC61499/DataType/dtPoint.dt"
    text = (golden_copy / "IEC61499" / "IEC61499.dfbproj").read_text(encoding="utf-8-sig")
    assert text.index('Include="DataType\\dtMode.dt"') < text.index('Include="DataType\\dtPoint.dt"') \
        < text.index('Include="DataType\\dtRange.dt"')


@pytest.mark.parametrize("bad", [
    lambda s: edit.create_datatype(s, "dtX", DataTypeDef("enum", values=[EnumValue("On")])),
    lambda s: edit.create_adapter(s, "aTest", Interface()),
    lambda s: edit.create_adapter(s, "1bad", Interface()),
    lambda s: edit.create_adapter(s, "aY", Interface(event_inputs=[Event("REQ", with_vars=["Missing"])])),
    lambda s: edit.create_basic(s, "fbY", Interface(event_inputs=[Event("REQ")]), [],
                                [ECState("S1", actions=[ECAction("Nope")])], [], []),
])
def test_invalid_specs_are_rejected(golden_copy, bad):
    sol = load_solution(golden_copy)
    with pytest.raises(ValueError):
        bad(sol)


def test_update_interface_keeps_connections(golden_copy):
    sol = load_solution(golden_copy)
    cs = edit.update_interface(sol, "fbTest", add_vars=[("input", Var("IN3", "INT"))],
                               set_with={"REQ": ["QI", "IN1", "IN2", "IN3"]})
    cs.apply()
    sol = load_solution(golden_copy)
    fb = sol.find_type("fbTest")
    assert fb.interface.event_inputs[1].with_vars == ["QI", "IN1", "IN2", "IN3"]
    cfb = sol.find_type("cfbTest")
    ends = {str(resolve_reference(c.destination, cfb.network, sol)) for c in cfb.network.connections}
    assert {"FB1.REQ", "FB1.IN1"} <= ends  # IDs unchanged → existing wiring intact


def test_remove_used_pin_is_refused(golden_copy):
    sol = load_solution(golden_copy)
    with pytest.raises(edit.EditError, match="still used"):
        edit.update_interface(sol, "fbTest", remove=["IN1"])
    try:
        edit.update_interface(sol, "fbTest", remove=["IN1"])
    except edit.EditError as e:
        assert "algorithm Calc" in str(e) and "cfbTest" in str(e)
    cs = edit.update_interface(sol, "fbTest", remove=["IN1"], force=True)
    new = cs.changes["IEC61499/fbTest.fbt"].new.decode()
    assert 'Name="IN1"' not in new and '<With Var="IN1" />' not in new


def test_algorithms_and_ecc(golden_copy):
    sol = load_solution(golden_copy)
    edit.upsert_algorithm(sol, "fbTest", "Calc", "OUT1 := IN1 * IN2;").apply()
    sol = load_solution(golden_copy)
    edit.upsert_algorithm(sol, "fbTest", "Reset", "Counter := 0;").apply()
    sol = load_solution(golden_copy)
    edit.update_ecc(sol, "fbTest", add_states=[ECState("Clear", actions=[ECAction("Reset", "CNF")])],
                    add_transitions=[ECTransition("START", "Clear", "INIT AND NOT QI"),
                                     ECTransition("Clear", "START", "1")]).apply()
    sol = load_solution(golden_copy)
    fb = sol.find_type("fbTest")
    assert fb.algorithms[1].text == "OUT1 := IN1 * IN2;"
    assert fb.attributes["FBType.Basic.Algorithm.Order"] == "Init,Calc,Reset"
    assert "Clear" in [s.name for s in fb.states]
    assert validate_solution(sol, "fbTest")["counts"]["error"] == 0
    edit.update_ecc(sol, "fbTest", remove_states=["Clear"]).apply()
    fb = load_solution(golden_copy).find_type("fbTest")
    assert "Clear" not in [s.name for s in fb.states]
    assert not [t for t in fb.transitions if "Clear" in (t.source, t.destination)]


def test_ecc_rejects_unknown_algorithm(golden_copy):
    sol = load_solution(golden_copy)
    with pytest.raises(edit.EditError):
        edit.update_ecc(sol, "fbTest", set_actions={"Run": [ECAction("Missing", "CNF")]})


def test_replace_datatype_drops_stale_blob(golden_copy):
    sol = load_solution(golden_copy)
    cs = edit.replace_datatype(sol, "dtStruct", DataTypeDef("struct", members=[Var("A", "INT"), Var("Z", "LREAL")]))
    new = cs.changes["IEC61499/DataType/dtStruct.dt"].new.decode()
    assert "nxtDataType" not in new and 'Name="Z" Type="LREAL"' in new


def test_backup_audit_and_conflict(golden_copy):
    sol = load_solution(golden_copy)
    cs = edit.upsert_algorithm(sol, "fbTest", "Calc", "OUT1 := 0;")
    result = cs.apply()
    assert (golden_copy / ".eae-mcp" / "audit.jsonl").exists()
    assert result["backup"] and list((golden_copy / ".eae-mcp" / "backup").rglob("fbTest.fbt"))
    pending = edit.upsert_algorithm(sol, "fbTest", "Calc", "OUT1 := 1;")
    path = golden_copy / "IEC61499" / "fbTest.fbt"
    path.write_bytes(path.read_bytes().replace(b"OUT1 := 0;", b"OUT1 := 2;"))  # edited in EAE meanwhile
    with pytest.raises(RuntimeError, match="changed on disk"):
        pending.apply()
    assert b"OUT1 := 2;" in path.read_bytes()


def test_run_change_requires_allow_write(golden_copy):
    ws = services.Workspace(Config(roots=[], allow_write=False))
    sol = ws.open(str(golden_copy))
    build = lambda: edit.create_adapter(sol, "aNew", Interface(event_inputs=[Event("REQ")]))  # noqa: E731
    assert services.run_change(ws, sol, build, dry_run=True)["dry_run"]
    with pytest.raises(services.NotFound, match="allow_write"):
        services.run_change(ws, sol, build, dry_run=False)
    ws.config.allow_write = True
    out = services.run_change(ws, sol, build, dry_run=False)
    assert "IEC61499/aNew.adp" in out["written"]
    assert ws.get().find_type("aNew") is not None  # re-indexed


def test_write_tools_over_mcp(golden_copy):
    import anyio
    from mcp import Client

    from eae_mcp.server import create_server

    async def scenario():
        server = create_server(Config(roots=[], allow_write=True))
        async with Client(server) as client:
            await client.call_tool("eae_open_solution", {"path": str(golden_copy)})
            r = await client.call_tool("eae_datatype_create", {
                "name": "dtLevel", "kind": "subrange", "base_type": "INT", "ranges": [[0, 10]], "dry_run": False})
            assert not r.is_error, r.content[0].text
            r = await client.call_tool("eae_validate", {"name": "dtLevel"})
            data = r.structured_content or json.loads(r.content[0].text)
            assert data["counts"]["error"] == 0
            r = await client.call_tool("eae_datatype_create", {"name": "dtLevel", "kind": "struct"})
            assert r.is_error

    anyio.run(scenario)


def _normalize(data: bytes) -> bytes:
    """Semantic form: drop generated IDs, dates, layout and EAE-only blobs, then canonicalize."""
    from lxml import etree

    root = xmlrt.parse_bytes(data).root
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        for attr in ("ID", "GUID", "Date", "x", "y"):
            el.attrib.pop(attr, None)
        if el.tag == "Attribute" and el.get("Name") in ("nxtDataType", "Configuration.Transaction.BezierPoints"):
            el.getparent().remove(el)
    for el in root.iter():
        if isinstance(el.tag, str):
            if el.text is not None and not el.text.strip():
                el.text = None
            if el.tail is not None and not el.tail.strip():
                el.tail = None
    return etree.tostring(root, method="c14n")


def test_generated_types_match_eae_golden(golden_dir):
    from eae_mcp.project import writer as w

    gold = golden_dir / "IEC61499"
    itf = Interface(
        event_inputs=[Event("REQ", comment="Request from Socket", with_vars=["ReqValue"])],
        event_outputs=[Event("CNF", comment="Confirmation from Plug", with_vars=["CnfValue"])],
        input_vars=[Var("ReqValue", "INT")], output_vars=[Var("CnfValue", "INT")])
    assert _normalize(w.build_adapter("aTest", itf)) == _normalize((gold / "aTest.adp").read_bytes())
    cases = {
        "dtStruct": DataTypeDef("struct", members=[Var("A", "INT"), Var("B", "REAL"), Var("C", "STRING[20]"),
                                                   Var("D", "BOOL")]),
        "dtEnum": DataTypeDef("enum", base_type="USINT", values=[EnumValue("Stop", "0"), EnumValue("Run", "1"),
                                                                  EnumValue("Fault", "2")]),
        "dtArray": DataTypeDef("array", base_type="INT", ranges=[("0", "9")]),
        "dtRange": DataTypeDef("subrange", base_type="INT", ranges=[("0", "100")]),
    }
    for name, dt in cases.items():
        assert _normalize(w.build_datatype(name, dt)) == _normalize((gold / "DataType" / f"{name}.dt").read_bytes()), name
    itf = Interface(
        event_inputs=[Event("INIT", comment="Initialization Request", with_vars=["QI"]),
                      Event("REQ", comment="Normal Execution Request", with_vars=["QI", "IN1", "IN2"])],
        event_outputs=[Event("INITO", comment="Initialization Confirm", with_vars=["QO"]),
                       Event("CNF", comment="Execution Confirmation", with_vars=["QO", "OUT1", "OUT2"])],
        input_vars=[Var("QI", "BOOL", comment="Input event qualifier"), Var("IN1", "INT"), Var("IN2", "INT")],
        output_vars=[Var("QO", "BOOL", comment="Output event qualifier"), Var("OUT1", "INT"), Var("OUT2", "BOOL")])
    fb = w.build_basic(
        "fbTest", itf, [Var("Counter", "INT")],
        [ECState("START", "Initial State"), ECState("Init", "Initialization", [ECAction("Init", "INITO")]),
         ECState("Run", "Normal execution", [ECAction("Calc", "CNF")])],
        [ECTransition("START", "Init", "INIT"), ECTransition("Init", "START", "1"),
         ECTransition("START", "Run", "REQ"), ECTransition("Run", "START", "1")],
        [Algorithm("Init", "QO := QI; \nCounter := 0;"),
         Algorithm("Calc", "Counter := Counter + 1;\nOUT1 := IN1 + IN2;\nOUT2 := OUT1 > 100;")])
    assert _normalize(fb) == _normalize((gold / "fbTest.fbt").read_bytes())


def test_write_into_library_project(solar_dir, tmp_path):
    dest = tmp_path / "solar"
    shutil.copytree(solar_dir, dest)
    sol = load_solution(dest)
    cs = edit.create_adapter(sol, "aDemo_v1_0", Interface(event_inputs=[Event("REQ")]), folder=".Standard.Demo",
                             library="SE.Agile")
    assert {c["file"] for c in cs.summary()} == {
        "SE.Agile/IEC61499/aDemo_v1_0.adp", "SE.Agile/IEC61499/aDemo_v1_0.doc.xml",
        "SE.Agile/IEC61499/SE.Agile.dfbproj", "SE.Agile/General/Folders.xml"}
    cs.apply()
    sol = load_solution(dest)
    td = sol.find_type("aDemo_v1_0")
    assert (td.namespace, td.project, td.folder) == ("SE.Agile", "SE.Agile", ".Standard.Demo")
    assert ".Standard.Demo" in sol.folders["SE.Agile"].as_tree()["Adapter"]
