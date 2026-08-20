@echo off
title AI News Agent
echo.
echo  ===============================
echo   AI News Agent - Starting...
echo  ===============================
echo.
cd /d "%~dp0backend"
timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:8000"
echo  Server chal raha hai: http://127.0.0.1:8000
echo  Band karne ke liye yeh window close karo.
echo.
uvicorn main:app --port 8000
