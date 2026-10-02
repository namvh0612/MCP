import datetime as dt
import shutil

import pytest

from eae_mcp.hmi import designer as ds
from eae_mcp.hmi import dotnet_edit as de
from eae_mcp.hmi.reader import load_hmi
from eae_mcp.io import xmlrt
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def test_designer_model_roundtrips_and_readds(golden_dir, solar_dir):
    """Every EAE-written Designer parses back to the same text, and removing then re-adding the topmost
    symbol reproduces the file byte for byte."""
    parsed = readded = 0
    for f in list(solar_dir.rglob("*.cnv.Designer.cs")) + list(golden_dir.rglob("*.cnv.Designer.cs")):
        text = f.read_bytes().decode("utf-8-sig")
        try:
            d = ds.parse(text)
        except ds.DesignerError:
            continue  # fresh symbols without sections, hand-formatted files: refused, never rewritten
        parsed += 1
        assert ds.dumps(d) == text
        last = d.sections[-2] if len(d.sections) > 1 else None
        if (last is None or not last.lines or not last.lines[0].endswith(".BeginInit();")
                or f"this.{last.name}}});" not in text or not d.fields[-1].endswith(f" {last.name};")
                or not all(line.endswith(";") and line.startswith(f"\t\t\tthis.{last.name}.") for line in last.lines)
                or not all(" = " in line for line in last.lines[1:-1])):
            continue
        new_line = next(line for line in d.prelude if line.startswith(f"\t\t\tthis.{last.name} = new "))
        if [line for line in d.prelude if " = new " in line][-1] != new_line:
            continue
        props = [tuple(line.strip()[len(f"this.{last.name}."):-1].split(" = ", 1)) for line in last.lines[1:-1]]
        ds.remove_object(d, last.name)
        ds.add_object(d, last.name, new_line.split(" = new ")[1][:-3], props)
        assert ds.dumps(d) == text, f
        readded += 1
    assert parsed > 150 and readded > 50


def test_place_symbol_like_eae(golden_copy, golden_dir):
    de.remove_object(load_solution(golden_copy), "Canvas1", "CAT1").apply()
    assert "CAT1" not in (golden_copy / "HMI/Canvas1.cnv.Designer.cs").read_text(encoding="utf-8-sig")
    de.place_symbol(load_solution(golden_copy), "Canvas1", "CAT1", x=16, y=8).apply()
    for f in ("Canvas1.cnv.Designer.cs", "Canvas1.cnv.resx"):
        assert (golden_copy / "HMI" / f).read_bytes() == (golden_dir / "HMI" / f).read_bytes(), f


def test_create_canvas_and_place(golden_copy, golden_dir):
    now = dt.datetime(2026, 10, 2, 12, 43)
    de.create_canvas(load_solution(golden_copy), "Canvas2", now=now).apply()
    de.place_symbol(load_solution(golden_copy), "Canvas2", "CAT1", x=16, y=8).apply()
    for f in ("cnv.cs", "cnv.Designer.cs", "cnv.resx"):
        gold = (golden_dir / f"HMI/Canvas1.{f}").read_bytes().replace(b"Canvas1", b"Canvas2")
        assert (golden_copy / f"HMI/Canvas2.{f}").read_bytes() == gold, f
    res = golden_copy / "HMI/CanvasesResolutionList.xml"
    assert '<Canvas Name="Canvas2" Title="" Tooltip="" Instance="HMI.Main.Canvases.Canvas2">' in res.read_text()
    assert xmlrt.roundtrips(res)
    proj = (golden_copy / "HMI/HMI.csproj").read_text(encoding="utf-8-sig")
    assert '<Compile Include="Canvas2.cnv.cs">\r\n      <Canvas>true</Canvas>' in proj.replace("\n", "\r\n").replace("\r\r", "\r")
    idx = load_hmi(load_solution(golden_copy))
    doc = next(d for d in idx.documents if d.name == "Canvas2" and d.technology == "hmi")
    assert doc.kind == "canvas" and [o.tag_name for o in doc.objects] == ["3811CA558F6E3EFC"]


def test_update_object(golden_copy):
    sol = load_solution(golden_copy)
    cs = de.update_object(sol, "Canvas1", "CAT1", {"Visible": "false"}, x=100, y=50)
    text = cs.changes["HMI/Canvas1.cnv.Designer.cs"].new.decode("utf-8-sig")
    assert "this.CAT1.DesignMatrix = new NxtControl.Drawing.Matrix2D(1D, 0D, 0D, 1D, 100D, 50D);" in text
    # inserted alphabetically, inside BeginInit/EndInit
    assert 'this.CAT1.TagName = "3811CA558F6E3EFC";\r\n\t\t\tthis.CAT1.Visible = false;\r\n\t\t\tthis.CAT1.EndInit();' in text
    with pytest.raises(EditError, match="one C# expression"):
        de.update_object(sol, "Canvas1", "CAT1", {"Visible": "false; System.IO.File.Delete(x)"})
    with pytest.raises(EditError, match="No object"):
        de.update_object(sol, "Canvas1", "nope", {"Visible": "false"})
