# eae-mcp

An MCP server for understanding **EcoStruxure Automation Expert (EAE) 26** solutions: Adapters, DataTypes,
Basic/Composite FBs, SubApps, Functions, CATs, the System (applications, devices, resources, mapping),
.NET HMI and eHMI.

Version 0.1 (milestone M1) is **read-only**. It indexes a solution's files directly (no EAE API is needed),
resolves EAE's ID-based references to names, and explains how the pieces fit together.

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

Resources: `eae://concepts/{overview, adapter, datatype, basic-fb, composite-fb, subapp, function, cat,
system, hmi-dotnet, ehmi, folders, library}`, `eae://solution/summary`, `eae://type/{name}`.
Prompts: `learn_component`, `review_application`, `design_basic_fb`, `design_cat`.

## Safety

- Read-only. Write tools arrive in M2 behind `allow_write`.
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

Docs: `docs/SPECS.md` (specification), `docs/EAE_FILE_FORMATS.md`, `docs/GOLDEN_FINDINGS.md`
(reverse-engineered formats), `docs/USER_GUIDE_M0.md` (how the golden files were captured).
