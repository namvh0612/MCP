import re
import shutil

import pytest

from eae_mcp.io import xmlrt
from eae_mcp.model import Var
from eae_mcp.project import edit
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution

CODE = ";\nIF Value < 10 THEN\n    DINT_TO_STRING_2D := CONCAT('0', TO_STRING(Value));\nELSE\n    DINT_TO_STRING_2D := TO_STRING(Value);\nEND_IF;\n"


def _norm(b: bytes) -> bytes:
    b = re.sub(rb'GUID="[^"]+"', b'GUID="*"', b)
    b = re.sub(rb'ID="[0-9A-F]{16}"', b'ID="*"', b)
    return re.sub(rb'Date="[^"]*"', b'Date="*"', b)


def test_create_function_like_eae(solar_dir, tmp_path):
    root = tmp_path / "solar"
    shutil.copytree(solar_dir, root)
    gold = (root / "IEC61499/POU/DINT_TO_STRING_2D.fct").read_bytes()
    (root / "IEC61499/POU/DINT_TO_STRING_2D.fct").unlink()
    text = (root / "IEC61499/IEC61499.dfbproj").read_text(encoding="utf-8-sig")
    # Remove the registration, then recreate the function and compare with what EAE wrote.
    proj = (root / "IEC61499/IEC61499.dfbproj").read_bytes()
    for pat in (rb'    <None Include="POU\\DINT_TO_STRING_2D.doc.xml">\r\n.*?</None>\r\n',
                rb'    <Compile Include="POU\\DINT_TO_STRING_2D.fct">\r\n.*?</Compile>\r\n'):
        proj = re.sub(pat, b"", proj, count=1, flags=re.S)
    (root / "IEC61499/IEC61499.dfbproj").write_bytes(proj)
    (root / "IEC61499/POU/DINT_TO_STRING_2D.doc.xml").unlink()
    sol = load_solution(root)
    cs = edit.create_function(sol, "DINT_TO_STRING_2D", CODE, inputs=[Var("Value", "DINT")], return_type="STRING")
    assert not cs.warnings
    cs.apply()
    assert _norm((root / "IEC61499/POU/DINT_TO_STRING_2D.fct").read_bytes()) == _norm(gold)
    after = (root / "IEC61499/IEC61499.dfbproj").read_text(encoding="utf-8-sig")
    assert re.sub(r"\s+", " ", after) == re.sub(r"\s+", " ", text)
    assert xmlrt.roundtrips(root / "IEC61499/POU/DINT_TO_STRING_2D.fct")


def test_function_inout_update_and_warnings(golden_dir, tmp_path):
    root = tmp_path / "g"
    shutil.copytree(golden_dir, root)
    sol = load_solution(root)
    cs = edit.create_function(sol, "SumArray", "FOR i := 0 TO 9 DO s := s + Data[i]; END_FOR;",
                              inouts=[Var("Data", "REAL", array_size="*")], return_type="REAL",
                              temp_vars=[Var("i", "DINT"), Var("s", "REAL", initial_value="0.0")])
    assert any("never assigns" in w for w in cs.warnings) and any("UPPER_BOUND" in w for w in cs.warnings)
    cs.apply()
    td = load_solution(root).find_type("SumArray")
    assert td.kind == "function" and td.interface.inout_vars[0].array_size == "*"
    cs = edit.update_function(load_solution(root), "SumArray",
                              code="s := 0.0;\nFOR i := 0 TO UPPER_BOUND(Data, 1) DO s := s + Data[i]; END_FOR;\nSumArray := s;\n")
    assert not cs.warnings
    cs.apply()
    td = load_solution(root).find_type("SumArray")
    assert "SumArray := s;" in td.algorithms[0].text and [v.name for v in td.internal_vars] == ["i", "s"]
    with pytest.raises(EditError, match="Duplicate"):
        edit.create_function(load_solution(root), "F2", "F2 := x;", inputs=[Var("x", "INT"), Var("X", "INT")],
                             return_type="INT")
