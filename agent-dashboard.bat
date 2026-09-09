@echo off
title Agentic AI Developer
echo.
echo  ==========================================
echo   Agentic AI Developer - Dashboard
echo  ==========================================
echo.

if "%ANTHROPIC_API_KEY%"=="" (
    echo  ERROR: ANTHROPIC_API_KEY set nahi hai.
    echo.
    echo  PowerShell mein ye chalayein, phir dobara koshish karein:
    echo    $env:ANTHROPIC_API_KEY="sk-ant-..."
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
echo  Browser khul raha hai...
echo  Band karne ke liye yeh window close karein.
echo.
python -m agentic_dev.server --workspace "%CD%"
pause
