# M3–M5 Acceptance Test in EAE 26

> Goal: prove that networks, CATs, OPC UA exposure, eHMI and .NET HMI edits made by eae-mcp **open,
> build and run in EAE 26**. One session covers M3, M4 and M5.
> Time: about 45 minutes. Work on a **copy** of `EAE_MCP_Golden`. Close EAE while Claude writes.

## 1. Prepare (once)

```powershell
cd C:\Tools\eae-mcp
git pull
.venv\Scripts\pip install -e .
Copy-Item C:\EAE\EAE_MCP_Golden C:\EAE\EAE_MCP_M5 -Recurse
```

Keep `allow_write = true` under `[project]` in `eae-mcp.toml`, then restart the MCP client (VS Code /
Claude Desktop / Claude Code) so the new tools load. `eae_catalog_build` must have run once (M3).

## 2. Ask Claude to make these changes (EAE closed)

Ask in plain words, e.g. *"Open C:\EAE\EAE_MCP_M5 and create a CAT catPump …"*. Claude shows a dry-run
diff first; confirm to write. Do the steps in order.

| # | Request to Claude | Tool used |
|---|---|---|
| D1 | Create CAT `catPump` in folder `.M5`, default CAT interface. HMI interface: input event `REQ` with `Value : INT`; output event `CMD` with `Start : BOOL` | `eae_cat_create` |
| D2 | In `catPump`: add `FB1 : fbTest`; connect `INIT → FB1.INIT`, `REQ → FB1.REQ`, `FB1.CNF → IThis.REQ`, `FB1.OUT1 → IThis.Value`, `IThis.INITO → INITO` | `eae_net_add_fb`, `eae_net_connect` |
| D3 | In `catPump`: add a sub-CAT `Sub1 : catTest` | `eae_net_add_fb` (adds `<SubCAT>`) |
| D4 | Add to `catPump`: .NET symbol `sBig`, .NET faceplate `fMain`, eHMI symbol `seBig` | `eae_cat_add_symbol` |
| D5 | Add `PUMP1 : catPump` to `APP1` and map it to `EcoRT_0/RES0` | `eae_net_add_fb`, `eae_map_to_resource` |
| D6 | Expose `PUMP1.IThis.Value` on OPC UA | `eae_opcua_expose` |
| D7 | Create eHMI canvas `Pumps` on device `EcoRT_0` and place `PUMP1` on it | `eae_ehmi_canvas_create`, `eae_ehmi_place_symbol` |
| D8 | Create .NET HMI canvas `Pumps` and place `PUMP1` at x=40, y=40 | `eae_hmi_canvas_create`, `eae_hmi_place_symbol` |
| D9 | Move `CAT1` on .NET canvas `Canvas1` to x=200, y=100 | `eae_hmi_update_object` |
| D10 | Run `eae_validate` on the whole solution | `eae_validate` |

| D11 | Prompt `design_hmi_from_description` with: "catPump: Value is the flow 0–100 m3/h, normal 30–70, low alarm 10, high alarm 90 (high priority)" — Claude runs `eae_hmi_design_suggest` and `eae_hmi_symbol_build` for catPump | `eae_hmi_symbol_build` |
| D12 | Build display `PumpsSA` (level 2, section "Pumps" with PUMP1) for hmi and for ehmi on EcoRT_0 | `eae_hmi_display_build` |

Before opening EAE, zip `C:\EAE\EAE_MCP_M5` as `M5_before_eae.zip`.

## 3. Check in EAE

Open `C:\EAE\EAE_MCP_M5` in EAE 26 and record each result in `notes.txt`:

| # | Check | Pass? |
|---|---|---|
| E1 | Solution opens without errors or "file missing" warnings | ☐ |
| E2 | `catPump` is under CAT folder `M5`; its HMI interface (`IThis`) shows `Value` and `Start` | ☐ |
| E3 | `catPump` network shows `IThis`, `FB1`, `Sub1` with the D2 wiring | ☐ |
| E4 | `catPump` lists symbols `sDefault`, `sBig`, faceplate `fMain`, eHMI `seDefault`, `seBig`; each opens in its editor | ☐ |
| E5 | `APP1` shows `PUMP1`, mapped to `RES0` | ☐ |
| E6 | OPC UA configuration (System or the CAT) shows `PUMP1 › IThis › Value` exposed | ☐ |
| E7 | eHMI canvas `Pumps` exists under `EcoRT_0` and shows the `PUMP1` symbol | ☐ |
| E8 | .NET canvas `Pumps` shows `PUMP1`; `CAT1` on `Canvas1` moved to (200, 100) | ☐ |
| E9 | **Tools › Recheck All** without errors (copy the Output window into `M5_output.txt`) | ☐ |
| E10 | **HMI › Build** and **eHMI › Build** without errors (append to `M5_output.txt`) | ☐ |
| E11 | Optional: deploy to the simulator; `Value` appears on both canvases and in an OPC UA client | ☐ |
| E13 | catPump symbols `sSA` / `seSA` open in their editors (gray card, label, value, span with shaded normal band and limit ticks) | ☐ |
| E14 | HMI › Build and eHMI › Build compile the generated code-behind (.cnv.cs / .sym.ts) without errors | ☐ |
| E15 | Runtime (simulator): the pointer moves with Value; above 90 it turns orange and widens; an alarm shows shape + color + number | ☐ |
| E16 | Displays `PumpsSA` (HMI and eHMI) show the title, the "Pumps" group and PUMP1 | ☐ |
| E12 | Draw something in `sBig` and `seBig`, Save All, close EAE, zip as `M5_after_eae.zip` | ☐ |

## 4. Send back

`notes.txt`, `M5_output.txt`, screenshots of anything that failed, `M5_before_eae.zip`, `M5_after_eae.zip`
(the diff between the two zips shows what EAE rewrote on save).
