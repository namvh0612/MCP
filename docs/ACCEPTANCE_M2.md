# M2 Acceptance Test in EAE 26

> Goal: prove that files created or edited by eae-mcp **open and compile in EAE 26**.
> Time: about 30 minutes. Work on a **copy** of `EAE_MCP_Golden`.

## 1. Prepare (once)

```powershell
cd C:\Tools\eae-mcp
git pull
.venv\Scripts\pip install -e .
Copy-Item C:\EAE\EAE_MCP_Golden C:\EAE\EAE_MCP_M2 -Recurse
```

In `eae-mcp.toml` set `allow_write = true` under `[project]`, then restart the MCP client (Claude Desktop/Code).

## 2. Ask Claude to make these changes (close EAE first)

Ask in plain words, for example: *"Open C:\EAE\EAE_MCP_M2 and create a Basic FB fbPI …"*. Claude shows a dry-run diff first, then writes when you confirm.

| # | Request to Claude | Tool used |
|---|---|---|
| A1 | Create adapter `aM2` with input event `REQ` (with `X : INT`) and output event `CNF` (with `Y : INT`) in folder `.M2` | `eae_adapter_create` |
| A2 | Create enum `dtM2Mode` (USINT): `Idle=0`, `Busy=1`, `Error=2` and struct `dtM2Point` with `X : REAL`, `Y : REAL` in folder `.M2` | `eae_datatype_create` |
| A3 | Create Basic FB `fbM2PI` with INIT/INITO (QI/QO), REQ (SP, PV : REAL) → CNF (OUT : REAL), internal `Kp : REAL := 1.0`, states Init/Run, algorithm `Calc`: `OUT := Kp * (SP - PV);`, in folder `.M2` | `eae_basic_create` |
| A4 | Add input variable `Ki : REAL` to `fbM2PI` and add it to REQ's WITH list | `eae_fb_update_interface` |
| A5 | Change algorithm `Calc` of `fbTest` to `OUT1 := IN1 * IN2;` | `eae_basic_upsert_algorithm` |
| A6 | Add state `Clear` to `fbTest` (action `Init` → `INITO`), with transitions `START → Clear` on `INIT AND NOT QI` and `Clear → START` on `1` | `eae_basic_update_ecc` |
| A7 | Run `eae_validate` on the whole solution | `eae_validate` |

## 3. Check in EAE

Open `C:\EAE\EAE_MCP_M2` in EAE 26 and record each result in `notes.txt`:

| # | Check | Pass? |
|---|---|---|
| B1 | Solution opens without errors or "file missing" warnings | ☐ |
| B2 | `aM2`, `dtM2Mode`, `dtM2Point`, `fbM2PI` appear under folder `M2` in their categories | ☐ |
| B3 | Each new type opens in its editor (adapter interface, DataType ST text, Basic FB interface/ECC/algorithm) | ☐ |
| B4 | `fbM2PI`: ECC shows START, Init, Run with transitions; `Ki` is in REQ's WITH | ☐ |
| B5 | `fbTest`: `Calc` shows the new code; state `Clear` exists; `cfbTest` and `catTest` still show `fbTest` wired as before | ☐ |
| B6 | **Tools › Recheck All** finishes without errors (copy the Output window into `M2_output.txt`) | ☐ |
| B7 | Place `fbM2PI` in a composite or the application, connect it, Save All: EAE accepts it | ☐ |
| B8 | Close EAE, zip `C:\EAE\EAE_MCP_M2` as `M2_after_eae.zip` (shows what EAE rewrote on save) | ☐ |

## 4. Send back

`notes.txt`, `M2_output.txt`, screenshots of anything that failed, `M2_after_eae.zip`.
