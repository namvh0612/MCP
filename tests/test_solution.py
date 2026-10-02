from collections import Counter

from eae_mcp.project.solution import load_solution, resolve_reference


def test_golden_types_and_kinds(golden_dir):
    sol = load_solution(golden_dir)
    kinds = Counter(t.kind for t in sol.types.values())
    assert kinds == {"datatype": 4, "subapp": 2, "adapter": 1, "cat": 1, "cat_hmi": 1, "composite": 1, "basic": 1}
    assert sol.references == {"Runtime.Base": "26.0.0.7", "SE.DPAC": "26.0.0.18", "SE.Standard": "26.0.0.6"}
    assert sol.warnings == []


def test_golden_basic_fb(golden_dir):
    sol = load_solution(golden_dir)
    fb = sol.find_type("fbTest")
    assert fb.kind == "basic"
    assert [s.name for s in fb.states] == ["START", "Init", "Run"]
    assert [a.name for a in fb.algorithms] == ["Init", "Calc"]
    assert "OUT1 := IN1 + IN2;" in fb.algorithms[1].text
    assert fb.interface.event_inputs[1].with_vars == ["QI", "IN1", "IN2"]


def test_golden_datatypes(golden_dir):
    sol = load_solution(golden_dir)
    assert sol.find_type("dtEnum").datatype.kind == "enum"
    assert [v.name for v in sol.find_type("dtEnum").datatype.values] == ["Stop", "Run", "Fault"]
    assert sol.find_type("dtArray").datatype.ranges == [("0", "9")]
    assert sol.find_type("dtRange").datatype.kind == "subrange"
    assert [m.name for m in sol.find_type("dtStruct").datatype.members] == ["A", "B", "C", "D"]


def test_composite_connections_resolve_to_names(golden_dir):
    sol = load_solution(golden_dir)
    cfb = sol.find_type("cfbTest")
    pairs = [(str(resolve_reference(c.source, cfb.network, sol)), str(resolve_reference(c.destination, cfb.network, sol)))
             for c in cfb.network.connections]
    assert ("REQ", "FB1.REQ") in pairs
    assert ("FB1.CNF", "FB2.START") in pairs
    assert ("FB1.OUT1", "Y") in pairs


def test_cat_manifest(golden_dir):
    sol = load_solution(golden_dir)
    cfg = sol.cats["Main.catTest"]
    assert cfg.hmi_interface == "IThis"
    assert {(s.name, s.technology) for s in cfg.symbols} == {("sDefault", "hmi"), ("seDefault", "ehmi")}
    assert cfg.folder == ".Logic"


def test_system_and_mapping(golden_dir):
    sol = load_solution(golden_dir)
    system = sol.systems[0]
    layer = system.applications[0].layers[0]
    assert [i.name for i in layer.network.instances] == ["CAT1"]
    dev = system.devices[0]
    assert (dev.name, dev.type, dev.folder) == ("EcoRT_0", "Soft_dPAC", ".Line1")
    res_fb = dev.resources[0].network.instances[0]
    assert res_fb.mapping == layer.network.instances[0].id
    assert {o.context.split(".")[0] for o in system.opcua} == {"3811CA558F6E3EFC", "AD6F4C542847B13B"}


def test_folders_union_of_xml_and_parent(golden_dir):
    tree = load_solution(golden_dir).folders["IEC61499"].as_tree()
    assert tree["Adapter"][".Core"] == ["aTest"]
    assert ".Logic" in tree["Adapter"]  # stale Folders.xml entry left by EAE's rename
    assert tree["SystemDevice"][".Line1"] == ["42ac64b9-b75e-4884-96b3-c103347b1d7f"]


def test_solar_demo_index(solar_dir):
    sol = load_solution(solar_dir)
    kinds = Counter(t.kind for t in sol.types.values())
    assert kinds["cat"] == 122 and kinds["basic"] == 111 and kinds["adapter"] == 55
    assert len(sol.cats) == 122
    assert sol.find_type("acPPC_v1_0").folder == ".ControlModule"
    assert sol.find_type("HMI_Indication_Real_v1_0").project == "SE.Agile"
    assert sol.warnings == []


def test_solar_ids_that_are_names_or_small_ints(solar_dir):
    """acPPC_v1_0 uses FB IDs like '35' and 'ALMW' (the instance name)."""
    sol = load_solution(solar_dir)
    cat = sol.find_type("acPPC_v1_0")
    ends = {str(resolve_reference(c.destination, cat.network, sol)) for c in cat.network.connections}
    assert "Grid.IPlug" in ends
    assert "ALMW.PLOAD" in ends
