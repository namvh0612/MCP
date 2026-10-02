# EAE 26.0 — Solution File Formats (reverse-engineered)

> Source: analysis of `SolarPlantDemo_v7.sln` (EAE **26.0.0.0**, `NxtVersion=26.0.0.0`).
> This is the reference for the MCP server's parsers and writers.
> **Verified/extended by golden files C0–C5:** see [`GOLDEN_FINDINGS.md`](GOLDEN_FINDINGS.md), which takes precedence where the two differ.
> Legend: ✅ observed directly in the sample · ⚠️ inferred, must be verified in EAE · ❓ unknown.

---

## 1. Solution layout

```
SolarPlantDemo.sln                       # VS solution (SharpDevelop 5.2 format)
├─ IEC61499/IEC61499.dfbproj             # Main logic project (namespace "Main")
├─ HMI/HMI.csproj                        # .NET HMI (WinForms-like canvases, C#)
├─ WEB/WEB.htmlproj                      # eHMI (web HMI, TypeScript + JSON)
├─ HwConfiguration/*.hwconfigproj        # Hardware configuration
├─ Topology/TopologyManager.topologyproj # Physical/network topology (JSON)
├─ AssetLinkData/*.assetLinkDataproj     # Asset Link (JSON)
├─ ATVHMIPlugin/*.atvdisplayproj         # ATV drive plugin
├─ SE.Agile/…                            # User library (same set of 6 projects)
├─ General/                              # Shared config (Folders, Archive, RBAC, Security, Certificates)
└─ PluginData/                           # Plugin data (AgileCat, ChangeHistory_*.json)
```

Project type GUIDs in `.sln` ✅:

| GUID | Project kind | Extension |
|---|---|---|
| `{EAD1E85F-CEF5-4861-AFF8-597F2DDE70FC}` | IEC 61499 library/app | `.dfbproj` |
| `{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}` | C# (.NET HMI) | `.csproj` |
| `{38DB5ADD-0BC9-44D4-BE85-0EAFA8D5BD5F}` | WEB (eHMI) | `.htmlproj` |
| `{72AEB29F-A91B-8B3D-40ED-1C96841A14A3}` | HW configuration | `.hwconfigproj` |
| `{E25C2A81-DD87-490C-A304-820B0BA163F2}` | Asset Link | `.assetLinkDataproj` |
| `{B8625A29-8134-4135-BEBD-5371646CD051}` | Topology | `.topologyproj` |
| `{AF5A4E9E-1CB6-4325-AE5C-F3437C6CEE36}` | ATV display plugin | `.atvdisplayproj` |

**An EAE "library" is a set of projects** sharing a prefix (`SE.Agile`, `SE.Agile.HMI`, `SE.Agile.WEB`, …) ✅.

### 1.1. `.dfbproj` — the registry of every object ✅

MSBuild XML. Every file is declared as `<Compile>` (a type) or `<None>`/`<Content>` (an auxiliary file), with metadata:

| Metadata | Meaning |
|---|---|
| `<IEC61499Type>` | `Adapter`, `Basic`, `Composite`, `CAT`, `DataType`, `Function`, `System`, `SystemApplication`, `SystemLayer`, `SystemDevice`, `SystemResource`, `CAT_OFFLINE`, `CAT_OPCUA`, `CAT_OPCUACLIENT` `SubApp` (golden C4) (❓ `ServiceInterface`) |
| `<Parent>` | Logical folder in Solution Explorer (e.g. `.ControlModule`, `.Connectors`). Matches `General/Folders.xml` |
| `<DependentUpon>` | Parent/child relationship (CAT_HMI → CAT, sysdev → system, …) |
| `<Plugin>` | Editor that owns the file (`OPCUAConfigurator`, `OfflineParametrizationEditor`, `OPCUAClientConfigurator`) |

Notable project properties: `NxtVersion`, `ProjectCreatedVersion`, `HMIProject`, `WebProject`, `CATInstancesHaveIds=true`, `OpcUaNodeIdType=Guid`, `CheckConnectionsStrictly`, `MultiUserSupport`.

System libraries are referenced with `<Reference Include="Runtime.Base|SE.DPAC|SE.HwCommon|SE.Standard|Standard.OPCUAClient">`. They are **not in the solution**; they live in the library store `C:\ProgramData\Schneider Electric\Libraries\<Lib>-<Version>\Files\<Namespace>\<Type>.fbt` (e.g. `Runtime.Base-26.0.0.7\Files\IEC61499.Standard\E_CYCLE.fbt`) ✅. User libraries are referenced with `<ProjectReference>` ✅.

> **Consequence for the MCP server:** adding or removing a type must also update `.dfbproj` (and `Folders.xml` for a new folder). Otherwise Buildtime does not see the file.

---

## 2. IEC 61499 types

All use `<!DOCTYPE … SYSTEM "../LibraryElement.dtd">` (the DTD file is **not** in the solution ⚠️) and `utf-8` encoding; some files carry a BOM.

### 2.1. Identifiers — the most important rule ✅

| Object | ID form |
|---|---|
| Type (FBType/AdapterType/POUType) | `GUID="xxxxxxxx-xxxx-…"` |
| Event, VarDeclaration, FB instance, network boundary Input/Output | `ID="` 16 hex `"` (e.g. `CAB0CAF95B2393DF`). Can be shorter when leading zeros are dropped (e.g. `BF5B9921346944`) |
| System, Application, Layer, Device | GUID |
| Resource | 16 hex |
| FB inside older CATs/composites | Small integer IDs (`ID="35" UID="1"`) plus the `Configuration.FB.IDCounter` attribute |

**Two reference styles inside networks:**
- **Format 2.0** (`Format="2.0"` on FBType/Layer/Resource): `Source="$<FBID>.<PinID>"`, `Parameter Name="$<VarID>"`. When the pin belongs to a system-library type (no ID available in the solution), the pin name is used instead: `$8E037BCAE66EA7E9.EO`. Parameters may also be `$<VarName>` (e.g. `$RootPath`).
- **Legacy format:** `Source="fbX.INITO"`, `Parameter Name="VALUE1"`.

→ The resolver must support **both** styles and map ID ↔ name through the type index.

### 2.2. Adapter — `.adp` ✅

```xml
<AdapterType GUID=… Name="aPricingUpdate_v1_0" Namespace="Main">
  <InterfaceList> <EventInputs/EventOutputs/InputVars/OutputVars> … </InterfaceList>
  <Service RightInterface="PLUG" LeftInterface="SOCKET"> … </Service>
</AdapterType>
```
Companion file: `.doc.xml` (DocBook).

Inside an FB, adapters are declared with `<AdapterInputs>` / `<AdapterOutputs>` → `<Adapter Name="ISocket" Type="aGrid_v1_0" Namespace="Main"/>`. EAE uses these names instead of the standard's `Plugs`/`Sockets`. Connections go in `<AdapterConnections>`.

### 2.3. DataType — `.dt` ✅ (not `.dtp`)

```xml
<DataType Namespace="SE.Agile" Name="MQTTOption_v1_0">
  <Attribute Name="nxtDataType" Value="<base64 blob>" Context="<number>" />
  <Identification Standard="1131-3" />
  <EnumeratedType Type="USINT"><EnumeratedValue Name="Disable" Value="0"/>…</EnumeratedType>
  <!-- or <StructuredType><VarDeclaration …/></StructuredType> -->
</DataType>
```
The sample has 14 structs and 6 enums. Golden C3b confirms `ArrayType` and `SubrangeType`; EAE 26 offers no Alias kind ✅. New DataTypes go into a `DataType\` sub-folder ✅.

⚠️ **`nxtDataType`** is an encrypted or hashed blob generated by Buildtime and present on 100% of `.dt` files. **Must verify** whether Buildtime regenerates it when a `.dt` lacks it (checklist C3).

### 2.4. Basic FB — `.fbt` with `<BasicFB>` ✅

```xml
<FBType GUID=… Name=… Namespace="Main">
  <InterfaceList> Events (with <With Var>), InputVars, OutputVars (ID, Type, InitialValue, ArraySize, Comment) </InterfaceList>
  <BasicFB ID="<guid>">
    <Attribute Name="FBType.Basic.Algorithm.Order" Value="REQ,RSP,TIMEOUT" />
    <InternalVars> … </InternalVars>
    <ECC>
      <ECState Name="START" x y> <ECAction Algorithm="REQ" Output="CNF"/> </ECState>
      <ECTransition Source Destination Condition="REQ" x y>
         <Attribute Name="Configuration.Transaction.BezierPoints" …/>
      </ECTransition>
    </ECC>
    <Algorithm Name="REQ"> <VarDeclaration …/>(local vars) <ST><![CDATA[ … ]]></ST> </Algorithm>
  </BasicFB>
</FBType>
```
Companion files: `.doc.xml`, `.meta.xml` (usually empty or BOM only).
Arrays: `Type="BYTE" ArraySize="1024"`. Strings: `STRING[64]`.

### 2.5. Composite FB — `.fbt` with `<FBNetwork>` ✅

A network contains:
- `<FB ID Name Type Namespace x y>` with optional `<Parameter>` and `<Attribute>` children.
- `<Input>`/`<Output>`: network boundary pins, `Type="Event|Data|Adapter"`.
- `<EventConnections>`, `<DataConnections>`, `<AdapterConnections>`. A connection may carry layout info (`dx1/dx2/dy`, `<AvoidsNodes>`, `<Points>`).

Companion file: `.composite.offline.xml` (`<OfflineParameterModel/>`).

**Generic FB** (a library FB with a parameterized interface): `Type="NETIO_62C40486027F6142"` plus `<Attribute Name="Configuration.GenericFBType.InterfaceParams" Value="Runtime.IoCommon#I:=1;SD:BYTE[256];RD:BYTE[1024]"/>` ✅. ❓ How the hash suffix is derived from the parameters.

### 2.6. Function (POU) — `.fct` ✅

`<POUType>` with `<InterfaceList ReturnValueType="INT">` and `<POUBasicFunction><TempVars/><Algorithm><ST/></Algorithm></POUBasicFunction>`. Stored under `POU/`.

### 2.7. SubApp ✅ (golden C4)

`<Name>/<Name>.app`, root `<SubAppType Format="2.0">` with `<SubAppInterfaceList>` (`SubAppEventInputs/SubAppEvent`, …) and `<SubAppNetwork>`. Companion files: `.doc.xml`, `.meta.xml`, `.subapp.offline.xml`, `.subapp.opcua.xml`. Registered as `IEC61499Type=SubApp`. Instances in a layer: `<SubApp ID Name Type Namespace x y/>`. Details in `GOLDEN_FINDINGS.md`.

### 2.8. Service Interface FB (SIFB) ✅ (partial)

A CAT's `_HMI.fbt` is an SIFB: `<InterfaceList>` plus `<Service RightInterface="" LeftInterface="">` with no body. Real runtime SIFBs (NETIO, E_DELAY, …) live in the system libraries.

---

## 3. CAT (Composite Automation Type) ✅

Each CAT is a folder `IEC61499/<CatName>/`:

| File | Role |
|---|---|
| `<Cat>.fbt` | Main FB (usually Composite, `Format="2.0"`). Attributes `HMI.Alias`, `Configuration.FB.IDCounter`; Agile CATs also have `AgileCatGuid`, `AgileBasic`, `AgileBroadcasterGuid` |
| `<Cat>.cfg` | **CAT manifest** (namespace `http://www.nxtcontrol.com/IEC61499.xsd`): `<SubCAT>` (nested CATs), `<HMIInterface>` → `<Symbol>` (.NET HMI symbols/faceplates), `<Plugin>` (auxiliary files), `<HWConfiguration>` |
| `<Cat>_HMI.fbt` | HMI interface SIFB (instance `IThis`) |
| `<Cat>_CAT.offline.xml`, `<Cat>_HMI.offline.xml` | Offline parametrization |
| `<Cat>_CAT.opcua.xml`, `<Cat>_HMI.opcua.xml` | OPC UA exposure (`<OPCUAObject>/<OPCUAVariable UID Enabled>` with `AccessLevel`, `RTAddress`) |
| `<Cat>.doc.xml`, `.meta.xml` | Documentation, metadata |
| `HMI/<Cat>/…` | .NET HMI symbols/faceplates (§5) |
| `WEB/<Cat>/…` | eHMI symbols (§6) |

**"Agile" architecture pattern in the sample** (worth turning into a prompt/template):
`acXxx` (CAT) = `fbXxx` (Basic FB with the logic) + `HMI_Indication_*`/`HMI_Control_*` (sub-CATs for HMI I/O) + `BroadcasterXxx`/`ListenerXxx` (pub/sub between CATs via adapter `aXxx` and MQTT) + `InitComponent`/`GetAssetName`.

---

## 4. System / Application / Device / Resource ✅

```
IEC61499/System/
  <sysId>.system                       # <System ID Name> (ns https://www.se.com/LibraryElements)
  <sysId>.cfg, .doc.xml
  <sysId>/
    <appId>.sysapp                     # <Application Name="APP1" ID>
    <appId>/<layerId>.syslay           # <Layer IsDefault Format="2.0"><SubAppNetwork> … FB instances + connections
    <appId>/<layerId>/{offline,opcua,opcuaclient}.xml
    <devId>.sysdev                     # <Device Name="EcoRT_0" Type="Soft_dPAC" Namespace="SE.DPAC">
    <devId>/<resId>.sysres             # <Resource Name="RES0" Type="EMB_RES_ECO"> <FBNetwork> FBs with Mapping="<layer FB ID>"
    <devId>/<resId>/{offline,opcua,opcuaclient,symlink}.xml
    <devId>/<devId>.hcf                # HW config items
    <devId>/<devId>.Simulation.Binding.xml   # logical ports (51500, 51496)
    <devId>/F513CAE3-….Properties.xml  # Device properties: Deploy (ClearBeforeDeploy, AutoStart), Boot (BootMode), eHMIProfile, SecurityApp
    <devId>/E0601B81-….Properties.xml
  OpenAdapter/OpenAdapter.Connections.xml
  snapshot.xml
```

**Mapping:** a resource FB has `Mapping="<ID of the layer FB>"` and **duplicates** its `<Parameter>` elements. Changing a parameter in the application therefore requires syncing the resource ⚠️ (or leaving that to Buildtime).

Device types observed: `Soft_dPAC`, `Archive_Database`, `Archive_Link` (namespace `SE.DPAC`).

---

## 5. .NET HMI (`HMI/`, `.csproj` project) ✅

Built on `NxtControl.GuiFramework` (C#, WinForms-Designer-like model):

| File | Role |
|---|---|
| `<Canvas>.cnv.cs` / `.cnv.Designer.cs` / `.cnv.resx` | Canvas (screen): code-behind / designer-generated layout (`InitializeComponent`) / resources |
| `<Cat>/<Cat>_<sym>.cnv.*` + `.cnv.xml` | CAT symbol (`sDefault`, `sPR`, …). `.cnv.xml` is the symbol's event/var mapping |
| `<Cat>/<Cat>_f<Name>.cnv.*` | Faceplate (`IsFaceplate="true"` in `.cfg`) |
| `<Cat>/<Cat>.def.cs`, `.event.cs` | **Generated** from `_HMI.fbt` (accessors, EventArgs). Never edit by hand |
| `<Cat>/<Cat>.Design.resx` | Design resources |
| `CanvasesResolutionList.xml`, `GraphicsList.xml`, `Colors/`, `Theme/`, `Alarms/AlarmClasses.xml`, `Languages/` | Global configuration |

Designer code pattern (`*.cnv.Designer.cs`): field declarations plus `InitializeComponent()` that instantiates objects (`NxtControl.GuiFramework.Rectangle/Label/RoundedRectangle/Group`, CAT symbols such as `HMI.Main.Symbols.acPPC_v1_0.sDefault`, library symbols such as `SE.Agile.Symbols.HMI_Indication_Real_v1_0.sValChanged`) and sets properties (`Bounds`, `Brush`, `Pen`, `Font`, `Text`, `DesignMatrix`, `TagName`, …).

Binding: a symbol on a canvas has `TagName = "<FB instance ID in the layer>"`. A nested symbol inside a CAT symbol uses `TagName = "<sub-CAT name>"` ✅.

## 6. eHMI (`WEB/`, `.htmlproj` project) ✅

TypeScript + JSON with a web runtime (`NxtControl.GuiFramework` on the JS side):

| File | Role |
|---|---|
| `<Cat>/<Cat>_<sym>.sym.json` | Symbol layout: `{"objects":[{type,name,left,top,width,height,…}], "_design_":…}` |
| `<Cat>/<Cat>_<sym>.sym.ts` | Symbol logic: `class extends NxtControl.GuiFramework.RuntimeSymbol` |
| `<Cat>/<Cat>_<sym>.sym.xml` | Mapping (may be empty) |
| `<Cat>/<Cat>_<sym>.user.cs` | C# partial class stub (`NxtControl.GuiHTMLFramework`) |
| `<deviceId>/<Canvas>.cnv.json` / `.cnv.ts` / `.user.cs` | **Canvases are per device** |
| `<deviceId>/WebCanvasesResolutionList.xml` | Canvas navigation, resolution, start canvas |
| Root-level `*.sym.json/.sym.ts` | Reusable graphics (`WEB.Main.Graphics.*`) |
| `*.spt.ts` | Support classes (TS helpers) registered in `WebGraphicsList.xml` |

Object types observed: `NxtControl.GuiFramework.{Rectangle, FreeText, Ellipse, ImageShape}`, CAT symbols `WEB.Main.Symbols.<Cat>.<sym>`, library symbols `SE.Agile.Symbols.<Cat>.<sym>`.

Binding: `"tagName": "<FB instance ID>"` on canvases, or `"<sub-CAT name>"` inside a symbol ✅.

`WEB.htmlproj` properties: `<WEBLibraries>WebBaseSymbols:WebBaseSymbolsExtended:</WEBLibraries>`, `<CanvasSize>`.

---

## 7. Files to never modify / ignore

| Path | Reason |
|---|---|
| `IEC61499/SnapshotCompiles/**` (`.bin`, `.hash`, `.rhash`, `.bthash`, `.baseId`) | Compile cache (~10 MB). Only Buildtime writes it |
| `General/Security/*.db`, `cae-model-*.json`, `se-rbac-*.json`, `General/Certificates`, `Topology/Content/*_DeviceCertificate` | Security. **Never read contents, never log, never include in fixtures** |
| `PluginData/ChangeHistory_*.json` | Agile plugin history |
| `*.def.cs`, `*.event.cs` (HMI) | Generated |
| `nxtDataType` attribute | Blob generated by Buildtime |
