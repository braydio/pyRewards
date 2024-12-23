@echo off
REM Navigate to the project directory
cd "C:\Users\chaff\Documents\Python\projects\rewardsMS"

REM Activate the virtual environment
call .venv\Scripts\activate

REM Run the Python script
python pyRewards.py

REM Pause to keep the command window open after execution
pause
