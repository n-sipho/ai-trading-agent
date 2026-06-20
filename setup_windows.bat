@echo off
echo ========================================
echo   SMC Trading Assistant - Full Setup
echo ========================================
echo.

REM === Step 1: Python Backend Setup ===
echo [1/4] Setting up Python virtual environment...
if not exist .mt5_agent (
    python -m venv .mt5_agent
)

echo [2/4] Activating environment and installing backend dependencies...
call .mt5_agent\Scripts\activate

pip install -r backend\requirements.txt
pip install -r requirements.txt

REM === Step 2: Frontend Setup ===
echo [3/4] Installing frontend dependencies...
cd frontend
call npm install
cd ..

REM === Step 3: Environment File ===
echo [4/4] Setting up .env file...
if not exist .env (
    copy .env-example .env
    echo Created .env file from template. Please edit it with your credentials!
) else (
    echo .env file already exists, skipping.
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To start the app:
echo   1. Start the backend:
echo      .mt5_agent\Scripts\activate
echo      cd backend
echo      python run.py
echo.
echo   2. Start the frontend (new terminal):
echo      cd frontend
echo      npm run dev
echo.
echo   3. (Optional) Start the quote server:
echo      metatrader-quote-server --login YOUR_LOGIN --password YOUR_PASS --server YOUR_SERVER --symbols "EURUSD,XAUUSD"
echo.
pause
