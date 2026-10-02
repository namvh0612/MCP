# CAT — Composite Automation Type

A CAT is the EAE unit of reuse for **equipment**: a composite FB packaged with everything an operator needs.

## Files (catTest example; ~24 files in 3 projects)
| Project | Files | Role |
|---|---|---|
| IEC61499 | `catTest/catTest.fbt` | The composite FB (`Comment="CAT Function Block Type"`, `Format="2.0"`) |
| | `catTest/catTest.cfg` | **Manifest**: sub-CATs, HMI interface, `<Symbol>` (.NET) and `<WebSymbol>` (eHMI), plugin files, logical folder |
| | `catTest/catTest_HMI.fbt` | **HMI interface SIFB** (instance `IThis`): its inputs are the values shown in HMI, its outputs come back from HMI |
| | `_CAT.offline.xml`, `_HMI.offline.xml` | Offline parametrization |
| | `_CAT.opcua.xml`, `_HMI.opcua.xml` | OPC UA exposure per variable |
| HMI | `catTest/catTest_sDefault.cnv.*` | .NET symbol; `.cnv.xml` mirrors the HMI interface |
| | `catTest/catTest.def.cs`, `.event.cs`, `.Design.resx` | Generated from `_HMI.fbt` — never edit |
| WEB | `catTest/catTest_seDefault.sym.{json,ts,xml}`, `.user.cs` | eHMI symbol |

## How data reaches the HMI
1. Add the variable (e.g. `OUT1 : INT`) to `catTest_HMI` and associate it with an event (`REQ WITH OUT1`).
2. In the CAT network, `IThis.QI = TRUE` and trigger `IThis.INIT`.
3. Wire the value to `IThis.OUT1` and fire `IThis.REQ` when it changes.
4. In the symbols, bind a widget with `TagName`/`tagName = "OUT1"`.

## Sub-CATs and the Agile pattern (SolarPlantDemo)
`acPPC_v1_0` = `fbPPC_v1_0` (Basic FB with the logic) + `HMI_Indication_*`/`HMI_Control_*` sub-CATs (one per HMI value) + `Broadcaster*`/`Listener*` CATs (publish/subscribe between equipment over adapters and MQTT) + `InitComponent`/`GetAssetName` helpers. Symbols bind sub-CATs by name (`"EXPLIM"`) or dotted path (`"Plant.Broadcaster_v1_0"`).
