# pyRewards

A small Python/Selenium learning project for **inspecting the Microsoft Rewards dashboard** and optionally opening individual activities **for you to complete manually**. It retains the original Microsoft Edge workflow, but is easier to run, debug, and extend.

## What changed in v2

- Finds cards from the page rather than assuming three daily cards and 18 more-activity slots.
- Distinguishes **completed**, **available**, **unknown**, and **redeem** cards. Unknown never means collected.
- Correctly detects new tabs and returns to the dashboard, without closing tabs that existed beforehand.
- Uses Selenium Manager, so there is no separate EdgeDriver-manager dependency.
- Uses a dedicated persistent browser profile for manual sign-in. No cookie-export script or passwords in source code.
- Supports Edge and Chrome on Windows/Linux/macOS where Selenium supports them.
- Produces a local JSON status report without storing account IDs, card URLs, or cookies.
- Provides unit tests and GitHub Actions CI.

## Quick start

Python **3.10+** and **Microsoft Edge** (or Chrome) are needed.

```powershell
git clone https://github.com/braydio/pyRewards.git
cd pyRewards
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python pyRewards.py
```

On Linux/macOS, activate with `source .venv/bin/activate` and use `python pyRewards.py`.

On Windows, `run_script.bat` runs interactive mode using `.venv` if present, or the Windows Python launcher otherwise.

### Modes

```bash
# Read-only inspection and status report (default)
python pyRewards.py

# Ask before opening each eligible card; complete activities yourself
python pyRewards.py --interactive

# Use Chrome instead of Edge
python pyRewards.py --browser chrome --interactive

# Custom report location and browser launch timeout
python pyRewards.py --report runs/today.json --timeout 25
```

The first launch starts a **separate browser profile** in `~/.pyrewards/browser-profile`. Sign in to Microsoft there when needed, then press Enter in the terminal if the dashboard needs to be rechecked. Keep this profile private. Do not point `--profile-dir` at a profile currently open in another browser process.

Reports are written to `runs/latest.json` by default and ignored by Git.

## How status detection works

The scraper checks Rewards dashboard card containers and the status icons or accessibility labels found inside them. Microsoft's page is not a stable public API. If it changes, some cards can appear as **unknown** or none may be found. Update `SECTION_SELECTORS` in `pyrewards/core.py` after inspecting the new DOM. An opened activity is **never** reported as earned or completed unless its observed dashboard status indicates completion.

## Program rules and limitations

Microsoft Rewards requires genuine activity. **Bot/macro-generated searches do not count as valid Rewards searches**, and automated patterns can result in earning limitations or suspension. This tool does **not** generate Bing searches, automate quizzes, bypass authentication, or promise to collect points. Interactive mode deliberately asks you before each action. Check Microsoft's [Rewards terms](https://www.microsoft.com/en/servicesagreement) before using any automation.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q pyRewards.py bingPypett.py pyrewards tests
```

The older `bingPypett.py` entry point is retained as a compatibility shim; its raw-cookie-storage prototype was retired.

## Troubleshooting

- **No cards discovered:** Check that you are signed in, the dashboard has loaded, and the CSS selectors still match the current page.
- **Browser fails to start:** Update Selenium and the installed browser, and verify the dedicated browser profile isn't locked by another process.
- **Card remains unknown:** The dashboard did not expose a recognized completion marker. This does not imply it was collected.
- **Opening a card fails:** The page may have reordered the cards; rerun inspection instead of blindly clicking a different link.
