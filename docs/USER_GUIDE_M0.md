# M0 User Guide — Producing Golden Files in EAE 26

> **Who:** the EAE user on the Windows machine.
> **Goal:** create small, known components in EAE so the MCP server can learn exactly which files EAE writes and how. These "golden files" gate every write feature of the MCP server (M2 and later).
> **Time:** about 2–3 hours in total. Steps can be done and sent in batches.
> **Note:** EAE menu names below are descriptive. If a label differs in your EAE 26 UI, use the equivalent command and note the real name in `notes.txt`.

---

## Part A — One-time setup (10 min)

| # | Do this | Done |
|---|---|---|
| A1 | Create a folder for deliverables: `%USERPROFILE%\Desktop\EAE_Golden` | ☐ |
| A2 | Create an empty text file `EAE_Golden\notes.txt`. You will write short observations there, per step | ☐ |
| A3 | Open **PowerShell** (not as admin) and keep it open. All commands below are PowerShell | ☐ |
| A4 | Set two variables (re-run them if you reopen PowerShell):<br>`$G = "$env:USERPROFILE\Desktop\EAE_Golden"`<br>`$S = "C:\EAE\EAE_MCP_Golden"` | ☐ |

**How to zip after each step** (always **Save All and close EAE first**, otherwise files are locked):
```powershell
Compress-Archive -Path $S -DestinationPath "$G\C<n>_<name>.zip" -Force
```
**Screenshots:** press `Win + Shift + S`, capture, then save into `$G` as `C<n>_<description>.png`.

---

## Part B — Steps

Do the steps **in order**, all in the **same** solution `EAE_MCP_Golden`. Each step builds on the previous one, so the server can diff consecutive zips.

### C0 — Empty baseline (5 min)
1. Start EAE Buildtime 26.0 → **File › New › Solution**. Name `EAE_MCP_Golden`, location `C:\EAE`.
2. Accept defaults. Do **not** add anything.
3. Screenshot the Solution Explorer → `C0_solution_explorer.png`.
4. **Save All**, close EAE.
5. `Compress-Archive -Path $S -DestinationPath "$G\C0_empty.zip" -Force`

☐ Done

### C1 — Inventory of the EAE installation (5 min, no EAE needed)
Run in PowerShell:
```powershell
$I = "C:\Program Files\Schneider Electric\EcoStruxure Automation Expert - Buildtime 26.0"
Get-ChildItem $I -Recurse -Include *.exe | Select-Object -Expand FullName > "$G\C1_exes.txt"
Get-ChildItem $I -Recurse -Include *.fbt,*.adp,*.dt,*.fct,*.dfbproj | Select-Object -Expand FullName > "$G\C1_types.txt"
Get-ChildItem $I -Recurse -Include *.dll | Select-Object -Expand FullName > "$G\C1_dlls.txt"
Get-ChildItem $I -Directory | Select-Object -Expand Name > "$G\C1_topdirs.txt"
```
Then find the main Buildtime executable (the one the Start-menu shortcut points to: right-click the shortcut › Open file location) and run:
```powershell
& "<full path to that exe>" /? 2>&1 > "$G\C1_help.txt"
```
If a window opens instead of printing help, close it and write "no CLI help" in `notes.txt`.

☐ Done

### C1b — Inventory of the system library store (5 min, no EAE needed)
System libraries (`E_CYCLE`, `E_DELAY`, `Soft_dPAC`, …) live in `C:\ProgramData\Schneider Electric\Libraries\<Lib>-<Version>\Files\<Namespace>\`. Run:
```powershell
$L = "C:\ProgramData\Schneider Electric\Libraries"
Get-ChildItem $L -Directory | Select-Object -Expand Name > "$G\C1b_packages.txt"
Get-ChildItem $L -Recurse -File | ForEach-Object { $_.FullName.Substring($L.Length + 1) } > "$G\C1b_files.txt"
Copy-Item "$L\Runtime.Base-26.0.0.7\Files\IEC61499.Standard\E_CYCLE.fbt" "$G\C1b_E_CYCLE.fbt"
```
If the folder version differs from `26.0.0.7`, adjust the last line.

☐ Done

### C2 — Adapter (10 min)
1. Open `EAE_MCP_Golden`. In the IEC61499 project: **Add › New Item › Adapter**, name `aTest`.
2. Interface:
   - Event output `REQ` with `With` → data output `ReqValue : INT`
   - Event input `CNF` with `With` → data input `CnfValue : INT`
3. Screenshot the adapter editor → `C2_adapter_editor.png`.
4. Save All, close EAE, zip as `C2_adapter.zip`.

☐ Done

### C3 — DataTypes + the `nxtDataType` experiment (15 min)
1. Open the solution. **Add › New Item › DataType** → `dtStruct`, a structure with fields `A : INT`, `B : REAL`, `C : STRING[20]`.
2. **Add › New Item › DataType** → `dtEnum`, an enumeration with values `Off = 0`, `On = 1`, `Fault = 2`.
3. Screenshot both editors → `C3_struct.png`, `C3_enum.png`.
4. Save All, close EAE, zip as `C3_datatypes.zip`.
5. **Experiment:** open `C:\EAE\EAE_MCP_Golden\IEC61499\dtStruct.dt` (the path may differ) in Notepad. Delete the whole line `<Attribute Name="nxtDataType" … />`, save.
6. Open the solution in EAE. Write in `notes.txt` what happened: error, warning, or nothing? Open `dtStruct`, Save All, close EAE.
7. Open `dtStruct.dt` again in Notepad: is the `nxtDataType` line back? Write the answer in `notes.txt`.
8. Zip as `C3_nxtDataType_experiment.zip`.

☐ Done

### C3b — Other DataType kinds (5 min)
1. Open **Add › New Item › DataType** and screenshot the dialog with all available kinds → `C3b_dialog.png`.
2. If **Array**, **Alias** or **Subrange** exist, create one each (`dtArray` = 10 × INT, `dtAlias` = alias of REAL, `dtRange` = INT 0..100).
3. Save All, close EAE, zip as `C3b_more_datatypes.zip`.

☐ Done

### C4 — SubApp (15 min)
1. **Add › New Item › SubApplication** (typed SubApp) → `subTest`.
2. Inside: add 2 FBs (e.g. `E_DELAY` and `E_PERMIT`), connect them with one event connection, add 1 event input pin and 1 event output pin on the boundary, and connect them.
3. Open the Application (`APP1`) in System. Create an **untyped** SubApp there (select 2 FBs › right-click › Create SubApplication, or the equivalent).
4. Screenshots → `C4_subapp_type.png`, `C4_untyped_subapp.png`.
5. Save All, close EAE, zip as `C4_subapp.zip`.

☐ Done

### C5 — Basic FB (20 min)
1. **Add › New Item › Basic FB** → `fbTest`.
2. Interface:
   - Event inputs: `INIT` (with `QI : BOOL`), `REQ` (with `IN1 : INT`, `IN2 : INT`)
   - Event outputs: `INITO` (with `QO : BOOL`), `CNF` (with `OUT1 : INT`, `OUT2 : BOOL`)
   - Internal var: `Counter : INT`
3. ECC with 3 states:
   - `START`
   - `Init` (action: algorithm `Init`, output `INITO`)
   - `Run` (action: algorithm `Calc`, output `CNF`)

   Transitions: `START → Init` on `INIT`; `START → Run` on `REQ`; `Init → START` on `1`; `Run → START` on `1`.
4. Algorithms (ST):
   - `Init`: `QO := QI; Counter := 0;`
   - `Calc`: `Counter := Counter + 1; OUT1 := IN1 + IN2; OUT2 := OUT1 > 100;`
5. Screenshots → `C5_interface.png`, `C5_ecc.png`, `C5_algorithm.png`.
6. Save All, close EAE, zip as `C5_basicfb.zip`.

☐ Done

### C6 — Composite FB (15 min)
1. **Add › New Item › Composite FB** → `cfbTest`.
2. Interface: event in `REQ`, event out `CNF`, data in `X : INT`, data out `Y : INT`, plus one **adapter output** (socket) of type `aTest`.
3. Inside: one `fbTest` instance and one `E_DELAY` instance.
   - Event connections: `REQ → fbTest.REQ`, `fbTest.CNF → E_DELAY.START`, `E_DELAY.EO → CNF`.
   - Data connections: `X → fbTest.IN1`, `fbTest.OUT1 → Y`.
   - Parameters: set `fbTest.IN2 = 5` and `E_DELAY.DT = T#1s`.
4. Screenshot → `C6_network.png`.
5. Save All, close EAE, zip as `C6_composite.zip`.

☐ Done

### C7 — CAT with .NET HMI and eHMI symbols (30 min)
1. **Add › New Item › CAT** → `catTest`. Use the default wizard options and screenshot every wizard page → `C7_wizard_1.png`, `C7_wizard_2.png`, ….
2. In the CAT's FB network, place one `fbTest` and connect it minimally (e.g. CAT `REQ` → `fbTest.REQ`).
3. **.NET HMI symbol:** open the CAT's default symbol (`sDefault`). Add one rectangle, one label, and a value display bound to `OUT1`. Screenshot → `C7_hmi_symbol.png`.
4. **Faceplate:** add a faceplate (e.g. `fMain`) with one label. Screenshot → `C7_hmi_faceplate.png`.
5. **eHMI symbol:** add a web/eHMI symbol for the CAT (e.g. `seDefault`) with one rectangle and one text bound to `OUT1`. Screenshot → `C7_ehmi_symbol.png`.
6. Save All, close EAE, zip as `C7_cat.zip`.

☐ Done

### C7b — Solution Explorer folders (25 min)
**Background (from SolarPlantDemo):** folders in Solution Explorer appear to be *logical*, not physical directories:
- Each type category (Basic, Composite, CAT, Adapter, …) has its **own** folder tree.
- Folders are named as dotted paths (`.Standard.IO`).
- They are listed in `General\Folders.xml`, and a type is placed by `<Parent>.Standard.IO</Parent>` in `.dfbproj`. A CAT also has `Folder="…"` in its `.cfg`.

These sub-steps confirm it. **Zip after each sub-step**, so every diff shows exactly one operation. Take one Solution Explorer screenshot per sub-step (`C7b_F<n>.png`).

| # | Action in EAE | Zip as |
|---|---|---|
| F1 | Under the **Basic FB** category node, create an **empty** folder `Logic` (right-click › Add Folder, or equivalent). Do not move anything into it | `C7b_F1_empty_folder.zip` |
| F2 | Move `fbTest` into `Logic` (drag & drop or Move to Folder) | `C7b_F2_move_basic.zip` |
| F3 | Inside `Logic`, create subfolder `Sub` and move `fbTest` into `Logic › Sub` | `C7b_F3_nested.zip` |
| F4 | Create a folder `Logic` in **each** of the other categories you have (Adapter, DataType, SubApp, Composite, CAT). Move `aTest`, `dtStruct`, `subTest`, `cfbTest`, `catTest` into them. If a category does not allow folders, write that in `notes.txt` | `C7b_F4_other_categories.zip` |
| F5 | Rename the Basic folder `Logic` to `Core` (its subfolder `Sub` stays inside) | `C7b_F5_rename.zip` |
| F6 | Move `fbTest` back to the Basic category root, then delete the empty folders `Core › Sub` and `Core` | `C7b_F6_delete.zip` |
| F7 | In **System › Devices**, create a folder `Line1` and move the device `EcoRT_0` into it | `C7b_F7_device_folder.zip` |

In `notes.txt`, record:
- the exact menu command used to create, rename and delete a folder;
- whether Windows Explorer shows any **new physical directory** under `C:\EAE\EAE_MCP_Golden\IEC61499` after F1–F4;
- any category that refused folders, or any error message.

Leave the other types inside their `Logic` folders. C8 works with them there.

☐ Done

### C8 — System: instance, mapping, canvases, OPC UA (30 min)
1. In System › Application `APP1`: drop one instance of `catTest`, name `CAT1`.
2. Make sure a **Soft dPAC** device with resource `RES0` exists (add one if not). Map `CAT1` to `RES0`.
3. **.NET HMI canvas:** create a canvas `TestCanvas` and drop `CAT1`'s symbol on it.
4. **eHMI canvas:** for the Soft dPAC device, create an eHMI canvas `TestWebCanvas` and drop `CAT1`'s eHMI symbol on it.
5. **OPC UA:** expose `OUT1` of `CAT1` via OPC UA (read access).
6. Screenshots → `C8_application.png`, `C8_mapping.png`, `C8_hmi_canvas.png`, `C8_ehmi_canvas.png`, `C8_opcua.png`.
7. Save All, close EAE, zip as `C8_system.zip`.

☐ Done

### C9 — Build (10 min)
1. Open the solution and **Build › Build Solution**.
2. Screenshot the Output window and the Error List → `C9_output.png`, `C9_errors.png`.
3. Copy the full text of the Output window into `C9_output.txt`.
4. Close EAE and look for log files written in the last 2 hours. The search covers only Schneider/EAE-related folders, because a full recursive scan of `LOCALAPPDATA`/`PROGRAMDATA` can take a very long time:
   ```powershell
   $t = (Get-Date).AddHours(-2)
   $roots = @(Get-ChildItem $env:LOCALAPPDATA, $env:APPDATA, $env:PROGRAMDATA -Directory -ErrorAction SilentlyContinue |
     Where-Object Name -match 'Schneider|nxt|EcoStruxure|EAE' | Select-Object -ExpandProperty FullName) + $S
   $roots | Out-File "$G\C9_logroots.txt" -Encoding utf8
   Get-ChildItem $roots -Recurse -File -Filter *.log -ErrorAction SilentlyContinue |
     Where-Object { $_.LastWriteTime -gt $t } |
     Select-Object -ExpandProperty FullName | Out-File "$G\C9_logs.txt" -Encoding utf8
   ```
   If `C9_logs.txt` is empty, write "no recent logs" in `notes.txt`.
5. Zip as `C9_built.zip`.

☐ Done

### C10 — Screenshots of SolarPlantDemo for the concept docs (20 min)
Open `SolarPlantDemo` and capture:

| File | View |
|---|---|
| `C10_solution_explorer.png` | Solution Explorer, all projects expanded one level |
| `C10_cat_acPPC_network.png` | CAT `acPPC_v1_0`, FB network |
| `C10_fbPPC_ecc.png` | Basic FB `fbPPC_v1_0`, ECC |
| `C10_fbPPC_algorithm.png` | Basic FB `fbPPC_v1_0`, one algorithm |
| `C10_adapter_aGrid.png` | Adapter `aGrid_v1_0` |
| `C10_app_layer.png` | Application `APP1`, default layer |
| `C10_resource_mapping.png` | Device `EcoRT_0` › `RES0` |
| `C10_device_properties.png` | Device `EcoRT_0` properties |
| `C10_hmi_controlpage.png` | .NET HMI canvas `ControlPage` |
| `C10_ehmi_controlpage.png` | eHMI canvas `ControlPage` |

☐ Done

### C11 — File-lock experiment (5 min)
1. Open `EAE_MCP_Golden` in EAE and **leave it open**.
2. In Notepad, open `fbTest.fbt` and change the `Comment="…"` text of the `FBType` element. Try to save. Did Notepad report the file as locked? Write the answer in `notes.txt`.
3. If the save succeeded, switch back to EAE. Did EAE offer to reload the file? Screenshot any dialog → `C11_reload.png`. Write the result in `notes.txt`.
4. Close EAE **without saving**.

☐ Done

---

## Part C — Sending the results

1. Send files in batches as you finish them. Suggested batches:
   - **Batch 1:** C0, C1, C2, C3, C3b
   - **Batch 2:** C4, C5, C6
   - **Batch 3:** C7, C7b, C8, C9 (+ C1b, C1c, C3c, C4b follow-ups)
   - **Batch 4:** C10, C11, `notes.txt`
2. Attach the files in the chat with Claude, or zip a batch: `Compress-Archive -Path "$G\*" -DestinationPath "$env:USERPROFILE\Desktop\EAE_Golden_batch1.zip"`.
3. **Do not** include anything from `General\Security`, certificates or real customer projects.

## Part D — What happens with each batch

| Batch | The server team (Claude) will |
|---|---|
| 1 | Build the system-type catalog from C1. Enable Adapter and DataType write tools, and resolve the `nxtDataType` question |
| 2 | Enable SubApp, Basic FB and Composite write tools, with golden tests against C4–C6 |
| 3 | Enable CAT, mapping, .NET HMI and eHMI write tools. Assess build automation from C9 |
| 4 | Write the English concept docs with your screenshots. Implement the "EAE is open" write guard |

## Tracker

| Step | Zip / files | Screenshots | Sent |
|---|---|---|---|
| C0 | `C0_empty.zip` | 1 | ☐ |
| C1 | `C1_*.txt` (5) | — | ☐ |
| C1b | `C1b_packages.txt`, `C1b_files.txt`, `C1b_E_CYCLE.fbt` | — | ☐ |
| C2 | `C2_adapter.zip` | 1 | ☐ |
| C3 | `C3_datatypes.zip`, `C3_nxtDataType_experiment.zip` | 2 | ☐ |
| C3b | `C3b_more_datatypes.zip` | 1 | ☐ |
| C4 | `C4_subapp.zip` | 2 | ☐ |
| C5 | `C5_basicfb.zip` | 3 | ☐ |
| C6 | `C6_composite.zip` | 1 | ☐ |
| C7 | `C7_cat.zip` | 4+ | ☐ |
| C7b | `C7b_F1…F7_*.zip` (7) | 7 | ☐ |
| C8 | `C8_system.zip` | 5 | ☐ |
| C9 | `C9_built.zip`, `C9_output.txt`, `C9_logs.txt` | 2 | ☐ |
| C10 | — | 10 | ☐ |
| C11 | — (notes) | 0–1 | ☐ |
| — | `notes.txt` | — | ☐ |
