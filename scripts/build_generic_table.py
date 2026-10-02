"""Build src/eae_mcp/knowledge/generic_types.json from solutions that use generic FBs.

Concrete generic types (NETIO_16308C75BF8BAF741, …) have no definition file in a project: EAE generates them
at build time from the FB's `Configuration.GenericFBType.InterfaceParams`. The suffix depends only on that
parameter string, so a table learned from one solution lets the server add generic FBs to any solution.

    python scripts/build_generic_table.py <solution> [<solution> …]
"""

import json
import sys
from pathlib import Path

from eae_mcp.project import library_guide as lg
from eae_mcp.project.solution import load_solution

OUT = Path(__file__).resolve().parent.parent / "src" / "eae_mcp" / "knowledge" / "generic_types.json"


def main(paths: list[str]) -> None:
    table: dict[str, dict] = json.loads(OUT.read_text()) if OUT.exists() else {}
    for p in paths:
        sol = load_solution(Path(p))
        for g in lg.generic_registry(sol):
            entry = table.setdefault(g["type"], {"base": g["base"], "params": g["params"], "pins": {}})
            td = lg.generic_typedef(sol, g["type"], g["namespace"])
            itf = td.interface
            for kind, direction, items in (("event", "in", itf.event_inputs), ("event", "out", itf.event_outputs),
                                           ("data", "in", itf.input_vars), ("data", "out", itf.output_vars)):
                for it in items:
                    entry["pins"][it.name] = [kind, direction] + ([it.type] if getattr(it, "type", "") else [])
    OUT.write_text(json.dumps(dict(sorted(table.items())), indent=1) + "\n")
    print(f"{len(table)} generic types -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
