# pyRewards

A small Python/Selenium learning project for **inspecting the Microsoft Rewards dashboard** and optionally opening individual activities **for you to complete manually**. It retains the original Microsoft Edge workflow, but is easier to run, debug, and extend.

## Open a numbered range of cards in separate tabs

Use `--skip N --open M` to skip the first N positions in pyRewards' **numbered list**, then automatically open the next M cards. No prompts are required for individual cards in this mode.

```powershell
# Skip #1-#4, then open #5, #6, and #7 in three independent tabs
.\.venv\Scripts\python.exe pyRewards.py --skip 4 --open 3

# Same selection, also run the recognized legacy quiz state machine in each tab
.\.venv\Scripts\python.exe pyRewards.py --skip 4 --open 3 --run-quizzes
```

The numbering is exactly what pyRewards prints in its initial snapshot, starting at **1**. Completed, redeem, or nonclickable cards still count toward the requested positions but are reported as skipped; they are not silently replaced with later cards. If there are fewer cards than requested, only the existing positions are considered.

A fresh browser tab opens the dashboard for **each** card, and its activity tab stays open while the next card is processed. If the card itself opens another tab, pyRewards keeps the resulting activity tab and closes its temporary launcher. It leaves all selected activity tabs open at the end until you press Enter in PowerShell; then Selenium shuts down. The JSON report has `selection` and `open_results` with positions and outcomes, without activity URLs.

`--open` and `--interactive` are alternative modes. `--run-quizzes` can be added to either one. The automated quiz runner can submit real interactions to Microsoft Rewards, regardless of whether you use it for tracking.

## Optional quiz navigation (restored from the 2024 exercise)

This project originally had `start_quiz()`, `take_quiz()`, and `get_current_question()` functions for Bing's legacy Supersonic quiz interface. The new `pyrewards/quiz.py` restores and hardens that flow as a bounded, opt-in exercise.

On Windows, from the project directory:

```powershell
.\.venv\Scripts\python.exe pyRewards.py --interactive --run-quizzes
```

Choose **o** for a card. After the card opens in Edge, the script searches for known quiz controls (`rqStartQuiz`, `rqHeaderCredits`, `rqAnswerOptionN`, `quizCompleteContainer`). If found, it starts the quiz, clicks answers in numeric order, and checks whether the original filled-circle progress indicator advances before proceeding. You can **watch each click** using the default 0.7-second pause. The tool does not generate Bing searches, attempt verification challenges, or guess controls on unsupported pages.

```powershell
# Slower, easy-to-observe clicks and a stricter per-quiz question limit
.\.venv\Scripts\python.exe pyRewards.py --interactive --run-quizzes --quiz-pause 1.5 --max-quiz-questions 10
```

**Tracking:** The `runs/latest.json` report now includes `quiz_runs` with question progress, attempted option IDs, and terminal statuses: `completed`, `not_quiz`, `unsupported`, `stalled`, `limit_reached`, or `error`. No raw page HTML, cookies, or activity URLs are logged. **Completed is reported only when the quiz's completion marker appears**, not merely when an option is clicked.

The legacy IDs are not a guaranteed description of today's Rewards interface; an unrecognized quiz will stop with `unsupported`. This has been unit-tested using a simulated quiz state machine, **not live-tested against your account**.

## What changed in v2

- Finds cards dynamically, including newer React tiles with `p.text-globalBody2Strong` titles and `+10` badges, rather than assuming fixed legacy card counts.
- Distinguishes **completed**, **available**, **unknown**, and **redeem** cards. Unknown never means collected.
- Opens the enclosing link/button when available, or clicks the tile body for React event handlers, after an explicit interactive prompt.
- Re-identifies cards by title before clicking, to avoid opening a different card if the dashboard reorders.
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

Microsoft Rewards requires genuine activity. **Bot/macro-generated searches do not count as valid Rewards searches**, and automated patterns can result in earning limitations or suspension. This tool does **not** generate Bing searches, bypass authentication, or promise to collect points. Quiz interactions are opt-in via `--interactive --run-quizzes` and may affect your live Rewards account even if you are only studying the Selenium behavior. Review the program rules before running it. Check Microsoft's [Rewards terms](https://www.microsoft.com/en/servicesagreement) before using any automation.

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
- **Quiz not detected:** The opened tab may not contain the older `rq*` quiz controls. The runner logs `not_quiz` or `unsupported`, and won't click unrelated content.
- **Quiz stalls:** No observable filled-circle or question-text change occurred after trying supported options. This is logged as `stalled` rather than looping forever.
- **Opening a card fails:** The script refuses ambiguous duplicate titles or changed URLs rather than clicking a different activity. The tile itself or its wrapper may still be inaccessible depending on the dashboard's JavaScript.
- **New cards not shown:** The newer React layout uses `div.p-paddingCardBodyDefaultOutside` containing `p.text-globalBody2Strong`. If that changes again, update `SECTION_SELECTORS` and `MODERN_CARD_TITLE_SELECTOR` in `pyrewards/core.py`.
