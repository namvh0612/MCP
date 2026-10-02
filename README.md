# eae-mcp

An MCP server for understanding **EcoStruxure Automation Expert (EAE) 26** solutions: Adapters, DataTypes,
Basic/Composite FBs, SubApps, Functions, CATs, the System (applications, devices, resources, mapping),
.NET HMI and eHMI.

It indexes a solution's files directly (no EAE API is needed), resolves EAE's ID-based references to names,
explains how the pieces fit together (M1), and creates/edits Adapters, DataTypes and Basic FBs exactly the way
EAE writes them (M2), and edits networks and resource mapping (M3).

## Install (Windows, next to EAE)

Requires Python 3.11+ ([python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`).

```powershell
git clone <this repo> C:\Tools\eae-mcp
cd C:\Tools\eae-mcp
py -m venv .venv
.venv\Scripts\pip install -e .
```

Create `eae-mcp.toml` (all keys optional):

```toml
[project]
roots = ["C:/EAE"]                      # solutions the server may open

[eae]
version = "26.0"
library_store = "C:/ProgramData/Schneider Electric/Libraries"   # default
# catalog_file = "C:/EAE/.eae-mcp/catalog.json"                 # for machines without EAE

[server]
transport = "stdio"                     # or "http"
http_bind = "127.0.0.1:8765"
```

### Claude Desktop / Claude Code (stdio)

```json
{
  "mcpServers": {
    "eae": {
      "command": "C:\\Tools\\eae-mcp\\.venv\\Scripts\\eae-mcp.exe",
      "args": ["--config", "C:\\Tools\\eae-mcp\\eae-mcp.toml"]
    }
  }
}
```

Claude Code: `claude mcp add eae -- C:\Tools\eae-mcp\.venv\Scripts\eae-mcp.exe --config C:\Tools\eae-mcp\eae-mcp.toml`

### Remote access (HTTP)

```powershell
$env:EAE_MCP_TOKEN = "<long random secret>"
.venv\Scripts\eae-mcp.exe --config eae-mcp.toml --transport http --host 0.0.0.0 --port 8765
```

Clients connect to `http://<windows-host>:8765/mcp` with `Authorization: Bearer <token>`.
The server refuses to listen on a non-loopback address without a token.

### Machines without EAE

Run `eae_catalog_build` once on the EAE machine. It writes `<solution>/.eae-mcp/catalog.json` with the
interfaces of the system-library types the solution uses. Copy the solution and the catalog, then set
`catalog_file`.

## Tools

| Tool | Purpose |
|---|---|
| `eae_list_solutions`, `eae_open_solution`, `eae_summary` | Find, index and summarize solutions |
| `eae_list`, `eae_get`, `eae_search`, `eae_find_usages`, `eae_folders` | Browse types, ST code, usages and logical folders |
| `eae_cat_describe` | A CAT's interface, network, HMI interface, sub-CATs, symbols and files |
| `eae_system_describe` | Applications, devices, resources, mapping, OPC UA exposure |
| `eae_hmi_list`, `eae_hmi_describe` | .NET HMI and eHMI canvases, symbols, faceplates and bindings |
| `eae_explain` | Explain any type, application instance, HMI document or device |
| `eae_trace` | HMI canvas → instance → CAT → sub-CATs/FBs → algorithms |
| `eae_show_component_files` | Every file of a component and its role |
| `eae_doc_scaffold` | Markdown doc skeleton with screenshot placeholders |
| `eae_catalog_build` | Index system-library types from the library store |
| `eae_validate` | Static checks: identifiers, reserved words, WITH, ECC, connections, registration |

### Write tools (M2–M4)

All write tools default to **`dry_run=true`** and return a unified diff. Pass `dry_run=false` to write;
this also requires `allow_write = true` under `[project]` (or `EAE_MCP_ALLOW_WRITE=1`).

| Tool | Purpose |
|---|---|
| `eae_adapter_create` | New Adapter (`.adp` + `.doc.xml`, registered in `.dfbproj`, optional folder) |
| `eae_datatype_create`, `eae_datatype_update` | New/changed DataType: struct, enum, array, subrange |
| `eae_basic_create` | New Basic FB: interface, internal vars, ECC, ST algorithms |
| `eae_fb_update_interface` | Add/remove events and variables, change WITH; existing IDs and wiring are kept |
| `eae_basic_upsert_algorithm` | Add or replace an ST algorithm |
| `eae_basic_update_ecc` | Add/remove states and transitions, replace a state's actions |
| `eae_composite_create` | New Composite FB (interface + boundary pins), filled with the `eae_net_*` tools |
| `eae_subapp_create` | New SubApp inside an application (event pins) |
| `eae_net_add_fb`, `eae_net_remove_fb` | Add/remove instances in a Composite, CAT, SubApp or application |
| `eae_net_connect`, `eae_net_disconnect` | Event/data/adapter connections, with direction and single-source checks |
| `eae_net_set_param` | Instance parameters (ST literals), synced to the mapped resource copy |
| `eae_map_to_resource`, `eae_unmap` | Map application instances to `Device/Resource`, copying shared connections |
| `eae_cat_create` | New CAT like EAE's "New CAT": `.fbt` with `IThis`, `_HMI.fbt`, `.cfg`, companions, a .NET HMI symbol (+ generated `.event.cs`/`.def.cs`) and an eHMI symbol |
| `eae_cat_add_symbol` | Add a .NET HMI symbol, a .NET faceplate or an eHMI symbol to a CAT |
| `eae_opcua_expose` | Expose/unexpose a variable on OPC UA (application layer and mapped resources) |
| `eae_ehmi_canvas_create` | New eHMI canvas on a device, added to its canvas resolution |
| `eae_ehmi_place_symbol`, `eae_ehmi_update_object`, `eae_ehmi_remove_object` | Put a CAT instance on an eHMI canvas, move/resize/edit it, remove it |

CAT bookkeeping is automatic: adding a CAT instance inside a CAT lists it as `<SubCAT>` in the `.cfg`,
and changing the IThis interface (`eae_fb_update_interface` on `<Cat>_HMI`) regenerates `.event.cs`,
the symbols' `.cnv.xml` mapping and `_HMI.opcua.xml`.

Every write:
- backs up modified files to `<solution>/.eae-mcp/backup/<timestamp>/`;
- appends to `<solution>/.eae-mcp/audit.jsonl`;
- writes atomically;
- refuses if a file changed on disk after it was read.

EAE reloads changed files automatically. Do not keep unsaved edits to the same type open in EAE.
After writing, run **Tools › Check Changes** in EAE.

Resources: `eae://concepts/{overview, adapter, datatype, basic-fb, composite-fb, subapp, function, cat,
system, hmi-dotnet, ehmi, folders, library}`, `eae://solution/summary`, `eae://type/{name}`.
Prompts: `learn_component`, `review_application`, `design_basic_fb`, `design_cat`.

## Safety

- Read-only unless `allow_write` is set. Write tools are dry-run by default.
- Only paths inside `roots` are opened.
- Security material is never read: `General/Security`, certificates, `se-rbac-*.json`, `*.db`.
- `bin/`, `obj/` and `SnapshotCompiles/` are ignored.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Every XML file in the fixtures (2,249 files) must round-trip byte for byte through `eae_mcp.io.xmlrt`.
That is the precondition for the M2 write tools.

VS Code setup: `docs/SETUP_VSCODE.md`. Docs: `docs/SPECS.md` (specification), `docs/EAE_FILE_FORMATS.md`, `docs/GOLDEN_FINDINGS.md`
(reverse-engineered formats), `docs/USER_GUIDE_M0.md` (how the golden files were captured).
