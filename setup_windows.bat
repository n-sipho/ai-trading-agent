@echo off
echo Setting up Python environment for mt5_agent...

REM Create a virtual environment named .mt5_agent
python -m venv .mt5_agent

REM Activate the virtual environment
call .mt5_agent\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip

REM Install dependencies from requirements.txt
echo Installing requirements...
pip install -r requirements.txt

echo.
echo Setup complete!
echo To run your bot, use: python hello_world.py
cmd /k
