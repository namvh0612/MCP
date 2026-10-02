# Changelog

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
