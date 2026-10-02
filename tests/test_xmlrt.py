from pathlib import Path

import pytest

from eae_mcp.io import xmlrt

XML_SUFFIXES = {
    ".xml", ".fbt", ".adp", ".dt", ".app", ".fct", ".cfg", ".system", ".sysapp", ".syslay", ".sysdev",
    ".sysres", ".hcf", ".sys", ".dfbproj", ".csproj", ".htmlproj", ".resx", ".hwconfigproj",
    ".topologyproj", ".atvdisplayproj", ".assetLinkDataproj",
}


def xml_files(root: Path):
    return [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in XML_SUFFIXES]


def test_golden_roundtrip_is_byte_identical(golden_dir):
    files = xml_files(golden_dir)
    assert len(files) > 80
    failures = [str(p) for p in files if not xmlrt.roundtrips(p)]
    assert failures == []


def test_solar_roundtrip_is_byte_identical(solar_dir):
    files = xml_files(solar_dir)
    assert len(files) > 2000
    failures = [str(p) for p in files if not xmlrt.roundtrips(p)]
    assert failures == []


def test_modified_attribute_changes_only_that_line(golden_dir):
    xf = xmlrt.load(golden_dir / "IEC61499" / "fbTest.fbt")
    xf.root.set("Comment", "Changed comment")
    before = xf.original.split(b"\r\n")
    after = xmlrt.dumps(xf).split(b"\r\n")
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(before) == len(after)
    assert len(changed) == 1
    assert b'Comment="Changed comment"' in after[changed[0]]


def test_new_element_uses_eae_style(golden_dir):
    xf = xmlrt.load(golden_dir / "IEC61499" / "aTest.adp")
    itf = next(e for e in xf.root if e.tag == "InterfaceList")
    from lxml import etree
    el = etree.SubElement(itf, "Extra")
    el.set("Name", "x")
    out = xmlrt.dumps(xf)
    assert b'<Extra Name="x" />' in out
    assert b"\n" not in out.replace(b"\r\n", b"")  # still CRLF only


def test_bom_and_empty_meta(tmp_path):
    empty = tmp_path / "x.meta.xml"
    empty.write_bytes(xmlrt.BOM)
    assert xmlrt.roundtrips(empty)
    with pytest.raises(xmlrt.EmptyXmlError):
        xmlrt.load(empty)


def test_save_is_atomic(tmp_path, golden_dir):
    src = golden_dir / "IEC61499" / "aTest.adp"
    target = tmp_path / "aTest.adp"
    target.write_bytes(src.read_bytes())
    xmlrt.save(xmlrt.load(target))
    assert target.read_bytes() == src.read_bytes()
    assert not list(tmp_path.glob("*.tmp"))
