@echo off
setlocal
title Reset API key
cd /d "%~dp0"

echo.
echo  ============================================
echo    API key reset
echo  ============================================
echo.

if exist ".env" (
    findstr /v /b "ANTHROPIC_API_KEY=" .env > .env.tmp 2>nul
    move /y .env.tmp .env >nul 2>&1
    echo  Purani key hata di gayi.
) else (
    echo  Koi purani key nahi thi.
)

echo.
echo  Nayi key console.anthropic.com/settings/keys se banayein.
echo.
set /p "NEWKEY=  Nayi key yahan paste karein (right-click = paste): "

if "%NEWKEY%"=="" (
    echo.
    echo  Koi key nahi di gayi. Kuch save nahi hua.
    pause
    exit /b 1
)

echo ANTHROPIC_API_KEY=%NEWKEY%>> .env
echo.
echo  Nayi key save ho gayi.
echo  Ab agent-dashboard.bat chalayein.
echo.
pause
