# EAE-MCP — MCP Server Specification for EcoStruxure Automation Expert 26

> Status: **v0.4** — M0 done (golden files C0–C11); M1 and M2 implemented (read + write for Adapter, DataType, Basic FB; see README). M2 awaits acceptance in EAE (`docs/ACCEPTANCE_M2.md`); M3 (networks) is next. Based on `SolarPlantDemo_v7` and the `EAE_MCP_Golden` captures (EAE 26.0).
> Companion documents:
> - [`EAE_FILE_FORMATS.md`](EAE_FILE_FORMATS.md): EAE 26 file formats, reverse-engineered from the sample.
> - [`VERIFICATION_CHECKLIST.md`](VERIFICATION_CHECKLIST.md): steps to perform in a real EAE installation.

---

## 1. Decisions

| # | Topic | Decision |
|---|---|---|
| D1 | Version | **EAE 26.0** (`NxtVersion=26.0.0.0`). A version layer is designed in so 26.1 can be added later |
| D2 | Primary goal | **Understand and manipulate every component**: Adapter → DataType → Basic FB → Composite FB → SubApp → CAT → .NET HMI (canvas/symbol/faceplate) → eHMI (web). Runtime operation and deployment come later |
| D3 | Host | Runs **on the Windows machine with EAE**. Projects can also be read **from another machine** over HTTP, or from a copy of a solution on a machine without EAE |
| D4 | EAE SDK/API | **None available.** Everything is based on project files. Build/deploy is manual, or via UI automation in a later phase |
| D5 | Concept documentation | The user operates EAE and captures screenshots. The MCP server provides doc scaffolds and a capture checklist |
| D6 | Technology | **Python 3.12 + MCP Python SDK (FastMCP) + lxml** (see §3) |
| D7 | Paths | Projects root: `C:\EAE` (all projects there may be used as references and test fixtures). EAE install: `C:\Program Files\Schneider Electric\EcoStruxure Automation Expert - Buildtime 26.0` |
| D8 | Language | **English** for everything: code, tool descriptions, concept docs, specs |
| D9 | HMI scope | **Both** .NET HMI and eHMI, read **and** write |
| D10 | Fixtures | Trimmed copies of the sample and of projects in `C:\EAE` may be used as fixtures, with security material stripped (§9) |

---

## 2. Findings from the sample that shape the design

1. **`.dfbproj` is the registry.** Every type must be declared as `<Compile>` with `<IEC61499Type>`, `<Parent>` (folder) and `<DependentUpon>`. A file that is not registered is invisible to EAE.
2. **References use IDs (Format 2.0).** Connections are `$<FBID>.<PinID>` and parameters are `$<VarID>`. Every tool therefore accepts **names** from the LLM and translates them to IDs internally. The LLM never handles IDs.
3. **System library types are not in the solution.** Examples: `E_PERMIT`, `E_DELAY`, `NETIO`, `INIT`, `Soft_dPAC`. The server must **build a catalog from the EAE library store** (`C:\ProgramData\Schneider Electric\Libraries\<Lib>-<Ver>\Files\<Namespace>\`). On a machine without EAE it uses an exported catalog.
4. **A CAT spans about 20 files in 3 projects:**
   - IEC61499: `.fbt`, `.cfg` (manifest), `_HMI.fbt`, OPC UA and offline-parametrization XML.
   - HMI: .NET symbols and faceplates.
   - WEB: eHMI symbols.
5. **Mapping from application to resource duplicates parameters.** A resource FB has a `Mapping` attribute pointing at the ID of the corresponding layer FB.
6. **The .NET HMI is designer-generated C#** (`*.cnv.Designer.cs`), so editing it needs a constrained code model and golden tests. **The eHMI is JSON + TypeScript**, which is straightforward to edit.
7. **Some files must never be touched:** `SnapshotCompiles/`, `General/Security/`, certificates, and the `nxtDataType` attribute.
8. **The sample has no SubApp.** One must be created in EAE (checklist C4).

---

## 3. Architecture

### 3.1. Technology choice

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Python + FastMCP + lxml** | lxml preserves XML on round-trip (comments, CDATA, attribute order, DOCTYPE). Fast iteration. `asyncua` for OPC UA, `pywinauto` for UI automation, `pythonnet` to load EAE .NET DLLs if needed | Needs Windows packaging (`uv` / PyInstaller) | ✅ **Chosen** |
| C# (.NET 8) + MCP C# SDK | Same ecosystem as EAE. Native Roslyn parsing of HMI C# | Slower to iterate on parsers | Reserved as an optional **sidecar** (Roslyn-based HMI C# rewriter, loading `NxtControl.*` assemblies) if the Python HMI code model proves insufficient |
| TypeScript | Natural for eHMI TS | Weaker XML round-trip and OPC UA support | ✗ |

### 3.2. Deployment

```
 Windows machine (EAE 26)                                    Other machine
┌──────────────────────────────────────────────────────┐   ┌──────────────────┐
│ EAE Buildtime ←(file system)→ eae-mcp server           │◄──│ Claude / MCP      │
│                                ├ stdio                 │HTTP│ client           │
│ C:\Program Files\…\Buildtime 26.0 → system catalog     │   └──────────────────┘
│ C:\EAE\* → solutions                                   │
└──────────────────────────────────────────────────────┘
```

- **Transports:** `stdio` (Claude Desktop/Code on the same machine) and `streamable-http` (remote clients). HTTP requires a bearer token and binds only to allowlisted addresses. HTTP is read-only by default.
- **"Read projects from another machine"** is supported in two ways:
  1. A remote client connects to the server on the Windows machine over HTTP.
  2. The server runs on a machine without EAE (Linux/macOS) and reads a copy of a solution. System types come from an exported `catalog.json`.

### 3.3. Source layout

```
src/eae_mcp/
  server.py                 # FastMCP: registers tools/resources/prompts
  config.py                 # eae-mcp.toml + env vars
  safety.py                 # read-only mode, allowlists, dry-run/diff, backups, audit log, open-in-EAE detection
  model/                    # plain dataclasses: TypeRef, Interface, Event, Var, ECC, Algorithm, Network, FBInstance,
                            #   Connection, Cat, HmiCanvas, HmiObject, EhmiCanvas, EhmiObject
  io/
    xmlrt.py                # lossless XML round-trip (lxml): BOM, DOCTYPE, CDATA, attribute order, 2-space indent, CRLF
    jsonrt.py               # lossless JSON round-trip for eHMI (tabs, BOM, key order, number formatting)
    ids.py                  # unique 16-hex IDs / GUIDs; CAT IDCounter
  project/
    solution.py             # parse .sln + projects; whole-solution index
    dfbproj.py              # read/write item registration; Folders.xml
    catalog.py              # type index: solution + referenced libraries + system libraries
    resolver.py             # name ↔ ID for pins/vars/FBs (Format 2.0 and legacy)
    types/                  # adapter.py, datatype.py, basic.py, composite.py, subapp.py, function.py, cat.py
    system.py               # system/app/layer/device/resource/mapping
    validate.py             # static checks
  hmi/
    dotnet/
      csproj.py             # HMI.csproj item registration
      designer.py           # constrained parser/writer for *.cnv.Designer.cs (InitializeComponent blocks)
      canvas.py, symbol.py  # canvases, CAT symbols, faceplates, .cnv.xml mapping
      templates/            # templates captured from EAE-generated files (golden)
    ehmi/
      htmlproj.py           # WEB.htmlproj item registration
      canvas.py, symbol.py  # .cnv.json/.sym.json + .ts/.user.cs/.sym.xml generation
      navigation.py         # WebCanvasesResolutionList.xml
      templates/
  knowledge/                # concept docs (Markdown, English) served as MCP resources; screenshots
  runtime/opcua.py          # (phase P2)
  buildtime/                # (phase P3) CLI or UI automation, if feasible
tests/
  fixtures/solar_min/       # trimmed SolarPlantDemo
  fixtures/eae_created/     # golden files produced in EAE by the checklist
  fixtures/c_eae/           # trimmed selections from C:\EAE
```

### 3.4. Write principles

1. **Lossless round-trip.** Parsing and re-serializing an unmodified file must produce byte-identical output. This gates every write tool.
2. **Minimal edits.** Touch only the targeted elements. Preserve unknown attributes and layout data (x/y, BezierPoints, Points).
3. **Atomic writes** (temp file + rename) and backups under `.eae-mcp/backup/<timestamp>/`.
4. **Writes are allowed while EAE has the solution open.** Golden C11 showed that EAE does not lock files and auto-reloads external changes. The server warns that unsaved edits in EAE for the same file will overwrite the server's change when the user saves in EAE.
5. **Complete operations.** Creating a type always does all of the following together:
   - creates the file;
   - registers it in `.dfbproj`, `HMI.csproj` or `WEB.htmlproj`;
   - updates `Folders.xml` if a new folder is needed;
   - creates `.doc.xml`/`.meta.xml` from templates.

---

## 4. Knowledge layer — understanding concepts (P0, serves D2 and D5)

**MCP resources** are English Markdown files in `knowledge/`. They are grounded in IEC 61499 and in observations from real projects, and include the user's screenshots.

| URI | Content |
|---|---|
| `eae://concepts/overview` | The big picture: Solution, Library, System, App, Device, Resource, HMI, eHMI |
| `eae://concepts/adapter` | Plugs/sockets, `AdapterInputs/Outputs`, example `aGrid_v1_0` |
| `eae://concepts/datatype` | Struct/Enum (Array/Alias ❓), `.dt`, `nxtDataType` |
| `eae://concepts/basic-fb` | Interface, `With`, ECC, ST algorithms, algorithm order |
| `eae://concepts/composite-fb` | FB networks, boundary pins, generic FBs |
| `eae://concepts/subapp` | SubApp vs Composite (pending sample) |
| `eae://concepts/function` | POU functions (`.fct`) |
| `eae://concepts/cat` | CAT = FB + HMI + OPC UA + offline params; `.cfg`; sub-CATs; the Agile pattern (acX = fbX + HMI_* + Broadcaster/Listener) |
| `eae://concepts/system` | App/Layer/Device/Resource, mapping, device properties |
| `eae://concepts/hmi-dotnet` | Canvases, symbols, faceplates, `TagName` binding, generated `.def.cs`/`.event.cs` |
| `eae://concepts/ehmi` | Per-device canvases, `.sym.json`/`.sym.ts`, `tagName`, graphics, support classes |
| `eae://formats/{kind}` | Format specs (excerpts of `EAE_FILE_FORMATS.md`) |

**Tools:**

| Tool | Description |
|---|---|
| `eae_explain` | Takes a `target` (type, instance or canvas name). Returns a structured explanation: kind, role, interface, relationships, related files, and links to concept resources |
| `eae_show_component_files` | Lists **every file** that makes up a component (e.g. a CAT's 20+ files across 3 projects) and the role of each |
| `eae_trace` | Follows the chain: eHMI/HMI canvas symbol → layer FB → CAT → sub-CAT → Basic FB → algorithm |
| `eae_doc_scaffold` | Generates an English doc skeleton for a component, with `[SCREENSHOT: …]` placeholders for EAE captures |

**Prompts:** `learn_component`, `design_cat`, `design_basic_fb`, `review_application`, `design_hmi_symbol`, `design_ehmi_symbol`.

---

## 5. Project layer — read and write per component

Conventions:
- Inputs use **names**, never IDs.
- Every write tool supports `dry_run` (default `true` in v1) and returns a unified diff.
- Every write result includes a `validation` report.

### 5.1. Solution & catalog (P0, read-only)

| Tool | Description |
|---|---|
| `eae_list_solutions` | Lists solutions under the configured roots (e.g. `C:\EAE`) |
| `eae_open_solution` | Takes a `path`. Returns a summary: version, projects, libraries, type counts by kind, systems |
| `eae_list` | `kind` ∈ {adapter, datatype, basic, composite, subapp, function, cat, system, device, hmi_canvas, hmi_symbol, ehmi_canvas, ehmi_symbol}. Filters: `library`, `folder`, `query` |
| `eae_get` | Normalized JSON definition of a type. `include_xml` is optional |
| `eae_folders` | List the logical folder tree per category; create/rename/delete folders and move types between folders (P1 read, P2 write; waits on checklist C7b) |
| `eae_find_usages` | Where a type/adapter/datatype is used (FB networks, CAT `.cfg`, canvases) |
| `eae_search` | Full-text search over names, comments, ST and TS/C# code |
| `eae_catalog_build` | (Windows) Scans the library store `C:\ProgramData\Schneider Electric\Libraries` for system types and exports `catalog.json` |

### 5.2. Adapter (P1)
`eae_adapter_create`, `eae_adapter_update_interface` (events, vars, `With`).

### 5.3. DataType (P1)
`eae_datatype_create` (struct/enum), `eae_datatype_update`. ⚠️ Enabled only after the `nxtDataType` handling is verified (checklist C3).

### 5.4. Basic FB (P1)

| Tool | Description |
|---|---|
| `eae_basic_create` | Interface + internal vars + ECC + algorithms in one call |
| `eae_fb_update_interface` | Add/change/remove events, vars and `With`. Updates every connection/parameter that references the IDs |
| `eae_basic_upsert_algorithm` | Add or update ST code (with local vars) |
| `eae_basic_update_ecc` | Add/remove states, transitions and actions. Keeps `FBType.Basic.Algorithm.Order` in sync |

### 5.5. Composite FB / SubApp / networks (P1)

| Tool | Description |
|---|---|
| `eae_composite_create` | Create a Composite FB type |
| `eae_subapp_create` | Group content inside an **application** into a SubApp (packaging only, not a reusable type; EAE stores it as `<Name>/<Name>.app`, see GOLDEN_FINDINGS C4b) |
| `eae_net_add_fb` | Add an instance to a network (composite, subapp or layer), with automatic x/y placement |
| `eae_net_connect` / `eae_net_disconnect` | Event/data/adapter connections. Checks type, direction and single-source rules |
| `eae_net_set_param` | Set a parameter (written as `$<VarID>` in Format 2.0) |
| `eae_net_remove_fb` | Remove an instance and its connections |

### 5.6. Function (P2)
`eae_function_create`, `eae_function_update`.

### 5.7. CAT (P1 read, P2 write)

| Tool | Description |
|---|---|
| `eae_cat_describe` | The `.cfg` manifest: sub-CATs, HMI interface, symbols/faceplates, OPC UA/offline config, eHMI files |
| `eae_cat_create` | Minimal CAT: `.fbt` + `.cfg` + `_HMI.fbt` + offline/OPC UA XML + project registration. Optionally creates a default .NET HMI symbol and eHMI symbol. ⚠️ Golden-tested against a CAT created by EAE (checklist C7) |
| `eae_cat_add_symbol` | Add a .NET symbol, .NET faceplate or eHMI symbol (files, `.cfg`, registration, regenerated `.event.cs`/`.def.cs`) |
| sub-CATs | No separate tool: `eae_net_add_fb` / `eae_net_remove_fb` inside a CAT keep `<SubCAT>` in `.cfg` in step |
| `eae_opcua_expose` | Expose/unexpose a variable (`Exposed` attribute in the layer and resource `opcua.xml`, golden C8) |
| IThis changes | `eae_fb_update_interface` on `<Cat>_HMI` regenerates `.event.cs`, `.cnv.xml` and `_HMI.opcua.xml` |

### 5.8. System (P1 read, P2 write)

- `eae_system_describe`: app → layer → FBs; device → resource → mappings; device properties.
- `eae_app_add_instance`: uses `eae_net_*` on the layer.
- `eae_map_to_resource`: creates the resource FB with `Mapping` and syncs parameters.
- `eae_device_properties`: device properties.

### 5.9. .NET HMI (P1 read, P2 write)

The writer uses a **constrained code model**. It parses `InitializeComponent()` into a list of `(field, type, property assignments)` and regenerates only that region, exactly in EAE's style (taken from golden templates). Code-behind (`*.cnv.cs`) is only edited in marked regions or by appending a method. Generated files (`*.def.cs`, `*.event.cs`) are never written.

| Tool | Description |
|---|---|
| `eae_hmi_list` | Canvases, CAT symbols, faceplates, graphics, resolutions |
| `eae_hmi_describe` | Objects, properties, `TagName` bindings, `.cnv.xml` mapping, code-behind summary |
| `eae_hmi_canvas_create` | New canvas (`.cnv.cs` + `.Designer.cs` + `.resx`), registered in `HMI.csproj` and `CanvasesResolutionList.xml` |
| `eae_hmi_canvas_add_symbol` | Place a CAT symbol on a canvas, binding `TagName` to the instance ID |
| `eae_hmi_symbol_create` | New symbol/faceplate for a CAT (files + `.cfg` `<Symbol>` entry + `.cnv.xml` mapping) |
| `eae_hmi_update_object` | Change object properties (bounds, brush, text, font, binding) |

⚠️ This requires golden files from EAE (checklist C7/C8) and acceptance testing in Buildtime. If the Python code model fails acceptance, switch to the Roslyn sidecar (§3.1).

### 5.10. eHMI (P1 read, P2 write)

| Tool | Description |
|---|---|
| `eae_ehmi_list` | Per-device canvases, CAT symbols, graphics, support classes |
| `eae_ehmi_describe` | Objects, `tagName` bindings, properties, related TS code |
| `eae_ehmi_canvas_create` | New canvas for a device (`.cnv.json` + `.cnv.ts` + `.user.cs`), registered in `.htmlproj` and the device's `WebCanvasesResolutionList.xml` |
| `eae_ehmi_place_symbol` | Place a CAT symbol on a canvas, with `tagName` = instance ID |
| `eae_cat_add_symbol` (`technology="ehmi"`) | New symbol for a CAT: `.sym.json` + `.sym.ts` + `.sym.xml` + `.user.cs` + `.htmlproj` registration |
| `eae_ehmi_update_object`, `eae_ehmi_remove_object` | Change object properties (position, color, text, binding); remove an object |

`.cnv.json`/`.sym.json` are rewritten in the file's own layout (BOM, indent, line ends), which reproduces every sample byte for byte. A device's first eHMI canvas must be made in EAE (it creates the resolution list).

### 5.11. Static validation (P1)

`eae_validate` (whole solution or one component) checks:
- XML well-formedness, unique IDs, and that every `$ID` resolves.
- Every referenced type exists in the catalog.
- Connection type and direction; each data input has a single source.
- `With` validity.
- The ECC has `START`; every transition targets an existing state; every referenced algorithm exists.
- Files are registered in `.dfbproj`/`.csproj`/`.htmlproj`, and every registered file exists.
- A CAT's `.cfg` matches its network.
- HMI `TagName` and eHMI `tagName` bindings point to existing instances or sub-CATs.

This is **not** a replacement for the EAE compiler.

---

## 6. Runtime (P2) and Buildtime (P3)

- **Runtime OPC UA:** `asyncua` for browse/read/write/subscribe against a dPAC. ❓ Endpoint, port and NodeId scheme (`OpcUaNodeIdType=Guid`) need verifying. Writes are blocked by default.
- **Buildtime:** there is no SDK, so this phase starts with an investigation (checklist C1/C9):
  1. `Studio\bin\FBTypeCompiler.exe` has a CLI (golden C1c): use it to validate/compile single types headlessly (`/libdir:`, `/library:`, `/outputDir:`, feature flags). A full solution build currently requires the IDE (Tools › Check Changes, HMI › Build, eHMI › Build).
  2. If not, use UI automation (`pywinauto`) for a simple "Build solution" and read the Output/Error List.
  3. Deployment is **not automated** in the current scope.

---

## 7. Safety

1. **Read-only by default.** Project writes need `allow_write=true`. Runtime writes and UI automation have their own flags.
2. Only operate inside `project.roots`. **Never read or return** the contents of `General/Security`, certificates or `se-rbac-users.json`.
3. Dry-run, diff, backups and a JSONL audit log for every write.
4. While EAE is open, warn before writing that unsaved IDE edits to the same file would overwrite the change (C11: no file locks, auto-reload).
5. HTTP transport requires a bearer token and an IP allowlist, and is read-only by default.
6. Correct MCP tool annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`) on every tool.

---

## 8. Configuration

```toml
# eae-mcp.toml
[project]
roots = ["C:/EAE"]
allow_write = false
backup = true

[eae]
version = "26.0"
install_dir = "C:/Program Files/Schneider Electric/EcoStruxure Automation Expert - Buildtime 26.0"
library_store = "C:/ProgramData/Schneider Electric/Libraries"   # <Lib>-<Ver>/Files/<Namespace>/<Type>.fbt
catalog_file = ".eae-mcp/catalog.json"     # used on machines without EAE

[server]
transport = "stdio"            # or "http"
http_bind = "127.0.0.1:8765"
http_token_env = "EAE_MCP_TOKEN"
http_allow_write = false

[runtime]                      # P2
endpoints = []
allow_write = false
```

---

## 9. Testing

| Kind | Content |
|---|---|
| Round-trip | Parse and re-serialize every XML/JSON/C#-designer file in the fixtures; output must be byte-identical |
| Resolver | Every `$ID` in the fixtures resolves (system-library pins require the catalog) |
| Golden | Compare MCP-created files with EAE-created files from the same spec (checklist C2–C8), semantically, ignoring IDs and dates |
| Acceptance (manual, Windows) | MCP-created files open, build without errors, and render correctly in EAE 26 (Buildtime, HMI runtime, eHMI in a browser) |
| MCP | Tool tests through the in-memory client SDK; manual checks with MCP Inspector |

**Fixtures:** `solar_min` and selections from `C:\EAE`, with the following removed:
- `SnapshotCompiles/`
- `General/Security/`
- `General/Certificates/`
- `Topology/Content/`
- `se-rbac-*.json`

A fixture-trimming script (`scripts/make_fixture.py`) performs this removal so it can be repeated.

---

## 10. Roadmap

| M | Scope | Done when |
|---|---|---|
| **M0** | Finalize specs. User runs checklist C0–C11 in EAE and sends zips and screenshots | Golden files exist for Adapter, DataType, Basic, Composite, SubApp, CAT, .NET HMI symbol/canvas, eHMI symbol/canvas |
| **M1** ✅ (2026-10-02) | Server skeleton, config, safety, lossless round-trip, solution index, catalog, resolver, read-only tools (§5.1, read parts of §5.7–5.10), knowledge layer (§4) | Claude can read and explain every component of SolarPlantDemo, including both HMIs |
| **M2** ✅ (2026-10-02, pending EAE acceptance) | Write Adapter, DataType, Basic FB; `eae_validate` | Created files build in EAE |
| **M3** ✅ (2026-10-02, pending EAE acceptance) | Networks (Composite/SubApp/Layer) and resource mapping | Same |
| **M4** ✅ (2026-10-02, pending EAE acceptance) | CAT (create, sub-CAT, OPC UA) + eHMI write (symbol, canvas) | A new CAT renders on an eHMI canvas |
| **M5** | .NET HMI write (symbol, faceplate, canvas) | A new CAT renders on an HMI canvas |
| **M6** | OPC UA runtime, Buildtime automation investigation, 26.1 support | — |

M1 can start immediately, since it only needs the sample. M2+ write tools wait on the M0 golden files.

---

## 11. Open questions

None blocking. Items to be answered by the checklist: C1 (install dir contents / CLI), C3 (`nxtDataType`), C4 (SubApp format), C9 (build automation), C11 (file locking).
