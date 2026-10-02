from eae_mcp.project.catalog import Catalog
from eae_mcp.project.solution import load_solution, resolve_reference


def test_select_exact_and_fallback_versions(library_store):
    pkgs = Catalog.select_packages(library_store, {"Runtime.Base": "26.0.0.7", "SE.DPAC": "26.0.0.99"})
    assert {(p.name, p.version) for p in pkgs} == {("Runtime.Base", "26.0.0.7"), ("SE.DPAC", "26.0.0.18")}
    pkgs = Catalog.select_packages(library_store, {"Runtime.Base": None})
    assert pkgs[0].version == "26.0.0.7"


def test_catalog_types_and_json_roundtrip(library_store, tmp_path):
    cat = Catalog.from_store(library_store, {"Runtime.Base": "26.0.0.7", "SE.DPAC": "26.0.0.18"})
    assert {"IEC61499.Standard.E_CYCLE", "IEC61499.Standard.E_DELAY", "SE.DPAC.Soft_dPAC"} <= set(cat.types)
    assert cat.find("E_DELAY").interface.pin_name("START") == "START"
    path = tmp_path / "catalog.json"
    cat.save(path)
    again = Catalog.load(path)
    assert again.find("E_PERMIT").interface.input_vars[0].name == "PERMIT"
    assert again.find("E_CYCLE").library_version == "26.0.0.7"


def test_library_pins_resolve_with_catalog(golden_dir, library_store):
    sol = load_solution(golden_dir, library_store=library_store)
    cfb = sol.find_type("cfbTest")
    delay = next(i for i in cfb.network.instances if i.type == "E_DELAY")
    end = resolve_reference(f"${delay.id}.EO", cfb.network, sol)
    assert end.resolved and str(end) == "FB2.EO"
    assert sol.find_type("E_DELAY").source == "library"
