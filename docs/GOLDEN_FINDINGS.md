# Golden File Findings

> Results of diffing the user's EAE 26.0 golden snapshots (`EAE_MCP_Golden`). Steps C0–C5 received 2026-10-01; C1b, C1c, C3c, C6–C11 received 2026-10-02 (see §Batch 2).
> Each step was compared file-by-file with the previous one, ignoring `obj/` build caches.

## Summary

| Step | Result | Files EAE wrote |
|---|---|---|
| C0 empty | ✅ Baseline OK | 84 files (incl. `obj/` caches) |
| C1 inventory | ⚠️ Partial | Install dir has **no IEC 61499 system libraries** (see §C1). `/?` printed nothing (GUI app) |
| C2 adapter | ✅ | `+ aTest.adp`, `+ aTest.doc.xml`, `M IEC61499.dfbproj`, `M System/.obsolete/System.sys` |
| C3 datatypes | ✅ | `+ DataType/dtStruct.{dt,doc.xml}`, `+ DataType/dtEnum.{dt,doc.xml}`, `M .dfbproj` |
| C3 `nxtDataType` experiment | ⚠️ Inconclusive | EAE loads the file without complaint and does **not** regenerate the attribute on Save All. Needs a build test (C9) |
| C3b more datatypes | ✅ | `+ dtArray`, `+ dtRange`. Kinds offered: **Enumeration, Subrange, Array, Structure** (no Alias) |
| C4 SubApp | ✅ (with a surprise) | `+ subTest/subTest.{app,doc.xml,meta.xml,subapp.offline.xml,subapp.opcua.xml}`, `+ SubApp1/…` (extracted type), `M .syslay`, `M .system`, `M .dfbproj` |
| C5 Basic FB | ✅ | `+ fbTest.{fbt,doc.xml,meta.xml}`, `M .dfbproj`, `M System/.obsolete/System.sys` |

---

## New facts (update `EAE_FILE_FORMATS.md`)

### Solution level
- A new solution also contains **`<Name>.nxtsln`** (content `﻿<Solution />`) next to the `.sln`.
- `obj/` folders exist in every project (`*.AssemblyReference.cache`, NuGet files, `IEC61499/obj/System.catinstance`). They are build artifacts and must be ignored.
- **`IEC61499/System/.obsolete/System.sys`** is a legacy single-file IEC 61499 `System` document (DOCTYPE `System`). It contains Application (with its `SubAppNetwork`) and Device/Resource. **EAE rewrites it on every save**. Open question: when the MCP server changes an application, must it also update this file? (Test in C11b.)
- On first save, EAE **re-serializes** template files. For example, `.system` went from a multi-line hand-formatted root to a single-line root with no trailing newline. Round-trip tests must use EAE-saved files, not freshly generated templates.

### `.dfbproj` registration rules ✅
- Items are grouped into ItemGroups by kind: `Reference` | `None` | `Compile` | `Folder` | `Content`.
- Within each ItemGroup, items are **sorted case-insensitively by `Include`** (`aTest` < `DataType\…` < `fbTest` < `Languages\…` < `Project` < `SubApp1` < `subTest` < `System\…`).
- One element is written as lowercase `<none Include="Languages\…">`. The writer must preserve it as-is.
- Each type in its own folder (SubApp, CAT) also gets a `<Folder Include="<name>" />` entry.
- Registration per kind:

| Kind | `Compile` metadata | Companion `None` items |
|---|---|---|
| Adapter `X.adp` | `IEC61499Type=Adapter` | `X.doc.xml` (DependentUpon `X.adp`) |
| DataType `DataType\X.dt` | `IEC61499Type=DataType` | `DataType\X.doc.xml` (DependentUpon `X.dt`) |
| Basic FB `X.fbt` | `IEC61499Type=Basic` | `X.doc.xml`, `X.meta.xml` |
| SubApp `X\X.app` | `IEC61499Type=SubApp` | `X\X.doc.xml`, `X\X.meta.xml`, `X\X.subapp.offline.xml` (`Plugin=OfflineParametrizationEditor`, `IEC61499Type=CAT_OFFLINE`), `X\X.subapp.opcua.xml` (`Plugin=OPCUAConfigurator`, `IEC61499Type=CAT_OPCUA`) + `<Folder Include="X"/>` |

- `<Parent>` (logical folder) is only written when the user places a type in a folder. It is absent in the golden solution.

### DataType ✅
- New DataTypes are created in a **`DataType\` sub-folder** of the IEC61499 project.
- The editor is **ST text** (`TYPE … END_TYPE`), and EAE converts it to XML. Syntax errors block the XML update ("Syntax error detected. XML will not be updated.").
- Enum syntax that works: `TYPE dtEnum : USINT (Stop:=0, Run:=1, Fault:=2); END_TYPE`. **`On` is reserved** and cannot be used as an identifier; `=` instead of `:=` is a syntax error.
- XML shapes:
  ```xml
  <StructuredType><VarDeclaration Name="A" Type="INT" />…</StructuredType>
  <EnumeratedType Type="USINT"><EnumeratedValue Name="Stop" Value="0" />…</EnumeratedType>
  <ArrayType BaseType="INT" Namespace=""><Subrange LowerLimit="0" UpperLimit="9" /></ArrayType>
  <SubrangeType BaseType="INT" InitialValue=""><Subrange LowerLimit="0" UpperLimit="100" /></SubrangeType>
  ```
- Header is always `Comment="IEC61131-3, Table 14#5"`, `<Identification Standard="1131-3" />`, `<VersionInfo … Remarks="Template" />`, `<CompilerInfo />`.
- Struct members have **no `ID`** attribute, unlike FB variables.
- `nxtDataType`: removing it is tolerated at load time and EAE does not restore it on Save All (the file was not modified, so it was not re-saved). Still unknown: is it needed for **compile**, and is it regenerated when the type is edited? → follow-up C3c.

### Adapter ✅
- Template default: event input `REQ` ("Request from Socket"), event output `CNF` ("Confirmation from Plug"), plus the fixed `<Service>` block with `request_confirm` / `indication_response` sequences. This matches the sample exactly.

### SubApp ✅ (previously ❓)
- Extension **`.app`**, stored in its **own folder** `subTest/subTest.app`, root `<SubAppType … Format="2.0">`, `<!DOCTYPE SubAppType …>`.
- Interface uses SubApp-specific element names:
  ```xml
  <SubAppInterfaceList>
    <SubAppEventInputs><SubAppEvent ID="…" Name="START" /></SubAppEventInputs>
    <SubAppEventOutputs><SubAppEvent ID="…" Name="EO" /></SubAppEventOutputs>
  </SubAppInterfaceList>
  <SubAppNetwork> FB…, EventConnections…, Input/Output boundary pins (with the same IDs as the interface events) </SubAppNetwork>
  ```
  ❓ Data pins presumably use `SubAppInputVars`/`SubAppOutputVars` (not exercised: subTest has event pins only).
- Boundary pin connections use the bare ID: `Source="$5D18ED6AA8AB522A"`.
- **"Untyped" SubApp in the application became a typed one:** EAE extracted the selected FBs into a new type `SubApp1` (`Comment="Extracted SubApplication Type"`, no `Format` attribute, minimal `VersionInfo`, empty `<SubAppInterfaceList />`). The layer now holds `<SubApp ID Name="SUB_APP1" Type="SubApp1" Namespace="Main" x y />`. → follow-up C4b: does EAE 26 support truly untyped SubApps at all?
- Library FBs used: `E_DELAY`, `E_PERMIT`, `E_CYCLE` with `Namespace="IEC61499.Standard"`. Generic `ADD` became `ADD_1990CFD1468AAE4A6` with `InterfaceParams="Runtime.Standard#CNT:=2;IN${CNT}:LREAL"`.

### Basic FB ✅
- Template: events `INIT`/`REQ`/`INITO`/`CNF` with default comments, vars `QI`/`QO` with comments. `REQ`/`CNF` include `With QI`/`With QO` by default.
- **`<Algorithm ID="<guid>" Name=…>`**: algorithms now carry a GUID `ID`. The older sample FBs did not have one, so the reader must accept both.
- `FBType.Basic.Algorithm.Order` lists algorithms in creation order.
- `ECTransition` without a custom curve has no `BezierPoints` attribute.
- ST text is stored verbatim, including trailing spaces (`QO := QI; ⏎`).
- Default `START` state is at `x="552.9412" y="429.4117"` (same as in the sample).

---

## C1 — System libraries are not in the install directory

- `C:\Program Files\…\Buildtime 26.0` contains only plugin templates (`EtherCATConfigurator`, `EthernetIPConfiguration`, `ProfinetConfiguration` HW-CAT templates).
- **Library store located (user, 2026-10-02):** `C:\ProgramData\Schneider Electric\Libraries\`. Example:
  `C:\ProgramData\Schneider Electric\Libraries\Runtime.Base-26.0.0.7\Files\IEC61499.Standard\E_CYCLE.fbt`
  - Layout: `Libraries\<LibraryName>-<Version>\Files\<Namespace>\<Type>.<ext>`
  - One library package (`Runtime.Base`) holds several namespaces (`IEC61499.Standard`, presumably `Runtime.Standard`, `Runtime.Management`, …).
  - The version is part of the folder name, so several versions can coexist. The catalog must pick the version the solution references (❓ where the referenced version is recorded: `.dfbproj` `<Reference>` has no version).
  - ❓ Whether these `.fbt` files are plain XML (readable interface) or compiled/encrypted. → follow-up C1b.
- Useful executables found in `Studio\bin`:
  - `EcoStruxureAutomationExpert.exe` (the IDE)
  - **`FBTypeCompiler.exe`**, **`FBTypeLinker.exe`** (possible CLI compiler)
  - `Microsoft.Build\MSBuild.exe` (the `.dfbproj` imports `$(SharpDevelopBinPath)\NxtControl.Build.61499.Targets`, so a **command-line build via MSBuild may be possible**)
  - `FbLibInstaller.exe`, `MissingLibrariesInstaller.exe`, `ArchiveDeployTool.exe`

  This changes the outlook for Buildtime automation (P3): headless build may be feasible without UI automation.

---

## Follow-ups for the user (batch 1) — all closed in batch 2 / 2026-10-02

| # | Action | Why |
|---|---|---|
| **C1b** | Inventory the library store and send one sample type: see `USER_GUIDE_M0.md` › C1b | Build the system-type catalog |
| **C1c** | Run each and save output:<br>`& "…\Studio\bin\FBTypeCompiler.exe" /? > "$G\C1c_fbtc.txt" 2>&1`<br>`& "…\Studio\bin\FBTypeLinker.exe" /? > "$G\C1c_fbtl.txt" 2>&1`<br>`& "…\Studio\bin\Microsoft.Build\MSBuild.exe" -version > "$G\C1c_msbuild.txt" 2>&1` | Headless build investigation |
| **C3c** | In C9, build **with** `dtStruct.dt` still missing `nxtDataType` and note any error. Then open `dtStruct` in the editor, add a field `D : BOOL`, save, and check whether `nxtDataType` came back | Decide whether the server must generate `nxtDataType` |
| **C4b** | In EAE, check whether a SubApp can be created inside the application **without** creating a type (look for a "untyped" or "group" option). Screenshot the context menu | Untyped SubApp support |
| **C11b** | (Later) Delete `IEC61499\System\.obsolete\System.sys` in a copy of the solution, open it in EAE: is it regenerated? Any error? | Decide whether the server must maintain this file |

---

# Batch 2 — C1b, C1c, C3c, C6–C11 (received 2026-10-02)

## Summary

| Step | Result | Files EAE wrote (ignoring `bin/`, `obj/`) |
|---|---|---|
| C1b library store | ✅ | 40,061 files inventoried (see §Library store) |
| C1c CLI tools | ✅/⚠️ | `FBTypeCompiler.exe` has a documented CLI ✅. `FBTypeLinker.exe` printed nothing. Standalone `MSBuild.exe` crashes (missing `System.Memory`) |
| C3c `nxtDataType` | ✅ Resolved | After editing `dtStruct` (add `D : BOOL`) and Save All, EAE **regenerated** `nxtDataType` |
| C6 composite | ✅ | `+ cfbTest.{fbt,doc.xml,meta.xml,composite.offline.xml}`, `M .dfbproj` (no adapter pin was added) |
| C7 CAT | ✅ (no faceplate) | 11 files in `IEC61499/catTest/`, 8 in `HMI/catTest/`, 5 in `WEB/catTest/`, `M` all three project files. The faceplate was not created (screenshot shows `sDefault`) |
| C7b folders | ✅ | Only `General/Folders.xml`, `.dfbproj` and the CAT `.cfg` change. **No physical directories** |
| C8 system | ✅ | Layer, resource, both `opcua.xml`, HMI canvas + resolution, eHMI canvas + resolution, `HMI.csproj`, `WEB.htmlproj` |
| C9 build | ✅ | Build log captured in `note.txt`. Source changes: only `System/.obsolete/System.sys` |
| C11 file lock | ✅ Resolved | Files are **not locked** while EAE is open. EAE **auto-reloads** externally changed files |
| C4b untyped SubApp | ❓ Not answered | — |

## Decisions unlocked

1. **`nxtDataType` (C3c):** the server may write `.dt` files **without** `nxtDataType`. EAE regenerates it on the next edit of the type. Still recommended: test once that a solution with a missing `nxtDataType` builds (C3d).
2. **File locking (C11):** EAE does not lock files and reloads changes made outside the IDE. The "block writes while EAE is open" rule in SPECS §3.4/§7 is **relaxed**. Writes are allowed while EAE is open, but the server must warn: if the user has **unsaved** edits in EAE for the same file, saving in EAE overwrites the server's change.
3. **Library catalog (C1b):** fully feasible offline. Interfaces are plain XML (see below).
4. **Library version:** `.dfbproj` records it: `<Reference Include="Runtime.Base"><Version>26.0.0.7</Version></Reference>`. The catalog resolves `Libraries\<Name>-<Version>`.
5. **Headless build (C1c):** `FBTypeCompiler.exe` accepts files plus `/libdir:`, `/library:`, `/outputDir:`, `/enable:`/`/disable:` features (the same flags as the `.dfbproj` properties: `NxtTypeECC`, `EventVariables`, `CheckValueRange`, …). It could validate single types outside the IDE. A full solution build still needs the IDE (Tools › Check Changes / HMI › Build / eHMI › Build).

## Library store ✅

`C:\ProgramData\Schneider Electric\Libraries\`
- One folder per package and version: `Runtime.Base-26.0.0.7`, `SE.DPAC-26.0.0.17`, `SE.DPAC-26.0.0.18`, `SE.Standard-26.0.0.6`, … (24.1, 25.0 and 26.0 side by side). Original packages are kept as `.backup\<Name>-<Version>.fblib`.
- Package layout:
  ```
  <Name>-<Version>\
    <Name>.iecproj                    # package project
    Files\<Namespace>\<Type>.{fbt,adp,dt,fct,res,dev,…} + .doc.xml
    IEC61499\<Name>.<GUID>.dll        # compiled types
    HwConfiguration\, HMI\, Documentation\, Icons\, Exports\, Configuration\
    Manifest.info, License.txt
  ```
- `Runtime.Base-26.0.0.7\Files` namespaces: `IEC61499.Standard` (40), `Runtime.Standard` (105), `Runtime.Fieldbus` (110), `Runtime.System` (68), `Runtime.IoCommon` (41), `Runtime.Management` (16), … `EMB_RES_ECO` is `Runtime.Management\EMB_RES_ECO.res`. `Soft_dPAC` is `SE.DPAC-26.0.0.17\Files\Soft_dPAC\Soft_dPAC.dev` (+ `.properties.xml`).
- File counts in 26.0 packages: 4,410 `.fbt`, 229 `.adp`, 198 `.dt`, 140 `.fct`, 28 `.dev`.
- **Library type files are readable XML.** Example `E_CYCLE.fbt`: full `InterfaceList` (events, `With`, vars without IDs), `Service`, plus `Attribute nxtLibraryData` (encrypted body) and `ObsoleteNamespace`. Pins of library types have **no IDs**, which explains why networks reference them by name (`$<FBID>.EO`).

## Composite FB (C6) ✅

- `FBType Format="2.0" Comment="Composite Function Block Type"`. Boundary `<Input>/<Output>` reuse the **same IDs** as the interface events/vars.
- Connections: `$<boundaryID>` → `$<FBID>.<PinID>` for user types, `$<FBID>.<PinName>` for library types (`$B928….START`, `$B928….EO`).
- Parameters: `$<VarID>` for user types (`$70FEA075D717A101` = `fbTest.IN2`), `$<VarName>` for library types (`$DT`).
- Instance names default to `FB1`, `FB2`, ….
- Registration: `Compile cfbTest.fbt` with `IEC61499Type=Composite`, plus `None` for `.composite.offline.xml`, `.doc.xml`, `.meta.xml`.

## CAT (C7) ✅

**IEC61499/catTest/** (11 files): `.fbt`, `.cfg`, `.doc.xml`, `.meta.xml`, `_CAT.offline.xml`, `_CAT.opcua.xml`, `_HMI.fbt`, `_HMI.doc.xml`, `_HMI.meta.xml`, `_HMI.offline.xml`, `_HMI.opcua.xml`.
- `catTest.fbt`: `Format="2.0" Comment="CAT Function Block Type"`, `Attribute HMI.Alias=""`, default INIT/REQ/INITO/CNF/QI/QO interface. The network contains the user FBs plus **`IThis` (type `catTest_HMI`)**.
- `catTest_HMI.fbt`: SIFB. Its interface **is the HMI data contract**: user-added input vars (e.g. `OUT1 : INT`) become values shown in HMI symbols. Per the user's note, for values to reach the HMI:
  1. add the var to `catTest_HMI` with an event `With`;
  2. `IThis.QI` must be `TRUE` and `IThis.INIT` must be triggered;
  3. the value is sent when its event (`REQ`) fires.
- `catTest.cfg` now includes **`<WebSymbol Name="seDefault" FileName="..\WEB\catTest\catTest_seDefault.sym.ts">`** with `DependentFiles` (`.sym.json`, `.sym.xml`, `.user.cs`), next to `<Symbol>` for .NET HMI, and `<MetaFile>`.
- `catTest_HMI.opcua.xml`: one `<OPCUAVariable UID="<HMI var ID>" Enabled="false">` per HMI input var.
- `.dfbproj` registration (note the quirks to preserve: duplicated `None` items for `_HMI.doc.xml`/`_HMI.meta.xml` with different `DependentUpon`, and an item pointing into the HMI project):
  ```xml
  <Compile Include="catTest\catTest.fbt"><IEC61499Type>CAT</IEC61499Type></Compile>
  <Compile Include="catTest\catTest_HMI.fbt"><IEC61499Type>CAT</IEC61499Type><Usage>Private</Usage>
    <DependentUpon>catTest.fbt</DependentUpon><HMI>..\HMI\catTest\catTest_sDefault.cnv.cs</HMI></Compile>
  <None Include="catTest\catTest.cfg"><DependentUpon>catTest.fbt</DependentUpon><IEC61499Type>CAT</IEC61499Type></None>
  <None Include="..\HMI\catTest\catTest_sDefault.doc.xml"><DependentUpon>catTest.fbt</DependentUpon></None>
  ```

**HMI/catTest/** (.NET HMI):
- `catTest.def.cs`, `catTest.event.cs`, `catTest.Design.resx` (generated).
- `catTest_sDefault.cnv.cs` (`class sDefault : NxtControl.GuiFramework.HMISymbol`, namespace `HMI.Main.Symbols.catTest`), `.cnv.Designer.cs`, `.cnv.resx`, `.cnv.xml`, `.doc.xml`.
- `.cnv.xml` mapping mirrors `_HMI.fbt`: `<EventInputs><Event Name="REQ">OUT1</Event></EventInputs><Inputs><Input Name="OUT1" Type="INT"/></Inputs>`.
- Designer: a value widget bound by `TagName = "OUT1"` (the HMI var name), e.g. `System.HMI.Symbols.Base.BarValueHorizontal<short>` (INT → `short`). Default `SymbolSize = 600×400`.
- `HMI.csproj`: `Compile` for `.def.cs`, `.event.cs`, `.cnv.cs`, `.cnv.Designer.cs` (DependentUpon `.cnv.cs`). `EmbeddedResource` for `.Design.resx`, `.cnv.resx`, `.cnv.xml`.

**WEB/catTest/** (eHMI):
- `catTest_seDefault.sym.json`: objects such as `System.WEB.Symbols.Base.Label` with `"tagName": "OUT1"`, `"valueType": "short"`, `"text": "${Value}"`, color tokens (`LabelBackColor`, …); `_design_` holds `{width:600,height:400,background:"CanvasBackColor",overlay:"Transparent"}`.
- `.sym.ts`: template `class seDefault extends NxtControl.GuiFramework.RuntimeSymbol`, namespace `WEB.Main.Symbols.catTest`.
- `.sym.xml`: empty `<Mapping>`. `.user.cs`: `partial class seDefault : NxtControl.GuiHTMLFramework.RuntimeSymbol`.
- `WEB.htmlproj`: `Compile .user.cs` (DependentUpon `.sym.ts`), `None .sym.ts`, `EmbeddedResource .sym.json` / `.sym.xml` (DependentUpon `.sym.ts`).

## Folders (C7b) ✅

- Folders are **purely logical**. No directories are created on disk.
- **`General/Folders.xml`** holds `<Folder Type="<category>" Name="<dotted path>"><Items/></Folder>`. Categories seen: `Basic`, `Composite`, `SubApp`, `CAT`, `Adapter`, `DataType`, `SystemDevice`.
- Paths start with a dot and nest with dots: `.Logic`, `.Logic.Sub`. Every level has its own entry.
- Membership: `<Parent>.Logic.Sub</Parent>` on the type's `Compile` item in `.dfbproj`. A CAT also gets `Folder=".Logic"` on the root of its `.cfg`.
- Creating an empty folder only touches `Folders.xml` (F1). Moving a type only touches `.dfbproj` (F2).
- **Device folders** (`SystemDevice`) list members explicitly: `Root` contains `<item>:.Line1</item>` (sub-folder reference, prefix `:`), `.Line1` contains device IDs. The `.sysdev` `Compile` item also gets `<Parent>.Line1</Parent>`.
- ⚠️ **EAE quirk on rename (F5):** renaming the *Basic* folder `.Logic` → `.Core` rewrote `<Parent>` of **all** categories (Adapter, DataType, SubApp, Composite and CAT items too), while `Folders.xml` renamed only the Basic entries. After F6, `Folders.xml` contained `Composite .Core` and the other categories still `.Logic` while their items say `.Core`. So EAE tolerates `Folders.xml` and `<Parent>` disagreeing.
  - **Server rule:** the folder tree of a category is the union of the `Folders.xml` entries and the `<Parent>` values of its items.
  - On rename, the server changes `<Parent>` **only for items of the same category**, plus that category's `Folders.xml` entries. It does not reproduce the EAE quirk.

## System, mapping, OPC UA (C8) ✅

- Layer: `<FB ID="3811CA558F6E3EFC" Name="CAT1" Type="catTest" Namespace="Main" x y/>` inside `<SubAppNetwork>`.
- Resource: `<FB ID="AD6F4C542847B13B" Name="CAT1" Type="catTest" Namespace="Main" Mapping="3811CA558F6E3EFC" x y/>`. The resource FB gets a **new ID**; `Mapping` points to the layer FB.
- OPC UA exposure is written **twice**, as an attribute keyed by an instance path of IDs:
  - `<layer>/opcua.xml`: `<OPCUAComplexObject UID="<appId>"><OPCUAAttribute Name="Exposed" Value="True" Locked="false" AttributeMask="True;True|False;True" Context="3811CA558F6E3EFC.78BDA8C5F15E2DB4.C5DC1469B4A95F87"/>` (layer FB ID . `IThis` FB ID . `OUT1` var ID).
  - `<resource>/opcua.xml`: same, with `UID="<deviceId>"` and the **resource** FB ID as the first path segment.
- Per the user, OPC UA can be exposed from the System or from the CAT configuration. A resource also needs `DPAC_FULLINIT` to initialize before deployment.

## Canvases (C8) ✅

**.NET HMI:** a resolution must exist before a canvas can be created.
- `HMI/CanvasResolution_2.cnv.{cs,Designer.cs,resx}`: the resolution frame (header, login, navigation, `workArea`). Generated from a template, hand-indented.
- `HMI/Canvas1.cnv.{cs,Designer.cs,resx}`: `class Canvas1 : NxtControl.GuiFramework.HMICanvas`, namespace `HMI.Main.Canvases`. The designer places `HMI.Main.Symbols.catTest.sDefault` with **`TagName = "3811CA558F6E3EFC"`** (layer FB ID), `SecurityToken = 4294967295u`, `DesignMatrix` for position. Canvas `Size` = resolution work area (1280×730).
- `CanvasesResolutionList.xml`: `<CanvasResolution Name="1280x800" StartCanvasClass="HMI.Main.Canvases.CanvasResolution_2" Width Height WorkAreaWidth WorkAreaHeight …><Topology Name="Default"><Canvases><Canvas Name="Canvas1" Instance="HMI.Main.Canvases.Canvas1"><Children/></Canvas>`.
- `HMI.csproj`: `Compile Canvas1.cnv.cs` with **`<Canvas>true</Canvas>`**, `.Designer.cs` DependentUpon, `EmbeddedResource .cnv.resx`. The resolution canvas has no `<Canvas>` flag.

**eHMI:** canvases are per device, in `WEB/<deviceId>/`.
- `Canvas1.cnv.json`: `{"objects":[{"type":"WEB.Main.Symbols.catTest.seDefault","name":"symbol1","left","top","width","height","tagName":"3811CA558F6E3EFC"}],"background":"CanvasBackColor","overlay":"Transparent","width":1024,"height":688}`.
- `Canvas1.cnv.ts` (`class Canvas1 extends NxtControl.GuiFramework.Canvas`), `Canvas1.user.cs` (`partial class Canvas1 : NxtControl.GuiHTMLFramework.Canvas`).
- `WEB/<deviceId>/WebCanvasesResolutionList.xml`: new `<CanvasResolution Name="1024x768" StartCanvasClass="WEB.Main.Canvases.CanvasResolution_2" …>` with the canvas in `Topology/Canvases`.
- `WEB.htmlproj`: `<CreateTemplate>true</CreateTemplate>` removed, `<CanvasSize>` added. `Compile <dev>\Canvas1.user.cs`, `None <dev>\Canvas1.cnv.ts` with `<Canvas>true</Canvas>`, `EmbeddedResource <dev>\Canvas1.cnv.json`.

## Build (C9) ✅

- IDE commands: **Tools › Check Changes / Recheck All / Clean** (IEC 61499), **HMI › Build / Rebuild / Clean**, **eHMI › Build / Rebuild / Clean**.
- Order in the log: HMI verify → HwConfiguration → IEC 61499 (`NFBTCompiler`, "Checking …" then "Compiling … build ids") → HMI build → eHMI build → "IEC61499 Build for Deploy" (System precompile, network connections, asset tag names) → AssetLinkData, Topology, ATV.
- Generic FBs are materialized as `obj/fbt/gfbt/ADD_1990CFD1468AAE4A6.gfbt` and compiled like user types.
- Outputs go to `*/bin/` (`IEC61499/bin/Default/IEC61499.dll`, `.offlineLib`, `.opcuaLib`, `HMI/bin/…`, `WEB/bin/…`). The server must ignore `bin/` and `obj/`.
- No log files were found under the Schneider/EAE folders. The Output window is the only build log.

## Follow-ups — closed 2026-10-02

| # | Outcome |
|---|---|
| C1b, C1c, C3c | Done in batch 2 (see above) |
| **C3d** | ✅ User: removing `nxtDataType` from `dtEnum.dt` and running Recheck All gives **no error**. The server may omit `nxtDataType` when creating or editing `.dt` files |
| **C4b** | ✅ User: a SubApp is **only a packaging of application content, not a reusable type**. Only CAT (and FB/Adapter/DataType/Function) types are reusable. EAE still stores each SubApp's content in a `<Name>/<Name>.app` file (`SubAppType`, `IEC61499Type=SubApp`) referenced from the layer as `<SubApp Type="<Name>">`. **Server rule:** treat a SubApp as application structure (create/edit it from the application), never offer it as a library type to instantiate elsewhere |
| **C7c** | Inferred from SolarPlantDemo (see §Faceplates). No golden capture |
| **C7d** | Researched from SolarPlantDemo (see §Adapters). No golden capture |
| C11b | Optional. Until tested, the server leaves `.obsolete/System.sys` untouched; EAE rewrites it on every save |

## Faceplates (.NET HMI) — inferred from SolarPlantDemo

- Files: `HMI/<Cat>/<Cat>_f<Name>.cnv.cs`, `.cnv.Designer.cs`, `.cnv.resx`, `.doc.xml`. **No `.cnv.xml`** mapping file (symbols have one, faceplates do not).
- Class: `public partial class fMain : NxtControl.GuiFramework.HMIFaceplate`, namespace **`HMI.Main.Faceplates.<Cat>`** (symbols use `HMI.Main.Symbols.<Cat>`).
- `.cfg`: `<Symbol Name="fMain" FileName="..\HMI\<Cat>\<Cat>_fMain.cnv.cs" DocFile="…_fMain.doc.xml" IsFaceplate="true">` with `DependentFiles` `.cnv.Designer.cs` and `.cnv.resx`.
- `HMI.csproj`: `Compile .cnv.cs`, `Compile .cnv.Designer.cs` (DependentUpon `.cnv.cs`), `None .doc.xml` (DependentUpon `.cnv.cs`), `EmbeddedResource .cnv.resx` (DependentUpon `.cnv.cs`).
- Opening: the generated `<Cat>.def.cs` gets one property per faceplate on each symbol class (`private HMI.Main.Faceplates.<Cat>.fMain fMain { get { … RegisterHMIFaceplate … } }`). Symbols open it from code-behind. Because `.def.cs` is generated by EAE, **after the server creates a faceplate the user must let EAE regenerate `.def.cs`** (e.g. open the CAT and save, or rebuild). This must be verified in acceptance testing.
- Bindings inside faceplates use the same `TagName` scheme as symbols: sub-CAT name (`"EXPLIM"`) or a dotted path into nested sub-CATs (`"Plant.Broadcaster_v1_0"`).
- eHMI faceplates: SolarPlantDemo has none (`<WebSymbol>` entries only), so eHMI faceplates stay out of scope until a sample exists.

## Adapters in networks — researched from SolarPlantDemo

- **Two declaration syntaxes**, depending on the FB kind:
  - Composite/CAT interfaces: `<AdapterInputs>` / `<AdapterOutputs>` → `<Adapter Name="IPlug" Type="aGrid_v1_0" Namespace="Main"/>`. The network has a boundary pin `<Input|Output Name="IPlug" Type="Adapter"/>`.
  - Basic FB interfaces: IEC-standard `<Sockets>` / `<Plugs>` → `<AdapterDeclaration Name="Plant" Type="aPlant_v1_0" Namespace="Main"/>`.
  - The reader must accept both. The writer uses the syntax of the FB kind being written.
- Connections live in `<AdapterConnections>`, e.g. `<Connection Source="$35.Grid" Destination="$Grid.IPlug"/>` or, in legacy format, `Source="fbBroadcasterGrid_v1_0.ISocket" Destination="ISocket"`.
- Adapter pins never had IDs in the sample. They are always referenced by **name**.

## Reference resolution — generalized rule

Network references are `$<node>[.<pin>]` (Format 2.0) or `<node>[.<pin>]` (legacy):
- `<node>` is the **`ID` attribute value** of an `<FB>`/`<SubApp>` or of a boundary `<Input>/<Output>`. **IDs are not always 16-hex.** Observed: 16-hex (`3D6E242334FC9264`), small integers (`35`, from `Configuration.FB.IDCounter`), and the **instance name itself** (`<FB ID="ALMW" Name="ALMW">`, sub-CAT instances). A boundary pin without an `ID` is referenced by its name (`$AssetName`).
- `<pin>` is the pin's `ID` when the referenced type declares IDs for that pin, otherwise the pin **name** (library types, adapter pins, older user types).
- Parameters follow the same rule: `$<VarID>` or `$<VarName>`.
- **Resolver algorithm:** look up `<node>` among the network's IDs, then its names. Look up `<pin>` among the target type's pin IDs, then its pin names. The writer emits the form the target type supports: ID if the pin has one, name otherwise.
