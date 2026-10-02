from collections import Counter

from eae_mcp.hmi.reader import load_hmi, parse_designer
from eae_mcp.project.solution import load_solution


def test_golden_hmi_and_ehmi(golden_dir):
    idx = load_hmi(load_solution(golden_dir))
    kinds = Counter((d.technology, d.kind) for d in idx.documents)
    assert kinds == {("hmi", "canvas"): 1, ("hmi", "resolution"): 1, ("hmi", "symbol"): 1,
                     ("ehmi", "canvas"): 1, ("ehmi", "symbol"): 1}
    hmi_canvas = idx.find("Canvas1", "hmi")[0]
    ehmi_canvas = idx.find("Canvas1", "ehmi")[0]
    assert hmi_canvas.objects[0].tag_name == "3811CA558F6E3EFC"
    assert ehmi_canvas.objects[0].tag_name == "3811CA558F6E3EFC"
    assert ehmi_canvas.device == "EcoRT_0"
    symbol = idx.find("sDefault", "hmi")[0]
    assert symbol.cat == "catTest"
    assert symbol.mapping["Inputs"] == [{"Name": "OUT1", "Type": "INT"}]


def test_solar_faceplates_and_symbols(solar_dir):
    idx = load_hmi(load_solution(solar_dir))
    kinds = Counter((d.technology, d.kind) for d in idx.documents)
    assert kinds[("hmi", "faceplate")] == 82
    assert kinds[("hmi", "canvas")] == 3
    fmain = next(d for d in idx.documents if d.cat == "acPPC_v1_0" and d.name == "fMain")
    assert "Plant.Broadcaster_v1_0" in {o.tag_name for o in fmain.objects}


def test_parse_designer_generic_types():
    text = '''private void InitializeComponent()
    {
        this.OUT1 = new System.HMI.Symbols.Base.BarValueHorizontal<short>();
        this.OUT1.TagName = "OUT1";
        this.SymbolSize = new System.Drawing.Size(600, 400);
    }'''
    objects, size = parse_designer(text)
    assert objects[0].type == "System.HMI.Symbols.Base.BarValueHorizontal<short>"
    assert objects[0].tag_name == "OUT1"
    assert size == "600x400"
