# SignalForge and Scanner — Complete Windows PowerShell Commands

This guide assumes the scanner and SignalForge repositories are separate folders. **Run every command from the correct directory shown below.** Do not use the placeholder `C:\path\to\...` literally.

The commands are paper-only. They do not submit orders, connect to a broker, or enable live trading.

## 1. Open PowerShell and choose one root directory

Open **PowerShell**. The following uses:

```text
C:\Users\<your-Windows-user>\TradingTools
```

PowerShell commands:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ProjectRoot = Join-Path $env:USERPROFILE "TradingTools"
$ScannerDir = Join-Path $ProjectRoot "scan-and-alert-"
$SignalForgeDir = Join-Path $ProjectRoot "AI-signal"

New-Item -ItemType Directory -Force -Path $ProjectRoot | Out-Null
Set-Location $ProjectRoot
Get-Location
```

To use a different folder, change only `$ProjectRoot`. For example:

```powershell
$ProjectRoot = "D:\TradingTools"
$ScannerDir = Join-Path $ProjectRoot "scan-and-alert-"
$SignalForgeDir = Join-Path $ProjectRoot "AI-signal"
New-Item -ItemType Directory -Force -Path $ProjectRoot | Out-Null
Set-Location $ProjectRoot
```

## 2. Find existing repositories instead of cloning duplicates

Run this first:

```powershell
Get-ChildItem -Path $env:USERPROFILE -Directory -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -in @("scan-and-alert-", "AI-signal") } |
  Select-Object -ExpandProperty FullName
```

If the repositories already exist, set the variables to their **real** paths:

```powershell
$ScannerDir = "C:\Users\<your-Windows-user>\TradingTools\scan-and-alert-"
$SignalForgeDir = "C:\Users\<your-Windows-user>\TradingTools\AI-signal"

Test-Path $ScannerDir
Test-Path $SignalForgeDir
```

Both commands should return `True`.

## 3. Clone the repositories if they do not exist

Only run the clone command for a repository whose directory does not already exist:

```powershell
Set-Location $ProjectRoot

gh repo clone mennaelammal-prog/scan-and-alert- $ScannerDir
gh repo clone mennaelammal-prog/AI-signal $SignalForgeDir
```

If `gh` is unavailable, install GitHub CLI or clone using Git:

```powershell
git clone https://github.com/mennaelammal-prog/scan-and-alert-.git $ScannerDir
git clone https://github.com/mennaelammal-prog/AI-signal.git $SignalForgeDir
```

Verify both folders:

```powershell
Get-ChildItem $ScannerDir
Get-ChildItem $SignalForgeDir
```

## 4. Select the implemented scanner branch

The scanner repository's default `main` branch is not the implementation branch. After cloning, switch to:

```text
claude/quirky-darwin-kh12ms
```

Run:

```powershell
Set-Location $ScannerDir
git fetch origin
git switch -C claude/quirky-darwin-kh12ms origin/claude/quirky-darwin-kh12ms
git branch --show-current
Test-Path .\pyproject.toml
```

Expected output:

```text
claude/quirky-darwin-kh12ms
True
```

If `Test-Path .\pyproject.toml` returns `False`, stop. The wrong branch is still checked out.

## 5. Set up and test the scanner repository

The scanner directory is `$ScannerDir`. **Change into it before running scanner commands.**

```powershell
Set-Location $ScannerDir
Get-Location

.\scripts\setup.ps1
.\scripts\migrate.ps1
.\scripts\test.ps1
```

If PowerShell blocks the scripts, run this in the same PowerShell window first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Check the scanner paper configuration:

```powershell
.\.venv\Scripts\Activate.ps1
python -m scanalert check-config
```

The configuration must report paper mode. The scanner must not have live credentials, live broker URLs, or a live-trading flag.

## 6. Start the scanner in PowerShell window 1

Keep this PowerShell window open:

```powershell
Set-Location $ScannerDir
.\.venv\Scripts\Activate.ps1

$env:TRADING_MODE = "paper"
$env:HOST = "127.0.0.1"
$env:PORT = "8000"
$env:DATA_PROVIDER = "fixture"
$env:FIXTURE_REPLAY_SPEED = "30"

python -m scanalert serve --host 127.0.0.1 --port 8000
```

The scanner should be available at:

```text
http://127.0.0.1:8000/ui/
```

In a second PowerShell window, check its health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 10
```

The response must include:

```text
paper_only = True
trading_mode = paper
```

Check the read-only alert endpoint:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/alerts?status=triggered&limit=10" |
  ConvertTo-Json -Depth 20
```

## 7. Set up SignalForge in PowerShell window 2

Open a second PowerShell window. Set the directories again because variables do not automatically transfer between windows:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ProjectRoot = Join-Path $env:USERPROFILE "TradingTools"
$SignalForgeDir = Join-Path $ProjectRoot "AI-signal"

Set-Location $SignalForgeDir
Get-Location
```

Create the SignalForge virtual environment and install it:

```powershell
# Python 3.12 is valid. Do not require the unavailable py -3.11 launcher.
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Confirm the correct repository and installation:

```powershell
Get-Location
Get-ChildItem
python --version
Get-Command signalforge
```

If the `signalforge` command is not found, use the module form in every command instead:

```powershell
python -m signalforge.cli --help
```

## 8. Run SignalForge tests and quality checks

Run these from the **AI-signal directory**, not the scanner directory:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

python -m pytest -q
python -m ruff check src tests
python -m compileall -q src
```

All tests should pass before connecting to the scanner.

## 9. Create the data directory and strategy-evidence file

Still from `$SignalForgeDir`:

```powershell
Set-Location $SignalForgeDir
New-Item -ItemType Directory -Force -Path .\data | Out-Null
```

Create a starter version-matched strategy-evidence file:

```powershell
@'
[
  {
    "strategy_id": "opening-range-breakout",
    "strategy_version": 3,
    "sample_size": 120,
    "expectancy_r": 0.42,
    "win_rate": 0.58,
    "profit_factor": 1.7,
    "max_drawdown_r": 2.0,
    "out_of_sample_expectancy_r": 0.25,
    "recent_expectancy_r": 0.31,
    "regime_expectancy_r": {
      "trending_up": 0.5
    },
    "time_bucket_expectancy": {
      "morning": 0.4
    }
  }
]
'@ | Set-Content -Encoding UTF8 .\data\strategy-stats.json

Get-Content .\data\strategy-stats.json
```

Replace this example with properly calculated, point-in-time strategy evidence before using the results for research. Do not calculate evidence using bars after the signal timestamp.

## 10. One-shot poll from the scanner

Run this from the **AI-signal directory**:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

signalforge poll `
  --scanner-url http://127.0.0.1:8000 `
  --stats .\data\strategy-stats.json `
  --db .\data\signalforge.db `
  --status triggered `
  --limit 100
```

If the command is not recognized, use:

```powershell
python -m signalforge.cli poll `
  --scanner-url http://127.0.0.1:8000 `
  --stats .\data\strategy-stats.json `
  --db .\data\signalforge.db `
  --status triggered `
  --limit 100
```

This performs a GET-only read from `/api/alerts`, stores ranked results in SQLite, and prints hypothetical paper signals.

## 11. Continuous watcher

Run this from the **AI-signal directory**:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

signalforge watch `
  --scanner-url http://127.0.0.1:8000 `
  --stats .\data\strategy-stats.json `
  --db .\data\signalforge.db `
  --interval 15 `
  --cycles 20
```

For continuous mode, omit `--cycles`:

```powershell
signalforge watch `
  --scanner-url http://127.0.0.1:8000 `
  --stats .\data\strategy-stats.json `
  --db .\data\signalforge.db `
  --interval 15
```

Stop it with:

```text
Ctrl+C
```

The watcher checks `/health` before every cycle and refuses to poll if the scanner is not paper-only.

## 12. Start the SignalForge read-only dashboard

Open another PowerShell window and set the SignalForge directory again:

```powershell
$ProjectRoot = Join-Path $env:USERPROFILE "TradingTools"
$SignalForgeDir = Join-Path $ProjectRoot "AI-signal"
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

signalforge serve `
  --db .\data\signalforge.db `
  --host 127.0.0.1 `
  --port 8765
```

Open this URL in the browser:

```text
http://127.0.0.1:8765/
```

Read-only JSON endpoints:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/summary | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:8765/api/signals | ConvertTo-Json -Depth 20
```

The dashboard must show:

```text
PAPER ONLY — HYPOTHETICAL SIGNALS — NOT ORDERS
```

## 13. Generate the descriptive paper report

From the **AI-signal directory**:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

signalforge report --db .\data\signalforge.db
```

Save the report to a file:

```powershell
signalforge report --db .\data\signalforge.db |
  Tee-Object -FilePath .\data\paper-report.json
```

## 14. Run leakage and walk-forward validation

The validation command requires ranked signal JSON and paper-outcome JSON exports:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1

signalforge validate `
  --signals .\data\ranked-signals.json `
  --outcomes .\data\paper-outcomes.json `
  --start 2026-01-01 `
  --end 2026-03-31 `
  --train-days 20 `
  --test-days 5
```

The validation output must be inspected for:

```text
lookahead_errors: []
clean: true
paper_only: true
```

## 15. Check which directory PowerShell is using

If a command fails with “path not found” or “file not found”, run:

```powershell
Get-Location
Get-ChildItem
Test-Path $ScannerDir
Test-Path $SignalForgeDir
```

Expected locations:

```powershell
Set-Location $ScannerDir
Get-Location
# ...\TradingTools\scan-and-alert-

Set-Location $SignalForgeDir
Get-Location
# ...\TradingTools\AI-signal
```

## 16. Check ports and stop processes

Check the scanner port:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

Check the SignalForge dashboard port:

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
```

Find the owning process:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object OwningProcess

Get-NetTCPConnection -LocalPort 8765 -State Listen |
  Select-Object OwningProcess

Get-Process -Id <PID>
```

Stop only the process you started for this local paper application:

```powershell
Stop-Process -Id <PID> -Force
```

Do not stop an unknown process.

## 17. Common errors

### `Cannot find path 'C:\path\to\scan-and-alert-'`

That path was only a placeholder. Set the actual directory first:

```powershell
$ScannerDir = "C:\Users\<your-Windows-user>\TradingTools\scan-and-alert-"
Set-Location $ScannerDir
Get-Location
```

### `No suitable Python runtime found` for `py -3.11`

Your Windows installation has Python 3.12. Python 3.12 satisfies the scanner and SignalForge requirement. Use:

```powershell
Set-Location $ScannerDir
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Do not use `py -3.11` unless `py -0p` shows that Python 3.11 is installed.

### `does not appear to be a Python project`

The scanner is probably still on the default documentation branch. Switch branches:

```powershell
Set-Location $ScannerDir
git fetch origin
git switch -C claude/quirky-darwin-kh12ms origin/claude/quirky-darwin-kh12ms
Test-Path .\pyproject.toml
```

The final command must return `True`.

### `signalforge is not recognized`

Activate the correct SignalForge environment and use the module form:

```powershell
Set-Location $SignalForgeDir
.\.venv\Scripts\Activate.ps1
python -m signalforge.cli --help
```

### `Virtual environment missing`

Run from the correct repository directory:

```powershell
Set-Location $SignalForgeDir
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Scanner health refuses polling

Check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 10
```

SignalForge intentionally refuses to poll unless the health response reports both:

```text
paper_only = True
trading_mode = paper
```

### Port already in use

Use another local dashboard port:

```powershell
signalforge serve --db .\data\signalforge.db --host 127.0.0.1 --port 8766
```

Then open:

```text
http://127.0.0.1:8766/
```

### Database is locked

Only one writer should use a SQLite database at a time. Stop duplicate watcher or poll processes, then rerun:

```powershell
Get-Process python -ErrorAction SilentlyContinue
```

## 18. Safety rules

- Keep `$env:TRADING_MODE = "paper"`.
- Keep the scanner bound to `127.0.0.1` for local use.
- Do not add live brokerage credentials.
- Do not add live broker URLs.
- Do not change `paper_only` or `hypothetical` to `false`.
- Do not treat quality score as a probability or recommendation.
- Do not expose ports publicly without authentication and TLS.
- Stop the watcher with `Ctrl+C` when finished.
