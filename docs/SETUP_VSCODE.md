# Setting up a test environment in VS Code (Windows)

Step-by-step guide to run and test **eae-mcp** on the Windows machine where EAE 26 is installed.
Estimated time: 20–30 minutes the first time.

The repository already contains the VS Code configuration:

| File | Used by |
|---|---|
| `.vscode/settings.json` | Python extension: interpreter `.venv`, pytest in `tests/` |
| `.vscode/extensions.json` | Recommended extensions (Python, Claude Code) |
| `.mcp.json` | Claude Code: registers the `eae` MCP server for this folder |
| `.vscode/mcp.json` | VS Code's built-in MCP support (GitHub Copilot agent mode) |
| `eae-mcp.example.toml` | Template for your local `eae-mcp.toml` (not committed) |

---

## Step 1 — Install the prerequisites (once)

Open **PowerShell** and run:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id Microsoft.VisualStudioCode -e
```

Close and reopen PowerShell, then check:

```powershell
git --version
py -3.12 --version        # Python 3.12.x
```

> If `winget` is blocked by company policy, install the same three programs from their websites.
> When installing Python manually, tick **"Add python.exe to PATH"**.

## Step 2 — Get the code

```powershell
mkdir C:\Tools -Force
cd C:\Tools
git clone -b claude/epic-planck-ts8mgl https://github.com/namvh0612/MCP eae-mcp
code C:\Tools\eae-mcp
```

The repository is private, so Git will open a browser window to sign in to GitHub the first time.

> Keep the code **outside OneDrive** (e.g. `C:\Tools`). OneDrive sync can lock files inside `.venv`.

In VS Code:
1. When asked **"Do you trust the authors of the files in this folder?"**, click **Yes, I trust the authors**.
2. When the popup **"Do you want to install the recommended extensions?"** appears, click **Install**. This installs Python and Claude Code. You can also install them from the Extensions view (`Ctrl+Shift+X`).

## Step 3 — Create the Python environment

Open the VS Code terminal (`` Ctrl+` ``). It is PowerShell by default. Run:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

Then select the interpreter:
1. Press `Ctrl+Shift+P`.
2. Choose **Python: Select Interpreter**.
3. Pick `.venv\Scripts\python.exe` (marked *Recommended*).

> **Behind a company proxy?** If `pip install` times out, run:
> `.venv\Scripts\python -m pip config set global.proxy http://<proxy-host>:<port>` and retry.
>
> **"running scripts is disabled on this system"** when the terminal activates `.venv`? Run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. The commands above work either way,
> because they call `.venv\Scripts\python` directly.

## Step 4 — Run the automated tests

**Option A — Testing view**
1. Click the beaker icon in the left bar.
2. If asked, choose **pytest** and the folder **tests**.
3. Click **Run Tests** (▷▷).

**Option B — Terminal**

```powershell
.venv\Scripts\python -m pytest
```

Expected result: **`59 passed`**. These tests use the fixtures in `tests/fixtures`, not your own projects.

## Step 5 — Create your configuration

```powershell
Copy-Item eae-mcp.example.toml eae-mcp.toml
code eae-mcp.toml
```

Edit it so it reads:

```toml
[project]
roots = ["C:/EAE"]          # the server may only open solutions under this folder
allow_write = false         # keep false until the acceptance test (Step 9)

[eae]
version = "26.0"
library_store = "C:/ProgramData/Schneider Electric/Libraries"

[server]
transport = "stdio"
```

Check that the server starts:

```powershell
.venv\Scripts\eae-mcp.exe --help
```

## Step 6 — Connect an MCP client

Choose **one** of the options below.

### Option A — Claude Code in VS Code (recommended)

1. Open the Claude Code panel (Claude icon in the left or top bar) and sign in.
2. Claude Code reads `.mcp.json` from the folder and asks whether to enable the project server **eae**. Approve it.
3. Type `/mcp` in the Claude Code panel. **eae** must show as *connected*, with 25 tools.

If `eae` shows as *failed*, register it with absolute paths instead:

```powershell
claude mcp add eae --scope local -- C:\Tools\eae-mcp\.venv\Scripts\eae-mcp.exe --config C:\Tools\eae-mcp\eae-mcp.toml
```

### Option B — GitHub Copilot Chat (agent mode)

1. Press `Ctrl+Shift+P` and choose **MCP: List Servers**. **eae** comes from `.vscode/mcp.json`; click **Start**.
2. Open Copilot Chat, switch the mode to **Agent**, and click the tools icon. The `eae_*` tools must be listed.

### Option C — MCP Inspector (manual tool testing, no AI)

This option needs Node.js (`winget install OpenJS.NodeJS.LTS`). Then run:

```powershell
npx @modelcontextprotocol/inspector .venv\Scripts\eae-mcp.exe --config eae-mcp.toml
```

A browser page opens.
1. Click **Connect**, then **Tools › List Tools**.
2. Call `eae_open_solution` with `{"path": "C:/EAE/EAE_MCP_Golden"}`.

## Step 7 — Smoke test (read-only)

Ask the client (Claude Code or Copilot agent) these questions, one at a time:

1. *"List the EAE solutions."* → uses `eae_list_solutions`. `EAE_MCP_Golden` must appear.
2. *"Open C:\EAE\EAE_MCP_Golden and give me a summary."* → 11 types, system with `EcoRT_0 (Soft_dPAC)`.
3. *"Build the library catalog for this solution."* → `eae_catalog_build`. This writes `C:\EAE\EAE_MCP_Golden\.eae-mcp\catalog.json` and should report several thousand library types.
4. *"Explain CAT1."* → type `catTest`, runs on `EcoRT_0/RES0`, shown on the HMI and eHMI canvas `Canvas1`.
5. *"Trace Canvas1 down to the algorithms."* → canvas → `CAT1` → `catTest` → `FB1 (fbTest)` → `Init, Calc`.
6. *"Validate the whole solution."* → 0 errors.
7. Repeat 2–6 with SolarPlantDemo, e.g. *"Explain PPC001"*, *"Describe the CAT acPPC_v1_0"*.

Write down anything wrong or surprising in `notes.txt`.

## Step 8 — Learning mode (optional)

- *"Use the learn_component prompt for acPPC_v1_0."*
- *"Read eae://concepts/cat and explain it with an example from this solution."*
- *"Make a documentation scaffold for fbTest."* → `eae_doc_scaffold` (Markdown with `[SCREENSHOT: …]` placeholders).

## Step 9 — Prepare for the M2 write test

1. Make a working copy, so the golden solution stays untouched:
   ```powershell
   Copy-Item C:\EAE\EAE_MCP_Golden C:\EAE\EAE_MCP_M2 -Recurse
   ```
2. In `eae-mcp.toml`, set `allow_write = true`.
3. Restart the server:
   - Claude Code: `/mcp` → **eae** → **Reconnect**.
   - Copilot: **MCP: List Servers** → **eae** → **Restart**.
4. Continue with **`docs/ACCEPTANCE_M2.md`**.

Every write tool first shows a dry-run diff. Only confirm when the diff looks right.

## Step 10 — Getting updates

```powershell
cd C:\Tools\eae-mcp
git pull
.venv\Scripts\python -m pip install -e ".[dev]"     # only needed when dependencies changed
.venv\Scripts\python -m pytest
```

Then restart the MCP server (Step 9.3).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `py` not found | Reinstall Python with "Add to PATH", or use the full path `C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe` |
| `pip install` hangs or fails with SSL errors | Company proxy: see Step 3. Ask IT for the proxy address if needed |
| Tests fail on `solar_demo.zip` | Make sure `git clone` completed; the zip is 4.8 MB in `tests/fixtures` |
| `/mcp` shows **eae** failed | Run `.venv\Scripts\eae-mcp.exe --config eae-mcp.toml` in the terminal. Python errors show there; press `Ctrl+C` to stop. Then try the `claude mcp add` command in Step 6 |
| "outside the configured project roots" | Add the folder to `roots` in `eae-mcp.toml` and restart the server |
| "Writing is disabled" | Set `allow_write = true` and restart the server (Step 9) |
| Problems panel: `MSB4019 … SharpDevelop.Build.CSharp.Standard.targets was not found` in `tests/fixtures/…/HMI.csproj` | Harmless. The C# Dev Kit extension tries to build the EAE test projects, which need EAE's build targets. `.vscode/settings.json` disables this (`dotnet.defaultSolution: disable`). Run **Developer: Reload Window** (`Ctrl+Shift+P`) and the error disappears. You can also disable C# Dev Kit for this workspace |
| Library types show as "not found" | Run `eae_catalog_build` once (Step 7.3) |
| EAE does not show a change made by the MCP | EAE reloads automatically; if not, close and reopen the solution, then run **Tools › Check Changes** |
