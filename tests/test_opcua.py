import shutil

import pytest

from eae_mcp.project import network_edit as ne
from eae_mcp.project import opcua_edit as oe
from eae_mcp.project.edit import EditError
from eae_mcp.project.solution import load_solution

SYS = "IEC61499/System/cc675751-63d4-4bbd-a7c3-0457798ec9ad"
LAYER = f"{SYS}/75c2c3a7-b9f4-4183-8924-f22398bdf243/9584feed-a7f9-4781-9ef4-f65cb648b9ab/opcua.xml"
RES = f"{SYS}/42ac64b9-b75e-4884-96b3-c103347b1d7f/B46693CF18BE45F0/opcua.xml"


@pytest.fixture()
def golden_copy(golden_dir, tmp_path):
    dest = tmp_path / "golden"
    shutil.copytree(golden_dir, dest)
    return dest


def test_unexpose_then_expose_restores_golden(golden_copy, golden_dir, library_store):
    oe.set_exposed(load_solution(golden_copy, library_store=library_store), "CAT1.IThis.OUT1", False).apply()
    sol = load_solution(golden_copy, library_store=library_store)
    assert not [o for s in sol.systems for o in s.opcua]
    oe.set_exposed(sol, "CAT1.IThis.OUT1", True).apply()
    for rel in (LAYER, RES):
        assert (golden_copy / rel).read_bytes() == (golden_dir / rel).read_bytes(), rel


def test_expose_is_idempotent_and_checks_path(golden_copy, library_store):
    sol = load_solution(golden_copy, library_store=library_store)
    cs = oe.set_exposed(sol, "CAT1.IThis.OUT1")
    assert not cs.changes and "already exposed" in cs.warnings[0]
    with pytest.raises(EditError, match="no variable 'NOPE'"):
        oe.set_exposed(sol, "CAT1.IThis.NOPE")
    with pytest.raises(EditError, match="no inner FB"):
        oe.set_exposed(sol, "CAT1.Nope.OUT1")


def test_expose_unmapped_instance_warns(golden_copy, library_store):
    ne.add_fb(load_solution(golden_copy, library_store=library_store), "APP1", "CAT2", "catTest").apply()
    cs = oe.set_exposed(load_solution(golden_copy, library_store=library_store), "CAT2.QI")
    assert list(cs.changes) == [LAYER]
    assert any("not mapped" in w for w in cs.warnings)
