@echo off
echo Checking virtual environment...

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing requirements...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting MegaETH Bot...
python main.py
pause
