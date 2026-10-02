"""Regenerate every CAT's <Cat>.event.cs / .def.cs and compare with what EAE wrote."""

import os
import re
from pathlib import Path

import pytest

from eae_mcp.hmi import codegen as cg
from eae_mcp.project.solution import load_solution

HEADER = re.compile(r"/\*.*?\*/\r?\n", re.S)
LEFTOVER = re.compile(r"\r?\nnamespace [\w.]+\.(?:Faceplates|Symbols)\.\w+\r\n\{\}\r\n")  # stale blocks EAE never removes


def _norm(text: str) -> str:
    return LEFTOVER.sub("", HEADER.sub("", text, count=1)).rstrip()



def _compare(root: Path):
    sol = load_solution(root)
    same, stale, bad = 0, 0, []
    for qn, cfg in sol.cats.items():
        td = sol.types[qn]
        hmi = sol.find_type(td.name + "_HMI", td.namespace)
        event_file = next((g for g in cfg.generated_files if g.endswith(".event.cs")), None)
        if hmi is None or event_file is None:
            continue
        path = Path(os.path.normpath(sol.root / "/".join(cfg.cfg_file.split("/")[:-2]) / event_file))
        symbols = [cg.SymbolRef(s.name, s.is_faceplate) for s in cfg.symbols if s.technology == "hmi"]
        real = path.read_bytes().decode("utf-8-sig")
        events = {e.name for e in hmi.interface.event_inputs + hmi.interface.event_outputs}
        if set(re.findall(r"public class (\w+)EventArgs", real)) - events:
            stale += 1  # generated from an older HMI interface; EAE refreshes it on the next build
            continue
        gen = cg.event_cs(td.name, td.namespace, hmi.interface, symbols)
        if _norm(gen) == _norm(real):
            same += 1
        else:
            bad.append(qn)
    return same, stale, bad


def test_event_cs_matches_eae_golden(golden_dir):
    same, _, bad = _compare(golden_dir)
    assert not bad and same >= 1


def test_event_cs_matches_eae_solar(solar_dir):
    same, stale, bad = _compare(solar_dir)
    assert not bad, bad
    assert same >= 50


def test_header_format():
    import datetime as dt
    h = cg.header(dt.datetime(2024, 12, 9, 13, 10))
    assert " * Date: 12/9/2024\r\n * Time: 1:10 PM\r\n" in h


def test_unsupported_type():
    with pytest.raises(cg.UnsupportedHmiType):
        cg.net_type("TIME")


def _compare_def(root: Path):
    sol = load_solution(root)
    same, bad = 0, []
    for qn, cfg in sol.cats.items():
        td = sol.types[qn]
        def_file = next((g for g in cfg.generated_files if g.endswith(".def.cs")), None)
        if def_file is None:
            continue
        real = Path(os.path.normpath(sol.root / "/".join(cfg.cfg_file.split("/")[:-2]) / def_file)).read_bytes()
        real = real.decode("utf-8-sig")
        if not real.startswith("/*"):
            continue  # written by an older EAE generator (no header comment, different layout)
        if "_HMI;" in real and "partial class" not in real:
            continue  # stale region left behind after the CAT's faceplates were removed
        symbols = [cg.SymbolRef(s.name, s.is_faceplate) for s in cfg.symbols if s.technology == "hmi"]
        gen = cg.def_cs(td.name, td.namespace, symbols)
        if HEADER.sub("", gen, count=1) == HEADER.sub("", real, count=1):
            same += 1
        else:
            bad.append(qn)
    return same, bad


def test_def_cs_matches_eae_byte_for_byte(golden_dir, solar_dir):
    same, bad = _compare_def(golden_dir)
    assert not bad and same == 1
    same, bad = _compare_def(solar_dir)
    assert not bad, bad
    assert same >= 25  # includes CATs with several faceplates (acGrid, acInverter, ...)
