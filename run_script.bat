@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" pyRewards.py --interactive
) else (
    py -3 pyRewards.py --interactive
)

echo.
pause
