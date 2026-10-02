import pytest

from eae_mcp import safety, services
from eae_mcp.config import Config


@pytest.fixture()
def ws_solar(solar_dir):
    ws = services.Workspace(Config(roots=[]))
    sol = ws.open(str(solar_dir))
    return ws, sol


@pytest.fixture()
def ws_golden(golden_dir, library_store):
    ws = services.Workspace(Config(roots=[], library_store=library_store))
    sol = ws.open(str(golden_dir))
    return ws, sol


def test_summary(ws_golden):
    _, sol = ws_golden
    s = services.solution_summary(sol)
    assert s["eae_version"] == "26.0.0.0"
    assert s["catalog"]["types"] >= 4
    assert s["systems"][0]["devices"] == ["EcoRT_0 (Soft_dPAC)"]


def test_explain_instance(ws_solar):
    ws, sol = ws_solar
    e = services.explain(sol, ws, "PPC001")
    assert e["what"] == "application instance"
    assert e["type"] == "acPPC_v1_0" and e["type_kind"] == "cat"
    assert e["runs_on"][0]["device"] == "EcoRT_0"
    assert "ehmi canvas ControlPage" in e["shown_on"]
    assert e["parameters"]["Grid_AssetName"] == "'GRID01'"  # stored as $<VarID>, resolved to the name


def test_explain_type_and_device(ws_golden):
    ws, sol = ws_golden
    e = services.explain(sol, ws, "fbTest")
    assert e["kind"] == "basic"
    assert "START → Init when INIT" in e["ecc"]["transitions"]
    assert services.explain(sol, ws, "EcoRT_0")["what"] == "device"


def test_explain_unknown_suggests(ws_golden):
    ws, sol = ws_golden
    with pytest.raises(services.NotFound, match="Did you mean"):
        services.explain(sol, ws, "fbTes")


def test_trace_from_canvas(ws_golden):
    ws, sol = ws_golden
    t = services.trace(sol, ws, "Canvas1")
    steps = [s["step"] for s in t["chain"]]
    assert "hmi canvas Canvas1" in steps and "ehmi canvas Canvas1" in steps
    inst = next(s for s in t["chain"] if s["step"].startswith("instance CAT1"))
    assert inst["runs_on"] == ["EcoRT_0/RES0"]
    contains = {c["instance"]: c for c in inst["type_tree"]["contains"]}
    assert contains["FB1"]["algorithms"] == ["Init", "Calc"]


def test_cat_describe_and_files(ws_golden):
    ws, sol = ws_golden
    c = services.cat_describe(sol, ws, "catTest")
    assert [v["name"] for v in c["hmi_interface"]["values_to_hmi"]] == ["QI", "OUT1"]
    assert {(s["technology"], s["name"]) for s in c["symbols"]} == {("hmi", "sDefault"), ("ehmi", "seDefault")}
    paths = {f["path"] for f in c["files"]}
    assert "IEC61499/catTest/catTest.cfg" in paths
    assert "HMI/catTest/catTest_sDefault.cnv.Designer.cs" in paths
    assert "WEB/catTest/catTest_seDefault.sym.json" in paths
    assert all(f["exists"] for f in c["files"])


def test_find_usages(ws_golden):
    ws, sol = ws_golden
    where = {u["where"] for u in services.find_usages(sol, ws, "catTest")}
    assert {"application", "resource", "hmi canvas", "ehmi canvas"} <= where
    assert any(u["in"] == "Main.catTest" for u in services.find_usages(sol, ws, "fbTest"))


def test_search_st(ws_golden):
    _, sol = ws_golden
    hits = services.search(sol, "IN1 + IN2")
    assert hits and hits[0]["algorithm"] == "Calc"


def test_hmi_describe_bindings(ws_golden):
    ws, sol = ws_golden
    d = services.hmi_describe(sol, ws, "Canvas1", "ehmi")
    assert d["bindings"][0]["instance"].startswith("APP1/CAT1")
    assert d["resolutions"][0]["name"] == "1024x768"


def test_folders_view_uses_device_names(ws_golden):
    _, sol = ws_golden
    assert services.folders_view(sol)["IEC61499"]["SystemDevice"][".Line1"] == ["EcoRT_0"]


def test_doc_scaffold(ws_golden):
    ws, sol = ws_golden
    md = services.doc_scaffold(sol, ws, "catTest")
    assert md.startswith("# catTest")
    assert "[SCREENSHOT: eHMI symbol]" in md


def test_concepts():
    names = services.concept_names()
    assert {"overview", "cat", "ehmi", "hmi-dotnet", "subapp"} <= set(names)
    assert "Composite Automation Type" in services.concept("cat")


def test_catalog_build(ws_golden, library_store, tmp_path):
    ws, sol = ws_golden
    r = services.catalog_build(ws, sol, str(library_store), str(tmp_path / "c.json"))
    assert r["types"] >= 4 and (tmp_path / "c.json").exists()


def test_roots_are_enforced(golden_dir, tmp_path):
    ws = services.Workspace(Config(roots=[tmp_path]))
    with pytest.raises(safety.AccessDenied):
        ws.open(str(golden_dir))


def test_sensitive_paths():
    assert safety.is_sensitive("General/Security/CAE_App.db")
    assert safety.is_sensitive("General/se-rbac-users.json")
    assert safety.is_sensitive("Topology/Content/89a8_DeviceCertificate")
    assert not safety.is_sensitive("IEC61499/fbTest.fbt")


def test_type_tools_accept_instance_names_and_explain_kind_words(ws_golden, tmp_path):
    ws, sol = ws_golden
    assert services.cat_describe(sol, ws, "CAT1")["name"] == "Main.catTest"
    with pytest.raises(services.NotFound, match="eae_list"):
        services.find_type(sol, "cat")


def test_doc_scaffold_is_saved_outside_the_project(golden_dir, tmp_path):
    import shutil
    dest = tmp_path / "g"
    shutil.copytree(golden_dir, dest)
    ws = services.Workspace(Config(roots=[]))
    sol = ws.open(str(dest))
    out = services.doc_scaffold_saved(sol, ws, "fbTest")
    assert out["saved_to"].endswith(".eae-mcp/docs/fbTest.md".replace("/", __import__("os").sep))
    assert out["markdown"].startswith("# fbTest")


def test_solution_by_name_and_clear_roots_error(golden_dir, tmp_path):
    import shutil
    root = tmp_path / "EAE"
    shutil.copytree(golden_dir, root / "EAE_MCP_Golden")
    ws = services.Workspace(Config(roots=[root]))
    assert ws.get("EAE_MCP_Golden").sln.stem == "EAE_MCP_Golden"
    with pytest.raises(services.NotFound, match="eae_list_solutions"):
        ws.get("Nope")
    with pytest.raises(safety.AccessDenied, match=str(root).replace("\\", "\\\\")):
        ws.get(str(golden_dir))
