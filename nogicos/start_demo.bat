@echo off
:: ============================================================
:: NogicOS Demo Launcher
:: ============================================================
:: Double-click to start NogicOS
::
:: This script:
:: 1. Checks Python and Node.js
:: 2. Installs dependencies if needed
:: 3. Starts the Electron app (which auto-starts Python server)
:: ============================================================

echo.
echo ============================================================
echo   NogicOS - AI Browser Demo
echo   "The more you use, the faster it gets"
echo ============================================================
echo.

:: Change to script directory
cd /d "%~dp0"

:: Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)
echo       Python OK

:: Check Node.js
echo [2/4] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
echo       Node.js OK

:: Check Python dependencies
echo [3/4] Checking Python dependencies...
python -c "import fastapi; import uvicorn; import playwright" >nul 2>&1
if errorlevel 1 (
    echo       Installing Python dependencies...
    pip install fastapi uvicorn playwright langchain-anthropic langgraph websockets -q
    playwright install chromium
)
echo       Dependencies OK

:: Check Node dependencies
echo [4/4] Checking Node dependencies...
if not exist "client\node_modules" (
    echo       Installing Node dependencies...
    cd client
    call npm install --silent
    cd ..
)
echo       Dependencies OK

echo.
echo ============================================================
echo   Starting NogicOS...
echo ============================================================
echo.
echo   HTTP API:  http://localhost:8080
echo   WebSocket: ws://localhost:8765
echo.
echo   Press Ctrl+C to stop
echo.
echo ============================================================
echo.

:: Start Electron (which will start Python server)
cd client
call npm start

:: If npm start fails, show error
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start NogicOS
    pause
)

