from eae_mcp import services
from eae_mcp.project import library_guide as lg
from eae_mcp.project.solution import load_solution


def test_library_guide_drill_down(solar_dir):
    sol = load_solution(solar_dir)
    top = lg.library_guide(sol)
    libs = {x["library"]: x for x in top["libraries"]}
    assert libs["SE.Agile"]["kinds"]["function"] == 39 and "VALFORMAT" in top["generic_fb_families"]
    assert "SE.Standard" in top["system_libraries"]
    folders = {f["folder"]: f for f in lg.library_guide(sol, "SE.Agile")["folders"]}
    assert "(function)" in folders and ".Standard.HMI" in folders
    hmi = lg.library_guide(sol, "SE.Agile", ".Standard.HMI")["types"]
    top_hmi = max((t for t in hmi if t["kind"] == "cat"), key=lambda t: t.get("uses", 0))
    assert top_hmi["name"] == "SE.Agile.HMI_Indication_Bool_v1_0" and top_hmi["uses"] > 100
    hits = lg.library_guide(sol, query="IsDigit")["results"]
    assert hits[0]["signature"] == "Ch:STRING[1] -> RETURN:BOOL"


def test_functions_keep_inout_and_type_namespace(solar_dir):
    sol = load_solution(solar_dir)
    td = sol.find_type("ConnectionBRemove_v1_0")
    inout = {v.name: v for v in td.interface.inout_vars}
    assert inout["Connections"].namespace == "SE.Agile" and inout["Connections"].array_size == "*"
    assert "INOUT Connections:ConnectionStatus_v1_0[*]" in lg.signature(td)


def test_generic_registry_and_params(solar_dir):
    sol = load_solution(solar_dir)
    assert lg.parse_generic_params("Runtime.Standard#I:=2;VALUE${I}:STRING,INT") == {
        "library": "Runtime.Standard", "counts": {"I": 2}, "pins": {"VALUE${I}": ["STRING", "INT"]}}
    reg = lg.generic_registry(sol)
    # The suffix depends only on the full parameter string (library included), not on the template.
    by_params = {}
    for g in reg:
        by_params.setdefault(g["params"], set()).add(g["type"].rsplit("_", 1)[1])
    assert len({g["base"] for g in reg if g["params"] == "Runtime.System#I:=1;VALUE${I}:STRING"}) == 2
    assert all(len(v) == 1 for v in by_params.values())
    pins = lg.learned_pins(sol)["PERSISTENCE_136D5288BCBDA0681"]
    assert pins["READ"] == ("event", "in") and pins["output1"] == ("data", "out")


def test_knowledge_search_returns_sections():
    hits = services.knowledge_search("E_PERMIT interlock")
    assert hits[0]["concept"] == "standard-library" and "E_PERMIT" in hits[0]["text"]
    assert len(hits[0]["text"]) < 4001
