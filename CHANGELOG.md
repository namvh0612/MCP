# Changelog

## Unreleased

- **Library knowledge:** `eae_library_guide` (ranked drill-down), `eae_generic_fbs` (generic FB registry with
  pins learned from connections; add generic FBs by template + parameters), `eae_knowledge` (section search),
  knowledge docs `standard-library` (IEC 61499 E_*, EAE runtime blocks, generic templates, path macros) and
  an expanded `function`. Parser now keeps VAR_IN_OUT and variable type namespaces.
- **Functions:** `eae_function_create` / `eae_function_update` (identical to EAE 26 output).
- **SA HMI generation:** `eae_hmi_design_suggest`, `eae_hmi_symbol_build`, `eae_hmi_display_build` and the
  prompt `design_hmi_from_description`: symbols and displays drawn to ISA-101 / High Performance HMI rules
  (gray graphics, moving analog indicators with normal band and limits, color + shape + number alarm
  indicators, colors only at runtime when abnormal), for .NET HMI and eHMI. Generated C# compiles against
  EAE API stubs, TypeScript passes tsc, and every result passes `eae_hmi_review`.
- **REST clients:** knowledge `rest-client` (SolarPlantDemo ElectricPriceUpdate analysed),
  `eae_rest_client_create` (generated CAT + FBs + function, ST verified with a simulator in tests),
  `eae_http_probe` (opt-in, GET/HEAD, allowed hosts only, token never returned); built-in table of generic FB
  types (`knowledge/generic_types.json`) so NETIO etc. can be added to any solution.
- **HMI design:** knowledge doc `hmi-design` (Endsley SA, ISA-101 hierarchy, High Performance HMI, ISA-18.2),
  `eae_hmi_review` (HP-01…10, NAV-01…03, ALM-01…05 + manual checks), prompt `design_hmi_sa`.

## 0.5.0 — 2026-10-02

Write support for every component, pending acceptance in EAE 26 (docs/ACCEPTANCE_M5.md).

- **M5 .NET HMI:** create canvases, place CAT symbols (bound by instance ID), move/update/remove objects
  through a constrained `InitializeComponent()` code model that round-trips every EAE-written file.
- **M4 CAT and eHMI:** create CATs like EAE's "New CAT" (IThis, `.cfg`, companions, .NET + eHMI symbols,
  generated `.event.cs`/`.def.cs` byte-identical to EAE's); add symbols/faceplates; sub-CAT bookkeeping;
  IThis changes regenerate code and mappings; OPC UA expose/unexpose; eHMI canvases and symbol placement.
- **M3 networks:** Composite and SubApp creation, add/remove FBs, connect/disconnect, parameters,
  resource mapping.

## 0.2.0 — 2026-10-02

- **M2:** create/edit Adapter, DataType, Basic FB; `eae_validate`; dry-run diffs, backups, audit log.

## 0.1.0 — 2026-10-02

- **M1:** read-only server: solution index, library catalog, explain/trace, HMI/eHMI readers, knowledge layer.
