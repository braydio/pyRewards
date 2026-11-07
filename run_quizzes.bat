@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" pyRewards.py --interactive --run-quizzes
) else (
    py -3 pyRewards.py --interactive --run-quizzes
)
echo.
pause
