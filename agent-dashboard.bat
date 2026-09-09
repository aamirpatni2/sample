@echo off
setlocal
title Agentic AI Developer
cd /d "%~dp0"

echo.
echo  ============================================
echo    Agentic AI Developer
echo  ============================================
echo.

REM Python must be on PATH. Installing it without "Add to PATH" is the usual cause.
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python nahi mila.
    echo.
    echo  python.org/downloads se install karein.
    echo  Install karte waqt "Add Python to PATH" pe TICK zaroor lagayein.
    echo.
    pause
    exit /b 1
)

REM Dependencies. Quiet when already present, so a normal launch stays clean.
python -c "import anthropic, fastapi, uvicorn, websockets" >nul 2>&1
if errorlevel 1 (
    echo  Zaroori packages install ho rahe hain, ek dafa...
    python -m pip install -q anthropic python-dotenv fastapi uvicorn websockets
    if errorlevel 1 (
        echo  Install nahi ho saka. Internet check karein.
        pause
        exit /b 1
    )
    echo  Ho gaya.
    echo.
)

REM A key set for the whole account persists; otherwise ask for one now. This is
REM why the dashboard can be launched by double-click with no terminal setup.
if not "%ANTHROPIC_API_KEY%"=="" goto :launch

if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        if "%%a"=="ANTHROPIC_API_KEY" set "ANTHROPIC_API_KEY=%%b"
    )
)
if not "%ANTHROPIC_API_KEY%"=="" goto :launch

echo  API key chahiye.
echo  console.anthropic.com/settings/keys se le sakte hain.
echo.
set /p "ANTHROPIC_API_KEY=  Key yahan paste karein (right-click = paste): "
echo.

if "%ANTHROPIC_API_KEY%"=="" (
    echo  Koi key nahi di gayi.
    pause
    exit /b 1
)

REM Save it so this is a one-time step. .env is gitignored.
echo ANTHROPIC_API_KEY=%ANTHROPIC_API_KEY%>> .env
echo  Key .env mein save ho gayi - agli baar nahi poochunga.
echo.

:launch
echo  Browser khul raha hai...
echo  Band karne ke liye yeh window close karein.
echo.
python -m agentic_dev.server --workspace "%CD%"
pause
