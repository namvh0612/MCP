"""MCP server exposing read-only understanding of EcoStruxure Automation Expert 26 solutions."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import safety, services
from .config import Config

INSTRUCTIONS = """\
Tools for understanding EcoStruxure Automation Expert (EAE) 26 solutions (IEC 61499).
Start with eae_list_solutions / eae_open_solution, then eae_summary.
- To learn a concept, read the resource eae://concepts/<name> (overview, adapter, datatype, basic-fb,
  composite-fb, subapp, function, cat, system, hmi-dotnet, ehmi, folders, library).
- eae_explain explains any type, application instance, HMI canvas/symbol or device.
- eae_trace follows HMI canvas → instance → CAT → sub-CATs → algorithms.
- eae_show_component_files lists every file a component consists of (a CAT spans ~20 files).
All tools are read-only in this version. Names are accepted everywhere; IDs are resolved internally.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _json(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, default=str)


def create_server(config: Config | None = None) -> MCPServer:
    ws = services.Workspace(config or Config.load())
    mcp = MCPServer(name="eae-mcp", instructions=INSTRUCTIONS, version="0.1.0")

    def run(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (services.NotFound, safety.AccessDenied, FileNotFoundError) as e:
            raise ToolError(str(e)) from e

    def sol(solution: str | None):
        return run(ws.get, solution)

    # -- solutions --------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    def eae_list_solutions() -> list[dict]:
        """List EAE solutions (.sln) found under the configured project roots."""
        return services.list_solutions(ws)

    @mcp.tool(annotations=READ_ONLY)
    def eae_open_solution(path: str) -> dict:
        """Open (index) an EAE solution folder or .sln file and make it the current solution.

        Returns a summary: projects, libraries, type counts, systems, library references.
        """
        return services.solution_summary(run(ws.open, path))

    @mcp.tool(annotations=READ_ONLY)
    def eae_summary(solution: str | None = None) -> dict:
        """Summary of the current (or named) solution."""
        return services.solution_summary(sol(solution))

    # -- types --------------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    def eae_list(kind: str | None = None, query: str = "", library: str | None = None,
                 folder: str | None = None, solution: str | None = None) -> list[dict] | dict:
        """List components.

        kind: adapter | datatype | basic | composite | subapp | function | cat | cat_hmi | sifb |
              system | hmi | hmi_canvas | hmi_symbol | hmi_faceplate | ehmi | ehmi_canvas | ehmi_symbol.
        Omit kind to list all types. library: '' for the main project, or e.g. 'SE.Agile'.
        folder: logical folder prefix such as '.Standard'.
        """
        s = sol(solution)
        return run(services.list_items, s, ws, kind, library, folder, query)

    @mcp.tool(annotations=READ_ONLY)
    def eae_get(name: str, include_xml: bool = False, solution: str | None = None) -> dict:
        """Full definition of a type (FB, CAT, adapter, datatype, function, subapp, library type).

        Networks are returned with connections resolved to names (`FB1.CNF -> FB2.START`).
        """
        s = sol(solution)
        td = run(services.find_type, s, name)
        return run(services.type_view, s, td, include_xml)

    @mcp.tool(annotations=READ_ONLY)
    def eae_find_usages(name: str, solution: str | None = None) -> list[dict]:
        """Where a type is used: type networks, adapter pins, variable types, CAT sub-CATs,
        application layers, resources and HMI documents."""
        s = sol(solution)
        return run(services.find_usages, s, ws, name)

    @mcp.tool(annotations=READ_ONLY)
    def eae_search(text: str, limit: int = 50, solution: str | None = None) -> list[dict]:
        """Full-text search over type names, comments, variables and ST algorithm code."""
        return services.search(sol(solution), text, limit)

    @mcp.tool(annotations=READ_ONLY)
    def eae_folders(solution: str | None = None) -> dict:
        """Logical Solution Explorer folder tree per project and category, with members."""
        return services.folders_view(sol(solution))

    # -- CAT / system -----------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    def eae_cat_describe(name: str, solution: str | None = None) -> dict:
        """Everything about a CAT: interface, network, HMI interface (values to/from HMI),
        sub-CATs, .NET HMI and eHMI symbols with their bindings, and all files."""
        s = sol(solution)
        return run(services.cat_describe, s, ws, name)

    @mcp.tool(annotations=READ_ONLY)
    def eae_system_describe(solution: str | None = None) -> list[dict]:
        """Systems: applications (layers and FB networks), devices, resources, mapping, OPC UA exposure."""
        return services.system_view(sol(solution))

    # -- HMI ------------------------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    def eae_hmi_list(technology: str | None = None, kind: str | None = None, query: str = "",
                     solution: str | None = None) -> list[dict]:
        """List .NET HMI ('hmi') and eHMI ('ehmi') documents.

        kind: canvas | resolution | symbol | faceplate | graphic.
        """
        s = sol(solution)
        return services.hmi_list(s, ws, technology, kind, query)

    @mcp.tool(annotations=READ_ONLY)
    def eae_hmi_describe(name: str, technology: str | None = None, solution: str | None = None) -> dict:
        """Describe a canvas, symbol or faceplate: objects, bindings (resolved to application
        instances for canvases), size, resolution and symbol mapping."""
        s = sol(solution)
        return run(services.hmi_describe, s, ws, name, technology)

    # -- understanding -------------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    def eae_explain(target: str, solution: str | None = None) -> dict:
        """Explain anything by name: a type, an application instance (e.g. 'PPC001'),
        an HMI/eHMI document or a device. Includes links to concept resources."""
        s = sol(solution)
        return run(services.explain, s, ws, target)

    @mcp.tool(annotations=READ_ONLY)
    def eae_trace(target: str, solution: str | None = None) -> dict:
        """Follow the chain HMI canvas → application instance → CAT → sub-CATs / inner FBs →
        algorithms. target: canvas name, instance name or type name."""
        s = sol(solution)
        return run(services.trace, s, ws, target)

    @mcp.tool(annotations=READ_ONLY)
    def eae_show_component_files(name: str, solution: str | None = None) -> dict:
        """Every file that makes up a component and its role (CATs span IEC61499, HMI and WEB)."""
        s = sol(solution)
        return run(services.component_files, s, name)

    @mcp.tool(annotations=READ_ONLY)
    def eae_doc_scaffold(name: str, solution: str | None = None) -> str:
        """Markdown documentation skeleton for a component, with [SCREENSHOT: …] placeholders
        for captures taken in EAE."""
        s = sol(solution)
        return run(services.doc_scaffold, s, ws, name)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                          openWorldHint=False))
    def eae_catalog_build(store: str | None = None, output: str | None = None,
                          solution: str | None = None) -> dict:
        """Index system-library types (E_CYCLE, E_DELAY, Soft_dPAC, …) from the EAE library store
        (default C:/ProgramData/Schneider Electric/Libraries) for the versions the solution references,
        and save the catalog as JSON (default <solution>/.eae-mcp/catalog.json) for use on machines
        without EAE. Does not modify the solution."""
        s = sol(solution)
        return run(services.catalog_build, ws, s, store, output)

    # -- resources --------------------------------------------------------------------------

    @mcp.resource("eae://concepts", mime_type="text/markdown")
    def concepts_index() -> str:
        """Index of EAE concept documents."""
        return "# EAE concepts\n\n" + "\n".join(f"- eae://concepts/{n}" for n in services.concept_names())

    @mcp.resource("eae://concepts/{name}", mime_type="text/markdown")
    def concept(name: str) -> str:
        """An EAE concept document (overview, adapter, datatype, basic-fb, composite-fb, subapp,
        function, cat, system, hmi-dotnet, ehmi, folders, library)."""
        return run(services.concept, name)

    @mcp.resource("eae://solution/summary", mime_type="application/json")
    def solution_summary() -> str:
        """Summary of the current solution."""
        return _json(services.solution_summary(sol(None)))

    @mcp.resource("eae://type/{name}", mime_type="application/json")
    def type_resource(name: str) -> str:
        """Normalized JSON definition of a type in the current solution."""
        s = sol(None)
        return _json(services.type_view(s, run(services.find_type, s, name)))

    # -- prompts -----------------------------------------------------------------------------

    @mcp.prompt()
    def learn_component(name: str) -> str:
        """Teach the concept behind a component using the open solution as the example."""
        return (
            f"Explain the EAE component '{name}' to an automation engineer.\n"
            "1. Call eae_explain and read the concept resource it links to.\n"
            "2. If it is a CAT, also call eae_cat_describe and eae_show_component_files.\n"
            "3. Explain: purpose, interface (events and the data they carry), internal behaviour "
            "(ECC/algorithms or network), how it is used in the application and shown on HMI/eHMI.\n"
            "4. Finish with the IEC 61499 concept it illustrates and one practical tip."
        )

    @mcp.prompt()
    def review_application(application: str = "APP1") -> str:
        """Review an application network for problems."""
        return (
            f"Review the EAE application '{application}'. Use eae_system_describe and eae_get on the "
            "types involved. Look for unconnected event inputs, data inputs without a source or "
            "parameter, unmapped instances, instances not shown on any HMI, and unresolved connections. "
            "Report findings as a prioritized list with the instance names."
        )

    @mcp.prompt()
    def design_basic_fb(description: str) -> str:
        """Design a Basic FB (interface + ECC + ST) from a functional description."""
        return (
            "Design an EAE 26 Basic FB for this requirement:\n"
            f"{description}\n\n"
            "Read eae://concepts/basic-fb first. Produce: interface (events with WITH, typed vars), "
            "internal vars, ECC (states, transitions with conditions, actions), and ST algorithms. "
            "Follow the template convention INIT/INITO + REQ/CNF with QI/QO. Avoid reserved words as "
            "identifiers (e.g. ON)."
        )

    @mcp.prompt()
    def design_cat(description: str) -> str:
        """Design a CAT (logic + HMI interface + symbols) from a description."""
        return (
            "Design an EAE 26 CAT for this equipment:\n"
            f"{description}\n\n"
            "Read eae://concepts/cat. Use an existing CAT as reference (eae_list kind=cat, then "
            "eae_cat_describe). Produce: CAT interface, inner network (Basic FB for logic + IThis HMI "
            "interface), the HMI interface variables and events, and the content of a default .NET "
            "symbol and an eHMI symbol (widgets and their tag bindings)."
        )

    return mcp
