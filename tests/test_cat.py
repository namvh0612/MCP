import datetime as dt
import re
import shutil

import pytest

from eae_mcp.io import xmlrt
from eae_mcp.model import Event, Interface, Var
from eae_mcp.project import cat_edit
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution
from eae_mcp.project.validate import validate_solution

NOW = dt.datetime(2026, 10, 2, 11, 34)


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def _norm(data: bytes, name: str = "catNew") -> bytes:
    data = data.replace(b"catTest", name.encode())
    data = re.sub(rb'GUID="[^"]+"', b'GUID="*"', data)
    data = re.sub(rb'(ID|UID)="[0-9A-F]{6,16}"', rb'\1="*"', data)
    data = re.sub(rb"\$[0-9A-F]{6,16}", b"$*", data)
    data = re.sub(rb'Date="[^"]*"', b'Date="*"', data)
    data = re.sub(rb" \* Date: [^\r]*\r\n \* Time: [^\r]*\r\n", b" * Date: *\r\n * Time: *\r\n", data)
    return data.lstrip(b"\xef\xbb\xbf")


def _create(golden_copy, library_store, **kw):
    sol = load_solution(golden_copy, library_store=library_store)
    hmi = Interface(event_inputs=[Event("REQ", with_vars=["OUT1"])], input_vars=[Var("OUT1", "INT")])
    cs = cat_edit.create_cat(sol, "catNew", hmi=hmi, folder=".Core", now=NOW, **kw)
    cs.apply()
    return cs


def test_create_cat_matches_golden(golden_copy, golden_dir, library_store):
    cs = _create(golden_copy, library_store)
    same = {
        "IEC61499/catTest/catTest_HMI.fbt", "IEC61499/catTest/catTest_HMI.opcua.xml",
        "IEC61499/catTest/catTest_CAT.opcua.xml", "IEC61499/catTest/catTest_CAT.offline.xml",
        "IEC61499/catTest/catTest_HMI.offline.xml", "IEC61499/catTest/catTest.doc.xml",
        "HMI/catTest/catTest.event.cs", "HMI/catTest/catTest.def.cs", "HMI/catTest/catTest.Design.resx",
        "HMI/catTest/catTest_sDefault.cnv.cs", "HMI/catTest/catTest_sDefault.cnv.xml",
        "WEB/catTest/catTest_seDefault.sym.ts", "WEB/catTest/catTest_seDefault.user.cs",
    }
    for rel in same:
        new = (golden_copy / rel.replace("catTest", "catNew")).read_bytes()
        assert _norm(new) == _norm((golden_dir / rel).read_bytes()), rel
    cfg = (golden_copy / "IEC61499/catNew/catNew.cfg").read_bytes()
    gold_cfg = _norm((golden_dir / "IEC61499/catTest/catTest.cfg").read_bytes()).replace(b".Logic", b".Core")
    assert cfg == gold_cfg
    # The CAT network differs from catTest (the user added FB1 and connections there); check its core.
    fbt = (golden_copy / "IEC61499/catNew/catNew.fbt").read_text()
    assert 'Name="IThis" Type="catNew_HMI"' in fbt and 'Value="TRUE"' in fbt and '<Attribute Name="HMI.Alias" Value="" />' in fbt

    sol = load_solution(golden_copy, library_store=library_store)
    assert "Main.catNew" in sol.cats
    cat = sol.cats["Main.catNew"]
    assert [s.name for s in cat.symbols] == ["sDefault", "seDefault"]
    td = sol.find_type("catNew")
    assert td.kind == "cat" and sol.find_type("catNew_HMI").kind == "cat_hmi"
    assert validate_solution(sol, "catNew")["counts"]["error"] == 0
    for rel in cs.changes:
        if rel.endswith((".fbt", ".cfg", "proj")):
            assert xmlrt.roundtrips(golden_copy / rel), rel


def test_create_cat_registration_like_golden(golden_copy, golden_dir, library_store):
    _create(golden_copy, library_store)

    def items(path, name):
        text = path.read_text(encoding="utf-8-sig")
        return re.findall(rf"<(\w+) Include=\"[^\"]*{name}[^\"]*\"(?: />|>.*?</\1>)", text, re.S), text

    for proj in ("IEC61499/IEC61499.dfbproj", "HMI/HMI.csproj", "WEB/WEB.htmlproj"):
        gold_text = (golden_dir / proj).read_text(encoding="utf-8-sig")
        new_text = (golden_copy / proj).read_text(encoding="utf-8-sig")
        pat = r"<(Compile|None|EmbeddedResource) Include=\"[^\"]*{n}[^\"]*\"(?: />|>.*?</\1>)"
        gold = [m.group(0) for m in re.finditer(pat.format(n="catTest"), gold_text, re.S)]
        new = [m.group(0).replace("catNew", "catTest") for m in re.finditer(pat.format(n="catNew"), new_text, re.S)]
        assert sorted(new) == sorted(gold), proj


def test_create_cat_without_web_symbol(golden_copy, library_store):
    sol = load_solution(golden_copy, library_store=library_store)
    cs = cat_edit.create_cat(sol, "catPlain", web_symbol=None)
    assert not any(rel.startswith("WEB/") for rel in cs.changes)
    assert b"WebSymbol" not in cs.changes["IEC61499/catPlain/catPlain.cfg"].new


def test_create_cat_rejects_reserved_hmi_names(golden_copy, library_store):
    sol = load_solution(golden_copy, library_store=library_store)
    with pytest.raises(EditError, match="already"):
        cat_edit.create_cat(sol, "catX", hmi=Interface(input_vars=[Var("STATUS", "STRING")]))
    with pytest.raises(EditError, match="exists"):
        cat_edit.create_cat(sol, "catTest")


def test_wire_cat_network(golden_copy, library_store):
    from eae_mcp.project import network_edit as ne
    from eae_mcp.project.solution import resolve_reference

    _create(golden_copy, library_store)
    ne.add_fb(load_solution(golden_copy, library_store=library_store), "catNew", "FB1", "fbTest").apply()
    ne.connect(load_solution(golden_copy, library_store=library_store), "catNew", "FB1.CNF", "IThis.REQ").apply()
    ne.connect(load_solution(golden_copy, library_store=library_store), "catNew", "FB1.OUT1", "IThis.OUT1").apply()
    sol = load_solution(golden_copy, library_store=library_store)
    td = sol.find_type("catNew")
    conns = {(str(resolve_reference(c.source, td.network, sol, td)), str(resolve_reference(c.destination, td.network, sol, td)))
             for c in td.network.connections}
    assert conns == {("FB1.CNF", "IThis.REQ"), ("FB1.OUT1", "IThis.OUT1")}
    assert validate_solution(sol, "catNew")["counts"]["error"] == 0


def test_cat_inside_cat_is_listed_as_subcat(golden_copy, library_store):
    from eae_mcp.project import network_edit as ne

    _create(golden_copy, library_store)
    ne.add_fb(load_solution(golden_copy, library_store=library_store), "catNew", "Inner", "catTest").apply()
    cfg = (golden_copy / "IEC61499/catNew/catNew.cfg").read_bytes().decode()
    assert '>\r\n  <SubCAT Name="Inner" Type="catTest" Namespace="Main" UsedInCAT="true" />\r\n  <HMIInterface' in cfg
    sol = load_solution(golden_copy, library_store=library_store)
    assert [(s.name, s.type) for s in sol.cats["Main.catNew"].sub_cats] == [("Inner", "catTest")]
    ne.remove_fb(sol, "catNew", "Inner").apply()
    assert "SubCAT" not in (golden_copy / "IEC61499/catNew/catNew.cfg").read_text()


def test_hmi_interface_change_regenerates_code(golden_copy, golden_dir, library_store):
    """Adding OUT1/REQ to a fresh CAT's IThis gives the same generated files as EAE's catTest."""
    from eae_mcp.project import edit

    sol = load_solution(golden_copy, library_store=library_store)
    cat_edit.create_cat(sol, "catNew", folder=".Core", now=NOW).apply()
    sol = load_solution(golden_copy, library_store=library_store)
    cs = edit.update_interface(sol, "catNew_HMI", add_vars=[("input", Var("OUT1", "INT"))],
                               add_events=[("input", Event("REQ", with_vars=["OUT1"]))])
    assert {"HMI/catNew/catNew.event.cs", "HMI/catNew/catNew_sDefault.cnv.xml",
            "IEC61499/catNew/catNew_HMI.opcua.xml"} <= set(cs.changes)
    cs.apply()
    for rel in ("HMI/catTest/catTest.event.cs", "HMI/catTest/catTest_sDefault.cnv.xml",
                "IEC61499/catTest/catTest_HMI.opcua.xml"):
        new = (golden_copy / rel.replace("catTest", "catNew")).read_bytes()
        assert _norm(new) == _norm((golden_dir / rel).read_bytes()), rel


def test_add_symbols_to_cat(golden_copy, library_store):
    sol = load_solution(golden_copy, library_store=library_store)
    cat_edit.add_symbol(sol, "catTest", "sBig").apply()
    cat_edit.add_symbol(load_solution(golden_copy, library_store=library_store), "catTest", "fMain", faceplate=True).apply()
    cat_edit.add_symbol(load_solution(golden_copy, library_store=library_store), "catTest", "seBig", "ehmi").apply()
    sol = load_solution(golden_copy, library_store=library_store)
    cat = sol.cats["Main.catTest"]
    assert [(s.name, s.technology, s.is_faceplate) for s in cat.symbols] == [
        ("sDefault", "hmi", False), ("sBig", "hmi", False), ("fMain", "hmi", True), ("seDefault", "ehmi", False),
        ("seBig", "ehmi", False)]
    event = (golden_copy / "HMI/catTest/catTest.event.cs").read_text()
    assert "partial class sBig" in event and "namespace HMI.Main.Faceplates.catTest" in event
    defs = (golden_copy / "HMI/catTest/catTest.def.cs").read_text()
    assert "private HMI.Main.Faceplates.catTest.fMain fMain" in defs and "partial class sBig" in defs
    assert b"HMIFaceplate" in (golden_copy / "HMI/catTest/catTest_fMain.cnv.cs").read_bytes()
    assert not (golden_copy / "HMI/catTest/catTest_fMain.cnv.xml").exists()
    assert (golden_copy / "HMI/catTest/catTest_sBig.cnv.xml").read_bytes() == \
        (golden_copy / "HMI/catTest/catTest_sDefault.cnv.xml").read_bytes()
    csproj = (golden_copy / "HMI/HMI.csproj").read_text(encoding="utf-8-sig")
    assert 'Include="catTest\\catTest_fMain.cnv.resx"' in csproj and 'catTest_fMain.cnv.xml' not in csproj
    assert 'catTest\\catTest_seBig.sym.ts' in (golden_copy / "WEB/WEB.htmlproj").read_text(encoding="utf-8-sig")
    assert xmlrt.roundtrips(golden_copy / "IEC61499/catTest/catTest.cfg")
    with pytest.raises(EditError, match="already has a symbol"):
        cat_edit.add_symbol(sol, "catTest", "sBig")
