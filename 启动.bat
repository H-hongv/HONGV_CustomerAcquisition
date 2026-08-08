@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ========================================
echo   WaiMao HuoKe v4.0
echo ========================================
echo.

REM Use the project venv Python when available (fallback: system python)
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

"%PY%" main.py
if errorlevel 1 (
    echo.
    echo ========================================
    echo   Qi Dong Shi Bai
    echo ========================================
    echo.
    echo Qing jian cha:
    echo   "%PY%" -m pip install -r requirements.txt
    pause
)
endlocal
